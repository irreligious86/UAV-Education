---
id: link-elrs
title: "ExpressLRS: Packet Rate, Telemetry, LQ"
level: L2
readingTime: 20 min
firmware: ELRS 3.x
status: published
added: 2026-11-07
tags:
  - ExpressLRS
  - telemetry
related:
  - link-protocols
  - bf-failsafe
next:
  - link-vtx
source: content/link/link-elrs.md
source_hash: 381da63db517
---

## summary
ExpressLRS (ELRS) is an open radio control system that has become the standard in FPV. This module explains the main trade-offs: packet rate versus range, 2.4 GHz versus 900 MHz, how much airtime to give to telemetry. And it teaches you to read LQ and RSSI in the log so you can tell a link problem from a setup problem.

## theory
### Packet rate: latency versus sensitivity
Packet rate is how many control packets per second the radio transmits. More packets means lower latency, but each packet is shorter and the receiver sensitivity is worse. That's why high rates are for racing and close-in freestyle, and low rates are for long-range flights.

2.4 GHz modes in ELRS 3.x:

- LoRa: 50, 150, 250, 500 Hz — the main set, the lower the farther;
- FLRC: F500, F1000 — minimal latency, shorter range; F1000 requires a serial receiver and a high UART speed;
- D250, D500 — FLRC 1000 Hz with repetition: in D500 each packet is sent twice, in D250 four times, more reliable under interference;
- Full Resolution modes (for example 100Hz Full, 333Hz Full) — all channels at full resolution for wings and complex mixes.

On 900 MHz (868/915) the rates are lower: 25, 50, 100, 200 Hz. The longer wavelength bends around obstacles better and gets through foliage — the choice for wings and long routes.

### Telemetry: the 1:N ratio
The telemetry ratio shows which packet out of N is given to the return channel. Telemetry interval = ratio × 1000 / packet rate (ms). For example, 500 Hz at 1:128 means a telemetry packet every 256 ms. There are two packet types: LINK (link statistics, roughly every 512 ms, always present) and DATA (flight controller telemetry and MSP). If you need to push a lot of data to the radio (GPS, the Lua configurator), you set the ratio more frequent (1:8, 1:4).

### Binding phrase
The binding phrase is not a password and not encryption. A UID is computed from it, which sets the frequency hopping pattern. A unique phrase is needed so you don't interfere with neighbors that have the same pattern. The radio and the receiver must have the same phrase and the same major ELRS version.

### LQ and RSSI
- RQly (uplink LQ) — how many of the radio's last 100 packets reached the receiver;
- TQly — the same for telemetry in the opposite direction;
- RSSI — signal strength in dBm; the margin is counted down to the sensitivity threshold of the current packet rate.

LQ answers the question “are the packets getting through”, RSSI answers “how much margin is left”. LQ 100% with RSSI right at the threshold means you're at the edge, even if everything flies: per the ELRS documentation, LQ falls “off a cliff” as soon as RSSI approaches the sensitivity limit. That's why the RSSI warning in the OSD is set 5–10 dB above the mode's threshold: for 250 Hz (−108 dBm) — around −103…−98 dBm.

### Modes and sensitivity — table (ELRS 3.x, from the Signal Health documentation)
| Band | Mode | Packets/s | Sensitivity | When |
|---|---|---|---|---|
| 2.4 GHz | 50 Hz | 50 | −115 dBm | maximum range on 2.4 |
| 2.4 GHz | 150 Hz | 150 | −112 | long range with good latency |
| 2.4 GHz | 250 Hz | 250 | −108 | the standard for freestyle/racing |
| 2.4 GHz | 500 Hz | 500 | −105 | minimal latency, close range |
| 2.4 GHz | F1000 (FLRC) | 1000 | −104 | racing, short distance |
| 900 MHz | 25 Hz | 25 | −123 | extreme range |
| 900 MHz | 50 Hz | 50 | −120 | long range |
| 900 MHz | 100 Hz Full | 100 | −112 | balance |
| 900 MHz | 200 Hz | 200 | −112 | close range on 900 |
Every −3 dB of sensitivity = ×0.71 in range; 50 → 250 Hz on 2.4 = −7 dB ≈ ×0.45. The range calculation is in the “Link Budget” module, interactive below.

### The latency the pilot feels
Packet interval 1/rate: 250 Hz → 4 ms, 50 Hz → 20 ms; plus processing in the radio (EdgeTX mixer at the module rate, ~1–3 ms), CRSF at 420 kbaud (~0.6 ms), RC smoothing in the FC (`rc_smoothing_auto_factor`, 1–10 ms). Going 150 → 250 Hz is noticeable in racing, 250 → 500 is barely noticeable against the filters and the motor (the “Stick-to-Motor Latency” widget in the “Control Theory” module). Switch mode (`Hybrid`/`Wide`): Wide gives 4 full channels, a 1-bit ARM (AUX1) and 7 channels AUX2–AUX8 with 64/128 positions; the “Full Res” modes (100 Hz Full, 333 Hz Full) — 8, 12 or 16 channels at 10 bits (8ch, 12ch Mixed, 16ch Rate/2) for wing/gimbal servos.

{{diagram:latency-chain|What makes up the latency from the stick to the aircraft's response; the largest contributions come from the radio packet and motor inertia.}}

### Dynamic power and telemetry
Dynamic Power (`Dyn`): the module raises power by itself when the onboard LQ/RSSI drop, and lowers it up close; it requires telemetry (ratio ≥ 1:64). Telemetry ratio 1:128 — telemetry interval = 128/250 s ≈ 0.5 s at 250 Hz: enough for voltage/LQ, slow for GPS coordinates (for long range — 1:16…1:32 or `Std`; `Race` disables telemetry while armed and doesn't suit long range). The telemetry channel is the same link, so MAVLink telemetry over ELRS (airport/MAVLink mode, MAVLink since 3.5.0) shares bandwidth with control — for a GCS, a separate modem or 4G is better.

### Worked example: setup for a 7" long range
900 MHz 100 Hz Full (−112) or 2.4 GHz 150 Hz (−112) — choose by the interference environment and antennas (900 means bigger antennas, better diffraction around obstacles); power per the budget for 10 km with a 12 dB margin (the “Link Budget” module); telemetry 1:32; Dynamic Power ON; Wide switch mode; warnings in EdgeTX: RSSI dBm (sensor `1RSS`/`2RSS`) ≤ −100 “caution”, ≤ −105 “turn back”; LQ (`RQly`) < 70% warning; in the OSD `osd_rssi_dbm_pos`, `osd_link_quality_pos`; receiver failsafe — `no pulses` (the default), in the FC — GPS Rescue/RTH.

## practice

{{widget:elrs-calc}}

Where the radio link sits in the “stick → motor” chain and how much it really weighs next to RC smoothing, filters and the motor:

{{widget:link-latency}}

### Choosing a mode for the task
1. Freestyle, racing, line-of-sight flights: 2.4 GHz, 250–500 Hz or F500.
2. 7–10" for long-range flights: 2.4 GHz 150 Hz or 900 MHz 100 Hz.
3. Wing, long routes, forest: 900 MHz, 50–100 Hz.

### Setup on the radio (ELRS Lua)
1. Tools → ExpressLRS: choose Packet Rate and Telem Ratio.
2. TX Power: for close-in flights don't set the maximum — the module heats up, plus you blast your neighbors. Dynamic Power will raise the power by itself when LQ drops.
3. After changing the mode, check that the receiver is connected again (green status in Lua).

### Analyzing the link from a Blackbox log
1. Enable RSSI/LQ logging in Betaflight (the `rssi` and link quality fields).
2. After the flight, find the segments where LQ drops below ~70% or RSSI approaches the threshold.
3. Match them with the RXLOSS moments in the OSD and with the drone's orientation. A real-world example: on a 10", RSSI stayed around 26–52%, dropped below 30% for tens of seconds, and that's exactly where the RXLOSS happened. The culprit was the receiver antenna, not the PID settings.

## diagnostics
- **Symptom:** RXLOSS when turning with the back toward the pilot
  - Possible cause: the receiver antenna is shadowed by the frame or carbon fiber.
  - What to do: move the antenna out, orient it at an angle, check it for damage.
- **Symptom:** LQ “sags” in waves even though the drone is close
  - Possible cause: strong 2.4 GHz interference (Wi-Fi, other pilots) or a damaged radio antenna.
  - What to do: try D250/D500 mode or 900 MHz, check the TX antenna.
- **Symptom:** won't bind after an update
  - Possible cause: different major ELRS versions or different binding phrases.
  - What to do: update both sides to the same version, check the phrase.
- **Symptom:** F1000 isn't available
  - Possible cause: an SPI receiver or insufficient UART speed on the radio.
  - What to do: use a serial receiver and check the module baud rate.
- **Symptom:** LQ 100%, but control is jerky
  - Possible cause: low packet rate with high `rc_smoothing`, or telemetry is too frequent.
  - What to do: 250 Hz, look at `debug_mode = RC_SMOOTHING`, ratio 1:64.
- **Symptom:** range in the field is half the calculated value
  - Possible cause: antennas (polarization, carbon), onboard interference, Dynamic Power doesn't keep up.
  - What to do: the “Antennas” and “Interference” modules; fixed power for the test; LQ/RSSI to the log.

## references
- ExpressLRS FAQ | https://www.expresslrs.org/faq/ | primary | A
- Telemetry Bandwidth — ExpressLRS Docs | https://www.expresslrs.org/info/telem-bandwidth/ | primary | A
- Lua Script How-To — ExpressLRS Docs | https://www.expresslrs.org/quick-start/transmitters/lua-howto/ | primary | A
- ExpressLRS — source code (GitHub) | https://github.com/ExpressLRS/ExpressLRS | primary | A

## checklist
- Packet rate is chosen for the task, not “the maximum”
- Telem ratio matches the amount of telemetry you need
- A unique binding phrase, the same major version on the radio and the receiver
- RSSI and LQ are written to the log
- The receiver antenna is moved out and not shadowed by the frame
