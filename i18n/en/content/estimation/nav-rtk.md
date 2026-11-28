---
id: nav-rtk
title: "RTK/PPK: base and rover, NTRIP, moving baseline, GPS yaw"
level: L3
readingTime: 45 min
firmware: ArduPilot 4.7 (checked against 4.7.3; the lab was captured on 4.6.3) · PX4 1.18 (parameters checked against v1.18.0)
status: published
added: 2026-11-10
tags:
  - RTK
  - RTCM
  - NTRIP
  - moving baseline
  - GPS yaw
  - F9P
related:
  - est-gnss
  - ap-ekf
  - est-kalman
  - nav-resilience
  - per-landing
next:
  - per-landing
source: content/estimation/nav-rtk.md
source_hash: c68430ba9472
---

## summary
In the "GNSS" module RTK got a single paragraph. Here is the whole chain: how the base learns its own position (survey-in or known coordinates), which RTCM3 messages it sends, how they reach the rover (NTRIP caster → Mission Planner/QGC → `GPS_RTCM_DATA` → the receiver's UART), what float/fixed and correction age mean, and how two F9P units on the frame give heading without a compass (moving baseline, "GPS for yaw"). It covers the ArduPilot 4.7 parameters (`GPS1_TYPE = 17/18`, `GPS1_POS_*`, `GPS1_MB_*`, `GPS_DRV_OPTIONS`, `EK3_SRC1_YAW = 2`) and the PX4 equivalents (`GPS_UBX_MODE`, `GPS_YAW_OFFSET`, `EKF2_GPS_CTRL`). The lab: moving baseline in SITL with real `GPS2_RAW.yaw` output, a log with `GPS.Status = 6`, a "fix type → accuracy" script on a generated rover log, then a bench with two F9P units.

## theory
### RTK and PPK: the same math, different timing
Both remove the errors common to the base and the rover (ionosphere, troposphere, orbits, clocks) through carrier-phase differences, and fix the integer ambiguities. The difference is when.

| | RTK (real-time kinematic) | PPK (post-processed kinematic) |
|---|---|---|
| When | in flight, every epoch | after the flight, from two raw logs |
| Base→rover link needed | yes, continuously (radio, 4G, NTRIP) | no |
| What it gives the autopilot | 1–3 cm position in the EKF, precision landing, GPS yaw | nothing in flight; image coordinates for photogrammetry |
| What to log | an ordinary log; fix status | RXM-RAWX from both receivers: ArduPilot `GPS_RAW_DATA = 1` (the `GRAW/GRXH/GRXS` messages), PX4 `GPS_DUMP_COMM = 2` |

Numbers for the ZED-F9P (ZED-F9P-04B data sheet): standard PVT 1.5 m CEP (1.0 m with SBAS), RTK 0.01 m + 1 ppm (1 ppm = 1 mm per kilometer of baseline; for 20 km that is 3 cm), convergence < 10 s with several constellations, velocity 0.05 m/s. Because of the "1 ppm," an NTRIP station is used no farther than ~50–100 km away: at 100 km that is 11 cm, with slower convergence. For your own base and a fast fix, keep the baseline shorter, 10–20 km (est-gnss).

### The base: survey-in or a known point
The base coordinate error transfers **entirely** to the rover: RTK gives centimeters *relative to the base*. There are two ways to set the point (u-blox `CFG-TMODE-MODE`):
- **Survey-in** (`SURVEY_IN`): the receiver averages its own position until both conditions are met, the minimum duration `CFG-TMODE-SVIN_MIN_DUR` and the 3D accuracy limit `CFG-TMODE-SVIN_ACC_LIMIT`. In Mission Planner these are the "SurveyIn Acc (m)" and "Time (s)" fields; typically 2 m and 60 s. The absolute accuracy of such a base is meters, while the rover's relative accuracy is centimeters: enough for landing on the same pad, not enough for a map in a national coordinate system. During survey-in you must not feed the base someone else's corrections.
- **Known coordinates** (`FIXED`, `CFG-TMODE-POS_TYPE` plus the `_HP` keys with millimeter resolution): a point from a surveyor, from a survey-in lasting many hours, or from PPK against a network of permanent stations. Mission Planner stores it ("Save"/"Use"); this works only if the base stands in the same spot.

### RTCM3: what exactly the base sends
The set that u-blox recommends for an F9P base and that Mission Planner enables (`ubx_m8p.cs`: 1005 and 1230 every 5 s, MSM once per second):

| Message | Content | Why |
|---|---|---|
| 1005 | the base antenna coordinates (ECEF); 1006 is the same plus the antenna height | without it the rover does not know what to compute relative to |
| 1074 / 1084 / 1094 / 1124 | MSM4: GPS / GLONASS / Galileo / BeiDou observations (pseudorange, phase, C/N0) | the corrections themselves; MSM4 is more compact |
| 1077 / 1087 / 1097 / 1127 | MSM7: the same constellations at full resolution with Doppler | an alternative to MSM4, the QGC/PX4 set; do not mix it with MSM4 in one stream |
| 1230 | GLONASS code-phase biases | without 1230 (or 1033) GLONASS stays float even with RTK fixed |
| 4072.0 | u-blox proprietary: the base PVT for moving baseline | mandatory in every epoch in MB mode; not needed for a static base |

A 1 Hz stream with four constellations is a few kB/s; the F9P raises MB to 5 Hz, but then UART2 needs 460800 baud, and the delivery latency must be below the navigation period minus 50 ms (≈150 ms at 5 Hz). The rover stops using corrections older than `CFG-NAVSPG-CONSTR_DGNSSTO` (60 s by default) and falls back to 3D/DGNSS.

### Delivery: NTRIP, Mission Planner, MAVLink
**NTRIP** is an HTTP-like protocol: a caster on port 2101 serves a sourcetable of mount points, and a client logs in and receives an RTCM stream. A public example is RTK2go (free; the login is a valid e-mail address, the password `none`); commercial networks give you a virtual station near you. The string in Mission Planner: `http://user:pass@host:2101/MOUNT`.

From there the corrections travel to the vehicle over telemetry: **Mission Planner → Setup → Optional Hardware → RTK/GPS Inject** cuts the stream into `GPS_RTCM_DATA` packets (id 233; `flags`: bit 0 means fragmented, bits 1–2 are the fragment number, bits 3–7 the sequence id; `data[180]`). The old `GPS_INJECT_DATA` (id 123, 110 bytes) has been marked superseded in MAVLink since 2022-05, and ArduPilot still accepts it. On board, `AP_GPS::handle_gps_rtcm_fragment()` reassembles the fragments and writes the bytes to the UART of the receiver selected by `GPS_INJECT_TO` (0 the first, 1 the second, 127 all). `GPA.RTCMFU/RTCMFD` in the log are the fragments used and discarded. With two RTCM sources the driver switches to full message parsing; bit 6 of `GPS_DRV_OPTIONS` forces it on, and bit 7 disables it. An alternative without a GCS: the base's radio modem straight into the rover's UART2.

### Fix states and correction age
`GPS_RAW_INT.fix_type` and `GPS.Status` in the log use one scale, `AP_GPS::GPS_Status`: 0 no GPS, 1 no fix, 2 is 2D, 3 is 3D, 4 is DGPS, **5 is RTK float**, **6 is RTK fixed**. Float means the ambiguities are still real-valued, with accuracy on the order of 10–50 cm that "wanders" (a practical guideline; the u-blox data sheet gives no such figure); fixed means they are integers, 1–3 cm. On u-blox the status comes from `carrSoln` in UBX-NAV-PVT. Important: the ArduPilot u-blox driver does not fill `rtk_age_ms` (checked in the 4.6.3 and 4.7.3 source), so `GPS2_RAW.dgps_age` is always 0 for an F9P (`GPS_RAW_INT` has no such field at all); look at the correction age in Mission Planner (the RTK window) or through `RTCMFU`; only the ERB, NOVA and SBF drivers fill `dgps_age` properly. EKF3 does not distinguish float from fixed: it takes the position measurement noise as `max(GPA.HAcc, EK3_POSNE_M_NSE)²`, and `EK3_POSNE_M_NSE` defaults to 0.5 m on Copter (`AP_NavEKF3_PosVelFusion.cpp`, `R_OBS[3]`). The RTK centimeters reach the filter only if you lower this parameter (0.1–0.2 m for landing); the same goes for velocity, `EK3_VELNE_M_NSE` 0.3 m/s on Copter (0.5 on Plane and Rover).

### Moving baseline: heading from two antennas
If the "base" sits on the frame itself, RTK solves the vector between the antennas to about a centimeter, and its direction is the heading. The error: σ_yaw ≈ atan(σ_rel / L); with σ_rel = 1 cm and L = 1 m that is 0.57°. The ZED-F9P-04B data sheet ("moving base" table) gives a heading accuracy of 0.4° without stating the baseline length in the table; the dependence on length is shown in a separate figure; for L = 30 cm the same formula gives about 2° (an estimate, not a specification). The ArduPilot wiki recommends ≥ 30 cm between the antennas (the code rejects only < 5 cm), and u-blox gives 20–30 cm for a drone. You get heading **standing on the ground**, an advantage over GSF (`EK3_SRC1_YAW = 8`), which needs motion, and over a compass near power wires.

{{diagram:rtk-mb-yaw-chain|The base sends 4072.0 + MSM4 to the rover over UART2, the rover outputs RELPOSNED, the driver checks the baseline length against GPSx_POS and passes heading to EKF3 only with RTK fixed; any failure turns GPS2_RAW.yaw into 65535.}}

ArduPilot 4.7 (the names with a receiver index date from 4.6; before 4.6 they had no index: `GPS_TYPE`, `GPS_TYPE2`, `GPS_POS1_X`, `GPS_MB1_TYPE`, and the upgrade renames them automatically; the `GPS*` names did not change between 4.6 and 4.7):
- `GPS1_TYPE = 17` (uBlox-MovingBaseline-Base), `GPS2_TYPE = 18` (Rover); DroneCAN 22/23; Unicore UM982 25; Septentrio dual antenna 26.
- `GPS1_POS_X/Y/Z`, `GPS2_POS_X/Y/Z` are the antenna phase centers relative to the vehicle center (X forward, Y right, Z down); the driver computes the expected baseline from them. Alternatively, `GPS1_MB_TYPE = 1` and `GPS1_MB_OFS_X/Y/Z` give the base vector relative to the rover directly. ArduPilot has no `GPS_YAW_OFFSET`: these offsets set the baseline orientation.
- The checks: the u-blox driver passes RELPOSNED on only with an RTK-fixed relative solution (flags `carrSolnFixed`, `gnssFixOK`, `relPosValid`, `relPosHeadingValid`, `isMoving` set, `carrSolnFloat`, `refPosMiss`, `refObsMiss` clear; `AP_GPS_UBLOX.cpp`), then `calculate_moving_base_yaw()` requires a baseline ≥ 5 cm, a mismatch between the measured and configured lengths ≤ 20% of the smaller of the two, and a vertical component within the range expected from the frame tilt ± 20% of that length. Otherwise no heading is output.
- `GPS_AUTO_SWITCH = 1` (UseBest); **not 2 (Blend)**. `GPS_DRV_OPTIONS` bit 0 sends RTCM between the modules over a UART2↔UART2 crossover (otherwise ArduPilot relays the base corrections through its own UART); bit 3 does the same over a dedicated CAN port.
- `EK3_SRC1_YAW = 2` (GPS) or `3` (GPS with Compass Fallback). EKF3 clamps the reported accuracy from below at 5° (`min_yaw_accuracy_deg`), and the gate is `EK3_YAW_I_GATE`. In the log: `GPS.Yaw`, `GPA.YAcc`, `XKF3.IYAW` (degrees), `XKF4.SM`.
- `GPS2_RAW.yaw`: 0 means heading is not configured, 65535 configured but currently unavailable, 1…36000 hundredths of a degree (36000 = north). An F9H as the rover reports a dummy length of 1 m, so the baseline-length check does not work with it.

### PX4 in brief
`GPS_UBX_MODE = 2` on the base and `1` on the rover (UART1 of both to the autopilot, the base UART2 → the rover UART2, 5 Hz; modes 3/4 carry RTCM over UART1), `GPS_YAW_OFFSET` is the angle of the "base→rover" baseline from the nose (0 means the rover is in front, 90 on the right), `EKF2_GPS_CTRL` bit 3 "Dual antenna heading" (default 7, 15 with heading). Corrections come from QGroundControl through `GPS_RTCM_DATA`; QGC configures the base for 1005 (0.2 Hz), 1077, 1087, 1097, 1127 and 1230 (1 Hz).

### Where it fits

- **Receives:** the observations of a dual-frequency receiver (`est-gnss`); the RTCM stream from a base or NTRIP: the ground station cuts it into `GPS_RTCM_DATA` packets and sends them over the MAVLink telemetry link (the link itself is in `comp-mavlink`); the antenna positions on the frame.
- **Provides:** centimeter-level position to the EKF, if `EK3_POSNE_M_NSE` is lowered (`ap-ekf`); dual-antenna heading instead of the compass (`est-attitude`); raw logs for PPK, for photogrammetry (`per-mapping`).
- **If you get this wrong:** wrong `GPS1_POS_*` → the measured baseline length disagrees with the configured one, no heading is output (`GPS2_RAW.yaw` = 65535), and the EKF is left without yaw or falls back to the compass with its interference (`ap-ekf`, `el-emi`). The link to the base drops → the corrections go stale, the status falls from fixed to 3D, and the accuracy returns to meters. An error in the base coordinates → the whole survey is shifted by the same amount (`per-mapping`).

## practice
The main path is ArduCopter 4.6.3 SITL (`arducopter -S --model + --defaults copter.parm,copter-gps-for-yaw.parm`). The u-blox simulator always outputs `carrSoln = fixed` (`SIM_GPS_UBLOX.cpp`, `pvt.flags = 0b10000011`), so `fix_type = 6` appears without a base; it is a SITL convention, not an achievement. The moving baseline, on the other hand, is honest: with `SIM_GPS2_HDG = 1` the second receiver computes RELPOSNED from `SIM_GPS_POS_Y`/`SIM_GPS2_POS_Y` and the model's true heading. In 4.6.3 the SIM parameters of the first receiver have no index (`SIM_GPS_ACC`), and those of the second do (`SIM_GPS2_ACC`). In 4.7.3 (as in 4.7.2) both have an index (`SIM_GPS1_POS_Y`, `SIM_GPS1_ACC`, `SIM_GPS1_HDG`), `SIM_GPS2_DISABLE 0` became `SIM_GPS2_ENABLE 1`, and the reference file adds `SIM_GPS1_HDG 4`, declaring the first receiver the moving-baseline base.

### Step 1. The bench parameters
`Tools/autotest/default_params/copter-gps-for-yaw.parm` is the reference: `EK3_SRC1_YAW 2`, `GPS_AUTO_CONFIG 0`, `GPS1_TYPE 17`, `GPS2_TYPE 18`, `GPS1_POS_Y -0.2`, `GPS2_POS_Y 0.2`, the same `SIM_GPS_POS_Y`/`SIM_GPS2_POS_Y`, `SIM_GPS2_DISABLE 0`, `SIM_GPS2_HDG 1` (the file from 4.6.3; in 4.7.3 it has `SIM_GPS1_POS_Y`, `SIM_GPS2_POS_Y`, `SIM_GPS2_ENABLE 1`, `SIM_GPS2_HDG 1`, `SIM_GPS1_HDG 4`). A 0.4 m baseline across the frame: base on the left, rover on the right. We read the parameters through pymavlink (the scripts `examples/sitl-nav-labs/rtk_mb_lab.py` and `rtk_mb_lab2.py`, run commands in the folder's README; an excerpt of the output):

The output was captured on Copter-4.6.3; in 4.7.3 `SIM_GPS_HDG` and `SIM_GPS_ACC` are called `SIM_GPS1_HDG` and `SIM_GPS1_ACC`.

```
== params (copter-gps-for-yaw.parm)
  GPS1_TYPE = 17.0
  GPS2_TYPE = 18.0
  GPS1_POS_Y = -0.20000000298023224
  GPS2_POS_Y = 0.20000000298023224
  GPS1_MB_TYPE = 0.0
  GPS_AUTO_SWITCH = 1.0
  GPS_DRV_OPTIONS = 0.0
  EK3_SRC1_YAW = 2.0
  SIM_GPS_HDG = 0.0
  SIM_GPS2_HDG = 1.0
  SIM_GPS_ACC = 0.30000001192092896
```

### Step 2. Wait for fix 6 and heading
Loop on `GPS2_RAW` while `fix_type < 6`, as the `GPSForYaw` autotest does (`wait_gps_fix_type_gte(6, message_type="GPS2_RAW")`, then yaw 270 ± 5° with a home heading of 270). Our home is set with a heading of 353°:

```
  t+ 8.4s fix_type=1 sats=3 yaw=35306 (cdeg) h_acc=0 mm dgps_age=0 ms
  t+ 8.6s fix_type=6 sats=10 yaw=35300 (cdeg) h_acc=300 mm dgps_age=0 ms
== GPS_RAW_INT (base, instance 1) vs GPS2_RAW (rover, instance 2)
  GPS_RAW_INT: fix_type=6 sats=10 eph=121 h_acc=300 mm v_acc=300 mm vel_acc=0 mm/s yaw=0
  GPS2_RAW:    fix_type=6 sats=10 eph=121 h_acc=300 mm yaw=35300 cdeg dgps_numch=0 dgps_age=0
== GPS yaw vs EKF yaw, 10 samples
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw= 344.48 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw=   0.00 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw=   0.01 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw= 353.00 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw= 353.01 deg
```

Write down: the base has `yaw = 0` (heading not configured), the rover 35300; on the ground the EKF holds 0°, then aligns to 353° without moving a single meter. `h_acc = 300 mm` comes from `SIM_GPS_ACC = 0.3` (in 4.7, `SIM_GPS1_ACC`), not RTK; `dgps_age = 0` because the u-blox driver does not fill the field.

### Step 3. Break the baseline
`GPS2_POS_Y 0.2 → 0.5`: the configured baseline becomes 0.7 m, while the receiver still measures 0.4 m; the difference of 0.3 m is > 20% of the smaller length (0.08 m):

```
== B. GPS2_POS_Y -> 0.5
  [bad-ofs] GPS2_RAW.yaw=35300 cdeg fix=6 h_acc=300 mm   EKF yaw=353.09 deg
  [bad-ofs] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.10 deg
  [bad-ofs] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.21 deg
== C. restored 0.2
  [restored] GPS2_RAW.yaw=35300 cdeg fix=6 h_acc=300 mm   EKF yaw=353.20 deg
== D. SIM_GPS2_HDG -> 0: rover stops sending UBX-NAV-RELPOSNED
  [no-relposned] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.17 deg
  [no-relposned] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.31 deg
```

For the passport: at 65535 the vehicle **does not fall**; EKF3 carries the heading on the gyro (a drift of 0.1–0.2° over 10 s in SITL, degrees per minute on a real IMU), and with `EK3_SRC1_YAW = 2` there is no fallback to the compass. Repeat with `= 3` and look at `XKF4.SM`.

### Step 4. Accuracy in SITL and the log
`SIM_GPS2_ACC 0.3 → 0.02`: a second later `h_acc = 20 mm`; this is what an RTK-fixed receiver looks like in `GPS2_RAW` (in EKF3 this number hits the `EK3_POSNE_M_NSE = 0.5` floor until you lower it). Set `LOG_DISARMED = 1` for 20 s and read the `.BIN` through `DFReader`:

```
GPS {'I': 0, 'Status': 6, 'NSats': 10, 'HDop': 1.21, 'Yaw': 353.0, 'U': 1}
GPA {'I': 0, 'HAcc': 0.3, 'VAcc': 0.3, 'SAcc': 0.0, 'YAcc': 0.0, 'Delta': 200, 'RTCMFU': 0, 'RTCMFD': 0}
GPS {'I': 1, 'Status': 6, 'NSats': 10, 'HDop': 1.21, 'Yaw': 353.0, 'U': 0}
XKF3 {'C': 0, 'IVN': 0.01, 'IPN': 0.0, 'IMX': 0, 'IYAW': -0.29, 'IVT': 0.0}
XKF4 {'C': 0, 'SV': 0.0, 'SP': 0.0, 'SM': 0.01, 'SS': 107327, 'PI': 0}
```

`GPS.Status = 6` on both instances, `GPA.Delta = 200` ms (5 Hz), `XKF3.IYAW = −0.29°` is the heading innovation, `GPA.YAcc = 0` because SITL does not model `accHeading`; on hardware this will be `accHeading` from RELPOSNED, on the order of tenths of a degree to a few degrees depending on the baseline length and the sky (a guideline, not a specification).

### Step 5. Fix type against accuracy on a rover log
The course has no real F9P log, so the script `examples/sitl-nav-labs/rtk_fixlog.py` (60 lines; the same dataset sits next to it as `rtk_fixlog.csv`) generates a 300-second CSV (`t, fix_type, hacc_m, nsats, corr_age_s`): 3D → corrections from second 20 → DGPS → float → fixed at second 60; from second 150 an NTRIP outage of 25 s, the correction age grows to 26 s, and the fix falls back fixed → float → 3D; reconvergence takes 15 s. hAcc per state comes from the data sheet (1.5 m / 0.014 m) and a typical float of 0.25 m. The same script accepts a real CSV from u-center or from a `GPS`+`GPA` log:

```python
# analysis part of rtk_fixlog.py; generate()/load() and the plot are omitted
rows = load(sys.argv[1]) if len(sys.argv) > 1 else generate()
print(f"{len(rows)} fixes, {rows[-1][0] - rows[0][0]:.0f} s")
print(f"{'fix':10} {'n':>4} {'share':>6} {'hAcc mean':>10} {'hAcc p95':>9}")
for k in sorted(FIX):
    h = sorted(r[2] for r in rows if r[1] == k)
    if h:
        print(f"{FIX[k]:10} {len(h):4d} {len(h)/len(rows):6.1%} {sum(h)/len(h):8.3f} m {h[int(len(h)*0.95)]:7.3f} m")
fixed = [r for r in rows if r[1] == 6]
print(f"time-to-fixed from first correction: {fixed[0][0] - next(r[0] for r in rows if r[4] > 0):.0f} s")
lost = [r for r in rows if r[4] >= 10]
print(f"samples with correction age >= 10 s: {len(lost)}, worst age {max(r[4] for r in rows):.0f} s, "
      f"fix during them: {sorted(set(FIX[r[1]] for r in lost))}")
```

```
300 fixes, 299 s
fix           n  share  hAcc mean  hAcc p95
3D           27   9.0%    1.435 m   1.945 m
DGPS         15   5.0%    0.587 m   0.836 m
RTK float    50  16.7%    0.250 m   0.358 m
RTK fixed   208  69.3%    0.014 m   0.019 m
time-to-fixed from first correction: 40 s
samples with correction age >= 10 s: 17, worst age 26 s, fix during them: ['3D', 'RTK float']
```

{{diagram:chart-rtk-fix-hacc|Accuracy jumps by two orders of magnitude between states: a 25 cm float is no good for a landing with a 5 cm threshold, and a 25-second correction outage throws the rover back to meters; watch the correction age, not just the fixed flag.}}

For the passport: the fixed share (69% here), the time to fixed (40 s), the worst correction age (26 s) and the state during the outage.

### Moving to real hardware
The bench: two ZED-F9P units (firmware ≥ 1.3.2), two antennas with ground planes ≥ 40 mm on a 50 cm bar, an autopilot with two free UARTs, Mission Planner, 4G for NTRIP. **Props off for every step**: heading and RTK are checked on a table and a cart, no flight needed.
1. **Single RTK.** One F9P as `GPS1_TYPE = 2`, in RTK/GPS Inject an NTRIP `http://email:none@rtk2go.com:2101/MOUNT` with a mount point ≤ 50 km away. Criterion: `fix_type` 3 → 5 → 6 in < 60 s, `h_acc` ≤ 30 mm, `GPA.RTCMFU` growing, `RTCMFD = 0`. Pull the 4G for 30 s and record after how many seconds the fix dropped to 5 and to 3 (the 60 s limit of `CONSTR_DGNSSTO`).
2. **Your own base.** The second F9P on a tripod, over USB into Mission Planner, survey-in 2 m / 60 s until "Position is Valid," save the position. The rover over telemetry should reach 6. Criterion: fixed holds for 10 min, and the position spread in place is < 3 cm (the script from the "GNSS" module on `GPS.Lat/Lng`).
3. **Moving baseline.** Both modules on the frame: `GPS1_TYPE 17`, `GPS2_TYPE 18`, `GPS1_POS_Y −0.25`, `GPS2_POS_Y +0.25` (0.5 m across, measured with a tape to the phase centers), `GPS_AUTO_SWITCH 1`, `EK3_SRC1_YAW 3`, a UART2↔UART2 crossover and `GPS_DRV_OPTIONS = 1`. Criterion: `GPS2_RAW.yaw` ≠ 0 and ≠ 65535 for 5 min; turn the bar in 90° steps against marks on the table, and `GPS.Yaw` differs from the marks by ≤ 2°; the calibrated compass (`ATTITUDE.yaw` with `EK3_SRC1_YAW = 1`) and the GPS heading disagree by ≤ 3°, accounting for declination. Then enter `GPS2_POS_Y 0.55`: the heading should disappear (65535), which proves the offsets are being read.
4. **Log criteria** for all three: `GPS.Status` ≥ 5 at least 95% of the time, `GPA.Delta` ≈ 200 ms without gaps > 400 ms, `GPA.SAcc` < 0.1 m/s, `GPA.YAcc` < 2°, `XKF3.IYAW` < 5° in magnitude, `XKF4.SM` < 0.5, and no `EKF3 ... yaw re-aligned` in the messages after the first 30 s.

Self-check: the lab is done when (SITL) the script output shows `GPS2_RAW.fix_type = 6` and a `yaw` within ±1° of the home heading, you have shown the switch to 65535 with a broken offset and with RELPOSNED disabled, with the EKF heading continuing, the log contains `GPS.Status = 6` and `XKF3.IYAW`, and the "fix type → hAcc mean/p95" table and the chart are built from the CSV with the fixed share and the worst correction age stated; (hardware) single RTK reached fix 6 with `h_acc` ≤ 30 mm and the degradation time during the NTRIP outage is recorded, your own base holds fixed for 10 min, moving baseline gives heading within 2° of the marks and 3° of the compass, and the log criteria of item 4 are met.

## diagnostics
- **Symptom:** the fix is stuck at 5 (float), fixed never comes
  - Possible cause: the base is farther than 50–100 km, no 1230 (GLONASS float), the rover antenna has no ground plane or sits under the props, multipath.
  - What to do: the nearest mount point, check the RTCM content in the RTK window (1005 + MSM + 1230 should be arriving), raise the antenna, try disabling GLONASS in `GPS1_GNSS_MODE`.
- **Symptom:** fix 6 is there, but the Loiter position is off by meters
  - Possible cause: a base after survey-in with a 2 m error (this is relative accuracy), or a restarted survey-in gave a different point.
  - What to do: for absolute accuracy, known base coordinates; set home and the mission only once fixed.
- **Symptom:** `GPS2_RAW.yaw = 65535` with fix 6
  - Possible cause: the baseline length from `GPSx_POS` disagrees with the measured one by > 20%, the antennas are closer than 5 cm, the antennas are at different heights, RELPOSNED does not arrive (no 4072.0 on UART2, the wrong `GPS_DRV_OPTIONS`).
  - What the log shows: `GPS[1].Yaw = 0`, `GPA[1].YAcc = 0`, the EKF heading slowly drifts.
  - What to do: remeasure the offsets to the phase centers, check the UART2 crossover and baud rate (38400 for 1 Hz, 460800 for 5 Hz), `GPS_AUTO_CONFIG = 1`.
- **Symptom:** `GPS2_RAW.yaw = 0`
  - Possible cause: the rover is not configured as 18/23/25, or the rover and base are swapped (only the rover outputs RELPOSNED).
  - What to do: `GPS2_TYPE = 18`, base 17; on PX4, `GPS_UBX_MODE` 2 on the base and 1 on the rover.
- **Symptom:** the GPS heading differs from the compass by 90° or 180°
  - Possible cause: the signs of `GPS1_POS_Y`/`GPS2_POS_Y` are swapped (on PX4, a wrong `GPS_YAW_OFFSET`).
  - What to do: base on the left → negative `GPS1_POS_Y`; turn the bar and check which way the heading changes.
- **Symptom:** in the log `RTCMFD` grows while `RTCMFU` stays put
  - Possible cause: telemetry loses `GPS_RTCM_DATA` fragments (low baud rate, a crowded link), the sequence id does not match.
  - What to do: 57600+ on telemetry, MSM4 instead of MSM7, lower the base rate to 1 Hz, or a radio modem into the rover's UART2.
- **Symptom:** EKF3 "yaw inconsistent" / `XKF4.SM` > 1 with `EK3_SRC1_YAW = 3`
  - Possible cause: the compass is wrong (power wires) while the GPS heading is right: a source conflict.
  - What to do: compassmot or move the compass; on the bench temporarily set `EK3_SRC1_YAW = 2` and compare `XKF3.IYAW`.

## references
- ArduPilot — GPS for Yaw (moving baseline) | https://ardupilot.org/copter/docs/common-gps-for-yaw.html | primary | A
- ArduPilot — RTK correction: Mission Planner RTK/GPS Inject, NTRIP | https://ardupilot.org/copter/docs/common-rtk-correction.html | primary | A
- ArduPilot source 4.6.3 — AP_GPS params, moving-base checks, SITL GPS (`libraries/AP_GPS/AP_GPS.cpp`, `GPS_Backend.cpp`, `libraries/SITL/SIM_GPS_UBLOX.cpp`, `Tools/autotest/default_params/copter-gps-for-yaw.parm`) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.6.3 | primary | A
- MAVLink common.xml — GPS_RTCM_DATA (233), GPS_INJECT_DATA (123), GPS_FIX_TYPE, GPS_RTK | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A
- u-blox — ZED-F9P-04B Data sheet (RTK accuracy, MB heading 0.4°, update rates) | https://content.u-blox.com/sites/default/files/ZED-F9P-04B_DataSheet_UBX-21044850.pdf | primary | A
- u-blox — ZED-F9H-01B Data sheet (heading rover) | https://content.u-blox.com/sites/default/files/ZED-F9H-01B_DataSheet_UBX-21025012.pdf | primary | A
- u-blox — ZED-F9P Integration manual (TMODE survey-in, RTCM set, DGNSS timeout) | https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf | primary | A
- u-blox — ZED-F9P Moving base application note | https://content.u-blox.com/sites/default/files/documents/ZED-F9P-MovingBase_AppNote_UBX-19009093.pdf | primary | A
- PX4 — RTK GPS heading with dual u-blox F9P | https://docs.px4.io/v1.17/en/gps_compass/u-blox_f9p_heading.html | primary | A
- PX4 — RTK GPS integration (QGC, GPS_RTCM_DATA, RTCM set) | https://docs.px4.io/v1.17/en/advanced/rtk_gps.html | primary | A
- PX4 source v1.18.0 — `src/drivers/gps/params.yaml`, `src/modules/ekf2/params_gnss.yaml` | https://github.com/PX4/PX4-Autopilot/tree/v1.18.0 | primary | A
- Mission Planner source — `ConfigSerialInjectGPS.cs`, `ExtLibs/Utilities/ubx_m8p.cs` (survey-in, RTCM rates, GPS_RTCM_DATA fragments) | https://github.com/ArduPilot/MissionPlanner | primary | B
- RTK2go — community NTRIP caster | http://rtk2go.com/ | secondary | B

## checklist
- I can tell RTK from PPK and know what to log for PPK
- I understand the difference between survey-in and known base coordinates, and where the base error goes
- I know the minimum RTCM3 set (1005, MSM4 ×4, 1230; 4072.0 for MB) and its rates
- I can feed corrections through NTRIP → Mission Planner → `GPS_RTCM_DATA` and read `RTCMFU/RTCMFD`
- I can read fix 5/6 and the correction age; I know that `dgps_age` is not filled for u-blox (4.6 and 4.7)
- I can set up moving baseline (`GPS1_TYPE 17/18`, `GPSx_POS`, `EK3_SRC1_YAW 2/3`) and understand the 5 cm / 20% checks
- I checked the GPS heading in SITL and on the bench against marks and the compass
