---
id: bf-hd-osd-video
title: "Digital video on Betaflight: DJI, Walksnail, HDZero — wiring, OSD and setup"
level: L2
readingTime: 50 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the lab was captured on the 4.5.x source (branch 4.5-maintenance, 7dcc851; version.h 4.5.6, the latest release is 4.5.5) · INAV 9.1 (checked against 9.1.0) · ArduPilot 4.7 (checked against 4.7.3)
status: published
added: 2026-11-14
tags:
  - digital video
  - HD OSD
  - MSP DisplayPort
  - DJI
  - Walksnail
  - HDZero
related:
  - link-digital-video
  - link-vtx
  - bf-modes-osd
  - bf-ports
  - bf-cli
  - el-power-design
  - bf-setup-scratch
  - inav-setup-scratch
  - ap-setup-scratch
  - bf-custom
next: []
source: content/betaflight/bf-hd-osd-video.md
source_hash: 9866b45dcc30
---

## summary
The overview of the four digital video families is in `link-digital-video`, and the analog VTX tables are in `link-vtx`. Here — how to connect a specific air unit to a Betaflight 2025.12 flight controller so that it does not burn out, the OSD appears in the goggles, and recording and power are set up. For DJI (O3, O4, the old Air Unit and Vista), Walksnail Avatar and HDZero: power, wiring, the port mask, `osd_displayport_device`, `vcd_video_system`, the canvas, fonts and the boot logo (analog and HD), the goggles side, the power-up order, heat, recording, power, latency and the equivalents in INAV and ArduPilot. The lab is a Python calculator following the firmware logic (port masks, the `isSerialConfigValid()` check, moving OSD elements between canvases per `osd.h`), then the bench: continuity checks, a fan, the link, OSD, recording.

## theory
### Who does what
In a digital system the goggles draw the OSD. The flight controller only says which character to draw in which cell of the grid: the MSP DisplayPort commands (`MSP_DP_WRITE_STRING`, `MSP_DP_DRAW_SCREEN`, heartbeat) travel over a single UART. Over the same UART the air unit can control the VTX over MSP (channel, power, pit mode) and tells the flight controller the size of its grid — the canvas. So HD video needs three things: correct UART wiring, the correct port function mask and the HD mode of the OSD. If even one is missing, you get the number one forum question: there is video but no OSD.

### Three systems: power and wires
The figures are taken from the manufacturers' documentation (links in the references). Power is the main thing that sets models apart within one system.

| System / model | Power per the specification | Where to take it from | UART (air unit wire → FC pad) | RC from the goggles | Latency (claimed) |
|---|---|---|---|---|---|
| DJI FPV Air Unit (2019) | 7.4–17.6 V, 4–9 W | VBAT 2S–4S | MSP over a UART | DJI radio → S.Bus | < 28 ms 720p/120 |
| Caddx Vista | 7.4–26.4 V | VBAT 2S–6S | as for the Air Unit | the same | 21–28 ms 720p/120 |
| DJI O3 Air Unit | 7.4–26.4 V (2S–6S) | VBAT or a BEC | white UART_RX → TX, gray UART_TX → RX, black and brown — grounds | yellow DJI HDL/S.Bus → the S.Bus pad | < 28 ms 810p/120 (Goggles V2), 30 ms 1080p/100 (Goggles 2) |
| DJI O4 Air Unit | 3.7–13.2 V, BEC ≥ 10 W | a BEC only (5 V/2 A) | the same colors | the same | from 20 ms 1080p/100 (Goggles 3) |
| DJI O4 Air Unit Pro | 7.4–26.4 V, BEC ≥ 13.5 W | VBAT or a 9 V/1.5 A BEC | the same colors | the same | from 15 ms 1080p/100 (Goggles 3) |
| Walksnail Avatar HD Pro | 6–25.2 V | VBAT (6S — with a 50 V/47 µF capacitor) | air unit RX → TX, air unit TX → RX | no, a separate receiver | 22 ms on average |
| Walksnail Avatar Mini V3 | 3.1–13 V (1–3S) | 4S and above — only through a BEC | the same | no | 22 ms on average |
| HDZero Race V3 | 4–12 V, 5–6 W | a 5–12 V BEC | white TX → RX, yellow RX → TX | no | model: ≈ 3 ms + the frame period (14 ms at 90 fps) |
| HDZero Freestyle V2 | 7–25 V, 6–15 W | a BEC is recommended | yellow RX → TX, white TX → RX | no | the same |

The rules that follow from the table:
- Do not power an air unit with an upper limit of 13 V directly from 4S: a charged 3S LiHV is 13.05 V, a 4S is 16.8 V. HDZero says explicitly that, except for the Freestyle of the second batch and newer, their VTXs are not rated for 6S VBAT, and recommends a BEC: it suppresses the voltage spikes that kill VTXs. The “10V/12V HD” pad on a flight controller usually suits any air unit in the table, but its current has to be checked against the 13.5 W of the O4 Pro and the 15 W of the Freestyle V2. The calculation of the branch is in `el-power-design`.
- TX↔RX are always crossed over, 3.3 V logic. DJI has two ground wires: power and signal. Both go to the flight controller.
- Only DJI has control from the goggles. The yellow S.Bus wire is connected to the flight controller's S.Bus pad, `serialrx_provider = SBUS`, and on an F4 — the pad with an inverter (`bf-ports`). If control goes over ELRS, the yellow wire is not connected, and the receiver goes on its own UART with CRSF.
- SoftSerial is no good for DisplayPort: HDZero forbids it outright, and Betaflight strips MSP off SoftSerial ports when validating the config (see below).

{{diagram:bf-hd-wiring|A worked example: ELRS on UART1, the air unit on UART4 with the mask 131073 = MSP + VTX_MSP; the air unit is powered per its specification — from VBAT or from a BEC only.}}

### The Betaflight side: the port mask
The Ports tab stores for each port a line `serial <id> <mask> <msp_baud> <gps_baud> <telemetry_baud> <blackbox_baud>` (`id`: 0 = UART1 … 9 = UART10, 20 = USB VCP, 30/31 = SoftSerial, 40 = LPUART1). The mask is the sum of the `serialPortFunction_e` bits from `io/serial.h`. Four bits matter for video: MSP = 1, VTX SmartAudio = 2048, VTX Tramp = 8192, **VTX_MSP = 131072** (`1 << 17`). The Peripherals item “VTX (MSP + Displayport)” together with MSP enabled gives the mask **131073**. The value 131072 from the course audit is confirmed by the source (4.5 and 2025.12), but it is the single VTX_MSP bit. The port must have 131073.

What the firmware does with the mask at boot (`io/serial.c`, `config/config.c`; the logic is the same in 4.5 and 2025.12):
1. `isSerialConfigValid()`: VTX_MSP alone is not allowed, only together with MSP or Serial RX. MSP can be on no more than 3 ports, and MSP is mandatory on VCP. MSP and Serial RX on SoftSerial are silently removed. On any violation the **whole** port config is reset to the board defaults, and the receiver “disappears” together with the OSD.
2. The port for DisplayPort is found like this: the first port, other than VCP, that has both MSP and VTX_MSP set. There is no longer a separate variable for selecting the port. `displayport_msp_serial` existed in 4.2–4.3 and was removed in 4.4 (it is not in `settings.c` of the 4.4, 4.5 and 2025.12 branches). The audit called it a 4.4 parameter — that is inaccurate. The DJI O3/O4 manuals and the old Walksnail quickstart still show it with the note “for 4.3”. On both 4.5 and 2025.12 the command `set displayport_msp_serial` returns the error `INVALID NAME`.
3. The baud rate is the `msp_baud` field, 115200. HDZero supports 115200 and 230400 (the Race V3 — only 115200), and DJI and Walksnail specify 115200 in their manuals.

### HD mode and the canvas
- `vcd_video_system = HD`. With HD, `fc/init.c` takes the MSP display regardless of `osd_displayport_device`. The OSD itself must be enabled (`feature OSD`, the OSD switch in Configuration).
- `osd_displayport_device = MSP` (the options are `NONE`, `AUTO`, `MAX7456`, `MSP`, `FRSKYOSD`).
- The defaults depend on the Cloud Build options. If the build has “OSD (HD)” (`USE_OSD_HD`), then `vcd_video_system = HD`, `osd_displayport_device = MSP`, and the canvas is 53×20 (`OSD_HD_COLS/ROWS` in `osd.h`). With only “OSD (SD)” — `AUTO` and 30×16. In a build without the HD option HD cannot be enabled: `displayport_msp.c` rolls `HD` back to `AUTO`. If the build has both options, the default is HD, and for an analog camera you have to set `PAL`/`NTSC`/`AUTO` by hand.
- The canvas is reported by the goggles. When the air unit sends `MSP_SET_OSD_CANVAS`, the flight controller writes `osd_canvas_width/height`. If it was not in HD/MSP before that, it switches by itself, saves the config and **reboots**. One extra reboot on the first connection is normal. The HDZero VTX firmware sends Betaflight the `HD_5018` mode, that is 50×18. For DJI and Walksnail the default 53×20 remains; check the real size with `get osd_canvas` after the link is up.
- An element's position is 16 bits (`osd.h`): x — bits 0–4 plus bit 10 (x up to 63), y — bits 5–9, OSD profiles 1–3 — bits 11–13, the type — bits 14–15. `OSD_POS(x,y) = (x & 31) | ((x << 5) & 0x400) | ((y & 31) << 5)`. At startup `osdInit()` clamps elements that fall outside the canvas to the last column or row. It does not move anything proportionally, so neighboring elements can land on top of each other (step 3 of the practice).
- Fonts: `displayport_msp_fonts` — four font page numbers for the severity levels (normal, info, warning, critical), `0,1,2,3` by default. This is how the firmware (4.5 and 2025.12) colors warnings if the goggles have the four-page color Betaflight font. With a single-page font some elements will disappear — then `set displayport_msp_fonts = 0,0,0,0` (the msp-osd documentation). In 4.3 this was `displayport_msp_attrs`.
- `displayport_msp_col_adjust/row_adjust` work only in the SD mode of the MSP display; with `HD` they are not read.

{{lesson:bf-modes-osd|How to place the elements and build the OSD profiles “full / race / recording”: the `osd_*_pos` bits, the warning and statistics masks, switching with a switch.}}

### The boot logo and the font: what the OSD chip stores and what the goggles store
**What the firmware draws (4.5 and 2025.12).** When the OSD starts, `osdCompleteInitialization()` (`osd/osd.c`) clears the screen and calls `osdDrawLogo()`: 24 × 4 consecutive characters, starting at code 160 (0xA0) up to `SYM_END_OF_FONT` 255 (0xFF), with the top left corner at (`middle − 12`, `middle − 5`) of the canvas. Below the logo are the firmware version and, if CMS is built in, the menu entry hint “MENU:THR MID / + YAW LEFT / + PITCH UP”. If the flight controller has a clock (RTC), a date and time line is shown below. The screen is held for 4 s; throttle or pitch up (> 1750 µs) while disarmed, as well as the flip mode switch (FLIP OVER AFTER CRASH, in 2025.12 — CRASHFLIP), dismiss it earlier. There is no logo as a picture in the firmware: it is 96 font characters, and the goggles show whatever is in cells 160–255 of the font being used to draw.

**Analog: MAX7456 and compatibles.** A character is 12 × 18 pixels at 2 bits each (`OSD_CHAR_WIDTH/HEIGHT`, `drivers/osd.h`), 54 meaningful bytes out of 64 in a record. The whole font, 256 characters, lives in the non-volatile memory (NVM) of the OSD chip itself, not in the flight controller's flash. The firmware writes there only on the `MSP_OSD_CHAR_WRITE` command (`max7456WriteNvm()` in `drivers/max7456.c`; there are no other calls in the source), so reflashing the flight controller does not touch the font or the logo. The 24 × 4 character logo is a 288 × 72 pixel picture.

**Betaflight Configurator 10.10, Font Manager.** A font is an `.mcm` file: the presets default, bold, large, extra_large, betaflight, digital, clarity, vision, impact, impact_mini, or your own file. The “Select custom image…” button accepts a PNG or BMP of exactly 288 × 72 px in three colors: 0,255,0 — green, becomes transparent (pixel code 01), 0,0,0 — black (00), 255,255,255 — white (10). On any other pixel, including those from anti-aliasing on export, the app refuses and prints its coordinates (`src/js/LogoManager.js`). The picture is cut into 96 cells and substituted into characters 160–255 of the font **loaded in the app**. It gets into the chip only with the “Upload Font” button: that writes all 256 characters with `MSP_OSD_CHAR_WRITE` and reboots the flight controller (`FONT.upload()` in `src/js/tabs/osd.js`). Hence the rule: the logo lives in the chip's memory as part of the font, and the next upload of any other font will put that font's logo back into 160–255. The order: select the font → substitute the logo → Upload Font; a course guideline — keep your own `.mcm` with the logo next to the aircraft's `diff all`. Use the app of the same version as the firmware: Configurator 10.10 is designed for API up to 1.46 (4.5), while 2025.12 reports API 1.47 — for that there is Betaflight App 2025.12, where I have not checked the Font Manager against the source. The Font Manager is active only if the OSD device is a MAX7456 or FrSky OSD and it has been detected (the `MSP_OSD_CONFIG` flags in `msp/msp.c`). With `osd_displayport_device = MSP` the button is grayed out.

{{diagram:bf-osd-logo-grid|The logo is font characters 160–255, 24 × 4 cells of 12 × 18 px; Upload Font rewrites all 256 characters, so a new font brings its own logo.}}

**HD: DJI, Walksnail, HDZero and other MSP DisplayPort systems.** The flight controller sends the same codes 160–255, the version and the CMS hint as ordinary characters over MSP, and the picture is drawn by the goggles' font (or the VTX's — where the system keeps its font depends on the system). A font cannot be uploaded to an HD system from Betaflight: in 4.5.3 the MSP display has no character write function, and in 2025.12 it exists only under the `USE_MSP_DISPLAYPORT_FONT` option (the `MSP_DP_FONTCHAR_WRITE` = 7 command, with the comment “New OSD chip works over MSP”), which in the 2025.12.5 sources is defined neither by `common_pre.h` nor by any target (this is a conclusion from the source tree; the Cloud Build options were not checked); the flag is tied to the AIRBOT THEIA OSD chip (`OSD_FLAGS_OSD_HARDWARE_AIRBOT_THEIA_OSD` in `msp/msp.c`). So on HD a custom logo means editing the font on the goggles side per the manufacturer's instructions. **Not verified against the Betaflight sources:** the formats and the way of replacing the font on DJI O3/O4, Walksnail, HDZero and WTFOS; whether their stock fonts have the Betaflight logo in 160–255; whether a custom picture is possible on stock DJI firmware.

**The logo on arming.** `osd_logo_on_arming`: OFF (the default), ON — on every arm, FIRST_ARMING — only on the first arm after power-up. `osd_logo_on_arming_duration` is in tenths of a second, 5–50 (0.5–5 s), default 5 = 0.5 s. Without the logo the ARMED text stays up for the same 0.5 s. While the arming screen is up, the other OSD elements are not drawn: until `resumeRefreshAt` arrives, `osdProcessStats2()` does nothing, and the `osdUpdate()` state machine skips drawing the elements (`osd/osd.c`). 2025.12 added `osd_arming_logo` (0–3, default 0): the severity level with which the logo is drawn on arming. On the MSP display it selects the goggles' font page through `displayport_msp_fonts`, so with a four-page HD font a different picture from page 1–3 can be shown on arming (whether a specific font has one cannot be checked from the sources); the MAX7456 ignores the level. A course guideline: on a racing aircraft — OFF, on the others FIRST_ARMING with 10–15 (1–1.5 s): on the first arm you can see whether it is the right aircraft and the right firmware, and a blind screen on takeoff is not needed any longer than that.

### Reference: variables and commands (2025.12; the names, defaults and ranges are the same as in 4.5)
| Variable / command | Default | Range | Meaning |
|---|---|---|---|
| `serial <id> 131073 115200 …` | per the board | a 32-bit mask | MSP + VTX_MSP: the DisplayPort port |
| `vcd_video_system` | `HD` with OSD (HD) in the build, otherwise `AUTO` | AUTO, PAL, NTSC, HD | HD = the MSP display with a canvas |
| `osd_displayport_device` | `MSP` with OSD (HD), otherwise `AUTO` | NONE, AUTO, MAX7456, MSP, FRSKYOSD | the OSD device |
| `osd_canvas_width` / `osd_canvas_height` | 53 / 20 (HD), 30 / 16 (SD) | 0–63 / 0–31 | the grid; overwritten by the goggles |
| `displayport_msp_fonts` | `0,1,2,3` | 4 values | the font page per severity level |
| `displayport_msp_use_device_blink` | OFF | OFF, ON | blinking is done by the goggles, not the FC |
| `displayport_msp_col_adjust` / `row_adjust` | 0 / 0 | −6…0 / −3…0 | the SD mode of MSP only |
| `osd_framerate_hz` | 12 | 1–60 | the OSD refresh rate |
| `osd_logo_on_arming` | OFF | OFF, ON, FIRST_ARMING | the logo on the arming screen |
| `osd_logo_on_arming_duration` | 5 (0.5 s) | 5–50, in 0.1 s | how long to hold the logo on arming |
| `osd_arming_logo` (2025.12 only) | 0 | 0–3 | the severity level (font page through `displayport_msp_fonts`) for the logo on arming |
| `osd_*_pos` | center, hidden | 0–65535 | `(x & 31) + (y<<5) + ((x>>5)<<10) + (profiles<<11)` |
| `osd_sys_*_pos` (`goggle_voltage`, `vtx_voltage`, `vtx_temp`, `bitrate`, `delay`, `lq`, `goggle_dvr`, `vtx_dvr`, `fan_speed`, `warnings`, `distance`) | hidden | 0–65535 | elements that the goggles draw themselves (`USE_MSP_DISPLAYPORT`) |
| `vtx_power` | 0 | a table index | the power of an MSP VTX (HDZero) |
| `vtx_low_power_disarm` | OFF | OFF, ON, UNTIL_FIRST_ARM | while disarmed an MSP VTX gets index 1 (`vtx_msp.c`) |
| `status` | — | — | the line `OSD: MSP (53 x 20)` — the display type and size |
| `vtx_info` | — | — | what the VTX reported |

`vcd_h_offset`/`vcd_v_offset` apply only to the analog MAX7456 and have nothing to do with HD. For `vtx_low_power_disarm` the audit said that it does not apply to digital. That is not so for VTXs controlled over MSP (in both 4.5 and 2025.12): `prepareMspFrame()` sends power index 1 while the aircraft is not armed, but only when a VTX table is loaded (otherwise the MSP VTX status never becomes READY). HDZero fills in the table itself. Whether DJI and Walksnail have an MSP VTX depends on the air unit firmware — check with the Video Transmitter tab.

### The goggles side
- **DJI O3/O4.** According to the DJI manual, Canvas mode works with Betaflight 4.3+. The set of elements and their places are defined in Betaflight; the goggles menu has no separate layout. Power, channel, bandwidth and recording (`Record With`, `Auto Record on Takeoff`) are set in the goggles menu, and analog VTX tables are not needed. The linking order: first the air unit with the goggles, then the radio.
- **The old DJI FPV Air Unit/Vista.** The stock firmware draws DJI's own OSD from MSP data: up to 24 elements, firmware v01.00.02.00 (2019). The port is MSP only (mask 1). The full Betaflight OSD through DisplayPort is provided by the unofficial WTFOS with the msp-osd package. It is installed on the goggles and on every air unit, and the flight controller is set up as for HD (mask 131073, `vcd_video_system = HD`).
- **Walksnail Avatar.** The OSD is “Canvas mode”. The flight controller is set up the same way: Peripherals “VTX (MSP + Displayport)”, `osd_displayport_device = MSP`, `vcd_video_system = HD`. Standby mode lowers the power while the aircraft is not armed.
- **HDZero.** The VTX fills in the flight controller's VTX table itself. Power and channel are set from Betaflight (the Video Transmitter tab, CMS) or from the VTX menu: `LP_MODE` (25 mW until arming), `PIT_MODE` (P1MW = 0.1 mW, 0MW), stick commands for leaving 0 mW. The `VTX PIT MODE` mode on a switch (`bf-modes-osd`) and `vtx_low_power_disarm` reach the VTX over the same MSP. The blue LED blinks three times after boot if MSP communication is detected. There is no recording on the VTX; the DVR is in the goggles.

### Power-up order, heat, recording
- Connect the antenna before power (Walksnail explicitly forbids powering up without an antenna).
- First the goggles, then the aircraft battery. When connecting over USB, first the battery, then USB: HDZero warns that the VTX may fail to boot if the battery is connected to a flight controller that is already connected to a PC.
- Heat. After power-up DJI keeps the air unit in low-power mode until takeoff or the start of recording, and shuts it down if it overheats on the ground. In flight, on overheating the recording stops, and if the heating continues the quality is reduced. The time on the bench from a cold start at 25 °C without airflow: the O4 Pro about 20 min, the O4 about 2.5 min. Walksnail alternates red and green blinking on overheating. HDZero blinks three short flashes: that is overheat protection, and on the Freestyle the RF is then turned off until arming or a power cycle. All three manufacturers say: on the bench a fan is needed. P1MW on HDZero heats too; for a break use 0MW.
- Recording. The O3 — to the air unit's built-in memory. The O4 — per the `Record With` setting in the goggles, and recording does not start while the air unit is on the ground in low-power mode. Walksnail — to the air unit's built-in memory (8 GB on the Mini V3, 32 GB in the HD Pro kit), 1080p/720p. HDZero — only the goggles DVR, a recording of what arrived over the radio.

### Power and the law
EIRP per the specifications. DJI O3/O4 Pro: FCC < 33 dBm (≈ 2 W), CE < 14 dBm (25 mW), SRRC < 30 dBm. Walksnail: FCC < 30 dBm (the Mini V3 — < 27 dBm), CE < 14 dBm, MIC < 25 dBm, and channels 1, 2, 6, 7 in FCC regions fall into the amateur band. HDZero: 25/200 mW, with 500 mW and 1 W only under an amateur radio license and separate firmware. The mode (FCC/CE) is selected in the goggles according to the rules of your country. In the EU only CE, < 14 dBm, is allowed. More power means more heat and more interference for the neighbors, while adding little range (`rf-link-budget`).

### INAV and ArduPilot — briefly
| | Betaflight 2025.12 | INAV 9.1 | ArduPilot 4.7 |
|---|---|---|---|
| Port function | VTX (MSP + Displayport), mask 131073 | MSP DisplayPort (`FUNCTION_MSP_OSD` = 1 << 25) | `SERIALn_PROTOCOL = 42` (DisplayPort); 33 — the old “DJI FPV” |
| OSD type | `osd_displayport_device = MSP` | the port selection | `OSD_TYPE = 5` (MSP_DISPLAYPORT); 3 — MSP |
| Grid | `vcd_video_system = HD`, the canvas from the goggles | `osd_video_system` = HDZERO, DJIWTF, AVATAR, BF43COMPAT, BFHDCOMPAT, DJI_NATIVE | set by the flight controller, per screen: `OSDn_TXT_RES` 0 — 30×16 (the default: HD goggles will show the SD grid), 1 — 50×18, 2 — 60×22; `MSP_OPTIONS` bit 2 — Betaflight symbols, bit 3 — INAV (bit 0 — only for protocol 33); the full table by system — `ap-osd-video` |
| Baud rate | 115200 | 115200 | `SERIALn_BAUD = 115` |

Which INAV 9.1 value (the same in 8.0.1) to set for each system: HDZero — HDZERO (50×18), Walksnail — AVATAR (53×20), DJI O4 and goggles with the INAV font — DJI_NATIVE (53×20, OSD type “INAV” in the goggles), DJI O3 on stock firmware — BFHDCOMPAT (53×20, the Betaflight font, some icons shown as “?”), Air Unit/Vista under WTFOS — DJIWTF (60×22), old DJI without WTFOS — BF43COMPAT (30×16).

The bit numbers in the masks differ between firmwares: 131072 in INAV is `FUNCTION_VTX_FFPV`. `serial` lines are not copied between firmwares.

### How 4.5 differs and what comes next
The names and ranges of all the variables in the reference are the same in 4.5 and 2025.12. In 2025.12 `diff` writes ports by name (`serial UART4 131073 …`; in 4.5 — by number, `serial 3 131073 …`, and 2025.12 accepts such lines), the `FUNCTION_GIMBAL` = 262144 bit was added, and the OSD type (analog or HD) is a separate Cloud Build option: without `USE_OSD_HD` in the build DisplayPort will not work with any mask. In the 2026.12 development branch ports are assigned with `*_uart` variables (`msp_uart_2 = UART4`). That is not a release yet.

### Place in the system

- **Receives:** power for the air unit from VBAT or a BEC per its specification (`el-power-design`); a free hardware UART and the MSP + VTX_MSP mask (`bf-ports`); the “OSD (HD)” option in the build (`bf-custom`); the canvas size — from the goggles.
- **Provides:** MSP DisplayPort commands — to the goggles, which draw the OSD (`link-digital-video`, `bf-modes-osd`); the power index and pit mode — to a VTX controlled over MSP (`link-vtx`).
- **If you get it wrong here:** the port has the VTX_MSP bit alone without MSP, or MSP ended up on a fourth port → the firmware resets the whole port config to defaults, and the receiver “disappears” together with the OSD: arming is blocked by the `RXLOSS` flag (`bf-ports`, `bf-arming-safety`). An air unit with a 13 V limit is powered directly from 4S → voltage spikes kill it; the calculation of the branch is in `el-power-design`.

## practice
### Step 1. Port masks from the source
Everything in the lab is Python that repeats the firmware logic. The script and the output were captured on the 4.5.x source (branch `4.5-maintenance`, commit `7dcc851`: `version.h` says 4.5.6, but there is no such release; the latest release is 4.5.5, and the `src/` code matches it except for the version number in `version.h`); `isSerialConfigValid()`, the search for the DisplayPort port, `telemetryCheckRxPortShared()` and the `OSD_POS` macros did not change in 2025.12 (only GIMBAL = 1 << 18 was added to the bit table, and MAVLINK to the list of receivers with telemetry on their own port), and the `serial` lines in the scenarios are written with port numbers, as in a 4.5 `diff`. SITL does not help here: it has no OSD and no VTX. The file `hd_osd_calc.py` consists of three blocks: this one, the block of step 3 and the `__main__` at the end of step 3. The first block decomposes a mask and validates a port config. On startup the bit table is checked against `src/main/io/serial.h`.

```python
import re, sys

FUNC = {  # Betaflight 4.5 io/serial.h, serialPortFunction_e
    "MSP": 1 << 0, "GPS": 1 << 1, "TELEMETRY_FRSKY_HUB": 1 << 2, "TELEMETRY_HOTT": 1 << 3,
    "TELEMETRY_LTM": 1 << 4, "TELEMETRY_SMARTPORT": 1 << 5, "RX_SERIAL": 1 << 6,
    "BLACKBOX": 1 << 7, "TELEMETRY_MAVLINK": 1 << 9, "ESC_SENSOR": 1 << 10,
    "VTX_SMARTAUDIO": 1 << 11, "TELEMETRY_IBUS": 1 << 12, "VTX_TRAMP": 1 << 13,
    "RCDEVICE": 1 << 14, "LIDAR_TF": 1 << 15, "FRSKY_OSD": 1 << 16, "VTX_MSP": 1 << 17,
}
TLM_SHAREABLE = FUNC["TELEMETRY_FRSKY_HUB"] | FUNC["TELEMETRY_LTM"] | FUNC["TELEMETRY_MAVLINK"]
TLM_PORT = TLM_SHAREABLE | FUNC["TELEMETRY_HOTT"] | FUNC["TELEMETRY_SMARTPORT"]
SHARABLE_WITH_MSP = FUNC["BLACKBOX"] | TLM_PORT | FUNC["VTX_MSP"]
MAX_MSP_PORT_COUNT = 3                                   # msp/msp_serial.h
RX_TLM_SHARED = {"SPEKTRUM1024", "SPEKTRUM2048", "SBUS", "SUMD", "SUMH", "XB-B", "XB-B-RJ01", "IBUS"}
PORT_NAME = {20: "VCP", 30: "SOFTSERIAL1", 31: "SOFTSERIAL2", 40: "LPUART1",
             **{i: f"UART{i + 1}" for i in range(10)}}


def check_source(path):
    src = open(path, encoding="utf-8").read()
    found = {m.group(1): 1 << int(m.group(2))
             for m in re.finditer(r"FUNCTION_(\w+)\s*=\s*\(1 << (\d+)\)", src)}
    assert found == FUNC, f"table differs from {path}: {set(found.items()) ^ set(FUNC.items())}"
    print(f"function table == {path.split('/src/')[-1] if '/src/' in path else path}: {len(found)} bits OK")


def encode(*names):
    return sum(FUNC[n] for n in names)


def decode(mask):
    names = [n for n, b in FUNC.items() if mask & b]
    rest = mask & ~sum(FUNC.values())
    return names + ([f"UNKNOWN(0x{rest:X})"] if rest else [])


def rx_port_shared(mask, provider):            # telemetry.c telemetryCheckRxPortShared (4.5)
    if mask & FUNC["RX_SERIAL"] and mask & TLM_SHAREABLE and provider in RX_TLM_SHARED:
        return True
    if mask & FUNC["TELEMETRY_IBUS"] and mask & FUNC["RX_SERIAL"] and provider == "IBUS":
        return True
    return bool(mask & FUNC["RX_SERIAL"] and mask & FUNC["VTX_MSP"])   # USE_MSP_OVER_TELEMETRY


def validate(lines, provider="CRSF"):
    """Returns (ok, notes, displayport_port). Mirrors isSerialConfigValid() order of checks."""
    ports, notes = [], []
    for ln in lines:
        p = ln.split()
        pid, mask, msp_baud = int(p[1]), int(p[2]), int(p[3])
        if not 9600 <= msp_baud <= 1000000:
            notes.append(f"{ln}: CLI rejects msp baud {msp_baud} (allowed 9600..1000000)")
        ports.append((pid, mask, msp_baud))
    msp_ports = 0
    for pid, mask, _ in ports:
        name = PORT_NAME.get(pid, str(pid))
        if pid in (30, 31) and mask & (FUNC["MSP"] | FUNC["RX_SERIAL"]):
            notes.append(f"{name}: MSP/Serial RX silently removed (not allowed on SoftSerial)")
            mask &= ~(FUNC["MSP"] | FUNC["RX_SERIAL"])
        if mask & FUNC["MSP"]:
            msp_ports += 1
        elif pid == 20:
            return False, notes + ["VCP without MSP -> INVALID"], None
        bits = bin(mask).count("1")
        if mask & FUNC["VTX_MSP"] and bits == 1:
            return False, notes + [f"{name}: VTX_MSP alone -> INVALID (must share with MSP or Serial RX)"], None
        if bits > 1:
            if bits > bin(FUNC["MSP"] | SHARABLE_WITH_MSP).count("1"):
                return False, notes + [f"{name}: too many shared functions -> INVALID"], None
            if mask & FUNC["MSP"] and mask & SHARABLE_WITH_MSP:
                pass
            elif rx_port_shared(mask, provider):
                pass
            else:
                return False, notes + [f"{name}: {'+'.join(decode(mask))} cannot share a port -> INVALID"], None
    if msp_ports == 0 or msp_ports > MAX_MSP_PORT_COUNT:
        return False, notes + [f"{msp_ports} MSP ports (allowed 1..{MAX_MSP_PORT_COUNT}) -> INVALID"], None
    dp = next((pid for pid, mask, _ in sorted(ports)
               if pid != 20 and mask & FUNC["MSP"] and mask & FUNC["VTX_MSP"]), None)
    if dp is not None:
        baud = next(b for pid, _, b in ports if pid == dp)
        if baud != 115200:
            notes.append(f"{PORT_NAME[dp]}: MSP baud {baud}; DJI, Walksnail and HDZero Race V3 expect 115200")
    return True, notes, dp
```

To run it: `python3 hd_osd_calc.py betaflight/src/main/io/serial.h` (a clone of the 4.5-maintenance branch; on the `serial.h` from 2025.12.5 the script will report the extra GIMBAL bit). The beginning of the output:

```text
function table == main/io/serial.h: 17 bits OK

== 1. masks
 131073 = MSP + VTX_MSP
 131072 = VTX_MSP
     64 = RX_SERIAL
 131201 = MSP + BLACKBOX + VTX_MSP
   2048 = VTX_SMARTAUDIO
encode(MSP, VTX_MSP) = 131073
```

The table of 17 bits matched the source. Write down in your notes the mask of your own video port and its decomposition.

### Step 2. Five port configs: which one will load
A worked example — a 5″ 6S: ELRS on UART1, the air unit on UART4. Five `serial` variants are run through `validate()`:

```text
== 2. port configs (serialrx_provider shown in brackets)
A good: ELRS UART1 + HD on UART4 [CRSF]: VALID; DisplayPort on UART4
B VTX bit only on UART4 [CRSF]: INVALID -> whole serial config reset to defaults
    UART4: VTX_MSP alone -> INVALID (must share with MSP or Serial RX)
C DJI SBUS on UART2, MSP only on UART4 [SBUS]: VALID; no DisplayPort port
D four MSP ports [CRSF]: INVALID -> whole serial config reset to defaults
    4 MSP ports (allowed 1..3) -> INVALID
E HD on UART4 at 230400 [CRSF]: VALID; DisplayPort on UART4
    UART4: MSP baud 230400; DJI, Walksnail and HDZero Race V3 expect 115200
```

What follows from this:
- B is the mask 131072, taken from the bit table without MSP. The firmware will reset **all** the ports, and the receiver will disappear together with the OSD. This is the nastiest error: from the outside it looks like “the settings got wiped”.
- C is a stock old DJI (Vista/Air Unit): the port is MSP only, and DJI draws the OSD itself. For the O3/O4 and WTFOS the same config means “there is video but no OSD”.
- E — the config will load, but the Race V3 works only at 115200. The other HDZero units cycle through 115200/230400 themselves, and DJI and Walksnail, per the documentation, expect 115200.
- D — MSP on VCP, UART1, UART2 and UART4: a fourth port with MSP is not allowed.

### Step 3. The canvas: from analog to HD and between systems
The second part of the file moves a layout of elements. The functions `osd_pos`/`osd_xy` are the macros `OSD_POS`/`OSD_X`/`OSD_Y`. `fw_clamp` repeats what `osdInit()` does. `edge_map` is the calculator's own rule; the firmware does not have it: elements in the outer quarters keep their distance to their edge, and the central half shifts together with the center.

```python
def osd_pos(x, y, profiles=(1,), typ=0):
    v = (x & 31) | ((x << 5) & 0x400) | ((y & 31) << 5)      # OSD_POS(x, y): x bit 5 -> bit 10
    for p in profiles:
        v |= 1 << (p - 1 + 11)                               # OSD_PROFILE_FLAG(p)
    return v | ((typ & 3) << 14)                             # OSD_TYPE bits 14-15


def osd_xy(v):
    return (v & 31) | ((v & 0x400) >> 5), (v >> 5) & 31     # OSD_X(v), OSD_Y(v)


def osd_profiles(v):
    return [p for p in (1, 2, 3) if v & (1 << (p - 1 + 11))]


def fw_clamp(v, cols, rows):                                 # osd.c osdInit(): what the FC itself does
    x, y = osd_xy(v)
    keep = v & (0x3800 | 0xC000)                             # OSD_PROFILE_MASK | OSD_TYPE_MASK
    return keep | osd_pos(min(x, cols - 1), min(y, rows - 1), profiles=())


def edge_map(v, src, dst):
    """Own rule: outer quarters keep their distance to that edge, the middle half shifts with the centre."""
    (sc, sr), (dc, dr) = src, dst
    x, y = osd_xy(v)
    nx = x if x < sc / 4 else (dc - (sc - x) if x >= 3 * sc / 4 else x + (dc - sc) // 2)
    ny = y if y < sr / 4 else (dr - (sr - y) if y >= 3 * sr / 4 else y + (dr - sr) // 2)
    return (v & (0x3800 | 0xC000)) | osd_pos(nx, ny, profiles=())
```

The `__main__` block — the same calls with the data of the example:

```python
if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_source(sys.argv[1])

    print("\n== 1. masks")
    for m in (131073, 131072, 64, 1 + 128 + 131072, 2048):
        print(f"{m:>7} = {' + '.join(decode(m))}")
    print("encode(MSP, VTX_MSP) =", encode("MSP", "VTX_MSP"))

    print("\n== 2. port configs (serialrx_provider shown in brackets)")
    cases = {
        "A good: ELRS UART1 + HD on UART4": (["serial 20 1 115200 57600 0 115200",
            "serial 0 64 115200 57600 0 115200", "serial 3 131073 115200 57600 0 115200"], "CRSF"),
        "B VTX bit only on UART4": (["serial 20 1 115200 57600 0 115200",
            "serial 0 64 115200 57600 0 115200", "serial 3 131072 115200 57600 0 115200"], "CRSF"),
        "C DJI SBUS on UART2, MSP only on UART4": (["serial 20 1 115200 57600 0 115200",
            "serial 1 64 115200 57600 0 115200", "serial 3 1 115200 57600 0 115200"], "SBUS"),
        "D four MSP ports": (["serial 20 1 115200 57600 0 115200", "serial 0 1 115200 57600 0 115200",
            "serial 1 1 115200 57600 0 115200", "serial 3 131073 115200 57600 0 115200"], "CRSF"),
        "E HD on UART4 at 230400": (["serial 20 1 115200 57600 0 115200",
            "serial 0 64 115200 57600 0 115200", "serial 3 131073 230400 57600 0 115200"], "CRSF"),
    }
    for title, (lines, prov) in cases.items():
        ok, notes, dp = validate(lines, prov)
        print(f"{title} [{prov}]: {'VALID' if ok else 'INVALID -> whole serial config reset to defaults'}"
              f"{'; DisplayPort on ' + PORT_NAME[dp] if dp is not None else ('; no DisplayPort port' if ok else '')}")
        for n in notes:
            print("   ", n)

    print("\n== 3. OSD positions: analog PAL 30x16 layout -> HD")
    sd = {  # element: (x, y) on the analog canvas, profile 1
        "osd_craft_name_pos": (11, 0), "osd_link_quality_pos": (23, 1),
        "osd_flymode_pos": (13, 14), "osd_avg_cell_voltage_pos": (1, 14),
        "osd_mah_drawn_pos": (1, 13), "osd_tim_2_pos": (23, 14), "osd_warnings_pos": (9, 10),
    }
    print(f"{'element':26}{'SD x,y':>8}{'value':>7}{'53x20 edge':>12}{'value':>7}{'50x18 edge':>12}{'value':>7}")
    hd53 = {}
    for name, (x, y) in sd.items():
        v = osd_pos(x, y)
        assert osd_xy(v) == (x, y) and osd_profiles(v) == [1]
        a, b = edge_map(v, (30, 16), (53, 20)), edge_map(v, (30, 16), (50, 18))
        hd53[name] = a
        print(f"{name:26}{x:>4},{y:<3}{v:>7}{'%d,%d' % osd_xy(a):>12}{a:>7}{'%d,%d' % osd_xy(b):>12}{b:>7}")

    print("\n== 4. firmware clamp: the 53x20 layout booted on HDZero (50x18) and on analog (30x16)")
    for name, v in hd53.items():
        h, s = fw_clamp(v, 50, 18), fw_clamp(v, 30, 16)
        print(f"{name:26} {'%d,%d' % osd_xy(v):>6} -> 50x18 {'%d,%d' % osd_xy(h):>6}   -> 30x16 {'%d,%d' % osd_xy(s):>6}")

    print("\n== 5. CLI for the 53x20 layout")
    for name, v in hd53.items():
        print(f"set {name} = {v}")
```

Input data: an analog PAL 30×16 layout from profile 1. The output:

```text
== 3. OSD positions: analog PAL 30x16 layout -> HD
element                     SD x,y  value  53x20 edge  value  50x18 edge  value
osd_craft_name_pos          11,0     2059        22,0   2070        21,0   2069
osd_link_quality_pos        23,1     2103        46,1   3118        43,1   3115
osd_flymode_pos             13,14    2509       24,18   2648       23,16   2583
osd_avg_cell_voltage_pos     1,14    2497        1,18   2625        1,16   2561
osd_mah_drawn_pos            1,13    2465        1,17   2593        1,15   2529
osd_tim_2_pos               23,14    2519       46,18   3662       43,16   3595
osd_warnings_pos             9,10    2377       20,12   2452       19,11   2419

== 4. firmware clamp: the 53x20 layout booted on HDZero (50x18) and on analog (30x16)
osd_craft_name_pos           22,0 -> 50x18   22,0   -> 30x16   22,0
osd_link_quality_pos         46,1 -> 50x18   46,1   -> 30x16   29,1
osd_flymode_pos             24,18 -> 50x18  24,17   -> 30x16  24,15
osd_avg_cell_voltage_pos     1,18 -> 50x18   1,17   -> 30x16   1,15
osd_mah_drawn_pos            1,17 -> 50x18   1,17   -> 30x16   1,15
osd_tim_2_pos               46,18 -> 50x18  46,17   -> 30x16  29,15
osd_warnings_pos            20,12 -> 50x18  20,12   -> 30x16  20,12

== 5. CLI for the 53x20 layout
set osd_craft_name_pos = 2070
set osd_link_quality_pos = 3118
set osd_flymode_pos = 2648
set osd_avg_cell_voltage_pos = 2625
set osd_mah_drawn_pos = 2593
set osd_tim_2_pos = 3662
set osd_warnings_pos = 2452
```

A check by hand: LQ at the point (46, 1) gives 46 & 31 = 14, bit 5 of x = 1 → 1024, y = 1 → 32, profile 1 → 2048. The sum is 3118 — it matches. The conclusions:
1. When moving from analog to HD the firmware clamps nothing: 30×16 fits entirely within 53×20, but the whole layout stays in the top left corner. You have to rearrange the elements yourself, from the table or in the OSD tab.
2. A layout made for 53×20 and loaded onto an HDZero at 50×18 breaks: `osdInit()` clamps the voltage (1,18) to row 17, and it lands on mAh (1,17). Each system needs its own layout. Keep it in a separate `diff`; OSD profiles are no good for this: they share one canvas.
3. The same HD config on analog: LQ and the timer are clamped to column 29, and the text is cut off by the right edge.

### Step 4. A config for the three systems (a procedure from the documentation)
Betaflight App: Ports → UART4 → Peripherals “VTX (MSP + Displayport)”, MSP enabled, 115200 → Save and Reboot; Configuration → OSD enabled; OSD → Video Format HD. The same in the CLI (the common part for O3/O4, Walksnail, HDZero and DJI V1 with WTFOS):

```text
serial UART4 131073 115200 57600 0 115200
set osd_displayport_device = MSP
set vcd_video_system = HD
set displayport_msp_fonts = 0,1,2,3
save
```

On 4.5 the first line is written with the port number: `serial 3 131073 115200 57600 0 115200`. DJI with control from a DJI radio: add `serial UART2 64 115200 57600 0 115200` (in 4.5 — `serial 1 64 …`; UART2, to which the S.Bus pad is routed) and `set serialrx_provider = SBUS`. HDZero: do not enter a VTX table, the VTX will load it. For racing — `set vtx_low_power_disarm = UNTIL_FIRST_ARM`. Save three `diff all` outputs and compare them line by line: only the receiver, the `osd_*_pos` layout and `vtx_*` should differ.

### Moving to real hardware
Propellers are off in all steps. Flying is needed only in step 6.
1. **Continuity checks before power.** A multimeter: + and − of the air unit's power wire — no short. The voltage on the pad the air unit connects to is measured with power from the battery through a smoke stopper, but **with the air unit disconnected**. The value must fall within the range from the table: for example, a 9–12 V BEC for the O4 and Race V3, but not 4S VBAT. Check continuity from air unit TX → flight controller RX and the other way around, and the grounds to GND.
2. **The bench with airflow.** The antenna is connected, and a fan is pointed at the air unit. The order: goggles → battery → USB. If the air unit heats up so much that the protection triggered (LED, a warning in the goggles), stop the bench session. The time until the O4 trips without airflow is 2.5 min, and it must not be exceeded.
3. **The first link and the OSD.** Linking per the system's manual. After boot: `status` shows `OSD: MSP (… x …)`, `get osd_canvas` — the size from the goggles (HDZero 50×18). On HDZero the blue LED blinked 3 times. The voltage, LQ and mode are visible in the goggles. Arming without propellers checks that the warnings (`ARMING_DISABLED`) are drawn, and that on HDZero/an MSP VTX the power leaves LP.
4. **Power.** In CE mode set 25 mW. On HDZero check the Video Transmitter tab: type MSP, power from the table.
5. **Recording.** 60 s of recording on the bench. The file opens on a PC, and the OSD (if it is recorded) and the time are visible in it. Note where the recording goes: the air unit or the goggles.
6. **Flight.** A 60 s hover, then a circuit of 2–3 minutes. The OSD warnings are visible, and recording started by itself (`Auto Record on Takeoff` on DJI). Latency is measured by the method from `link-digital-video`.

Abort: a smell, the overheat protection blinking, the receiver disappearing after saving Ports (a sign of a config reset), the OSD blinking or disappearing in flight.

Self-check: the lab is complete when:
- **Calculation (without hardware)**: `hd_osd_calc.py` has been run against the `serial.h` of the 4.5 branch (the line `17 bits OK`; for 2025.12 note in your notes that the GIMBAL bit was added). For your own aircraft your notes contain the `serial` line and the decomposition of the mask (the sum of the bits equals the mask, as 131073 = MSP + VTX_MSP), the `validate()` verdict (VALID, DisplayPort on the right UART), a table of `set osd_*_pos` for the canvas of your system in which at least one position is recalculated by hand following the LQ check (46, 1) → 3118, and the list of elements that `osdInit()` would clamp on another canvas — it matches part 4 of the script output on your layout.
- **Hardware**: the wiring table is filled in (wire → pad, the pad voltage from the battery with the air unit disconnected), airflow was running on the bench, `status` and `get osd_canvas` are written down, the OSD is visible in the goggles, and there is a 60-second recording with the storage medium noted. Power is set according to the rules of your country, and the `diff all` after setup is saved in the aircraft's folder.

**Reference for self-check.** The correct result of the calculation: the script prints `17 bits OK`, your aircraft's config gives `VALID; DisplayPort on UART…` with the right port, and the `osd_*_pos` values decode back into the same x, y. The verdict `INVALID -> whole serial config reset to defaults` most often means the mask 131072 (VTX_MSP without MSP, variant B) or a fourth port with MSP (variant D). `VALID; no DisplayPort port` — the port has MSP only (variant C): there will be video but no OSD. When checking another canvas the reference is part 4 of the output: a 53×20 layout on 50×18 loses row 18 (the voltage lands on mAh in row 17), and on 30×16 the elements to the right of column 29 are clamped to it and cut off.

{{diagram:bf-hd-no-osd|“There is video but no OSD”: first the mask 131073, then HD mode and the OSD, then the UART communication, and only then the goggles settings.}}

## diagnostics
- **Symptom:** there is video, but no OSD in the goggles (question No. 11)
  - Possible cause: the port mask is 1 or 131072 instead of 131073; `vcd_video_system` is not HD; the OSD is off; TX/RX are not crossed over; the port is SoftSerial.
  - What to do: `serial` → the mask 131073 on the air unit's UART, `get vcd_video_system`, `feature OSD`, continuity checks; the decision tree is below.
- **Symptom:** after saving Ports the receiver disappeared, and the ports went back to defaults
  - Possible cause: VTX_MSP without MSP or a fourth port with MSP — `isSerialConfigValid()` reset the whole port config.
  - What to do: `validate()` from the practice, then fix the mask and check the number of ports with MSP (≤ 3).
- **Symptom:** `set displayport_msp_serial = 3` → `INVALID NAME`
  - Possible cause: the variable was removed in 4.4, and the instructions were written for 4.3.
  - What to do: nothing needs to be entered — the port is determined by the mask 131073.
- **Symptom:** the OSD has moved into the top left corner, or elements overlap each other
  - Possible cause: a layout from SD (30×16) or from another HD canvas; `osdInit()` only clamps to the edge.
  - What to do: a layout for your own canvas (`get osd_canvas`), a separate `diff` per system.
  - Consequences: voltage covered by mAh cannot be seen in flight.
- **Symptom:** some OSD elements or warnings are not drawn, the rest are in place
  - Possible cause: `displayport_msp_fonts = 0,1,2,3` with a single-page font in the goggles.
  - What to do: the color Betaflight font in the goggles, or `set displayport_msp_fonts = 0,0,0,0`.
- **Symptom:** on the first connection of the goggles the flight controller rebooted by itself
  - Possible cause: the goggles sent `MSP_SET_OSD_CANVAS` while the FC was not in HD/MSP — the firmware switched, saved and rebooted.
  - What to do: nothing, this is normal; check that `get vcd_video_system` = HD.
- **Symptom:** the air unit shuts down or the recording is cut off on the bench
  - Possible cause: overheating without airflow; for the O4 a cold start without airflow is about 2.5 min.
  - What to do: a fan, do not keep it powered on the ground; HDZero — 0MW instead of P1MW.
- **Symptom:** the HDZero VTX did not boot (no blue LED) with USB connected
  - Possible cause: the battery was connected to a flight controller already connected to a PC.
  - What to do: first the battery, then USB; VTX power within the specification.
- **Symptom:** the DJI radio is linked, but the bars in Receiver do not move
  - Possible cause: the yellow S.Bus wire is not on the S.Bus pad (an F4 without an inverter), `serialrx_provider` is not SBUS.
  - What to do: the S.Bus pad, Serial RX on that UART, `serialrx_provider = SBUS` (`bf-ports`).
- **Symptom:** your own logo is gone, and the standard one is back at power-up (analog)
  - Possible cause: another font was uploaded — “Upload Font” rewrites all 256 characters, including 160–255 with the logo.
  - What to do: select the font, substitute the 288 × 72 picture again, Upload Font; keep your own `.mcm` with the logo.
- **Symptom:** the Font Manager is grayed out, or “Select custom image…” refuses
  - Possible cause: the OSD device is MSP (HD) or the MAX7456 was not detected; the picture is not 288 × 72 px or has pixels outside the three colors (anti-aliasing, a PNG with a palette of shades).
  - What to do: for HD the font is changed in the goggles; for analog check `status` (the OSD type), and export the picture without anti-aliasing strictly in 0,255,0 / 0,0,0 / 255,255,255.
- **Symptom:** on an analog aircraft there is no OSD or it jitters (question No. 12)
  - Possible cause: the build has “OSD (HD)”, and the default is `HD`/`MSP`; the wrong video system for the camera.
  - What to do: `set vcd_video_system = PAL` (or NTSC/AUTO), `osd_displayport_device = MAX7456` or AUTO, centering with `vcd_h_offset`/`vcd_v_offset`.


## checklist
- I know the supply range of my air unit and where to take it from — VBAT or a BEC only
- TX/RX crossed over, both grounds on the flight controller, not SoftSerial
- The air unit's port has the mask 131073 and 115200, and MSP is enabled on no more than 3 ports
- `vcd_video_system = HD`, `osd_displayport_device = MSP`, the OSD is enabled
- I know that `displayport_msp_serial` was removed in 4.4
- The OSD layout is made for the canvas of my system, and `displayport_msp_fonts` matches the font in the goggles
- I know that the logo is font characters 160–255: on analog it is in the MAX7456 memory and is overwritten by a font upload, on HD it is in the goggles' font
- Airflow is running on the bench, and the power-up order is: antenna → goggles → battery → USB
- Recording is checked, and power is set according to the country's rules

## references
- Betaflight io/serial.h — serialPortFunction_e, tag 2025.12.5 (FUNCTION_GIMBAL = 1 << 18) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/io/serial.h | primary | A
- Betaflight io/serial.h — serialPortFunction_e (FUNCTION_VTX_MSP = 1 << 17), 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/serial.h | primary | A
- Betaflight io/serial.c — isSerialConfigValid(), 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/serial.c | primary | A
- Betaflight osd/osd.h — OSD_POS, OSD_HD_COLS/ROWS 53×20, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/osd/osd.h | primary | A
- Betaflight cli/settings.c — displayport_msp_*, vcd_video_system, osd_canvas_*, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/settings.c | primary | A
- Betaflight cli/settings.c 4.3-maintenance — displayport_msp_serial, displayport_msp_attrs | https://raw.githubusercontent.com/betaflight/betaflight/4.3-maintenance/src/main/cli/settings.c | primary | A
- Betaflight App — OSD tab (HD 53×20, the canvas from the VTX) | https://betaflight.com/docs/wiki/app/osd-tab | primary | A
- Betaflight osd/osd.c — osdDrawLogo, osd_logo_on_arming, osd_arming_logo, 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/osd/osd.c | primary | A
- Betaflight drivers/max7456.c — max7456WriteNvm (font NVM), 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/drivers/max7456.c | primary | A
- Betaflight Configurator 10.10 — LogoManager.js (288×72, three colours, PNG/BMP) | https://raw.githubusercontent.com/betaflight/betaflight-configurator/10.10.0/src/js/LogoManager.js | primary | A
- Betaflight Configurator 10.10 — tabs/osd.js (Font Manager, .mcm, Upload Font) | https://raw.githubusercontent.com/betaflight/betaflight-configurator/10.10.0/src/js/tabs/osd.js | primary | A
- DJI O3 Air Unit User Manual v1.0 (pinout, Canvas mode, overheating, linking) | https://xcopter.com/download/DJI_O3_Air_Unit_User_Manual_v1.0_ENo.pdf | primary | A
- DJI O3 Air Unit specifications | https://www.cliftoncameras.co.uk/uploads/specifications/DJI%20O3%20Air%20Unit.pdf | primary | A
- DJI O4 Air Unit / O4 Air Unit Pro specs | https://www.dji.com/o4-air-unit/specs | primary | A
- DJI O4 Air Unit Series User Manual v1 (BEC ≥ 10/13.5 W, time on the bench) | https://hobbydrone.cz/user/related_files/dji_o4_air_unit_series_user_manual_v1_en.pdf | primary | A
- DJI FPV Air Unit specs (7.4–17.6 V, < 28 ms) | https://www.dji.com/fpv/info | primary | A
- DJI Digital FPV System Release Notes (custom OSD, 24 elements) | https://manuals.plus/m/21886e9a1f15ac666e592e9149600fb1e60f9d4a47d083ae5c8f773ecd562a25 | primary | B
- Walksnail Avatar HD Pro Kit specifications | https://www.caddxfpv.com/products/walksnail-avatar-hd-pro-kit-dual-antenna | primary | A
- Walksnail Avatar kit Quickstart guide V1.1 | https://cdn.shopify.com/s/files/1/0618/3020/1566/files/Avatar_kit_Quickstart_guide_EN_CN_V1.1.pdf | primary | A
- Walksnail Avatar HD Mini VTX V3 manual (3.1–13 V supply, airflow on the bench, CE) | https://www.rotorama.com/assets/docs/5f2b6df00100231feac11bb2a7480570/47716-1/walksnail-avatar-hd-mini-vtx-v3-manual-en.pdf | primary | A
- HDZero VTX docs — targets (power, BEC vs VBAT, pinout) | https://hd-zero.github.io/hdzero-vtx-docs/latest/vtx_targets | primary | A
- HDZero VTX docs — user manual (baud, LP_MODE, PIT_MODE, VTX table) | https://raw.githubusercontent.com/hd-zero/hdzero-vtx-docs/main/docs/vtx_user_manual.md | primary | A
- HDZero VTX docs — troubleshoot (overheating, USB/battery order) | https://raw.githubusercontent.com/hd-zero/hdzero-vtx-docs/main/docs/vtx_troubleshoot.md | primary | A
- HDZero VTX firmware msp_displayport.c (MSP_SET_OSD_CANVAS, HD_5018) | https://raw.githubusercontent.com/hd-zero/hdzero-vtx/main/src/msp_displayport.c | primary | A
- Divimath — Latency analysis, analog vs HDZero (white paper) | https://www.helicomicro.com/wp-content/uploads/2022/09/WhitePaper-LatencyAnalysis-AnalogvsHDZero.pdf | primary | B
- fpv-wtf msp-osd README (WTFOS, displayport_msp_fonts, 4.3 vs 4.4) | https://raw.githubusercontent.com/fpv-wtf/msp-osd/main/README.md | secondary | B
- Caddx Vista unit specifications (retailer listing) | https://www.getfpv.com/caddx-vista-unit-for-dji-digital-hd-fpv-no-camera.html | secondary | B

## notes
The Betaflight names, defaults and ranges are from the 4.5-maintenance source (code = 4.5.5), checked against the 2025.12.5 settings table (no differences in the variables of the reference); the masks were verified by a program against `serial.h`, the positions — against `osd.h`. Power, transmit power and latency are the manufacturers' claims; the HDZero latency is an estimate from the Divimath model. The logo and fonts: firmware — `osd/osd.c`, `drivers/max7456.c`, `io/displayport_msp.c` (4.5.3 and 2025.12.5), the app — Configurator 10.10.0 (`LogoManager.js`, `tabs/osd.js`). Not verified: how to change the font and the logo on the HD goggles side. Not verified: the canvas reported by DJI O3/O4 and Walksnail (read `get osd_canvas`); an MSP VTX on DJI and Walksnail; the DJI firmware version that gave the old goggles Canvas mode. The order “goggles → aircraft” is practice, not a manufacturer requirement.
