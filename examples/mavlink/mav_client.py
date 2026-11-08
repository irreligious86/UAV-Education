"""Reliable MAVLink client helpers on top of pymavlink: commands with ACK and retries,
parameters, and the mission upload/download microservice with per-item retransmission.

Used by the `mav-services` lab. Every function returns or raises — no silent "hope".
"""
from __future__ import annotations

import time

from pymavlink import mavutil

M = mavutil.mavlink


def connect(url: str, sysid: int = 255, timeout: float = 10.0):
    m = mavutil.mavlink_connection(url, source_system=sysid, source_component=M.MAV_COMP_ID_MISSIONPLANNER)
    # a udpin peer learns our address only from our first packet: announce ourselves until it answers
    deadline = time.time() + timeout
    while time.time() < deadline:
        m.mav.heartbeat_send(M.MAV_TYPE_GCS, M.MAV_AUTOPILOT_INVALID, 0, 0, M.MAV_STATE_ACTIVE)
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
        if hb is not None and hb.get_srcComponent() == M.MAV_COMP_ID_AUTOPILOT1:
            m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
            return m
    raise TimeoutError("no HEARTBEAT")


def command(m, cmd: int, *params, retries: int = 5, timeout: float = 0.5) -> int:
    """COMMAND_LONG with confirmation counter and retries. Returns MAV_RESULT on ACCEPTED, raises otherwise."""
    p = list(params) + [0.0] * (7 - len(params))
    for attempt in range(retries):
        m.mav.command_long_send(m.target_system, m.target_component, cmd, attempt, *p)
        deadline = time.time() + timeout
        while time.time() < deadline:
            ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=max(0.0, deadline - time.time()))
            if ack is None or ack.command != cmd:
                continue
            if ack.result == M.MAV_RESULT_IN_PROGRESS:
                deadline = time.time() + timeout
                continue
            if ack.result == M.MAV_RESULT_ACCEPTED:
                return ack.result
            raise RuntimeError(f"command {cmd} rejected: result {ack.result}")
    raise TimeoutError(f"command {cmd}: no ACK after {retries} tries")


def _pid(name: str) -> bytes:
    return name.encode()[:16]


def param_get(m, name: str, retries: int = 5, timeout: float = 0.5) -> float:
    for _ in range(retries):
        m.mav.param_request_read_send(m.target_system, m.target_component, _pid(name), -1)
        deadline = time.time() + timeout
        while time.time() < deadline:
            pv = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=max(0.0, deadline - time.time()))
            if pv is not None and pv.param_id.rstrip("\x00") == name:
                return float(pv.param_value)
    raise TimeoutError(f"param {name}: no PARAM_VALUE")


def param_set(m, name: str, value: float, retries: int = 5, timeout: float = 0.5) -> float:
    """PARAM_SET is confirmed by a PARAM_VALUE echo with the new value (there is no ACK message)."""
    for _ in range(retries):
        m.mav.param_set_send(m.target_system, m.target_component, _pid(name), float(value), M.MAV_PARAM_TYPE_REAL32)
        deadline = time.time() + timeout
        while time.time() < deadline:
            pv = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=max(0.0, deadline - time.time()))
            if pv is not None and pv.param_id.rstrip("\x00") == name and abs(pv.param_value - value) < 1e-4:
                return float(pv.param_value)
    raise TimeoutError(f"param {name}: set not confirmed")


def waypoint(seq: int, lat: float, lon: float, alt: float, cmd: int = M.MAV_CMD_NAV_WAYPOINT) -> dict:
    return {"seq": seq, "frame": M.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, "command": cmd, "current": 0, "autocontinue": 1,
            "params": (0.0, 0.0, 0.0, 0.0), "x": int(lat * 1e7), "y": int(lon * 1e7), "z": float(alt)}


def mission_upload(m, items: list[dict], timeout: float = 1.0, max_retries: int = 10) -> None:
    """Upload: MISSION_COUNT → (MISSION_REQUEST_INT seq → MISSION_ITEM_INT)* → MISSION_ACK.
    The vehicle drives the dialogue; we resend COUNT if it stays silent, and answer duplicate requests."""
    retries = 0
    m.mav.mission_count_send(m.target_system, m.target_component, len(items))
    while True:
        msg = m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True, timeout=timeout)
        if msg is None:
            retries += 1
            if retries > max_retries:
                raise TimeoutError("mission upload: vehicle stopped responding")
            m.mav.mission_count_send(m.target_system, m.target_component, len(items))   # restart is safe: it resets the transaction
            continue
        if msg.get_type() == "MISSION_ACK":
            if msg.type != M.MAV_MISSION_ACCEPTED:
                raise RuntimeError(f"mission rejected: {msg.type}")
            return
        it = items[msg.seq]
        m.mav.mission_item_int_send(m.target_system, m.target_component, it["seq"], it["frame"], it["command"], it["current"],
                                    it["autocontinue"], *it["params"], it["x"], it["y"], it["z"])


def mission_download(m, timeout: float = 1.0, max_retries: int = 10) -> list:
    retries = 0
    count = None
    while count is None:
        m.mav.mission_request_list_send(m.target_system, m.target_component)
        msg = m.recv_match(type="MISSION_COUNT", blocking=True, timeout=timeout)
        if msg is not None:
            count = msg.count
        else:
            retries += 1
            if retries > max_retries:
                raise TimeoutError("mission download: no MISSION_COUNT")
    items = []
    seq = 0
    while seq < count:
        m.mav.mission_request_int_send(m.target_system, m.target_component, seq)
        msg = m.recv_match(type="MISSION_ITEM_INT", blocking=True, timeout=timeout)
        if msg is None or msg.seq != seq:
            retries += 1
            if retries > max_retries:
                raise TimeoutError(f"mission download: item {seq} lost")
            continue
        items.append(msg)
        seq += 1
    m.mav.mission_ack_send(m.target_system, m.target_component, M.MAV_MISSION_ACCEPTED)
    return items
