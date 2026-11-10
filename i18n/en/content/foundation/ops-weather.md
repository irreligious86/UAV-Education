---
id: ops-weather
title: "Weather and flight planning: wind, density altitude, cold, icing"
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
source_hash: 1526d548a576
---

## summary
Half of all “unexplained” aircraft losses are weather nobody did the math on: the wind at 100 m is twice as strong as at the ground, heat in the mountains ate the thrust margin, a cold battery sagged on takeoff, fog coated the propellers with ice. This module gives you the calculations you do before you leave for the field: the wind profile with height and gusts, the wind limit for your own aircraft, density altitude and what it does to thrust and flight time, batteries in the cold, icing conditions, reading METAR/TAF aviation reports — and pulls them together into a “go / no-go” sheet with numbers.

## theory
### Wind: one thing at the ground, another at height
- **Profile.** Friction with the ground slows the air down: wind increases with height. A simple model is the power law v(h) = v₁₀·(h/10)^α, where v₁₀ is the wind at 10 m (that's where weather stations measure it), α ≈ 1/7 for open terrain, more (0.2–0.3) over forest and buildings. Example: 7 m/s at 10 m → at 100 m 7·10^(1/7) ≈ 9.7 m/s.
- **Gusts.** The mean wind is not the maximum. Reports give gusts separately (G in METAR); if they are missing, assume a factor of 1.3–1.5 over the mean.
- **Mechanical turbulence.** Behind buildings, tree lines or a hill there are eddies extending downwind for several obstacle heights. Takeoff and landing on the downwind side of an obstacle is the bumpiest place.
- **Thermals.** During the day, rising air over heated ground; for light aircraft and mapping, morning and evening are better.

### The wind limit for your aircraft
- **Multicopter.** Flying into the wind, the aircraft is tilted; the stronger the wind, the more tilt and throttle. A practical rule: gusts no more than ~50–60 % of the aircraft's maximum horizontal speed in a position-hold mode — the rest is margin for maneuvering and returning. Check it in the log: average tilt and throttle while hovering in the wind; a hover throttle above ~70 % means there is no margin.
- **Plane.** The wind must be noticeably below cruise speed: with a 15 m/s wind and an 18 m/s cruise, the ground speed into the wind is 3 m/s, and the return takes six times longer.
- **Route planning.** Fly out into the wind, come back downwind: on the way back, when the battery is weaker, the wind helps. If the route is the reverse, calculate the return time using the ground speed into the wind.

{{diagram:chart-wind-profile|Wind versus height for 10 m/s at 10 m: at 100 m the mean is ~14 m/s, gusts ×1.4 — about 20 m/s.}}

### Density altitude
Propeller thrust is proportional to air density ρ, and the power needed to hover at the same thrust is proportional to 1/√ρ (from momentum theory, module “Propeller aerodynamics”). Density drops with altitude and with temperature.
- **Density altitude** is the altitude in the standard atmosphere (ISA: 15 °C and 1013.25 hPa at sea level, −6.5 °C per km) at which the density is the same as it is now. Estimate: density altitude ≈ pressure altitude + ~36 m for every °C above the ISA temperature at that altitude.
- **Example.** A site at 2000 m, +30 °C. The ISA temperature at 2000 m is +2 °C, the deviation is +28 °C → density altitude ≈ 2000 + 28·36 ≈ 3000 m. Density is ~74 % of sea level: maximum thrust drops to ~74 %, hover power rises by ~16 %, flight time drops by roughly the same amount, and a 2:1 thrust-to-weight ratio turns into ~1.5:1.
- **What to do.** Recalculate thrust-to-weight and flight time, carry less payload, use props with more pitch or diameter (if the motors and ESCs can handle the current), keep a larger battery reserve.

{{diagram:chart-density-altitude|Maximum thrust and hover power versus density altitude (ISA): at 3000 m thrust is ~74 %, hover power ~116 %.}}

### Cold and batteries
- The internal resistance of lithium cells rises several-fold in the cold: under load the voltage sags more, the flight controller sees “low voltage” earlier, and the capacity actually delivered drops.
- Rules: keep the batteries warm (inside pocket, insulated bag, hand warmer) at 20–25 °C before takeoff; for the first 30–60 s hover at low throttle while the cells warm up from their own current; do not lower the voltage warning threshold “so it stops beeping”; plan flight time 20–30 % shorter than in summer.
- **Do not charge** LiPo cold (below ~5–10 °C) — lithium plates onto the anode, the cell degrades and becomes dangerous.
- Mechanics and electronics: thickened grease, brittle plastic, condensation when you bring a cold aircraft into the warmth — let it warm up in a closed case before powering it on.

### Icing
- Conditions: visible moisture (fog, drizzle, clouds, wet snow) and a temperature of roughly +2 to −10 °C; the most dangerous is supercooled drizzle and fog around 0 °C.
- Ice on the props builds up within minutes: thrust drops, vibration rises, the props become unbalanced; on a plane, the stall speed rises. Small UAVs without ice protection systems do not fly in these conditions.
- What to look for in a report: a temperature/dew point spread of 0–2 °C at a temperature below or near zero — fog and icing are likely.

### Reports: METAR and TAF
METAR is the actual weather at an airfield, TAF is the forecast. An example report:
```text
METAR XXXX 081230Z 27012G22KT 9999 BKN015 04/01 Q1013
```
- `27012G22KT` — wind from 270° (westerly), 12 knots, gusts 22 knots (1 knot ≈ 0.51 m/s: 6 m/s, gusts 11 m/s);
- `9999` — visibility 10 km or more; `BKN015` — broken clouds, base at 1500 feet (~450 m);
- `04/01` — temperature +4 °C, dew point +1 °C (a 3 °C spread — humid, cold, fog possible toward evening);
- `Q1013` — QNH pressure 1013 hPa (for barometric altitude).

The wind at flight altitude comes from a winds-aloft forecast (weather services with a breakdown by level, or the wind at 925 hPa ≈ 750 m) and, above all, from an anemometer at the site.

### The “go / no-go” sheet
Numbers set in advance, not on the spot: the gust limit for the aircraft, the minimum battery temperature at takeoff, the minimum temperature/dew point spread, visibility (visual line of sight — per your country's rules), precipitation — none. The decision is made before you leave and confirmed at the site with the anemometer.

## practice
### Step 1. Wind profile
For the nearest weather station, take the wind at 10 m and the gusts. Calculate the wind and gusts at 30, 60 and 100 m for open terrain (α = 1/7) and over forest (α = 0.25). Write down a table.

### Step 2. Your aircraft's limit
From a log of a flight in the wind (or tethered in front of a fan — roughly): hover throttle and average tilt. Find the aircraft's maximum horizontal speed in a position-hold mode (documentation or a flight). Calculate the gust limit and compare it with the table from step 1: at what altitude you can't fly today.

### Step 3. Density altitude
For your site (elevation, typical summer temperature) and for a trip to the mountains (2000 m, +25 °C), calculate the density altitude, the density ratio, and the change in thrust-to-weight and hover time of your aircraft. A script to check:
```python
def rho(h):              # ISA, h — density altitude, m
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
Take the current METAR and TAF for the nearest airfield, decode them item by item, convert the wind to m/s, and estimate the risk of fog and icing from the temperature/dew point spread.

### Step 5. Your own “go / no-go” sheet
Fill it in for your aircraft: gust limit, battery temperature, dew point, visibility, precipitation. Attach it to your field trip checklist (module “Field operations”).

The lab counts as done when the wind-by-height table is calculated, your aircraft's gust limit is backed by a log, density altitude and thrust loss are calculated for two cases, the report is decoded, and the “go / no-go” sheet is filled in with numbers.

## diagnostics
- **Symptom:** calm at the ground, but at altitude the aircraft can't make it back
  - Possible cause: wind increases with height, the limit was based on the wind at the ground.
  - What to do: base the limit on the wind at working altitude, fly out into the wind, descend for the return.
- **Symptom:** in the mountains the aircraft is sluggish and drains the battery quickly
  - Possible cause: high density altitude — less thrust, more power needed to hover.
  - What to do: recalculate thrust-to-weight and flight time, remove payload, use props suited to the density.
- **Symptom:** in winter, a voltage warning right after takeoff
  - Possible cause: a cold battery, high internal resistance.
  - What to do: warm it to 20–25 °C, hover at low throttle at the start, shorter flights.
- **Symptom:** in fog, vibration rises and thrust drops
  - Possible cause: prop icing.
  - What to do: land immediately; do not fly in visible moisture around 0 °C.
- **Symptom:** bumpy takeoff and landing in moderate wind
  - Possible cause: turbulence behind an obstacle.
  - What to do: move the takeoff point to the upwind side or several obstacle heights away.

## references
- WMO — Manual on Codes (METAR/TAF code forms) | https://library.wmo.int/idurl/4/35713 | primary | A
- NOAA Aviation Weather Center — decoded METAR/TAF | https://aviationweather.gov/data/metar/ | primary | A
- NASA — Earth Atmosphere Model (standard atmosphere) | https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html | primary | B
- FAA — Pilot's Handbook of Aeronautical Knowledge (Weather Theory, Density Altitude) | https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak | primary | A

## checklist
- I calculate the wind at working altitude from the 10 m wind and account for gusts
- I know my aircraft's wind limit and plan the route into the wind
- I calculate density altitude and its effect on thrust and flight time
- I prepare batteries for the cold and never charge them cold
- I recognize icing and fog conditions from a report
- I read METAR and TAF and fill in the “go / no-go” sheet
