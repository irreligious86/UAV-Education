---
id: link-digital-video
title: "Digital FPV video: DJI, Walksnail, HDZero, OpenIPC"
level: L2
readingTime: 30 min
firmware: Betaflight 2025.12 (checked against 2025.12.5) · INAV 9.1 (checked against 9.1.0) · ArduPilot 4.5+ (checked against 4.7.3)
status: published
tags:
  - digital video
  - HD OSD
  - MSP DisplayPort
  - latency
related:
  - link-vtx
  - per-camera
  - rf-antennas
  - rf-link-budget
next:
  - ops-field
source: content/link/link-digital-video.md
source_hash: 8e8f6b579768
---

## summary
The analog VTX from the "VTX tables" module gives you minimal latency and graceful degradation into noise. Digital systems give a far sharper picture, onboard HD recording and a high-resolution OSD, but they pay with compression, latency that depends on the mode, and a "cliff": a freeze instead of snow. This module explains how analog, frame-synchronous digital (HDZero), compressed video (DJI, Walksnail) and the open OpenIPC + WFB-ng stack differ at the core; how to connect HD OSD over MSP DisplayPort in Betaflight, INAV and ArduPilot; and how to choose a system for the job rather than by the advertising. The lab measures latency and the behavior of your own system at the edge of range.

## theory
### What changes when you go digital
- **Compression.** Camera → H.264/H.265 encoder → radio → decoder → screen. The encoder looks for similarities between frames; the lower the bitrate, the more it has to "make up". Hence the artifacts on fast passes over grass and trees, where consecutive frames are least alike.
- **Latency is not one number.** Manufacturers quote the minimum in the best mode (high frame rate, strong signal). At the edge of range the systems lower the bitrate and frame rate, and latency grows. Compare systems by measuring them in your own modes, not by the box.
- **Degradation.** Analog at the edge means noise and stripes, but the picture is there and the pilot sees where they are flying. Digital holds a clean picture almost to the end, then freezes or breaks up into blocks. Behavior at the cliff is the main safety question for long-range flights: what the pilot sees a second before losing video, and what the aircraft does.
- **Onboard recording.** Digital air units record video without radio losses; this is the "HD DVR" for reviewing a flight, as opposed to recording in the goggles.

### Four families
| System | Principle | Strength | Limitations |
|---|---|---|---|
| Analog 5.8 GHz | uncompressed composite signal | minimal and constant latency, graceful degradation, cheap | low sharpness, interference is visible at once |
| HDZero | digital without inter-frame compression, synchronous with the camera frame | low and stable latency, predictable for racing | less sharp than compressed systems, blocks at the edge |
| DJI (O3/O4), Walksnail Avatar | compressed H.264/H.265 video with adaptive bitrate | the best picture, onboard recording, good range | latency depends on the mode, closed ecosystem, fewer simultaneous channels |
| OpenIPC + WFB-ng | open IP-camera firmware + Wi-Fi adapters in monitor mode, FEC | open, tunable for the job, MAVLink telemetry in the same link | built and tuned by hand, higher latency than FPV systems |

Latency, resolution and range figures for specific models change with every generation and firmware: check the manufacturer's documentation for your version and, above all, measure.

### HD OSD: MSP DisplayPort
In digital systems the goggles or the air unit draw the OSD; the flight controller only sends **what** to draw, over the MSP DisplayPort protocol on a UART.
- **Betaflight 2025.12** (the same since 4.4): a UART on the Ports tab with the MSP function for the air unit (Peripherals: VTX (MSP + Displayport)); in the CLI `set osd_displayport_device = MSP`, video system `set vcd_video_system = HD`. In Cloud Build keep the **OSD (Digital)** option (`OSD_HD`, on by default) selected: a build without it has no MSP DisplayPort OSD and the goggles show none. OSD elements are placed on a larger canvas.
- **INAV**: a UART with the MSP_OSD (DisplayPort) function; `osd_video_system` per system: HDZERO, AVATAR (Walksnail), DJI_NATIVE (DJI O4 and goggles with the INAV font), BFHDCOMPAT (DJI O3 on stock firmware), DJIWTF (WTFOS); details in `bf-hd-osd-video`, section "INAV and ArduPilot — briefly".
- **ArduPilot 4.7**: `SERIALn_PROTOCOL = 42` (DisplayPort), `OSD_TYPE = 5` (MSP_DISPLAYPORT), for HDZero, Walksnail, DJI O3/O4 and DJI on WTFOS. The old protocol 33 ("DJI FPV", `OSD_TYPE = 3`) is only for DJI FPV V1/V2 goggles without WTFOS: the goggles draw the elements and the flight controller answers like Betaflight. The flight controller sets the grid, separately for each screen: `OSDn_TXT_RES` 0 = 30x16 (the default; HD goggles show a coarse SD grid), 1 = 50x18, 2 = 60x22 (HDZero: only 0 or 1). `MSP_OPTIONS` (default 0): bit 0 (1) EnableTelemetryMode, "push" telemetry, only for protocol 33 with a single wire; bit 2 (4) EnableBTFLFonts, Betaflight font indexes in DisplayPort (stock DJI O3/O4); bit 3 (8) EnableINAVFonts, overrides bit 2; reboot after a change. ArduPilot sets up an analog VTX by itself: `VTX_ENABLE = 1`, a port with protocol 37 (SmartAudio) or 44 (IRC Tramp), `VTX_BAND`, `VTX_CHANNEL`, `VTX_POWER`, `VTX_MAX_POWER`. The "system → port → `OSD_TYPE` → `MSP_OPTIONS` → `OSDn_TXT_RES`" table and the VTX parameters are in `ap-osd-video`.
- Digital systems control the VTX (channel, power) either over the same MSP link or from the goggles' menu; analog VTX tables are not needed here.

### Frequencies and neighbors
Digital systems also work in 5.8 GHz; how many of them fit in the air at once depends on the system and the channel width. HDZero works on the standard 5.8 GHz channel grid, up to 8 pilots, like analog with planning; compressed-video systems on wide channels (DJI O3 up to 40 MHz, O4 with Goggles 3/N3 up to 60 MHz: one channel at 60 or 40 MHz, three at 20, three at 10) leave fewer slots (figures in link-vtx). At a shared field you agree on channels in advance; mixed analog + digital is a common source of mutual interference. Power and permitted channels follow your country's rules.

### How to choose
- **Racing and practice in a crowd**: analog or HDZero; constant low latency, many channels.
- **Freestyle and filming**: DJI or Walksnail; the picture and recording matter more than a few milliseconds.
- **Long-range autopilot flights**: behavior at the edge and the telemetry link matter more; digital video + a separate RC link (ELRS) + an OSD with the key data; OpenIPC if you need an open system and MAVLink in the video link.
- **An aircraft with a companion computer and vision**: video for the pilot and video for the algorithm are separate streams; do not make navigation depend on the pilot's video link.

{{diagram:fpv-video-choice|Choosing an FPV video system for the job: constant low latency means analog or HDZero, picture and recording mean DJI/Walksnail, openness and MAVLink in the link mean OpenIPC.}}

### Goggles: compatibility and choice
Goggles outlive aircraft, and every next video transmitter (VTX) has to work with them. So the question is: **which VTXs are already on your aircraft, and which ones are you willing to buy next**. Prices and the full DJI matrix with latencies are in `f-starter-kit`; here is what each pair of goggles receives (per manufacturers and reviews, as of November 2026).

| Goggles | Receive natively | Via a module or input | Do not receive |
|---|---|---|---|
| DJI Goggles 3 | O4, O4 Pro; O3 after an update (goggles v01.00.0300, O3 v01.03.0000) | — | analog, HDZero, Walksnail, Vista and the original DJI FPV Air Unit |
| DJI Goggles N3 | O4, O4 Pro | — | O3 and anything non-DJI |
| DJI Goggles 2 / Integra | O3, O4, O4 Pro; Vista and the original DJI FPV Air Unit on compatible goggles firmware | — | analog and anything non-DJI |
| HDZero Goggle 2, BoxPro | HDZero and analog (built-in receiver) | Walksnail: an external VRX into the HDMI input | DJI |
| HDZero Goggle (original) | HDZero | analog: an expansion module with a bay for an analog receiver | DJI |
| Walksnail Goggles X | Walksnail | analog and HDZero: an external receiver into the AV/HDMI input | DJI |
| Walksnail Goggles L | Walksnail | — | everything else |
| Analog goggles | analog 5.8 GHz | digital only through a separate VRX with HDMI output, if the goggles have an HDMI input (**not verified** per model) | DJI |

Two patterns. DJI works only with DJI, and within DJI compatibility goes by generation: N3 goggles take only O4, and the DJI radio is also tied to the goggles' generation. HDZero and Walksnail are open toward analog, but accept each other only through an external receiver.

{{diagram:goggles-vtx-links|DJI is a closed loop split by generation; HDZero and Walksnail are open to analog (only HDZero Goggle 2 and BoxPro receive it natively, the rest through a module or a receiver), and to each other only through an external receiver.}}

**How to choose.**

1. List your fleet: how many aircraft on each system. Changing systems costs "goggles + a VTX for every aircraft" (`f-starter-kit`).
2. Analog aircraft must keep flying → goggles with an analog receiver: HDZero Goggle 2 or BoxPro, Walksnail Goggles X with an external receiver. DJI goggles do not fit here at all.
3. You stay on DJI and own O3 → Goggles 3 or Goggles 2/Integra; buy N3 only if the whole fleet is on O4.
4. Before buying, check the compatibility list on the manufacturer's page for the current firmware: O3 support in Goggles 3 came with an update, and the lists change.

**How to check after buying.** Update the goggles and air unit firmware, bind, and on the bench with props off make sure there is a picture and an OSD (OSD setup is in `bf-hd-osd-video`). Then compare the goggles recording with the onboard recording: clean onboard but blocks in the goggles means a radio problem, not a compatibility one.

### Where it fits in the system

- **Takes in:** a UART with MSP DisplayPort and the OSD content from the flight controller (`bf-hd-osd-video`); bandwidth in 5.8 GHz that has to be shared with neighbors (`link-vtx`); range margin from the link budget (`rf-link-budget`, `rf-antennas`).
- **Puts out:** picture and OSD to the pilot with mode-dependent latency; onboard HD recording for flight review; a choice of goggles that decides the VTX of every next aircraft (`f-starter-kit`); an occupied channel in the field's shared frequency table (`ops-field`).
- **If you get this wrong:** a system chosen by the latency on the box → at the edge of range the bitrate and frame rate drop, latency grows, then a freeze: the picture disappears without the gradual warning analog gives; behavior at the edge is measured in advance (`rf-link-budget`). The OSD (Digital) option dropped from the Cloud Build → video is there, no OSD in the goggles (`bf-hd-osd-video`).

## practice
### Step 1. Inventory your system
Air unit and goggles model, firmware version, modes (resolution, frame rate, bitrate), antennas and their polarization, channel. Write it in the aircraft's logbook.

### Step 2. HD OSD
Connect the air unit to a flight controller UART and set up MSP DisplayPort (Betaflight: `osd_displayport_device = MSP`, `vcd_video_system = HD`; INAV: MSP_OSD on the port and `osd_video_system` for your system; ArduPilot: `SERIALn_PROTOCOL = 42`, `OSD_TYPE = 5`). Show voltage, current, RSSI/LQ, flight time and warnings. Check that the elements do not cover the center of the frame.

### Step 3. Latency
The method from the "Cameras and video streams on a companion computer" module: a stopwatch with milliseconds on a phone screen, the aircraft's camera pointed at it, and the goggles (or their output/recording) filmed with a second phone together with the original screen. 10 measurements in each mode (for example 60 and 100 fps, or two bitrate modes), median and maximum. Record the table.

### Step 4. Edge of range on the ground
The aircraft on a stand; the pilot walks away or blocks line of sight (a building corner, trees), at reduced power so you do not have to walk far. Record at what RSSI/link quality the bitrate drops, latency grows, blocks appear, and the picture freezes. For analog (if you have it), the same for comparison. Conclusion: how much link-quality margin you need in flight to never reach the freeze. A starting point for the OSD threshold (a course guideline): the link-quality value at which the bitrate dropped **first** in this test, not the one at which it froze; turn back at that threshold.

Self-check: the lab is done when the HD OSD is visible in the goggles and does not cover the center of the frame, the aircraft's logbook has a latency table for two modes (10 measurements each, median and maximum), and the behavior at the edge is recorded step by step with link-quality numbers: at what value the bitrate drops, latency grows, blocks appear, and the freeze comes.

**Reference answer for self-check.** The module deliberately sets no specific milliseconds: they depend on the system and firmware; what is checked is the pattern. The correct result: the maximum is above the median, the mode with the lower frame rate or bitrate gives higher latency, and at the edge the events come in the order "bitrate dropped → latency grew → blocks → freeze", each with a recorded link-quality number. Latency matched the box figure and is the same in both modes: only the best mode with a strong signal was measured, or the measurements got mixed up. The edge record only says "video lost" with no numbers before it: you cannot derive a link-quality margin from such a test; repeat step 4 with smaller distance steps.

## diagnostics
- **Symptom:** no OSD in the goggles, video is there
  - Possible cause: the UART is not in MSP / DisplayPort mode, TX/RX are swapped, the HD OSD device is not selected.
  - What to do: check the port function, `osd_displayport_device`, the crossed TX/RX wiring.
- **Symptom:** the picture freezes at range without warning
  - Possible cause: the digital "cliff", flying at the limit of link quality.
  - What to do: show video link quality in the OSD, turn back at a threshold (start with the quality at which the bitrate dropped in the lab), check antennas and polarization.
- **Symptom:** blocks and "mush" over grass and trees
  - Possible cause: too low a bitrate for a scene with a lot of motion.
  - What to do: a higher-bitrate mode, lower resolution or frame rate, cleaner air.
- **Symptom:** a neighbor at the field gets interference
  - Possible cause: wide digital channels next to analog ones, a wrong frequency plan.
  - What to do: agree on channels, lower power on the ground, spread out in frequency.
- **Symptom:** latency is noticeably higher than advertised
  - Possible cause: a low frame rate mode, a weak signal, recording in the goggles, different firmware.
  - What to do: measure in different modes, update the firmware, check which mode is actually active.

## references
- Betaflight — HD OSD / MSP DisplayPort (OSD tab) | https://betaflight.com/docs/wiki/app/osd-tab | primary | A
- ArduPilot — MSP DisplayPort OSD | https://ardupilot.org/copter/docs/common-msp-osd-overview-4.2.html | primary | A
- OpenIPC — open firmware for IP cameras (FPV) | https://github.com/OpenIPC | primary | B
- WFB-ng — long-range Wi-Fi broadcast link | https://github.com/svpcom/wfb-ng | primary | B
- DJI — O4 Air Unit Series, Specs (compatible goggles; accessed 2026-11-18) | https://www.dji.com/o4-air-unit/specs | primary | A
- Oscar Liang — DJI Goggles 3 Supports O3 (firmware versions, updated 2024-10-11) | https://oscarliang.com/dji-goggles-3-supports-o3/ | secondary | B
- Unmanned Tech — DJI Goggles 3 vs N3 compatibility (2026-06-09) | https://www.unmannedtechshop.co.uk/de/blogs/knowledge-base/dji-goggles-3-vs-n3-compatibility-guide-what-nobody-tells-you | secondary | B
- RCDrone — HDZero Goggle 2 compatibility: analog, Walksnail VRX (2026-11-13) | https://rcdrone.top/blogs/articles/hdzero-goggle-2-compatibility-analog-walksnail-vrx | secondary | C

## checklist
- I can explain the difference between analog, frame-synchronous digital and compressed video
- I understand why a digital system's latency has to be measured in your own mode
- I can set up HD OSD over MSP DisplayPort
- I know how the system behaves at the edge of range, and I show link quality in the OSD
- I choose a system for the job and coordinate frequencies at the field
