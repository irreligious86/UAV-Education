# nav-vtrn — vision-based terrain navigation lab

Code for the course module `nav-vtrn` («Ориентирование по местности камерой»).

- `vtrn_lab.py` — synthetic orthophoto, visual odometry, map matching against the map, a 2-state fusion
  filter, place recognition; prints the error-vs-distance tables used in the module.
- `sitl_vtrn.py` — closed loop on ArduCopter 4.6.3 SITL: renders the nadir frame from the simulator's true
  pose, runs VO + map matching and sends `GPS_INPUT` as GPS2 (`GPS2_TYPE = 14`). Imports `vtrn_lab.py`, keep
  both files side by side.
- `run_sitl.sh` — example SITL start used for the module's runs (adjust paths).

The map is synthetic (no tilt, parallax, shadows or blur). Requires `numpy`, `opencv-python-headless`,
`pymavlink`.
