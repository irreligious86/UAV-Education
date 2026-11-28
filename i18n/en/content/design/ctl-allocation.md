---
id: ctl-allocation
title: "Mixer and control allocation: the matrix, saturation, PX4 Control Allocation, tilted motors"
level: L3
readingTime: 45 min
firmware: PX4 1.18 (parameters checked against v1.18.0; allocator code per v1.17.0, the same in 1.15, 1.16 and v1.18.0) · ArduCopter 4.7 (checked against 4.7.3) · Betaflight 2025.12 (checked against 2025.12.5)
status: published
tags:
  - mixer
  - control allocation
  - effectiveness matrix
  - airmode
  - motor failure
related:
  - px4-control
  - px4-architecture
  - ap-heavy
  - math-linalg-rot
  - ctl-theory
  - f-frame-mech
next:
  - ctl-sysid
source: content/design/ctl-allocation.md
source_hash: 10ce1e2fc6f0
---

## summary
The controller outputs three torques and a thrust, but there are 4, 6 or 8 motors, and they can sit anywhere. The translation is done by the mixer (in PX4, control allocation). You will build one in Python the same way PX4 does: an effectiveness matrix, a pseudo-inverse, normalization, sequential desaturation. Then you will run the awkward cases: a dead cat with an off-center CG, a maneuver at the limit, a hexacopter with a dead motor, tilted motors, and carry the result over to Betaflight (`mmix`), ArduPilot (`FRAME_CLASS` 15 + Lua) and PX4 (`CA_*`, the Actuators tab). Lab: your own frame in Python and PX4 SITL, a motor failure in SIH, and on hardware a motor test without props and a hover log.

## theory
### The effectiveness matrix B
Each motor i with a normalized command uᵢ ∈ [0, 1] produces a force and a torque. PX4 computes them with the formula from `ActuatorEffectivenessRotors.cpp` (the same in 1.15–1.18):

- thrust: **Fᵢ = CT · aᵢ**, where aᵢ is the unit rotor axis (`CA_ROTORn_AX/AY/AZ`, (0, 0, −1) by default, that is, up in FRD axes);
- torque: **Mᵢ = CT · (pᵢ × aᵢ) − CT · KM · aᵢ**, where pᵢ is the rotor position relative to the CG in meters (`CA_ROTORn_PX/PY/PZ`), and `KM` is the ratio of reaction torque to thrust: positive for a CCW rotor, negative for a CW one (defaults `CT` = 6.5, `KM` = 0.05).

The columns [Mx My Mz Fx Fy Fz]ᵀ form a 6×N matrix B; you need to find u such that B·u equals the requested torques and thrust. On a copter with vertical motors the Fx and Fy rows are zero, leaving four independent axes.

### The pseudo-inverse and normalization
With N > 4 there are infinitely many solutions. PX4 takes the pseudo-inverse M = pinv(B), that is the minimum-norm solution u, and normalizes the columns (`ControlAllocationPseudoInverse.cpp`): roll and pitch get a common scale, yaw is scaled to a maximum of 1, and thrust to the average over the motors. That way `MC_*RATE_K` mean the same thing on any frame, but if the geometry changes the physical effectiveness of an axis, the loop gain changes too (step 5).

Betaflight and ArduPilot take ready-made roll/pitch/yaw/throttle factors per motor (ArduPilot scales them to ±0.5 in `normalise_rpy_factors`). The signs differ, and that is the main mistake when porting:

| Firmware | Where the matrix is | Pitch sign of a rear motor | Yaw of a CW motor |
|---|---|---|---|
| PX4 | computed from `CA_ROTORn_*` | negative (nose up = +My) | `KM` < 0 |
| ArduPilot | `add_motor_raw(n, roll, pitch, yaw, order)` | negative (as in PX4) | −1 |
| Betaflight | `mmix n THR ROLL PITCH YAW` | **positive** (`mixerQuadX`) | −1 (documentation: 1 = CCW) |

### Saturation: who gives way first
When a command goes outside [0, 1], something has to give:

- **PX4** (`CA_METHOD` = 1, or 2 = Auto, which picks sequential desaturation for a multirotor, `ControlAllocationSequentialDesaturation.cpp`). With `MC_AIRMODE` = 0 the thrust may only be reduced, then roll and pitch are squeezed, and yaw is added last and cut first; for it the upper bound is temporarily raised by 15 % (`MINIMUM_YAW_MARGIN`). With `MC_AIRMODE` = 1 the thrust may also be raised for roll/pitch, and with 2 also for yaw. `CA_METHOD` = 0 simply clips the outputs, and the axes start to affect each other.
- **ArduPilot** (`AP_MotorsMatrix::output_armed_stabilizing`). First yaw is limited to what fits at the "best" throttle, but no less than `MOT_YAW_HEADROOM`/1000 (default 200 → 0.2). If roll+pitch+yaw is still wider than the range, they are scaled together and the throttle is shifted; the `limit.*` flags are set. Air mode in Acro is enabled with `ACRO_OPTIONS` bit 0 or RC option 84.
- **Betaflight** (`mixer.c`, `mixer_type` = LEGACY by default; the 2025.12.5 options are LEGACY, LINEAR, DYNAMIC, EZLANDING. LINEAR and DYNAMIC are another way to fit the span into 0…1, through the common function `applyMixerAdjustmentLinear()`, and they differ in the formula for shifting each motor; EZLANDING is a limit for landing, `bf-features-tour`. Course guideline: LEGACY for an ordinary build; another type only as an experiment, comparing two logs of the same maneuver.) If the roll+pitch+yaw span is larger than 1, all three axes are divided by the span equally, after which the throttle is shifted so that everything fits. Without airmode, below 50 % throttle the span is additionally squeezed to 0.5…1. Roll priority over yaw comes earlier, at the PID stage: `pidsum_limit` = 500 against `pidsum_limit_yaw` = 400.

### Motor failure on a hexacopter
On an X hexacopter with alternating rotation (PNPNPN), after one motor is lost the pseudo-inverse itself drives the opposite motor to 0, and the remaining four hold the hover. Each carries W/4 instead of W/6, 1.5 times more. The motor at zero sits at its bound, and in some directions there is no torque margin (step 4). The PPNNPN layout (the `MotorMatrix_fault_tolerant_hex.lua` example in ArduPilot) survives some failures with a margin on every axis.

How the firmwares react:
- **PX4.** `CA_FAILURE_MODE` = 1 removes the failed motor from the matrix (in 1.15–1.18 it is the only mode besides 0 = Ignore). The failure is reported by a detector based on ESC current: in 1.18, `FD_ACT_EN` (default **0**, the check is off), the expected current `MOTFAIL_C2T` = 35 A at full thrust, the tolerance `MOTFAIL_OFF` = 10 A either way, `MOTFAIL_TIME` = 1 s (`esc_check_params.yaml`, v1.18.0); in 1.15–1.17, `FD_ACT_EN` = 1, `FD_ACT_MOT_THR` = 0.2, `FD_ACT_MOT_C2T` = 2.0 A/%, `FD_ACT_MOT_TOUT` = 100 ms. The action is set by `COM_ACT_FAIL_ACT`. On the main branch the modes are extended: 1 and 2 additionally stop or reverse the opposite motor of a hexacopter.
- **ArduPilot.** The `thrust_loss_check` detector turns on thrust boost if for 1 s the vehicle descends with throttle ≥ 90 % (or at the throttle limit) and a target lean angle < 15°. The GCS gets the message "Potential Thrust Loss (N)". The motor with the highest filtered output is considered lost and excluded from the saturation calculation; the thrust imbalance detector works only with ≥ 6 motors.
- **Betaflight.** There is no dedicated handling of a motor failure.

### Tilted motors
If you tilt the motor axis tangentially to the circle by an angle θ, in the same direction as its reaction torque acts, the arm r also starts working for yaw:

**Mz = CT · (r · sinθ + |KM| · cosθ)**, and the vertical thrust drops as **cosθ**.

With r = 0.246 m and KM = 0.05, a 10° tilt gives ×1.84 in yaw at the cost of 1.5 % of thrust; the side forces of the pairs cancel each other. How to choose θ: from the log, find by how many times yaw authority falls short (yaw hits saturation in the maneuver), solve (r·sinθ + |KM|·cosθ) / |KM| = the required multiplier and take the smallest such θ: every extra degree costs 1 − cosθ of thrust in every flight regime. In the same example ×1.5 needs θ ≈ 6° at the cost of 0.5 % of thrust. The check afterwards: the same maneuver in the log without yaw saturation, and a hover throttle that has grown no more than calculated. In PX4 the tilt is the `CA_ROTORn_AX/AY/AZ` axis. The ArduPilot and Betaflight matrices have no rotor axis, and an equal increase of yaw on all motors would be eaten by the normalization.

{{diagram:alloc-pipeline|PX4 builds B from CA_ROTORn_*, inverts it once when the parameters change, and in every cycle only multiplies and desaturates; a motor failure means removing a column, not a new controller.}}

### Place in the system

- **Receives:** three torques and a thrust from the rate controller (`px4-control`); rotor positions and axes (`px4-setup-scratch`); motor spin directions (`f-motors-esc`).
- **Provides:** a normalized command to each motor and ESC; saturation flags to the controller; the behavior on a motor failure to the redundancy design (`el-redundancy`, `ap-heavy`).
- **If you get it wrong here:** the pitch sign is carried from PX4 into Betaflight `mmix` as is → the axis works backwards; a motor test without props catches it (`bf-setup-scratch`). The CG is off center but the matrix is symmetric → some motors hover near their limit, yaw is cut first, and the heading "drifts" during maneuvers; you see it as diverging outputs in `RCOU` (`ap-logs`).

## practice
The main path is Python 3 + numpy/scipy (numpy 2.5.3, scipy 1.18.1) and PX4 SITL. PX4 was not built in the author's container (2 cores, an incomplete source tree), so the SITL commands are taken from the PX4 1.17 documentation and marked as quotes. The Python code was run, and its output is pasted unedited.

### Step 1. An allocator as in PX4
The file `alloc.py` is a direct port of three PX4 functions: `computeEffectivenessMatrix`, `updateControlAllocationMatrixScale` and `ControlAllocationSequentialDesaturation`.

```python
# alloc.py - control allocation as PX4 control_allocator does it (v1.15-1.18)
import numpy as np

def effectiveness(rotors):
    """rotors: list of dict(p=(px,py,pz), a=(ax,ay,az), ct, km) -> B 6xN (Mx,My,Mz,Fx,Fy,Fz)."""
    B = np.zeros((6, len(rotors)))
    for i, r in enumerate(rotors):
        a = np.array(r.get("a", (0, 0, -1)), float); a /= np.linalg.norm(a)
        p = np.array(r["p"], float); ct = r.get("ct", 6.5); km = r["km"]
        B[:3, i] = ct * np.cross(p, a) - ct * km * a   # ActuatorEffectivenessRotors.cpp
        B[3:, i] = ct * a
    return B

def mix_matrix(B):
    """Pseudo-inverse + normalisation (ControlAllocationPseudoInverse.cpp)."""
    M = np.linalg.pinv(B)                                # N x 6
    nz = lambda c: max(np.sum(np.abs(c) > 1e-3), 1)
    rs = np.sqrt(np.sum(M[:, 0]**2) / (nz(M[:, 0]) / 2))
    ps = np.sqrt(np.sum(M[:, 1]**2) / (nz(M[:, 1]) / 2))
    s = np.ones(6); s[0] = s[1] = max(rs, ps); s[2] = M[:, 2].max()
    for ax in (5, 4, 3):                                 # thrust z first, x/y fall back to z
        c = np.abs(M[:, ax]); n = np.sum(c > 1e-7)
        s[ax] = c.sum() / n if n else s[5]
    M = M / s; M[np.abs(M) < 1e-3] = 0
    return M

def desat(u, v, increase_only=False, lo=0.0, hi=1.0):
    """desaturateActuators(): shift u along v to get back into [lo, hi]."""
    def gain(u):
        kmin = kmax = 0.0
        for ui, vi in zip(u, v):
            if abs(vi) < 0.2: continue
            if ui < lo: k = (lo - ui) / vi; kmin = min(kmin, k); kmax = max(kmax, k)
            if ui > hi: k = (hi - ui) / vi; kmin = min(kmin, k); kmax = max(kmax, k)
        return kmin + kmax
    g = gain(u)
    if increase_only and g < 0: return u
    u = u + g * v
    return u + 0.5 * gain(u) * v

def allocate(M, sp, method="seq", airmode=0):
    """sp = [roll, pitch, yaw, Fx, Fy, Fz] (normalised, hover Fz < 0)."""
    if method == "clip":                                 # CA_METHOD = 0
        return np.clip(M @ sp, 0, 1)
    R, P, Y, T = M[:, 0], M[:, 1], M[:, 2], M[:, 5]
    no_yaw = sp.copy(); no_yaw[2] = 0
    u = M @ no_yaw
    if airmode == 2:                                     # MC_AIRMODE = 2
        u = desat(u + Y * sp[2], T); return desat(u, Y)
    if airmode == 1: u = desat(u, T)                     # MC_AIRMODE = 1
    else: u = desat(desat(desat(u, T, True), R), P)      # MC_AIRMODE = 0
    u = u + Y * sp[2]                                    # mixYaw()
    u = desat(u, Y, hi=1.15)                             # MINIMUM_YAW_MARGIN = 0.15
    return desat(u, T, True)
```

### Step 2. Your own frame: a 7" dead cat
The front arms of such a frame are wider and shorter, and the CG is shifted aft. The code blocks of steps 2–5 are one file, `demo.py`; run it with `python3 demo.py`.

```python
import numpy as np
from scipy.optimize import linprog
from alloc import effectiveness, mix_matrix, allocate
np.set_printoptions(precision=3, suppress=True)

# --- 1. custom frame: "dead cat" 7", CG behind the geometric centre (metres, FRD)
cat = [dict(p=( 0.13,  0.17, 0), km= 0.05),   # 0 front right, CCW
       dict(p=(-0.15, -0.11, 0), km= 0.05),   # 1 rear left,   CCW
       dict(p=( 0.13, -0.17, 0), km=-0.05),   # 2 front left,  CW
       dict(p=(-0.15,  0.11, 0), km=-0.05)]   # 3 rear right,  CW
B = effectiveness(cat); M = mix_matrix(B)
print("mix [roll pitch yaw thrust]:\n", M[:, [0, 1, 2, 5]])
u = M @ [0, 0, 0, 0, 0, -0.5]
print("hover u:", u, "front/rear:", round(u[0] / u[1], 3))
```

```text
mix [roll pitch yaw thrust]:
 [[-0.707  0.707  0.647 -1.071]
 [ 0.707 -0.707  1.    -0.929]
 [ 0.707  0.707 -0.647 -1.071]
 [-0.707 -0.707 -1.    -0.929]]
hover u: [0.536 0.464 0.536 0.464] front/rear: 1.154
```

In hover the front motors are loaded 15.4 % more than the rear ones, and that is exactly 0.15/0.13, the ratio of the arms to the CG. Roll is done by the diagonal pairs (all coefficients 0.707), and yaw loads the rear motors more (1.0 against 0.647).

### Step 3. Saturation
```python
def run(name, sp, **kw):
    sp = np.array(sp, float); want = B @ (M @ sp); got = B @ allocate(M, sp, **kw)
    print(f"{name:20s} roll {got[0]/want[0]:.2f}  yaw " +
          (f"{got[2]/want[2]:.2f}" if abs(want[2]) > 1e-6 else " -  ") + f"  thrust {got[5]/want[5]:.2f}")
hard = [0.6, 0, 0.5, 0, 0, -0.6]
print("ideal u:", M @ hard)
run("CA_METHOD=0 clip", hard, method="clip")
run("seq, MC_AIRMODE=0", hard, airmode=0)
low = [0.4, 0, 0, 0, 0, -0.05]
run("low thr, AIRMODE=0", low, airmode=0)
run("low thr, AIRMODE=1", low, airmode=1)
```

```text
ideal u: [ 0.542  1.481  0.744 -0.367]
CA_METHOD=0 clip     roll 0.61  yaw 0.48  thrust 0.95
seq, MC_AIRMODE=0    roll 1.00  yaw 0.15  thrust 0.90
low thr, AIRMODE=0   roll 0.16  yaw  -    thrust 1.00
low thr, AIRMODE=1   roll 1.00  yaw  -    thrust 6.09
```

Clipping gives 61 % of the roll and a spurious pitch. Desaturation gives 100 % of the roll, while yaw drops to 15 % and thrust to 90 %. At 5 % throttle without airmode, 16 % of the roll is left: that is how a vehicle tumbles on a descent. With `MC_AIRMODE` = 1 the roll is full, but the thrust grows 6 times: the vehicle jumps up. That is why PX4 tells you to keep airmode off while tuning.

### Step 4. A hexacopter with a dead motor
The geometry, numbering and spin directions are taken from `10044_sihsim_hex` (1 m arm); CT = 1 is the calculation's normalization, while the airframe itself keeps the default 6.5. A vehicle with T/W = 3 hovers on 2 thrust units out of 6.

```python
ang = [30, 90, 150, -150, -90, -30]
hexa = lambda s: [dict(p=(np.cos(np.radians(a)), np.sin(np.radians(a)), 0), ct=1, km=0.05 * k)
                  for a, k in zip(ang, s)]
PNPNPN, PPNNPN = [1, -1, 1, -1, 1, -1], [-1, -1, 1, -1, 1, 1]
def margins(rot, lost, W=2.0):            # max |torque| per axis while the other two stay 0
    Bh = effectiveness(rot)[[0, 1, 2, 5]]; bnd = [(0, 0) if i == lost else (0, 1) for i in range(6)]
    out = []
    for ax in range(3):
        for sg in (1, -1):
            r = linprog(-sg * Bh[ax], A_eq=np.delete(Bh, ax, 0), b_eq=[0, 0, -W], bounds=bnd)
            out.append(max(sg * Bh[ax] @ r.x, 0) if r.success else 0)
    return np.round(out, 2)               # +R -R +P -P +Y -Y
Bh = effectiveness(hexa(PNPNPN))[[0, 1, 2, 5]]; Bh[:, 0] = 0          # CA_FAILURE_MODE=1
print("PNPNPN, M0 lost, pinv hover u:", np.linalg.pinv(Bh) @ [0, 0, 0, -3.0])
for k in range(6):
    print(f"lost M{k}: PNPNPN {margins(hexa(PNPNPN), k)}  PPNNPN {margins(hexa(PPNNPN), k)}")
```

```text
PNPNPN, M0 lost, pinv hover u: [-0.    0.75  0.75 -0.    0.75  0.75]
lost M0: PNPNPN [1.5  0.   0.   1.73 0.   0.1 ]  PPNNPN [1.   1.   0.58 1.73 0.1  0.03]
lost M1: PNPNPN [1.5  0.   1.73 1.73 0.1  0.  ]  PPNNPN [1.   1.   1.73 1.73 0.1  0.1 ]
lost M2: PNPNPN [1.5  0.   1.73 0.   0.   0.1 ]  PPNNPN [1.   0.   1.73 0.   0.   0.1 ]
lost M3: PNPNPN [0.   1.5  1.73 0.   0.1  0.  ]  PPNNPN [0.   1.   1.73 0.   0.1  0.  ]
lost M4: PNPNPN [0.   1.5  1.73 1.73 0.   0.1 ]  PPNNPN [1.   1.   1.73 1.73 0.1  0.1 ]
lost M5: PNPNPN [0.   1.5  0.   1.73 0.1  0.  ]  PPNNPN [1.   1.   0.58 1.73 0.03 0.1 ]
```

For PNPNPN the pseudo-inverse (at T/W = 2, W = 3) sets the opposite motor M3 to 0, and the other four run at 75 %. With any failure at least two zeros remain, always in one roll direction and one yaw direction. The vehicle hovers, but it has nothing left to counter a gust from the "zero" side. PPNNPN survives the failure of M0, M1, M4 and M5 with a margin in all six directions, and with M2 or M3 lost it also ends up with zeros. The conclusion for a design: a hexacopter by itself does not protect you from a motor failure. You need a rotation layout checked with a calculation like this, and thrust margin: with PNPNPN, four motors carry the whole weight, that is, each carries 1.5 times its normal load.

### Step 5. Tilting the motors
```python
P, KM = [(0.174, 0.174), (-0.174, -0.174), (0.174, -0.174), (-0.174, 0.174)], [0.05, 0.05, -0.05, -0.05]
def tilted(deg):
    s, c = np.sin(np.radians(deg)), np.cos(np.radians(deg))
    return [dict(p=(x, y, 0), km=k, a=(-y / np.hypot(x, y) * np.sign(k) * s,
                                       x / np.hypot(x, y) * np.sign(k) * s, -c)) for (x, y), k in zip(P, KM)]
B0 = effectiveness(tilted(0))
for d in (0, 5, 10, 15):
    Bt = effectiveness(tilted(d))
    print(f"tilt {d:2d} deg: yaw x{Bt[2,0]/B0[2,0]:.2f}  Fz x{Bt[5,0]/B0[5,0]:.3f}")
print("CA_ROTOR0_AX/AY/AZ @10 deg:", np.round(tilted(10)[0]["a"], 3))
```

```text
tilt  0 deg: yaw x1.00  Fz x1.000
tilt  5 deg: yaw x1.43  Fz x0.996
tilt 10 deg: yaw x1.84  Fz x0.985
tilt 15 deg: yaw x2.24  Fz x0.966
CA_ROTOR0_AX/AY/AZ @10 deg: [-0.123  0.123 -0.985]
```

{{diagram:chart-alloc-tilt|Tilting the motors tangentially by 10° gives ×1.84 in yaw torque at the cost of 1.5 % of vertical thrust. Because of the PX4 normalization, the physical gain of the yaw loop grows by the same factor, so the yaw tuning has to be checked again.}}

In the normalized PX4 matrix the yaw column stays [1 1 −1 −1], so the torque per unit of command grows from 1.30 to 2.39 (×1.84). The same `MC_YAWRATE_K` now gives a loop 1.84 times stiffer.

### Step 6. Carrying it over to the firmwares and PX4 SITL
PX4: `CA_AIRFRAME` = 0 (Multirotor), `CA_ROTOR_COUNT` = 4, `CA_ROTORn_PX/PY` from step 2, `CA_ROTORn_KM` = ±0.05; in Actuators → Geometry check the diagram and Direction CCW. The documentation (Actuators): "The X, Y, Z positions are in FRD coordinate frame, relative to the centre of gravity". A hexacopter failure in SITL (PX4 1.17, quotes from the SIH and Failure Injection documentation): build with `make px4_sitl sihsim_hex`, then `SYS_FAILURE_EN` = 1, `CA_FAILURE_MODE` = 1, take off, in pxh `failure motor off -i 1`, and to restore `failure motor ok -i 1`. According to the 1.17 source, the injection only stops the motor (`motor_stop_mask`, "Stopping motors" in the console). It is the failure detector that removes it from the matrix, and then "Removing motor from allocation" appears in the console. In the log (Flight Review / pyulog) look at `control_allocator_status.motor_stop_mask`, `handled_motor_failure_mask`, `unallocated_torque`, `actuator_motors.control[0..5]`. If the motor has been removed, the expectation from step 4 is: the opposite motor near 0, the rest near 75 % at T/W 2.

Betaflight (configuration, not run in the container; the pitch column is taken with the opposite sign, roll and pitch are scaled to ±1):

```text
mixer CUSTOM
mmix reset
mmix 0 0.929 -1.000  1.000 -1.000
mmix 1 1.071 -1.000 -1.000  0.647
mmix 2 0.929  1.000  1.000  1.000
mmix 3 1.071  1.000 -1.000 -0.647
save
```

The motor order is as in QUADX: 0 is RR, 1 is FR, 2 is RL, 3 is FL. ArduPilot (`FRAME_CLASS` = 15, `SCR_ENABLE` = 1, the script in `APM/scripts/`, not run in the container):

```lua
MotorsMatrix:add_motor_raw(0, -0.707,  0.707,  0.647, 1)  -- front right, CCW
MotorsMatrix:add_motor_raw(1,  0.707, -0.707,  1.0,   3)  -- rear left, CCW
MotorsMatrix:add_motor_raw(2,  0.707,  0.707, -0.647, 4)  -- front left, CW
MotorsMatrix:add_motor_raw(3, -0.707, -0.707, -1.0,   2)  -- rear right, CW
MotorsMatrix:set_throttle_factor(0, 1.071)
MotorsMatrix:set_throttle_factor(1, 0.929)
MotorsMatrix:set_throttle_factor(2, 1.071)
MotorsMatrix:set_throttle_factor(3, 0.929)
assert(MotorsMatrix:init(4), "Failed to init MotorsMatrix")
motors:set_frame_string("deadcat 7")
```

`set_throttle_factor` works only before `init()` and only in class 15. The factors here are fractions of thrust: the linearization into throttle is done by `THR_MDL_FAC` / `MOT_THST_EXPO`.

### Moving to real hardware
1. **Props removed**, battery through a smoke stopper. PX4: Actuators → Enable sliders (or Identify & Assign Motors for PWM); ArduPilot: Motor Test, order A-B-C-D = testing order; Betaflight: the Motors tab. The PX4 documentation says it plainly: "Remove the propellers from motors before assigning outputs or any testing".
2. For each motor: its place on the frame matches the diagram, the spin direction matches `KM` / the yaw sign (tape on the bell), the motor does not spin when disarmed, and at minimum it spins steadily.
3. Signs without props: arm in Stabilize/Acro, tilt the frame to the right by hand, and the right motors should spin up; turn it in yaw, and the pair that counters the turn should speed up. Otherwise a column sign is wrong.
4. **Fit the props only now.** Hover for 30–60 s at 1–2 m, in an open area, with people at least 10 m away. Abort criterion: the vehicle drifts with centered sticks, or any motor is above 90 % → land.
5. The hover log: PX4 `actuator_motors`, ArduPilot `RCOU.C1…C4`, Betaflight `motor[0..3]`. On a dead cat the ratio of the mean front outputs to the rear ones should match step 2 within ±5 %: in PX4 `actuator_motors` this is thrust (1.15; `THR_MDL_FAC` is applied later, in the output driver), while in the ArduPilot and Betaflight commands it is about √1.15 ≈ 1.07, if thrust grows as the square of the command. The mean outputs of the CW pair and the CCW pair differ by no more than 5 %, or else a motor is misaligned or `KM` is wrong.

Self-check: the lab is done when: (SITL/calculation) the mix columns and the load ratio of your frame are computed in Python and explained by the geometry (first reproduce the dead cat from step 2: the front motors are loaded 15.4 % more, and that is the arm ratio 0.15/0.13); the saturation table from step 3 is repeated for your frame, with a conclusion on which axis gives way first; in the SIH hexacopter after `failure motor off -i 1` the log has a nonzero `motor_stop_mask`, you have recorded whether the removal from the matrix fired (`handled_motor_failure_mask`), and the motor outputs are compared with the step 4 prediction; (hardware) the motor test without props matches the diagram in the place and direction of every motor, and the hover log shows an output ratio within ±5 % of the calculation and no motor above 90 %.

## diagnostics
- **Symptom:** on liftoff the vehicle flips over abruptly
  - Possible cause: a wrong motor order or direction, or a column sign mixed up (in Betaflight the pitch sign is opposite to PX4/ArduPilot).
  - What to do: remove the props, test the motors one at a time, check the signs by tilting the frame by hand (step 3 of moving to hardware).
- **Symptom:** in sharp roll maneuvers yaw "lets go" and the vehicle overshoots its heading
  - Possible cause: normal desaturation: yaw is cut first (PX4 `MINIMUM_YAW_MARGIN`, ArduPilot `MOT_YAW_HEADROOM`, Betaflight `pidsum_limit_yaw`).
  - What to do: raise the T/W or the throttle headroom; on ArduPilot raise `MOT_YAW_HEADROOM`; on PX4 check `control_allocator_status.unallocated_torque[2]`.
  - What the log shows: yaw in saturation at the roll peaks, `actuator_saturation` ≠ 0.
- **Symptom:** a tumble or a "drop" at zero throttle on a descent
  - Possible cause: airmode is off, and at low throttle the roll is squeezed (in step 3, down to 16 %).
  - What to do: `MC_AIRMODE` = 1 after tuning (PX4), `ACRO_OPTIONS` bit 0 (ArduPilot), AIRMODE (Betaflight); in PX4 yaw airmode requires an arm switch.
- **Symptom:** after changing the frame or tilting the motors, yaw oscillates
  - Possible cause: the PX4 normalization keeps the command, but the physical gain has grown (×1.84 at 10°).
  - What to do: reduce `MC_YAWRATE_K`/P in proportion to the effectiveness increase and retune.
- **Symptom:** after a motor failure the hexacopter spins in yaw and drifts away
  - Possible cause: PNPNPN has no margin in some directions; `CA_FAILURE_MODE` = 0, or the detector did not fire (no ESC current telemetry for `FD_ACT_*`).
  - What to do: T/W ≥ 3, check the layout (PPNNPN), enable `CA_FAILURE_MODE` = 1 and test the detector in SITL.
  - Consequences: without failure handling PX4 keeps allocating torque to the dead motor, and the error grows until control is lost.
- **Symptom:** ArduPilot with a scripted matrix does not arm
  - Possible cause: `SCR_ENABLE` = 0, the script is not in `APM/scripts/`, `init()` was called before `add_motor_raw`, `FRAME_CLASS` ≠ 15.
  - What to do: the script messages in the GCS, the order of the calls, a reboot after changing `FRAME_CLASS`.

## checklist
- I can write the B column for a motor from its position, axis, CT and KM
- I understand why PX4 normalizes the matrix and how that changes the gain after a geometry change
- I know who gives way first at saturation in PX4, ArduPilot and Betaflight
- I computed the hover load of the motors on my frame
- I understand why a PNPNPN hexacopter has no margin in some directions after a failure
- I carried the matrix over to mmix / Lua / CA_* with the correct signs
- I checked the motors without props and compared the hover log with the calculation

## references
- PX4 Guide: Control Allocation (Mixing) | https://docs.px4.io/v1.17/en/concept/control_allocation.html | primary | A
- PX4 Guide: Actuator Configuration and Testing | https://docs.px4.io/v1.17/en/config/actuators.html | primary | A
- PX4 Guide: System Failure Injection | https://docs.px4.io/v1.17/en/debug/failure_injection.html | primary | A
- PX4 source: ActuatorEffectivenessRotors.cpp (v1.17.0) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessRotors.cpp | primary | A
- PX4 source: ControlAllocationSequentialDesaturation.cpp (v1.17.0) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/lib/control_allocation/control_allocation/ControlAllocationSequentialDesaturation.cpp | primary | A
- PX4 source: control_allocator module.yaml (CA_* parameters, v1.17.0) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/control_allocator/module.yaml | primary | A
- ArduPilot source: AP_MotorsMatrix.cpp (Copter-4.7.2; the same algorithm in 4.6.3) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Motors/AP_MotorsMatrix.cpp | primary | A
- ArduPilot example: MotorMatrix_fault_tolerant_hex.lua | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_Scripting/examples/MotorMatrix_fault_tolerant_hex.lua | primary | A
- Betaflight: Mixer (mmix, mixer_type) | https://betaflight.com/docs/wiki/guides/current/Mixer | primary | A
- Betaflight source: mixer.c (tag 2025.12.5; the mixing functions are the same as in 4.5) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/mixer.c | primary | A
