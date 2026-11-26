---
id: f-safety
title: "Safety and the Pre-Flight Check"
level: L1
readingTime: 25 min
firmware: any firmware
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
source_hash: c3dbe1ced49d
---

## summary
The tip of a 5-inch prop moves at about 300 km/h and carries enough energy to cut skin down to the bone; a shorted LiPo dumps hundreds of amps and burns with its own oxidizer: you can knock the flame down, but the burning restarts until the cells cool off. Most injuries in the hobby happen not in the air but on the bench: the drone armed with props on during setup. This module gives you the physics of the danger in numbers, the rules that are not up for discussion, the full list of Betaflight arming disable flags (from the source code, with explanations) and the ArduPilot equivalent, pre-flight and post-flight checklists, and what to do in a battery fire.

## theory
### Danger in numbers
- **Propeller.** Tip speed = π · D · n. For a 5" (D = 0.127 m) in hover at 14,000 rpm (233 rev/s): 0.40 m × 233 ≈ 93 m/s — about 335 km/h; unloaded, up to 30,000 rpm — 200 m/s. The kinetic energy of a spinning 5" prop (~4 g) is a few joules: enough for deep cuts; 7–10" — tens of joules, broken fingers; 15" on an X8 — injuries that end your hobby.
- **Motors on the bench.** A motor test in the configurator without removing the props is a classic injury. The firmware warns you but won't stop you.
- **LiPo.** Internal resistance is 1–3 mΩ per cell: a short circuit of a 6S pack means hundreds of amps, and the wire glows hot within a second. A cell punctured in a crash can catch fire minutes or hours after the impact. The burning is thermal runaway with oxygen released from the cathode: knock the flame down (ABC extinguisher, sand), then **cool with plenty of water**, or carry it outside in a non-flammable container and let it burn out. A class D extinguisher is designed for metallic lithium — LiPo and Li-Ion don't contain any. A puffed pack is retired: discharge it to 0 in salt water (several days) and dispose of it.
- **Link loss.** If failsafe hasn't been tested on this aircraft, it will do something nobody chose (module “Failsafe”).
- **The first flight after any change** — a swapped motor, prop direction, wrong mixer, untested filter: statistically the most dangerous flight.


{{diagram:safety-thermal-ladder|Окно заряда 10–45 °C и ступени разгона на одной шкале: от верха окна до саморазогрева всего 35 °C, а с 180 °C катод сам даёт кислород.}}

{{diagram:safety-bench-sequence|Порядок стенда: шаги 1–6 без пропов, пропы — последним шагом на площадке; любой непройденный шаг останавливает работу.}}

### How the firmware protects against arming (Betaflight master; 2025.12 has no `AUTOPILOT_SW`, 4.5 has no `FLIP_SWITCH`/`ALT_HOLD_SW`/`POS_HOLD_SW`/`AUTOPILOT_SW`, and `ARM_SWITCH` is called `ARMSWITCH`)
Arming is impossible while at least one disable flag is active. The list lives in `src/main/fc/runtime_config.c`; the flags are shown by `status` in the CLI and in the OSD (the “Warnings” element):

{{diagram:arming-tree|“Won't arm” troubleshooting tree: read the flag first, then check the specific cause.}}

| Flag | What it means | What to do |
|---|---|---|
| `NOGYRO` | gyro not detected | check the board/target, don't fly |
| `FAILSAFE` / `BOXFAILSAFE` | failsafe active (no RC) / failsafe switch on | restore the link, turn the switch off |
| `RXLOSS` | no receiver signal | bind, RX power, port protocol |
| `NOT_DISARMED` | not disarmed after… | disarm with the switch |
| `RUNAWAY` | runaway takeoff protection triggered | disarm; check motor/prop direction |
| `CRASH` | crash detector | disarm/reboot |
| `THROTTLE` | throttle not at minimum | throttle stick down, check `min_check` |
| `ANGLE` | tilt greater than `small_angle` | level it, or `small_angle = 180` for Acro |
| `BOOTGRACE` | not enough time since power-on | wait |
| `NOPREARM` | PREARM not enabled | enable PREARM |
| `LOAD` | CPU overload | lower the loop rate/disable features |
| `CALIB` | calibration in progress | wait |
| `CLI`, `CMS`, `MSP`, `BST` | CLI / OSD menu open / configurator connected | close it — and that's how it should be |
| `PARALYZE` | PARALYZE mode activated | reboot |
| `GPS` | GPS Rescue requires a fix, there isn't one | wait for a fix or disable the requirement |
| `RESCUE_SW` | GPS Rescue switch on at arming | turn it off |
| `DSHOT_TELEM` | RPM filter enabled, but no eRPM from the ESC | `dshot_bidir`, ESC firmware, wires |
| `REBOOT_REQD` | reboot required after setup | reboot |
| `DSHOT_BBANG` | bitbang DShot error | check resources/timers |
| `NO_ACC_CAL` | accelerometer not calibrated | calibrate |
| `MOTOR_PROTO` | motor protocol not configured | select DShot |
| `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`, `AUTOPILOT_SW` | mode switch on at arming | turn it off |
| `ARM_SWITCH` | ARM switch was on when connected | turn it off and on again |

These flags are a safety net, not a nuisance. The rule: fix the cause, don't disable the check. **ArduPilot**: `ARMING_SKIPCHK` (4.7+, a bitmask of **skipped** checks; before 4.7 — `ARMING_CHECK`, a bitmask of enabled ones: baro, compass, GPS, INS, parameters, RC, voltage, geofence…), and “PreArm: …” messages in the GCS follow the same logic; skipping checks is acceptable only on a test stand.

### Modes and devices for protection
- **PREARM** — a second switch without which arming is impossible; mandatory on aircraft with 7"+ props.
- **Failsafe** — what to do on link loss; tested on the ground without props before the first flight of every new build.
- **Beeper** and **GPS in the OSD** — to find a crashed aircraft.
- **Runaway takeoff prevention** (Betaflight `runaway_takeoff_prevention = ON`) — disarms if, after arming, the gyro shows growing rotation that doesn't respond to control inputs (swapped motors/props).
- **Low-battery buzzer, timer** — so you don't keep flying on a depleted battery.

### Site and people
The safe zone radius around takeoff is at least 10–15 m for a 5", 30 m for heavy aircraft; nobody stands in the plane of the props during arming; take off away from yourself. Rules and zones — module “Rules”, team organization — “Field Operations”.

## practice

### Pre-flight checklist (print it)
1. Props: intact, tightened, direction matches the motor diagram, no foreign objects in the prop plane.
2. Battery: no puffing or damage, per-cell voltage normal (4.1–4.2 V/cell when full), secured with a strap, XT connector not melted.
3. RC and VTX antennas: in place, intact, not in the prop plane; VTX with antenna attached (without one it will burn out).
4. Radio: correct model, charged, ARM/PREARM switches off, failsafe test done on this aircraft.
5. Video/OSD: voltage, LQ/RSSI, warnings — no flags.
6. Zone: people and animals outside the radius, takeoff away from yourself, obstacles accounted for, site rules.
7. After arming: 2–3 s of hover at 0.5–1 m — response, sound, no shaking; at the slightest oddity — land.

{{diagram:preflight-go-nogo|Предполётный чек-лист как цепочка «да/нет»: любой непройденный пункт останавливает вылет, а странность на первом висении заканчивается посадкой.}}

### Bench rules
1. Props off before you plug in the battery. Always. Including “just for a second”.
2. The first power-up of a new/resoldered build goes through a smoke stopper, with a multimeter check beforehand (module “Electricity 101”).
3. Motor test — only without props, with limited throttle, with your hand at the battery connector.
4. Configurator connected → `MSP` flag → arming impossible. Don't bypass it.
5. Charge LiPos in a fireproof bag/box, under supervision, in balance mode, not on a flammable surface; store at 3.8 V/cell.

### In a battery fire
1. Don't touch it with your hands, don't blow on it. Step back, get people to step back (the smoke is toxic).
2. Sand/earth on top, or drag it with a metal object onto a non-flammable surface.
3. Extinguisher — knock the flame down, then cool (the burning can restart).
4. Afterwards — don't leave it unattended for an hour; put the remains in a metal container.

### After the flight
1. Disarm, turn the radio off last (not first!), unplug the battery.
2. Feel the motor and ESC temperature by hand; inspect the props and frame.
3. Entry in the aircraft log: what you changed, how it flew, what you noticed; the log file — if it was a test flight.

### Лабораторные (SITL ArduCopter 4.7.2 и расчёт; текст — в русской версии)

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

```python
import math
# 1) Energy of a pack and the IATA passenger category (Wh = Ah x V nominal; LiPo/Li-Ion 3.6-3.7 V per cell)
def wh(s, mah, v_cell): return s * v_cell * mah / 1000
def iata(e): return "<=100 Wh: ручная кладь, без согласования" if e <= 100 else (
    "100-160 Wh: ручная кладь, согласование, не больше 2" if e <= 160 else ">160 Wh: пассажиру нельзя, только груз")
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
    print(f"pack {t} C:", "заряжать" if 10 <= t <= 45 else "не заряжать: ждать/греть до 10-45 C")
```

```text
6S 1300 LiPo         28.9 Wh  <=100 Wh: ручная кладь, без согласования
6S 2200 LiPo         48.8 Wh  <=100 Wh: ручная кладь, без согласования
4S 5200 LiPo         77.0 Wh  <=100 Wh: ручная кладь, без согласования
6S2P P42A Li-Ion    181.4 Wh  >160 Wh: пассажиру нельзя, только груз
6S4P P42A Li-Ion    362.9 Wh  >160 Wh: пассажиру нельзя, только груз
6S 1300: 1C = 1.3 A, P = 6x4.2x1.3 = 33 W
4S 5200: 1C = 5.2 A, P = 4x4.2x5.2 = 87 W
5" 4 g @ 14000 rpm: tip    93 m/s, E =   5.8 J
5" 4 g @ 30000 rpm: tip   199 m/s, E =  26.5 J
7" 9 g @ 9000 rpm: tip    84 m/s, E =  10.5 J
10" 18 g @ 6000 rpm: tip    80 m/s, E =  19.1 J
pack 5 C: не заряжать: ждать/греть до 10-45 C
pack 25 C: заряжать
pack 52 C: не заряжать: ждать/греть до 10-45 C
```

## diagnostics
- **Symptom:** the drone won't arm
  - Possible cause: an arming disable flag is active.
  - What to do: `status` in the CLI or OSD Warnings; the table above; fix the cause.
- **Symptom:** the drone armed right after the battery was plugged in
  - Possible cause: the ARM switch was on and the `ARM_SWITCH` protection was disabled/didn't trigger, or arming is assigned to the wrong channel.
  - What to do: check Modes, the ARM channel range, add PREARM.
- **Symptom:** after arming the aircraft lurched sideways and disarmed
  - Possible cause: runaway takeoff — swapped motors/prop direction.
  - What to do: motor test without props, direction diagram, `resource`/`motor` remap.
- **Symptom:** after a crash the battery heats up with no load
  - Possible cause: an internal short.
  - What to do: isolate it on a non-flammable surface outdoors, watch it, don't charge it, dispose of it.
- **Symptom:** the VTX is hot, no video
  - Possible cause: it was powered without an antenna.
  - What to do: always attach the antenna before power; the VTX may already be damaged.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight source — fc/runtime_config.c (armingDisableFlagNames) | https://github.com/betaflight/betaflight/blob/master/src/main/fc/runtime_config.c | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Safety — ArduPilot Copter (multicopter safety practices) | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A

## checklist
- No props on the bench — no exceptions
- I know all the arming disable flags and what to do with each
- The pre-flight checklist is printed and in use
- Failsafe tested on this drone without props
- I know what to do in a LiPo fire and where the sand is
- After every flight I make an entry in the aircraft log
