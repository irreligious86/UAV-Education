---
id: inav-osd-hd
title: "OSD in INAV: analog and HD (DJI O3/O4, Walksnail, HDZero), layouts, alarms, custom elements"
level: L2
readingTime: 45 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-18
tags:
  - INAV
  - OSD
  - MSP DisplayPort
  - DJI
  - Walksnail
  - HDZero
related:
  - bf-hd-osd-video
  - link-digital-video
  - inav-setup-scratch
  - link-vtx
next:
  - inav-ipf
source: content/inav/inav-osd-hd.md
source_hash: f641bed9df8b
---

## summary
The OSD in INAV is a grid of characters that the flight controller either overlays on the analog video itself with the MAX7456 chip or sends over a UART to a digital air unit, where the goggles draw it. This module covers both paths on INAV 9.1.0: which `osd_video_system` value and which port function to set for HDZero, Walksnail, DJI O3, DJI O4 and WTFOS, what grid each has, how the four layouts and their switching work, alarms with their units, the statistics screen, the custom elements `osd_custom_elements`, the CMS menu, the horizon and the correction of the home arrow for a pan servo. Power and wiring of the air units are in `bf-hd-osd-video`, the overview of the systems is in `link-digital-video`; they are not repeated here. The lab needs no hardware: choose the port and the grid for four systems, parse ten `osd_layout` lines and find the elements that do not fit into a smaller grid, and convert alarm thresholds into firmware units.

## theory
### Who draws the OSD
There are two paths, and they are mutually exclusive.

- **Analog.** The board has a MAX7456 chip. The camera video passes through it, the chip, on commands from the processor (SPI), overlays characters from the font stored in its own memory and passes the frame to the VTX. The grid is 30×16 (PAL) or 30×13 (NTSC).
- **HD.** The flight controller sends MSP DisplayPort commands to the air unit over a UART: “in row R, starting at column C, these characters”. The goggles draw them — with their own font. The flight controller does not know what is actually visible in the goggles.

{{diagram:inav-osd-signal-path|In analog the OSD is overlaid by the chip on the flight controller, in HD — by the goggles. If MSP DisplayPort is assigned in the ports, the MAX7456 is not initialized: both paths do not work at the same time.}}

At startup (`fc_init.c`) INAV takes the first available output in this order: FrSky OSD → MSP DisplayPort (if there is a port with this function) → MAX7456. `feature OSD` must be enabled. The settings are read at boot, so after changing the port or `osd_video_system` you need `save` and a reboot.

### `osd_video_system`: value → grid → system
In Betaflight HD goggles report the grid size themselves. In INAV you set the grid, with one setting. The nine values of 9.1.0 (`settings.yaml`, the sizes — `displayport_msp_osd.c`):

| Value | Grid (columns×rows) | What for | Font |
|---|---|---|---|
| `AUTO` (default) | analog: PAL or NTSC by the camera signal; over MSP — 30×16 | an analog camera | the MAX7456 memory |
| `PAL` | 30×16 | analog PAL | the MAX7456 memory |
| `NTSC` | 30×13 | analog NTSC | the MAX7456 memory |
| `HDZERO` | 50×18 | HDZero | the INAV font on the goggles side |
| `AVATAR` | 53×20 | Walksnail Avatar | the INAV font on the goggles side |
| `DJIWTF` | 60×22 | old DJI Air Unit / Vista and DJI FPV goggles with WTFOS | the INAV font, installed by WTFOS |
| `BF43COMPAT` | 30×16 | DJI goggles with the Betaflight font, the SD grid | the DJI font; what is missing — `?` |
| `BFHDCOMPAT` | 53×20 | DJI O3 and goggles without the INAV font | the DJI font; what is missing — `?` |
| `DJI_NATIVE` | 53×20 | DJI O4 / O4 Pro and goggles on firmware that has the OSD type “INAV” | the INAV font, built into the goggles |

What you need to know about DJI:

- **Compatibility modes** (`BF43COMPAT`, `BFHDCOMPAT`). The DJI font is single-page, 256 glyphs based on Betaflight; INAV has two pages, up to 512. The firmware remaps every INAV character to the nearest DJI glyph; if there is no match, it outputs `?` (`osd_highlight_djis_missing_font_symbols = ON`, default) or a space (`OFF`). In the document `DJI compatible OSD.md` these values are still called DJI43COMPAT and DJIHDCOMPAT — the 9.1.0 CLI does not accept such names. In the goggles the canvas has to be switched to HD by hand.
- **`DJI_NATIVE`** appeared in 8.0.1. The release notes say: DJI released firmware for the O4 and the Goggles 2, 3, N3 and Integra that adds the INAV font and fixes arm detection on the O4; in the configurator select DJI_NATIVE, and in the goggles — the OSD type “INAV”; the value `AVATAR` gives the same grid and font. According to the 9.1.0 source `DJI_NATIVE` differs from `AVATAR` only in the index of the direction glyph (`osd.c`, `osd_hud.c`). You cannot load your own font into such goggles (`OSD.md`: “no custom fonts”).
- **Not verified:** the version numbers of the goggles and air unit firmware from which the “INAV” OSD type works; whether the combination “O3 + updated Goggles 2 / Integra” shows the INAV font. If the goggles menu has no “INAV” item — use `BFHDCOMPAT`.
- **`enable_broken_o4_workaround`** (OFF): for an O4 on its first firmware, which did not see the arm state and stayed in low-power mode. The 8.0.1 notes promised to remove the setting in INAV 9, but it is there in 9.1.0. On an updated O4 it is not needed.

WTFOS is a full DisplayPort implementation for the old DJI units: according to the INAV documentation it is better than the compatibility mode if you have the choice. The HDZero, Walksnail and WTFOS fonts are on the goggles side; the file names and folders on the SD card were not checked in this module — see the manual of your system.

{{diagram:chart-inav-osd-canvas|The grids differ by a factor of 2–3 in the number of cells. A layout built for 53×20 loses row 18 on 50×18, and six elements out of ten on 30×16: INAV does not move elements the way Betaflight does.}}

### The port: which function
Port functions in INAV are bits of the mask in the `serial` command (`io/serial.h`). The bit numbers do not match Betaflight, and `serial` lines are not moved between the firmwares.

| Function | Mask | When |
|---|---|---|
| `FUNCTION_MSP_OSD` (“MSP DisplayPort” on the Ports tab) | 33554432 (1 << 25) | all the HD systems from the table above; it is also VTX control over MSP (`FUNCTION_VTX_MSP` is the same number) |
| `FUNCTION_DJI_HD_OSD` (“DJI FPV VTX”) | 2097152 (1 << 21) | an old DJI Air Unit/Vista **without** WTFOS: a fixed set of DJI fields, not the INAV grid |
| `FUNCTION_FRSKY_OSD` | 1048576 (1 << 20) | FrSky PixelOSD |

The baud rate of the DisplayPort port is taken from the last field of the `serial` line (the peripheral baud rate), 115200 by default. An example for UART4: `serial 3 33554432 115200 115200 0 115200`.

Three properties of the exchange that explain most “no OSD” cases (`displayport_msp_osd.c`):

- The flight controller starts sending the OSD only after it has **received** some MSP request from the air unit; the unit sends them about once every 125 ms. Silence for longer than 1 s — transmission stops. So both wires are needed: without the line “unit TX → flight controller RX” the OSD will never appear.
- While the CLI is open, the OSD is not sent over MSP.
- Only the changed characters are transmitted; once every `osd_msp_displayport_fullframe_interval` (10 ds = 1 s; −1 — off, 0 — every frame) the screen is redrawn in full to clear the “garbage” left after lost packets.

The old DJI protocol shows INAV messages in the craft name field: `dji_use_name_for_messages = ON` (default).

### Layouts and switching them
There are four layouts: 0 (the main one) and 1–3 (the alternates). By default 1–3 hold the same positions as 0, but all elements are hidden. The default positions are designed for a 30×16 grid — on an HD grid they are bunched in the top left corner, and the layout has to be built again.

Which layout is active is decided by the firmware every frame in this order (`osd.c`):

1. a temporary override from the CMS or the configurator (editing an element activates its layout for 10 s);
2. `osd_failsafe_switch_layout = ON` (OFF by default) and failsafe → layout 0;
3. the OSD ALT 3 mode → 3, otherwise OSD ALT 2 → 2, otherwise OSD ALT 1 → 1;
4. operation 32 “Set OSD Layout” of the programming framework (`inav-ipf`), operand 0–3;
5. otherwise 0.

That is, the switch is stronger than the logic: if an OSD ALT mode is active, operation 32 has no effect. The OSD OFF mode blanks the screen, except for the CMS menu and the case from item 2.

In the CLI a position is one line per element:

```
osd_layout <layout 0–3> <element 0–168> <column> <row> <V|H>
```

The column and the row here are decimal, there is no packing; `V` — visible, `H` — hidden. Without the last field the visibility is kept. The packing exists inside: in memory and in MSP (`MSP2_INAV_OSD_LAYOUTS`) an element is a 16-bit word (`osd.h`):

```
word = x | (y << 6) | 0x2000·visible      x = word & 63,  y = (word >> 6) & 63
```

6 bits per coordinate, so the CLI accepts a column and a row of 0–63 — more than any grid. There is no “does it fit” check anywhere: an element beyond the edge is simply not visible. The element numbers are in the table of `docs/OSD.md` (169 in total, 0–168).

### Alarms: defaults and units
An alarm in INAV is a blinking element. The thresholds are stored in firmware units and do not depend on `osd_units`: the altitude is always in meters, even if the screen shows feet.

| Setting | Default | Range | Unit | Blinks when |
|---|---|---|---|---|
| `osd_rssi_alarm` | 20 | 0–100 | % | RSSI is below |
| `osd_link_quality_alarm` | 70 | 0–100 | % | LQ is below (CRSF) |
| `osd_rssi_dbm_alarm` | 0 | −130…0 | dBm | RSSI is below; 0 — off |
| `osd_snr_alarm` | 4 | −20…30 (up to 99 in 8.0.1) | dB | the SNR element **appears** when SNR ≤ the threshold |
| `osd_time_alarm` | 10 | 0–600 | min | flight time ≥ the threshold; 0 — off |
| `osd_alt_alarm` | 100 | 0–10000 | m | altitude is above; 0 — off |
| `osd_neg_alt_alarm` | 5 | 0–10000 | m | below the takeoff point by more than the threshold |
| `osd_dist_alarm` | 1000 | 0–50000 | m | farther from home; 0 — off |
| `osd_current_alarm` | 0 | 0–255 | A, integers | current is above; 0 — off |
| `osd_gforce_alarm` | 5 | 0–20 | g | g-force is above |
| `osd_imu_temp_alarm_min` / `_max` | −200 / 600 | −550…1250 | 0.1 °C | out of range |
| `osd_esc_temp_alarm_min` / `_max` | −200 / 900 | −550…1500 | 0.1 °C | out of range |
| `osd_airspeed_alarm_min` / `_max` | 0 / 0 | 0–27000 | cm/s | out of range; 0 — off |

The battery threshold is not an OSD matter: it is set in the battery profile (`inav-setup-scratch`). If the blinking is not visible — `display_force_sw_blink = ON` (software blink).

### Units, the arm screen and statistics
- `osd_units` (`METRIC` by default): `IMPERIAL`, `METRIC`, `METRIC_MPH` (meters, speed in miles per hour), `UK` (everything imperial, temperature in °C), `GA` (knots, nautical miles, feet).
- `osd_main_voltage_decimals` 1–2 (1); `osd_crsf_lq_format` TYPE1–TYPE3; `osd_coordinate_digits` 8–11 (9).
- The arm screen: `osd_arm_screen_display_time` 1000–5000 ms (1500), `osd_home_position_arm_screen = ON` shows the home coordinates.
- The statistics after disarm stay for up to 60 s. On a grid of 18 rows or more — one page, on analog — two: they are flipped with the roll stick or by themselves every `osd_stats_page_auto_swap_time` seconds (3; 0 — with the stick only). `osd_stats_energy_unit` — MAH or WH.
- The cumulative odometer is a separate feature: `stats = ON` accumulates `stats_total_time` (s), `stats_total_dist` (m), `stats_total_energy` (mWh) and, since 9.x, `stats_flight_count`.

### Custom elements: `osd_custom_elements`
Eight elements (there were three in 7.x), their numbers in a layout are 147–149 and 154–158. Each consists of three parts and a visibility condition:

```
osd_custom_elements <No. 0–7> <type1> <value1> <type2> <value2> <type3> <value3> <visibility> <value> "<TEXT>"
```

| Part type | What it outputs | Value |
|---|---|---|
| 0 | nothing | — |
| 1 | the text from the quotes (up to 15 characters, the firmware converts it to upper case; one text per element) | — |
| 2 | an icon | the font character code, 0–255 |
| 3 / 4 | an icon, the code is taken from a GVAR / from a logic condition | the GVAR / condition number |
| 5–9 | an integer from a GVAR, 1–5 digits | the GVAR number |
| 10–16 | a number with a decimal point from a GVAR: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1 digits | the GVAR number |
| 17–21, 22–28 | the same from a logic condition | the condition number |

Visibility: 0 — always, 1 — while the GVAR ≠ 0, 2 — while the logic condition is true. The width of a number is the number of digits plus one cell for the sign. The framework has no fractions: the “2.1” format shows the integer 123 as 12.3. All values in the CLI are 0–255. When moving from 7.x: the type numbers 4–7 shifted in 8.0, and the 8.0.0 release notes require you to correct them. An element is enabled like any other: `osd_layout 0 147 <column> <row> V`. How to compute GVARs and conditions is in `inav-ipf`.

### The CMS menu
The CMS is a setup menu in the OSD itself (PIDs, rates, navigation, VTX, alarms, element positions). Entry while disarmed: throttle centered, yaw left, pitch up (the code does not check the roll position, although `Controls.md` shows it centered). While the menu is open, arming is disabled (the `CMS` flag). In the submenu of an element you can change the column, the row and the visibility and see a preview at once. The thresholds of the entry stick command, the other stick commands and adjusting values with a switch in flight (during which the element with the value blinks) are in `inav-adjustments`.

### Crosshairs, horizon, sidebars, HUD
| Setting | Default | Range | Meaning |
|---|---|---|---|
| `osd_crosshairs_style` | DEFAULT | DEFAULT, AIRCRAFT, TYPE3–TYPE8 | the look of the crosshairs (in `osd.h` 9.1.0 the enum ends at TYPE7) |
| `osd_ahi_max_pitch` | 20 | 10–90 ° | the pitch at which the horizon line reaches the edge |
| `osd_ahi_reverse_roll` | OFF | — | the horizon as a roll indicator |
| `osd_camera_uptilt` | 0 | −40…80 ° | the camera uptilt; `osd_ahi_camera_uptilt_comp = ON` shifts the horizon by it |
| `osd_camera_fov_h` / `_v` | 135 / 85 | 60–150 / 30–120 ° | the field of view for the HUD |
| `osd_horizon_offset` | 0 | −2…2 rows | a vertical shift of the horizon and the sidebars |
| `osd_left_sidebar_scroll` / `osd_right_…` | NONE | NONE, ALTITUDE, SPEED, HOME_DISTANCE | what scrolls on the sidebar |
| `osd_sidebar_height` | 3 | 0–5 rows | the height of the sidebars |
| `osd_hud_homing`, `osd_hud_homepoint` | OFF | — | arrows toward home, the home point in 3D |
| `osd_hud_radar_disp` | 0 | 0–4 | how many nearby aircraft from the ESP32 radar to show |
| `osd_hud_wp_disp` | 0 | 0–3 | how many of the nearest mission waypoints to show |

If the camera is on a pan servo, the home arrow has to take the camera rotation into account: `osd_pan_servo_index` is the servo number, `osd_pan_servo_range_decadegrees` (−36…36, 0 — off) is the full travel of the servo in tens of degrees: a 180° servo → 18, and a minus reverses the direction. Before 9.0 the setting was called `osd_pan_servo_pwm2centideg`; on migration only the name changes, the number stays the same (a 180° servo — 18). In 9.1.0 the correction is divided by the actual servo travel `max − min`, so with a travel other than 1000 µs check the arrow again. The correction is computed like this:

```
angle, ° = (PWM − center) · range_decadegrees · 1000 / (max − min) / 100
```

A servo of 1000–2000 µs, center 1500, value 18: at 1750 µs the camera is turned by 45°. The firmware converts the result to whole degrees, dropping the fractional part: 6.75 → 6°.

`osd_row_shiftdown` (0–1) exists in 9.1.0, but nothing in the source reads it: changing it is pointless.

### Place in the system
- **Receives:** the UART and the power of the air unit (`bf-hd-osd-video`, `link-digital-video`); the ports and the initial setup (`inav-setup-scratch`); calibrated voltage and current; GVARs and logic conditions for custom elements and layout switching (`inav-ipf`).
- **Provides:** to the pilot — telemetry, alarms and system messages in the frame; to DVR recordings — the same data for flight analysis; VTX control over MSP (`link-vtx`).
- **If you get it wrong here:** a wrong `osd_video_system` — the elements at the edge are not visible, and the pilot misses an alarm; a threshold in the “wrong” units — altitude or distance blink too late (`inav-gps`); an MSP DisplayPort port on a board with an analog OSD — the MAX7456 is silent, and the cause is looked for in the camera and the VTX (`link-vtx`).

## practice
The lab is a calculation exercise, without a flight controller or a simulator. The configuration lines below were written for the exercise; they are not the output of a real aircraft.

### Step 1. The port and the grid for four systems
On each aircraft the air unit is connected to UART4 (identifier 3). Write down the `serial` line and the value of `osd_video_system`:

1. HDZero Freestyle V2 + HDZero goggles;
2. Walksnail Avatar + Avatar goggles;
3. DJI O4 Pro + Goggles 3, the goggles menu has the OSD type “INAV”;
4. DJI O3 + Goggles 2, there is no “INAV” item in the menu.

The `serial` line is the same for all: `serial 3 33554432 115200 115200 0 115200`. Only the grid differs: `HDZERO` (50×18), `AVATAR` (53×20), `DJI_NATIVE` (53×20), `BFHDCOMPAT` (53×20, some glyphs are `?`).

### Step 2. Ten `osd_layout` lines: the grid and the boundaries
Layout 0 is built for Walksnail (53×20):

```
osd_layout 0 0 2 1 V
osd_layout 0 1 2 2 V
osd_layout 0 15 44 1 V
osd_layout 0 23 44 2 V
osd_layout 0 14 2 18 V
osd_layout 0 7 24 17 V
osd_layout 0 30 13 18 V
osd_layout 0 12 44 18 V
osd_layout 0 110 2 3 H
osd_layout 0 147 22 3 V
```

For each line write down: the element (from `docs/OSD.md`), the column, the row, whether it is visible. Then check whether the anchor of the element (its left cell) falls inside the grid: column < the number of columns **and** row < the number of rows. Do this for 53×20, 50×18 and 30×16.

The result: all ten fit in 53×20. In 50×18 three drop out — elements 14, 30 and 12 (row 18 with rows 0–17). In 30×16 six drop out: 15 and 23 (column 44), 14, 30 and 12 (row 18), 7 (row 17). Element 110 is in the grid but hidden (`H`).

Element 147 is defined by the line `osd_custom_elements 0 1 0 6 2 0 0 2 5 "bat low"`. Parse it: part 1 — text (type 1), `BAT LOW` on the screen, 7 cells; part 2 — type 6, GVAR 2 with two digits, 3 cells with the sign; part 3 is empty; visibility 2 — while logic condition 5 is true. The width is 10 cells: columns 22–31. In 30×16 the anchor is inside, but the last two characters are beyond the edge (columns 30 and 31).

### Step 3. Packing a position
Convert three lines into the 16-bit words that `MSP2_INAV_OSD_LAYOUTS` returns: `2 1 V` → 2 + 1·64 + 8192 = 8258 (0x2042); `44 18 V` → 44 + 18·64 + 8192 = 9388 (0x24AC); `2 3 H` → 2 + 3·64 = 194 (0x00C2). Now back: 0x2118 → x = 0x2118 & 63 = 24, y = (0x2118 >> 6) & 63 = 4, the 0x2000 bit is set — (24, 4), visible; 0x03D5 → (21, 15), hidden.

### Step 4. Alarm thresholds in firmware units
A fixed wing, the pilot thinks in feet and km/h, the screen has `osd_units = IMPERIAL`. The thresholds needed: a ceiling of 400 feet; a distance of 1.5 miles; a time of 18 min; the ESC no hotter than 80 °C; the airspeed no lower than 40 km/h and no higher than 110 km/h; a current of 45 A; a full redraw of the HD OSD once every 2.5 s.

The conversion: 400 · 0.3048 = 121.92 m → `osd_alt_alarm = 121` (round an upper threshold down: 122 m is already 400.3 feet); 1.5 · 1609.344 = 2414 m → `osd_dist_alarm = 2414`; `osd_time_alarm = 18`; `osd_esc_temp_alarm_max = 800`; 40 / 3.6 · 100 = 1111 cm/s → `osd_airspeed_alarm_min = 1112` (a lower threshold — up), 110 / 3.6 · 100 = 3055.6 → `osd_airspeed_alarm_max = 3055`; `osd_current_alarm = 45`; `osd_msp_displayport_fullframe_interval = 25`.

### Moving to real hardware
The propellers stay off for the whole check; cool the air unit with a fan — on the bench it overheats (`bf-hd-osd-video`).

1. Save a `diff all`. On the Ports tab enable MSP DisplayPort on the UART of the air unit, select the system in OSD, `save`.
2. In the goggles enable the custom OSD (on DJI — Canvas Mode / the “INAV” type). The INAV splash screen with the version should appear.
3. Put one element in each of the four corners of the grid. All four are visible — the grid is chosen correctly; the right or bottom ones are not visible — `osd_video_system` is larger than the real grid.
4. Assign OSD ALT 1 and OSD ALT 2 to a three-position switch, enable different elements in layouts 1 and 2, check the switching.
5. Set `osd_alt_alarm = 1` and lift the aircraft by hand by 1.5 m: the altitude should start blinking. Put the working value back.

On hardware the work is done when the four corner elements are visible, the layout changes with the switch and the test alarm blinks.

Self-check: the lab is done when:
- for the four systems the mask 33554432 and the values `HDZERO`, `AVATAR`, `DJI_NATIVE`, `BFHDCOMPAT` are written down — an exact match;
- for the ten lines you got: outside 50×18 — elements 14, 30, 12; outside 30×16 — 15, 23, 14, 30, 12, 7; element 110 is hidden; element 147 has a width of 10 cells and 2 characters beyond the edge of the 30×16 grid;
- the words match: 8258, 9388, 194; the reverse decoding gave (24, 4, visible) and (21, 15, hidden);
- the thresholds match: 121, 2414, 18, 800, 1112, 3055, 45, 25 (±1 is acceptable for the airspeed).

**Reference for the self-check.** The correct result is the numbers from the four items above. Typical errors: (1) no element dropped out of 50×18 — you compared row 18 with the row count 18 using “≤”; rows are numbered from zero, and in a grid of 18 rows the last one is 17. If two elements came out outside 30×16 (15 and 23), you checked only the columns. (2) The words came out as 8226 and 8812 (or 8780 if the column was also truncated to 5 bits), or decoding 0x2118 gave (24, 8) — the five-bit formula `x | (y << 5)` was applied; in INAV it remains only for the old DJI protocol (`OSD_POS_SD`), and in the layouts a coordinate takes 6 bits. (3) `osd_alt_alarm = 400` or `osd_esc_temp_alarm_max = 80` — the threshold was written in screen units: the altitude in the firmware is always in meters, the temperature in tenths of a degree; with 80 the element would blink already at 8 °C. (4) The mask 33554433 or 2097152 — an extra MSP bit was added or the old DJI protocol was chosen: the INAV grid needs the single function MSP DisplayPort.

## diagnostics
- **Symptom:** there is HD video, but no INAV OSD at all
  - Possible cause: the MSP DisplayPort port (33554432) is not assigned or is assigned to the wrong UART; `feature OSD` is off; the wire “unit TX → flight controller RX” is not connected — the flight controller waits for an MSP request from the unit and sends nothing without it; the custom OSD is off in the goggles.
  - What to do: check `serial` and `feature`; check both signal wires for continuity; close the CLI — with the CLI open the OSD is not sent over MSP; enable Canvas Mode / the OSD type in the goggles.
- **Symptom:** there is analog video, but no OSD
  - Possible cause: MSP DisplayPort is assigned to some port — then the MAX7456 is not initialized; the board has no chip (an HD version of the flight controller); the OSD OFF mode is active; the camera is not connected to the chip input.
  - What to do: remove the MSP DisplayPort function from all ports; check the Modes tab; `osd_video_system = AUTO` or PAL/NTSC by hand to match the camera.
- **Symptom:** all the elements are bunched in the top left corner of the HD screen
  - Possible cause: the default layout is designed for 30×16.
  - What to do: after selecting `osd_video_system` arrange the elements again on the OSD tab.
- **Symptom:** the elements at the right or bottom edge are not visible
  - Possible cause: `osd_video_system` sets a grid larger than that of the goggles (for example, `DJIWTF` 60×22 on an O3 with 53×20, `AVATAR` on HDZero).
  - What to do: set the value from the table; check with four corner elements.
- **Symptom:** `?` characters instead of icons (DJI)
  - Possible cause: the `BFHDCOMPAT` / `BF43COMPAT` mode — the DJI font has no match for an INAV character.
  - What to do: if the goggles have the OSD type “INAV” — update the firmware and set `DJI_NATIVE`; otherwise remove such elements or hide the characters: `osd_highlight_djis_missing_font_symbols = OFF`.
- **Symptom:** a DJI O4 stays at low power after arming
  - Possible cause: old O4 firmware does not recognize the arm state.
  - What to do: update the air unit and the goggles; if you cannot update — `set enable_broken_o4_workaround = ON`.
- **Symptom:** the splash screen of the analog OSD shows “INVALID FONT” or “INVALID FONT VERSION”, garbage instead of icons
  - Possible cause: the MAX7456 still holds the font of another firmware or of an old version.
  - What to do: upload the font on the OSD tab of a configurator of the same version as the firmware.
- **Symptom:** an alternate layout is empty
  - Possible cause: in layouts 1–3 all elements are hidden by default.
  - What to do: select the layout in the configurator and enable the elements, or copy the `osd_layout 0 …` lines with the first number replaced.
- **Symptom:** operation 32 of the framework does not change the layout
  - Possible cause: one of the OSD ALT modes is active — it has priority; or failsafe is active with `osd_failsafe_switch_layout = ON`.
  - What to do: remove OSD ALT from the switch or switch with logic only.
- **Symptom:** the altitude alarm triggers “in the wrong place” with feet on the screen
  - Possible cause: `osd_alt_alarm` was entered in feet, but the firmware compares meters.
  - What to do: convert: feet · 0.3048.
- **Symptom:** a custom element does not appear
  - Possible cause: the visibility condition is false; the element is not enabled in the active layout; the type number was carried over from 7.x.
  - What to do: temporarily set visibility 0; check `osd_layout <layout> 147 …`; compare the type numbers with the table.
- **Symptom:** “stuck” characters remain on the HD OSD at the edge of the link
  - Possible cause: a packet with a cell update was lost.
  - What to do: keep `osd_msp_displayport_fullframe_interval = 10`; the value −1 disables the full redraw.

## checklist
- [ ] `feature OSD` is enabled; on an analog board no port has MSP DisplayPort assigned
- [ ] HD: the port is 33554432, 115200, both UART wires are connected
- [ ] `osd_video_system` is chosen from the table, the four corner elements are visible
- [ ] The layout is built for your grid, not left over from 30×16
- [ ] The alarm thresholds are written in meters, cm/s, 0.1 °C and whole amps
- [ ] The needed elements are enabled in the alternate layouts; OSD ALT is checked with the switch
- [ ] A `diff all` is saved after the setup

## references
- INAV 9.1.0 OSD.md (systems, grids, element numbers, statistics) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/OSD.md | primary | A
- INAV 9.1.0 displayport_msp_osd.c (grids, the exchange with the VTX, the full redraw) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/displayport_msp_osd.c | primary | A
- INAV 9.1.0 osd.h (position packing, the number of layouts) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/osd.h | primary | A
- INAV 9.1.0 osd.c (layout selection, alarms, statistics) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/osd.c | primary | A
- INAV 9.1.0 settings.yaml (values, ranges, units) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 serial.h (port functions) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/serial.h | primary | A
- INAV 9.1.0 custom_elements.h (part types of custom elements) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/osd/custom_elements.h | primary | A
- INAV 9.1.0 DJI compatible OSD.md | https://github.com/iNavFlight/inav/blob/9.1.0/docs/DJI%20compatible%20OSD.md | primary | A
- INAV 8.0.1 release notes (DJI_NATIVE, O4) | https://github.com/iNavFlight/inav/releases/tag/8.0.1 | primary | A
- INAV 8.0.0 Release Notes (the O4 workaround, the change of custom element types) | https://github.com/iNavFlight/inav/wiki/8.0.0-Release-Notes | primary | A
- INAV wiki: Custom OSD Elements | https://github.com/iNavFlight/inav/wiki/Custom-OSD-Elements | primary | B
- INAV 9.1.0 Controls.md (the CMS entry stick command) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Controls.md | primary | A
