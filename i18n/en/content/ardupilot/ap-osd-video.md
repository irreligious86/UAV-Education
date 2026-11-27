---
id: ap-osd-video
title: "OSD and video in ArduPilot: MAX7456, MSP DisplayPort (DJI, Walksnail, HDZero), OSDn screens, VTX"
level: L2
readingTime: 50 min
firmware: ArduCopter 4.7 (checked against 4.7.3)
status: published
added: 2026-11-18
tags:
  - ArduPilot
  - OSD
  - MSP DisplayPort
  - MAX7456
  - VTX
  - DJI
  - Walksnail
  - HDZero
related:
  - ap-setup-scratch
  - ap-intro
  - bf-hd-osd-video
  - inav-osd-hd
  - link-digital-video
  - link-vtx
next:
  - ap-safety-fs
source: content/ardupilot/ap-osd-video.md
source_hash: bfe8055b20aa
---

## summary
The OSD in ArduPilot is a separate library, `AP_OSD`, with five backend types, four item screens, and two parameter screens. This module works through it on ArduCopter 4.7.2: what each `OSD_TYPE` value means, which `SERIALn_PROTOCOL` and which `MSP_OPTIONS` bits analog, HDZero, Walksnail, DJI O3/O4, and legacy DJI need; how to choose the `OSDn_TXT_RES` grid, exactly how screens switch with each `OSD_SW_METHOD`, what the `OSD_W_*` warning levels do, and how the flight controller controls an analog VTX through `VTX_*`. Power and wiring of the air units and the goggle settings are in `bf-hd-osd-video` and `inav-osd-hd` and are not repeated here. The lab needs no hardware and no simulator: from a training parameter file you determine the active screen for given channel values, find the items that are off the grid, pick the "port, OSD type, MSP options" triple for four systems, and find three configuration errors.

## theory
### Who draws the OSD: `OSD_TYPE`
`OSD_TYPE` selects the backend, that is, whoever turns flight controller data into a picture. The default in the source is 0, but a board can set its own value: in the 4.7.2 tree about a hundred board definitions (`hwdef`) set 1 and about fifteen set 5. The parameter requires a reboot; while it is 0, the other `OSD_*` parameters are hidden.

| `OSD_TYPE` | Name | Who draws | What else is needed |
|---|---|---|---|
| 0 | None | nobody | — |
| 1 | MAX7456 | a chip on the board overlays characters on the analog video; the grid is 30×16 (PAL) or 30×13 (NTSC), and the standard is detected automatically | camera and VTX on the board's pads |
| 2 | SITL | a simulator window | a build with SFML (`sim_vehicle.py --osd`) |
| 3 | MSP | the goggles: the flight controller sends only MSP telemetry and item positions and draws nothing itself | `SERIALn_PROTOCOL = 33` or 32 |
| 4 | TXONLY | nobody; it makes the OSD parameter selection available to other modules (the CRSF script on the transmitter) | — |
| 5 | MSP_DISPLAYPORT | the goggles draw, in their own font, the characters that the flight controller has placed in cells | `SERIALn_PROTOCOL = 42` |

The OSD thread runs with a 100 ms period: 10 times per second the screen is cleared and drawn again.

`OSD_TYPE2` enables a second backend alongside the first. The typical case is a long-range wing with an analog VTX and an HD system (`OSD_TYPE = 1`, `OSD_TYPE2 = 5`). The compatible pairs are "MAX7456 or SITL" + "MSP or DisplayPort". Two identical types, MAX7456 + SITL, and MSP + DisplayPort do not start; the flight controller then refuses to arm with the message `OSD_TYPE2 not compatible with first OSD`. Both backends show the same current screen, so for different grids you make two screens and switch between them with a switch.

{{diagram:ap-osd-backend-map|Three OSD paths in ArduPilot: MAX7456 draws by itself, DisplayPort hands cells to the goggles, and legacy MSP hands over telemetry only. The port protocol and the OSD type must match as a pair: 42 with 5, 33 with 3.}}

### The port: `SERIALn_PROTOCOL` and `MSP_OPTIONS`
| `SERIALn_PROTOCOL` | Purpose | Wires |
|---|---|---|
| 32 MSP | MSP telemetry on request: third-party MSP OSDs, MSP sensors | TX and RX |
| 33 DJI FPV | telemetry for legacy DJI (FPV Goggles V1/V2 without WTFOS): the flight controller answers as Betaflight (`BTFL`) | TX and RX; TX only with bit 0 of `MSP_OPTIONS` |
| 42 DisplayPort | cell-by-cell output: HDZero, Walksnail, DJI O3/O4, DJI with WTFOS | TX and RX |
| 37 SmartAudio | analog VTX control | one wire on TX |
| 44 IRC Tramp | analog VTX control | one wire on TX and `SERIALn_OPTIONS = 4` (half duplex) |
| 29 Crossfire VTX | VTX control over CRSF | TX and RX |

For 32, 33, and 42 the firmware sets a default baud rate of `SERIALn_BAUD = 115`. It is only a default: if the port's baud rate was already saved as something else, it stays that way, so check it by hand.

`MSP_OPTIONS` (0 by default) is a bitmask:

| Bit | Value | Name | What it does |
|---|---|---|---|
| 0 | 1 | EnableTelemetryMode | "push" mode: the flight controller sends packets by itself without waiting for requests. Needed when only one wire runs between the OSD and the flight controller. It works only with protocol 33; for DisplayPort leave it at 0 |
| 1 | 2 | — | unused |
| 2 | 4 | EnableBTFLFonts | DisplayPort: character indexes from the Betaflight font table, and the answer to the firmware type request is `BTFL`; decimal packing is disabled in this case |
| 3 | 8 | EnableINAVFonts | DisplayPort: characters are translated to the INAV font; overrides bit 2 |

The character table is selected when the backend starts, so a reboot is needed after changing `MSP_OPTIONS`. `MSP_OSD_NCELLS` (0 Auto, 1–14) sets the cell count for the average cell voltage in MSP telemetry; Auto calculates `floor(V / 4.35) + 1` from the highest voltage seen.

### Which system needs what
| System | `SERIALn_PROTOCOL` | `OSD_TYPE` | `MSP_OPTIONS` | `OSDn_TXT_RES` | Font |
|---|---|---|---|---|---|
| Analog, a board with a MAX7456 | — | 1 | — | — | `OSD_FONT` 0–4 in the chip |
| HDZero | 42 | 5 | 0 | 0 or 1; with 2 the text turns into garbage | the ArduPilot font in the goggles |
| Walksnail Avatar | 42 | 5 | 0 | 1 | the ArduPilot font file is selected in the goggle menu |
| DJI Air Unit/Vista with WTFOS + msp-osd | 42 | 5 | 0 | 2 (or 1) | a font package on the goggles' SD card |
| DJI O3 / O4, stock firmware | 42 | 5 | 4; 8 if the INAV font is selected in the goggles | 1 | the Betaflight or INAV font in the goggles |
| DJI FPV V1/V2 without WTFOS | 33 | 3 | 0 (1 with a single wire) | — | the goggles draw the items |

The HDZero and WTFOS rows follow the ArduPilot wiki; for legacy DJI the wiki also sets bit 2 of `MSP_OPTIONS` and bit 5 of `OSD_OPTIONS`, but in the 4.7 code bit 2 affects only DisplayPort (protocol 33 always identifies as BTFL), so 0 works. For DJI O3/O4 and Walksnail the wiki gives no ready recipe with `OSDn_TXT_RES`: the values in the table come from practice on the ArduPilot forum and from the fact that the 50×18 grid fits into the 53×20 canvas of these systems. In DJI goggles the custom OSD option must be enabled. With the Betaflight font add bit 5 to `OSD_OPTIONS`, otherwise the arrows point the wrong way. Ready-made ArduPilot fonts for Walksnail and WTFOS are in the source tree: `libraries/AP_OSD/fonts/HDFonts`.

### Grid and fonts
`OSDn_TXT_RES` is set separately for each screen and works only with DisplayPort: 0 is 30×16, 1 is 50×18, 2 is 60×22. The default is 0, so HD goggles first show the coarse SD grid. `OSDn_FONT` (0–21) is the font index the flight controller requests from the goggles for that screen. Both numbers are sent to the goggles on every cycle, so the grid changes together with the screen.

The coordinates `OSDn_<ITEM>_X` (0–59) and `OSDn_<ITEM>_Y` (0–21) are counted from the top left corner, starting at zero. When the grid changes, the firmware does not recalculate them or clamp them to the edge: a layout made for 60×22 loses everything to the right of column 49 and below row 17 in the 50×18 grid, and the defaults, designed for 30×16, bunch up in the top left corner in HD. In Mission Planner's onboard OSD configuration page, enable the HD layout option for HD.

`OSD_FONT` applies to MAX7456 and SITL: 0 clarity, 1 clarity_medium, 2 bfstyle, 3 bold, 4 digital; it can be changed on the fly (the ground station will ask for a reboot because of how the parameter is flagged, but MAX7456 reloads the font immediately). The font is looked for first on the SD card (`font0.bin` … `font9.bin` in the root), then in the firmware; if the file is missing, font 0 is used. On boards with 1 MB of flash the fonts may be left out of the build, in which case put them on the card. `OSD_V_OFFSET` (0–31, default 16) and `OSD_H_OFFSET` (0–63, default 32) shift the MAX7456 picture.

### Screens and switching between them
There are six screens: `OSD1`…`OSD4` hold items, and `OSD5` and `OSD6` are parameter screens (9 `OSDn_PARAMk_*` slots each and a save button; the values are changed with the sticks, only while disarmed; while such a screen is open, arming is refused with `In OSD menu`). `OSD1_ENABLE` is forced on, and the other `OSDn_ENABLE` parameters default to 0. Every screen has `OSDn_CHAN_MIN` (900) and `OSDn_CHAN_MAX` (2100).

`OSD_CHAN` is the number of the RC channel used for switching (0 disables it, 5–16). `OSD_SW_METHOD` sets the method:

| Value | Behavior (4.7.2 source) |
|---|---|
| 0 (default) | The next enabled screen on every change of the channel by more than 200 µs from the value remembered at the previous switch. The direction does not matter. A 1000 → 2000 flick is one step |
| 1 | The screen whose range the channel falls into: `CHAN_MIN ≤ PWM < CHAN_MAX`, with the upper bound excluded. If several enabled screens match, the one with the higher number wins. If none matches, the screen does not change |
| 2 | While the channel is above that channel's `RCn_TRIM`: the first step after 0.1–0.2 s, then the next screen every 1.2 s (the thread ticks every 100 ms, the branch runs on every second tick, and a step happens when more than 1000 ms have passed since the last one). At or below `RCn_TRIM` it stays put and the timer resets |

"Next" goes around the circle 1 → 2 → … → 6, skipping disabled screens, so enabled parameter screens take part in the cycle.

Events switch the screen by themselves: `OSD_ARM_SCR` on arming, `OSD_DSARM_SCR` on disarming, `OSD_FS_SCR` on a radio or battery failsafe (0 disables it, 1–4; the screen must be enabled). When the failsafe ends, the previous screen comes back. With method 1 the event screen stays until the switch moves into a different range.

### Items: `OSDn_<ITEM>_EN/_X/_Y`
The 4.7.2 metadata has 65 items per screen; five of them (`RC_*`, `RSSIDBM`) exist only in your own build with the extended link statistics option: in `AP_OSD_config.h` the `AP_OSD_LINK_STATS_EXTENSIONS_ENABLED` flag is 0, it is enabled on the custom build server (the `OSD_EXTENDED_LINK_STATS` item), and the stock firmware builds do not have these items.

| Group | Items |
|---|---|
| Battery | `BAT_VOLT`, `RESTVOLT`, `AVGCELLV`, `ACRVOLT`, `CURRENT`, `BATUSED`, `BAT2_VLT`, `BAT2USED`, `CURRENT2` |
| Link | `RSSI`, `LINK_Q`; in the special build, `RC_LQ`, `RC_SNR`, `RSSIDBM`, `RC_PWR`, `RC_ANT` |
| Altitude and speed | `ALTITUDE`, `TER_HGT`, `RNGF`, `VSPEED`, `GSPEED`, `ASPEED`, `ASPD1`, `ASPD2`, `WIND` |
| Navigation | `HOME`, `HEADING`, `COMPASS`, `SATS`, `HDOP`, `GPSLAT`, `GPSLONG`, `PLUSCODE`, `WAYPOINT`, `XTRACK`, `FENCE` |
| Horizon | `HORIZON`, `SIDEBARS`, `ROLL`, `PITCH` |
| Flight state | `FLTMODE`, `MESSAGE`, `THROTTLE`, `FLTIME`, `DIST`, `STATS`, `EFF`, `CLIMBEFF`, `CLK`, `CALLSIGN`, `VTX_PWR` |
| Motors and sensors | `ESCTEMP`, `ESCRPM`, `ESCAMPS` (the ESC is selected with `OSDn_ESC_IDX`, 0 means the highest value), `RPM`, `TEMP`, `BTEMP`, `ATEMP` |
| Legacy MSP only | `CRSSHAIR`, `HOMEDIST`, `HOMEDIR`, `POWER`, `CELLVOLT`, `BATTBAR`, `ARMING` |

`FLTMODE` is four letters of the mode and an arming symbol. `MESSAGE` shows the flight controller's latest text message (the same one as in the ground station's Messages) for `OSD_MSG_TIME` seconds (1–20, default 10) in capital letters; the visible width is 26 cells, and longer text scrolls. `STATS` is a block of 6 lines: the maximum speed, current, altitude, and distance, and the distance traveled; it is usually put on a separate screen, and that screen is set in `OSD_DSARM_SCR`.

Legacy DJI (type 3) takes from a screen only the enable flags and positions of the 26 items in its own set. It shows the flight mode in the `MESSAGE` field (the "craft name" on DJI), while `FLTMODE` is hidden and flashes only on a failsafe. The `OSD_W_*` warning levels do not work for it, and the units are metric or imperial only.

### Units, options, warning levels
`OSD_UNITS`: 0 Metric (m, km/h, m/s), 1 Imperial (feet, mph, °F), 2 SI (speed in m/s), 3 Aviation (feet, knots, feet/min, nautical miles).

`OSD_OPTIONS` (1 by default):

| Bit | Value | Effect |
|---|---|---|
| 0 | 1 | a digit and the decimal point packed into one character (saves a cell) |
| 1 | 2 | the wind arrow shows where the wind is coming from |
| 2 | 4 | invert the horizon roll |
| 3 | 8 | convert feet to miles at 5280 ft instead of 10000 ft |
| 4 | 16 | disable the crosshair |
| 5 | 32 | translate the arrows for the Betaflight font |
| 6 | 64 | aviation-style horizon in inverted flight |
| 7 | 128 | prefix LQ with the RF mode (special build only) |

Warning levels: an item flashes while its value is below the level.

| Parameter | Default | Range | Item |
|---|---|---|---|
| `OSD_W_BATVOLT` | 10.0 V | 0–100 | `BAT_VOLT` |
| `OSD_W_RESTVOLT` | 10.0 V | 0–100 | `RESTVOLT` |
| `OSD_W_AVGCELLV` | 3.6 V | 0–100 | `AVGCELLV` |
| `OSD_W_ACRVOLT` | 3.6 V | 0–100 | `ACRVOLT` |
| `OSD_W_RSSI` | 30% | −128…100 | `RSSI` |
| `OSD_W_NSAT` | 9 | 1–30 | `SATS` (it also flashes without a 3D fix) |
| `OSD_W_TERR` | −1 (disabled), m | −1…3000 | `TER_HGT` |
| `OSD_W_LQ`, `OSD_W_SNR` | 50%, 0 dB | 0–100, −20…10 | special build only |

10.0 V will never trigger on 4S and above, so set the level for your battery. `OSD_CELL_COUNT` for `AVGCELLV` and `ACRVOLT`: with −1 (the default) the item shows dashes, 0 is autodetection, N is manual. Autodetection calculates `floor(Vmax · 0.2381 + 1)`; at exactly 4.20 V per cell it comes out one cell too many (12.6 V → 4), so it is more reliable to set the cell count by hand.

### VTX control
For an analog transmitter: `VTX_ENABLE = 1` and a port with protocol 37 (SmartAudio: one wire on TX, 4800 baud, and the firmware enables half duplex itself), 44 (Tramp: one wire on TX, 9600 baud; the firmware does not enable half duplex itself, so set `SERIALn_OPTIONS = 4`), or 29 (CRSF). Once the VTX is detected, a `VTX: <band><channel> <frequency>MHz, PWR: <power>mW` line appears in Messages, and any unset `VTX_*` parameters are filled in from the transmitter's current settings.

| Parameter | Range | Meaning |
|---|---|---|
| `VTX_BAND` | 0 A, 1 B, 2 E, 3 Airwave (F), 4 RaceBand, 5 Low RaceBand, 6–7 1.3 GHz, 8 X, 9–10 3.3 GHz | band |
| `VTX_CHANNEL` | 0–7 | channel; 0 is the first one |
| `VTX_FREQ` | 1000–6000 MHz | follows the band and channel; if you set a frequency from the table, they adjust to it |
| `VTX_POWER` | 1–1000 mW | rounded down to a level from the firmware table: 25, 100, 200, 400, 500, 600, 800, 1000 |
| `VTX_MAX_POWER` | 25–1000, default 800 | the ceiling for the power switch (a switch or a knob, see `ap-aux-tune`) |
| `VTX_OPTIONS` | bitmask | bit 0 is pit mode; bit 1 is pit mode until armed; bit 2 is pit mode when disarmed; bit 3 unlocks frequencies and power levels; bits 4–6 are workarounds for nonstandard SmartAudio |

Conversion: dBm = 10 · log₁₀(mW). 25 mW ≈ 14 dBm, 200 ≈ 23, 800 ≈ 29. Pit mode on the ground and full power in the air: bits 0 and 1 (value 3) leave the power on after disarming; bits 0, 1, and 2 (value 7) return to pit mode on disarming (per the 4.7.2 source bit 2 alone is enough for that, but 7 is unambiguous and matches the wiki). `RCx_OPTION = 94` (VTX Power) reads the channel as a six-position switch (boundaries at 1231, 1361, 1491, 1621, 1750 µs) and maps the positions to levels no higher than `VTX_MAX_POWER`; the lowest position is 0 mW, that is, pit mode, and you can enter it only while disarmed. Frequencies and legal power are in `link-vtx`.

### 4.6 → 4.7
The names, values, and defaults of the `OSD*`, `MSP_*`, and `VTX_*` parameters in 4.7.2 are the same as in 4.6.3: the metadata of the two versions matches completely for these groups. They are not in the rename table in `ap-intro`, and an OSD parameter file carries over without edits.

### Place in the system
- **Receives:** the UART map and the board setup order from `ap-setup-scratch` (in `-bdshot` builds the timer and UART layout is different, see `ap-outputs`); power, wiring, and the behavior of DJI, Walksnail, and HDZero goggles from `bf-hd-osd-video` and `link-digital-video`; the frequency table and power regulations from `link-vtx`; voltage, RSSI, mode, and messages from the battery monitor, the receiver, and the failsafe logic (`ap-safety-fs`).
- **Provides:** to the pilot, a picture of the vehicle's state and warnings; to neighboring modules, a ready "port, OSD type, MSP options" triple and a screen layout; to the counterparts on other firmware (`inav-osd-hd`, `bf-hd-osd-video`), a point of comparison.
- **If you get it wrong here:** the pilot does not see a low battery or a failsafe and learns about them from the crash (`ap-safety-fs`); a wrong VTX power causes interference for others and overheating (`link-vtx`); an open parameter screen blocks arming.

## practice
The lab is a calculation exercise: you need neither a flight controller nor a simulator. The parameter files below are a training example assembled by hand; they are not a dump from a real vehicle. Every answer follows from the tables in the theory.

```
# training example, assembled by hand (vehicle A)
OSD_TYPE,5
SERIAL4_PROTOCOL,42
SERIAL4_BAUD,115
MSP_OPTIONS,4
OSD_OPTIONS,33
OSD_CHAN,7
RC7_TRIM,1500
OSD_ARM_SCR,2
OSD_DSARM_SCR,3
OSD1_ENABLE,1
OSD1_CHAN_MIN,900
OSD1_CHAN_MAX,1300
OSD2_ENABLE,1
OSD2_CHAN_MIN,1300
OSD2_CHAN_MAX,1700
OSD3_ENABLE,1
OSD3_CHAN_MIN,1700
OSD3_CHAN_MAX,2100
OSD4_ENABLE,0
OSD4_CHAN_MIN,900
OSD4_CHAN_MAX,2100
OSD5_ENABLE,0
OSD6_ENABLE,0
```

### Step 1. Which screen is active
After power-up screen 1 is shown, channel 7 is at 1000 µs, and the vehicle is disarmed. Determine the screen for the three methods.

1. `OSD_SW_METHOD = 1`. The channel goes through, in turn: 1000, 1299, 1300, 1700, 2000. Then separately: it is moved from 1500 to 2100. Then: what happens if you set `OSD4_ENABLE = 1` without touching its range?
2. `OSD_SW_METHOD = 0`. A three-position switch: 1000 → 1500 → 2000 → 1500 → 1000. Separately: 1000 → 1150 → 1250 (a smooth knob).
3. `OSD_SW_METHOD = 2`. The channel is raised from 1000 to 2000 and held for 3.0 s. Separately: held at 1500.
4. `OSD_SW_METHOD = 1`, with the channel at 1000 the whole time. Arm, then disarm.

Result. (1) 1, 1, 2, 3, 3; at 2100 screen 2 stays, because the upper bound is not part of the range and no screen matched; with screen 4 enabled, screen 4 is shown at any value in 900–2099, because it always matches and has the higher number. (2) 1 → 2 → 3 → 1 → 2: after the third screen comes the first, because 4, 5, and 6 are disabled; on the knob 1150 changes nothing (150 < 200), and 1250 switches to screen 2 (250 from the remembered 1000). (3) Three steps, at about 0.2, 1.4, and 2.6 s: 1 → 2 → 3 → 1, ending on screen 1; at 1500 there is no switching, because the channel must be strictly above `RC7_TRIM`. (4) Screen 2 on arming and screen 3 on disarming; the switch is in the range of screen 1 all this time, and the firmware does not go back to it until the channel moves into a different range.

### Step 2. What does not fit the grid
Screen 2 was laid out for WTFOS, `OSD2_TXT_RES = 2`:

```
# training example, assembled by hand (vehicle A, screen 2)
OSD2_BAT_VOLT_X,2    OSD2_BAT_VOLT_Y,1
OSD2_CURRENT_X,2     OSD2_CURRENT_Y,2
OSD2_GSPEED_X,2      OSD2_GSPEED_Y,10
OSD2_HOME_X,46       OSD2_HOME_Y,1
OSD2_ALTITUDE_X,54   OSD2_ALTITUDE_Y,10
OSD2_VSPEED_X,25     OSD2_VSPEED_Y,15
OSD2_MESSAGE_X,6     OSD2_MESSAGE_Y,15
OSD2_SATS_X,2        OSD2_SATS_Y,20
OSD2_FLTMODE_X,27    OSD2_FLTMODE_Y,20
OSD2_STATS_X,40      OSD2_STATS_Y,13
```

All ten items are enabled. For `OSD2_TXT_RES` = 2, 1, and 0, list the items whose anchor (the top left cell) is off the grid: the anchor is inside when X < the number of columns **and** Y < the number of rows. For `MESSAGE` (up to 26 cells wide) and `STATS` (6 lines high) also check the far edge.

Result. 60×22: everything fits. 50×18: three anchors are off the grid, `ALTITUDE` (column 54) and `SATS` and `FLTMODE` (row 20); the anchor of `STATS` is inside, but the block takes rows 13–18, and the last line is past the edge. 30×16: five anchors are off the grid, `HOME` (46), `ALTITUDE` (54), `STATS` (40), and `SATS` and `FLTMODE` (row 20); `MESSAGE` sits in columns 6–31, so the last two characters of a long message are past the edge.

{{diagram:chart-ap-osd-grid-fit|A layout made for 60×22 loses three items and a line of statistics in the 50×18 grid, and five items in 30×16. ArduPilot does not recalculate coordinates when OSDn_TXT_RES changes.}}

### Step 3. Port, OSD type, and options for four systems
The air unit is connected to SERIAL4 with two wires. Write down `SERIAL4_PROTOCOL`, `OSD_TYPE`, `MSP_OPTIONS`, and `OSD1_TXT_RES`:

1. HDZero;
2. Walksnail Avatar, with the ArduPilot font selected in the goggles;
3. DJI O3 on stock firmware, with the Betaflight font in the goggles;
4. DJI FPV Air Unit and V2 goggles without WTFOS.

Result: (1) 42, 5, 0, grid 1 (or 0); (2) 42, 5, 0, grid 1; (3) 42, 5, 4, grid 1, plus bit 5 in `OSD_OPTIONS`; (4) 33, 3, 0, and `OSD1_TXT_RES` has no effect.

While you are at it, decode vehicle A's masks: `MSP_OPTIONS = 4` is bit 2 only, Betaflight characters; `OSD_OPTIONS = 33` = 1 + 32, bits 0 and 5. Bit 0 has no effect here: with Betaflight characters, decimal packing is disabled on DisplayPort. The reverse problem: you need decimal packing, the crosshair removed, and the arrows translated for Betaflight: 1 + 16 + 32 = 49.

### Step 4. Three errors in a configuration
Vehicle B: HDZero on SERIAL2, with the second screen needed only as the arming screen.

```
# training example, assembled by hand (vehicle B)
OSD_TYPE,5
OSD_TYPE2,0
SERIAL2_PROTOCOL,33
SERIAL2_BAUD,115
MSP_OPTIONS,0
OSD_CHAN,0
OSD_ARM_SCR,2
OSD1_ENABLE,1
OSD1_TXT_RES,2
OSD2_ENABLE,0
OSD2_TXT_RES,1
```

Result: there are exactly three errors. (1) `SERIAL2_PROTOCOL = 33` with `OSD_TYPE = 5`: the DisplayPort backend looks for a port with protocol 42, does not find one, and does not start (Messages shows `MSP DisplayPort uart not available`); it must be 42. (2) `OSD1_TXT_RES = 2`: HDZero understands only 0 and 1; it must be 1. (3) `OSD_ARM_SCR = 2` with `OSD2_ENABLE = 0`: a disabled screen is not shown on arming; you need `OSD2_ENABLE = 1`. The other lines are correct: `OSD_CHAN = 0` is allowed, and the arming screen works without a switch.

### Step 5. VTX power
An analog VTX on SmartAudio. (a) `VTX_POWER = 300`: what does the firmware store? (b) How much is that in dBm, and how many dB do you lose relative to 800 mW? (c) Which `VTX_OPTIONS` value gives pit mode until arming and a return to pit mode after disarming?

Result: (a) 200, the nearest table level below; (b) 10 · log₁₀ 200 = 23.0 dBm, 800 mW is 29.0 dBm, a difference of 6.0 dB; (c) 1 + 2 + 4 = 7.

### Moving to real hardware
The propellers are off for the whole check. Cool a digital air unit on the bench with a fan (`bf-hd-osd-video`), and screw on the VTX antenna before applying power.

1. Save the full parameter list to a file. Set the triple from step 3 for your system, reboot the flight controller, and refresh the parameter list: the `OSD1_*` parameters appear.
2. Messages must not contain `MSP DisplayPort uart not available`. In DJI goggles, enable the custom OSD option.
3. Put one item in each of the four corners of the chosen grid (for 50×18, columns 0 and 49, rows 0 and 17). If you see all four, the grid is right.
4. Enable the second screen, assign `OSD_CHAN`, set `OSD_SW_METHOD = 1`, and check both switch positions.
5. Set `OSD_W_BATVOLT` 0.5 V above the current voltage: `BAT_VOLT` should start flashing. Put the working level back.
6. Analog VTX: `VTX_ENABLE = 1`, protocol 37 or 44; after a reboot find the `VTX: …` line in Messages; change `VTX_CHANNEL` and confirm that the picture moved to the other channel.

On hardware the work is done when the four corner items are visible, the screen changes with the switch, the test warning level flashes, and the `VTX:` line shows the band, channel, and power you set.

Self-check: the lab is done when:
- step 1: method 1 gives screens 1, 1, 2, 3, 3, at 2100 screen 2 stays, and with screen 4 enabled it is always 4; method 0 gives 1, 2, 3, 1, 2 and a switch at 1250 but not at 1150; method 2 gives screen 1 after 3.0 s; arming gives 2, disarming gives 3;
- step 2: off the 50×18 grid are `ALTITUDE`, `SATS`, `FLTMODE`, and one line of `STATS`; off the 30×16 grid are `HOME`, `ALTITUDE`, `STATS`, `SATS`, `FLTMODE`, and two characters of `MESSAGE`;
- step 3: the triples (42, 5, 0), (42, 5, 0), (42, 5, 4), (33, 3, 0) match exactly; the mask is 49;
- step 4: exactly three errors are found: protocol 33, grid 2 for HDZero, a disabled arming screen;
- step 5: 200 mW, 23.0 dBm (tolerance ±0.1), a difference of 6.0 dB (±0.1), `VTX_OPTIONS = 7`.

**Reference for the self-check.** The correct result is the numbers in the five items above. Typical mistakes: (1) you got screen 1 at 1300 and screen 3 at 2100: the bounds were taken as "min < PWM ≤ max", while the firmware uses "min ≤ PWM < max". (2) In method 0 you got screen 4 after screen 3, or "back to 2": the cycle only goes forward around the circle and skips disabled screens, and the direction of the flick does not matter. (3) In step 2 you found no items off the 50×18 grid by row: row 20 was compared with 22, or row 18 was treated as valid, while in a grid of 18 rows the last one is number 17. (4) You wrote 33 and 3 for DJI O3: that is the set for the legacy V1/V2 goggles; O3 works over DisplayPort. (5) `VTX_POWER` was "rounded" to 400: the firmware only rounds down.

## diagnostics
- **Symptom:** the goggles of an HD system (HDZero, Walksnail, DJI O3/O4) show video but no OSD.
  Possible cause: `OSD_TYPE` is not 5 or there was no reboot; the air unit's port is not `SERIALn_PROTOCOL = 42`; only one UART wire is connected; the saved port baud rate is not 115; the custom OSD option is off in DJI goggles.
  What to do: check Messages for `MSP DisplayPort uart not available`; check the SERIAL number against the board's UART table; set `SERIALn_BAUD = 115`; power the air unit and the flight controller at the same time.
- **Symptom:** there is analog video but no OSD at all.
  Possible cause: `OSD_TYPE` is not 1; the board has no MAX7456; the camera and VTX are soldered past the board's pads, bypassing the chip; the build for a 1 MB board has no fonts.
  What to do: `OSD_TYPE = 1` and a reboot; camera to the board's video input, VTX to its video output; on the `OSD: Failed to load font` message, put `font0.bin` in the root of the SD card.
- **Symptom:** the analog OSD is visible, but the bottom items are gone.
  Possible cause: an NTSC camera, so the grid is 30×13 and items with Y ≥ 13 are not visible.
  What to do: move the items up or switch the camera to PAL.
- **Symptom:** letters, foreign symbols, or question marks instead of icons.
  Possible cause: the character table does not match the goggles' font: the Betaflight font without bit 2 of `MSP_OPTIONS`, the INAV font without bit 3, or the bit is set but the goggles have the ArduPilot font.
  What to do: make `MSP_OPTIONS` match the goggles' font (0, 4, or 8) and reboot the flight controller; for Walksnail and WTFOS install the ArduPilot font from `HDFonts`.
- **Symptom:** the home arrow or the wind arrow points the wrong way, and everything else is right.
  Possible cause: the Betaflight font without bit 5 of `OSD_OPTIONS`.
  What to do: add 32 to `OSD_OPTIONS`.
- **Symptom:** on HDZero the text turned into garbage after you set the grid.
  Possible cause: `OSDn_TXT_RES = 2`.
  What to do: set 1 (50×18) or 0.
- **Symptom:** after changing `OSDn_TXT_RES` some items disappeared or everything bunched up in a corner.
  Possible cause: coordinates are not recalculated; the layout was made for a different grid.
  What to do: check every enabled item: X < columns, Y < rows; for `MESSAGE` allow for a width of 26, for `STATS` a height of 6.
- **Symptom:** the screen does not change with the switch.
  Possible cause: `OSD_CHAN = 0`; the second screen is not enabled; with method 1 the channel value falls into no range; with method 0 the channel travel is less than 200 µs; with method 2 the channel is not above `RCn_TRIM`.
  What to do: look at the channel value on the radio calibration page and compare it with `OSDn_CHAN_MIN/MAX`; remember that the upper bound is not part of the range.
- **Symptom:** the screen changes by itself on arming or the "wrong" one stays after disarming.
  Possible cause: `OSD_ARM_SCR` or `OSD_DSARM_SCR` is set; with method 1 the firmware does not go back to the switch's screen until the channel changes range.
  What to do: set the event parameters to zero or flick the switch.
- **Symptom:** there is no flight mode text.
  Possible cause: on DisplayPort, `OSDn_FLTMODE_EN = 0` or the item is off the grid; on legacy DJI the mode is shown in the `MESSAGE` field, and the "craft name" is turned off in the goggles.
  What to do: set `OSDn_FLTMODE_EN` and check the coordinates; for legacy DJI set `OSDn_MESSAGE_EN` and enable the craft name field in the goggles' custom OSD settings.
- **Symptom:** `AVGCELLV` shows dashes, or the per-cell voltage reads low.
  Possible cause: `OSD_CELL_COUNT = −1`; autodetection at 4.20 V per cell counted one cell too many.
  What to do: set `OSD_CELL_COUNT` to the cell count.
- **Symptom:** the flight controller does not arm: `In OSD menu` or `OSD_TYPE2 not compatible with first OSD`.
  Possible cause: parameter screen 5 or 6 is open; the second OSD type makes an incompatible pair.
  What to do: switch to screens 1–4; keep the pair "1 + 5" or "1 + 3".
- **Symptom:** the VTX does not change channel or power, and there is no `VTX:` line in Messages.
  Possible cause: `VTX_ENABLE = 0`; the SmartAudio/Tramp wire is not on the port's TX; the VTX is not set to external control; a level was requested that the transmitter does not have.
  What to do: check protocol 37 or 44 and reboot; for Tramp check `SERIALn_OPTIONS = 4`: without half duplex the flight controller cannot hear the VTX's reply; for a temperamental SmartAudio unit use bits 4–6 of `VTX_OPTIONS`.
  Consequences: in pit mode (`VTX_OPTIONS` bit 0) the picture is lost within a few meters, and that is not a fault.

## checklist
- `OSD_TYPE` and `SERIALn_PROTOCOL` are set as a pair: 1 with no port, 5 with 42, 3 with 33
- `SERIALn_BAUD = 115`, and both UART wires are connected
- `MSP_OPTIONS` matches the font in the goggles: 0 ArduPilot, 4 Betaflight, 8 INAV
- `OSDn_TXT_RES` is set on every enabled screen; not 2 for HDZero
- Every enabled item is inside the grid, and the width of `MESSAGE` and the height of `STATS` are checked
- The `OSDn_CHAN_MIN/MAX` ranges do not overlap, and the working switch values do not equal an upper bound
- `OSD_W_BATVOLT` and `OSD_CELL_COUNT` are set for your battery
- Screens 5 and 6 are disabled or cannot be reached with the switch in flight
- `VTX_POWER` and `VTX_OPTIONS` comply with your country's rules; pit mode is tested on the ground

## references
- ArduPilot Copter-4.7.2 AP_OSD.cpp (types, screen switching, warning levels, pre-arm check) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_OSD/AP_OSD.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_OSD_Screen.cpp (items, units, messages, cell count) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_OSD/AP_OSD_Screen.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_OSD_MSP_DisplayPort.cpp (grid, character tables) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_OSD/AP_OSD_MSP_DisplayPort.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_MSP.cpp (MSP_OPTIONS, legacy DJI item mapping) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_MSP/AP_MSP.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_VideoTX.cpp (VTX_*, power table, pit mode) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_VideoTX/AP_VideoTX.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_SerialManager.h (serial protocol numbers) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_SerialManager/AP_SerialManager.h | primary | A
- ArduPilot wiki: DisplayPort OSD (page source) | https://github.com/ArduPilot/ardupilot_wiki/blob/master/common/source/docs/common-displayport.rst | primary | A
- ArduPilot wiki: MSP OSD (page source) | https://github.com/ArduPilot/ardupilot_wiki/blob/master/common/source/docs/common-msp-osd-overview-4.2.rst | primary | A
- ArduPilot wiki: OSD, second OSD, item list (page source) | https://github.com/ArduPilot/ardupilot_wiki/blob/master/common/source/docs/common-osd-overview.rst | primary | A
- ArduPilot wiki: Video Transmitter Support (page source) | https://github.com/ArduPilot/ardupilot_wiki/blob/master/common/source/docs/common-vtx.rst | primary | A
- ArduPilot wiki: OSD based parameter menu (page source) | https://github.com/ArduPilot/ardupilot_wiki/blob/master/common/source/docs/common-paramosd.rst | primary | A
- ArduPilot Discourse: DJI Air Unit O3 and MSP DisplayPort OSD | https://discuss.ardupilot.org/t/dji-air-unit-o3-and-msp-displayport-osd/93549 | secondary | B
- ArduPilot Discourse: DJI O4 OSD configuration | https://discuss.ardupilot.org/t/dji-o4-osd-configuration/144342 | secondary | B

## notes
The values for DJI O3/O4 and the grid for Walksnail come from discussions on the ArduPilot forum, not from the wiki or the source: the 4.7.2 tree has no list of systems with recommended `MSP_OPTIONS` and `OSDn_TXT_RES`. If items at the right edge are cut off in your goggles with grid 1, that is a matter of the goggles' canvas; see `bf-hd-osd-video`.
