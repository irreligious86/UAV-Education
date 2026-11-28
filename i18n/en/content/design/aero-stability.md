---
id: aero-stability
title: "Airplane: stability, CG, static margin, drag polar"
level: L3
readingTime: 45 min
firmware: ArduPlane 4.7 (checked against 4.7.3) · INAV 9.1 (checked against 9.1.0)
status: published
tags:
  - CG
  - neutral point
  - static margin
  - drag polar
  - flying wing
related:
  - aero-wing
  - ap-plane-tuning
  - inav-wing
  - ap-logs
  - f-aero-props
next:
  - ap-plane-tuning
source: content/design/aero-stability.md
source_hash: 892906493a4a
---

## summary
"Wing aerodynamics" gave you the rule "CG 5–15 % MAC ahead of the neutral point". Here you compute it yourself: the MAC of a tapered wing, the neutral point of a flying wing and of an airplane with a tail (through the horizontal tail volume coefficient), the static margin and the balance point, and then the drag polar: maximum lift-to-drag ratio, the best-range speed and the best-endurance speed. The worked example is the Skywalker 1830, using the manufacturer's data. Lab: a Python script with the calculation and a check against the CG from the manual, then balancing a real airframe, a glide test and a check of the pitch trim in the ArduPlane/INAV log.

## theory
### The MAC and where to find it
The mean aerodynamic chord (MAC) is the chord of an equivalent rectangular wing with the same moments. All CG percentages are measured from it, not from the root chord. For a tapered wing panel with root chord c_r, tip chord c_t, taper ratio λ = c_t/c_r, semispan b/2 and leading-edge sweep Λ:

- MAC = ⅔·c_r·(1 + λ + λ²)/(1 + λ);
- spanwise station y_MAC = (b/2)/3 · (1 + 2λ)/(1 + λ);
- the MAC leading edge lies aft of the root leading edge by x_LE = y_MAC·tan Λ.

For a straight wing x_LE = 0 and MAC ≈ S/b.

### Neutral point and static margin
The neutral point (NP) is the CG position at which the pitching moment does not depend on the angle of attack: dCm/dα = 0. The static margin is SM = (x_NP − x_CG)/MAC. Its physical meaning: dCm/dCL = −SM. With SM = 10 %, an increase of C_L by 0.1 (a gust pitched the nose up) gives a nose-down moment ΔCm = −0.01 that brings the airplane back. At SM = 0 there is no restoring moment, at SM < 0 a disturbance grows, and the autopilot holds the airframe only until the control surface saturates.

**Flying wing.** NP ≈ the wing's aerodynamic center: a quarter of the MAC, measured from its leading edge: x_NP = x_LE + 0.25·MAC. The CG goes 5–10 % MAC ahead of it.

**Airplane with a tail.** The horizontal tail moves the NP aft (Etkin, MIT 16.333):

h_n = h_ac + η·V_h·(a_t/a_w)·(1 − dε/dα), where h is in fractions of the MAC from its leading edge, h_ac ≈ 0.25;

- V_h = S_h·l_h/(S·MAC) is the **horizontal tail volume coefficient**: the tail area S_h times the tail arm l_h (from the quarter MAC of the wing to the quarter chord of the tail), divided by S·MAC. Trainers and FPV airplanes have 0.4–0.7; for your own design start with 0.6 (course guideline: in the worked Skywalker 1830 example, at 0.6 the whole CG range from the manual gives a margin of 6.6–11 %, at 0.5 the aft end gives only 2.2 %); for a ready-made airframe you do not choose V_h, you measure it;
- a = 2π·AR/(2 + √(AR² + 4)) is the C_L(α) slope of a wing or tail of finite aspect ratio, 1/rad;
- dε/dα ≈ 2a_w/(π·AR) is the downwash from the wing at the tail;
- η ≈ 0.9 is the dynamic pressure loss at the tail.

The fuselage and a motor ahead of the wing move the NP forward by a few % MAC: the formula is optimistic, so do not aim for the 5 % lower bound. XFLR5 (the vortex lattice method) computes the NP more accurately: you build the wing and the tail and find the CG position at which the Cm(α) curve goes flat; that is the NP.

### Trim and reflex on a flying wing
The moment about the CG: Cm = Cm0 − SM·C_L. Level flight means Cm = 0, that is C_L,trim = Cm0/SM. With a positive margin you need a **positive** Cm0. On an airplane the tail provides it with a negative incidence. A wing has no tail, and an ordinary cambered airfoil has Cm0 < 0 (about −0.05…−0.1), so wings fly on airfoils with an upturned trailing edge (reflex), on sweep with washout at the tips, or with the elevons raised by 2–4 mm. Example: SM = 8 %, cruise C_L = 0.35 → you need Cm0 = 0.08·0.35 = +0.028. At SM = 15 % it is already +0.053: more reflex, more trim drag, a lower C_Lmax. That is why wings keep a margin of 5–10 %, not 15.

### The polar, the lift-to-drag ratio and two "best" speeds
The drag polar: C_D = C_D0 + k·C_L², k = 1/(π·e·AR). C_D0 is the parasite drag (fuselage, camera, antennas, foam roughness), e is the Oswald efficiency factor (an ellipse is 1.0, a rectangular wing about 0.7 per NASA, a tapered wing with AR ≈ 8 is 0.75–0.85).

- The maximum lift-to-drag ratio (L/D)max = 1/(2√(C_D0·k)) at C_L = √(C_D0/k) → the speed V_md. For an electric airplane (the mass does not change) this is the **best-range speed**: the energy per kilometer is proportional to the drag force.
- Minimum power is at C_L = √(3·C_D0/k), V_mp = V_md/3^¼ ≈ 0.76·V_md, the **best-endurance speed**.
- The lower limit is the stall: V_s = √(2mg/(ρ·S·C_Lmax)). On heavily loaded FPV airplanes V_mp often ends up below 1.2·V_s, and endurance is in practice limited by `AIRSPEED_MIN`.
- Into a headwind, fly faster than V_md for range: the glider pilots' rule of thumb is to add about half the headwind component.

{{diagram:chart-stability-polar|For 2.7 kg and C_D0 0.040 the maximum L/D of 11.3 is at 10.8 m/s, and the minimum power speed (8.2 m/s) lies below the 9.4 m/s stall: endurance is limited by AIRSPEED_MIN, not by the polar. The L/D peak is flat: 12 m/s costs only 2.3 % more energy per kilometer.}}

### What a wrong CG does in flight and in the log
- **Aft CG (SM < 5 %)**: the airplane is "twitchy", overshoots in pitch, holds speed poorly, tends to tip stalls and spins; AUTOTUNE produces small gains. At SM < 0, after the launch the nose pitches up and the elevator hits its stop.
- **Forward CG (SM > 20 %)**: it needs constant up elevator, trim drag grows, there is not enough elevator to flare on landing, and the airplane is reluctant to leave the ground.
- **ArduPlane**: the CG documentation suggests looking at the pitch integrator `PIDP.I` after the first flight. Consistently above zero means the airplane needed up elevator (nose heavy, or the elevator trim is wrong); below zero means it is tail heavy. Also look at `CTUN.Pitch` against `CTUN.NavPitch` (oscillation means a small margin) and at the elevator output in `RCOU` against `SERVOn_TRIM`. `SERVO_AUTO_TRIM = 1` adjusts the servo trims in flight, but no more than 20 % away from center, and `PTCH_TRIM_DEG` sets the pitch angle of level flight. Both parameters fix the trim, not the CG.
- **INAV**: `fw_level_pitch_trim` (degrees) is the level-flight pitch in self-leveling modes, `feature FW_AUTOTRIM` auto-trims the servo midpoints. The sign is the same: a persistent nonzero pitch I term in Blackbox.

### Place in the system

- **Receives:** the wing geometry and the CG rule (`aero-wing`); the mass and the placement of the battery and payload (`des-sizing`); the parasite drag C_D0 from everything that sticks out into the airflow.
- **Provides:** the CG position and the static margin to the tuning preparation (`ap-plane-tuning`, `inav-wing`); V_md and V_mp to the choice of the cruise speed and `AIRSPEED_MIN`; the maximum L/D to the airplane power calculation (`des-sizing`).
- **If you get it wrong here:** an aft CG → pitch overshoot, AUTOTUNE produces small gains; people look for the cause in the PID, but it is in the balance (`ap-plane-tuning`). A forward CG → constant up elevator, the pitch integrator consistently above zero, more trim drag and consumption; visible in the log in `PIDP` (`ap-plane-tuning`).

## practice
### Step 1. The worked example data
The Skywalker 1830 (2015 version) is a popular conventional FPV platform. From the manufacturer's manual: span 1830 mm, wing area 41.06 dm², flying weight 2500–3000 g, CG 90–100 mm behind the wing leading edge. The wing is almost rectangular, so MAC ≈ S/b. The manufacturer does not give the tail dimensions, so the script builds a table over V_h, and later you plug in your own measurement. The tail aspect ratio is taken as 4, η = 0.9. For the polar the inputs are a mass of 2.7 kg (the middle of the range), e = 0.80, C_Lmax = 1.2 and C_D0 = 0.040. This is an estimate that the glide test in step 4 will refine.

### Step 2. The script
Save it as `aero_stability.py` and run `python3 aero_stability.py` (only Python 3 is needed).

```python
"""aero_stability.py - CG, neutral point, static margin and drag polar for a small fixed-wing UAV."""
import math

RHO, G = 1.225, 9.81


def lift_slope(ar):
    """3D lift-curve slope of a straight wing, 1/rad (Helmbold / DATCOM form)."""
    return 2 * math.pi * ar / (2 + math.sqrt(ar ** 2 + 4))


def trapezoid_mac(c_root, c_tip, half_span, sweep_le_deg):
    """MAC, its spanwise station and the x of its leading edge behind the root LE (m)."""
    lam = c_tip / c_root
    mac = 2 / 3 * c_root * (1 + lam + lam ** 2) / (1 + lam)
    y_mac = half_span / 3 * (1 + 2 * lam) / (1 + lam)
    x_le_mac = y_mac * math.tan(math.radians(sweep_le_deg))
    return mac, y_mac, x_le_mac


def np_with_tail(v_h, ar_w, ar_t, eta=0.9, h_ac_w=0.25):
    """Neutral point as a fraction of MAC: h_n = h_ac + eta*V_h*(a_t/a_w)*(1 - de/da)."""
    a_w, a_t = lift_slope(ar_w), lift_slope(ar_t)
    deda = 2 * a_w / (math.pi * ar_w)
    return h_ac_w + eta * v_h * (a_t / a_w) * (1 - deda)


def polar(m, s, b, cd0, e, cl_max, eta_total=0.5):
    w, ar = m * G, b ** 2 / s
    k = 1 / (math.pi * e * ar)
    v = lambda cl: math.sqrt(2 * w / (RHO * s * cl))
    cl_md, cl_mp = math.sqrt(cd0 / k), math.sqrt(3 * cd0 / k)
    out = {"AR": ar, "k": k, "V_s": v(cl_max), "V_mp": v(cl_mp), "V_md": v(cl_md),
           "LD_max": 1 / (2 * math.sqrt(cd0 * k))}
    for name, cl in (("V_md", cl_md), ("V_mp", cl_mp)):
        cd = cd0 + k * cl ** 2
        out["P_" + name] = w / (cl / cd) * out[name] / eta_total     # electric power, W
    return out


def cd0_from_glide(m, s, b, e, v, ld):
    """Back out C_D0 from a measured glide ratio L/D at airspeed v."""
    k = 1 / (math.pi * e * b ** 2 / s)
    cl = 2 * m * G / (RHO * v ** 2 * s)
    return cl / ld - k * cl ** 2


if __name__ == "__main__":
    # --- 1. Skywalker 1830 (2015), manufacturer manual: span 1830 mm, wing area 41.06 dm^2,
    #        flying weight 2500-3000 g, CG 90-100 mm behind the wing leading edge.
    b, s = 1.83, 0.4106
    mac = s / b                        # near-rectangular wing: MAC ~ mean chord
    ar = b ** 2 / s
    print(f"Skywalker 1830: AR = {ar:.2f}, MAC = {mac * 1000:.0f} mm")
    print(" V_h   NP,mm  SM@CG90  SM@CG100")
    for v_h in (0.4, 0.5, 0.6, 0.7, 0.8):
        h_n = np_with_tail(v_h, ar, ar_t=4.0)
        sm90, sm100 = h_n - 0.090 / mac, h_n - 0.100 / mac
        print(f" {v_h:.1f}  {h_n * mac * 1000:5.0f}  {sm90 * 100:6.1f} %  {sm100 * 100:6.1f} %")
    h_n = np_with_tail(0.6, ar, ar_t=4.0)
    for sm in (0.05, 0.10, 0.15):
        print(f" V_h 0.6: CG for SM {sm * 100:.0f} % = {(h_n - sm) * mac * 1000:.0f} mm from LE")

    # --- 2. Flying wing (training example): span 1.0 m, root 300 mm, tip 180 mm, LE sweep 25 deg
    mac_w, y_w, x_w = trapezoid_mac(0.30, 0.18, 0.50, 25)
    x_np = x_w + 0.25 * mac_w
    print(f"\nWing: MAC = {mac_w * 1000:.0f} mm at y = {y_w * 1000:.0f} mm, MAC LE at {x_w * 1000:.0f} mm")
    print(f" NP = {x_np * 1000:.0f} mm from root LE; CG for SM 8 % = {(x_np - 0.08 * mac_w) * 1000:.0f} mm")

    # --- 3. Drag polar, Skywalker 1830 at 2.7 kg; C_D0 and e are estimates to be refined by a glide test
    p = polar(m=2.7, s=s, b=b, cd0=0.040, e=0.80, cl_max=1.2)
    print(f"\nPolar: k = {p['k']:.4f}, (L/D)max = {p['LD_max']:.1f}")
    print(f" V_s = {p['V_s']:.1f} m/s, V_mp (endurance) = {p['V_mp']:.1f} m/s, V_md (range) = {p['V_md']:.1f} m/s")
    print(f" electric power at V_mp = {p['P_V_mp']:.0f} W, at V_md = {p['P_V_md']:.0f} W (eta 0.5)")
    print(f" glide 10.5 at 12 m/s -> C_D0 = {cd0_from_glide(2.7, s, b, 0.80, 12.0, 10.5):.3f}")
```

Output:

```text
Skywalker 1830: AR = 8.16, MAC = 224 mm
 V_h   NP,mm  SM@CG90  SM@CG100
 0.4     95     2.3 %    -2.1 %
 0.5    105     6.7 %     2.2 %
 0.6    115    11.1 %     6.6 %
 0.7    125    15.4 %    11.0 %
 0.8    134    19.8 %    15.3 %
 V_h 0.6: CG for SM 5 % = 104 mm from LE
 V_h 0.6: CG for SM 10 % = 92 mm from LE
 V_h 0.6: CG for SM 15 % = 81 mm from LE

Wing: MAC = 245 mm at y = 229 mm, MAC LE at 107 mm
 NP = 168 mm from root LE; CG for SM 8 % = 149 mm

Polar: k = 0.0488, (L/D)max = 11.3
 V_s = 9.4 m/s, V_mp (endurance) = 8.2 m/s, V_md (range) = 10.8 m/s
 electric power at V_mp = 44 W, at V_md = 50 W (eta 0.5)
 glide 10.5 at 12 m/s -> C_D0 = 0.044
```

### Step 3. Reading the result
The manufacturer's CG of 90–100 mm is 40–45 % MAC. For a flying wing that CG would be fatal, but for an airplane with a tail it is normal: at V_h = 0.6 the neutral point is at 115 mm (51 % MAC), the margin is 11 % at the forward end of the range and 6.6 % at the aft end. The conclusion: the forward end (90–92 mm) is for the first flight, and 100 mm only after you have made sure your V_h is no less than 0.6. At V_h = 0.4 the aft end is already unstable (−2.1 %). So measure S_h and l_h on your own airframe, compute V_h and plug it in.

{{diagram:chart-stability-margin|The margin drops by 0.45 % MAC for every millimeter the CG moves aft: the range from the manual (90–100 mm) gives 5–15 % only at V_h ≈ 0.56–0.69, so take the forward end for the first flight.}}

The wing from the training example: NP 168 mm from the root leading edge, CG for an 8 % margin at 149 mm. Note that this is 17 % MAC from its leading edge, but 50 % of the root chord. The classic mistake "CG at a quarter of the root chord" on a swept wing puts the CG 74 mm ahead of where it should be: a heavy nose with a margin of about 38 % MAC.

The polar: (L/D)max = 11.3 at 10.8 m/s, but that is only 1.15·V_s. Set `AIRSPEED_MIN` ≈ 1.25·9.4 ≈ 12 m/s and `AIRSPEED_CRUISE` to 12–13 m/s: at 12 m/s the L/D is 11.1, and the energy per kilometer is only 2.3 % above the optimum (at 13 m/s, 10.6 and +7 %). At 15 m/s you need 86 W against 50 W. The battery shift needed to move the CG by d is Δx_batt = d·M/m_batt: 10 mm with a 2.7 kg airplane and a 0.54 kg battery means 50 mm of battery travel.

### Moving to real hardware
1. **Propeller removed** for the whole time you balance and check the control surfaces. Weigh the airplane in full flying configuration: battery, camera, VTX, antennas.
2. Mark the calculated point on the underside of the wing next to the fuselage (for the Skywalker 1830, 92 mm from the leading edge) and balance the airplane on two fingers or a balancing stand. The nose should be slightly below the horizon. Move the battery rather than adding lead. Record the final CG position and the mass.
3. Check that the elevator is neutral at `SERVOn_TRIM`, and on a wing that the elevons are raised by the specified reflex.
4. **Fit the propeller only at the field**, just before the launch, after checking the modes. The first flight is in FBWA, climb to 80–100 m. Dive test: in level flight, release the stick in a shallow dive, and the airplane should pull out smoothly by itself.
5. **Glide test:** at 100 m, in calm air or into the wind, throttle to zero, hold a constant speed for 15–20 s. Repeat for 10, 12 and 14 m/s. L/D = V/w (airspeed from `CTUN.As`, sink rate from the barometric altitude `BARO.Alt`). Plug the L/D into `cd0_from_glide()` and recompute the polar with the real C_D0. Keep in mind that in FBWA, with the throttle below `TRIM_THROTTLE`, `STAB_PITCH_DOWN` (2° by default) is added to the pitch, so hold the speed with the stick, not by pitch angle.
6. **Log:** a stretch of steady cruise of ≥ 30 s in FBWA. The mean `PIDP.I` and the offset of the elevator output in `RCOU` from `SERVOn_TRIM` (on INAV, the pitch I term in Blackbox).

Hardware criteria: the CG within ±3 mm of the calculated point; the airplane recovers from the dive test by itself; in cruise the mean `PIDP.I` is close to zero and does not systematically change sign (as an estimate, no more than ~10 % of the elevator range); the measured L/D differs from the calculated one by no more than 25 %, otherwise recompute C_D0.

Self-check: the lab is done when (calculation, no hardware) the script has been run for your airframe or for the Skywalker 1830 example, and you have recorded the MAC, V_h, NP, the CG for a 10 % margin, and (L/D)max, V_md, V_mp, V_s (for the Skywalker 1830 example the numbers match the step 2 output and the step 3 discussion: NP at 115 mm for V_h = 0.6, margin 11 % at 90 mm and 6.6 % at 100 mm, (L/D)max = 11.3 at 10.8 m/s; for your own airframe the margin falls within 5–15 %), and `AIRSPEED_MIN` and `AIRSPEED_CRUISE` are justified by the polar; (hardware) the airplane is balanced at the calculated point ±3 mm, the dive test and the glide test with the C_D0 recalculation are done, and the sign and size of `PIDP.I` in the cruise log are explained by the CG or the trim.

## diagnostics
- **Symptom:** after the launch the airplane pitches up and stalls, with the elevator at its full down stop
  - Possible cause: the CG is behind the neutral point (SM < 0), a common mistake when the battery is moved aft for a "light tail" or a flying wing is balanced at a quarter of the root chord.
  - What the log shows: `CTUN.Pitch` rises against `CTUN.NavPitch`, the elevator output in `RCOU` is at its limit, `PIDP.I` is strongly negative.
  - What to do: recompute the NP, move the CG forward by 5–10 % MAC, repeat the balancing.
- **Symptom:** in cruise it constantly needs up elevator, lands "flat", and there is not enough flare
  - Possible cause: nose heavy, SM > 20 %.
  - What the log shows: a persistently positive `PIDP.I`, the elevator noticeably above `SERVOn_TRIM`.
  - What to do: move the CG aft by 3–5 mm per iteration until the margin is 10 %, then set the trim again.
- **Symptom:** pitch oscillation in FBWA/AUTO, and AUTOTUNE produced very small `PTCH_RATE_*`
  - Possible cause: a small margin (2–5 %), a weak natural pitch "spring".
  - What to do: move the CG forward by 2–3 % MAC; after any change of the CG or the payload, repeat AUTOTUNE.
- **Symptom:** a flying wing pulls toward the ground and needs a lot of "up elevator" even with the correct CG
  - Possible cause: the airfoil Cm0 is negative, no reflex or washout.
  - What to do: raise the elevons by 2–4 mm mechanically, not with the autopilot trim; if the difference is large, move to a reflex airfoil.
- **Symptom:** the flight time is 30–40 % below the polar-based estimate
  - Possible cause: C_D0 underestimated (antennas, camera, gaps), or the cruise is above V_md.
  - What to do: a glide test, recompute C_D0 with `cd0_from_glide()`, lower `AIRSPEED_CRUISE` toward 1.25·V_s.
- **Symptom:** `SERVO_AUTO_TRIM` has "drifted" to its limit, and the airplane still does not hold level flight
  - Possible cause: the auto-trim is masking the CG or a misaligned incidence, and its limit is 20 % from center.
  - What to do: return the trims to mechanical neutral, check the CG and the tail incidence, and only then enable auto-trim.

## checklist
- I computed the MAC and its position for my wing (not the root chord)
- I measured S_h and l_h and computed V_h and the neutral point
- The CG is set with a 5–15 % margin (a wing: 5–10 %) and marked on the airframe
- I know why a flying wing needs reflex and how it relates to the margin
- From the polar I found (L/D)max, V_md, V_mp and compared them with V_s
- The glide test is done and C_D0 is recalculated
- I checked `PIDP.I` and the elevator output in cruise in the log

## references
- ArduPlane — Center of Gravity (PIDP.I check) | https://ardupilot.org/plane/docs/guide-center-of-gravity.html | primary | A
- ArduPilot source — ArduPlane/Parameters.cpp (PTCH_TRIM_DEG, STAB_PITCH_DOWN) | https://github.com/ArduPilot/ardupilot/blob/master/ArduPlane/Parameters.cpp | primary | A
- ArduPilot source — SRV_Channels.cpp (SERVO_AUTO_TRIM) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/SRV_Channel/SRV_Channels.cpp | primary | A
- ArduPilot source — ArduPlane/Log.cpp (CTUN fields) | https://github.com/ArduPilot/ardupilot/blob/master/ArduPlane/Log.cpp | primary | A
- MIT OCW 16.333 Aircraft Stability and Control, Lecture 2: static stability, wing/tail contributions | https://ocw.mit.edu/courses/16-333-aircraft-stability-and-control-fall-2004/resources/lecture_2/ | primary | A
- NASA Glenn — Induced drag coefficient | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/induced-drag-coefficient/ | primary | A
- INAV settings (fw_level_pitch_trim, FW_AUTOTRIM) | https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml | primary | A
- XFLR5 — analysis tool for airfoils, wings and planes at low Reynolds numbers | https://www.xflr5.tech/xflr5.htm | primary | B
- Skywalker 1830 (2015) user manual — span, wing area, CG | https://manuals.online/fpv/toy/2015-new-skywalker-1830/user-manual/26dqz | secondary | B

## notes
The NP formula without the fuselage is optimistic, so check the aft end of the CG range in flight, not only by calculation. The standard airplane model in ArduPlane SITL (`libraries/SITL/SIM_Plane.h`, the skywalker_2013 coefficients from last_letter) has Cmα = −0.7 with C_Lα = 6.9, that is about a 10 % margin without accounting for `CGOffset`. A comment in the source says that the "honest" CG offset made the model too tail heavy, so it was moved forward.
