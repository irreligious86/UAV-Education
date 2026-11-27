---
id: bf-setup-scratch
title: "Betaflight from scratch: from a blank board to the first hover"
level: L2
readingTime: 55 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the SITL lab was captured on 4.5.x (the 4.5-maintenance branch, 7dcc851; version.h 4.5.6, the latest release is 4.5.5)
status: published
added: 2026-11-10
tags:
  - Betaflight
  - setup
  - SITL
  - calibration
  - failsafe
  - first flight
related:
  - bf-intro
  - bf-ports
  - link-elrs
  - link-protocols
  - f-motors-esc
  - bf-modes-osd
  - bf-failsafe
  - link-vtx
  - bf-filters
  - bf-pid
  - bf-blackbox
  - bf-cli
next:
  - bf-filters
  - bf-blackbox
source: content/betaflight/bf-setup-scratch.md
source_hash: 55e8b2cc32f3
---

## summary
One 5″ quadcopter (Betaflight 2025.12, an ELRS receiver, DShot ESCs, an analog or digital VTX) goes from a blank board to a recorded hover. The order is the 17 setup steps of the course. Steps already covered in other modules are given here in one line: what to press in this firmware and where to go for the details. What the course has not covered before is described in detail: calibrating `vbat_scale`, `ibata_scale` and `ibata_offset` with a multimeter and the charger's mAh (the formulas are checked against the 4.5 and 2025.12 sources — they are the same), motor order and direction (`motor_output_reordering`, `resource`, DShot commands through `dshotprog` and the Motor direction dialog), calibrating PWM ESCs, the preflight check and the first hover with abort criteria, and the basics of GPS Rescue. The main path is Betaflight SITL built from source. The lab: a config and a failsafe test in SITL, then the same config on a real aircraft, battery calibration, `diff all` and a log of a 60-second hover.

## theory
### The map of the steps: what, where and with what
{{diagram:bf-setup-flow|The 17 steps go strictly in order: configuration, modes, failsafe and the backup are checked in SITL; the receiver, motors, ESCs and battery — only on the bench without props; the props go on at step 15.}}

| # | Step | Where | Betaflight 2025.12: tab / CLI | Details |
|---|---|---|---|---|
| 1 | Firmware, a backup of the old config | SITL, USB | Firmware Flasher, `diff all` | bf-intro |
| 2 | Orientation, mixer | SITL, USB | Setup, `mixer QUADX`, `align_board_*` | bf-intro |
| 3 | UART ports | SITL (CLI only), USB | Ports, `serial` | bf-ports |
| 4 | Receiver, bind | bench | Receiver, `serialrx_provider = CRSF` | link-elrs |
| 5 | Channels, endpoints, centers | bench | Receiver, `map`, `min_check`, `max_check` | here, link-protocols |
| 6 | Motor protocol | bench | Motors, `motor_pwm_protocol` | f-motors-esc |
| 7 | Order and direction | bench, props off | Motors, `motor_output_reordering`, `dshotprog` | here, bf-cli |
| 8 | ESC calibration (PWM only) | bench, props off | Motors, the master slider | here |
| 9 | Accelerometer | SITL, bench | Setup → Calibrate Accelerometer | bf-intro |
| 10 | Voltage and current | bench + flight | Power & Battery, `vbat_scale`, `ibata_scale`, `ibata_offset` | here |
| 11 | Modes, arming, arming disable flags | SITL | Modes, `aux`, `status` | bf-modes-osd |
| 12 | Failsafe: set up and check | SITL + bench | Failsafe, `failsafe_*` | bf-failsafe |
| 13 | OSD and video | bench | OSD, Video Transmitter | bf-modes-osd, link-vtx |
| 14 | GPS and GPS Rescue (if there is a GPS) | bench + field | `gps_rescue_*`, `ap_hover_throttle` | here, bf-failsafe |
| 15 | Preflight and the first hover | field | — | here |
| 16 | The first tuning | field | filters, PID, sliders | bf-filters, bf-pid |
| 17 | Log, `diff all`, restore | SITL + field | Blackbox, CLI | bf-blackbox, bf-cli |

### What Betaflight SITL can and cannot do
This section and the lab below were verified on SITL 4.5.x (the `4.5-maintenance` branch, commit `7dcc851`: `version.h` says 4.5.6, but there is no such release; the latest release is 4.5.5, and the `src/` code matches it except for the version number in `version.h`); for 2025.12 the lab will be rerun, and the known differences are named along the way. SITL is the same firmware built with an ordinary gcc for Linux (`make TARGET=SITL`). The sensors are virtual (`GYRO=VIRTUAL, ACC=VIRTUAL, BARO=VIRTUAL`), and the UARTs are replaced by the TCP ports `127.0.0.1:576x`: UART1 = 5761, UART2 = 5762. The config is stored in `eeprom.bin` in the current folder, and `save` and `exit` terminate the process — it has to be started again. SITL talks to a simulator over UDP: it receives the aircraft state (FDM) on port 9003 and the RC channels on 9004, and sends the motors to 9002 (Gazebo) and 9001 (RealFlight). Without a simulator the aircraft does not fly, but the CLI, the modes, the arming disable flags, failsafe and `diff all` work as on a board.

What SITL 4.5 does not have: this can be seen in `src/main/target/SITL/target.h` (in 2025.12 the file is in `src/platform/SIMULATOR/target/SITL/`), where the relevant `USE_*` are disabled, and in the CLI responses:
- **DShot.** The default protocol is `DISABLED`, so the `MOTOR_PROTO` flag is set. In SITL `PWM` is used, and the DShot settings (`dshot_bidir` and `dshot_idle_value` — the 4.5 name; in 2025.12 it is `motor_idle`) are not in the SITL 4.5 CLI.
- **Serial receiver, ADC, OSD, VTX, GPS, Blackbox, `resource`.** The CLI answers `get gps_provider` and `get blackbox_device` with `INVALID NAME`, and `resource` with `UNKNOWN COMMAND`. In SITL 2025.12 a virtual GPS (`gps_provider = VIRTUAL`) and Blackbox (`blackbox_device = VIRTUAL`) are enabled in `target.h`.
- **Link loss.** Once the first RC UDP packet has arrived, `rxRCFrameStatus()` in `sitl.c` always returns “frame received”. If the RC stream is stopped, there will be no `RXLOSS` flag. Failsafe in SITL is checked with the FAILSAFE mode on a switch.

### Voltage and current sensors: the formulas from the source
`src/main/sensors/voltage.c` (the formula did not change in 2025.12) converts an ADC reading to a voltage (in units of 0.01 V):

`V = ((ADC · vbat_scale · Vref_mV / 10 + 0xFFF · 5) / (0xFFF · vbat_divider)) / vbat_multiplier`

The voltage is **directly proportional** to `vbat_scale` (110 by default with `vbat_divider` 10 and `vbat_multiplier` 1: V = U_pin · vbat_scale / (vbat_divider · vbat_multiplier) = U_pin · 110/10 = 11 · U_pin — a 10 kΩ : 1 kΩ resistor divider; that is, `vbat_scale` = the divider ratio × 10, not × 100 as in INAV). Hence **new = old × V_multimeter / V_FC**. A step of one unit is 0.9 %, which on a full 6S pack is ≈ 36 mV per cell. The lab criterion (an error of less than 50 mV per cell) is achievable without fractional values.

`src/main/sensors/current.c`: `centiAmps = (mV · 10000 / ibata_scale + ibata_offset) / 10`, that is, the current in mA is `10000 · mV / ibata_scale + ibata_offset`. `ibata_scale` is in mV per 10 A (400 = 40 mV/A, an ACS758 sensor), and `ibata_offset` is in mA. The betaflight.com documentation gives the same units. The current is **inversely proportional** to scale, so **new = old × mAh_FC / mAh_charger**. The offset correction: **new_offset = old_offset + (I_ammeter − I_FC) × 1000**. A negative `ibata_scale` (range −16000…16000) is needed if the sensor is fitted “backwards” and shows a negative current.

Betaflight integrates mAh from the moment power is applied, not from arming (`updateCurrentmAhDrawnState()` always runs). Power the aircraft from a fully charged pack and disconnect it right after landing: then the charger counts exactly what the FC does.

{{diagram:chart-bf-mah-calibration|The mAh reading is inversely proportional to ibata_scale: a flight that gave 905 mAh at 400 against 1032 by the charger reads as 1031 at 351 — inside the ±5 % band.}}

### Motors: order, direction, protocol
In the `QUADX` mixer (`flight/mixer_init.c`) the motors go as follows: 1 — rear right, 2 — front right, 3 — rear left, 4 — front left. With `yaw_motors_reversed = OFF` (props in) the rotation is: 1 — CW, 2 — CCW, 3 — CCW, 4 — CW, viewed from above. `ON` (props out) changes all four directions. A mistake is fixed in different ways:
- **Order.** The simplest way is the Reorder motors dialog in the Motors tab. It writes the `motor_output_reordering` array (the MSP command `MSP2_SET_MOTOR_OUTPUT_REORDERING`). In the driver, mixer motor `i` is output on the `resource MOTOR` pad numbered `motor_output_reordering[i] + 1`. By default the array is `0,1,2,3,4,5,6,7`. The second way is to reassign the pins with `resource MOTOR n <pin>`: that is already a remapping of timers and DMA, and it is covered in bf-cli.
- **Direction.** There is **no** `motor_direction` parameter (neither in 4.5 nor in 2025.12): the direction is stored in the ESC. DShot ESCs (BLHeli_S, Bluejay, BLHeli_32, AM32) accept the commands `DSHOT_CMD_SPIN_DIRECTION_1` (7), `_2` (8) and `DSHOT_CMD_SAVE_SETTINGS` (12). The Motor direction dialog in Betaflight App sends exactly 7 or 8, then 12 (`MSP2_SEND_DSHOT_COMMAND`). From the CLI the same is done by `dshotprog <index> <commands>`, where the index is from 0, and 255 is all the motors. The FC itself repeats the direction and save commands 10 times, as the DShot specification requires. Which of the directions 1/2 turns out to be “normal” depends on how the phases are wired, so always check with your eyes after the command. Without DShot the direction is changed in the ESC configurator or by swapping two phase wires.
- **Protocol.** DShot needs no calibration: the throttle is sent as a number 48…2047. Idle is `motor_idle` = 550 (5.5 %; before 2025.12 — `dshot_idle_value`), that is, 48 + 0.055 · 1999 ≈ 158. PWM, OneShot and Multishot send the throttle as a pulse length, so the ESC has to be taught the 1000 and 2000 µs limits once (`min_command` = 1000, `max_throttle` = 2000; idle in 2025.12 is set by the same `motor_idle`, while 4.5 had a separate `min_throttle` = 1070 for PWM, removed in 2025.12).

### Hover throttle: why know it in advance
Thrust is roughly proportional to the square of the RPM, and the RPM to the throttle. So the hover throttle ≈ √(m / T_max). For a 5″ of 650 g with motors of 1600 g of thrust each (T/W ≈ 9.8) that is √(650/6400) ≈ 0.32, that is, about 30 %. The square is the upper estimate: the real thrust curve lies between a straight line and a square, and with the ArduPilot curve of 0.65 the same T/W gives about 21 % (the table and the bands by class — `f-physics`, “Hover throttle”). Real 5″ quads on 6S hover at 20–35 %. This number is needed three times: as an abort criterion for the first hover (throttle above 60 % — something is wrong), as `ap_hover_throttle` (the autopilot hover throttle: GPS Rescue, ALTHOLD, POS HOLD; before 2025.12 — `gps_rescue_throttle_hover`) and as the AUTO-LAND throttle in failsafe (bf-failsafe).

### Place in the system

- **Receives:** the finished parts from the other modules: ports (`bf-ports`), the receiver (`link-elrs`), modes (`bf-modes-osd`), failsafe (`bf-failsafe`); the multimeter readings and the charger's mAh for sensor calibration.
- **Provides:** calibrated voltage and current — to the OSD warnings (`bf-modes-osd`); the correct motor order and direction — to the first arm (`bf-arming-safety`); the hover throttle — for the AUTO-LAND throttle and `ap_hover_throttle` (`bf-failsafe`); the hover log and `diff all` (`bf-blackbox`).
- **If you get it wrong here:** the motor order or direction is mixed up → a flip at liftoff, RUNAWAY triggers; the symptom table is in `bf-arming-safety`. `ibata_scale` is not calibrated → the mAh in the OSD is wrong, and the capacity warning comes at the wrong time (`bf-modes-osd`).

## practice
### Step 1. Build SITL, connect Betaflight App, save the initial config
Step 1 of 17. The commands and the output were captured on the 4.5-maintenance branch (commit 7dcc851). The branch moves, so clone the tag `-b 4.5.5`: it has the same `src/` code except for the version number, and SITL will call itself 4.5.5. For 2025.12 take `-b 2025.12.5`; the ELF size will be different. The build on gcc 13.3 took about a minute:

```bash
git clone --depth 1 -b 4.5.5 https://github.com/betaflight/betaflight.git && cd betaflight
make arm_sdk_install        # the Makefile checks for arm-none-eabi-gcc even for SITL
make TARGET=SITL            # -> obj/main/betaflight_SITL.elf
mkdir -p ~/bfsitl && cd ~/bfsitl && ~/betaflight/obj/main/betaflight_SITL.elf
```

Without the ARM toolchain `make` stops with `arm-none-eabi-gcc not in the PATH`. This compiler is not used for SITL, so a dummy `arm-none-eabi-gcc` script in the PATH that prints `10.3.1` is enough. That is how I built it:

```text
   text	   data	    bss	    dec	    hex	filename
 291764	  16456	  73832	 382052	  5d464	./obj/main/betaflight_SITL.elf
```

The official way to connect is Betaflight App 2025.12 (the web version) through websockify. Turn on “Enable manual connection mode” in Options and enter `ws://127.0.0.1:6761` in the port field:

```bash
pip3 install --user websockify
python3 -m websockify 127.0.0.1:6761 127.0.0.1:5761
```

I checked the bridge with MSP requests over the websocket: `MSP_API_VERSION` returned 1.46 (that is 4.5; SITL from the branch calls itself 4.5.6), `MSP_FC_VARIANT` — `BTFL`. The CLI is available without the application too: send `#` to TCP 5761. The first thing to do is run `diff all` and save the result. On a real board this is the backup of the old config before flashing.

### Step 2. Quad X, orientation, ports
Steps 2–3. In SITL `mixer` answers `Mixer: QUADX`, `align_board_yaw = 0`. The ports in SITL are set up only with the `serial` command (function 64 = Serial RX), but the build has no serial receiver. So work out the UART allocation for ELRS, GPS and the VTX from the table in bf-ports, and check it on the board.

### Step 3. The accelerometer
Step 9. Calibration runs in SITL too, if FDM packets of a stationary aircraft are fed to port 9003 (the specific force in NED (0, 0, −g), the quaternion w = 1) and `MSP_ACC_CALIBRATION` (205) is sent. I fed a small tilt (0.3; −0.2 m/s²), and after the calibration `get acc_calibration` showed `-6,5,0,1`. The first three numbers are the offsets, and the fourth (`calibrationCompleted` = 1) is the sign of a completed calibration. On a board the same is done by the Calibrate Accelerometer button on a level table.

### Step 4. The battery calibration calculation
Step 10, the calculation part. The measurements are made on hardware, but you check the formulas before that. An example: 6S 1300 mAh. The multimeter on the XT60 showed 24.42 V, the FC — 24.04 V. On the bench (the motors stopped, the VTX at 25 mW) the ammeter showed 0.42 A, the FC — 0.19 A. After a flight with the offset already corrected the OSD showed 905 mAh, and the charger put back 1032 mAh.

The formulas of the script did not change in 2025.12 (`sensors/voltage.c`, `sensors/current.c`).

```python
# Betaflight 4.5 battery-sensor calibration (formulas from sensors/voltage.c and sensors/current.c)
# V ~ vbat_scale (linear)      ->  new = old * V_meter / V_fc
# I = 10000*mV/ibata_scale + ibata_offset [mA]   ->  slope ~ 1/scale  ->  new = old * mAh_fc / mAh_charger
def vbat(old, v_meter, v_fc, cells):
    new = round(old * v_meter / v_fc)
    v_after = v_fc * new / old
    return new, v_after, abs(v_after - v_meter) / cells

def ibat_offset(old_offset_ma, i_meter_a, i_fc_a):
    return round(old_offset_ma + (i_meter_a - i_fc_a) * 1000)

def ibat_scale(old, mah_fc, mah_charger):
    new = round(old * mah_fc / mah_charger)
    return new, mah_fc * old / new

new, v_after, err = vbat(110, 24.42, 24.04, 6)
print(f"vbat_scale: 110 -> {new}; FC would show {v_after:.2f} V; error {err*1000:.0f} mV/cell")
print(f"one vbat_scale step = {100/new:.2f} % = {24.42/new/6*1000:.0f} mV/cell on a full 6S")
print(f"ibata_offset: 0 -> {ibat_offset(0, 0.42, 0.19)} mA")
new_i, mah_after = ibat_scale(400, 905, 1032)
print(f"ibata_scale: 400 -> {new_i}; same flight would read {mah_after:.0f} mAh "
      f"({(mah_after/1032-1)*100:+.1f} % vs charger)")
```

```text
vbat_scale: 110 -> 112; FC would show 24.48 V; error 10 mV/cell
one vbat_scale step = 0.89 % = 36 mV/cell on a full 6S
ibata_offset: 0 -> 230 mA
ibata_scale: 400 -> 351; same flight would read 1031 mAh (-0.1 % vs charger)
```

Strictly speaking, the offset is part of the mAh too: 0.23 A for the 6 minutes from power-up to disconnection is 23 mAh. The exact formula 400 × (905 − 23) / (1032 − 23) gives 350 instead of 351, a difference of 0.3 %. The current in flight is tens of times the quiescent current, so the offset is set first, then the scale, and a control flight checks both corrections.

### Step 5. Modes and arming
Step 11. Setup from a clean `eeprom.bin` in a single CLI batch: ARM on AUX1 (1700–2100), ANGLE on AUX2, the FAILSAFE mode (id 27) on AUX3, the PWM protocol (SITL has no DShot). The actual output, with the `Allowed …` lines removed:

```text
# status
GYRO=VIRTUAL, ACC=VIRTUAL, BARO=VIRTUAL
Arming disable flags: RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO
# mixer
Mixer: QUADX
# set motor_pwm_protocol = PWM
motor_pwm_protocol set to PWM
# aux 0 0 0 1700 2100 0 0
# aux 1 1 1 1300 2100 0 0
# aux 2 27 2 1700 2100 0 0
# set failsafe_switch_mode = STAGE2
failsafe_switch_mode set to STAGE2
# set craft_name = SCRATCH5
# save
Rebooting
SITL exit code after save: 0
```

Five arming disable flags are five reasons why the aircraft will not arm: no RC, the horizon is unknown, the boot time has not elapsed, the CLI is open, no motor protocol is selected. Each following step clears its own flag.

### Step 6. Arming and failsafe from a switch
Step 12. The script starts SITL and does three things: it sends RC packets (a `double` timestamp + 16 × `uint16`) to UDP 9004, feeds the FDM of a stationary aircraft to 9003 and reads the motor outputs from 9002. It takes the arming flags from `MSP_STATUS_EX` (150) over TCP 5761:

The script and the output were captured on 4.5-maintenance; in 2025.12 the last flag is called `ARM_SWITCH` and is on bit 28, and bits 25–27 are `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`, so the `NAMES` table has to be extended for 2025.12.

```python
# Betaflight SITL: arming + failsafe check over MSP (TCP 5761) with RC over UDP 9004
import socket, struct, subprocess, threading, time, sys
NAMES=("NOGYRO FAILSAFE RXLOSS NOT_DISARMED BOXFAILSAFE RUNAWAY CRASH THROTTLE ANGLE BOOTGRACE NOPREARM LOAD "
       "CALIB CLI CMS BST MSP PARALYZE GPS RESCUE_SW DSHOT_TELEM REBOOT_REQD DSHOT_BBANG NO_ACC_CAL "
       "MOTOR_PROTO ARMSWITCH").split()   # fc/runtime_config.c, armingDisableFlagNames[]
sitl=subprocess.Popen([sys.argv[1]],cwd=sys.argv[2],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(2)
rc=[1500,1500,1000,1500]+[1000]*12   # AETR + AUX1..12, throttle low, arm switch low
sending=True; t0=time.time()
def rc_thread():
    u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    while True:
        if sending: u.sendto(struct.pack('<d16H',time.time()-t0,*rc),('127.0.0.1',9004))
        time.sleep(0.02)
threading.Thread(target=rc_thread,daemon=True).start()
def fdm_thread():  # stationary, level airframe on the ground: NED specific force (0,0,-g), quaternion w=1
    u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    while True:
        u.sendto(struct.pack('<d3d3d4d3d3dd',time.time()-t0,0,0,0,0,0,-9.80665,1,0,0,0,0,0,0,0,0,0,101325),('127.0.0.1',9003))
        time.sleep(0.002)
threading.Thread(target=fdm_thread,daemon=True).start()
motors=[0,0,0,0]
def pwm_thread():  # SITL sends motor outputs (0..1) to the simulator port 9002
    u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); u.bind(('127.0.0.1',9002))
    while True:
        d=u.recv(64); motors[:]=struct.unpack('<4f',d[:16])
threading.Thread(target=pwm_thread,daemon=True).start()
m=socket.create_connection(('127.0.0.1',5761)); m.settimeout(1)
def msp(cmd):
    m.sendall(b'$M<'+bytes([0,cmd,cmd])); buf=b''
    while True:
        buf+=m.recv(4096)
        while True:
            i=buf.find(b'$M>')
            if i<0 or len(buf)<i+6 or len(buf)<i+6+buf[i+3]: break
            n=buf[i+3]; c=buf[i+4]; payload=buf[i+5:i+5+n]; buf=buf[i+6+n:]
            if c==cmd: return payload
def status():
    p=msp(150); fm=struct.unpack_from('<I',p,6)[0]; bc=p[15]; o=16+bc
    flags=struct.unpack_from('<I',p,o+1)[0]
    return fm&1, [NAMES[b] for b in range(26) if flags>>b&1]
def show(tag): a,f=status(); print(f"t={time.time()-t0:5.1f}s {tag:34s} armed={a} motors={[round(x,3) for x in motors]} disable={f}")
time.sleep(1); show("boot: RC + FDM, arm switch low")
time.sleep(3); show("after gyro calibration")
rc[2]=1300; rc[4]=1800; time.sleep(0.5); show("arm attempt, throttle 1300")
rc[4]=1000; rc[2]=1000; time.sleep(0.3); rc[4]=1800; time.sleep(0.5); show("arm, throttle 1000 (idle)")
rc[2]=1400; time.sleep(0.5); show("throttle 1400")
rc[6]=1800; time.sleep(0.1); show("FAILSAFE switch on, 0.1 s")
time.sleep(1.0); show("FAILSAFE switch on, 1.1 s")
rc[6]=1000; rc[2]=1000; time.sleep(0.5); show("switch off, arm switch still high")
rc[4]=1000; time.sleep(0.5); show("arm switch low")
rc[4]=1800; time.sleep(0.5); show("re-arm")
sitl.terminate()
```

```text
t=  1.0s boot: RC + FDM, arm switch low     armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['BOOTGRACE']
t=  4.0s after gyro calibration             armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=[]
t=  4.5s arm attempt, throttle 1300         armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['THROTTLE', 'ARMSWITCH']
t=  5.4s arm, throttle 1000 (idle)          armed=1 motors=[0.07, 0.07, 0.07, 0.07] disable=[]
t=  5.9s throttle 1400                      armed=1 motors=[0.412, 0.412, 0.412, 0.412] disable=[]
t=  6.0s FAILSAFE switch on, 0.1 s          armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['FAILSAFE', 'RXLOSS', 'BOXFAILSAFE', 'ARMSWITCH']
t=  7.0s FAILSAFE switch on, 1.1 s          armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['FAILSAFE', 'RXLOSS', 'BOXFAILSAFE', 'ARMSWITCH']
t=  7.5s switch off, arm switch still high  armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['ARMSWITCH']
t=  8.1s arm switch low                     armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=[]
t=  8.6s re-arm                             armed=1 motors=[0.07, 0.07, 0.07, 0.07] disable=[]
```

What the output shows:
- Without FDM the `ANGLE` flag is set: the horizon is not estimated. With FDM it disappears, and `BOOTGRACE` goes away after 3–4 s. On hardware the same flag is set by tilt: `isUpright()` in `flight/imu.c` requires an established attitude **and** a tilt of less than `small_angle` (25° by default, 0–180). The flag is not set while FLIP OVER AFTER CRASH is on.
- Throttle at 1300 on arming gives `THROTTLE`: arming is possible only with the throttle below `min_check` (1050).
- The idle of 0.07 is `min_throttle` 1070 on the 1000–2000 scale (SITL 4.5 with the PWM protocol; 2025.12 has no `min_throttle`, and idle is set by `motor_idle`). At a throttle of 1400 the output is 0.412 = 0.07 + 0.93 × (1400 − 1050) / (2000 − 1050).
- With `failsafe_switch_mode = STAGE2` the switch starts Stage 2 immediately. The default procedure is `DROP`, so after 0.1 s the aircraft is disarmed. The `ARMSWITCH` flag (in 2025.12 — `ARM_SWITCH`) prevents re-arming until the arm switch is lowered. This is protection against an accidental motor restart after the link recovers.

### Step 7. The first tuning and the backup
Steps 16–17. The default filters and PID are fine for the first hover. Without a physical model SITL cannot check them; they are tuned from a log (bf-filters, bf-pid). `diff all` from SITL contains only what you changed:

```text
# name: SCRATCH5
feature -GPS
feature -TELEMETRY
aux 0 0 0 1700 2100 0 0
aux 1 1 1 1300 2100 0 0
aux 2 27 2 1700 2100 0 0
set motor_pwm_protocol = PWM
set failsafe_switch_mode = STAGE2
set craft_name = SCRATCH5
```

The restore check: delete `eeprom.bin`, paste the diff into the CLI of a new SITL (`batch start`, `defaults nosave`, the commands, `save`) and run `diff all` again. For me the `set`/`aux`/`feature` lines matched completely. That is exactly how you will restore the aircraft after reflashing.

### Moving to real hardware
Props off until item 13. The first power-up after soldering is through a smoke stopper. Before the battery is connected a multimeter between + and − must show at least hundreds of ohms.

**1. Firmware (step 1).** `diff all` of the old firmware — to a file. In Betaflight App: the board target, a Cloud Build with the options for this aircraft (CRSF, DShot, OSD SD or HD, GPS, a magnetometer if there is one, the VTX protocol), Full chip erase (bf-intro; the checklist for moving from 4.5 is there too).

**2. Orientation and ports (steps 2–3).** In the Setup tab tilt the aircraft: the model must follow the movement. If the board is rotated, set `align_board_yaw`. In Ports: the receiver UART → Serial Rx; GPS (if there is one) → GPS; VTX → Peripherals: SmartAudio or Tramp for analog, MSP + `osd_displayport_device = MSP` for HD (bf-ports, link-vtx).

**3. Receiver and channels (steps 4–5).** Receiver: Serial, `serialrx_provider = CRSF`. ELRS bind — a binding phrase, and the major ELRS versions on the TX and the RX match (4.x with 4.x; 3.x and 4.x do not link with each other). An on-board SPI receiver under Betaflight 2025.12 is ELRS 3: a module on 4.x needs a separate receiver on a UART (link-elrs). The radio: `map AETR1234`. CRSF in Betaflight gives 988–2012 µs (`rx/crsf.c`: 172 → 988, 1811 → 2012). Fill in the channel table:

| Check | Norm |
|---|---|
| Roll right / pitch forward / throttle up / yaw right | the corresponding channel increases |
| Center of roll, pitch, yaw | 1500 ± 5 |
| Throttle at the bottom | below `min_check` = 1050 (otherwise the `THROTTLE` flag) |
| Throttle at the top | above `max_check` = 1900 |
| AUX switches | every position is no closer than 50 µs to the boundary of the mode range |

**4. Protocol (step 6).** `motor_pwm_protocol = DSHOT600` or `DSHOT300` (the choice by PID rate — f-motors-esc). For Bluejay, BLHeli_32 and AM32: `dshot_bidir = ON`, `motor_poles = 14` — this is the basis of the RPM filter. In Motors check that none of the four motors has telemetry errors.

**5. Order and direction (step 7).** Connect the battery, the Motors tab → “I understand the risks”. Raise each slider in turn to ~1100 and note which motor spins and which way (a strip of tape on the bell). An example: slider 1 spins the front right, slider 2 — the rear right, 3 and 4 are in place. So pad M2 is connected to the rear right and M1 to the front right: `set motor_output_reordering = 1,0,2,3,4,5,6,7` or the Reorder motors dialog. If motor 3 spins CW instead of CCW: the Motor direction dialog or `dshotprog 2 8 12` in the CLI. If it got worse — `dshotprog 2 7 12`. Repeat the check of all four and save (`save`).

**6. ESC calibration (step 8, PWM/OneShot/Multishot only).** The battery is disconnected, the motor test is enabled, the master slider is at 2000. Connect the battery. After the “maximum” tone lower the slider to 1000, wait for the confirmation and disconnect the battery. The check: all the motors start at the same slider value (a difference of ≤ 10 µs). DShot ESCs are not calibrated.

**7. Accelerometer (step 9).** Calibrate Accelerometer on a level table. The `ANGLE` flag disappears from `status` when the aircraft sits level.

**8. Voltage and current (step 10).** Power & Battery: `battery_meter = ADC`, `current_meter = ADC`, `bat_capacity = 1300`. The voltage — a multimeter on the XT60; the FC — the `Voltage:` line in `status`. Compute `vbat_scale` per step 4 and repeat the check on a pack at storage charge (≈ 3.85 V per cell): an error of less than 50 mV per cell at both points. The quiescent current — an ammeter in series with the battery (the 10 A range) → `ibata_offset`. Then a flight using 50–70 % of the capacity (650–900 mAh), disconnect the battery right after landing, balance-charge it to the end → `ibata_scale` from the mAh. A control flight: the difference from the charger is less than 5 %. The firmware guesses the cell count when the battery is connected: `V / vbat_max_cell_voltage + 1` with the fractional part dropped (`sensors/battery.c`, no more than 8). With the default 4.30 V/cell this breaks on HV LiPo (4S at 4.35 V = 17.4 V → “5S”) and on a deeply discharged 6S (21.0 V → “5S”); then `force_battery_cell_count = 6` (0 — auto). `vbat_detect_cell_voltage` = 300 (3.00 V) — below it the battery is considered not connected; `vbat_full_cell_voltage` = 410 — below it, until the first arm, the OSD shows `BATT < FULL`. For Li-Ion `use_cbat_alerts = ON` and `cbat_alert_percent` (10 by default) are useful: a warning by the used capacity `bat_capacity`, not by the voltage, which on Li-Ion sags under load too early. `vbat_cutoff_percent` (100 by default = off): at the critical voltage the throttle is smoothly limited to this percentage over 10 s (`batteryUpdateLVC()`, `fc/rc.c`); 100 leaves the throttle entirely to the pilot.

**9. Modes (step 11).** Paste the `aux` lines from SITL, and in the Modes tab check that the switches highlight ARM, ANGLE and FAILSAFE. For a 5″, BEEPER and FLIP OVER AFTER CRASH are useful (bf-modes-osd).

**10. Failsafe on the bench (step 12).** Props off, the battery connected. Arm and turn the TX module off in the radio menu. First Stage 1 holds (`failsafe_delay` = 15, 1.5 s), then Stage 2: with `DROP` the aircraft is disarmed, and the OSD shows `FAILSAFE`. Repeat the test with the switch. Record Stage 2 on OSD video or in Blackbox (bf-failsafe).

**11. OSD and video (step 13).** The minimum of elements: average cell voltage, mAh, LQ/RSSI, mode, timer, warnings. The VTX on the bench — 25 mW and only with an antenna (link-vtx).

**12. GPS Rescue, if a GPS is fitted (step 14).** `gps_provider = UBLOX`, 5 Hz or higher. The defaults of the module configuration (`pg/gps.c`): `gps_auto_config = ON` (the FC configures the u-blox itself at every start; with OFF none of the settings below are sent), `gps_update_rate_hz` = 10, `gps_ublox_flight_model = AIRBORNE_4G`, `gps_ublox_use_galileo = OFF`, `gps_sbas_mode = NONE` (AUTO, EGNOS, WAAS, MSAS, GAGAN, NONE), `gps_set_home_point_once = OFF`. For M8/M10: `gps_ublox_use_galileo = ON` (more satellites — a faster fix), `gps_sbas_mode = AUTO` or your regional system (in Europe — `EGNOS`). With NONE the firmware turns SBAS off in the module. Details — bf-gps-setup. The defaults in 2025.12 (`pg/gps_rescue_multirotor.c`, `pg/autopilot_multirotor.c`; the same numbers as in 4.5): `gps_rescue_min_sats` = 8 (the documentation advises 10), `gps_rescue_min_start_dist` = 15 m, `gps_rescue_alt_mode = MAX_ALT`, `gps_rescue_initial_climb` = 10 m, `gps_rescue_return_alt` = 30 m, `gps_rescue_ground_speed` = 750 cm/s, `ap_hover_throttle` = 1275 (before 2025.12 — `gps_rescue_throttle_hover`), `gps_rescue_sanity_checks = RESCUE_SANITY_FS_ONLY`, `gps_rescue_allow_arming_without_fix = OFF`. Do not arm without a confirmed home point: on a real failsafe the aircraft will fall. Enable `failsafe_procedure = GPS-RESCUE` only after item 13, when `ap_hover_throttle` is taken from the log. The first tests — from a switch with `failsafe_switch_mode = STAGE1` over grass, at 30–50 m.

**13. Preflight and the first hover (step 15) — the props go on here.** Before the flight:
- the props are fitted per the props-in scheme and tightened;
- the battery is strapped, and the antennas are far from the props;
- `status` has no flags except `ARM_SWITCH` (in 4.5 — `ARMSWITCH`);
- the OSD shows 4.15–4.20 V per cell;
- Blackbox is erased, the mode is ANGLE.

The site: grass, 10 × 10 m clear, people no closer than 10 m, the pilot 5 m behind the aircraft. Fly the first time in line of sight, without goggles. Arm → throttle up smoothly to liftoff → a hover at 1–1.5 m for 60 s → land → disarm. **Disarm immediately** if at liftoff the aircraft rolls or spins in place: that is the motor order or direction, not PID. Land and investigate if:
- oscillations can be heard or seen;
- the hover throttle is above 60 % or below 12 %;
- in ANGLE without stick input the aircraft drifts more than 1 m in 5 s in calm air (trim the accelerometer);
- under load the voltage is below 3.5 V per cell;
- LQ dropped or the video was lost;
- after 60 s a motor is hot: you cannot keep a finger on it for 5 s.

Write down the hover throttle: `rcCommand[3]` in Blackbox Explorer, the median over 60 s. This value goes into `ap_hover_throttle` (range 1100–1700; in 4.5 — `gps_rescue_throttle_hover`).

**14. The first tuning and the backup (steps 16–17).** The gyro spectrum from the hover log → the filters and the RPM filter (bf-filters, bf-rpm-filter). Then the PID sliders (bf-pid). After every change — `diff all` with the date and version, in a file and in git.

Self-check: the lab is complete when:
- **SITL**: Betaflight SITL is built (the lab was captured on 4.5-maintenance). Your repository holds a `diff all` with `aux` for ARM, ANGLE and FAILSAFE and `failsafe_switch_mode`; its `set`/`aux`/`feature` lines match step 7. The script log shows the same sequence as in step 6: an arm (`armed=1`, motors 0.07), the `THROTTLE` block, the triggering of `FAILSAFE`/`BOXFAILSAFE` and the `ARMSWITCH` block (in 2025.12 — `ARM_SWITCH`) after failsafe. Restoring the diff into a clean SITL was checked: the repeated `diff all` matched the original. The calculation of `vbat_scale`, `ibata_offset` and `ibata_scale` was done with the formulas from the source and on the example data gives 112, 230 mA and 351.
- **Hardware**: the channel table is filled in, the motor order and direction correspond to `QUADX`, and calibration is done for PWM ESCs. The voltage error is less than 0.05 V per cell at two points, and the FC's mAh is within 5 % of the charger. Stage 2 failsafe is recorded. The Blackbox log of a 60-second hover and the `diff all` from the real aircraft are saved; the hover throttle (the median of `rcCommand[3]`) is written in the aircraft log and lies between 12 and 60 %.

**Reference for self-check.** The SITL part is correct if the log lines match step 6 in meaning: an arm attempt with the throttle at 1300 — `armed=0` and `['THROTTLE', 'ARMSWITCH']`; throttle 1400 while armed — an output of 0.412; the FAILSAFE switch — `armed=0` already after 0.1 s; after it arming is possible only through a lowered switch. If the `ANGLE` flag remains and there is no arm at all — the script is not feeding FDM, and the horizon is not estimated. If failsafe did not disarm immediately — the config does not have `failsafe_switch_mode = STAGE2`. An `ibata_scale` of 350 instead of 351 in the battery calculation is not a mistake: that is the exact formula with the offset taken into account (a difference of 0.3 %). On hardware the hover throttle of a typical 5″ on 6S is 20–35 %; a value outside 12–60 % means a problem with the propulsion system or the weight, not with the setup.

## diagnostics
- **Symptom:** `make TARGET=SITL` stops with `arm-none-eabi-gcc not in the PATH`
  - Possible cause: `mk/tools.mk` checks for the ARM toolchain for any target.
  - What to do: `make arm_sdk_install` or a dummy `arm-none-eabi-gcc` script in the PATH that prints the required version (10.3.1).
- **Symptom:** Betaflight App or the CLI see INAV instead of Betaflight (`MSP_FC_VARIANT` = `INAV`)
  - Possible cause: INAV SITL is running on the same machine and uses the same TCP 5760–5761.
  - What to do: close it or run Betaflight SITL in a separate network namespace (`unshare -n`, bring up `lo`).
- **Symptom:** in SITL arming fails with the `ANGLE` flag
  - Possible cause: there is no FDM data, and the horizon is not estimated (`isUpright()` requires `attitudeIsEstablished`).
  - What to do: feed the FDM of a stationary aircraft to UDP 9003 or connect a simulator.
- **Symptom:** the RC stream is stopped, but `RXLOSS` does not appear
  - Possible cause: in SITL the frame status is always “received” after the first packet.
  - What to do: check failsafe with the FAILSAFE mode on a switch, and link loss — only on hardware.
- **Symptom:** at the first liftoff the aircraft flips or spins in place
  - Possible cause: the motors are not in `QUADX` order, the direction is wrong, or `yaw_motors_reversed` does not match the props.
  - What to do: remove the props, a test in the Motors tab, `motor_output_reordering`, `dshotprog`/Motor direction.
  - Consequences: broken props, frame, sometimes an ESC; on the bench this is caught in 5 minutes.
- **Symptom:** after `dshotprog` the direction did not change
  - Possible cause: the protocol is not DShot, the aircraft is armed, or command 12 was not sent.
  - What to do: DShot, disarm, `dshotprog <i> 8 12`, reconnect the battery and check.
- **Symptom:** the voltage in the OSD differs from the multimeter by 0.3–1 V
  - Possible cause: `vbat_scale` is from another board or was corrected the wrong way.
  - What to do: new = old × V_multimeter / V_FC; increasing scale increases the reading.
- **Symptom:** the mAh in the OSD is 10–30 % less than the charger puts back
  - Possible cause: `ibata_scale` is too high (the current is inversely proportional to scale).
  - What to do: new = old × mAh_FC / mAh_charger, a control flight.
- **Symptom:** PWM ESCs: one motor starts later than the others
  - Possible cause: the ESCs are not calibrated to 1000/2000 µs.
  - What to do: calibration with the master slider without props; move to DShot if the ESC supports it.
- **Symptom:** after a real failsafe GPS Rescue disarms and the aircraft falls
  - Possible cause: there was no home point, too few satellites, or `ap_hover_throttle` (before 2025.12 — `gps_rescue_throttle_hover`) is too low.
  - What to do: arm only with a home point, the hover throttle from the log, tests from a switch with `STAGE1` at a short distance.

## checklist
- SITL is built, the initial `diff all` is saved
- Quad X, orientation, ports and channels are checked, the channel table is filled in
- The DShot protocol, motor order and direction are checked without props; PWM ESCs are calibrated
- `vbat_scale`, `ibata_offset`, `ibata_scale` are calculated and checked with a multimeter and a charger
- ARM, ANGLE, FAILSAFE are on switches; failsafe is checked in SITL and on the bench
- The OSD shows cell voltage, mAh, LQ; GPS Rescue is set up if there is a GPS
- The first hover of 60 s with Blackbox, the hover throttle is written down
- `diff all` from the real aircraft and the log are saved, the restore is checked

## references
- Betaflight voltage.c (the vbat_scale formula), the 4.5-maintenance branch | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/voltage.c | primary | A
- Betaflight current.c (the ibata_scale, ibata_offset formula) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/current.c | primary | A
- Betaflight dshot_command.h (DShot commands 7, 8, 12, 20, 21) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/drivers/dshot_command.h | primary | A
- Betaflight SITL README | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/target/SITL/README.md | primary | A
- Betaflight SITL (build, websockify, Betaflight App) | https://betaflight.com/docs/development/SITL | primary | A
- Betaflight Power & Battery tab | https://betaflight.com/docs/wiki/configurator/power-tab | primary | A
- Betaflight Battery (the units of amperage_meter_scale, offset) | https://betaflight.com/docs/development/Battery | primary | A
- Betaflight Motors tab | https://betaflight.com/docs/wiki/configurator/motors-tab | primary | A
- Betaflight GPS Rescue 4.5 | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5 | primary | A
- Betaflight Configurator: the Motor direction dialog (commands 7/8 + 12) | https://github.com/betaflight/betaflight-configurator/blob/master/src/composables/motors/escDshotDirection/EscDshotDirectionMotorDriver.ts | primary | A

## notes
GPS Rescue: the 4.5 documentation page gives a minimum start distance of 30 m, while the source (`pg/gps_rescue.c` in 4.5, `pg/gps_rescue_multirotor.c` in 2025.12.5) sets `minStartDistM = 15` (range 10–30). Trust the source of your own firmware: `get gps_rescue_min_start_dist`.
