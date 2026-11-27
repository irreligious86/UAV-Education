---
id: f-safety
title: "Safety and the Pre-Flight Check"
level: L1
readingTime: 40 min
firmware: Betaflight 2025.12 · ArduPilot 4.7 (checked against 4.7.3; the lab was recorded on SITL 4.7.2) · PX4 1.18 (parameters checked against v1.18.0)
status: published
added: 2026-11-07
tags:
  - safety
  - checklist
  - LiPo
  - arming
related:
  - bf-failsafe
  - f-power
  - f-regulations
  - ops-field
next:
  - f-regulations
source: content/foundation/f-safety.md
source_hash: 9dececcbbc89
---

## summary
The tip of a five-inch prop moves at about 330 km/h and carries enough energy to cut skin down to the bone; a LiPo with an internal short delivers hundreds of amps and burns with its own oxidizer: the flame can be knocked down, but the burning resumes until the cells cool. The typical injury in the hobby happens not in the air but on the bench: the drone armed with props on during setup (course guideline, not statistics). The module gives you the physics of the hazard in numbers, the mechanism of thermal runaway, the course's numbers for charging, storing and transporting batteries, the power-up order for a bench without props, what “armed” means in Betaflight, ArduPilot and PX4, the full list of Betaflight's arming disable flags (from the source code, with explanations), pre-flight and post-flight checklists, and what to do in a battery fire. Lab: in ArduCopter 4.7.2 SITL, see the idle RPM after arming and the reaction to an RC loss on the ground and in the air, calculate a battery's energy and transport category, then — a failsafe test on your own aircraft without props.

## theory
### The hazard in numbers
- **Propeller.** Tip speed = π · D · n. For a 5" (D = 0.127 m) in hover at 14,000 rpm (233 rev/s; this is a light aircraft, a heavy 5" hovers at up to ~20,000 — f-frame-mech): 0.40 m × 233 ≈ 93 m/s — about 335 km/h; at full throttle up to ~30,000 rpm (course estimate) — 200 m/s. The kinetic energy of a spinning prop in the thin-rod model E = ½ · I · ω², I = m · D² / 12: a 5" weighing 4 g at 14,000 rpm — 5.8 J, at 30,000 rpm — 26 J; a 7" (9 g) at 9,000 rpm — 10 J; a 10" (18 g) at 6,000 rpm — 19 J (the calculation is in the practice; prop masses are an assumption, weigh your own; the rod model is an upper estimate). In the rod model the energy is mostly in the outer half of the blade, and that is the part that hits your hand. The scale of injuries is a course guideline, not statistics: 5" — deep cuts, 7–10" — broken fingers, 15" on an X8 — severe injuries. Energy grows with the square of RPM, so a 5" at full throttle (26 J) is more dangerous than a 10" in hover (19 J).
- **Motors on the bench.** A motor test in the configurator without removing the props is a classic injury. The firmware warns you, but it won't stop you.
- **LiPo.** Internal resistance of 1–3 mΩ per cell: a fresh 6S has about 12 mΩ per pack (`f-power`), and by Ohm's law a short circuit at 25.2 V gives up to 25.2 / 0.012 ≈ 2100 A; the wires and connector add only a few mΩ, so the current stays on the order of a thousand amps (course estimate) — a wire glows red-hot within a second. A cell punctured in a crash can catch fire minutes or hours after the impact. The burning is thermal runaway with oxygen released from the cathode: knock down the flame (an ABC extinguisher, sand), then **cool it with a large amount of water**, or carry it outdoors in a non-flammable container and let it burn out. A class D extinguisher is designed for metallic lithium — there is none in LiPo or Li-Ion. A swollen pack is retired: discharge it to 0 through a load (a resistor or a bulb, not salt water — the procedure is in `f-power`) and hand it in for disposal.
- **Loss of link.** If the failsafe has not been tested on this aircraft, it does something nobody chose (the “Failsafe” module).
- **The first flight after any change** — a swapped motor, the prop direction, a wrong mixer, an untested filter: the most dangerous flight (course guideline: it reveals all the errors that are not visible on the bench).

### Why LiPo burns: thermal runaway step by step
A LiPo or Li-Ion cell is a graphite anode, an oxide cathode (in drone LiPos usually based on cobalt and nickel), a polymer separator tens of microns thick between them, and an organic electrolyte. The electrolyte is a mixture of carbonates: an EC/DMC mixture has a flash point of about 25 °C, i.e. there is always fuel inside the cell. The danger is not a “spark” but a chain of reactions, each of which heats the cell and starts the next one. The steps according to the review by Liu et al. (Science Advances, 2018):

1. **At about 80 °C** the rate of exothermic side reactions grows so much that the cell starts heating itself. Thermal runaway is defined as self-heating faster than 10 °C per minute.
2. **From ~90 °C** the protective film on the anode (SEI) decomposes, releasing flammable gases (in an accident this is what swells the cell; ordinary “puffing over time” is gas from aging and over-discharge at normal temperature). Then the lithium in the anode reacts with the electrolyte solvent.
3. **At ~135 °C** a polyethylene separator melts, **at ~165 °C** — a polypropylene one. The anode and cathode touch, an internal short circuit begins, and the cell's entire energy is released inside it.
4. **At 180–250 °C** (the review gives both figures for LiCoO2) the cathode decomposes and releases oxygen. Now the electrolyte no longer needs air to burn: smothering the flame does not mean putting it out.

Three practical conclusions follow from the mechanism. First: you fight the temperature, not the flame. An ABC extinguisher or sand knock down the open burning, but as long as the cells are hotter than ~80 °C the reactions continue, so next comes a lot of water for cooling, or a non-flammable container outdoors and letting it burn out. Second: mechanical damage starts the same chain from step 3 — a crushed separator gives an internal short circuit without any overheating, which is why a pack can catch fire minutes after an impact (hence the post-crash quarantine in `ops-maintenance`). Third: the charging “window”, 10–45 °C per the Gens Ace datasheet (`f-power`), is only 35 °C away from the onset of self-heating. A pack is sometimes hot to the touch after an aggressive flight; charging it without letting it cool into the window means cutting into an already small 35 °C margin.

{{diagram:safety-thermal-ladder|The 10–45 °C charging window and the runaway steps on one scale: from the top of the window to self-heating is only 35 °C, and from 180 °C the cathode supplies its own oxygen.}}

### Charging, storage, transport: the course's numbers
The numbers below are already adopted in the course (an audit of the selection rules; the canonical values live in `f-power` and `ops-maintenance`); here they are collected in one table as safety rules. Where a number is a course guideline rather than a datasheet value, this is stated.

| What | Number | Source |
|---|---|---|
| Charge current | 1C for LiPo, 0.5–1C for Li-Ion (Gens Ace allows up to 2C but recommends 0.5–1C for service life) | Gens Ace datasheet, `f-power` |
| End of charge | 4.20 V/cell (Gens Ace's limit is 4.22 V); LiHV — 4.35 V/cell, only where permitted | Tattu, Gens Ace, `f-power` |
| Pack temperature when charging | 10–45 °C | Gens Ace datasheet, `f-power` |
| Storage | LiPo 3.80–3.90 V/cell (Storage mode), Li-Ion 3.6–3.7 V/cell | Gens Ace, Team Associated, `f-power` |
| Full charge without flying | no longer than a day | course guideline (`f-power`, `ops-maintenance`) |
| Cell spread | ≤ 0.02 V after charging, ≤ 0.05 V after a flight; from 0.03 V after charging and resting — watch it, more than 0.05 V — retire it | course guideline (`f-power`, `ops-maintenance`) |
| Lower limit under load | 3.0 V/cell (LiPo); land on the alarm at 3.5 V, critical 3.3 V on 4–6S | Tattu, Gens Ace, Betaflight defaults, `f-power` |
| Quarantine after an impact | on a non-flammable surface, outdoors or in a fireproof box, for at least 15 min (Team Associated: a damaged battery can catch fire even after 10 min) | `ops-maintenance`, `f-power` |
| Transport as a passenger | spare batteries — carry-on baggage only, terminals insulated; ≤ 100 Wh — up to 20 without approval; 100–160 Wh — no more than 2 per device, with the airline's approval; > 160 Wh — not allowed, cargo only | IATA, Guidance for Passengers Travelling with Lithium Batteries 2026 |

The energy for transport is calculated from the nominal values: Wh = Ah × nominal voltage (as in the IATA document). The nominal cell voltage is 3.7 V for LiPo and 3.6 V for the Molicel P42A (in the calculation in the practice). A 6S 1300 mAh — 6 × 3.7 × 1.3 = 28.9 Wh, freely in carry-on baggage; a 6S2P of P42A (8.4 Ah) — 181 Wh, cannot be carried by a passenger at all: such a pack is shipped as cargo. IATA notes that airlines prefer a charge below 25 % and may impose stricter conditions, so read your own airline's rules separately before a trip. Storage mode (3.8 V/cell) is roughly half charge, i.e. more than 25 %: Storage is the minimum preparation, and if the airline requires less than 25 %, discharge the pack further (course guideline).

{{lesson:f-power|Per-cell thresholds, calculating the charging current and power, parallel charging and disposal — every number with a source.}}

### A bench without props: the power-up order
Prop injuries on the bench usually happen in the same way (course guideline): “I only plugged the battery in for a second”. So on the bench you follow an order in which the props come last, and every step checks what could kill the next one.

1. **A multimeter before power.** The resistance between “+” and “−” of the power input is not close to zero, there are no solder bridges — a short on the input with a LiPo burns the board and the wire (`el-measure`).
2. **The first power-up through a smoke stopper** or a bench power supply with current limiting: in a short circuit the fuse or the bulb burns, not the ESC.
3. **USB and the configurator.** In Betaflight a connected configurator sets the `MSP` flag, and arming is impossible. In ArduPilot and PX4 there is no such block by default (in PX4 the USB check is enabled by `CBRK_USB_CHK = 0`; the default is 197848 — disabled): a GCS can arm the aircraft over MAVLink with a button or a script, so the “no props” rule is stricter here, not looser.
4. **Motor test** — without props, at low throttle: the motor number per the frame diagram, the spin direction, an even sound.
5. **Arming with the switch without props.** Make sure that after arming the motors spin at idle (the table below): it is exactly this spinning that cuts fingers at “zero” throttle.
6. **A failsafe test without props** — switch off the radio and make sure the aircraft does what you chose (practice, “Moving to real hardware”).
7. **Props — at the flying site**, as the last action before the first hover, in an area where nobody is around.

If thrust is needed on the bench (a thrust stand, `des-thrust-stand`), the motor or aircraft is rigidly fixed, the person stands outside the plane of rotation, and arming is done remotely or with a switch at a distance, not by hand next to the prop.

{{diagram:safety-bench-sequence|The bench order: steps 1–6 without props, props — the last step at the flying site; any step not passed stops the work.}}

### “Armed” means the props are spinning
Beginners often think that an armed aircraft with zero throttle is safe. This is wrong in all three firmwares: after arming the motors spin at idle, and a loss of link produces different reactions with different delays in different firmware. The table gives the defaults from the source code of the target versions.

| | Betaflight 2025.12 | ArduCopter 4.7.2 | PX4 1.17 |
|---|---|---|---|
| Motors after arming | `motor_idle` = 550 (5.5 %; in 4.5 — `dshot_idle_value`) — they spin unless `MOTOR_STOP` is enabled | `MOT_SPIN_ARM` = 0.1: in SITL PWM 1100 two seconds after arming | they spin up, spool-up time `COM_SPOOLUP_TIME` = 1 s |
| Auto-disarm on the ground | `auto_disarm_delay` = 5 s, but only with `MOTOR_STOP`, stick arming and no Airmode; with switch arming — only a beep | `DISARM_DELAY` = 10 s | `COM_DISARM_PRFLT` = 10 s without takeoff, `COM_DISARM_LAND` = 2 s after landing |
| When the RC loss is detected | `RXLOSS` after 150 ms (in 4.5 — 100 ms), Stage 2 after `failsafe_delay` = 15 (1.5 s) | after `RC_FS_TIMEOUT` = 1.0 s without frames, or when throttle is below `FS_THR_VALUE` = 975 µs | after `COM_RC_LOSS_T` = 0.5 s, the action — after `COM_FAIL_ACT_T` = 5 s |
| Default action | `failsafe_procedure` = DROP | `FS_THR_ENABLE` = 1: RTL in the air, disarm on the ground | `NAV_RCL_ACT` = 2: Return |

Three consequences. Idle RPM is already a dangerous blade-edge speed, so “arming on the bench to have a look” is acceptable without props, but not with them. Betaflight with switch arming does not disarm by itself: an armed aircraft will keep spinning its props until it is disarmed. In ArduPilot, after the link returns, the aircraft stays in RTL (in the practice this is visible in the SITL log), and you can take back control only by switching the mode — you need to know this before your first flight.

{{lesson:bf-failsafe|Betaflight's failsafe stages, choosing the procedure for the aircraft, and a test with a switch without turning off the radio in the air.}}

### How the firmware protects against arming (Betaflight 2025.12; 4.5 has no `FLIP_SWITCH`/`ALT_HOLD_SW`/`POS_HOLD_SW`, and `ARM_SWITCH` is called `ARMSWITCH`; `AUTOPILOT_SW` appeared in 2026.6 — released 17.09.2026, outside the course's base version)
Arming is impossible while at least one arming disable flag is active. Their list is in `src/main/fc/runtime_config.c`; they are visible via `status` in the CLI and in the OSD (the “Warnings” element):

{{diagram:arming-tree|The “won't arm” troubleshooting tree: first read the flag, then check the specific cause.}}

| Flag | What it means | What to do |
|---|---|---|
| `NOGYRO` | no gyro detected | check the board/target, do not fly |
| `FAILSAFE` / `BOXFAILSAFE` | failsafe is active (no RC) / the failsafe switch is on | restore the link, turn off the switch |
| `RXLOSS` | no receiver signal | bind, RX power, the port protocol |
| `NOT_DISARMED` | the link to the receiver appeared (or returned) while the ARM switch is already on | lower the ARM switch |
| `RUNAWAY` | the runaway takeoff protection triggered | disarm; check the motor/prop directions |
| `CRASH` | the crash detector | disarm/reboot |
| `THROTTLE` | throttle is not at minimum | throttle stick down, check `min_check` |
| `ANGLE` | tilted more than `small_angle` | level it, or `small_angle = 180` for Acro |
| `BOOTGRACE` | the time after power-up has not yet passed | wait |
| `NOPREARM` | PREARM is not enabled | enable PREARM |
| `LOAD` | processor overload | lower the main loop rate/disable features |
| `CALIB` | calibration in progress | wait |
| `CLI`, `CMS`, `MSP`, `BST` | the CLI / the OSD menu is open / the configurator is connected | close it — and that is how it should be |
| `PARALYZE` | the PARALYZE mode has been activated | reboot |
| `GPS` | GPS Rescue requires a fix, and there is none | wait for a fix or disable the requirement |
| `RESCUE_SW` | the GPS Rescue switch is on at arming | turn it off |
| `DSHOT_TELEM` | the RPM filter is enabled, but there is no eRPM from the ESC | `dshot_bidir`, ESC firmware, wires |
| `REBOOT_REQD` | a reboot is required after configuration | reboot |
| `DSHOT_BBANG` | a bitbang DShot error | check the resources/timers |
| `NO_ACC_CAL` | the accelerometer is not calibrated | calibrate |
| `MOTOR_PROTO` | the motor protocol is not configured | select DShot |
| `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW` (2026.6 adds `AUTOPILOT_SW`) | a mode switch is on at arming; `FLIP_SWITCH` — turtle was turned off by the switch with `crashflip_auto_rearm = OFF` | turn the mode off; for `FLIP_SWITCH` — lower ARM |
| `ARM_SWITCH` | the ARM switch is on while any other block is in effect; in the OSD it is shown only if it is the only one (`status` in the CLI shows all of them) | lower ARM, remove the other causes |

These flags are a safeguard, not a nuisance. The rule: fix the cause, don't disable the check. **ArduPilot**: `ARMING_SKIPCHK` (4.7+, a bitmask of the **skipped** checks; before 4.7 — `ARMING_CHECK`, a bitmask of the enabled ones: baro, compass, GPS, INS, parameters, RC, voltage, geofence…), “PreArm: …” messages in the GCS — the same logic; skipping checks is acceptable only on the bench.

### Protective modes and devices
- **PREARM** — a second switch without which arming is impossible; mandatory on aircraft with 7"+ props (course guideline; the reason is the prop's energy in hover: 7" — about 10 J, 10" — 19 J versus 5.8 J for a 5", subsection “The hazard in numbers”, and the scale of injuries is there too — fractures, not cuts).
- **Failsafe** — what to do on loss of link; tested on the ground without props before the first flight of every new build.
- **Beeper** and **GPS in the OSD** — to find a crashed aircraft.
- **Runaway takeoff prevention** (Betaflight `runaway_takeoff_prevention = ON`) — a disarm if after arming the gyro shows growing rotation that does not respond to control (swapped motors/props).
- **A low-battery buzzer, a timer** — so you don't fly away on a depleted battery.

### The site and people
The radius of the safe zone around the takeoff point is at least 10–15 m for a 5", 30 m for a 7" and larger and for an X8 (course guideline; the boundary is the same as for PREARM: from 7" the prop's energy in hover is 10 J and above, “The hazard in numbers”); nobody stands in the plane of the props at arming; take off away from yourself. Regulations and zones — the “Regulations” module, team organization — “Field operations”.

The procedure at the site relies on voice and order, not on memory. Before arming, the pilot asks “Aircraft 1, arm?” and arms only after the reply “Clear to arm” — these are the team's radio exchange phrases from `ops-field`; without an observer, the pilot inspects the 360° zone themselves before arming. Batteries in the field lie in a fireproof box or bag, in the shade: in the sun a dark pack heats up, and a hot pack is not charged until it is back in the 10–45 °C window. Charging in the field is done only under supervision, on a non-flammable surface, never in a car with nobody in it. After a crash the order is: disarm with the switch (if the aircraft hasn't disarmed by itself), approach only after making sure the motors have stopped, disconnect the battery first, inspect the pack and send it into quarantine on a non-flammable surface for at least 15 minutes (`ops-maintenance`); a damaged pack is not charged and not put into another aircraft. The radio is switched off last: with the radio off and the battery connected, it is the failsafe that decides, not the pilot.

### Place in the system

- **Receives:** the arming disable flags and PreArm messages from the firmware (`bf-arming-safety`, `ap-safety-fs`); the configured failsafe (`bf-failsafe`); the state of the battery after charging and after an impact (`f-power`).
- **Provides:** the “props off” rule — to all bench work (`diag-troubleshooting`, `el-measure`); the pre-flight and post-flight checklists — to the sortie protocols (`ops-field`); the S-xx group of requirements — to the engineering folder (`eng-method-101`).
- **If you get it wrong here:** the arming check was disabled instead of fixing the cause → the first flight with a swapped motor or prop ends with a flip (tree 2 in `diag-troubleshooting`). The failsafe was not tested on the ground → on loss of link the aircraft does something nobody chose; the Airspeeder case (`ops-case-studies`): the controller held the last throttle, the kill switch did not work; the setup — `bf-failsafe`.

## practice
### Pre-flight checklist (print it)
1. Props: intact, tightened, direction per the motor diagram, no foreign objects in the prop plane.
2. Battery: no swelling or damage, per-cell voltage normal (4.1–4.2 V/cell when full, a guideline), secured with a strap, the XT connector not melted.
3. RC and VTX antennas: in place, intact, not in the prop plane; the VTX with its antenna on (without it the VTX can burn out — a guideline).
4. Radio: the correct model, charged, the ARM/PREARM switches off, a failsafe test done on this aircraft.
5. Video/OSD: voltage, LQ/RSSI (LQ — the share of control packets that arrived, %, normal near home — 100; RSSI — the signal level, dBm; in detail — `link-protocols`, `link-elrs`), warnings — no flags.
6. Zone: people and animals outside the radius, take off away from yourself, obstacles accounted for, the site's rules.
7. After arming: 2–3 s of hover at 0.5–1 m — the response, the sound, no jitter; at any oddity — land.

{{diagram:preflight-go-nogo|The pre-flight checklist as a “yes/no” chain: any item not passed stops the sortie, and an oddity in the first hover ends with a landing.}}

### Bench rules
1. Props are removed before connecting the battery. Always. Including “for a second”.
2. The first power-up of a new/resoldered build — through a smoke stopper, with a multimeter check before that (the “Electricity 101” module).
3. Motor test — only without props, with limited throttle, with your hand next to the battery connector.
4. Configurator connected → the `MSP` flag → arming impossible. Do not bypass it.
5. Charging LiPo — in a fireproof bag/box, under supervision, with a balance charge, not on a flammable surface; storage at 3.8 V/cell.

### In a battery fire
1. Do not touch it with your hands, do not blow on it. Step back, let people step back (the smoke is toxic).
2. Sand/earth on top, or drag it with a metal object onto a non-flammable surface.
3. An extinguisher — to knock down the flame, then cool it (the burning can resume).
4. Afterwards — do not leave it unattended for an hour (course guideline); the remains go into a metal container.

### After the flight
1. Disarm, switch off the radio last (not first!), disconnect the battery.
2. Motor and ESC temperature by hand; inspection of the props and frame.
3. An entry in the aircraft logbook: what you changed, how it flew, what you noticed; the log — if it was a test flight.

### Lab 1 (done in SITL): what “armed” means and what an RC loss does
No hardware needed: ArduCopter 4.7.2 SITL and `pymavlink`. The script arms the aircraft on the ground in STABILIZE with the throttle at 1000 µs and reads the motor PWM, then “switches off the receiver” (`SIM_RC_FAIL = 1`, frames stop arriving) — first on the ground, then in GUIDED at 10 m — and prints the mode change with timestamps. Launch: `arducopter -S --model + -I 6 -w --defaults Tools/autotest/default_params/copter.parm --home -35.363261,149.165230,584,353`, in another terminal — `python3 fs_bench.py tcp:127.0.0.1:5820` (port 5760 + 10 × the instance number).

```python
"""f-safety lab: ArduCopter 4.7.2 SITL — what 'armed' means on the bench, and what an RC loss does
(1) on the ground, armed;  (2) in the air at 10 m in GUIDED.  RC loss = SIM_RC_FAIL=1 (no pulses)."""
import sys, time
from pymavlink import mavutil
m = mavutil.mavlink_connection(sys.argv[1]); m.wait_heartbeat()
t0 = time.time()
def T(): return f"t={time.time()-t0:6.1f}s"
def setp(n, v):
    m.mav.param_set_send(m.target_system, m.target_component, n.encode(), v, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    time.sleep(0.3)
def mode(name):
    m.set_mode(m.mode_mapping()[name])
def flush():
    while m.recv_match(blocking=False) is not None: pass
def armed():
    flush()
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    return bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED), mavutil.mode_string_v10(hb)
def pwm():
    flush()
    s = m.recv_match(type='SERVO_OUTPUT_RAW', blocking=True, timeout=3)
    return [s.servo1_raw, s.servo2_raw, s.servo3_raw, s.servo4_raw]
def drain(sec, tag=""):
    end = time.time() + sec; last = None
    while time.time() < end:
        msg = m.recv_match(type=['STATUSTEXT', 'HEARTBEAT'], blocking=True, timeout=0.5)
        if msg is None: continue
        if msg.get_type() == 'STATUSTEXT':
            print(f"{T()} {tag} STATUSTEXT: {msg.text}")
        else:
            st = (bool(msg.base_mode & 128), mavutil.mode_string_v10(msg))
            if st != last: print(f"{T()} {tag} armed={st[0]} mode={st[1]}"); last = st
m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
for n in ("MOT_SPIN_ARM", "MOT_SPIN_MIN", "FS_THR_ENABLE", "FS_THR_VALUE", "RC_FS_TIMEOUT", "DISARM_DELAY"):
    flush(); m.mav.param_request_read_send(m.target_system, m.target_component, n.encode(), -1)
    while True:
        p = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
        if p.param_id == n: break
    print(f"param {p.param_id} = {p.param_value:g}")
# wait until arming is possible (EKF + GPS) — try every 2 s
mode('STABILIZE')
for i in range(40):
    m.arducopter_arm(); time.sleep(1.5)
    if armed()[0]: break
flush(); print(f"{T()} (1) armed on the ground in STABILIZE, throttle stick 1000 us: motors PWM = {pwm()}")
time.sleep(2); print(f"{T()}     2 s later, still no throttle:                motors PWM = {pwm()}")
flush(); setp("SIM_RC_FAIL", 1); print(f"{T()}     SIM_RC_FAIL=1 (receiver silent)")
drain(4, "   ")
setp("SIM_RC_FAIL", 0); time.sleep(2)
# (2) in the air
mode('GUIDED')
for i in range(10):
    m.arducopter_arm(); time.sleep(1.5)
    if armed()[0]: break
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
while True:
    p = m.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    if p.relative_alt > 9500: break
print(f"{T()} (2) GUIDED, 10 m reached; now SIM_RC_FAIL=1")
flush(); tf = time.time(); setp("SIM_RC_FAIL", 1)
end = time.time() + 6; last = None
while time.time() < end:
    msg = m.recv_match(type=['STATUSTEXT', 'HEARTBEAT'], blocking=True, timeout=0.5)
    if msg is None: continue
    dt = time.time() - tf
    if msg.get_type() == 'STATUSTEXT': print(f"    +{dt:4.2f}s STATUSTEXT: {msg.text}")
    else:
        md = mavutil.mode_string_v10(msg)
        if md != last: print(f"    +{dt:4.2f}s mode={md}"); last = md
setp("SIM_RC_FAIL", 0); print(f"{T()} RC restored (SIM_RC_FAIL=0)"); drain(3, "   ")
```

Output of a run in the author's environment (ArduCopter 4.7.2 SITL, pymavlink 2.4.50):

```text
param MOT_SPIN_ARM = 0.1
param MOT_SPIN_MIN = 0.15
param FS_THR_ENABLE = 1
param FS_THR_VALUE = 975
param RC_FS_TIMEOUT = 1
param DISARM_DELAY = 10
t=  25.0s (1) armed on the ground in STABILIZE, throttle stick 1000 us: motors PWM = [1026, 1026, 1026, 1026]
t=  27.1s     2 s later, still no throttle:                motors PWM = [1100, 1100, 1100, 1100]
t=  27.5s     SIM_RC_FAIL=1 (receiver silent)
t=  28.0s     armed=True mode=STABILIZE
t=  28.2s     STATUSTEXT: Radio Failsafe - Disarming
t=  28.2s     STATUSTEXT: Disarming motors
t=  29.0s     armed=False mode=STABILIZE
t=  29.4s     STATUSTEXT: PreArm: Radio failsafe on
t=  50.8s (2) GUIDED, 10 m reached; now SIM_RC_FAIL=1
    +0.30s mode=GUIDED
    +0.99s mode=RTL
    +0.99s STATUSTEXT: Radio Failsafe
t=  57.9s RC restored (SIM_RC_FAIL=0)
t=  57.9s     STATUSTEXT: Radio Failsafe Cleared
t=  58.0s     armed=True mode=RTL
```

What this shows. A second after arming the PWM is ≈ 1020–1030 (depending on when during spool-up it is read; in this run 1026), after two seconds — 1100: the motors have spun up to `MOT_SPIN_ARM` = 0.1 with the throttle stick at zero — with props on, that is already cutting rotation. An RC loss on the ground produced “Radio Failsafe - Disarming” after about 1 s (`RC_FS_TIMEOUT`), and until the link returns arming is blocked (“PreArm: Radio failsafe on”). In the air RTL engaged after 0.99 s, and after the link returned (“Radio Failsafe Cleared”) the aircraft stayed in RTL: control comes back only by switching the mode.

### Lab 2 (done): battery energy, transport, charging, prop energy
The numbers in the theory were calculated with this script (Python 3, no libraries): Wh and the IATA category, the 1C current and the charging power, the prop's energy in the rod model, the temperature gate before charging.

```python
import math
# 1) Energy of a pack and the IATA passenger category (Wh = Ah x V nominal; LiPo/Li-Ion 3.6-3.7 V per cell)
def wh(s, mah, v_cell): return s * v_cell * mah / 1000
def iata(e): return "<=100 Wh: carry-on, no approval needed" if e <= 100 else (
    "100-160 Wh: carry-on, with approval, no more than 2" if e <= 160 else ">160 Wh: not allowed for passengers, cargo only")
packs = [("6S 1300 LiPo", 6, 1300, 3.7), ("6S 2200 LiPo", 6, 2200, 3.7), ("4S 5200 LiPo", 4, 5200, 3.7),
         ("6S2P P42A Li-Ion", 6, 8400, 3.6), ("6S4P P42A Li-Ion", 6, 16800, 3.6)]
for name, s, mah, v in packs:
    e = wh(s, mah, v); print(f"{name:18s} {e:6.1f} Wh  {iata(e)}")
# 2) Charging: current at 1C (course rule) and charger power at 4.2 V/cell
for name, s, mah in [("6S 1300", 6, 1300), ("4S 5200", 4, 5200)]:
    i = mah / 1000; p = s * 4.2 * i
    print(f"{name}: 1C = {i:.1f} A, P = {s}x4.2x{i:.1f} = {p:.0f} W")
# 3) Kinetic energy of a spinning prop, thin-rod model I = m L^2 / 12 (L = diameter)
for d_in, m_g, rpm in [(5, 4, 14000), (5, 4, 30000), (7, 9, 9000), (10, 18, 6000)]:
    L = d_in * 0.0254; I = m_g / 1000 * L**2 / 12; w = rpm * 2 * math.pi / 60
    print(f'{d_in}" {m_g} g @ {rpm} rpm: tip {math.pi*L*rpm/60:5.0f} m/s, E = {0.5*I*w*w:5.1f} J')
# 4) Temperature gate before charging (Gens Ace 10-45 C, course rule)
for t in (5, 25, 52):
    print(f"pack {t} C:", "charge" if 10 <= t <= 45 else "do not charge: wait/warm up to 10-45 C")
```

```text
6S 1300 LiPo         28.9 Wh  <=100 Wh: carry-on, no approval needed
6S 2200 LiPo         48.8 Wh  <=100 Wh: carry-on, no approval needed
4S 5200 LiPo         77.0 Wh  <=100 Wh: carry-on, no approval needed
6S2P P42A Li-Ion    181.4 Wh  >160 Wh: not allowed for passengers, cargo only
6S4P P42A Li-Ion    362.9 Wh  >160 Wh: not allowed for passengers, cargo only
6S 1300: 1C = 1.3 A, P = 6x4.2x1.3 = 33 W
4S 5200: 1C = 5.2 A, P = 4x4.2x5.2 = 87 W
5" 4 g @ 14000 rpm: tip    93 m/s, E =   5.8 J
5" 4 g @ 30000 rpm: tip   199 m/s, E =  26.5 J
7" 9 g @ 9000 rpm: tip    84 m/s, E =  10.5 J
10" 18 g @ 6000 rpm: tip    80 m/s, E =  19.1 J
pack 5 C: do not charge: wait/warm up to 10-45 C
pack 25 C: charge
pack 52 C: do not charge: wait/warm up to 10-45 C
```

### Moving to real hardware: a failsafe test without props
This step was not performed in the author's environment (it needs your own aircraft); the order follows `bf-failsafe` and `ap-safety-fs`.
1. Props removed, the aircraft secured or lying on the bench, the battery charged, the firmware version and `diff all` / `.param` recorded in the logbook.
2. The radio on, arm with the switch. Betaflight: the motors at idle; ArduPilot: PWM ≈ `MOT_PWM_MIN` + 0.1 × range, as in lab 1.
3. Betaflight: raise the throttle to ~30 %, switch off the radio and time it with a stopwatch or from the log. ArduPilot: throttle at zero (as in lab 1), STABILIZE mode, switch off the radio. With the throttle raised, Copter assumes it has taken off: in STABILIZE/ACRO it disarms on RC loss only at zero throttle or after landing (`should_disarm_on_failsafe()` in `events.cpp`), otherwise it performs the `FS_THR_ENABLE` action (RTL or LAND) with the motors running — that scenario is tested only in SITL, as in lab 1.
4. **Acceptance criteria:** Betaflight with DROP — the motors stopped no later than ~1.5 s (`failsafe_delay` = 15) and the OSD shows `FAILSAFE`/`RXLOSS`; ArduPilot with zero throttle — a disarm after ~1 s and “Radio Failsafe - Disarming” in the messages; in Betaflight, after the radio is switched back on, re-arming is possible only after the ARM switch is returned to “off” (the `ARM_SWITCH` flag).
5. **Abort and disconnect the battery** if, while performing step 3 as written, the motors keep spinning for longer than 3 s after the radio is switched off, or the aircraft arms with the ARM switch raised. A common cause is the receiver holding the last values: over CRSF an ELRS receiver stops sending frames on loss of link, and the flight controller sees this; on PWM/SBUS outputs set “No Pulses”. If in ArduPilot the motors keep spinning with the throttle raised, that is not a failsafe failure but the RTL/LAND action: it means step 3 was performed incorrectly. Do not fly until the cause is found.
6. Write the test date, the reaction time and the action into the aircraft logbook.

### An exercise without hardware: flag, cause, action
No aircraft needed — only the flag table and the rules of this module. First close the flag table and answer from memory, then check.

**1. Twelve situations.** For each one, write down the arming disable flag that `status` or the OSD will show, and the correct action.

| # | Situation |
|---|---|
| 1 | the aircraft is connected over USB, the configurator is open |
| 2 | the battery was connected with the ARM switch raised |
| 3 | the aircraft stands on a slope, tilted more than `small_angle` |
| 4 | the radio is off, the receiver has no signal |
| 5 | the throttle stick is at 20 % |
| 6 | the RPM filter is enabled, no eRPM arrives from the ESC |
| 7 | the battery was connected a second ago |
| 8 | PREARM is assigned on a 7", the second switch is not on |
| 9 | after arming the aircraft jerked and disarmed by itself, re-arming fails |
| 10 | a setting was changed, the firmware is waiting for a reboot |
| 11 | the GPS Rescue switch is on |
| 12 | the failsafe test switch is on |

**2. Prop tip speed.** Using the formula from the section “The hazard in numbers” (tip speed = π · D · n, D in meters, n in revolutions per second; 5" = 0.127 m), calculate the speed in m/s and km/h: a 5" at 20,000 rpm (hover of a heavy aircraft) and a 7" at 12,000 rpm.

**3. True or false.** (a) For a burning LiPo the best choice is a class D extinguisher. (b) A swollen pack is discharged in salt water. (c) After the flight the radio is switched off first. (d) A motor test with props on is acceptable at low throttle. (e) With the `ANGLE` flag, for flying in Acro you can set `small_angle = 180`. (f) If arming fails because of a flag, the check is disabled in the settings. (g) After a battery fire has been put out, it may be left unattended no sooner than an hour later.

Self-check: the lab is done when:
- the flags by row: 1 — `MSP`; 2 — `NOT_DISARMED` (alongside it `status` shows `ARM_SWITCH`; in the OSD first `RXLOSS`/`BOOTGRACE`, then `NOT_DISARMED`); 3 — `ANGLE`; 4 — `RXLOSS`; 5 — `THROTTLE`; 6 — `DSHOT_TELEM`; 7 — `BOOTGRACE`; 8 — `NOPREARM`; 9 — `RUNAWAY`; 10 — `REBOOT_REQD`; 11 — `RESCUE_SW`; 12 — `BOXFAILSAFE`; at least 10 of 12 correct from memory;
- speed: a 5" at 20,000 rpm — 133 m/s, 479 km/h; a 7" at 12,000 rpm — 112 m/s, 402 km/h (2 % tolerance);
- only (e) and (g) are true; the other five statements are false;
- **(SITL, lab 1)** you got: PWM 2 s after arming — 1100 ± 10 with throttle at 1000 µs; on the ground — “Radio Failsafe - Disarming” 1.0 ± 0.3 s after `SIM_RC_FAIL = 1`; in the air — RTL after 1.0 ± 0.3 s, and after “Radio Failsafe Cleared” the mode stays RTL;
- **(calculation, lab 2)** 6S 1300 — 28.9 Wh; 6S4P P42A — 363 Wh and the category “cargo only”; 4S 5200 at 1C — 5.2 A and 87 W (2 % tolerance);
- **(hardware)** the pre-flight checklist is printed; the logbook has the date of the failsafe test without props, and the motors stopped (Betaflight DROP) or the aircraft disarmed (ArduPilot, throttle at zero) within the criteria of step 4 of “Moving to real hardware”.

**Reference for self-check.** Actions: 1 — close the configurator, do not bypass the flag; 2 — lower the ARM switch: `NOT_DISARMED` clears when there is a link and ARM is off; 3 — level the aircraft (or `small_angle = 180` for Acro); 4 — switch on the radio, check the bind, the receiver power and the port protocol (`FAILSAFE` may appear next to it); 5 — throttle stick down, check `min_check`; 6 — `dshot_bidir`, ESC firmware, wires; 7 — wait; 8 — enable PREARM; 9 — disarm and check the motor and prop directions with no props on the shafts; 10 — reboot; 11 and 12 — turn off the switch. The speed calculation: 0.127 × π = 0.399 m per revolution, 20,000 / 60 = 333 rev/s, the product is 133 m/s, multiplied by 3.6 — 479 km/h; for a 7" D = 7 × 0.0254 = 0.178 m. On item 3: there is no metallic lithium in LiPo — the flame is knocked down with an ABC extinguisher or sand and cooled with water; a swollen pack is discharged through a load; the radio is switched off last; the props are removed before connecting the battery, “including for a second”; the cause of the flag is fixed, the check is not disabled. Common wrong answers: row 2 has only `ARM_SWITCH` — it appears in `status`, but in the OSD it is hidden while other flags exist, and the situation “the link appeared with ARM raised” itself is indicated by `NOT_DISARMED`; `THROTTLE` was written — the situation doesn't mention throttle; row 12 has `FAILSAFE` — that is the RC loss flag, while the switch gives `BOXFAILSAFE`; the speed came out as 7980 m/s — revolutions per minute were not converted to revolutions per second; for the 7" D = 0.127 m was used — that is the diameter of a 5". On the labs: if the PWM after arming is 1000 — you read an old message from the buffer, or the aircraft has already disarmed on `DISARM_DELAY` (10 s without throttle); if the failsafe doesn't trigger in SITL — `FS_THR_ENABLE` = 0 in the parameters; if you got 6S 1300 = 32.8 Wh — 4.2 V was used instead of the nominal 3.7 V; if 6S4P is “allowed in carry-on” — the factor of 4 was forgotten (16.8 Ah).

## diagnostics
- **Symptom:** the drone won't arm
  - Possible cause: an arming disable flag is active.
  - What to do: `status` in the CLI or the OSD Warnings; the table above; fix the cause.
- **Symptom:** the drone armed right after the battery was connected
  - Possible cause: arming is assigned to the wrong channel or range; or the link already existed before the battery was connected (the receiver was powered from USB), and `NOT_DISARMED` was not set — it is set only at the moment the link appears with ARM raised (a conclusion from the code of `fc/core.c`).
  - What to do: check Modes, the ARM channel range, add PREARM.
- **Symptom:** after arming the aircraft jerked sideways and disarmed
  - Possible cause: runaway takeoff — swapped motors/prop directions.
  - What to do: a motor test without props, the direction diagram, `resource`/`motor` remap.
- **Symptom:** after a crash the battery heats up without a load
  - Possible cause: an internal short.
  - What to do: isolate it on a non-flammable surface outdoors, watch it, do not charge it, dispose of it.
- **Symptom:** the link has returned, but the ArduPilot aircraft doesn't respond to the sticks and flies home
  - Possible cause: this is normal — after a radio failsafe Copter stays in RTL (visible in lab 1).
  - What to do: flip the mode switch to exit RTL; practice this in SITL before your first flight.
- **Symptom:** a Betaflight aircraft armed on the bench does not disarm by itself
  - Possible cause: `auto_disarm_delay` works only with `MOTOR_STOP`, stick arming and no Airmode; with switch arming Betaflight only beeps, while the motors spin at `motor_idle`.
  - What to do: disarm with the switch; on the bench — only without props.
- **Symptom:** the pack is hot after a flight, the charger won't start charging or complains about the temperature
  - Possible cause: the pack is outside the 10–45 °C window (Gens Ace datasheet), the charger's temperature sensor tripped.
  - What to do: let it cool in the shade on a non-flammable surface; do not cool it with water or put it in a fridge (condensation).
- **Symptom:** the VTX is hot, no video
  - Possible cause: it was powered without an antenna.
  - What to do: always attach the antenna before power; the VTX may already be damaged.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight source — fc/runtime_config.c (armingDisableFlagNames) | https://github.com/betaflight/betaflight/blob/master/src/main/fc/runtime_config.c | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Safety — ArduPilot Copter (multicopter safety practices) | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A
- ArduCopter 4.7.2 source — Parameters.cpp (FS_THR_ENABLE, FS_THR_VALUE, DISARM_DELAY), RC_Channels_VarInfo.h (RC_FS_TIMEOUT), AP_MotorsMulticopter.cpp (MOT_SPIN_ARM) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/Parameters.cpp | primary | A
- Betaflight 2025.12 source — flight/failsafe.c (failsafe defaults), pg/motor.c (motor_idle), fc/rc_controls.c (auto_disarm_delay) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/flight/failsafe.c | primary | A
- PX4 1.17 source — commander_params.c (COM_RC_LOSS_T, COM_FAIL_ACT_T, NAV_RCL_ACT, COM_DISARM_PRFLT, COM_SPOOLUP_TIME) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/commander/commander_params.c | primary | A
- Liu K., Liu Y., Lin D., Pei A., Cui Y. Materials for lithium-ion battery safety. Science Advances 4(6), eaas9820, 2018 (the stages of thermal runaway) | https://pmc.ncbi.nlm.nih.gov/articles/PMC6014713 | primary | A
- IATA — Guidance Document for Passengers Travelling with Lithium Batteries, 2026 (100/160 Wh, Wh = Ah × V; accessed 2026-11-25) | https://www.iata.org/contentassets/6fea26dd84d24b26a7a1fd5788561d6e/passengers_travelling_with_lithium_batteries.pdf | primary | A

## checklist
- No props on the bench — no exceptions
- I know all the arming disable flags and what to do with each one
- The pre-flight checklist is printed and used
- The failsafe has been tested on this drone without props, the reaction time is recorded
- I know that after arming the motors spin at idle, and how my firmware reacts to an RC loss
- I don't charge a hot pack until it is back within 10–45 °C; on a trip I take only packs up to 100 Wh (or get approval for 100–160)
- I know what to do in a LiPo fire and where the sand is
- After a flight I make an entry in the aircraft logbook
