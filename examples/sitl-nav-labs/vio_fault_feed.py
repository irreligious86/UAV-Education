#!/usr/bin/env python3
"""per-visual-nav lab: three VIO failure modes against ArduCopter 4.7.2 SITL (no GPS, ExternalNav only).

Truth = SIM_STATE, converted to local NED at the first sample, +noise, +transport lag (sim time),
stamped with the FC clock and sent as VISION_POSITION_ESTIMATE at --rate Hz.
Flight: origin -> arm in LOITER -> GUIDED takeoff to --alt -> LOITER hover; at t_fault (s after hover
start) one fault is injected for --fault-len s:
  --fault freeze : keep sending the LAST pose at the same rate (tracking lost, pose frozen)
  --fault stop   : stop sending (companion detected tracking loss and went silent)
  --fault jump   : add --jump metres north to every pose (relocalisation jump)
Every 1 s it prints: truth N/E, EKF estimate N/E (LOCAL_POSITION_NED), "gap" = |estimate - truth|
(horizontal), "drift" = how far the vehicle really moved from where it hovered when LOITER started,
EKF_STATUS_REPORT pos_horiz_variance (= sqrt of the position test ratio, same as XKF4.SP) and the mode.

usage: vio_fault_feed.py --port 5790 --fault freeze --fault-at 10 --fault-len 20 [--detector]
"""
import argparse, collections, math, os, random, time
os.environ["MAVLINK20"] = "1"
from pymavlink import mavutil

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=5770)
ap.add_argument("--lag", type=float, default=50.0)
ap.add_argument("--noise", type=float, default=0.02)
ap.add_argument("--rate", type=float, default=30.0)
ap.add_argument("--alt", type=float, default=3.0)
ap.add_argument("--fault", choices=["none", "freeze", "stop", "jump"], default="none")
ap.add_argument("--fault-at", type=float, default=10.0)
ap.add_argument("--fault-len", type=float, default=20.0)
ap.add_argument("--jump", type=float, default=5.0)
ap.add_argument("--detector", action="store_true", help="bridge stops publishing when the pose has not moved 1 mm for 0.5 s")
ap.add_argument("--after", type=float, default=15.0, help="seconds to watch after the fault ends")
args = ap.parse_args()
random.seed(1)

m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{args.port}", source_system=255, source_component=190)
m.wait_heartbeat()

def set_interval(msg_id, hz):
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, msg_id, 1e6 / hz, 0, 0, 0, 0, 0)

for mid, hz in ((mavutil.mavlink.MAVLINK_MSG_ID_SIM_STATE, 50), (mavutil.mavlink.MAVLINK_MSG_ID_SYSTEM_TIME, 50),
                (mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 10), (mavutil.mavlink.MAVLINK_MSG_ID_EKF_STATUS_REPORT, 5)):
    set_interval(mid, hz)

lat0 = lon0 = alt0 = None
t_boot = 0
queue = collections.deque()
last_sent = 0.0
last_pose = None
truth = est = None
pos_ratio = 0.0
armed = False
mode_name = "?"
sent = 0
phase, t_phase = "wait", time.time()
rc_thr = 1000
t_rc = t_print = 0.0
fault_on = False
hover0 = None
last_moved_ms, ref_pose, silenced = 0, None, False

def ned(lat, lon, alt):
    dn = (lat - lat0) * 1e-7 * 111319.5
    de = (lon - lon0) * 1e-7 * 111319.5 * math.cos(math.radians(lat0 * 1e-7))
    return dn, de, -(alt - alt0)

def send(s):
    global sent
    t_us, n, e, d, r, p, y = s
    m.mav.vision_position_estimate_send(t_us, n, e, d, r, p, y, [float("nan")] + [0.0] * 20, 0)
    sent += 1

def cmd(c, *p):
    m.mav.command_long_send(m.target_system, m.target_component, c, 0, *([*p] + [0] * (7 - len(p))))

while True:
    now = time.time()
    if now - t_rc > 0.5:
        t_rc = now
        m.mav.rc_channels_override_send(m.target_system, m.target_component, 1500, 1500, rc_thr, 1500, 0, 0, 0, 0)
    msg = m.recv_match(blocking=True, timeout=1.0)
    if msg is None:
        continue
    t = msg.get_type()
    if t == "SYSTEM_TIME":
        t_boot = msg.time_boot_ms
    elif t == "SIM_STATE":
        if lat0 is None:
            lat0, lon0, alt0 = msg.lat_int, msg.lon_int, msg.alt
        n, e, d = ned(msg.lat_int, msg.lon_int, msg.alt)
        truth = (n, e, d)
        if t_boot and t_boot - last_sent >= 1000.0 / args.rate:
            last_sent = t_boot
            s = (t_boot * 1000, n + random.gauss(0, args.noise), e + random.gauss(0, args.noise),
                 d + random.gauss(0, args.noise), msg.roll, msg.pitch, msg.yaw)
            queue.append((t_boot + args.lag, s))
    elif t == "LOCAL_POSITION_NED":
        est = (msg.x, msg.y, msg.z)
    elif t == "EKF_STATUS_REPORT":
        pos_ratio = msg.pos_horiz_variance
    elif t == "STATUSTEXT":
        print(f"[{t_boot/1000:7.1f}s] MSG {msg.text}")
    elif t == "HEARTBEAT" and msg.get_srcSystem() == m.target_system and msg.get_srcComponent() == 1:
        armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        mode_name = mavutil.mode_string_v10(msg)
    while queue and queue[0][0] <= t_boot:
        s = queue.popleft()[1]
        if fault_on and args.fault == "stop":
            continue
        if fault_on and args.fault == "freeze":
            s = (s[0],) + last_pose[1:]          # fresh timestamp, frozen pose
        elif fault_on and args.fault == "jump":
            s = (s[0], s[1] + args.jump) + s[2:]
        else:
            last_pose = s
        if args.detector:                                   # frozen-pose detector in the bridge
            if ref_pose is None or max(abs(a - b) for a, b in zip(s[1:4], ref_pose)) > 0.001:
                ref_pose, last_moved_ms = s[1:4], t_boot
                if silenced:
                    silenced = False; print(f"[{t_boot/1000:7.1f}s] detector: pose moves again, publishing")
            elif t_boot - last_moved_ms > 500:
                if not silenced:
                    silenced = True; print(f"[{t_boot/1000:7.1f}s] detector: pose frozen 0.5 s, stop publishing")
                continue
        send(s)

    if phase == "wait" and sent > 60:
        m.mav.set_gps_global_origin_send(m.target_system, int(lat0), int(lon0), int(alt0 * 1000))
        phase, t_phase = "settle", now
    elif phase == "settle" and now - t_phase > 25:
        m.set_mode_apm("LOITER"); cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        phase, t_phase = "arm", now
    elif phase == "arm" and armed:
        m.set_mode_apm("GUIDED"); cmd(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, args.alt)
        rc_thr = 1500
        print(f"[{t_boot/1000:7.1f}s] armed, takeoff {args.alt} m")
        phase, t_phase = "climb", now
    elif phase == "arm" and now - t_phase > 20:
        print("arming failed"); break
    elif phase == "climb" and now - t_phase > 10:
        m.set_mode_apm("LOITER")
        print(f"[{t_boot/1000:7.1f}s] LOITER hover, fault '{args.fault}' at +{args.fault_at:.0f} s for {args.fault_len:.0f} s")
        phase, t_phase = "hover", now
    elif phase == "hover":
        th = now - t_phase
        if args.fault != "none" and not fault_on and args.fault_at <= th < args.fault_at + args.fault_len:
            fault_on = True; print(f"[{t_boot/1000:7.1f}s] >>> fault ON ({args.fault})")
        elif fault_on and th >= args.fault_at + args.fault_len:
            fault_on = False; print(f"[{t_boot/1000:7.1f}s] <<< fault OFF")
        if th > args.fault_at + args.fault_len + args.after:
            break
        if hover0 is None and truth:
            hover0 = truth[:2]
        if now - t_print >= 1.0 and truth and est:
            t_print = now
            gap = math.hypot(est[0] - truth[0], est[1] - truth[1])
            drift = math.hypot(truth[0] - hover0[0], truth[1] - hover0[1])
            print(f"[{t_boot/1000:7.1f}s] t+{th:5.1f} truth N {truth[0]:+6.2f} E {truth[1]:+6.2f} | est N {est[0]:+6.2f} "
                  f"E {est[1]:+6.2f} | gap {gap:5.2f} | drift {drift:5.2f} m | ratio {pos_ratio:4.2f} | {mode_name}{' FAULT' if fault_on else ''}")
print(f"sent {sent} VISION_POSITION_ESTIMATE")
