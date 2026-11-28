---
id: per-fpv-footage
title: "Filming with FPV: action camera, ND filters, Gyroflow and DVR"
level: L2
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5) · Gyroflow 1.7 (documentation as of November 2026)
status: published
added: 2026-11-22
tags:
  - filming
  - action camera
  - ND filter
  - Gyroflow
  - DVR
  - vibration
related:
  - bf-blackbox
  - bf-filters
  - f-frame-mech
  - link-digital-video
  - link-vtx
  - bf-hd-osd-video
  - ops-field
  - el-emi
  - f-aero-props
  - f-regulations
next:
  - ops-field
source: content/companion/per-fpv-footage.md
source_hash: a0b59a81d180
---

## summary
The picture in your goggles is a control channel, not footage: an analog DVR records a standard-definition frame with interference, a digital one records whatever made it through the radio. For a video you need a separate recording: an action camera, or the onboard recording of a digital video unit. The module covers camera classes with their mass and what that mass costs in flight time, stabilization in the camera and in Gyroflow (the camera's gyro or the flight controller's Blackbox), exposure through shutter angle and ND filters with stop counting, vibration and "jello", camera tilt versus speed, DVR for crash analysis and searching, memory cards and camera power. After the module you can choose a camera, a filter and settings for the task, and find the cause of a defect from a description of the footage. The practice is computational: exposure, recording size, tilt geometry, and the analysis of four defects.

## theory
### Three recordings and what each is for
| Recording | Where it is written | What is in it | What it is for |
|---|---|---|---|
| Goggle DVR (analog) | the SD card in the goggles or in the receiver module | a PAL 576 / NTSC 480 line frame after the radio: snow, breakups, OSD | flight review, search: the last frame and the coordinates in the OSD |
| Goggle DVR (digital) | the goggles (HDZero: only there; DJI O4: per the `Record With` setting) | what made it through the radio, with OSD | the same; you can see where the link degraded |
| Onboard recording on the video unit | the unit's internal memory or microSD (DJI O3/O4, Walksnail) | the camera frame without radio losses, without OSD | crash analysis, a mid-quality video |
| Action camera | its own microSD | 4K, 10-bit on higher-end models, a gyro for Gyroflow | the video |

The main consequence: the onboard recording stays on board. If the aircraft is lost, only what was recorded in the goggles and on the radio helps you find it (`ops-field`). Power-on order, heating and recording for each system are in `bf-hd-osd-video`, and the comparison of systems is in `link-digital-video`.

### Camera classes and what they cost the aircraft
Camera mass is flight time and tune. An estimate from disk theory (`f-aero-props`): hover power grows as m^1.5, so with the same battery the hover time is t ∝ m^−1.5. For a 5" weighing 600 g without a camera:

| Class | Example (manufacturer's mass) | Price, as of November 2026 | Gyro for Gyroflow | Hover time, share of "no camera" |
|---|---|---|---|---|
| Full-size action camera | GoPro HERO13 Black 159 g with battery; DJI Osmo Action 5 Pro 146 g | ~$300–500 (estimate, not verified) | yes (HERO 8+ even with HyperSmooth; DJI with EIS off) | 0.70 (+159 g) |
| 360° | Insta360 X5 200 g, 8K30, up to 180 Mbit/s | not verified | no (Gyroflow does not support 360°; stabilization is in the manufacturer's app) | 0.65 (+200 g) |
| "Naked" GoPro (housing removed, powered from the flight battery) | Flywoo Naked V1/V2 based on HERO9–12: 45/49 g; GoPro HERO10 Bones 54 g, 5–27 V | $350–590 (Flywoo, Oscar Liang review) | yes, the same electronics | 0.90 (+45 g) |
| Lightweight FPV camera | RunCam Thumb 2 27.8 g, 4K60 100 Mbit/s, 5 V only, up to 0.7 A | ~$99 (review) | yes, a separate .gcsv file | 0.93 (+28 g) |
| Magnetic mini camera | Insta360 GO 3S 39.1 g, 4K30, 120 Mbit/s | not verified | yes | 0.91 (+39 g) |
| Onboard recording on the video unit | DJI O4 Pro ≈32 g (camera + unit), 4K120, 130 Mbit/s; O4 ≈8.2 g, 4K60, 100 Mbit/s; Walksnail HD Pro 1080p60, 32 GB of internal memory | O4 Pro $229 (Adorama, November 22, 2026); Walksnail HD Pro kit $159 (caddxfpv) | yes, but the O3/O4 camera must be soft-mounted, or you need Optical correction | replaces the FPV camera and VTX, adds almost nothing |

Mass is not only time. A camera on top at the front raises the center of mass and moves it forward, and increases the pitch moment of inertia: the same PID gives a different response, and the rear pair of motors is unloaded. After fitting a heavy camera, record a Blackbox log and check the tune (`bf-pid`, `bf-blackbox`), just as after changing the battery. A "naked" GoPro loses the housing's protection and the built-in battery (which is needed for firmware updates), and overheating is a frequent complaint about such builds (per the Flywoo V2 review, the metal front helps).

### Stabilization: in the camera or in Gyroflow
**In the camera** (HyperSmooth on GoPro, RockSteady on DJI) it is electronic: the frame is cropped and shifted by the gyro in real time. The upside: a finished file. The limits: the crop is chosen once and for all, the algorithm sees only the past, and the horizon is not held in every mode (on the Osmo Action 5 Pro, HorizonSteady is 1080p/2.7K up to 60 fps only, HorizonBalancing up to 4K 60 fps; on the HERO13 Black, in-camera Horizon Leveling is not available in every mode). Sharp FPV flips and vibration are the worst case for any EIS.

**Gyroflow** (GPLv3, Windows/Linux/macOS/Android/iOS, plugins for DaVinci Resolve, Premiere, Final Cut) stabilizes after the flight from the recorded gyro. What it needs:
- **Motion data.** The camera's gyro in the file (GoPro HERO 5+, but HERO5 and HERO7 are marked "Bad on FPV drone"; HERO 8+ can shoot with HyperSmooth on; DJI Avata/O3/O4/Action 4–6 need EIS off and FOV Wide, otherwise the gyro is not recorded; Insta360 GO/Ace: on some models, FreeFrame mode) or an external log: Betaflight/INAV Blackbox (`.bbl`, `.bfl`, `.csv`) and ArduPilot logs (`.bin`, `.log`). No gyro: Optical correction (since 1.7.0) estimates the motion from the pixels, which is worse.
- **A lens profile.** Built-in official profiles for GoPro, DJI, Sony, Insta360, RunCam Thumb/5 Orange; HERO11+ writes its calibration into the file. For your own camera, a chessboard calibration.
- **Synchronization.** Not needed for the camera's gyro (GoPro 8+, DJI, Insta360). Needed for a flight controller log: Gyroflow compares the motion from the log with the video's optical flow; 2–3 points on stretches with motion in all axes are usually enough, and all the points should have similar offsets.
- **Camera tilt.** In a flight controller log the gyro is in the frame axes while the camera is tilted: the angle goes into Motion data → Rotation → Pitch (up is positive, 30° → `30`). An error of a few degrees causes drift and a "rocking" horizon.
- **Rolling shutter.** You need the Frame readout time value; for GoPro, DJI, Insta360 and Sony it is filled in automatically. Changing the value requires resynchronization.
- **Smoothing and horizon.** The Default algorithm suits 99.5 % of cases according to the documentation; Smoothness 0–1, default 0.5; Horizon lock holds the horizon and needs a larger crop; FOV 1.0 with Dynamic zoom uses the most pixels.

The workflow: load the video → check the lens profile → motion data (from the file or the FC log) → tilt → synchronization → smoothing, horizon → export, or a project in the editor through the plugin.

What to log in Blackbox for Gyroflow (Betaflight 2025.12): the Gyroflow documentation suggests starting with 250 Hz, `debug_mode = NONE` and the "Gyroflow logger" preset from the gyroflow-betaflight preset source (the Presets tab); unneeded fields are turned off with `blackbox_disable_*` (`bf-blackbox`). Log rate = PID rate × `blackbox_sample_rate`; the values are 1/1…1/16, default 1/4 (`cli/settings.c:292–294`, `blackbox/blackbox.c:111`; the list is the same as in 4.5). At 8 kHz the minimum is 500 Hz; 250 Hz comes from 4 kHz and 1/16. A camera whose gyro is logged by the flight controller must move together with it: on a soft mount the camera's relative motion is not visible in the log.

{{diagram:footage-gyroflow-paths|Three paths into Gyroflow: the camera's gyro in the file, no synchronization; a flight controller log, with synchronization and the camera tilt entered; no gyro, a motion estimate from the pixels.}}

### Exposure: shutter angle, ND and stops
Shutter speed from shutter angle: t = (angle / 360) / fps. The 180° rule is t = 1/(2·fps): 1/48 s at 24 fps, 1/120 s at 60. The eye perceives that amount of motion blur as smooth "cinema"; a smaller angle makes motion choppy, a larger one smears it.

An action camera has no adjustable aperture (f/2.5 on the HERO13, f/2.8 on the Action 5 Pro), so in sunlight it goes to a short shutter speed, 1/5000 s and shorter. ND filters cut the light: ND-N passes 1/N of the light, which is log2 N stops (the optical density is lg N):

| Filter | Transmits | Stops | Density |
|---|---|---|---|
| ND4 | 25 % | 2 | 0.6 |
| ND8 | 12.5 % | 3 | 0.9 |
| ND16 | 6.25 % | 4 | 1.2 |
| ND32 | 3.125 % | 5 | 1.5 |
| ND64 | 1.56 % | 6 | 1.8 |

Counting stops. Scene brightness is the EV at ISO 100 (bright sun ≈ 15, the "sunny 16" rule). The unfiltered shutter speed at ISO 100: t₀ = N²/2^EV. Stops needed: n = log2(t / t₀). Take a filter with k ≥ n stops (round up), and make up the extra k − n stops with ISO: ISO = 100·2^(k−n). The camera cannot go below its base ISO, so rounding down means overexposure or a shorter shutter speed.

When you do **not** need ND. The Gyroflow documentation says it plainly: motion blur cannot be removed from the frame, and after stabilization it remains in the direction of the original motion: the shake of the frame is gone, but the blur "shakes". The 180° rule works only with smooth flying; for FPV with strong stabilization 90° or even 45° is better, with blur added in the edit. Bottom line: for Gyroflow, a filter 1–2 stops weaker or none; for 180°, only smooth cinematic flying.

{{diagram:chart-footage-nd|ND stops at 60 fps and f/2.5: in sunlight (EV 15) 180° needs 5.45 stops, so ND64 with ISO 146, and 90° for Gyroflow needs one stop less; in overcast weather (EV 12) ND8 is enough.}}

### Other camera settings
| Setting | Choice | Why |
|---|---|---|
| Exposure | shutter fixed (by angle), auto ISO with an upper limit | auto shutter "breathes" between sky and ground and changes the blur from frame to frame |
| White balance | fixed (5500 K in daylight) | auto WB changes color when the scene changes; Gyroflow recommends a fixed one for RunCam |
| Resolution | full sensor 4:3 / 8:7 (GoPro), 4K | Gyroflow crops: spare pixels are spare stabilization; 16:9 allows higher frame rates |
| Frame rate | 4K60 for a normal video; 2.7K120 or 4K120 for 4–5× slow motion | 60 gives a 1/120 shutter and smoothness after stabilization; 120 → slow motion at 24/30 |
| Bitrate | the maximum (HERO13 up to 120 Mbit/s, O4 Pro 130) | compression destroys grass and foliage in motion |
| Color | 10-bit and a log profile (D-Log M on the O4 Pro) only if you will grade; otherwise standard | ungraded log looks gray; on cheap cameras "Flat" only compresses the range (Gyroflow, RunCam: "doesn't actually provide more dynamic range") |
| In-camera stabilization | off for DJI and RunCam under Gyroflow; on GoPro 8+ it can stay on | otherwise there is no gyro in the file (DJI) or the stabilization is doubled |

Flicker: light from a 50 Hz mains pulses at 100 Hz (60 Hz → 120 Hz). A shutter speed that is a multiple of the pulse period (1/100 or 1/50 s on 50 Hz) removes the bands; at 60 fps on 50 Hz mains a 1/120 shutter flickers, so shoot 50 fps at 1/100.

### Vibration and "jello"
An action camera sensor reads the frame line by line (rolling shutter): the top and bottom of the frame are captured at different moments. If the camera vibrates with a period comparable to the readout time, straight lines bend and "wobble": that is jello. Causes, roughly from highest frequency down: unbalanced or bent props, a bent motor shaft or a worn bearing, frame resonance, a camera mount that is too stiff or, on the contrary, loose (`f-frame-mech`). Flight controller filters do not cure jello: they clean the gyro signal for the PID, they do not make the camera shake less (`bf-filters`, "What filters do not fix").

Diagnosis from two sources. From the footage: jello at all throttle levels means camera and mount mechanics; only at a certain throttle means resonance; appeared after a crash means a prop or a shaft. From Blackbox: a peak in the `gyroUnfilt` spectrum at the motor rotation frequency (revolutions per second) means imbalance; broadband noise means bearings. A special case is DJI O3/O4: the Gyroflow documentation requires a soft camera mount (or Optical correction), because the light unit picks up motor noise, and 24 kHz ESC PWM interferes with the IMU sampling rate; 48 kHz and above helps (`f-esc-firmware`). Some O4 Pro units made in 2026 have a different gyro (ICM-40609-D), which reports nonexistent motion under vibration; a soft mount does not help.

The mount: a TPU holder is a compromise between damping high frequencies and swaying at low ones. Too soft a holder gives a slow "floating" of the frame that Gyroflow cannot see from the flight controller's gyro.

### Camera tilt and speed
In level flight at constant speed, thrust balances weight and drag, so tan θ = D/W, and drag D ∝ v². A simplified model: if at speed v₀ the aircraft flies with tilt θ₀ (from Blackbox or the OSD), then tan θ(v) = tan θ₀ · (v/v₀)². A camera tilted up by α looks at an angle α − θ above the horizon; the horizon in the frame sits θ − α from the center. At α = θ the camera looks exactly along the flight path. Example: θ₀ = 30° at 20 m/s → at 10 m/s θ = 8.2°, at 25 m/s θ = 42.1°. With a 30° camera: in a hover the horizon is 30° below center, at 20 m/s it is centered, at 25 m/s it is 12° above. Hence the typical angles: an indoor cinewhoop 0–10°, cinematic on a 5" 15–30°, fast freestyle and racing 30–45°. The action camera is set to the same tilt as the FPV camera, or a few degrees lower so the video does not end up in the sky; with a flight controller log, Gyroflow must know this angle.

Props in the frame come from a wide field of view and a low mounting position: move the camera forward, raise it, choose a narrower lens mode, or crop. The props are fixed relative to the camera, so after stabilization they "slide" around the frame: they have to be taken out of the frame, not stabilized.

### Memory cards, power, interference
Size: MB/s = Mbit/s / 8. 120 Mbit/s is 15 MB/s, 0.9 GB per minute, 3.6 GB for a 4-minute flight. The card must sustain at least the stream rate with a margin: class V30 guarantees 30 MB/s of sequential writing (V60 60, V90 90; SD Association), which covers 120–130 Mbit/s with a twofold margin; V10 (10 MB/s) does not. V30/U3 cards are recommended for the HERO13 and the Osmo Action 5 Pro. The O4 Pro has 4 GB built in, which at 130 Mbit/s is about 4 minutes, so you need a microSD; the O4 has 23 GB of internal memory and no slot.

Power. A full-size camera runs on its own battery (HERO13: 1900 mAh) and is independent of the aircraft. A "naked" GoPro and the HERO10 Bones run from the flight battery (2S–6S); the RunCam Thumb 2 takes 5 V only, up to 0.7 A, which is 3.5 W on the flight controller's BEC, so check its headroom (`el-power-design`). The camera's power wire is another path for interference into analog video (a ground loop, `el-emi`). An action camera's Bluetooth (and 2.4 GHz Wi-Fi) radiates next to the receiver, and its electronics sit next to the GPS: compare GPS C/N0 with the camera on and off (`el-emi`), and turn the wireless functions off in flight.

### Law and privacy
Filming people and private property is regulated separately from flying and differs by country; what to check in your own rules is in `f-regulations`. This module introduces no new legal facts.

### Choosing for the task
| Task | Camera | ND and shutter | Mode | Stabilization | Check afterwards |
|---|---|---|---|---|---|
| (a) Learning freestyle | onboard recording on the video unit or a lightweight camera | no ND; auto shutter is acceptable | 1080p–4K60 | in the camera or none | goggle DVR and the onboard file, for crash analysis; props in the frame |
| (b) Cinematic on a 5" | a "naked" GoPro or a HERO 8+ | smooth flying: 180° with ND per the calculation; aggressive: 90° and a filter one stop weaker | 4K60, full sensor, 10-bit, fixed WB | Gyroflow from the camera gyro | jello, the horizon after Gyroflow, the tune after +45–159 g |
| (c) Indoor cinewhoop | O4 Pro or a lightweight camera | no ND; shutter 1/100 (50 Hz mains) or 1/120 (60 Hz) | 50 or 60 fps per the mains | Gyroflow; on the O4, a soft mount or Optical correction | flicker, ISO noise, prop guards in the frame |
| (d) Long-range flight | a lightweight 5 V camera or onboard recording | ND8–16 for 180°, since the flying is smooth | 2.7K–4K30/60, card capacity for the duration | Gyroflow with horizon lock | GPS C/N0 with and without the camera, whether the card is big enough, OSD coordinates in the goggle DVR |

### Where it fits
- **Takes in:** the frame mechanics and prop balancing (`f-frame-mech`), on which jello depends; the flight controller's gyro log (`bf-blackbox`) for Gyroflow; 5 V power from a BEC (`el-power-design`); the onboard recording and the DVR from the video system (`link-digital-video`, `bf-hd-osd-video`).
- **Hands off:** the mass and the center-of-mass shift, to the tune (`bf-pid`) and the flight time (`f-aero-props`); the DVR with OSD coordinates, to the search for a downed aircraft (`ops-field`); the onboard recording, to crash analysis.
- **If you get this wrong:** a 159 g GoPro without rechecking the tune → pitch oscillations and hot motors show up in Blackbox (`bf-pid`); the camera's Wi-Fi and its power next to the GPS → C/N0 drops and GPS Rescue misbehaves (`el-emi`); onboard recording instead of the goggle DVR → after losing the aircraft there is no last frame to search with (`ops-field`).

## practice
The practice is computational: you need neither a camera nor an aircraft. The input data is given in the problems; the formulas are from the theory section. The camera in all steps: f/2.5, minimum ISO 100, filters ND2…ND64.

### Step 1. Exposure: shutter speed and filter
For each row, find the shutter speed t = (angle/360)/fps, the unfiltered shutter speed t₀ = 6.25/2^EV, the number of stops n = log2(t/t₀), the filter (rounding up) and the ISO.

| Scene | EV | fps | Angle | t | n | Filter | ISO |
|---|---|---|---|---|---|---|---|
| A: sun, cinematic | 15 | 60 | 180° | 1/120 | 5.45 | ND64 | 146 |
| B: overcast | 12 | 60 | 180° | 1/120 | 2.45 | ND8 | 146 |
| C: sun, Gyroflow | 15 | 60 | 90° | 1/240 | 4.45 | ND32 | 146 |
| D: heavy overcast | 10 | 60 | 180° | 1/120 | 0.45 | ND2 or none | 146 / — |
| E: sun, slow motion | 15 | 120 | 180° | 1/240 | 4.45 | ND32 | 146 |

Analysis of A: t₀ = 6.25/32768 = 1/5243 s; 5243/120 = 43.7; log2 43.7 = 5.45. ND32 gives 5 stops, 0.45 stop short, and ISO cannot go below 100, so you get overexposure or a 1/164 s shutter (132°). ND64 gives 6 stops, and ISO makes up the extra 0.55 stop: 100·2^0.55 = 146. Analysis of D: without a filter at ISO 100 the shutter is 1/164 s (132°), which for a Gyroflow video is a good result even without ND. Work out scene F yourself: EV 13, 30 fps, 180°; you should get t = 1/60, n = 4.45, ND32, ISO 146.

### Step 2. Card and recording size
A session: 6 batteries of 4 minutes each, 4K60 at 120 Mbit/s. The stream is 120/8 = 15 MB/s; per flight 15·240 = 3600 MB = 3.6 GB; per session 21.6 GB, so a 64 GB card with room to spare, class V30 (30 MB/s, twice the stream). The same on the O4 Pro at 130 Mbit/s: 16.25 MB/s, 3.9 GB per flight; the built-in 4 GB lasts 4000/16.25 = 246 s ≈ 4.1 minutes, just one flight. Blackbox for Gyroflow: per the `bf-blackbox` estimate, 2 kHz with the full set of fields is 60–100 KB/s; at 250 Hz that is 7.5–12.5 KB/s, and 16 MB of flash lasts 21–36 minutes. Work it out yourself: 128 GB at 120 Mbit/s is how many hours? Answer: 2.37 h.

### Step 3. Camera tilt versus speed
Given: per Blackbox, the aircraft flies at 20 m/s with a tilt of θ₀ = 30°. With the model tan θ = tan 30° · (v/20)² we get: 10 m/s → 8.2°, 15 m/s → 18.0°, 25 m/s → 42.1°. A camera tilted at 30° with a 70° vertical field of view (35° half-angle): in a hover the horizon is 30° below center (at the very bottom edge of the frame), at 20 m/s it is centered, at 25 m/s it is 12.1° above center. To have the horizon centered at 25 m/s you need a tilt of ≈ 42°; at 40° it is 2.1° above center. Work out θ for 30 m/s yourself: 52.4°.

### Step 4. Four defects
For each description, name the cause and the fix:
1. Poles and the horizon line bend in a wave, worse at full throttle; after landing, the props have nicks.
2. After Gyroflow from Blackbox, the horizon slowly tilts in turns and "rocks"; the camera is at 25°, Rotation → Pitch was left at 0; two of the three sync points give similar offsets, the third is far off.
3. A cinewhoop in a gym, 50 Hz mains, 60 fps, a 1/120 shutter: dark bands crawl across the frame.
4. The video was shot with ND32 at 180° and run through Gyroflow with heavy smoothing: the picture is steady, but the trees "shake" with blur.

### Moving to real hardware
Props off while you fit the camera and check the mount and the power. Weigh the aircraft with and without the camera, record the difference and the hover-time share from t ∝ m^−1.5. The first flight with the camera is a hover and a smooth circle with Blackbox, then compare the `gyroUnfilt` spectrum and the motor outputs with the previous log (`bf-blackbox`). Turn the camera and its recording on before arming; format the card in the camera. The hardware criterion: the log entry has the mass, the camera tilt, the filter and the shutter speed, and in Gyroflow the video from this flight is synchronized with 2–3 points with similar offsets.

Self-check: the lab is done when: (1) in step 1 for A–E you get t, n and the filter from the table, and for F t = 1/60 s, n = 4.45 ± 0.02, ND32, ISO 146 ± 2; (2) in step 2: 3.6 GB per flight, 21.6 GB per session, class V30, 4.1 ± 0.1 minutes in the O4 Pro's built-in memory, and 2.37 ± 0.02 h for 128 GB; (3) in step 3: θ(30 m/s) = 52.4 ± 0.2°, and the horizon at 25 m/s with a 30° tilt is 12.1 ± 0.2° above center; (4) in step 4, each of the four situations is matched with a cause and a fix that agree with the reference below. Items 1–4 need no hardware; the hardware path adds a log entry for the first flight with the camera.

**Reference answer for self-check.**

| Defect | Cause | Fix |
|---|---|---|
| 1. A wave on straight lines | jello: vibration from damaged props + rolling shutter | new props, check the shafts, a soft camera mount; Gyroflow will not remove it |
| 2. A tilting and rocking horizon | the 25° tilt was not entered in Rotation → Pitch; one sync point contradicts the other two | enter 25, delete the contradicting point, resynchronize on stretches with motion |
| 3. Bands | 1/120 s is not a multiple of the 1/100 s light pulse period | 50 fps with 1/100 or 1/50 s |
| 4. Shaking blur | 180° under strong stabilization: the blur stays in the direction of the original motion | 90° or 45°, a filter 1–2 stops weaker; add blur in the edit |

Common mistakes in step 1: choosing ND32 for scene A because 5.45 was "rounded" down, so the result is overexposed by 0.45 stop; or computing t = 1/60 for 60 fps by mixing up 360° and 180°. In step 2 the common mistake is taking 120 Mbit/s for 120 MB/s, which makes the size 8 times larger. In step 3, using v/v₀ without the square: at 25 m/s that gives 35.8° instead of 42.1°.

## diagnostics
- **Symptom:** jello: straight lines bend in a wave
  - Possible cause: a damaged or unbalanced prop, a bent shaft, a bearing; the camera rigidly mounted to the frame; on DJI O3/O4, 24 kHz ESC PWM interfering with the IMU sampling.
  - What the log shows: a `gyroUnfilt` peak at the motor rotation frequency, or broadband noise.
  - What to do: replace the props, check the shafts and balance (`f-frame-mech`), a TPU mount; for O3/O4, a soft mount or Optical correction, ESC PWM at 48 kHz or higher.
- **Symptom:** after Gyroflow the horizon drifts or the frame "rocks"
  - Possible cause: the camera tilt was not entered for a flight controller log; a wrong IMU orientation; contradicting sync points; settings changed after synchronization.
  - What to do: enter the tilt in Rotation → Pitch, delete the outlying point, resynchronize with 2–3 points on stretches with motion.
- **Symptom:** Gyroflow cannot find the gyro in a DJI file
  - Possible cause: RockSteady/EIS is on, or FOV is not Wide.
  - What to do: turn EIS off, FOV Wide; for footage already shot, Optical correction.
- **Symptom:** the blur "shakes" after stabilization
  - Possible cause: a long shutter (180° and ND) with heavy smoothing.
  - What to do: 90° or 45°, a weaker ND or none.
- **Symptom:** bands and flicker indoors
  - Possible cause: the shutter speed is not a multiple of the light pulse period (100 Hz on 50 Hz mains).
  - What to do: 1/100 or 1/50 s, a frame rate of 50.
- **Symptom:** the recording stops or frames are dropped
  - Possible cause: the card is slower than the stream (V10 at 120 Mbit/s), the built-in memory is full (4 GB on the O4 Pro), overheating.
  - What to do: V30 or faster, calculate the size per session, cooling airflow on the ground (`bf-hd-osd-video`).
- **Symptom:** after fitting the camera the aircraft feels sluggish or oscillates in pitch
  - Possible cause: +45–200 g and a center-of-mass shift forward and up.
  - Consequences: different inertia, motors overheating, less flight time.
  - What to do: Blackbox and a recheck of the tune (`bf-pid`), move the battery.
- **Symptom:** with the camera on, GPS gets worse or the 2.4 GHz control link drops out
  - Possible cause: the camera's Wi-Fi/Bluetooth, interference from its electronics and power.
  - What to do: turn the wireless functions off, move the camera and its power wire away from the GPS, compare C/N0 (`el-emi`).
- **Symptom:** after losing the aircraft there is nothing to search with
  - Possible cause: only the onboard recording was running, the goggle DVR was off.
  - What to do: always record the goggle DVR, coordinates in the OSD (`ops-field`).

## checklist
- I know how the goggle DVR, the onboard recording and an action camera differ, and which of them helps in a search
- I choose a camera class for the task and estimate the cost of its mass in hover time
- I compute the shutter speed from the shutter angle, and the ND stops and ISO from EV
- I know when ND is not needed (Gyroflow and strong stabilization)
- I prepare a recording for Gyroflow: the camera gyro or Blackbox, tilt, synchronization
- I find the cause of jello from the footage and from the Blackbox spectrum
- I compute the recording size and card class from the bitrate
- I choose the camera tilt for the speed with the simplified model

## references
- Gyroflow — Supported cameras: GoPro | https://docs.gyroflow.xyz/app/getting-started/supported-cameras/gopro.md | primary | A
- Gyroflow — Supported cameras: DJI (O3/O4, EIS, ESC PWM, the 2026 O4 Pro gyro) | https://docs.gyroflow.xyz/app/getting-started/supported-cameras/dji.md | primary | A
- Gyroflow — Supported cameras: Insta360 (360° not supported) | https://docs.gyroflow.xyz/app/getting-started/supported-cameras/insta360.md | primary | A
- Gyroflow — Supported cameras: RunCam (recommended settings) | https://docs.gyroflow.xyz/app/getting-started/supported-cameras/runcam.md | primary | A
- Gyroflow — Flight controllers (Betaflight, ArduPilot, camera tilt) | https://docs.gyroflow.xyz/app/getting-started/supported-cameras/flight-controllers.md | primary | A
- Gyroflow — External gyro source: Flight Controller (250 Hz, debug NONE, preset) | https://docs.gyroflow.xyz/app/advanced-usage/using-external-gyro-source/flight-controller.md | primary | A
- Gyroflow — Synchronization | https://docs.gyroflow.xyz/app/getting-started/basic-usage/synchronization.md | primary | A
- Gyroflow — Stabilization (smoothing, horizon lock, rolling shutter) | https://docs.gyroflow.xyz/app/getting-started/basic-usage/stabilization.md | primary | A
- Gyroflow — Common filming tips & issues (180° and blur) | https://docs.gyroflow.xyz/app/getting-started/common-filming-tips-and-issues.md | primary | A
- Gyroflow — Basic usage | https://docs.gyroflow.xyz/app/getting-started/basic-usage.md | primary | A
- Gyroflow — README (features, gyro sources, license) | https://raw.githubusercontent.com/gyroflow/gyroflow/master/README.md | primary | A
- Betaflight `cli/settings.c`, tag 2025.12.5 (`blackbox_sample_rate`, `blackbox_disable_*`) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight `blackbox/blackbox.c`, tag 2025.12.5 (Blackbox defaults) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/blackbox/blackbox.c | primary | A
- DJI — O4 Air Unit Series specs | https://www.dji.com/o4-air-unit/specs | primary | A
- DJI — Osmo Action 5 Pro specs | https://www.dji.com/osmo-action-5-pro/specs | primary | A
- Insta360 — GO 3S specs | https://www.insta360.com/specs/go3s | primary | A
- Insta360 — X5 | https://www.insta360.com/product/insta360-x5?from=htrab_2026 | primary | B
- GoPro — HERO10 Black Bones | https://gopro.com/en/us/shop/cameras/hero10-black-bones/CHDBO-101-master.html | primary | B
- Walksnail — Avatar HD Pro Kit | https://caddxfpv.com/products/walksnail-avatar-hd-pro-kit | primary | B
- Caddx/Walksnail — Review: Avatar HD Pro/V2 Kit (Pro Kit: 32 GB, gyro for Gyroflow) | https://caddxfpv.com/blogs/news/review-walksnail-avatar-hd-pro-v2-kit | primary | B
- SD Association — Video Speed Class (V6…V90) | https://www.sdcard.org/press/thoughtleadership/160301SD_March_Thought_Leadership_FINAL_video_speed_class.html | primary | A
- RED — Shutter angle tutorial | https://www.reddigitalcinema.com/red-101/shutter-angle-tutorial | primary | B
- Marumi — ND filter line-up (optical density) | https://cdn.shopify.com/s/files/1/0549/4751/2365/files/ND_Filter_Line_Up_Marumi_catalog_2021_P05-06.pdf | primary | B
- Freewell — ND filter chart (stops and transmission) | https://freewellgear.com/pages/nd-filter-chart | primary | B
- GoPro — HERO13 Black / HERO12 Black / HERO comparison (the manufacturer's table, hosted by a distributor) | https://www.gpseesti.ee/DATA/www_files/gopro/goprotabel/h13black-h12black-hero-vordlus.pdf | secondary | B
- Clifton Cameras — GoPro HERO13 Black full spec | https://cliftoncameras.co.uk/uploads/downloads/Product%20Specifications/GoPro/GoPro%20Hero13%20Black%20Full%20Spec.pdf | secondary | B
- Adorama — DJI O4 Air Unit Pro (price) | https://www.adorama.com/djio4ap.html | secondary | B
- Oscar Liang — Flywoo Naked GoPro V2 | https://oscarliang.com/flywoo-naked-gopro-v2 | secondary | B
- Oscar Liang — RunCam Thumb 2 | https://oscarliang.com/runcam-thumb-2 | secondary | B

## notes
What could not be verified against primary sources: the gopro.com pages are closed to automated reading, so the HERO13 Black specifications come from a distributor's specification sheet and the GoPro comparison table hosted by a distributor; prices of full-size action cameras and the Insta360 as of November 2026 were not found (the $300–500 band is an estimate); the prices of the RunCam Thumb 2 and the "naked" GoPros come from Oscar Liang's reviews, with no price date; the number of the latest Gyroflow release (the releases page did not open; the master source says 1.7.1); the internal memory of the Walksnail HD Pro is 32 GB per the Caddx/Walksnail review (Pro Kit: 32 GB, the V2 Kit: 8 or 32 GB) and the Dual kit page; the "8GB" line in the specification table of the Single kit page contradicts the "32G" caption on the same page and is taken to be an error on the page. The hover-time model t ∝ m^−1.5 is an estimate for a hover on the same battery, ignoring the rise in current and the voltage sag. The model tan θ ∝ v² ignores the change in drag area with tilt and the lift of the body. The EV values for the scenes in the practice are given as problem conditions.
