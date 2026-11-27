---
id: ops-weather
title: "Weather and Flight Planning: Wind, Density Altitude, Cold, Icing"
level: L2
readingTime: 30 min
firmware: any
status: published
tags:
  - weather
  - wind
  - density altitude
  - planning
related:
  - ops-field
  - f-aero-props
  - f-power
  - el-battery-packs
next:
  - ops-field
source: content/foundation/ops-weather.md
source_hash: 012a9dd35b24
---

## summary
Half of all “unexplained” aircraft losses are weather that nobody calculated: the wind at 100 m is twice as strong as at the ground, heat in the mountains ate the thrust margin, a cold battery sagged on takeoff, fog coated the propellers with ice. The module gives you the calculations you do before leaving for the field: the wind profile with height and gusts, the wind limit for your aircraft, density altitude and what it does to thrust and flight time, the battery in the cold, icing conditions, reading METAR/TAF aviation reports — and brings them together into a “go / no-go” sheet with numbers.

## theory
### Wind: one thing at the ground, another aloft
- **Profile.** Friction with the ground slows the air: wind grows with height. A simple model is the power law v(h) = v₁₀·(h/10)^α, where v₁₀ is the wind at 10 m (that is how weather stations measure it), α ≈ 1/7 for open terrain, more (0.2–0.3) over forest and buildings. Example: 7 m/s at 10 m → at 100 m 7·10^(1/7) ≈ 9.7 m/s.
- **Gusts.** The mean wind is not the maximum. Reports give gusts separately (G in METAR); if there are none, allow a factor of 1.3–1.5 over the mean.
- **Mechanical turbulence.** Behind buildings, a tree line, a hill — eddies at a distance of several obstacle heights downwind. Taking off and landing on the lee side of an obstacle is the bumpiest place.
- **Thermals.** During the day, rising currents over heated ground; for light aircraft and mapping, morning and evening are better.

### The wind limit for your aircraft
- **Multicopter.** Flying into the wind, the aircraft is tilted; the stronger the wind, the greater the tilt and throttle. Rule of thumb (course guideline): gusts no more than ~50–60 % of the aircraft's maximum horizontal speed in a position-holding mode — the rest is margin for maneuvering and the return. Where the number comes from: returning into the wind needs an airspeed of about 1.5 × the wind (the same margin as in `des-sizing`), i.e. wind no more than 1 / 1.5 ≈ 67 % of maximum speed; 50–60 % leaves extra margin for a gust stronger than forecast. Check against the log: the mean tilt and throttle when hovering in wind; throttle above 65–71 % means T/W below 2, no margin for any class, and for a 5–7" 60 % is already a reason to be wary (the bands by class — in `f-physics`, “Hover throttle”).
- **Plane.** The wind must be noticeably below the cruise speed: with 15 m/s of wind and an 18 m/s cruise, the ground speed into the wind is 3 m/s, and the return will take six times longer.
- **Route planning.** Fly out into the wind, come back downwind: on the way back, when the battery is weaker, the wind helps. Calculate the return time from the ground speed into the wind if the route is the reverse.

{{diagram:chart-wind-profile|Wind with height for 10 m/s at 10 m: at 100 m the mean is ~14 m/s, gusts ×1.4 — about 20 m/s.}}

### Density altitude
A propeller's thrust is proportional to the air density ρ, and the power needed to hover at the same thrust — to 1/√ρ (from the momentum theory of the propeller, the “Propeller aerodynamics” module). Density falls with altitude and with temperature.
- **Density altitude** — the altitude in the standard atmosphere (ISA: 15 °C and 1013.25 hPa at sea level, −6.5 °C per km) at which the density is the same as now. Estimate: density altitude ≈ pressure altitude + ~36 m for every °C above the ISA temperature at that altitude.
- **Example.** A site at 2000 m, +30 °C. The ISA temperature at 2000 m is +2 °C, a deviation of +28 °C → density altitude ≈ 2000 + 28·36 ≈ 3000 m. Density is ~74 % of sea level: maximum thrust drops to ~74 %, hover power grows by ~16 %, flight time drops by about the same, and a 2:1 thrust-to-weight ratio turns into ~1.5:1.
- **What to do.** Recalculate the thrust-to-weight ratio and flight time, less payload, props with more pitch or diameter (if the motors and ESCs allow it current-wise), a larger battery margin.

{{diagram:chart-density-altitude|Maximum thrust and hover power versus density altitude (ISA): at 3000 m thrust is ~74 %, hover power ~116 %.}}

### Cold and batteries
- The internal resistance of lithium cells grows several times in the cold: under load the voltage sags more, the flight controller sees “low voltage” sooner, and the capacity actually delivered falls.
- Rules: keep batteries warm (an inside pocket, an insulated bag, a heat pack) at 20–25 °C before takeoff; the first 30–60 s — hover at low throttle while the cells warm up from their own current; do not lower the voltage warning threshold “so it stops beeping”; plan the flight time 20–30 % shorter than in summer.
- **Do not charge** LiPo when cold (below ~5–10 °C: the threshold depends on the manufacturer, Gens Ace — 10 °C, see f-power) — lithium plates on the anode, the cell degrades and becomes dangerous.
- Mechanics and electronics: thickened grease, brittle plastic, condensation when you bring a cold aircraft into the warmth — let it warm up in a closed case before powering it on.

### Icing
- Conditions: visible moisture (fog, drizzle, clouds, wet snow) and a temperature from roughly +2 to −10 °C; the most dangerous is supercooled drizzle and fog around 0 °C.
- Ice on the props builds up within minutes: thrust drops, vibration grows, the props become unbalanced; on a plane — the stall speed rises. Small UAVs without anti-icing systems do not fly in such conditions.
- The sign in a report: a temperature/dew point spread of 0–2 °C at a negative or near-zero temperature — fog and icing are likely.

### Reports: METAR and TAF
METAR is the actual weather at an aerodrome, TAF is the forecast. An example report:
```text
METAR XXXX 081230Z 27012G22KT 9999 BKN015 04/01 Q1013
```
- `27012G22KT` — wind from 270° (westerly), 12 knots, gusts 22 knots (1 knot ≈ 0.51 m/s: 6 m/s, gusts 11 m/s);
- `9999` — visibility 10 km or more; `BKN015` — broken clouds, base at 1500 feet (~450 m);
- `04/01` — temperature +4 °C, dew point +1 °C (a 3 °C spread — damp, cold, fog possible toward evening);
- `Q1013` — QNH pressure 1013 hPa (for barometric altitude).

The wind at flight altitude — from the winds-aloft forecast (weather services with a breakdown by levels, or the wind at 925 hPa ≈ 750 m) and, above all, from an anemometer at the site.

### The “go / no-go” sheet
Numbers in advance, not on site: the gust limit for the aircraft, the minimum battery temperature at takeoff, the minimum temperature/dew point spread (start — no less than 3 °C: at 0–2 °C fog and icing are likely, 3 °C is already “damp”, signs above; course guideline), visibility (visual line of sight — per your country's rules), precipitation — none. The decision is made before leaving and confirmed at the site with an anemometer.

### Place in the system

- **Receives:** the aircraft's T/W and maximum horizontal speed (`f-mechanics`, `f-components-choice`); the dependence of thrust and power on air density (`f-aero-props`); battery behavior under load (`f-power`).
- **Provides:** the “go / no-go” decision with numbers, the gust limit and the flight-time correction — to sortie planning and the briefing (`ops-field`).
- **If you get it wrong here:** the wind at the ground is taken for the wind at flight altitude → the return into the wind takes longer than calculated, the battery margin runs out before home; visible through the voltage thresholds and the battery failsafe (`f-power`, `ap-safety-fs`). A cold battery → sag on takeoff and an early “low voltage” (`f-power`). Heat in the mountains → T/W 2:1 turns into ~1.5:1, no margin for maneuvering (`f-physics`).

## practice
### Step 1. Wind profile
For the nearest weather station, take the wind at 10 m and the gusts. Calculate the wind and gusts at heights of 30, 60, 100 m for open terrain (α = 1/7) and over forest (α = 0.25). Write down a table.

### Step 2. Your aircraft's limit
From a flight log in wind (or tethered in front of a fan — roughly): the hover throttle and the mean tilt. Find the aircraft's maximum horizontal speed in a position-holding mode (documentation or a flight). Calculate the gust limit and compare it with the table from step 1: at what height you must not fly today.

### Step 3. Density altitude
For your own site (elevation, typical summer temperature) and for a trip to the mountains (2000 m, +25 °C), calculate the density altitude, the density ratio and the change in thrust-to-weight ratio and hover time of your aircraft. A script for checking:
```python
def rho(h):              # ISA, h is density altitude, m
    return 1.225 * (1 - 2.25577e-5 * h) ** 4.2559

def density_alt(field_m, oat_c):
    isa_t = 15 - 6.5 * field_m / 1000
    return field_m + 36.6 * (oat_c - isa_t)

da = density_alt(2000, 30)
r = rho(da) / 1.225
print(f"DA {da:.0f} m, ρ/ρ0 {r:.2f}, thrust {r:.0%}, hover power {1 / r ** 0.5:.0%}")
# DA 3025 m, ρ/ρ0 0.74, thrust 74%, hover power 116%
```

### Step 4. Decoding a report
Take the current METAR and TAF of the nearest aerodrome, decode them item by item, convert the wind to m/s, assess the risk of fog and icing from the temperature/dew point spread.

### Step 5. Your own “go / no-go” sheet
Fill it in for your aircraft: gust limit, battery temperature, dew point, visibility, precipitation. Attach it to the field trip checklist (the “Field operations” module).

Self-check: the lab is done when the wind-by-height table is calculated, and the formula was first checked on the example from the theory (7 m/s at 10 m → ≈ 9.7 m/s at 100 m with α = 1/7; gusts — from the report or ×1.3–1.5 over the mean); your aircraft's gust limit is derived as 50–60 % of its maximum horizontal speed and confirmed by a log (hover throttle in wind below ~70 %); the density altitude and thrust loss are calculated for two cases, and the script on the reference 2000 m and +30 °C prints `DA 3025 m, ρ/ρ0 0.74, thrust 74%, hover power 116%`; the report is decoded by the same items as the METAR example (wind and gusts in m/s, visibility, clouds, temperature and dew point, pressure), and a conclusion about fog and icing is written down from the temperature/dew point spread; every line of the “go / no-go” sheet has a number in it.

## diagnostics
- **Symptom:** it is calm at the ground, but at altitude the aircraft cannot get back
  - Possible cause: the wind grows with height, the limit was calculated from the wind at the ground.
  - What to do: calculate the limit from the wind at the working altitude, fly out into the wind, descend for the return.
- **Symptom:** in the mountains the aircraft is sluggish and drains the battery fast
  - Possible cause: a high density altitude — less thrust, more power to hover.
  - What to do: recalculate the thrust-to-weight ratio and flight time, remove payload, props suited to the density.
- **Symptom:** in winter, a voltage warning right after takeoff
  - Possible cause: a cold battery, high internal resistance.
  - What to do: warm it to 20–25 °C, hover at low throttle at the start, a shorter flight.
- **Symptom:** in fog, vibration grows and thrust drops
  - Possible cause: prop icing.
  - What to do: land immediately; do not fly in visible moisture around 0 °C.
- **Symptom:** bumpiness on takeoff and landing in moderate wind
  - Possible cause: turbulence behind an obstacle.
  - What to do: move the takeoff point to the windward side or several obstacle heights away.

## references
- WMO — Manual on Codes (METAR/TAF code forms) | https://library.wmo.int/idurl/4/35713 | primary | A
- NOAA Aviation Weather Center — decoded METAR/TAF | https://aviationweather.gov/data/metar/ | primary | A
- NASA — Earth Atmosphere Model (standard atmosphere) | https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html | primary | B
- FAA — Pilot's Handbook of Aeronautical Knowledge (Weather Theory, Density Altitude) | https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak | primary | A

## checklist
- I calculate the wind at the working altitude from the wind at 10 m and account for gusts
- I know my aircraft's wind limit and plan the route into the wind
- I calculate density altitude and its effect on thrust and flight time
- I prepare batteries for the cold and do not charge them cold
- I recognize icing and fog conditions from a report
- I read METAR and TAF and fill in the “go / no-go” sheet
