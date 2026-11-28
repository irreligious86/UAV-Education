#!/usr/bin/env python3
"""nav-indoor lab: feed ArduCopter SITL with VISION_POSITION_ESTIMATE built from SITL truth.

Truth = SIM_STATE (lat/lon/alt + attitude).  We convert it to a local NED frame anchored at the
first sample, add Gaussian noise and a transport lag (in SIM time), stamp it with the FC clock
(usec = time_boot_ms*1000, as a time-synced mocap bridge would) and send it as
VISION_POSITION_ESTIMATE.  Then: set EKF origin, arm in LOITER (no GPS), take off in GUIDED,
fly a square and land.  Prints STATUSTEXT and estimate-vs-truth error.

usage: extnav_feed.py --port 5770 --lag 50 --noise 0.02 --rate 30 --side 4 --speed 1.5
"""
import argparse, math, os, random, time, collections
os.environ["MAVLINK20"] = "1"      # reset_counter is a MAVLink 2 extension field
from pymavlink import mavutil

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=5770)
ap.add_argument("--lag", type=float, default=50.0, help="transport lag, ms (sim time)")
ap.add_argument("--jitter", type=float, default=0.0, help="uniform extra lag 0..jitter, ms")
ap.add_argument("--noise", type=float, default=0.02, help="position noise sigma, m")
ap.add_argument("--rate", type=float, default=30.0, help="send rate, Hz")
ap.add_argument("--side", type=float, default=4.0, help="square side, m")
ap.add_argument("--speed", type=float, default=1.5, help="WPNAV_SPEED, m/s")
ap.add_argument("--alt", type=float, default=2.0)
ap.add_argument("--hover", type=float, default=15.0)
ap.add_argument("--no-origin", action="store_true", help="do not send SET_GPS_GLOBAL_ORIGIN")
ap.add_argument("--swap-xy", action="store_true", help="frame bug: send ENU x/y (east, north) as if they were NED")
ap.add_argument("--jump", type=float, default=0.0, help="source jumps north by this many metres 5 s into the hover")
ap.add_argument("--jump-reset", action="store_true", help="increment reset_counter together with the jump")
args = ap.parse_args()

m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{args.port}", source_system=255, source_component=190)  # 255 = GCS: RC override is only accepted from SYSID_MYGCS
m.wait_heartbeat()
print(f"heartbeat from sys {m.target_system} comp {m.target_component}")

def set_interval(msg_id, hz):
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, msg_id, 1e6 / hz, 0, 0, 0, 0, 0)

for mid, hz in ((mavutil.mavlink.MAVLINK_MSG_ID_SIM_STATE, 50), (mavutil.mavlink.MAVLINK_MSG_ID_SYSTEM_TIME, 50),
                (mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 10), (mavutil.mavlink.MAVLINK_MSG_ID_EKF_STATUS_REPORT, 2)):
    set_interval(mid, hz)

m.mav.param_set_send(m.target_system, m.target_component, b"WPNAV_SPEED", args.speed * 100, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)

lat0 = lon0 = alt0 = None
t_boot = 0            # FC time, ms (SYSTEM_TIME)
queue = collections.deque()  # (send_at_ms, sample)
last_sent = 0.0
truth = None          # latest truth NED (n, e, d, yaw)
est = None            # latest LOCAL_POSITION_NED
origin_sent = False
phase = "wait"
t_phase = time.time()
armed = False
messages = []
sent = 0
err_log = []
jump_off = 0.0
reset_cnt = 0

def ned_from(lat, lon, alt):
    dn = (lat - lat0) * 1e-7 * 111319.5
    de = (lon - lon0) * 1e-7 * 111319.5 * math.cos(math.radians(lat0 * 1e-7))
    return dn, de, -(alt - alt0)

def send_vision(sample):
    global sent
    t_us, n, e, d, r, p, y = sample
    if args.swap_xy:
        n, e = e, n
    n += jump_off
    cov = [float("nan")] + [0.0] * 20                             # NaN -> VISO_POS_M_NSE / VISO_YAW_M_NSE used
    m.mav.vision_position_estimate_send(t_us, n, e, d, r, p, y, cov, reset_cnt)
    sent += 1

def mode(name):
    m.set_mode_apm(name)

def cmd(c, *p):
    m.mav.command_long_send(m.target_system, m.target_component, c, 0, *([*p] + [0] * (7 - len(p))))

def goto(n, e, d):
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                                             0b0000111111111000, n, e, d, 0, 0, 0, 0, 0, 0, 0, 0)

sq = [(0, 0), (args.side, 0), (args.side, args.side), (0, args.side), (0, 0)]
sq_i = 0
t0 = time.time()
rc_thr = 1000           # RC override: sticks centred, throttle low before arming, mid in flight (Loiter needs it)
t_rc = 0.0
while True:
    if time.time() - t_rc > 0.5:
        t_rc = time.time()
        m.mav.rc_channels_override_send(m.target_system, m.target_component, 1500, 1500, rc_thr, 1500, 0, 0, 0, 0)
    msg = m.recv_match(blocking=True, timeout=1.0)
    if msg is None:
        continue
    t = msg.get_type()
    if t == "SYSTEM_TIME":
        t_boot = msg.time_boot_ms
    elif t == "SIM_STATE":
        if lat0 is None:
            lat0, lon0, alt0 = msg.lat_int, msg.lon_int, msg.alt   # lat_int/lon_int: int32 1e-7 deg (float lat/lon lose ~1 m)
            print(f"origin from truth: lat {lat0/1e7:.7f} lon {lon0/1e7:.7f} alt {alt0:.1f}")
        n, e, d = ned_from(msg.lat_int, msg.lon_int, msg.alt)
        truth = (n, e, d, msg.yaw)
        if t_boot and (t_boot - last_sent) >= 1000.0 / args.rate:
            last_sent = t_boot
            s = (t_boot * 1000, n + random.gauss(0, args.noise), e + random.gauss(0, args.noise),
                 d + random.gauss(0, args.noise), msg.roll, msg.pitch, msg.yaw)
            queue.append((t_boot + args.lag + random.uniform(0, args.jitter), s))
    elif t == "LOCAL_POSITION_NED":
        est = (msg.x, msg.y, msg.z)
        if truth and armed:
            err_log.append((t_boot, math.hypot(msg.x - truth[0], msg.y - truth[1])))
    elif t == "STATUSTEXT":
        line = f"[{t_boot/1000:7.1f}s] {msg.text}"
        print(line); messages.append(line)
    elif t == "COMMAND_ACK" and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
        print(f"[{t_boot/1000:7.1f}s] COMMAND_ACK arm: result {msg.result}")
    elif t == "HEARTBEAT" and msg.get_srcSystem() == m.target_system:
        armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    # deliver lagged samples (sim time)
    while queue and queue[0][0] <= t_boot:
        send_vision(queue.popleft()[1])

    # ------------------------------------------------ flight sequence (state machine)
    now = time.time()
    if phase == "wait" and sent > 60 and not origin_sent and args.no_origin:
        origin_sent = True
        print(f"[{t_boot/1000:7.1f}s] -> origin NOT sent")
        phase, t_phase = "settle", now
    elif phase == "wait" and sent > 60 and not origin_sent:
        m.mav.set_gps_global_origin_send(m.target_system, int(lat0), int(lon0), int(alt0 * 1000))
        origin_sent = True
        print(f"[{t_boot/1000:7.1f}s] -> SET_GPS_GLOBAL_ORIGIN sent")
        phase, t_phase = "settle", now
    elif phase == "settle" and now - t_phase > 25:
        mode("LOITER"); phase, t_phase = "arm", now
        print(f"[{t_boot/1000:7.1f}s] -> mode LOITER, arming (ARMING_CHECK=1, no GPS)")
        cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
    elif phase == "arm" and armed:
        mode("GUIDED"); cmd(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, args.alt)
        print(f"[{t_boot/1000:7.1f}s] -> ARMED, GUIDED takeoff {args.alt} m")
        phase, t_phase = "climb", now
        rc_thr = 1500
    elif phase == "arm" and now - t_phase > 20:
        print("arming failed, giving up"); break
    elif phase == "climb" and now - t_phase > 10:
        phase, t_phase = "hover", now
        print(f"[{t_boot/1000:7.1f}s] -> hover {args.hover} s   truth {truth[0]:+.2f} {truth[1]:+.2f} {truth[2]:+.2f}  est {est[0]:+.2f} {est[1]:+.2f} {est[2]:+.2f}")
    elif phase == "hover" and args.jump and jump_off == 0.0 and now - t_phase > 5:
        jump_off = args.jump
        reset_cnt = 1 if args.jump_reset else 0
        print(f"[{t_boot/1000:7.1f}s] -> source jumps {args.jump:+.1f} m north, reset_counter={reset_cnt}")
    elif phase == "hover" and now - t_phase > args.hover:
        phase, t_phase = "square", now; sq_i = 1
        goto(sq[1][0], sq[1][1], -args.alt)
        print(f"[{t_boot/1000:7.1f}s] -> square {args.side} m at {args.speed} m/s")
    elif phase == "square":
        tn, te = sq[sq_i]
        if est and math.hypot(est[0] - tn, est[1] - te) < 0.3 and now - t_phase > 3:
            sq_i += 1; t_phase = now
            if sq_i >= len(sq):
                phase, t_phase = "loiter", now; mode("LOITER")
                print(f"[{t_boot/1000:7.1f}s] -> square done, LOITER 10 s")
            else:
                goto(sq[sq_i][0], sq[sq_i][1], -args.alt)
        elif now - t_phase > 40:
            print(f"[{t_boot/1000:7.1f}s] -> waypoint timeout (est {est}), LOITER"); phase, t_phase = "loiter", now; mode("LOITER")
    elif phase == "loiter" and now - t_phase > 10:
        mode("LAND"); phase, t_phase = "land", now
        print(f"[{t_boot/1000:7.1f}s] -> LAND")
    elif phase == "land" and (not armed) and now - t_phase > 5:
        break
    elif phase == "land" and now - t_phase > 60:
        break

errs = [e for _, e in err_log]
if errs:
    errs_sorted = sorted(errs)
    print(f"horizontal error est-vs-truth while armed: mean {sum(errs)/len(errs):.3f} m, "
          f"p95 {errs_sorted[int(0.95*len(errs))]:.3f} m, max {max(errs):.3f} m  (n={len(errs)})")
print(f"sent {sent} VISION_POSITION_ESTIMATE, lag {args.lag} ms, noise {args.noise} m, rate {args.rate} Hz")
