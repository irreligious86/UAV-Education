# sitl-nav-labs — ArduCopter 4.7.2 SITL labs for navigation modules

Scripts that produce the SITL tables of three course modules. Each run starts SITL with
`Tools/autotest/default_params/copter.parm` plus a lab parameter file, runs one pymavlink script,
stops SITL and keeps the run folder (`sitl.log`, `feed.log`, `logs/*.BIN`).

| Module | Script | Parameter file | What it shows |
|---|---|---|---|
| `ros2-nav` | `oa_dijkstra_lab.py` | `oa.parm` (control: `oa_nofence.parm`) | `OA_TYPE = 2` flies around a 20 × 20 m exclusion square; prints path, max lateral offset, clearance |
| `per-visual-nav` | `vio_fault_feed.py` | `extnav.parm` | ExternalNav only (`VISION_POSITION_ESTIMATE` from SITL truth); frozen pose, stopped feed, 5 m jump, frozen-pose detector |
| `est-gnss` | `gnss_prearm.py` | none (extra params on the command line) | which GNSS check blocks arming: satellites, hAcc, `GPS_HDOP_GOOD` |

Helpers: `oadj.py <log.BIN>` prints the Dijkstra `OADJ` records and OA/fence parameters; `logsum.py <log.BIN>`
prints `XKF4.SP` (core 0) maxima per 5 s window and the `VISP` count.

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
```

`INSTANCE` (default 3, TCP port 5760 + 10 × INSTANCE) lets several runs go in parallel; `RUN_ROOT` moves the
run folders. SITL runs in real time (`--speedup 1`); a run takes 1–2 minutes. Numbers vary by a few per cent
between runs (timing, wind). Requires `pymavlink`.
