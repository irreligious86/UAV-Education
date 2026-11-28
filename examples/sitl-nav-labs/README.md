# sitl-nav-labs — ArduCopter SITL labs for navigation modules

Scripts that produce the SITL tables of five course modules (ArduCopter 4.7.2; the `nav-indoor` and `nav-rtk`
outputs were captured on Copter-4.6.3, see the notes below). Each run starts SITL with
`Tools/autotest/default_params/copter.parm` plus a lab parameter file, runs one pymavlink script,
stops SITL and keeps the run folder (`sitl.log`, `feed.log`, `logs/*.BIN`).

| Module | Script | Parameter file | What it shows |
|---|---|---|---|
| `ros2-nav` | `oa_dijkstra_lab.py` | `oa.parm` (control: `oa_nofence.parm`) | `OA_TYPE = 2` flies around a 20 × 20 m exclusion square; prints path, max lateral offset, clearance |
| `per-visual-nav` | `vio_fault_feed.py` | `extnav.parm` | ExternalNav only (`VISION_POSITION_ESTIMATE` from SITL truth); frozen pose, stopped feed, 5 m jump, frozen-pose detector |
| `est-gnss` | `gnss_prearm.py` | none (extra params on the command line) | which GNSS check blocks arming: satellites, hAcc, `GPS_HDOP_GOOD` |
| `nav-indoor` | `extnav_feed.py` | `indoor.parm` (`VISO_DELAY_MS` overridden on the command line) | mocap bridge: `VISION_POSITION_ESTIMATE` from SITL truth with `--lag`/`--noise`; arm without GPS (`--no-origin`), square flight, delay sweep, source jump (`--jump 2`, `--jump-reset`), ENU/NED swap (`--swap-xy`) |
| `nav-rtk` | `rtk_mb_lab.py`, `rtk_mb_lab2.py` | `$ARDUPILOT/Tools/autotest/default_params/copter-gps-for-yaw.parm` | moving-baseline yaw: `GPS2_RAW.yaw` vs EKF yaw, broken baseline (`GPS2_POS_Y`), RELPOSNED off (`SIM_GPS2_HDG 0`), simulated hAcc |
| `nav-rtk` | `rtk_fixlog.py` (no SITL) | none | fix type vs hAcc, time to fixed, correction age; without arguments it generates the 300 s dataset that is also saved as `rtk_fixlog.csv` |

Helpers: `oadj.py <log.BIN>` prints the Dijkstra `OADJ` records and OA/fence parameters; `logsum.py <log.BIN>`
prints `XKF4.SP` (core 0) maxima per 5 s window and the `VISP` count. For `nav-indoor`: `analyze.py <log.BIN>`
(XKF1 vs `SIM` truth in flight, XKF3 innovations, XKF4 test ratios, `VISP`, messages), `timeline.py <log.BIN> <t0> <t1>`
(XKF1/XKF3/XKF4.SP once per second), `truth_at.py <log.BIN> <t>...` (true N/E vs XKF1 at given times).

```bash
export ARDUPILOT=~/ardupilot          # checkout with build/sitl/bin/arducopter (Copter-4.7.2)
./run_lab.sh oa oa.parm "" oa_dijkstra_lab.py
./run_lab.sh oa_nofence_enable oa_nofence.parm "" oa_dijkstra_lab.py   # DO_FENCE_ENABLE is refused (result 4)
./run_lab.sh oa_nofence oa_nofence.parm "" oa_dijkstra_lab.py --no-enable
./run_lab.sh freeze extnav.parm "" vio_fault_feed.py --fault freeze --fault-at 10 --fault-len 20
./run_lab.sh stop extnav.parm "" vio_fault_feed.py --fault stop --fault-at 10 --fault-len 20
./run_lab.sh jump extnav.parm "" vio_fault_feed.py --fault jump --jump 5 --fault-at 10 --fault-len 20
./run_lab.sh freeze_det extnav.parm "" vio_fault_feed.py --fault freeze --fault-at 10 --fault-len 20 --detector
./run_lab.sh g_sats5 - "SIM_GPS1_NUMSATS 5" gnss_prearm.py
python3 oadj.py sitl-run/oa/logs/00000001.BIN
export HOME_LOC=-35.363261,149.165230,584,353 LAB_TIMEOUT=400      # nav-indoor
./run_lab.sh in_noorigin indoor.parm "" extnav_feed.py --no-origin
./run_lab.sh in_50_50 indoor.parm "VISO_DELAY_MS 50" extnav_feed.py --lag 50
./run_lab.sh in_150_50 indoor.parm "VISO_DELAY_MS 50" extnav_feed.py --lag 150   # sweep: --lag vs VISO_DELAY_MS
./run_lab.sh in_jump indoor.parm "" extnav_feed.py --jump 2                     # add --jump-reset for the second run
./run_lab.sh in_swap indoor.parm "" extnav_feed.py --swap-xy
python3 analyze.py sitl-run/in_50_50/logs/00000001.BIN
unset HOME_LOC LAB_TIMEOUT
./run_lab.sh mb_yaw "$ARDUPILOT/Tools/autotest/default_params/copter-gps-for-yaw.parm" "" rtk_mb_lab.py   # nav-rtk
./run_lab.sh mb_yaw2 "$ARDUPILOT/Tools/autotest/default_params/copter-gps-for-yaw.parm" "" rtk_mb_lab2.py
python3 rtk_fixlog.py [rtk_fixlog.csv] [plot.png]       # a real log: CSV t_s,fix_type,hacc_m,nsats,corr_age_s
```

`INSTANCE` (default 3, TCP port 5760 + 10 × INSTANCE) lets several runs go in parallel; `RUN_ROOT` moves the
run folders. SITL runs in real time (`--speedup 1`); a run takes 1–2 minutes. Numbers vary by a few per cent
between runs (timing, wind). Requires `pymavlink`. Extra `"NAME VALUE"` pairs are appended after the parameter
file, so they override it (`VISO_DELAY_MS 150`); `HOME_LOC` changes the home point and heading, `LAB_TIMEOUT` the
script time limit; the parameter file may also be an absolute path.

Version notes. `indoor.parm` is the Copter-4.6.3 file of the `nav-indoor` module: on 4.6.3 the `SIM_GPS1_ENABLE 0`
line is ignored as unknown and GPS is off through `GPS1_TYPE 0`; on 4.7 `ARMING_CHECK` is `ARMING_SKIPCHK`.
`rtk_mb_lab*.py` were run on Copter-4.6.3, where the first receiver's simulator parameters have no index
(`SIM_GPS_HDG`, `SIM_GPS_ACC`); on 4.7 they are `SIM_GPS1_HDG`, `SIM_GPS1_ACC`. The u-blox simulator always
reports RTK fixed, so `fix_type = 6` in SITL does not need a base.
