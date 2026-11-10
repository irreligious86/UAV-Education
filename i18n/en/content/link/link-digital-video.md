---
id: link-digital-video
title: "Digital FPV Video: DJI, Walksnail, HDZero, OpenIPC"
level: L2
readingTime: 30 min
firmware: Betaflight 4.4+ · INAV 7+ · ArduPilot 4.5+
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
source_hash: 542319dc9938
---

## summary
The analog VTX from the “VTX Tables” module means minimal latency and graceful degradation into noise. Digital systems give you a picture that's many times sharper, onboard HD recording and a high-resolution OSD, but they pay for it with compression, latency that depends on the mode, and the “cliff”: a freeze instead of snow. This module explains how analog, frame-synchronous digital (HDZero), compressed video (DJI, Walksnail) and the open OpenIPC + WFB-ng combo fundamentally differ; how to hook up HD OSD via MSP DisplayPort in Betaflight, INAV and ArduPilot; and how to pick a system for the task rather than by the marketing. The lab is measuring the latency and the behavior at the edge of range of your own system.

## theory
### What changes when you go digital
- **Compression.** Camera → H.264/H.265 encoder → radio → decoder → screen. The encoder looks for similarities between frames; the lower the bitrate, the more it has to “make things up”. Hence the artifacts on fast passes over grass and trees — where frames are least alike.
- **Latency is not one number.** Manufacturers quote the minimum in the best mode (high frame rate, strong signal). At the edge of range, systems lower the bitrate and frame rate, and latency grows. Compare systems by measuring in your own modes, not by the box.
- **Degradation.** Analog at the edge means noise and stripes, but there's still a picture, and the pilot sees where they're flying. Digital holds a clean picture almost to the end, then freezes or breaks up into blocks. Behavior at link loss is the main safety question for long-range flights: what the pilot will see one second before losing video, and what the aircraft will do.
- **Onboard recording.** Digital air units record video without radio losses — that's the “HD DVR” for flight review, as opposed to recording in the goggles.

### Four families
| System | Principle | Strength | Limitations |
|---|---|---|---|
| Analog 5.8 GHz | uncompressed composite signal | minimal and constant latency, graceful degradation, cheap | low sharpness, interference shows immediately |
| HDZero | digital without inter-frame compression, synchronous with the camera frame | low and stable latency, predictable for racing | less sharp than compressed systems, blocks at the edge |
| DJI (O3/O4), Walksnail Avatar | compressed H.264/H.265 video with bitrate adaptation | best picture, onboard recording, good range | latency depends on the mode, closed ecosystem, fewer simultaneous channels |
| OpenIPC + WFB-ng | open IP camera firmware + Wi-Fi adapters in monitor mode, FEC | openness, tunable for the task, MAVLink telemetry in the same channel | built and configured by hand, higher latency than FPV systems |

Latency, resolution and range figures for specific models change with every generation and firmware — check the manufacturer's documentation for your version and, most importantly, measure.

### HD OSD: MSP DisplayPort
In digital systems the OSD is drawn by the goggles or the air unit, and the flight controller only sends **what** to draw, using the MSP DisplayPort protocol over UART.
- **Betaflight 4.4+**: a UART on the Ports tab — MSP function for the air unit (Peripherals: VTX (MSP + DisplayPort)); in the CLI `set osd_displayport_device = MSP`, video system `set vcd_video_system = HD`. OSD elements are laid out on a larger canvas.
- **INAV**: a UART with MSP DisplayPort for HD OSD, OSD type per your system's documentation.
- **ArduPilot**: `SERIALn_PROTOCOL = 42` (DisplayPort), `OSD_TYPE = 5` (MSP DisplayPort).
- VTX control (channel, power) on digital systems goes either through the same MSP or from the goggles menu — analog VTX tables aren't needed here.

### Frequencies and neighbors
Digital systems also work in 5.8 GHz and occupy a wider band, so fewer of them fit in the air at the same time than analog aircraft on Raceband. At a shared field, agree on channels in advance; mixed analog + digital is a common source of mutual interference. Power and permitted channels — per your country's rules.

### How to choose
- **Racing and practicing in a crowd**: analog or HDZero — constant low latency, lots of channels.
- **Freestyle and filming**: DJI or Walksnail — the picture and recording matter more than a few milliseconds.
- **Long-range autopilot flights**: what matters more is behavior at the edge and the telemetry link; digital video + a separate RC link (ELRS) + an OSD with the key data; OpenIPC — if you need an open system and MAVLink in the video channel.
- **An aircraft with a companion computer and vision**: video for the pilot and video for the algorithm are different streams; don't tie navigation to the pilot's video channel.

{{diagram:fpv-video-choice|Choosing an FPV video system by task: constant low latency — analog or HDZero, picture and recording — DJI/Walksnail, openness and MAVLink in the channel — OpenIPC.}}

## practice
### Step 1. Inventory your system
Air unit and goggles model, firmware version, modes (resolution, frame rate, bitrate), antennas and their polarization, channel. Write it into the aircraft's logbook.

### Step 2. HD OSD
Connect the air unit to a flight controller UART, set up MSP DisplayPort (Betaflight: `osd_displayport_device = MSP`, `vcd_video_system = HD`; ArduPilot: `SERIALn_PROTOCOL = 42`, `OSD_TYPE = 5`). Display voltage, current, RSSI/LQ, flight time, warnings. Check that the elements don't cover the center of the frame.

### Step 3. Latency
The method from the “Cameras and Video Stream” module: a stopwatch with milliseconds on a phone screen, the aircraft camera looks at it, and the goggles (or their output/recording) are filmed by a second phone together with the original screen. 10 measurements in each mode (for example, 60 and 100 fps, or two bitrate modes), median and maximum. Write down a table.

### Step 4. Edge of range on the ground
Aircraft on a tripod, the pilot walks away or blocks the line of sight (a building corner, trees) — at reduced power so you don't have to walk far. Write down: at what RSSI/link quality the bitrate drops, latency grows, blocks appear, freeze. For analog (if you have it) — the same for comparison. Conclusion: what link quality margin you need in flight so you never get to the freeze.

The lab counts as done when HD OSD is set up, latency is measured in two modes (median and maximum), and the behavior at the edge is described step by step with link quality numbers.

## diagnostics
- **Symptom:** no OSD in the goggles, video is fine
  - Possible cause: the UART isn't in MSP / DisplayPort mode, TX/RX are swapped, the HD OSD device isn't selected.
  - What to do: check the port function, `osd_displayport_device`, the TX/RX crossover wiring.
- **Symptom:** the picture freezes at range without warning
  - Possible cause: the digital “cliff”, flying at the limit of link quality.
  - What to do: show video link quality in the OSD, turn back at a threshold, check the antennas and polarization.
- **Symptom:** blocks and “mush” over grass and trees
  - Possible cause: the bitrate is too low for a scene with lots of motion.
  - What to do: a higher-bitrate mode, lower resolution or frame rate, a cleaner spectrum.
- **Symptom:** interference for a neighbor at the field
  - Possible cause: wide digital channels next to analog ones, a wrong frequency plan.
  - What to do: agree on channels, lower power on the ground, separate by frequency.
- **Symptom:** latency is noticeably higher than advertised
  - Possible cause: a low-frame-rate mode, weak signal, recording in the goggles, different firmware.
  - What to do: measure in different modes, update the firmware, check which mode is actually active.

## references
- Betaflight — HD OSD / MSP DisplayPort (OSD tab) | https://betaflight.com/docs/wiki/app/osd-tab | primary | A
- ArduPilot — MSP DisplayPort OSD | https://ardupilot.org/copter/docs/common-msp-osd-overview-4.2.html | primary | A
- OpenIPC — open firmware for IP cameras (FPV) | https://github.com/OpenIPC | primary | B
- WFB-ng — long-range Wi-Fi broadcast link | https://github.com/svpcom/wfb-ng | primary | B

## checklist
- I can explain the difference between analog, frame-synchronous digital and compressed video
- I understand why a digital system's latency has to be measured in my own mode
- I can set up HD OSD via MSP DisplayPort
- I know how my system behaves at the edge of range, and I show link quality in the OSD
- I pick a system for the task and coordinate frequencies at the field
