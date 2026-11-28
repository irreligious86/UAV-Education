# nav-vtrn — vision-based terrain navigation lab

Code for the course module `nav-vtrn` («Ориентирование по местности камерой»).

- `vtrn_lab.py` — synthetic orthophoto, visual odometry, map matching against the map, a 2-state fusion
  filter, place recognition; prints the error-vs-distance tables used in the module.
- `sitl_vtrn.py` — closed loop on ArduCopter SITL (recorded on 4.6.3; GNSS loss via `SIM_GPS_DISABLE = 1` on 4.6.x or
  `SIM_GPS1_ENABLE = 0` on 4.7.x, whichever exists — the script stops if neither is accepted): renders the nadir frame from the simulator's true
  pose, runs VO + map matching and sends `GPS_INPUT` as GPS2 (`GPS2_TYPE = 14`). Imports `vtrn_lab.py`, keep
  both files side by side.
- `run_sitl.sh` — example SITL start used for the module's runs (adjust paths).
- `dfsum.py` — reads the SITL dataflash log after a run (`python3 dfsum.py sitl-run/logs/00000001.BIN`): which GPS
  the EKF used, GPS/GPA/XKF3/XKF4 rows and the `on GPS2 (vision) ...` summary (XKF4.SP/SV, |IPE|) quoted in the module.

The map is synthetic (no tilt, parallax, shadows or blur). Requires `numpy`, `opencv-python-headless`,
`pymavlink`.
