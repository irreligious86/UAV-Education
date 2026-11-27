---
id: ap-payload
title: "Payload in ArduPilot: camera, gimbal, relay, release and winch, wiring and parameters"
level: L2
readingTime: 60 min
firmware: ArduCopter 4.7 (checked against 4.7.3)
status: published
added: 2026-11-22
tags:
  - ArduPilot
  - camera
  - gimbal
  - gripper
  - winch
  - CAM1_TYPE
  - MNT1_TYPE
  - payload
related:
  - payload-gimbal
  - per-mapping
  - ap-outputs
  - ap-aux-tune
  - ap-missions
  - ap-safety-fs
  - per-camera
  - ap-lua
  - el-power-design
next:
  - per-mapping
source: content/ardupilot/ap-payload.md
source_hash: dea5e4a3d8b3
---

## summary
A camera, a gimbal, a gripper and a winch use the same flight controller outputs as the motors, but mistakes here look different: the vehicle flies normally, yet there are no pictures, the gimbal points at the sky or the payload is lying in the parking area. Working from ArduCopter 4.7.2, this module follows a command from a switch, a mission or MAVLink to a servo, a relay or a port: the `CAM1_TYPE` and `MNT1_TYPE` types, the trigger and shutter feedback parameters, the conversion of a servo gimbal angle to microseconds, the `GRIP_*` gripper, the `WINCH_*` winch, and the moment DO commands execute in a mission. After the module you choose the camera trigger method, the gimbal type and the release mechanism for specific hardware, and you know which output will move on the ground while the safety switch is on. The lab is a calculation exercise with no hardware and no simulator: a gimbal servo pulse, the trigger distance and the number of pictures in a survey, the georeferencing error, an output plan with a release, and three mistakes in a parameter file.

## theory
### What is in the module and in what order to read it
The module answers "where to plug it in and what to write", not "how the protocol works": the manager and device roles in MAVLink Gimbal v2 and gimbal control from code are covered in `payload-gimbal`, and the overlap and GSD calculation in `per-mapping`. First comes the common path of a command, then three blocks: the camera, the gimbal, and payload release (gripper, winch, relay). Each block has a parameter table followed by a selection table with a rule. Read the safety section before the lab: in the lab you work out which outputs stay live while the safety switch blocks the rest. Output functions, timer groups, GPIO and relays are not repeated here, they are in `ap-outputs`; switch thresholds and behavior are in `ap-aux-tune`.

### The path of a command: source → library → output
Neither a switch nor a mission writes to an output directly. The source calls a library (`AP_Camera`, `AP_Mount`, `AP_Gripper`, `AP_Winch`), the library picks a driver from the `TYPE` parameter, and the driver is what moves the servo, toggles the relay or sends a frame to the port.

{{diagram:ap-payload-paths|Three payload paths: the command arrives at the library, the TYPE parameter selects the driver, and what leaves is a servo pulse, a relay level, UART or MAVLink. Camera type 4 depends on the gimbal driver.}}

Three consequences follow. First, the driver is created at boot, so a change of `CAM1_TYPE`, `MNT1_TYPE`, `GRIP_ENABLE`, `GRIP_TYPE` or `WINCH_TYPE` needs a reboot. Second, while `TYPE` is 0, a command is accepted and silently does nothing. Third, one output can have several sources: a gripper is released by a switch, by a mission and by a failsafe, and each of them has to be accounted for.

There are two cameras and two gimbals: `CAM1_*`, `CAM2_*`, `MNT1_*`, `MNT2_*`. There is one gripper and one winch.

### The camera: `CAM1_TYPE` and the trigger parameters
| `CAM1_TYPE` | Driver | What it does on a trigger |
|---|---|---|
| 0 | None | nothing |
| 1 | Servo | puts the `CAM1_SERVO_ON` pulse on the output with function 10 (CameraTrigger) for the time `CAM1_DURATION`, then `CAM1_SERVO_OFF` |
| 2 | Relay | turns on the relay with `RELAYn_FUNCTION = 4` (Camera) for the time `CAM1_DURATION` |
| 3 | GoPro in Solo Gimbal | only in builds with the 3DR Solo gimbal |
| 4 | Mount | passes the trigger to the gimbal driver (Siyi, Topotek, Viewpro, Xacti) |
| 5 | MAVLink | sends `MAV_CMD_DO_DIGICAM_CONTROL` with the fifth parameter set to 1 to all components |
| 6 | MAVLinkCamV2 | sends `MAV_CMD_IMAGE_START_CAPTURE` to the camera component (type `MAV_TYPE_CAMERA`, compid 100 for the first camera); only on boards with more than 1 MB of flash |
| 7 | Scripting | increments a request counter, and a Lua script takes the picture (`ap-lua`) |
| 8 | RunCam | control of a RunCam camera over UART (`SERIALn_PROTOCOL = 26`); this driver does not take a photo on a trigger, its trigger function returns failure |

| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `CAM1_DURATION` | 0.1 s | 0–5 | how long the servo or relay is held; counted in updates of 20 ms |
| `CAM1_SERVO_ON` / `CAM1_SERVO_OFF` | 1300 / 1100 µs | 1000–2000 | the PWM value when the shutter is activated and deactivated; written as is, `SERVOn_MIN/MAX` are not involved |
| `CAM1_RELAY_ON` | 1 | 0 / 1 | whether the relay goes Low or High when it triggers |
| `CAM1_TRIGG_DIST` | 0 m | 0–1000 | a trigger every N meters; 0 is off |
| `CAM1_INTRVAL_MIN` | 0 s | 0–10 | the minimum time between photos |
| `CAM1_FEEDBAK_PIN` | −1 | −1…127 | the shutter feedback pin; −1 and 0 are off; needs a reboot |
| `CAM1_FEEDBAK_POL` | 1 | 0 / 1 | 0 TriggerLow: the pin goes low on trigger; 1 TriggerHigh: it goes high |
| `CAM1_OPTIONS` | 0 | bit 0 | recording starts at arming and stops at disarming |
| `CAM1_MNT_INST` | 0 | 0, 1, 2 | the mount instance the camera is associated with; 0 means the mount with the same instance number |
| `CAM1_HFOV`, `CAM1_VFOV` | 0° | 0–360, 0–180 | horizontal and vertical field of view for the `CAMERA_FOV_STATUS` message; 0 if unknown |
| `CAM1_ZOM_RAT_MAX`, `CAM1_FOC_RAT_MAX` (since 4.7.3) | 5 %/s | 0–100 | the speed at which the zoom output (function 180) and the focus output (function 92) move for continuous (rate) commands: switches 167/168, `MAV_CMD_SET_CAMERA_ZOOM` / `_FOCUS` with the CONTINUOUS type. Only used by `CAM1_TYPE = 1`; 5 %/s moves across the full range in 20 s, the same as 4.7.2 produced |
| `CAM_MAX_ROLL` | 0° | 0–180 | at a larger roll angle the distance trigger is skipped; 0 means no limit |
| `CAM_AUTO_ONLY` | 0 | 0 / 1 | 1: triggering by distance only in AUTO mode |

From the transmitter, `RCx_OPTION = 9` takes a picture in the high position; 166 is video recording, 167–169 are zoom and focus, 102 is the camera mode. Before 4.7 RunCam was configured with the `CAM_RC_*` parameters, now they are `CAM1_RC_*`.

### How to choose the trigger method
| Camera | Method | What to set | What to check afterwards |
|---|---|---|---|
| A servo presses the shutter button | `CAM1_TYPE = 1`, an output with function 10 | `CAM1_SERVO_ON/OFF` for the actual travel, `CAM1_DURATION` no shorter than the press time | the servo is in a 50 Hz group and on a separate BEC (`ap-outputs`); a picture from switch 9 |
| Wired trigger: the camera waits for a contact closure | `CAM1_TYPE = 2`, a relay on a GPIO, with a transistor or optocoupler between the pin and the camera | `SERVOn_FUNCTION = -1`, `RELAYn_PIN`, `RELAYn_FUNCTION = 4`, `CAM1_RELAY_ON` | the level on the pad with a multimeter; `RELAYn_FUNCTION` is exactly 4, not 1 |
| A camera or companion computer with MAVLink Camera v2 | `CAM1_TYPE = 6` | a port with MAVLink 2, the camera has its own compid | the MAVLink inspector shows the camera `HEARTBEAT` and `CAMERA_INFORMATION` |
| The camera is built into the gimbal | `CAM1_TYPE = 4` | first a working `MNT1_TYPE`, then `CAM1_MNT_INST` | a picture from switch 9; no `Mount: not healthy` line |
| A nonstandard camera | `CAM1_TYPE = 7` | a driver script | `ap-lua` |

The selection rule: take the "smartest" channel the camera supports. MAVLink and a built-in gimbal camera return an acknowledgment and can zoom and record; a relay and a servo are a one-way channel, and the flight controller never learns whether the picture was taken. A servo is the last resort: the mechanics wear out and add delay. The cable pinouts and input levels of specific cameras cannot be checked from the source, so look at the camera documentation (the module marks this as unverified).

**When shutter feedback is needed.** Without it the georeferencing error of a picture is v · τ, where v is the ground speed and τ is the delay from the command to the shutter firing. Compare it with the position accuracy: with ordinary GNSS (2–5 m per `per-mapping`) and ground control points, an error of 1–2 m is lost in the noise and the wire is not needed; with RTK or PPK, where you expect centimeters, the accuracy is lost without `CAM1_FEEDBAK_PIN`. Feedback is worth the wire in one more case: when you need to count missed pictures.

### Triggering by distance: what the firmware does
The camera driver is called 50 times a second. If `CAM1_TRIGG_DIST` is greater than zero, it compares the current position with the point of the last picture and triggers the shutter once the distance is at least the set value. Details from `AP_Camera_Backend.cpp`:

- the distance is horizontal, in a straight line from the point of the previous picture; the first position after enabling is only stored, with no picture;
- the check runs once every 20 ms, so the actual spacing exceeds the set one by up to v · 0.02 s (0.24 m at 12 m/s);
- with `CAM_AUTO_ONLY = 1` outside AUTO, and at a roll angle above `CAM_MAX_ROLL`, the picture is skipped and the reference point does not move;
- if less than `CAM1_INTRVAL_MIN` has passed since the previous picture, the trigger is postponed and fires as soon as the time is up. The vehicle does not slow down for it: the spacing becomes v · `CAM1_INTRVAL_MIN`;
- a servo and a relay do not accept a new trigger until `CAM1_DURATION` has expired;
- if time-based capture is active (`IMAGE_START_CAPTURE` with an interval), triggering by distance does not work.

Commands the firmware understands:

| Command | Parameters | Action |
|---|---|---|
| `DO_SET_CAM_TRIGG_DIST` (206) | p1 is meters; p3 = 1 takes a picture immediately | changes `CAM1_TRIGG_DIST` of the primary camera until reboot, without saving it |
| `DO_DIGICAM_CONTROL` (203) | p5 = 1 is the trigger | one picture |
| `IMAGE_START_CAPTURE` (2000) | p1 is the camera (0 is all), p2 is the interval in s; p3 is the number of pictures | p3 = 1 or p2 = p3 = 0 is one picture; p3 = 0 with p2 > 0 is capture forever |
| `IMAGE_STOP_CAPTURE` (2001) | p1 is the camera | stops the sequence |

{{diagram:chart-ap-payload-trigger-interval|With a 24 m spacing and a minimum interval of 1.5 s the survey holds the spacing up to 16 m/s; above that the spacing grows in proportion to speed, and at 18 m/s with a tailwind the overlap drops from 80 to 77.5 %.}}

How to choose `CAM1_INTRVAL_MIN`: set the camera cycle time (from a picture until it is ready for the next one), measured with the same memory card and format. Then the overlap degrades gradually in a tailwind. With zero, the camera at the same speed simply misses every second picture and the spacing doubles.

### The `CAM` and `TRIG` logs
Both messages have the same fields: `TimeUS`, `I` (instance number), `Img` (image number), `GPSTime`, `GPSWeek`, `Lat`, `Lng`, `Alt`, `RelAlt`, `GPSAlt`, `R`, `P`, `Y`. The difference is when they are written, and that depends on `CAM1_FEEDBAK_PIN`:

| | Pin not set (−1) | Pin set |
|---|---|---|
| At the moment of the trigger command | `CAM` | `TRIG` |
| At the moment the shutter fires | nothing | `CAM`, where `TimeUS` is the time of the edge on the pin |

So `TRIG` appears in the log only with feedback configured; without it there are only `CAM` records, and their time is the moment of the command. With feedback, the time of the edge is taken from the interrupt to microsecond accuracy, but the position in the `CAM` record is read in the next driver update, that is, up to 20 ms later; for centimeter georeferencing the position is interpolated by `TimeUS` from the position records. The difference between the number of `TRIG` and `CAM` records is the number of missed pictures.

The pin must be in GPIO mode: the output has `SERVOn_FUNCTION = -1`, and the number comes from the board `hwdef` (`ap-outputs`). There is no pre-arm check for it, so a wrong number stays silent. The firmware enables the pull resistor itself: up with `CAM1_FEEDBAK_POL = 0`, down with 1. The pulse must last at least 2 ms. The messages are written when bit 15 (Camera) of `LOG_BITMASK` is set; it is set by default.

### The gimbal: `MNT1_TYPE`
| `MNT1_TYPE` | Driver | Connection | What it is |
|---|---|---|---|
| 0 | None | — | no gimbal |
| 1 | Servo | outputs with functions 6–8 | servos with no stabilization of their own: the flight controller subtracts the vehicle attitude |
| 2 | 3DR Solo | — | only in builds for the Solo |
| 3 | Alexmos Serial | UART, `SERIALn_PROTOCOL = 7`, 115200 baud | SimpleBGC controllers |
| 4 | SToRM32 MAVLink | a port with MAVLink | SToRM32 as a MAVLink component |
| 5 | SToRM32 Serial | UART, `SERIALn_PROTOCOL = 8` | SToRM32 over its own protocol |
| 6 | MAVLink (Gremsy, AVT) | a port with MAVLink 2 | a Gimbal v2 device, compid 154; more than 1 MB of flash |
| 7 | BrushlessPWM | outputs with functions 6–8 | a brushless gimbal with PWM inputs; it stabilizes itself |
| 8 | Siyi | UART, `SERIALn_PROTOCOL = 8` | Siyi camera gimbals |
| 9 | Scripting | a Lua script | the driver is in a script |
| 10 | Xacti | DroneCAN | more than 1 MB of flash |
| 11 | Viewpro | UART, `SERIALn_PROTOCOL = 8` | more than 1 MB of flash |
| 12 | Topotek | UART, `SERIALn_PROTOCOL = 8` | |
| 13 | CADDX | UART, `SERIALn_PROTOCOL = 8` | more than 1 MB of flash |
| 14 | XFRobot | UART, `SERIALn_PROTOCOL = 8` | new in 4.7; more than 1 MB of flash |

For protocols 7 and 8 the firmware sets `SERIALn_BAUD = 115` by itself at boot. The UART wiring is flight controller TX to gimbal RX, RX to TX, and a common ground; for Siyi the ArduPilot wiki gives exactly this set: protocol 8, baud 115, `MNT1_TYPE = 8`, `CAM1_TYPE = 4`. The supply voltage and connectors of specific gimbals are not given in the source or on those pages, so take them from the manufacturer. If `MNT1_TYPE` is set but the driver is not in the build, arming is refused with `PreArm: Mount: check TYPE`; if the gimbal does not respond, with `PreArm: Mount: not healthy`.

### Gimbal parameters
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `MNT1_DEFLT_MODE` | 3 | 0–6 | the mode on startup: 0 Retracted, 1 Neutral, 2 MavLink Targeting, 3 RC Targeting, 4 GPS Point, 5 SysID Target, 6 Home Location |
| `MNT1_RC_RATE` | 0 deg/s | 0–90 | 0: the stick sets the angle; above 0: the maximum rate of pilot rate control |
| `MNT1_PITCH_MIN` / `MAX` | −90 / 20° | −90…90 | pitch angle limits; negative is down |
| `MNT1_ROLL_MIN` / `MAX` | −30 / 30° | −180…180 | roll angle limits |
| `MNT1_YAW_MIN` / `MAX` | −180 / 180° | −180…180 | yaw angle limits |
| `MNT1_RETRACT_X/Y/Z` | 0° | −180…180 | the roll, pitch and yaw angles in the retracted position |
| `MNT1_NEUTRAL_X/Y/Z` | 0° | −180…180 | the same for the neutral position |
| `MNT1_LEAD_RLL` / `MNT1_LEAD_PTCH` | 0 s | 0–0.2 | the lead time of a servo gimbal, based on the vehicle roll and pitch rate |
| `MNT1_OPTIONS` | 0 | bits 0–2 | 0: the RC lock state is taken from the previous mode; 1: return to neutral angles on RC failsafe; 2: force FPV (body-frame) lock on roll and pitch in RC targeting mode |
| `MNT1_SYSID_DFLT` | 0 | — | the default target sysID to point at in mode 5; needs a reboot |
| `MNT1_DEVID` | 0 | — | the ID of the detected device; written by the firmware, do not edit it by hand |

Outputs: functions 6, 7 and 8 are yaw, pitch and roll of the first gimbal, and 9 is the retract servo; 12–15 are the same for the second one. The retract servo sits at `SERVOn_MIN` and moves to `SERVOn_MAX` in the retracted mode; since 4.7 it works with any gimbal type, in 4.6 only with a servo gimbal. **Note for an update from 4.6: the polarity was inverted.** In 4.6.3 the retract servo was at `SERVOn_MAX` normally and at `SERVOn_MIN` when retracted, so a gimbal set up on 4.6 stays retracted in normal flight on 4.7 (and extends when you command retract, e.g. for a belly landing); after updating, flip `SERVOn_REVERSED` of that output and check both positions on the bench.

### Servo gimbal: angle → microseconds
For types 1 and 7 the pulse width is calculated by `SRV_Channels::move_servo`. For pitch:

- a is θ · 10 with the fractional part dropped (truncation toward zero: −453.7 → −453, 453.7 → 453);
- v = (a − 10 · `MNT1_PITCH_MIN`) / (10 · `MNT1_PITCH_MAX` − 10 · `MNT1_PITCH_MIN`), then v is constrained to the range from 0 to 1;
- with `SERVOn_REVERSED = 1`, 1 − v is taken;
- PWM = `SERVOn_MIN` + ⌊v · (`SERVOn_MAX` − `SERVOn_MIN`)⌋.

`SERVOn_TRIM` is not in the formula: the lower angle limit is `SERVOn_MIN`, the upper one is `SERVOn_MAX`, and zero degrees lands wherever it happens to. With limits of −90…20 and an output of 1100…1900, zero is 1754 µs, and 1500 µs is −35°. If `MNT1_PITCH_MAX` is not greater than `MNT1_PITCH_MIN`, the servo does not move at all. That is why `SERVOn_MIN/MAX` are chosen to match the mechanical positions for the angles `MNT1_PITCH_MIN` and `MNT1_PITCH_MAX`.

For type 1, θ is the angle relative to the body: θ = target − vehicle pitch (nose down is negative), and then the lead "angular rate · `MNT1_LEAD_PTCH`" is subtracted. For type 7 the target itself goes to the servo: the gimbal stabilizes itself. The retracted and neutral angles go out without the pitch subtraction but through the same limits: `MNT1_RETRACT_Y = 60` with `MNT1_PITCH_MAX = 20` gives the same 20°.

### How to choose the gimbal type
| Hardware | `MNT1_TYPE` | Why | What to check afterwards |
|---|---|---|---|
| Two servos with no controller | 1 | the flight controller calculates the stabilization; accuracy is limited by the servo and the 50 Hz rate | tilt the vehicle on the bench: the camera must stay in place; if it follows with a lag, add `MNT1_LEAD_PTCH` in steps of 0.01 s |
| A brushless gimbal with a PWM input per axis | 7 | the gimbal holds the horizon by itself, the flight controller only sets the angle | the pulse on the output does not change when the vehicle is tilted; type 1 would give double compensation here |
| A SimpleBGC or SToRM32 controller with a UART | 3, 5 or 4 | the flight controller receives the gimbal angles from the gimbal | no `Mount: not healthy`; in the `MNT` log the `Pitch` and `DPitch` fields agree |
| A Siyi, Viewpro, Topotek, CADDX or XFRobot camera gimbal | 8, 11–14 | one UART carries both the angles and the camera (`CAM1_TYPE = 4`) | the same, plus a picture from switch 9 |
| A gimbal with MAVLink Gimbal v2 | 6 | the standard protocol; the roles are in `payload-gimbal` | the inspector shows component 154 |

The rule: if the gimbal has its own controller, never set type 1, because the attitude compensation adds to the gimbal's own. Between PWM and UART choose UART: over PWM the flight controller does not know where the gimbal is actually pointing and logs the commanded angle instead of the measured one. On a board with 1 MB of flash, types 6, 10, 11, 13 and 14 are not available.

### The gimbal from the transmitter and from a mission
In RC targeting mode (`MNT1_DEFLT_MODE = 3`) the axes come from the channels with `RCx_OPTION` 212, 213, 214 (roll, pitch, yaw; 215–217 are the second gimbal). With `MNT1_RC_RATE = 0` the stick sets the angle: θ = MIN + (s + 1) / 2 · (MAX − MIN), where s from −1 to +1 is measured from `RCx_TRIM` with a dead zone. A centered stick is the middle of the range, which for −90…20 is −35°, not the horizon. The switches:

| `RCx_OPTION` | Positions |
|---|---|
| 27 (113 is the second gimbal) | HIGH retracts, LOW returns the default mode |
| 163 Mount Yaw Lock (Mount Lock in 4.6) | HIGH: the camera heading is held relative to the earth, otherwise relative to the nose |
| 185 Mount Roll/Pitch Lock (new in 4.7) | HIGH: roll and pitch are held relative to the horizon, MIDDLE: pitch only, LOW: everything is tied to the body |
| 186 Mount POI Lock (new in 4.7, more than 1 MB of flash) | HIGH: store the point on the ground the camera is looking at and hold it; MIDDLE: suspend; LOW: clear |

These four functions are already executed at boot and on the first receiver frame, from the current switch position (`ap-aux-tune`).

From a mission: `DO_GIMBAL_MANAGER_PITCHYAW` (p1 is pitch, p2 is yaw, p5 is the flags, p7 is the gimbal number, 0 is the primary one), `DO_SET_ROI_LOCATION`, `DO_SET_ROI_NONE`, `DO_MOUNT_CONTROL` (p1 is pitch, p2 is roll, p3 is yaw). The `MOUNT_CONFIGURE` and `MOUNT_CONTROL` messages were removed in 4.7; the commands of the same names remain.

**When a DO command executes.** Per `AP_Mission.cpp`, the DO and CONDITION commands placed between navigation commands A and B are started when A has completed and B has started, one per update. When B completes, whatever has not been executed is discarded. For an action to happen at a waypoint, put it after the waypoint that has a delay, and follow it with a navigation command that lasts longer than all the conditions, for example `NAV_LOITER_TIME` with no coordinates.

### The gripper: `GRIP_*`
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `GRIP_ENABLE` | 0 | 0 / 1 | enable; the other parameters appear after this |
| `GRIP_TYPE` | 0 | 0 None, 1 Servo, 2 EPM | a servo or an electropermanent magnet |
| `GRIP_GRAB` | 1900 µs | 1000–2000 | the PWM value sent to initiate grabbing the cargo |
| `GRIP_RELEASE` | 1100 µs | 1000–2000 | the PWM value sent to release the cargo |
| `GRIP_NEUTRAL` | 1500 µs | 1000–2000 | the PWM value after boot and when neither grabbing nor releasing; 1500 is mid-travel between grab and release |
| `GRIP_REGRAB` | 0 s | 0–255 | for an EPM: the interval at which the grab is repeated; 0 disables it |
| `GRIP_AUTOCLOSE` | 0 s | 0.25–255 | the time after opening at which the gripper closes again; 0 disables it |
| `GRIP_CAN_ID` | 0 | 0–255 | the hardpoint ID for an EPM on CAN |

The output is function 28. The pulses are written as is, without `SERVOn_MIN/MAX`. Type 1 sets `GRIP_GRAB` or `GRIP_RELEASE` and leaves it there; after 0.5 s the state is considered reached. Type 2 gives a pulse for 0.5 s and returns the output to `GRIP_NEUTRAL`, which is how a magnet that needs only a kick is driven. In the 4.7.2 tree the CAN branch of the EPM driver is closed off by macros that are not defined anywhere, so `GRIP_CAN_ID` affects nothing; a DroneCAN node with a cargo hardpoint is driven as a relay with `RELAYn_PIN` 1000–1015 (`ap-outputs`).

Command sources: the `RCx_OPTION = 19` switch (LOW releases, MIDDLE does nothing, HIGH grabs); `DO_GRIPPER` (211: p1 is the gripper number, not used; p2 is 0 to release, 1 to grab); `NAV_PAYLOAD_PLACE` (Copter: a descent until the payload touches down, a release, a climb; the `PLDP_*` parameters); bit 5 of `FS_OPTIONS` (release on any failsafe action other than "none") and bit 2 of `FLIGHT_OPTIONS` (release on thrust loss). `DO_SET_SERVO` also works on the output with function 28, which is a fourth path that bypasses `GRIP_*`.

### Winch, sprayer, parachute, landing gear
**Winch** (Copter only). `WINCH_TYPE`: 0 None, 1 PWM, 2 Daiwa (UART, `SERIALn_PROTOCOL = 31`). `WINCH_RATE_MAX` is 1 m/s (0–10), the line rate with no load; `WINCH_POS_P` is 1 (0.01–10), the P gain of the line length controller; `WINCH_OPTIONS` is 7: bit 0 is spin freely on startup, bit 1 is verbose output, bit 2 is retry if stuck (Daiwa only). The output is function 88: `SERVOn_TRIM` is stop, toward `SERVOn_MAX` deploys line; 133 is the clutch (Daiwa). Switch 44: HIGH holds (rate 0), otherwise the spool is relaxed; channel 45 is the rate from a stick. `DO_WINCH` (42600): p2 is 0 relax, 1 relative length (the line changes by p3), 2 rate; p3 is meters (negative retracts); p4 is m/s. With type 1 the line length is not measured but integrated from the commanded rate. Since 4.7 the winch is built only with more than 2048 KB of flash: ordinary H7 boards with 2 MB have no `WINCH_*` parameters and need a custom build.

**Sprayer** (Copter): `SPRAY_ENABLE`, `SPRAY_PUMP_RATE` (10 % at 1 m/s), `SPRAY_PUMP_MIN`, `SPRAY_SPINNER` (1300 µs), `SPRAY_SPEED_MIN` (100 cm/s); outputs 22 (pump) and 23 (spinner); switch 15, the `DO_SPRAYER` command. When disarmed, the switch runs the pump as a test.

**Parachute**: the output is function 27 or a relay with function 3, the `CHUTE_*` parameters; switches 21–23 are covered in `ap-aux-tune`, and its place in the failure scheme in `ap-safety-fs`. **Landing gear**: function 29, `LGR_*`, switch 29. `DO_SET_SERVO`, `DO_SET_RELAY`, `DO_REPEAT_SERVO` and `DO_REPEAT_RELAY` are in `ap-outputs`.

### How to choose the release mechanism
The thresholds in the table are an engineering estimate, not data from the source: calculate the force from the description of your own mechanism.

| Mechanism | When it fits | What happens to the payload with no power | Main risk |
|---|---|---|---|
| A servo with a pin (`GRIP_TYPE = 1`) | a light payload that hangs on the pin, not on the servo torque | it stays if the mechanism is self-locking | a servo that "holds by torque": when the outputs are blocked or the BEC fails, the payload goes |
| An electropermanent magnet (`GRIP_TYPE = 2`) | a payload with a steel plate, frequent cycles | it stays: the magnet holds with no current | shear and vibration reduce the force; so do a gap and paint |
| A relay: electromagnet, solenoid, burn wire | a one-shot or heavy lock | an electromagnet lets go, a spring lock holds: decide in advance which is safer | the relay level while the flight controller boots and reboots |
| A winch | delivery with no landing and no free fall | depends on the winch brake | the line in the propellers, snagging on an obstacle, swinging |

The rule: size the holding force with a margin of at least three payload weights, and choose the mechanism by what must happen when power is lost. Over people and anything expensive, only lower the payload (winch, `NAV_PAYLOAD_PLACE`), never drop it.

For a release on the move, the lead distance without air drag is x = v · √(2h / g). Assumptions: a point payload, no drag and no wind, zero vertical speed of the vehicle at the moment of release, level ground. For 30 m and 10 m/s that is 2.47 s of fall and 24.7 m; a real payload lands closer, and a light box much closer. The impact speed is then √(2gh) = 24.3 m/s, which is where the requirement for the drop zone comes from.

### Payload safety
- **A release on the ground.** Switch 19 in the LOW position is executed on the first receiver frame: turn the transmitter on with the switch at "release" and the gripper opens. In 4.6 the function was executed even earlier, at boot, when the receiver is silent and the position reads as LOW, so the gripper opened by itself; since 4.7 it sits at `GRIP_NEUTRAL` after boot. Hang the payload after turning the transmitter on and checking the switch position.
- **The gripper neutral is mid-travel.** After every boot (and after an in-flight reboot, for example from a brownout) a type 1 gripper servo goes to `GRIP_NEUTRAL`, by default 1500 µs, mid-travel between grab (1900) and release (1100), before any switch or command. A pin that holds the payload may already be out of the payload lug halfway, or be holding it by the edge. For a servo with a pin, set `GRIP_NEUTRAL` equal to `GRIP_GRAB`, or check on the bench that the pin does not come out at neutral: hang the payload, reboot the flight controller and see where the servo stops.
- **The safety switch does not hold the payload.** The Copter default for `BRD_SAFETY_MASK` is all of outputs 1–14 except the motor outputs (`ap-outputs`): the gripper servo, the gimbal and the parachute move while the safety is on. To make the safety hold everything, write 0; to leave only the gimbal, write the bit of its output. A relay on a GPIO pin of the main processor is not blocked by the switch at all: the write to the pin bypasses the safety logic.
- **Blocking is not holding.** A blocked output produces no pulse. An analog servo with no pulse goes limp: a payload that was held by its torque falls at the very moment you press "safe".
- **Failsafe with a payload.** Bit 5 of `FS_OPTIONS` releases the gripper on any failsafe action other than "none", including over people. Enable it only for a route with nothing underneath.
- **Relay at boot.** For function 1 the level is set by `RELAYn_DEFAULT`; for functions 3 and 4 the firmware turns the relay off at startup. Before the firmware starts, the pin is usually high-impedance, so pull a load that must not fire to its off level with a resistor (`el-power-design`).
- **The winch line.** With the PWM type the length is calculated and drifts; bit 0 of `WINCH_OPTIONS` leaves the spool free after boot, so the payload stays on the ground unless you engage the hold before takeoff. On loss of the transmitter the rate is zeroed only in the stick rate control mode. The altitude margin is the line length plus the swing amplitude.
- **The gimbal and camera** will not bring the vehicle down by themselves, but a gimbal servo against its stop draws stall current and sags the BEC that may also power the receiver.

### What changed between 4.6.3 and 4.7.2
| Before (4.6.3) | After (4.7.2) |
|---|---|
| `CAM_RC_*` (RunCam separate from the camera) | `CAM1_RC_*`, `CAM2_RC_*`, the new type `CAM1_TYPE = 8` |
| `MNT1_TYPE` 0–13, 6 is "Gremsy" | 14 XFRobot added; 6 is "MAVLink (Gremsy/AVT)", the driver was renamed |
| `MNT1_OPTIONS`: bit 0 only | bit 1 (return to neutral angles on RC failsafe) and bit 2 (FPV lock) added |
| `RCx_OPTION` 163 is Mount Lock | 163 is Mount Yaw Lock; 185 and 186 are new |
| the retract servo (9): only with a servo gimbal, `SERVOn_MIN` = retracted | with any gimbal type; `SERVOn_MAX` = retracted (polarity inverted: flip `SERVOn_REVERSED` after the update) |
| with switch 19 assigned, the gripper opens already at boot (the receiver is silent, so the position is LOW) | `GRIP_NEUTRAL` after boot, the switch is executed with the first receiver frame |
| the winch in all builds | only with more than 2048 KB of flash |
| the `MOUNT_CONFIGURE` and `MOUNT_CONTROL` messages are accepted | removed; the commands remain |
| camera servo: trigger and exposure settings | zoom (the new function 180) and focus by servo added; in 4.7.3 their speed is set by `CAMx_ZOM_RAT_MAX` / `CAMx_FOC_RAT_MAX`, and the rate from the command is constrained to ±1 |

The `CAM1_*`, `MNT1_*`, `GRIP_*` and `WINCH_*` names, their defaults and the `move_servo` formula are the same in the two trees (except the retract output polarity, see the table).

### Place in the system
- **Receives:** outputs, groups, GPIO pins and relays from `ap-outputs`; switches from `ap-aux-tune`; mission commands from `ap-missions`; the trigger distance from `per-mapping`; payload power from `el-power-design`.
- **Provides:** the `CAM` and `TRIG` records to georeferencing (`per-mapping`); the gimbal angles in `MNT` and `GIMBAL_DEVICE_ATTITUDE_STATUS` to the picture geometry (`payload-gimbal`); the step change in mass at release to the altitude controller (`ap-tuning`).
- **If you get it wrong here:** `RELAYn_FUNCTION = 1` instead of 4 gives a full set of `CAM` records in the log and an empty memory card, which you find out at home in `per-mapping`; type 1 on a gimbal with its own controller tilts the horizon by twice the angle; bit 5 of `FS_OPTIONS` or a forgotten `BRD_SAFETY_MASK` lets the payload go on a failsafe or in the parking area (`ap-safety-fs`).

## practice
The lab is a calculation exercise: you need no flight controller, simulator or hardware. The parameter files below are a training example assembled by hand; they are not an export from a real vehicle. Every answer follows from the formulas and tables of the theory.

### Step 1. Servo gimbal: angle to microseconds
The camera pitch is a servo on output 8: `MNT1_TYPE = 1`, `SERVO8_FUNCTION = 7`, `MNT1_PITCH_MIN = -90`, `MNT1_PITCH_MAX = 20`, `SERVO8_MIN = 1100`, `SERVO8_MAX = 1900`, `SERVO8_TRIM = 1500`, `SERVO8_REVERSED = 0`. The vehicle sits level unless stated otherwise. Find the pulse:

(a) a target of −90°; (b) a target of 0°; (c) a target of −45°; (d) a target of −45° with `SERVO8_REVERSED = 1`; (e) an angle of +30° reaches the servo; (f) a target of −45° relative to the horizon while the vehicle flies pitched nose down by 10°; (g) the gimbal is retracted, `MNT1_RETRACT_Y = 60`; (h) which angle corresponds to a pulse of 1500 µs?

Result. The angle range is 110°, the pulse range is 800 µs.

| Item | Calculation | Pulse |
|---|---|---|
| (a) | v = 0 | **1100** |
| (b) | v = 900 / 1100 = 0.8182; 0.8182 · 800 = 654.5 → 654 | **1754** |
| (c) | v = 450 / 1100 = 0.4091; 327.3 → 327 | **1427** |
| (d) | 1 − 0.4091 = 0.5909; 472.7 → 472 | **1572** |
| (e) | v = 1200 / 1100 > 1, constrained to 1 | **1900** |
| (f) | θ = −45 − (−10) = −35°; v = 550 / 1100 = 0.5 | **1500** |
| (g) | 60° is above the 20° limit, v is constrained to 1 | **1900** |
| (h) | v = 0.5 → θ = −90 + 0.5 · 110 | **−35°** |

The conclusion from (g): the retracted position coincides with the upper limit of the working travel, and there is no separate "parking" position. If you need one, widen `MNT1_PITCH_MAX` (and choose `SERVO8_MAX` again) or put a retract servo on function 9. The conclusion from (b) and (h): `SERVO8_TRIM = 1500` takes no part in the calculation.

### Step 2. Triggering by distance
Data from `per-mapping`: altitude 100 m, picture footprint 180 × 120 m, the long side across the flight line, forward overlap 80 %. The flight line is 610 m, the planned ground speed is 12 m/s, the camera cycle time is 1.5 s, the shutter delay is 0.12 s.

(a) Which `CAM1_TRIGG_DIST` do you write? (b) How many pictures will there be on the line if the `DO_SET_CAM_TRIGG_DIST` command at its start is given with p3 = 0, and how many with p3 = 1? (c) The interval between pictures at 12 m/s and the speed limit for the camera. (d) On the return line there is a tailwind, the ground speed is 18 m/s, `CAM1_INTRVAL_MIN = 1.5`: what do the spacing and overlap become? And with `CAM1_INTRVAL_MIN = 0`, if the camera misses every second trigger? (e) The georeferencing error of a picture at 12 and 18 m/s without feedback; what is the shift between adjacent opposite lines at 12 m/s? (f) What does `CAM1_FEEDBAK_PIN` change, and what inaccuracy remains?

Result. (a) 120 · (1 − 0.8) = **24 m**. (b) 610 / 24 = 25.4 → **25** pictures; with p3 = 1 a picture at the start is added, **26**. (c) 24 / 12 = **2.0 s**; 24 / 1.5 = **16 m/s**. (d) The distance interval 24 / 18 = 1.33 s is less than 1.5 s, so the trigger waits: the spacing is 18 · 1.5 = **27 m**, the overlap is 1 − 27 / 120 = **77.5 %**. With zero and every other trigger missed, the spacing is 48 m and the overlap is **60 %**. (e) 12 · 0.12 = **1.44 m**, 18 · 0.12 = **2.16 m**; on opposite lines the shifts point in opposite directions: 2 · 1.44 = **2.88 m**. (f) With the pin, the `CAM` record gets the time of the shutter edge and the error from the camera delay disappears; what remains is that the position in the record is taken up to 20 ms later: 12 · 0.02 = **0.24 m**, which is removed by interpolating by `TimeUS`. The moment of the command goes to `TRIG`.

### Step 3. Camera, gimbal and gripper on one board
A quadcopter on a MatekH743, DShot600 motors on outputs 1–4. The groups from `ap-outputs`: {1, 2}, {3, 4, 5, 6}, {7, 8, 9, 10}, {11, 12}, {13}; the GPIO pin number of output n is 49 + n. Needed: a gripper servo, a gimbal pitch servo, a camera trigger through a relay, and shutter feedback.

(a) Draw up an output plan and the parameters. (b) The same plan is moved to a board with a safety switch and the same numbering. `BRD_SAFETY_MASK` was not touched. Which of the four outputs work while the safety is on? Which value do you write so that only the gimbal moves while the safety is on? (c) Write a mission: takeoff to 30 m, fly to a waypoint, camera down, a picture, a release, another picture 2 s later, return. (d) What changes if the last navigation command before the return lasts 1 s?

Result. (a) Outputs 5 and 6 are disabled: they are in a group with motors 3 and 4. The group {7, 8, 9, 10} is free:

```
# training example, assembled by hand
SERVO7_FUNCTION,28
GRIP_ENABLE,1
GRIP_TYPE,1
SERVO8_FUNCTION,7
MNT1_TYPE,1
SERVO9_FUNCTION,-1
RELAY1_FUNCTION,4
RELAY1_PIN,58
CAM1_TYPE,2
SERVO10_FUNCTION,-1
CAM1_FEEDBAK_PIN,59
```

(b) The default is 16383 − 15 = **16368**, outputs 5–14. The bits of outputs 7 (64) and 8 (128) are set: the gripper and the gimbal move while the safety is on. Outputs 9 and 10 are GPIO pins, which the switch does not affect: the camera relay fires too. The gimbal only is **128**; nothing on PWM is **0**.

(c) One of the correct sequences:

| No. | Command | Parameters | When it executes |
|---|---|---|---|
| 1 | `NAV_TAKEOFF` | altitude 30 m | |
| 2 | `NAV_WAYPOINT` | the release point, p1 = 3 s | |
| 3 | `DO_GIMBAL_MANAGER_PITCHYAW` | p1 = −90, p2 = 0, p5 = 0, p7 = 0 | when command 2 has completed |
| 4 | `DO_DIGICAM_CONTROL` | p5 = 1 | next |
| 5 | `DO_GRIPPER` | p1 = 1, p2 = 0 | next |
| 6 | `CONDITION_DELAY` | p1 = 2 s | waits 2 s |
| 7 | `DO_DIGICAM_CONTROL` | p5 = 1 | after the delay |
| 8 | `NAV_LOITER_TIME` | p1 = 6 s, zero coordinates | starts together with command 3 and holds the point |
| 9 | `NAV_RETURN_TO_LAUNCH` | | |

(d) Commands 3–7 execute while command 8 is running. If it lasts 1 s, it completes before the 2 s delay expires, and the remainder, the second picture, is discarded. The release still happens.

### Step 4. Three mistakes in a parameter file
The vehicle from step 3. The gimbal is two servos with no controller. The camera is triggered by a contact closure through an optocoupler, and the hot shoe gives an active-low pulse. The gripper is a servo with a pin. Find the lines that make the system work differently from what was intended.

```
# training example, assembled by hand
MNT1_TYPE,1
MNT1_DEFLT_MODE,3
MNT1_PITCH_MIN,-90
MNT1_PITCH_MAX,20
MNT1_RC_RATE,0
RC6_OPTION,213
SERVO8_FUNCTION,7
SERVO8_MIN,1100
SERVO8_MAX,1900
SERVO8_TRIM,1500
CAM1_TYPE,2
CAM1_DURATION,0.1
CAM1_RELAY_ON,1
CAM1_TRIGG_DIST,0
CAM1_INTRVAL_MIN,1.5
CAM1_FEEDBAK_PIN,59
CAM1_FEEDBAK_POL,0
SERVO9_FUNCTION,-1
RELAY1_FUNCTION,1
RELAY1_PIN,58
SERVO10_FUNCTION,0
RC8_OPTION,9
GRIP_ENABLE,1
GRIP_TYPE,2
GRIP_GRAB,1900
GRIP_RELEASE,1100
GRIP_NEUTRAL,1500
SERVO7_FUNCTION,28
RC7_OPTION,19
FS_OPTIONS,16
```

Result: there are exactly three mistakes. (1) `RELAY1_FUNCTION,1`: the camera driver looks for a relay with function 4 and does not find one; the pin does not change, but the trigger counts as done and a record is logged for every "picture". It must be 4. (2) `SERVO10_FUNCTION,0` with `CAM1_FEEDBAK_PIN,59`: pin 59 is output 10, which has stayed a timer output and not an input; there is no feedback, and the firmware does not report it. It must be −1. (3) `GRIP_TYPE,2` for a servo: 0.5 s after a grab the EPM driver returns the output to `GRIP_NEUTRAL` = 1500 µs, so the servo goes to mid-travel and the pin comes halfway out. It must be 1.

The rest is correct: `CAM1_TRIGG_DIST = 0` means the mission sets the spacing; `CAM1_FEEDBAK_POL = 0` matches an active-low pulse; `SERVO8_TRIM` takes no part in the gimbal calculation; `MNT1_RC_RATE = 0` means the stick sets the angle; `FS_OPTIONS = 16` is bit 4 (the default), and bit 5 "Release Gripper" is not set.

### Moving to real hardware
The propellers are off for the whole check. The servos and loads are powered from a separate BEC. No payload is hung until items 1–4 are done.

1. Save the full parameter list. Write down the groups and pin numbers from the `hwdef.dat` of your board (`ap-outputs`).
2. Set `TYPE` and the output functions, then reboot. Read `BRD_SAFETY_MASK` and decide what must move while the safety is on.
3. Turn the transmitter on, check the position of switch 19, then power the gripper. Exercise "grab, release" from the switch and with a command from the ground station; Messages must show the lines `Gripper load grabbing` and `Gripper load releasing`.
4. Power-cycle the flight controller with the transmitter in both switch positions: write down what the gripper does at boot and on the first receiver frame.
5. The gimbal: measure the pulse on the output at two angles and compare it with the formula of step 1; tilt the vehicle and make sure the compensation goes the right way.
6. The camera: ten triggers from switch 9, and record a short log. Without a feedback pin it has 10 `CAM` records; with the pin, 10 `TRIG` and 10 `CAM`. Compare with the number of files on the card.
7. The first release in flight is from a height of 2–3 m over soft ground, in a mode with altitude hold, with no people nearby.

On hardware the work is done when the gimbal pulse matches the calculation within 5 µs, the number of `CAM` records equals the number of files on the card, and the gripper behavior at boot and on the first receiver frame matches the safety section.

Self-check: the lab is done when:
- step 1: the pulses 1100, 1754, 1427, 1572, 1900, 1500, 1900 µs and the angle −35° match (tolerance ±1 µs: the angle passes through radians in single-precision numbers);
- step 2: 24 m; 25 and 26 pictures; 2.0 s and 16 m/s; 27 m and 77.5 %, 60 % with missed triggers; 1.44, 2.16 and 2.88 m; the remainder of 0.24 m match exactly;
- step 3: the gripper and the gimbal are in the group {7, 8, 9, 10}, the relay and the feedback are on pins 58 and 59 with function −1; the default mask is 16368, for the gimbal alone 128; in the mission all DO commands come after the release point and before a navigation command longer than 2 s;
- step 4: exactly three mistakes are found: relay function 1 instead of 4, output 10 not in GPIO mode, gripper type 2 instead of 1.

**Reference for the self-check.** The correct result is the numbers and lines above. Typical mistakes: (1) in step 1 you got 1500 for 0°: it was calculated from `SERVO8_TRIM`, while the gimbal formula goes from `SERVO8_MIN` by the fraction of the angle range; you got 1755 and 1573: the fraction was rounded, while the firmware truncates it; in (f) you got 1354: the vehicle pitch was added instead of subtracted (−55° instead of −35°). (2) In step 2 you got 96 m: the overlap was taken instead of its complement; 26 pictures with p3 = 0: the picture at the start of the line was counted, which does not exist without p3 = 1; the overlap at 18 m/s stayed 80 %: the trigger waiting for `CAM1_INTRVAL_MIN` was not taken into account. (3) In step 3 a servo was put on output 5 or 6: they are in the TIM5 group with motors; a mask of 192 instead of 128: the gripper bit was left in too; `DO_GRIPPER` was put before the release point: then it executes at the start of the flight toward it. (4) In step 4 `FS_OPTIONS = 16` (the default, without the gripper bit) or `CAM1_TRIGG_DIST = 0` (the mission sets the spacing) was named as a mistake.

## diagnostics
- **Symptom:** the log has a `CAM` record for every picture, but the memory card has no pictures or fewer of them.
  Possible cause: without a feedback pin, `CAM` is the moment of the command, not of the picture. `RELAYn_FUNCTION` is not 4; `CAM1_SERVO_ON/OFF` do not press the button fully; `CAM1_DURATION` is shorter than the camera needs; the camera cannot keep up.
  What to do: check the level on the pad and the servo travel from switch 9; raise `CAM1_DURATION`; set `CAM1_INTRVAL_MIN` from the camera cycle time; to count actual pictures, connect `CAM1_FEEDBAK_PIN`.
- **Symptom:** there is no `TRIG` in the log although pictures were taken.
  Possible cause: `TRIG` is written only when `CAM1_FEEDBAK_PIN` is set; without it the moment of the command is recorded in `CAM`.
  What to do: to check the number of pictures in SITL and without feedback, count `CAM`.
- **Symptom:** `TRIG` records are there, `CAM` records are missing or noticeably fewer.
  Possible cause: the hot shoe pulse does not arrive: the pin is not in GPIO mode, the number is wrong, the `CAM1_FEEDBAK_POL` polarity is reversed, the pulse is shorter than 2 ms; or the camera really is missing pictures.
  What to do: `SERVOn_FUNCTION = -1` on the output of that pin, the number from `hwdef`, a reboot; compare the number of `CAM` records with the number of files.
- **Symptom:** pictures come less often than the calculated spacing on some lines and as planned on others.
  Possible cause: in a tailwind the distance interval is shorter than `CAM1_INTRVAL_MIN`, and the trigger is postponed.
  What to do: calculate d / v for the maximum ground speed; lower the line speed or increase the altitude.
- **Symptom:** the survey continues in the turns and on the way home.
  Possible cause: `DO_SET_CAM_TRIGG_DIST` was not zeroed at the end of the section; `CAM_AUTO_ONLY = 0`.
  What to do: a command with p1 = 0 after the last line, `CAM_AUTO_ONLY = 1`, `CAM_MAX_ROLL` for the turns.
- **Symptom:** the gimbal does not move, and arming is refused: `PreArm: Mount: check TYPE` or `PreArm: Mount: not healthy`.
  Possible cause: the driver of this type is not in the build (a board with 1 MB of flash); the port is not on protocol 8 (or 7 for Alexmos); TX and RX are swapped; there was no reboot after the type change.
  What to do: check the type against the table, check `SERIALn_PROTOCOL`, swap the wires, reboot.
- **Symptom:** when the vehicle tilts, the servo gimbal moves the camera twice as far or the opposite way.
  Possible cause: type 1 on a gimbal with its own stabilization; or the servo is mounted mirrored.
  What to do: for a gimbal with a controller, type 7; for servos, `SERVOn_REVERSED`.
- **Symptom:** with the stick centered the camera looks down at an angle and not at the horizon.
  Possible cause: with `MNT1_RC_RATE = 0` the stick center is the middle of the `MNT1_PITCH_MIN…MAX` range.
  What to do: make the range symmetric, shift `RCx_TRIM`, or switch to rate control (`MNT1_RC_RATE` above 0).
- **Symptom:** the retracted gimbal sits in the same place as at the upper limit.
  Possible cause: `MNT1_RETRACT_Y` is outside the `MNT1_PITCH_MIN…MAX` limits and is constrained.
  What to do: widen the limit or use a retract servo (function 9).
- **Symptom:** Messages shows `Gripper Released`, but the gripper did not move.
  Possible cause: this line is printed by the mission command handler regardless of the result. `GRIP_ENABLE = 0`, `GRIP_TYPE = 0`, there is no output with function 28, or there was no reboot.
  What to do: look for the driver lines `Gripper load releasing` and `Gripper load released`; check the parameters and reboot.
- **Symptom:** half a second after the command the gripper servo goes to the middle position.
  Possible cause: `GRIP_TYPE = 2` (EPM) on a servo.
  What to do: `GRIP_TYPE = 1`, a reboot.
  Consequences: the payload hangs on a half-open pin.
- **Symptom:** after the flight controller is powered on (or rebooted) the gripper pin sits halfway and the payload hangs by the edge.
  Possible cause: a type 1 servo sits at `GRIP_NEUTRAL` = 1500 µs after boot, midway between `GRIP_GRAB` and `GRIP_RELEASE`.
  What to do: `GRIP_NEUTRAL` = `GRIP_GRAB` (or a value at which the pin is certainly closed), a reboot and a check with the payload.
  Consequences: the payload is shaken loose by vibration at takeoff.
- **Symptom:** the gripper opens by itself when the transmitter is turned on.
  Possible cause: switch 19 is at LOW, and the function is executed with the first receiver frame.
  What to do: turn the transmitter on with the switch at HIGH or MIDDLE; hang the payload after that.
- **Symptom:** the gripper opened in flight with no pilot command.
  Possible cause: a failsafe triggered with bit 5 set in `FS_OPTIONS`; thrust loss with bit 2 set in `FLIGHT_OPTIONS`; a `DO_SET_SERVO` on the gripper output in the mission.
  What to do: break both parameters down into bits; find the failsafe event and the mission command in the log.
- **Symptom:** `DO_GRIPPER` or the second picture in the mission did not execute.
  Possible cause: the command comes after `CONDITION_DELAY`, and the next navigation command completed earlier.
  What to do: lengthen the navigation command (`NAV_LOITER_TIME`) or remove the delay.
- **Symptom:** there are no `WINCH_*` parameters in the list.
  Possible cause: since 4.7 the winch is not included in builds for boards with up to and including 2048 KB of flash.
  What to do: build a firmware with the winch on the ArduPilot custom build server.
- **Symptom:** the gripper or the gimbal moves while the safety switch is on.
  Possible cause: the Copter default for `BRD_SAFETY_MASK` is all non-motor outputs.
  What to do: write 0 or a mask of only the outputs you need (`ap-outputs`).

## checklist
- A reboot followed every change of `CAM1_TYPE`, `MNT1_TYPE`, `GRIP_TYPE`, `WINCH_TYPE`
- The camera, gimbal and gripper servos are in a 50 Hz group with no DShot and are powered from a separate BEC
- For a camera on a relay: `RELAYn_FUNCTION = 4`, and the output of the pin has `SERVOn_FUNCTION = -1`
- `CAM1_INTRVAL_MIN` equals the measured camera cycle time; the spacing / the maximum ground speed is no less than it
- I know that without `CAM1_FEEDBAK_PIN` a `CAM` record is the moment of the command, and I have calculated the error v · τ
- A gimbal with its own controller is not type 1; `SERVOn_MIN/MAX` match the angles `MNT1_PITCH_MIN/MAX`
- The retracted gimbal position lies inside the limits or is moved to a retract servo; after an update from 4.6 the retract servo's `SERVOn_REVERSED` is flipped and both positions are checked on the bench
- `BRD_SAFETY_MASK` has been read: while the safety is on, only the outputs I chose move
- The gripper switch is checked before the payload is hung; the payload holds with no pulse on the servo
- `GRIP_NEUTRAL` for a servo with a pin equals `GRIP_GRAB` or has been checked: after a reboot with the payload the pin is closed
- Bit 5 of `FS_OPTIONS` and bit 2 of `FLIGHT_OPTIONS` are set deliberately: there are no people under the route
- In the mission, an action at a waypoint comes after that waypoint and before a navigation command that lasts longer than all the delays
- The first release is from a low height, with no people in the drop zone; the impact speed is calculated

## references
- ArduPilot Copter-4.7.2 AP_Camera_Params.cpp (CAMn_TYPE and the trigger parameters) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Camera/AP_Camera_Params.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Camera_Backend.cpp (triggering by distance, CAM1_INTRVAL_MIN, feedback, CAM and TRIG) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Camera/AP_Camera_Backend.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Camera LogStructure.h (the CAM and TRIG fields) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Camera/LogStructure.h | primary | A
- ArduPilot Copter-4.7.2 AP_Mount_Params.cpp (MNTn_TYPE and the gimbal parameters) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Mount/AP_Mount_Params.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Mount_Servo.cpp (attitude compensation, lead) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Mount/AP_Mount_Servo.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Mount_Backend.cpp (modes, RC targeting, retracted position, retract servo) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Mount/AP_Mount_Backend.cpp | primary | A
- ArduPilot Copter-4.7.2 SRV_Channel_aux.cpp (move_servo: gimbal angle to microseconds) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/SRV_Channel/SRV_Channel_aux.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Gripper.cpp and AP_Gripper_EPM.cpp (GRIP_*, the EPM return to neutral) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Gripper/AP_Gripper.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Winch.cpp and AP_Winch_config.h (WINCH_*, the build condition) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Winch/AP_Winch.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Mission.cpp and AP_Mission_Commands.cpp (parameters and the moment DO commands execute) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Mission/AP_Mission.cpp | primary | A
- ArduPilot Copter-4.7.2 RC_Channel.cpp (functions 9, 19, 27, 163, 185, 186, first execution) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/RC_Channel/RC_Channel.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_SerialManager.cpp (protocols 7, 8, 26, 31 and the 115200 baud rate) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_SerialManager/AP_SerialManager.cpp | primary | A
- ArduPilot Copter-4.7.2 ReleaseNotes.txt (camera, gimbal, gripper and winch changes in 4.7) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/ReleaseNotes.txt | primary | A
- Camera Shutter Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/common-camera-shutter-with-servo.html | primary | A
- Camera Gimbals (the list of supported gimbals) — ArduPilot Copter | https://ardupilot.org/copter/docs/common-cameras-and-gimbals.html | primary | A
- SIYI gimbals (UART wiring and parameters) — ArduPilot Copter | https://ardupilot.org/copter/docs/common-siyi-zr10-gimbal.html | primary | A
- Brushless PWM gimbals — ArduPilot Copter | https://ardupilot.org/copter/docs/common-brushless-pwm-gimbal.html | primary | A
- Servo gimbals — ArduPilot Copter | https://ardupilot.org/copter/docs/common-camera-gimbal.html | primary | A
- Grippers — ArduPilot Copter | https://ardupilot.org/copter/docs/common-gripper-landingpage.html | primary | A
- Daiwa winch — ArduPilot Copter | https://ardupilot.org/copter/docs/common-daiwa-winch.html | primary | A

## notes
Everything the module says about firmware behavior comes from reading the source at tag Copter-4.7.2; the firmware was not built or run in this pass, neither on a board nor in SITL. The comparison with 4.6.3 is based on the tree at tag Copter-4.6.3 and on the parameter metadata of both releases. The numbers of step 1 were recalculated by a script that repeats the `move_servo` arithmetic in single-precision numbers; a difference of 1 µs is possible on a board. Not confirmed by the source and marked in the text: the pinouts, supply voltage and input levels of specific cameras and gimbals, the cycle time and shutter delay of cameras (in step 2 they are given as problem data), the holding forces of grippers and the thresholds of the release mechanism selection table (an engineering estimate). The statement "the safety switch does not block a relay on a GPIO" is based on `AP_HAL_ChibiOS/GPIO.cpp`, where the write to the pin does not check the safety state; it was not checked on IOMCU pins. The wiki page on triggering through a relay (`common-pixhawk-camera-trigger-setup`) described the old parameter names at the time of writing and is not included in the sources.
