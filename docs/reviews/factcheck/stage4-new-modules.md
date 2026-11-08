# stage4-new-modules

Basis: ArduPilot source, master @2a54162 (2026-11-08), and the release branches ArduPilot-4.7 and Plane-4.5 (ArduPlane/Parameters.cpp, ReleaseNotes.txt, libraries/AP_Mount, AP_Camera, AP_Gripper, AP_BLHeli, AP_Motors, Filter/HarmonicNotchFilter, AP_TECS, AP_L1_Control, AP_Landing, APM_Control incl. AP_AutoTune, AP_OpenDroneID, AP_CANManager, AP_DroneCAN, AP_GPS, AP_BattMonitor, AP_RangeFinder, AP_OSD, AP_SerialManager, RC_Channel, SRV_Channel, GCS_MAVLink/GCS_Signing, Tools/AP_Periph). PX4-Autopilot main @68c3a54 (params yaml for gimbal, fw_*, fw_performance_model, uavcan). pymavlink 2.4.50 (signatures and constants checked locally). MAVProxy master mavproxy_signing.py. mavlink-devguide master (gimbal_v2, camera, message_signing sources). Bluejay README and tags (v0.21.0 latest), AM32 README and source (EDT in main.c). betaflight.com docs source (osd-tab, DSHOT-RPM-Filtering, Betaflight-2025.12 CLI commands). ArduRemoteID README. ros2_documentation jazzy About-Security. ardupilot.org pages read through WebFetch: plane AUTOTUNE, TECS tuning, navigation tuning, automatic landing, MAVLink2 signing, BLHeli passthrough, CAN bus setup, MSP OSD, Remote ID, mount targeting, cameras and gimbals. PX4 docs pages: dronecan, config_fw, gimbal_control. The ArduPlane parameters these modules name have the same names in 4.5, 4.7 and master. The 4.7 renames affect Copter and QuadPlane parameters that these modules do not use. In 4.7, RNGFND_LANDING became a bitmask, but value 1 (bit 0 "All") still enables landing use. GPS1_TYPE (renamed from GPS_TYPE in 4.6) is stated correctly.

## el-dronecan
verified: 31
- severity: error
  file: content/electronics/el-dronecan.md
  quote: "вплоть до ESC-моста PWM → CAN"
  fix: "вплоть до ESC-моста CAN → PWM/DShot (узел принимает команды ESC с шины и выдаёт их на обычные регуляторы)"
  why: The AP_Periph ESC bridge goes the other way. It subscribes to uavcan.equipment.esc.RawCommand from the bus and drives PWM/DShot outputs (rc_out.cpp, rcout_esc). It does not convert PWM input into CAN.
  source: https://github.com/ArduPilot/ardupilot/blob/master/Tools/AP_Periph/rc_out.cpp

## link-digital-video
verified: 18

## payload-gimbal
verified: 34
- severity: imprecise
  file: content/companion/payload-gimbal.md
  quote: "В инспекторе MAVLink найти компонент 154 и `GIMBAL_DEVICE_ATTITUDE_STATUS`."
  fix: "В инспекторе MAVLink найти `GIMBAL_DEVICE_ATTITUDE_STATUS` (для серво- и serial-подвесов его шлёт сам автопилот, компонент 1; отдельный компонент 154 появляется только у MAVLink-подвеса)."
  why: With MNT1_TYPE = 1 (servo), the step's own SITL suggestion, no gimbal component 154 exists. ArduPilot's AP_Mount_Backend sends GIMBAL_DEVICE_ATTITUDE_STATUS from the autopilot's own component, so a student following the step will never find component 154.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Mount/AP_Mount_Backend.cpp

## f-esc-firmware
verified: 29
- severity: outdated
  file: content/foundation/f-esc-firmware.md
  quote: "| Bluejay | те же 8-битные ESC, что BLHeli_S |"
  fix: "| Bluejay | 8-битные EFM8 BB21 и BB51 (BB1/BB10 — только до версии 0.18.1) |"
  why: Bluejay now supports only EFM8 BB21 and BB51. BB10 (BB1, "L" layout) was dropped after 0.18.1, so with the module's "Bluejay 0.21+" BB1-based BLHeli_S ESCs are not covered.
  source: https://github.com/bird-sanctuary/bluejay/blob/main/README.md

## ap-plane-tuning
verified: 52

## f-remote-id-security
verified: 33
- severity: imprecise
  file: content/foundation/f-remote-id-security.md
  quote: "Если команда проходит через MAVProxy (он подписывает за всех), подключите скрипт к порту SITL напрямую"
  fix: "Если команда проходит через MAVProxy, это ожидаемо: MAVProxy подключён к SERIAL0 SITL (`tcp:127.0.0.1:5760`), а канал 0 ArduPilot считает защищённым (как USB) и принимает неподписанные пакеты, — подключите скрипт к порту SITL напрямую"
  why: ArduPilot's accept_unsigned_callback always accepts unsigned packets on MAVLINK_COMM_0, the USB-equivalent channel. MAVProxy uses that channel in SITL (5760), so an unsigned command forwarded through it passes whether or not MAVProxy signs it. The advice to use SERIAL2/5763 is right, but the stated reason is not.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/GCS_Signing.cpp
