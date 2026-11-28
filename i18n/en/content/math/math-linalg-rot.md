---
id: math-linalg-rot
title: "Vectors, matrices and rotations: the language of attitude"
level: L2
readingTime: 45 min
firmware: ArduPilot (checked against 4.7.3) · PX4 (checked against v1.18.0) · Betaflight
status: published
added: 2026-11-08
tags:
  - linear algebra
  - rotations
  - quaternions
  - coordinate frames
related:
  - est-attitude
  - est-kalman
  - f-physics
next:
  - math-ode-dyn
source: content/math/math-linalg-rot.md
source_hash: e9cf87605c5d
---

## summary
Everything the autopilot says about attitude (the angles on the OSD, the quaternion in `ATT`/`AHRS`, the gravity vector in body axes, "where the camera is pointing") comes down to a handful of linear algebra operations. This module gives you exactly those: a vector as an arrow and as a column of numbers, the dot and cross products, a rotation matrix as "where the axes went," composing rotations and why the order matters, Euler angles and their singularity, the quaternion as a compact, singularity-free form of the same rotation, small rotations and the attitude derivative, and finally the four coordinate frames people mix up most often (NED/FRD in ArduPilot and PX4, ENU/FLU in ROS). The lab: a 14-function `rot.py` library checked against `scipy.spatial.transform`. Not sure whether you need this elective? Take the [10-problem entry test](../pages/prerequisites.html).

## theory
### A vector: an arrow and numbers
A vector is an arrow (a direction and a length), and a column of numbers is its coordinates **in a chosen basis**. The same arrow "down toward the center of the Earth" is written as (0, 0, 9.81) in the NED basis, and as (0, 4.9, 8.5) in the axes of an airframe rolled 30°. That is why every vector in code needs a label saying which axes it is expressed in: `g_ned`, `a_body`. Most attitude bugs are a vector in one basis used as if it were in another.

Length: |v| = √(v·v). Unit vector: v/|v|. A basis is three mutually perpendicular unit vectors; it is right-handed if **x × y = z** (thumb x, index finger y, middle finger z of the right hand).

### Dot and cross products
The **dot product** a·b = |a||b|cos θ = aₓbₓ + a_yb_y + a_zb_z. It means "how much of a lies along b." Uses: projecting thrust onto the vertical (T·ẑ), the angle between vectors, checking perpendicularity (= 0). The vehicle's tilt from vertical: cos θ = g_body·(0,0,1)/|g_body|.

The **cross product** a × b is a vector perpendicular to both, with length |a||b|sin θ and direction by the right-hand rule. Components: (a_yb_z − a_zb_y, a_zbₓ − aₓb_z, aₓb_y − a_yb_x). Uses: torque M = r × F (lever arm times force, which is exactly how the mixer computes motor torques), the velocity of a point v = ω × r, the normal to a plane. It is anticommutative: b × a = −(a × b).

### The rotation matrix
A rotation is a linear transformation that preserves lengths and angles. Its matrix R (3×3) has the properties Rᵀ R = I (orthonormal columns) and det R = +1. The set of such matrices is the group SO(3). The most useful reading: **the columns of R are the axes of the rotated basis, written in the original one**. If R_nb takes body to NED (v_ned = R_nb · v_body), then the first column of R_nb is where the vehicle's nose points, in NED coordinates.

The inverse rotation is the transpose: R⁻¹ = Rᵀ. So v_body = R_nbᵀ · v_ned, and there should be no matrix inversions in attitude code.

Elementary rotations about the axes (angle φ; right-hand rule: a positive rotation is counterclockwise when viewed from the tip of the axis):

```
Rx(φ) = [[1, 0, 0], [0, cos φ, −sin φ], [0, sin φ, cos φ]]
Ry(θ) = [[cos θ, 0, sin θ], [0, 1, 0], [−sin θ, 0, cos θ]]
Rz(ψ) = [[cos ψ, −sin ψ, 0], [sin ψ, cos ψ, 0], [0, 0, 1]]
```

### Composition: order matters
Rotations do not commute: Rx(90°)·Ry(90°) ≠ Ry(90°)·Rx(90°); check it with a cube or in the lab. The rule for reading a product R = A·B·v: B is applied to the vector first, then A. The aerospace Euler sequence "yaw → pitch → roll" (ZYX) gives the matrix from body to NED:

R_nb = Rz(ψ) · Ry(θ) · Rx(φ)

Read it like this: a vector in body axes is first "unwound" by roll, then by pitch, then by yaw, and comes out in NED. In ArduPilot code this is `Matrix3f::from_euler(roll, pitch, yaw)`, in PX4 `matrix::Dcmf(matrix::Eulerf(...))`.

{{diagram:rot-order-noncommute|Rx(90°)·Ry(90°) and Ry(90°)·Rx(90°) take (1, 0, 0) to different vectors, (0, 1, 0) and (0, 0, −1): the right-hand factor acts first.}}

{{diagram:frames-rotations|Coordinate frames: NED and FRD (ArduPilot, PX4) versus ENU and FLU (ROS). The same vehicle, different axis labels, and different signs for "up."}}

### Euler angles and their singularity
The angles (roll φ, pitch θ, yaw ψ) are convenient for humans and useless as an internal representation: at θ = ±90° the roll and yaw axes coincide (gimbal lock), and φ and ψ cannot be recovered from the matrix uniquely, only their sum or difference. Ranges: φ ∈ (−180°, 180°], θ ∈ [−90°, 90°], ψ ∈ (−180°, 180°] (the OSD usually shows heading as 0–360°). Extraction from the matrix: θ = −asin(R₃₁), φ = atan2(R₃₂, R₃₃), ψ = atan2(R₂₁, R₁₁); use `atan2`, not `atan`, or you lose the quadrant. For aerobatics, a wing hovering vertically, and any state estimation, Euler angles are not used inside the filter.

### The quaternion
A quaternion q = (w, x, y, z) = (cos(α/2), **n**·sin(α/2)) encodes a rotation by angle α about a unit axis **n**. Four numbers instead of nine, one normalization constraint instead of six orthogonality conditions, and no singularity. Operations:
- The conjugate q* = (w, −x, −y, −z) is the inverse rotation (for a unit quaternion).
- The product q₁ ⊗ q₂ is the composition of rotations (q₂ first, then q₁, as with matrices, under the Hamilton convention):
  w = w₁w₂ − x₁x₂ − y₁y₂ − z₁z₂; x = w₁x₂ + x₁w₂ + y₁z₂ − z₁y₂; y = w₁y₂ − x₁z₂ + y₁w₂ + z₁x₂; z = w₁z₂ + x₁y₂ − y₁x₂ + z₁w₂.
- Rotating a vector: v' = q ⊗ (0, v) ⊗ q*. In practice it is faster through the matrix: R(q) with elements R₁₁ = 1 − 2(y² + z²), R₁₂ = 2(xy − wz), R₁₃ = 2(xz + wy) and so on.
- q and −q are the same rotation (the double cover). So when comparing quaternions and when interpolating, look at the sign of their dot product.
- Normalize after every update, otherwise rounding errors accumulate and the "rotation" starts to scale.

ArduPilot keeps the EKF attitude as a quaternion (`Quaternion` in `AP_Math`), logged as `XKQ`; PX4 as `vehicle_attitude.q` in (w, x, y, z) order. ROS 2 (`geometry_msgs/Quaternion`) uses the order **(x, y, z, w)**. Mixing up the order is a classic companion-integration bug.

### Small rotations and the attitude derivative
For a small angle δ: sin δ ≈ δ, cos δ ≈ 1, and the rotation by the vector δ = (δₓ, δ_y, δ_z) is approximated as R ≈ I + [δ]ₓ, where [δ]ₓ is the skew-symmetric cross-product matrix. From this comes the key gyro equation: if ω is the angular rate in body axes, then over a step Δt the attitude is updated as q ← q ⊗ (1, ω·Δt/2), followed by normalization. This is "gyro integration" in any AHRS: hundreds to thousands of times per second (at the loop rate), the quaternion is multiplied by an almost-identity one. Small-angle errors are what the EKF estimates as a correction: not a "new attitude" but a δ by which the current one is rotated a little further.

### Coordinate frames to know by heart
| Frame | Axes | Who uses it | Tell-tale sign |
|---|---|---|---|
| NED | North, East, Down | ArduPilot, PX4 (local), MAVLink `LOCAL_POSITION_NED` | altitude is **negative** (z down) |
| FRD | Forward, Right, Down (body) | ArduPilot, PX4, MAVLink | g in hover = (0, 0, +9.81) |
| ENU | East, North, Up | ROS, REP-103, geodesy | z up, yaw from east, counterclockwise |
| FLU | Forward, Left, Up (body) | ROS `base_link` | a right turn is a negative yaw |

FRD → FLU: (x, y, z) → (x, −y, −z). NED → ENU: (n, e, d) → (e, n, −d). Yaw: ψ_enu = 90° − ψ_ned. `px4_ros_com`/MAVROS does all of this, but when "the camera points the wrong way" or "the drone flies south instead of north," these two substitutions are exactly what to check.

### Where it fits

- **Takes in:** the angular rate and the gravity vector in body axes from the IMU (`est-sensors`); the attitude quaternion from the estimator: ArduPilot (`ap-ekf`), PX4 (`px4-architecture`).
- **Hands off:** the matrix R_nb and quaternions to attitude estimation (`est-attitude`); the torque M = r × F to the mixer (`ctl-allocation`); the NED ↔ ENU and FRD ↔ FLU substitutions to the ROS 2 integration (`ros2-basics`, `px4-ros2`).
- **If you get this wrong:** you mixed up the quaternion order (w, x, y, z) and (x, y, z, w) → the companion gets a different attitude → "the camera points the wrong way" when converting a pixel to a point on the ground (`per-geometry`). You skipped the NED → ENU substitution → the drone flies south instead of north, or down instead of climbing (`px4-ros2`).

## practice
### Step 1. The `rot.py` library
Write 14 functions without libraries (only `math` and lists, or `numpy`): `dot`, `cross`, `norm`, `rot_x/rot_y/rot_z(angle)`, `euler_to_R(roll, pitch, yaw)`, `R_to_euler(R)`, `quat_mul(q1, q2)`, `quat_conj(q)`, `quat_to_R(q)`, `R_to_quat(R)`, `rotate_vec(q, v)`, `small_angle_update(q, omega, dt)`.

```python
import numpy as np
from scipy.spatial.transform import Rotation as Rot
import rot

for _ in range(1000):
    e = np.random.uniform(-np.pi, np.pi, 3); e[1] = np.random.uniform(-1.4, 1.4)   # avoid gimbal lock in the check
    R_ref = Rot.from_euler("ZYX", e[::-1]).as_matrix()                              # yaw, pitch, roll
    R = rot.euler_to_R(*e)
    assert np.allclose(R, R_ref, atol=1e-9)
    assert np.allclose(rot.R_to_euler(R), e, atol=1e-9)
    q = rot.R_to_quat(R); q_ref = Rot.from_matrix(R).as_quat()                       # scipy: (x, y, z, w)!
    assert np.allclose(np.abs(q), np.abs([q_ref[3], *q_ref[:3]]), atol=1e-9)        # sign-agnostic
    v = np.random.randn(3)
    assert np.allclose(rot.rotate_vec(q, v), R @ v, atol=1e-9)
print("rot.py: all checks passed")
```

The test must pass a thousand times on random angles. If only `R_to_euler` fails as |θ| → 90°, that is not a bug but gimbal lock, and the test deliberately avoids it.

### Step 2. Gravity in body axes
A vehicle at roll = 20°, pitch = −10°, yaw = 135°. Find what the accelerometer should read (in m/s², FRD axes) in a hover with no acceleration. Check the answer with `R_nbᵀ · (0, 0, −9.81)`: the accelerometer measures specific force (−g), so when level it reads (0, 0, −9.81) in FRD. Note that yaw does not affect the result; explain why.

### Step 3. Non-commutativity
Compute Rx(90°)·Ry(90°) and Ry(90°)·Rx(90°) and apply them to the vector (1, 0, 0). Draw both results. Then do the same for 1° and 1° and confirm numerically that the difference is second-order small (which is why the small-angle approximation works).

### Step 4. Gyro integration
Generate ω(t) = (0, 0, 1 rad/s) for 2π seconds with a 1 ms step. Integrate with `small_angle_update` and confirm that after 2π s the quaternion has returned to the initial one (up to sign). Repeat with a 50 ms step (round(2π/Δt) = 126 steps): the error is visible; compare the norm with and without normalization at every step.

Self-check: the lab is done when the step 1 self-test passes a thousand times on random angles, the step 2 answer matches the reference below, and the plots from steps 3–4 give the numbers in the reference.

**Reference answer for self-check.** Step 2: the accelerometer reads ≈ (−1.70, −3.30, −9.08) m/s², magnitude 9.81; yaw has no effect because it rotates about the vertical, which is exactly the direction of gravity. Step 3: Rx(90°)·Ry(90°) takes (1, 0, 0) to (0, 1, 0), and Ry(90°)·Rx(90°) to (0, 0, −1); for 1° and 1° the results differ by about 3·10⁻⁴, the square of the angle in radians. Step 4: with a 1 ms step the quaternion arrives at (−1, 0, 0, 0), which is the same rotation as the initial (1, 0, 0, 0); with a 50 ms step the z component is about −0.008: most of it is because 126 steps cover 6.30 s rather than 2π s; the update's own error is only ~0.001 rad (it rotates by 2·atan(ωΔt/2) instead of ωΔt per step). Without normalization |q| grows (to about 1.04 at 50 ms). Typical wrong results: the step 2 answer changes when yaw changes: R_nb was applied instead of R_nbᵀ; a rotation that is "almost right, but mirrored": the order (w, x, y, z) and (x, y, z, w) was mixed up.

## diagnostics
- **Symptom:** after conversion to ROS the drone "flies south," and the camera points down and back
  - Possible cause: the NED→ENU and FRD→FLU substitutions were not both done, or only one was.
  - What to do: check the signs of y and z separately for position and for attitude; yaw_enu = 90° − yaw_ned.
- **Symptom:** a quaternion from MAVLink gives a rotation that is "almost right, but mirrored"
  - Possible cause: (w,x,y,z) order versus (x,y,z,w).
  - What to do: check that the scalar part ≈ 1 at zero angles; reorder at the boundary.
- **Symptom:** the attitude estimate slowly "stretches," angles drift while stationary
  - Possible cause: the quaternion is not normalized after the update.
  - What to do: normalize after every multiplication; monitor |q| − 1.
- **Symptom:** Euler angles jump by ±180° in the log
  - Possible cause: not a bug: yaw range wrapping, or pitch passing through 90°.
  - What to do: use the quaternion/matrix for analysis, and angles for display only.

## references
- ArduPilot — AP_Math: Matrix3, Quaternion (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Math | primary | A
- PX4 — Matrix library (Dcm, Euler, Quaternion) | https://github.com/PX4/PX4-Autopilot/tree/v1.18.0/src/lib/matrix | primary | A
- ROS REP-103 — Standard Units of Measure and Coordinate Conventions | https://www.ros.org/reps/rep-0103.html | primary | A
- MIT OCW 18.06 — Linear Algebra (Strang) | https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/ | secondary | A
- J. Solà — Quaternion kinematics for the error-state Kalman filter | https://arxiv.org/abs/1711.02508 | secondary | A

## checklist
- I tell an arrow from its coordinates and label the basis of every vector
- I can compute dot and cross products and know what they mean physically
- I read the columns of a rotation matrix as the axes of the new basis; I remember R⁻¹ = Rᵀ
- I understand why rotation order matters and where Euler angles become singular
- I can multiply quaternions, rotate a vector and do a small-angle gyro update
- I convert between NED/FRD and ENU/FLU without sign errors
