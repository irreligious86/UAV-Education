# perception-ros2

## per-camera
verified: 16
- severity: outdated
  file: content/companion/per-camera.md
  quote: "`libcamera-hello --list-cameras`"
  fix: "`rpicam-hello --list-cameras` (до Raspberry Pi OS Bookworm — `libcamera-hello`)"
  why: From Bookworm onward the camera apps are named rpicam-*; libcamera-* is the legacy name.
  source: https://raspberrypi.com/documentation/computers/camera_software.html

## per-cv
verified: 15
- severity: imprecise
  file: content/companion/per-cv.md
  quote: "Hailo-8 (Pi AI Kit)"
  fix: "Hailo-8L (Pi AI Kit, 13 TOPS) или Hailo-8 (AI HAT+ 26 TOPS)"
  why: The Raspberry Pi AI Kit ships the Hailo-8L (13 TOPS) module, not the Hailo-8.
  source: https://raspberrypi.com/products/ai-kit

## per-depth-avoid
verified: 30, no findings
(Checked against AC_Avoid.cpp, AP_OAPathPlanner.cpp, AP_OABendyRuler.cpp, AP_Proximity_Params.cpp, AP_Proximity_MAV.cpp and the PX4 collision_prevention doc: AVOID_ENABLE bits, AVOID_BEHAVE 0/1, AVOID_DIST_MAX, AVOID_ACCEL_MAX, AVOID_BACKUP_SPD, OA_TYPE 1/2/3, OA_MARGIN_MAX semantics, OA_BR_LOOKAHEAD, PRX1_TYPE 2/10, PRX1_ORIENT/YAW_CORR, OBSTACLE_DISTANCE ID/specials/frame/angle convention, CP_DIST/CP_DELAY/CP_GUIDE_ANG/CP_GO_NO_DATA default 0, MPC_POS_MODE note, v_max arithmetic.)

## per-edge-ml
verified: 15, no findings

## per-geometry
verified: 25, no findings
(All numeric examples re-computed: f_x from HFOV, 80 px → 10 m, roll 10° → 17.6 m, 1°/100 m → 1.7 m, 60° off-nadir → 7 m, 50 ms@100°/s → ~9 m, 1 px → 12.5 cm, stereo δZ 0.31 m / 1.25 m; OpenCV camera frame; Brown–Conrady signs; CAM/TRIG logs; PLND_CAM_POS_*.)

## per-landing
verified: 35
- severity: error
  file: content/companion/per-landing.md
  quote: "m = mavutil.mavlink_connection("udpout:127.0.0.1:14550", "
  fix: "m = mavutil.mavlink_connection("udpin:127.0.0.1:14550", "
  why: sim_vehicle.py makes MAVProxy *send* (--out) to 127.0.0.1:14550; a script that also udpout-sends to 14550 never reaches the autopilot — it must listen there (udpin) so replies go back to MAVProxy (or connect to tcp:127.0.0.1:5762).
  source: https://github.com/ArduPilot/ardupilot/blob/master/Tools/autotest/sim_vehicle.py
- severity: imprecise
  file: content/companion/per-landing.md
  quote: "Её заполняют, когда PnP даёт полную позу."
  fix: "Её заполняют, когда PnP даёт полную позу. ArduPilot при `position_valid = 1` требует `distance > 0` (иначе сообщение отбрасывается) и `q` не использует; PX4 принимает только `x, y, z` в `MAV_FRAME_LOCAL_NED`."
  why: AC_PrecLand_MAVLink drops position_valid messages with distance<=0 and only uses x,y,z/distance; PX4 requires LOCAL_NED and only x,y,z.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AC_PrecLand/AC_PrecLand_MAVLink.cpp

## per-mapping
verified: 30
- severity: error
  file: content/companion/per-mapping.md
  quote: "`CAM1_AUTO_ONLY` — снимать только в Auto. `CAM1_MAX_ROLL` — не снимать"
  fix: "`CAM_AUTO_ONLY` — снимать только в Auto. `CAM_MAX_ROLL` — не снимать"
  why: AUTO_ONLY and MAX_ROLL are frontend (AP_Camera) params CAM_AUTO_ONLY / CAM_MAX_ROLL; there is no CAM1_ version (CAM1_* = AP_Camera_Params instance group).
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Camera/AP_Camera.cpp
- severity: error
  file: content/companion/per-mapping.md
  quote: "галсах, `CAM1_MAX_ROLL`"
  fix: "галсах, `CAM_MAX_ROLL`"
  why: Same parameter-name error in diagnostics.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Camera/AP_Camera.cpp
- severity: imprecise
  file: content/companion/per-mapping.md
  quote: "— но и пропустит кадры, а не замедлит аппарат."
  fix: "— спуск при этом откладывается до истечения интервала (кадр снимается позже, шаг съёмки растёт), а аппарат не замедляется."
  why: CAMx_INTRVAL_MIN sets trigger_pending and postpones the shot ("Postpone shooting"), it does not drop it.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Camera/AP_Camera_Backend.cpp

## per-tracking
verified: 18
- severity: outdated
  file: content/companion/per-tracking.md
  quote: "(ArduPilot `MNT_*`/`GIMBAL_MANAGER`)"
  fix: "(ArduPilot `MNT1_*`/`GIMBAL_MANAGER`)"
  why: Since ArduPilot 4.3 mount params are per-instance MNT1_*/MNT2_*; MNT_* no longer exists.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Mount/AP_Mount.cpp

## per-visual-nav
verified: 22, no findings
(VISO_TYPE 1=MAVLink, VISO_ORIENT/POS/DELAY_MS, EK3_SRCx_* value 6=ExternalNav, EK3_SRC_OPTIONS bit 1, XKF4 SP/SV, VISP/VISV, EKF2_EV_CTRL bits, /fmu/in/vehicle_visual_odometry, MAVROS odometry/out.)

## ros2-app-arch
verified: 16
- severity: imprecise
  file: content/ros2/ros2-app-arch.md
  quote: "в кольцевом режиме (`--max-bag-duration`, `--max-bag-size`)"
  fix: "с разбиением на файлы (`--max-bag-duration`, `--max-bag-size`; автоудаление старых файлов `--max-bag-files` есть только в новых версиях rosbag2, в Humble/Jazzy место на диске нужно чистить самому)"
  why: In Humble/Jazzy/Kilted these flags only split the bag; circular deletion (--max-bag-files) exists only in Rolling.
  source: https://github.com/ros2/rosbag2/blob/rolling/ros2bag/ros2bag/verb/record.py

## ros2-ardupilot
verified: 30
- severity: imprecise
  file: content/ros2/ros2-ardupilot.md
  quote: "локальная поза из EKF, ENU, frame `map`"
  fix: "локальная поза из EKF относительно home, ENU (в `header.frame_id` прошивка пишет `base_link`)"
  why: AP_DDS_Client fills PoseStamped header.frame_id with BASE_LINK_FRAME_ID ("base_link"), not "map"; cmd_vel accepts "map"/"base_link".
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/AP_DDS_Client.cpp

## ros2-basics
verified: 22, no findings
(PX4 publisher QoS BEST_EFFORT+TRANSIENT_LOCAL confirmed in uxrce_dds_client/utilities.hpp; vehicle_status_v1 correct for v1.16/v1.17; ROS_LOCALHOST_ONLY vs ROS_AUTOMATIC_DISCOVERY_RANGE; bag default storage; /ap/time, /ap/clock; ros2 topic pub/echo --qos-reliability; ros2 bag play --clock; static_transform_publisher flags; pitch sign.)

## ros2-from-ros1
verified: 15, no findings

## ros2-nav
verified: 16
- severity: error
  file: content/ros2/ros2-nav.md
  quote: "`OA_MARGIN_MAX`, `OA_LOOKAHEAD`."
  fix: "`OA_MARGIN_MAX`, `OA_BR_LOOKAHEAD`."
  why: There is no OA_LOOKAHEAD; the BendyRuler look-ahead parameter is OA_BR_LOOKAHEAD.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AC_Avoidance/AP_OABendyRuler.cpp

## ros2-px4
verified: 22
- severity: imprecise
  file: content/ros2/ros2-px4.md
  quote: "PX4 рекомендует ROS 2 Humble на Ubuntu 22.04."
  fix: "Документация PX4 (main) рекомендует ROS 2 Jazzy на Ubuntu 24.04; на Ubuntu 22.04 — Humble (так же указано в документации релизов v1.16/v1.17)."
  why: The current main ROS 2 user guide names Jazzy/Ubuntu 24.04 as recommended; Humble remains recommended only in release-branch docs.
  source: https://docs.px4.io/main/en/ros2/user_guide.html
- severity: imprecise
  file: content/ros2/ros2-px4.md
  quote: "`/fmu/out/vehicle_local_position_v1`"
  fix: "`/fmu/out/vehicle_local_position_v1` (в PX4 v1.16 — без суффикса, имя берите из `MESSAGE_VERSION`)"
  why: VehicleLocalPosition has MESSAGE_VERSION 0 in v1.16.0 (no suffix) and 1 only from v1.17 — hard-coded name breaks on v1.16.
  source: https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/msg/versioned/VehicleLocalPosition.msg

## unverified
- per-camera: CSI ribbon "до ~30 см без усилителя" and typical latency figures (30–60 / 60–120 / 150–300 ms) — rules of thumb, no authoritative source.
- per-visual-nav: "Luxonis OAK-D (стерео, VIO в прошивке)" — could not confirm on-device VIO as a shipped firmware feature.
- per-visual-nav: wording of EK3_SRC_OPTIONS bit 1 ("выравнивание ExternalNav с потоком при переключении") vs source "AlignExtNavPosWhenUsingOptFlow" — roughly matches, left as is.
- per-edge-ml / per-cv: speed/accuracy ratios (TensorRT ×3–10, INT8 ×2, −1–3 % mAP, Pi 5 fps) — workload-dependent.
- ros2-from-ros1: ros1_bridge build requirements for Humble (source build) — consistent with repo README, not re-checked in detail.
