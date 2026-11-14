#!/usr/bin/env python3
"""Replay targets.csv (vision pipeline output) into ArduCopter SITL: GUIDED velocity follow with
watchdog/timeout interlocks, then FOLLOW mode fed with GLOBAL_POSITION_INT from a fake "target" sysid.

SITL (instance 4, ArduCopter 4.6.3 built as in module ap-sitl; $AP is the ardupilot checkout):
    mkdir sitl4 && cd sitl4 && $AP/build/sitl/bin/arducopter -w -S --model + -I 4 --speedup 1 \
        --home -35.363261,149.165230,584,353 --defaults $AP/Tools/autotest/default_params/copter.parm
Then:  python3 sitl_follow.py tcp:127.0.0.1:5800 data/targets.csv
"""
import csv, math, sys, time
from pymavlink import mavutil

URL = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5800"
CSV = sys.argv[2] if len(sys.argv) > 2 else "data/targets.csv"
ALT, KP, V_MAX, RATE = 15.0, 0.8, 2.0, 10.0
WATCHDOG_S, TIMEOUT_S = 0.5, 3.0
TARGET_SYSID = 200
VEL_MASK = 0b1101_1100_0111               # 3527: use vx vy vz only (ignore pos, accel, yaw, yaw_rate)
R_E = 6378137.0
REC_LAT0, REC_LON0 = -35.3632621, 149.1652374     # origin of the recorded flight (gen_video.py)

m = mavutil.mavlink_connection(URL, source_system=255)
m.wait_heartbeat(timeout=120)
print(f"heartbeat from sysid {m.target_system}, firmware:", end=" ")
last_hb = None
v = None
for _ in range(10):
    m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0, 148, 0, 0, 0, 0, 0, 0)
    v = m.recv_match(type="AUTOPILOT_VERSION", blocking=True, timeout=3)
    if v: break
fv = v.flight_sw_version if v else 0
print(f"{(fv >> 24) & 255}.{(fv >> 16) & 255}.{(fv >> 8) & 255}")
for sid, rate in ((mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10), (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10), (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS, 2)):
    m.mav.request_data_stream_send(m.target_system, m.target_component, sid, rate, 1)

last = {}
t_rc = 0.0
QUIET = True                              # print only fence / failsafe texts from the autopilot
texts = []


def pump(seconds=0.0, until=None, timeout=90.0):
    global t_rc
    RC_ON = rel_alt_ok()
    t_end = time.time() + (timeout if until else seconds)
    while True:
        if RC_ON and time.time() - t_rc > 0.5:           # the "pilot": sticks centred, throttle mid (LOITER descends on low throttle)
            m.mav.rc_channels_override_send(m.target_system, m.target_component, 1500, 1500, 1500, 1500, 0, 0, 0, 0); t_rc = time.time()
        msg = m.recv_match(blocking=True, timeout=0.05)
        if msg is not None and msg.get_srcSystem() == m.target_system:
            last[msg.get_type()] = msg
            if msg.get_type() == "STATUSTEXT":
                texts.append(msg.text)
                if not QUIET or any(k in msg.text for k in ("ence", "ailsafe", "Follow", "Plnd")): print("   FC:", msg.text)
            if until and until(msg): return msg
        if time.time() >= t_end: return None


def rel_alt_ok():
    g = last.get('GLOBAL_POSITION_INT'); return bool(g) and g.relative_alt > 5000    # airborne


def set_param(name, value):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    r = pump(until=lambda x: x.get_type() == "PARAM_VALUE" and x.param_id == name)
    print(f"   {name} = {r.param_value:g}")


def mode(name):
    m.set_mode(m.mode_mapping()[name])
    ok = pump(until=lambda x: x.get_type() == "HEARTBEAT" and mavutil.mode_string_v10(x) == name, timeout=10)
    print(f"   mode {name}" if ok else f"   mode {name} REFUSED (still {mavutil.mode_string_v10(last['HEARTBEAT'])})")


def where():
    g = last["GLOBAL_POSITION_INT"]
    n = math.radians(g.lat / 1e7 - lat0) * R_E; e = math.radians(g.lon / 1e7 - lon0) * R_E * math.cos(math.radians(lat0))
    return f"pos=({n:+.1f},{e:+.1f}) m v=({g.vx / 100:+.1f},{g.vy / 100:+.1f}) m/s mode={mavutil.mode_string_v10(last['HEARTBEAT'])}"


def rel_alt():
    return last["GLOBAL_POSITION_INT"].relative_alt / 1000.0


def send_vel(vn, ve, vd=0.0):
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                                             VEL_MASK, 0, 0, 0, vn, ve, vd, 0, 0, 0, 0, 0)


# -------------------------------------------------- 0. clock offset companion <-> FC via TIMESYNC
print("== 0. TIMESYNC")
rtts, offs = [], []
for _ in range(10):
    ts1 = time.monotonic_ns()
    m.mav.timesync_send(0, ts1)
    r = pump(until=lambda x: x.get_type() == "TIMESYNC" and x.ts1 == ts1)
    rtt = time.monotonic_ns() - ts1
    rtts.append(rtt / 1e6); offs.append((r.tc1 - (ts1 + rtt / 2)) / 1e6)
    time.sleep(0.1)
print(f"   RTT median {sorted(rtts)[5]:.2f} ms, FC clock - companion clock = {sorted(offs)[5]:.1f} ms (spread {max(offs) - min(offs):.2f} ms)")

# -------------------------------------------------- 1. parameters: interlocks live in the autopilot too
print("== 1. parameters")
for k, val in (("FENCE_ENABLE", 1), ("FENCE_TYPE", 3), ("FENCE_RADIUS", 60), ("FENCE_ALT_MAX", 30), ("FENCE_ACTION", 1),
               ("WPNAV_SPEED", 300), ("GUID_TIMEOUT", 3), ("FOLL_ENABLE", 1), ("FOLL_SYSID", TARGET_SYSID),
               ("FOLL_OFS_Z", -ALT), ("FOLL_POS_P", 0.3), ("FOLL_DIST_MAX", 60), ("FOLL_YAW_BEHAVE", 0), ("FOLL_ALT_TYPE", 1)):
    set_param(k, val)

# -------------------------------------------------- 2. arm and take off in GUIDED
print("== 2. takeoff")
pump(until=lambda x: x.get_type() == "HEARTBEAT")
if last["HEARTBEAT"].base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:        # a previous run is still in the air: land it first
    m.set_mode(m.mode_mapping()["LAND"])
    assert pump(until=lambda x: x.get_type() == "HEARTBEAT" and not x.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED, timeout=120), "still armed"
t_arm = time.time()
PREARM = mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK
ok = pump(until=lambda x: x.get_type() == "SYS_STATUS" and x.onboard_control_sensors_health & PREARM, timeout=180)
assert ok, f"pre-arm checks never passed: {texts[-3:]}"
print(f"   pre-arm checks passed after {time.time() - t_arm:.0f} s (EKF has a position, fence can be armed)")
mode("GUIDED")
for _ in range(6):                                                    # RC override from a previous run needs 3 s to expire
    m.arducopter_arm()
    ok = pump(until=lambda x: x.get_type() == "HEARTBEAT" and x.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED, timeout=4)
    if ok: break
assert ok, f"did not arm: {texts[-3:]}"
print("   armed")
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, ALT)
t0 = time.time()
while rel_alt() < ALT - 0.5 and time.time() - t0 < 60:
    pump(0.2)
print(f"   alt {rel_alt():.1f} m after {time.time() - t0:.0f} s")
assert rel_alt() > ALT - 1.0, "take-off failed"
home = last["GLOBAL_POSITION_INT"]
lat0, lon0 = home.lat / 1e7, home.lon / 1e7
print(f"   home {lat0:.7f} {lon0:.7f}")

# -------------------------------------------------- 3. GUIDED velocity follow from the pipeline log
print("== 3. GUIDED velocity follow (replay of targets.csv at 30 fps, commands at 10 Hz)")
rows = list(csv.DictReader(open(CSV)))
t_start, k, last_seen, n_sent, state_prev, latched = time.time(), 0, 0.0, 0, None, False
tgt_n = tgt_e = 0.0
hist = []
while k < len(rows):
    now = time.time() - t_start
    while k < len(rows) and int(rows[k]["t_us"]) / 1e6 <= now:    # consume pipeline rows up to "now"
        r = rows[k]; k += 1
        if r["state"] == "TRACK":
            last_seen, tgt_n, tgt_e = now, float(r["n"]), float(r["e"])
    age = now - last_seen
    if latched and age <= WATCHDOG_S and now - t_latch > 1.0:
        print(f"   t={now:5.1f}s target is back, operator re-enables follow:", end=""); mode("GUIDED"); latched = False
    if latched:
        state = "LOITER"                                              # nothing is sent: the autopilot and the pilot own the aircraft
    elif age <= WATCHDOG_S:
        state = "TRACK"; vn, ve = max(-V_MAX, min(V_MAX, KP * tgt_n)), max(-V_MAX, min(V_MAX, KP * tgt_e))
        send_vel(vn, ve); n_sent += 1
    elif age <= TIMEOUT_S:
        state = "HOLD"; send_vel(0, 0); n_sent += 1                 # watchdog: explicit zero velocity, stay in GUIDED
    else:
        state = "LOITER"; latched, t_latch = True, now               # timeout: hand the aircraft back, latch until the operator acts
        mode("LOITER")
    g = last.get("GLOBAL_POSITION_INT")
    if state != state_prev:
        print(f"   t={now:5.1f}s {state_prev}->{state}  v_fc=({g.vx / 100:+.1f},{g.vy / 100:+.1f}) m/s  alt={g.relative_alt / 1000:.1f} m  mode={mavutil.mode_string_v10(last['HEARTBEAT'])}")
        state_prev = state
    hist.append((now, state, g.vx / 100, g.vy / 100))
    pump(1.0 / RATE)
print(f"   sent {n_sent} velocity setpoints; interlock states: " + ", ".join(f"{s}={sum(1 for h in hist if h[1] == s)}" for s in ("TRACK", "HOLD", "LOITER")))
# did the autopilot actually stop on HOLD?
holds = [h for h in hist if h[1] == "HOLD"]
if holds:
    t_h = holds[0][0]
    v_before = [math.hypot(h[2], h[3]) for h in hist if t_h - 1.5 <= h[0] < t_h - 0.5]   # HOLD starts 0.5 s after the last detection
    v_after = [math.hypot(h[2], h[3]) for h in hist if t_h + 1.5 <= h[0] < t_h + 2.5]
    print(f"   |v| before first HOLD {sum(v_before) / len(v_before):.2f} m/s, 1.5-2.5 s after {sum(v_after) / len(v_after):.2f} m/s")

# -------------------------------------------------- 4. FOLLOW mode fed with GLOBAL_POSITION_INT from the pipeline
print("== 4. FOLLOW mode: pipeline publishes the target as sysid 200 GLOBAL_POSITION_INT")
fake = type("Fake", (), {})(); fake.mav = mavutil.mavlink.MAVLink(m, srcSystem=TARGET_SYSID, srcComponent=1)   # same link, other sysid
mode("FOLLOW")
t_f, k, prev = time.time(), 0, None
d_hist = []
def ne_of(lat, lon):
    return math.radians(lat - lat0) * R_E, math.radians(lon - lon0) * R_E * math.cos(math.radians(lat0))
while k < len(rows) and time.time() - t_f < 20.0:                   # the dark slice starts at 20.1 s: the stream dies by itself
    now = time.time() - t_f
    while k < len(rows) and int(rows[k]["t_us"]) / 1e6 <= now:
        r = rows[k]; k += 1
        if r["state"] != "TRACK" or k % 3: continue                  # 10 Hz
        # geo-referenced target from the pipeline; the recorded scene is re-anchored on this take-off point
        tn = math.radians(float(r["lat"]) - REC_LAT0) * R_E; te = math.radians(float(r["lon"]) - REC_LON0) * R_E * math.cos(math.radians(REC_LAT0))
        lat_t = lat0 + math.degrees(tn / R_E); lon_t = lon0 + math.degrees(te / (R_E * math.cos(math.radians(lat0))))
        if prev and now - prev[0] >= 1.0:                            # target velocity over a 1 s baseline, cm/s
            vx, vy = int(100 * (tn - prev[1]) / (now - prev[0])), int(100 * (te - prev[2]) / (now - prev[0])); prev = (now, tn, te)
        elif prev is None:
            prev, vx, vy = (now, tn, te), 0, 0
        fake.mav.global_position_int_send(int(now * 1000), int(lat_t * 1e7), int(lon_t * 1e7), int(home.alt - home.relative_alt), 0, vx, vy, 0, 65535)
        g = last["GLOBAL_POSITION_INT"]; vn_, ve_ = ne_of(g.lat / 1e7, g.lon / 1e7)
        d_hist.append((now, math.hypot(tn - vn_, te - ve_), math.hypot(g.vx, g.vy) / 100, g.relative_alt / 1000))
    pump(0.03)
print(f"   horizontal distance to target: start {d_hist[0][1]:.1f} m, t=10 s {min(d_hist, key=lambda d: abs(d[0] - 10))[1]:.1f} m, "
      f"mean over the last 5 s {sum(d[1] for d in d_hist if d[0] > 15) / sum(1 for d in d_hist if d[0] > 15):.1f} m; "
      f"|v| max {max(d[2] for d in d_hist):.1f} m/s, alt {min(d[3] for d in d_hist):.1f}-{max(d[3] for d in d_hist):.1f} m")
print("   target stream stops (dark slice: the pipeline has nothing to publish)")
for sec in (1, 2, 3, 4, 5):
    pump(1.0); print(f"   +{sec} s: {where()}")

# -------------------------------------------------- 5. GUID_TIMEOUT: go silent and watch the autopilot
print("== 5. speed limit and GUID_TIMEOUT: companion goes silent in GUIDED")
mode("GUIDED")
print(f"   start: {where()}")
for sec in (1, 2, 3, 4):                                             # ask for 6 m/s with WPNAV_SPEED = 300 cm/s: is it capped?
    for _ in range(10): send_vel(6.0, 0.0); pump(0.1)
    print(f"   6.0 m/s north commanded, +{sec} s: {where()}")
for _ in range(30): send_vel(1.5, 0.0); pump(0.1)
print(f"   1.5 m/s north commanded for 3 s: {where()}; now silent")
for sec in (1, 2, 3, 4, 5):
    pump(1.0); print(f"   +{sec} s silence: {where()}")

# -------------------------------------------------- 6. geofence: the last line of defence is in the autopilot
print("== 6. geofence: companion keeps commanding 3 m/s north, FENCE_RADIUS = 60 m")
mode("GUIDED")
t_g = time.time()
while time.time() - t_g < 40 and mavutil.mode_string_v10(last["HEARTBEAT"]) == "GUIDED":
    send_vel(3.0, 0.0); pump(0.1)
print(f"   after {time.time() - t_g:.0f} s: {where()}")
for _ in range(30): send_vel(3.0, 0.0); pump(0.1)
print(f"   3 s later, still sending 3 m/s north: {where()}")
print("   fence shrinks to 30 m while the vehicle is outside it (the same as flying through a fence without avoidance)")
set_param("FENCE_RADIUS", 30)
for _ in range(30): send_vel(3.0, 0.0); pump(0.1)                  # companion still pushing north: must be ignored outside GUIDED
print(f"   3 s later, still sending 3 m/s north: {where()}")
mode("LAND")
ok = pump(until=lambda x: x.get_type() == "HEARTBEAT" and not x.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED, timeout=120)
print("landed and disarmed" if ok else "still armed after 120 s")
