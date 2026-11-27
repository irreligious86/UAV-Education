#!/usr/bin/env python3
"""ros2-nav lab: ArduCopter 4.7.2 SITL, OA_TYPE=2 (Dijkstra) around an exclusion polygon fence.

Uploads a 20 x 20 m exclusion square centred 40 m north of home, takes off to 10 m in GUIDED
(GUID_OPTIONS=64: position targets go through WPNav, so object avoidance applies), sends a target
80 m north (the straight line crosses the square) and records the track from LOCAL_POSITION_NED.
Prints path length vs straight line, max lateral offset, min clearance to the square, flight time.

usage: oa_dijkstra_lab.py --port 5800 [--no-fence | --no-enable] [--csv track.csv]
  --no-fence   do not upload the exclusion square at all (with FENCE_ENABLE 1 arming then fails:
               "Fences enabled, but none selected" - use oa_nofence.parm for a straight-flight baseline)
  --no-enable  upload it but do not send MAV_CMD_DO_FENCE_ENABLE (control run with FENCE_ENABLE 0)
"""
import argparse, math, time
from pymavlink import mavutil

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=5800)
ap.add_argument("--no-fence", action="store_true")
ap.add_argument("--no-enable", action="store_true")
ap.add_argument("--goal", type=float, default=80.0)
ap.add_argument("--csv", default="track.csv")
args = ap.parse_args()

m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{args.port}", source_system=255, source_component=190)
m.wait_heartbeat()
tgt = (m.target_system, m.target_component)

def interval(mid, hz):
    m.mav.command_long_send(*tgt, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, mid, 1e6 / hz, 0, 0, 0, 0, 0)

interval(mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 10)
interval(mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 5)

# wait for a GPS home
home = None
while home is None:
    g = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=5)
    if g and g.lat != 0:
        home = (g.lat / 1e7, g.lon / 1e7)
print(f"home {home[0]:.6f} {home[1]:.6f}")

def ll(n, e):
    lat = home[0] + n / 111319.5
    lon = home[1] + e / (111319.5 * math.cos(math.radians(home[0])))
    return int(lat * 1e7), int(lon * 1e7)

SQ = [(30, -10), (30, 10), (50, 10), (50, -10)]       # N, E of the exclusion square, m
if not args.no_fence:
    items = SQ
    m.mav.mission_count_send(*tgt, len(items), mavutil.mavlink.MAV_MISSION_TYPE_FENCE)
    sent = 0
    while True:
        r = m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True, timeout=5)
        if r is None:
            raise SystemExit("fence upload timeout")
        if r.get_type() == "MISSION_ACK":
            print(f"fence upload ack type {r.type}")
            break
        n, e = items[r.seq]
        la, lo = ll(n, e)
        m.mav.mission_item_int_send(*tgt, r.seq, mavutil.mavlink.MAV_FRAME_GLOBAL,
                                    mavutil.mavlink.MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION, 0, 1,
                                    len(items), 0, 0, 0, la, lo, 0, mavutil.mavlink.MAV_MISSION_TYPE_FENCE)
    if not args.no_enable:
        m.mav.command_long_send(*tgt, mavutil.mavlink.MAV_CMD_DO_FENCE_ENABLE, 0, 1, 0, 0, 0, 0, 0, 0)
        a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
        print(f"DO_FENCE_ENABLE ack result {a.result if a else 'none'}")
m.mav.param_request_read_send(*tgt, b"FENCE_ENABLE", -1)
pv, t_pv = None, time.time()
while pv is None and time.time() - t_pv < 5:
    r = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
    if r is not None and r.param_id.rstrip("\x00") == "FENCE_ENABLE":
        pv = r
print(f"FENCE_ENABLE = {pv.param_value:.0f}" if pv else "FENCE_ENABLE: no reply")

# arm and take off
t0 = time.time()
while time.time() - t0 < 60:
    m.set_mode_apm("GUIDED")
    m.mav.command_long_send(*tgt, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
    a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
    if a and a.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM and a.result == 0:
        break
    time.sleep(2)
m.mav.command_long_send(*tgt, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
print("armed, takeoff 10 m")
t1 = time.time()
while time.time() - t1 < 25:
    p = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=2)
    if p and p.z < -9.5:
        break
m.mav.set_position_target_local_ned_send(0, *tgt, mavutil.mavlink.MAV_FRAME_LOCAL_NED, 0b0000111111111000,
                                         args.goal, 0, -10, 0, 0, 0, 0, 0, 0, 0, 0)
print(f"goal {args.goal:.0f} m north sent")
track, t_go = [], time.time()
while time.time() - t_go < 120:
    msg = m.recv_match(type=["LOCAL_POSITION_NED", "STATUSTEXT"], blocking=True, timeout=2)
    if msg is None:
        continue
    if msg.get_type() == "STATUSTEXT":
        print(f"  MSG {msg.text}")
        continue
    track.append((time.time() - t_go, msg.x, msg.y))
    if math.hypot(msg.x - args.goal, msg.y) < 0.5 and math.hypot(msg.vx, msg.vy) < 0.2:
        break

def seg_dist(px, py, a, b):
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def inside(px, py):
    return 30 <= px <= 50 and -10 <= py <= 10

length = sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(track, track[1:]))
start = (track[0][1], track[0][2])
clear = min((-1 if inside(x, y) else min(seg_dist(x, y, SQ[i], SQ[(i + 1) % 4]) for i in range(4))) for _, x, y in track)
lat = max(abs(y) for _, _, y in track)
print(f"time {track[-1][0]:.1f} s, path {length:.1f} m vs straight {math.hypot(args.goal - start[0], start[1]):.1f} m, "
      f"max |E| {lat:.1f} m, min clearance to square {clear:.1f} m")
for tt, x, y in track[:: max(1, len(track) // 16)]:
    print(f"  t {tt:5.1f}  N {x:6.1f}  E {y:6.1f}")
with open(args.csv, "w") as f:
    f.write("t,n,e\n")
    for tt, x, y in track:
        f.write(f"{tt:.2f},{x:.2f},{y:.2f}\n")
