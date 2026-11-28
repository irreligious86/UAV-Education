---
id: comp-jetson-nano
title: "Jetson Nano as a companion: what it can do, what it lacks, and how to get the most out of it"
level: L2
readingTime: 50 min
firmware: ArduPilot 4.7 (checked against 4.7.3; lab recorded on 4.6.3) · PX4 1.18 (parameters checked against v1.18.0) · JetPack 4.6.6 / 6.2
status: published
added: 2026-11-14
tags:
  - Jetson Nano
  - Jetson Orin Nano
  - TensorRT
  - GStreamer
  - tegrastats
  - companion
related:
  - comp-intro
  - comp-raspberry
  - px4-companion-jetson
  - per-camera
  - per-edge-ml
  - ap-companion
  - mav-routing
next:
  - per-edge-ml
source: content/companion/comp-jetson-nano.md
source_hash: c9effb4774e6
---

## summary
A "Jetson Nano" in a shop is two different boards: the original 2019 Nano (Maxwell, 4 GB, JetPack 4, end of life) and the Jetson Orin Nano (Ampere, 8 GB, JetPack 6, Super mode). This module covers both honestly: what each one can and cannot compute, how much it really draws and why 5 V is the main trap, how it heats up and throttles, which cameras and video pipeline to use, how the inference stack differs, how to connect the UART to the flight controller and run everything as a service. The course has no Jetson, so all hardware figures come from NVIDIA documentation and published benchmarks with links, not from our own measurements. The lab needs no hardware: a parser for a `tegrastats` line and a "companion health → MAVLink" bridge that, in SITL, writes the temperature and load into the flight controller's log as `NAMED_VALUE_FLOAT`. Then, the order of steps for moving to a real board.

## theory
### Two boards under one name
The boundary of responsibility is the same as in the "Companion: why, and where the boundary is" module: the flight controller flies and returns by itself, the Jetson only watches and advises.

| | Jetson Nano (2019) | Jetson Orin Nano 8 GB (Super) |
|---|---|---|
| CPU | 4 × Cortex-A57, 1.43 GHz | 6 × Cortex-A78AE, 1.7 GHz |
| GPU | Maxwell, 128 cores, 472 GFLOPS, no Tensor Cores | Ampere, 1024 cores, 32 Tensor Cores, 67 TOPS (INT8, sparse) |
| Memory | 4 GB LPDDR4, shared by CPU and GPU | 8 GB LPDDR5, shared |
| Power modes | 10 W (MAXN), 5 W | 15 W, 25 W, MAXN_SUPER (without the Super configuration: 15 and 7 W) |
| Hardware encoder | yes: 4Kp30 or 4 × 1080p30, H.264/H.265 | **no NVENC**: 1080p30 in software, ≈ 2 CPU cores |
| System | JetPack 4.6.6, L4T 32.7.6, Ubuntu 18.04, kernel 4.9 | JetPack 6.2, L4T 36.4.3, Ubuntu 22.04 (the course's version; JetPack 7.2.x, Jetson Linux 39.2, Ubuntu 24.04 also supports Orin since 2026) |
| CUDA / TensorRT | 10.2 / 8.2.1 | 12.6 / 10.3 (JetPack 7.2.1: 13.2 / 10.16) |
| Devkit power | 5 V: micro-USB 2 A or barrel jack 4 A | barrel jack 9–20 V (19 V supply in the box) |
| Module | 69.6 × 45 mm, SO-DIMM 260 | the same form factor |
| Status | module in production until January 2027; devkit discontinued | module until January 2032 |

What "end of life" means in practice. JetPack 4.6.6 (November 22, 2024) is the last in the series: there will be no more critical updates, and JetPack 5/6 do not exist for the Nano. Ubuntu 18.04 means Python 3.6, while current `ultralytics` needs a newer Python, so on the Nano it is run in the ready-made `ultralytics/ultralytics:latest-jetson-jetpack4` container. For TensorRT 8.x, Q-engineering exports ONNX with `opset=11`; DeepStream is 6.0.1 and no newer. Bottom line: the Nano is fine if it is already sitting in a drawer and the task is one small detector; there is no reason to buy one for a new project. Orin on PX4 has its own module, "PX4 + Jetson Orin".

### Power modes: nvpmodel and jetson_clocks
`nvpmodel` sets the ceiling: how many cores are online and the maximum CPU/GPU frequencies. `sudo nvpmodel -q` shows the current mode, `sudo nvpmodel -m <ID>` switches it.

| Board | Mode | ID | CPU cores | CPU max, MHz | GPU max, MHz |
|---|---|---|---|---|---|
| Nano | MAXN (10 W) | 0 | 4 | 1479 | 921.6 |
| Nano | 5 W | 1 | 2 | 918 | 640 |
| Orin Nano 8 GB Super | 15 W | 0 | 6 | 1497.6 | 612 |
| Orin Nano 8 GB Super | 25 W (default) | 1 | 6 | 1344 | 918 |
| Orin Nano 8 GB Super | MAXN_SUPER | 2 | 6 | 1728 | 1020 |

The Nano's "10 W" is the budget for the CPU and GPU rails only, not for the whole board. `jetson_clocks` pins the CPU, GPU and memory clocks to the maximum of the current mode: latency is more stable, consumption higher; since release 32.4 it no longer turns the fan on by itself (`jetson_clocks --fan`). On Orin, a mode change that alters the GPU TPC mask requires a reboot, and `nvpmodel` will offer one itself. In 5 W mode the Nano loses two cores and a third of its GPU clock, so the detector, mavlink-router and the encoder end up sharing two cores.

### Power: what it really draws, and the 5 V traps
Real `tegrastats` lines from the NVIDIA forum (Jetson Nano, field `POM_5V_IN`, the 5 V input, in mW): with a CSI camera running and no load, 2.9 W; under TensorRT, a peak of 7.7 W with an average of 4.5 W. The devkit carrier adds 0.5–1.25 W, and USB peripherals add their own watts. Budget for the BEC: 10 W module + 1.25 W carrier + camera and USB Wi-Fi/LTE ≈ 15 W → 3 A; get a 5 A BEC. The Orin Nano idles at about 4 W (an NVIDIA employee's answer on the forum; the thread author's devkit drew 6.1 W in the default 25 W mode), and the ceiling is the selected mode.

Nano traps:
- The module needs **4.75–5.25 V** at its input, and the devkit expects exactly 5 V: "5.3 V" from an adjustable BEC and a sag to 4.6 V are both out of range.
- Micro-USB is rated for 2 A. The 5.5 × 2.1 mm barrel jack is rated for 4 A, but works only with jumper **J48** fitted; without it the board is powered from micro-USB.
- Pins 2 and 4 of the J41 header take 2.5 A each (5 A in total), which is convenient on board, but it is a direct 5 V input.
- Voltage drop in the wire: U = U_BEC − I·(2·L·r + R_connector). A meter-long micro-USB cable at 28 AWG (0.213 Ω/m, connector taken as 0.10 Ω): R = 0.53 Ω, so at 1.54 A (7.7 W) the board sees 4.19 V, and the 4.75 V threshold is already crossed at 0.48 A. A short 0.3 m at 24 AWG: 4.77 V at 1.54 A and 4.55 V at 3 A. The barrel jack, 0.3 m at 20 AWG (connector 0.03 Ω): 4.85 V at 3 A.

{{diagram:chart-jetson-brownout|With 5.0 V at the BEC, a meter-long micro-USB cable drops the Jetson Nano input below 4.75 V at just 0.5 A; a short 20 AWG pair into the barrel jack holds 4.8 V up to 4 A.}}

The Orin Nano devkit accepts 9–20 V: 4S (up to 16.8 V) is formally within range, while 3S under load sags to 9–10 V and below, so feed it a regulated 12 V. Power either board from a separate BEC with a common ground to the flight controller, as in the "Raspberry Pi + ArduPilot" module.

The cost in flight. A 2.0 kg quadcopter hovers at 300 W, the battery is 4S 5 Ah, the usable 80 % = 59.2 Wh → 11.84 min. Add only 10 W: 59.2 / 310 → 11.46 min (−3.2 %). Add 200 g as well (devkit carrier 77 g + module with heatsink 61 g + BEC, camera, mounting; hover power ∝ m^1.5 → 346 W): 9.97 min (−15.8 %). Mass costs five times more than watts, which is why on board you fit the module on a compact carrier, not the devkit.

### Heat and throttling
| Board | Software throttling | Hardware throttling | Shutdown |
|---|---|---|---|
| Nano, CPU | 97.0 °C | 100.5 °C | 102.0 °C (software), 102.5 °C (hardware) |
| Nano, GPU | 97.5 °C | 101.0 °C | 102.5 / 103.0 °C |
| Orin Nano, CPU/GPU/SoC | 99.0 °C | 103.0 °C | 104.5 / 105.0 °C |

On the Nano the fan turns on at 51 °C (the weighted CPU+GPU zone). Throttling reports no errors: the GPU clock in the `GR3D_FREQ` field drops, inference time grows, and the tracking loop gets stale coordinates (the "ML on board" module). Overheating to 102 °C means the companion shuts down in the air. Hence the rule: the temperature and the GPU clock go into telemetry and into the flight controller's log, with the warning set with a margin (85 °C in the lab).

### Carrier boards and mass
Nano devkit: the module is 15 g, the module with heatsink 61 g (an NVIDIA employee's answer on the forum), the carrier 77 g (a forum user's calculation from elinux, 138 − 61); 138 g in total without wires, not from a specification. Orin Nano devkit per the Carrier Board Specification: the carrier is 100 × 79 mm, the assembled devkit 103 × 90.5 × 34.8 mm and 175 g; weigh your own anyway. ArduPilot's list of companion boards includes carriers for Jetson modules: ARK Jetson PAB Carrier, Holybro Pixhawk Jetson Baseboard, Aerium Lumen. The Nano and the Orin Nano have the same connector, but check the compatibility of a particular carrier with a particular module in its documentation.

### Cameras and video
- **CSI**: the IMX219 (Raspberry Pi Camera v2, 8 MP) works on the Nano out of the box; the IMX477 (HQ, 12.3 MP) works with JetPack 4.6 through Jetson-IO (`sudo /opt/nvidia/jetson-io/jetson-io.py`). The Orin Nano has 22-pin connectors: a 15-pin ribbon needs an adapter cable.
- **USB**: `v4l2src`; MJPEG has to be decoded, which costs tens of extra milliseconds (the "Cameras and video streaming on a companion" module).
- **Capture**: `nvarguscamerasrc` delivers frames in GPU memory (`memory:NVMM`), with no copy to the CPU.
- **Encoding on the Nano** is in hardware, `nvv4l2h264enc` (the old `omxh264enc` from gst-omx is deprecated). For low latency: constant bitrate, no B-frames, frequent keyframes, SPS/PPS before every IDR:

```bash
gst-launch-1.0 nvarguscamerasrc sensor-id=0 \
  ! 'video/x-raw(memory:NVMM),width=1280,height=720,framerate=60/1,format=NV12' \
  ! nvv4l2h264enc bitrate=4000000 control-rate=1 iframeinterval=30 insert-sps-pps=true \
      maxperf-enable=true preset-level=1 \
  ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=192.168.1.10 port=5600 sync=false
```

- **The Orin Nano** has no encoder: instead of `nvv4l2h264enc` you use `nvvidconv ! 'video/x-raw,format=I420' ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=4000`. In NVIDIA's documentation (libx264 via libav, not this GStreamer pipeline: 10 Mbps CBR, resolution not stated), `ultrafast` on a 30 fps camera stream gives 30.66 fps at 38 % load per core (on all six cores), and those cores are no longer available for the detector's post-processing.

The pipelines were not run on a board (there is no Jetson): the encoder properties were checked against the Accelerated GStreamer guide, and the `sensor-id` property (also spelled `sensor_id`) against the JetsonHacks CSI-Camera examples; check the sensor name and modes with `gst-inspect-1.0 nvarguscamerasrc` and your camera's output.

### The inference stack and benchmarks
There is one path: PyTorch → ONNX → a **TensorRT engine** built on the same board (an engine is tied to the GPU and the TensorRT version, so one built on a laptop or on an Orin does not transfer to a Nano). In `ultralytics`: `model.export(format="engine", quantize=16)` for FP16 and `quantize=8, data=...` for INT8 with calibration on your own frames; the old flags `half=True` and `int8=True` are still accepted. In Q-engineering's test INT8 added no speed and hurt mAP (Maxwell has no Tensor Cores); on the Orin Nano Super INT8 cuts frame time by 17–39 % relative to FP16, but the mAP of YOLO26n drops from 0.480 to 0.449. DeepStream is a ready-made "decoder → TensorRT → tracker → encoder" pipeline on GStreamer: 6.0.1 for JetPack 4.6.x, 7.1 for JetPack 6.1.

| Board | Model | Format | ms/frame | fps | Source |
|---|---|---|---|---|---|
| Raspberry Pi 5 | YOLO26n | PyTorch, CPU | 299.09 | 3.3 | Ultralytics, 8.4.108 |
| Raspberry Pi 5 | YOLO26n | NCNN, CPU | 67.03 | 14.9 | Ultralytics |
| Raspberry Pi 5 | YOLO26s | NCNN, CPU | 172.88 | 5.8 | Ultralytics |
| Jetson Nano | YOLOv8n | TensorRT FP16 | — | 19 | Q-engineering, C++ |
| Jetson Nano | YOLOv8s | TensorRT FP16 | — | 9.25 | Q-engineering |
| Jetson Nano | YOLOv8m and larger | TensorRT FP16 | — | no data | Q-engineering |
| Orin Nano Super | YOLO26n | PyTorch, GPU | 15.60 | 64 | Ultralytics, 8.4.33 |
| Orin Nano Super | YOLO26n | TensorRT FP16 | 4.57 | 219 | Ultralytics |
| Orin Nano Super | YOLO26n | TensorRT INT8 | 3.80 | 263 | Ultralytics |
| Orin Nano Super | YOLO26s | TensorRT FP16 | 7.17 | 139 | Ultralytics |

Read the table with care: these are other people's measurements, and we ran none of them. The Ultralytics rows are inference time only, without capture, preprocessing and NMS, at a 640 px input; their Orin Nano Super is on JetPack 6.1. The Q-engineering rows are the fps of their C++ demo, FP16, inference only (their README: grabbing frames, post-processing and drawing are not counted); the input size is not stated. The models are from different generations (YOLOv8 and YOLO26), and no source states the `nvpmodel` mode, so the rows can be compared only by order of magnitude. The conclusion is robust all the same: the Nano with TensorRT gives 19 fps on a nano model, on par with a Pi 5 on its CPU alone (14.9 fps); the Orin Nano is an order of magnitude faster. NVIDIA's own 2019 benchmark for the Nano (TensorRT FP16): SSD MobileNet-V2 300 × 300 at 39 fps, Tiny YOLO v3 416 × 416 at 25 fps.

### What the Nano can run at the same time
Memory is shared: in the forum line under TensorRT, 3100 of 3957 MB are in use plus another 535 MB in swap, with the desktop running. The first step is headless: `sudo systemctl set-default multi-user.target` (per the Ultralytics Jetson guide, this frees up to ~865 MB).

- **Realistic** (an estimate from the table and the memory, not a measurement): one n/s detector in FP16 at 10–20 fps + CSI capture + hardware H.264 at 720p–1080p + mavlink-router + a pymavlink script.
- **Too much** (also an estimate): two detectors, or a detector plus VIO/SLAM; m and larger models in real time (s is already at 9 fps); ROS 2 with visualization on board; anything that needs a recent Python, PyTorch or Isaac ROS outside a container.

The Orin Nano has a different limit: no encoder (video to the ground costs CPU) and 8 GB for everything.

### UART, MAVLink, ROS 2
- Nano J41 header: pin 8 is TX, pin 10 is RX, pin 6 is GND; the device is `/dev/ttyTHS1`. Levels are **3.3 V, and the board does not tolerate 5 V**; do not connect the 5 V wire from the TELEM port.
- By default this UART carries the console: `sudo systemctl stop nvgetty && sudo systemctl disable nvgetty`, and add the user to the `dialout` group.
- ArduPilot: `SERIAL2_PROTOCOL = 2` (MAVLink 2), `SERIAL2_BAUD = 921` (the SITL default is 57). PX4: `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard`, `SER_TEL2_BAUD = 921600`.
- One UART, several consumers: `mavlink-routerd -e 192.168.1.10:14550 /dev/ttyTHS1:921600`, local scripts connect to TCP 5760 (the "MAVLink routing and transport" module); on the bench `mavproxy.py --master=/dev/ttyTHS1 --baudrate 921600` is enough. Control from code is in the "Companion + ArduPilot" module.
- ROS 2: there are no binary packages of current distributions for Ubuntu 18.04; the working path on the Nano is the `dustynv/ros:humble-ros-base-l4t-r32.7.1` containers (jetson-containers, JetPack 4.6.1+ required). On the Orin Nano with JetPack 6, Humble installs from apt (with JetPack 7.x on Ubuntu 24.04 the apt distribution is Jazzy).

### Storage, headless, autostart, shutdown
- The Nano devkit boots from microSD (at least 32 GB UHS-1) and has no NVMe slot (M.2 Key E only, for Wi-Fi); since JetPack 4.5 the kernel and root filesystem can boot from a USB drive (JetPack 4.5 release notes), but an inserted microSD takes priority (we have not verified this). The Orin Nano devkit has two M.2 Key M slots for NVMe: write logs and video there.
- First setup without a monitor: power into the barrel jack, micro-USB to a laptop, `sudo screen /dev/ttyACM0 115200`.
- Autostart: a `systemd` unit with `Type=notify`, `WatchdogSec` and `Restart=always` (step 4), as on the Raspberry Pi.
- Shutdown: before removing the battery, `sudo shutdown -h now`; cutting power during a write corrupts the filesystem. MAVLink has `MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN` with `param2 = 2` (shut down the onboard computer) for this; the lab script does not implement it.

### What to choose
{{diagram:jetson-sizing-tree|Choosing from the task: MAVLink and logic, a Pi 5; one small detector on a Nano you already own; a detector with a tracker, an Orin Nano; SLAM and several networks, an Orin NX and up.}}

The Pi 5: 5 V 5 A, a current OS, a CPU detector up to ~15 fps, and no hardware H.264 encoder either. The Nano beats it only with its encoder and the GPU CSI pipeline. The Orin Nano: when you need more than 20 fps, a tracker, or an s/m model. Its successor, the Jetson Orin Nano 2, was announced by NVIDIA on August 25, 2026 (78 TOPS, 8 GB, an 8-core CPU; module and devkit expected in the first half of 2027); this module does not cover it.

### Where it fits

- **Takes in:** power from a separate BEC with a common ground (`el-power-design`); MAVLink from a TELEM port at 921600 (`mav-routing`); frames from a CSI or USB camera (`per-camera`).
- **Hands off:** setpoints and vision results to the autopilot (`ap-companion`); H.264 video to the ground; temperature and load into the flight controller's log as `NAMED_VALUE_FLOAT`; its own watts and grams into the vehicle budget (`des-sizing`).
- **If you get this wrong:** a long thin 5 V wire → under load the Nano input drops below 4.75 V and the companion disappears in the air; on the autopilot side that is a GUIDED setpoint timeout (`ap-companion`). Overheating → throttling without errors, slower inference, and the tracking loop gets stale coordinates (`per-tracking`); you catch it by profiling in `per-edge-ml`.

## practice
The main path needs no Jetson: real `tegrastats` lines, ArduCopter 4.6.3 SITL (`-I 5`), pymavlink 2.4.50. Everything below was run, and the output is real.

### Step 1. A tegrastats sample
`tegrastats_sample.txt`: lines 1–2 are real, from the NVIDIA forum (camera with no load; TensorRT), line 3 is **synthetic**: the second line, edited by hand up to software throttling (97.5 °C, clocks cut). It is not a measurement.

```
RAM 1698/3965MB (lfb 99x4MB) CPU [16%@921,10%@921,10%@921,11%@921] EMC_FREQ 0% GR3D_FREQ 0% PLL@32.5C CPU@36C PMIC@100C GPU@33.5C AO@42.5C thermal@34.75C POM_5V_IN 2915/2915 POM_5V_GPU 40/40 POM_5V_CPU 319/319
RAM 3100/3957MB (lfb 18x1MB) SWAP 535/4096MB (cached 22MB) IRAM 0/252kB(lfb 252kB) CPU [79%@1428,100%@1428,81%@1428,83%@1428] EMC_FREQ 22%@1600 GR3D_FREQ 99%@844 APE 25 PLL@44.5C CPU@48.5C PMIC@100C GPU@43.5C AO@51C thermal@46C POM_5V_IN 7700/4490 POM_5V_GPU 2408/523 POM_5V_CPU 1224/613
RAM 3100/3957MB (lfb 18x1MB) SWAP 535/4096MB (cached 22MB) CPU [95%@918,100%@918,97%@918,98%@918] EMC_FREQ 22%@1600 GR3D_FREQ 99%@537 PLL@93.5C CPU@97.5C PMIC@100C GPU@98C AO@99C thermal@97.75C POM_5V_IN 5200/4900 POM_5V_GPU 1600/900 POM_5V_CPU 700/650
```

Format: `CPU [load%@MHz]` per core (`off` means the core is offline), `GR3D_FREQ` is GPU load and clock, `X@YC` are zone temperatures, `POM_5V_IN a/b` is the instantaneous and average power in mW.

### Step 2. The parser
`cc_health.py`, first half:

```python
#!/usr/bin/env python3
"""Companion health: tegrastats -> dict -> MAVLink HEARTBEAT + NAMED_VALUE_FLOAT + STATUSTEXT.
Jetson:  cc_health.py --link /dev/ttyTHS1 --baud 921600
No Jetson: cc_health.py --link tcp:127.0.0.1:5813 --replay tegrastats_sample.txt   (or --parse FILE)"""
import argparse, os, re, socket, subprocess, time

RE_RAM = re.compile(r"RAM (\d+)/(\d+)MB")
RE_CPU = re.compile(r"CPU \[([^\]]*)\]")
RE_CORE = re.compile(r"(\d+)%@(\d+)|off")
RE_GR3D = re.compile(r"GR3D_FREQ (\d+)%(?:@(\d+))?")
RE_TEMP = re.compile(r"([A-Za-z0-9_]+)@([\d.]+)C")
RE_PWR = re.compile(r"((?:POM_5V|VDD)_[A-Z_0-9]+) (\d+)(?:mW)?/(\d+)")


def parse_tegrastats(line):
    """One tegrastats line -> flat dict; a field missing on this board is simply absent."""
    d = {}
    if m := RE_RAM.search(line):
        d["ram_pct"] = round(100.0 * int(m[1]) / int(m[2]), 1)
    if m := RE_CPU.search(line):
        cores = [(int(a), int(b)) for a, b in RE_CORE.findall(m[1]) if a]      # 'off' cores skipped
        d["cpu_pct"] = round(sum(c[0] for c in cores) / max(1, len(cores)), 1)
        d["cpu_mhz"] = max((c[1] for c in cores), default=0)
        d["cores"] = len(cores)
    if m := RE_GR3D.search(line):
        d["gpu_pct"] = int(m[1])
        if m[2]:
            d["gpu_mhz"] = int(m[2])
    temps = {k: float(v) for k, v in RE_TEMP.findall(line)}
    temps.pop("PMIC", None)                    # PMIC@100C on Nano is a constant, not a reading
    hot = [temps[k] for k in ("CPU", "GPU", "cpu", "gpu", "tj") if k in temps]  # Nano: CPU@ GPU@; Orin: cpu@ gpu@ tj@
    d["t_max"] = max(hot or temps.values(), default=float("nan"))
    pwr = {k: int(a) for k, a, _ in RE_PWR.findall(line)}
    if (mw := pwr.get("POM_5V_IN") or pwr.get("VDD_IN")):                       # Nano / Orin total input, mW
        d["p_in_w"] = mw / 1000.0
    return d


def lines_replay(path, period, loop=True):
    while True:
        for line in open(path):
            if line.strip() and not line.startswith("#"):
                yield line.rstrip()
                time.sleep(period)
        if not loop:
            return


def lines_tegrastats(period):
    p = subprocess.Popen(["tegrastats", "--interval", str(int(period * 1000))], stdout=subprocess.PIPE, text=True)
    yield from (line.rstrip() for line in p.stdout)
```

`python3 cc_health.py --parse tegrastats_sample.txt`:

```
{'ram_pct': 42.8, 'cpu_pct': 11.8, 'cpu_mhz': 921, 'cores': 4, 'gpu_pct': 0, 't_max': 36.0, 'p_in_w': 2.915}
{'ram_pct': 78.3, 'cpu_pct': 85.8, 'cpu_mhz': 1428, 'cores': 4, 'gpu_pct': 99, 'gpu_mhz': 844, 't_max': 48.5, 'p_in_w': 7.7}
{'ram_pct': 78.3, 'cpu_pct': 97.5, 'cpu_mhz': 918, 'cores': 4, 'gpu_pct': 99, 'gpu_mhz': 537, 't_max': 98.0, 'p_in_w': 5.2}
```

Check by hand: 1698 / 3965 = 42.8 %; the average (79 + 100 + 81 + 83) / 4 = 85.8 %; `PMIC@100C` is discarded: on the Nano it is a constant, and without that line `t_max` would always be 100 °C. In the first line `GR3D_FREQ` has no frequency, so the `gpu_mhz` field is simply absent and the bridge does not send it. The sign of throttling in the third line is not the temperature by itself but 537 MHz at 99 % GPU load, against 844 MHz in the second. The Orin format (zones `cpu@`, `gpu@`, `tj@` in lowercase, `VDD_IN 5171mW/5171mW`) is handled in the expressions, but it was tested only on a line assembled from forum posts, not on a board.

### Step 3. The bridge to MAVLink, and SITL
The second half of `cc_health.py`. The bridge presents itself as a separate component of the same system: the flight controller's sysid, compid 191 (`MAV_COMP_ID_ONBOARD_COMPUTER`), and its own `HEARTBEAT` once a second. A `NAMED_VALUE_FLOAT` name is at most 10 characters.

```python
def sd_notify(msg):
    """READY=1 / WATCHDOG=1 for systemd Type=notify; no-op when started by hand."""
    if addr := os.environ.get("NOTIFY_SOCKET"):
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect("\0" + addr[1:] if addr[0] == "@" else addr)
            s.sendall(msg.encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--link", default="tcp:127.0.0.1:5813")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--replay")
    ap.add_argument("--parse")
    ap.add_argument("--period", type=float, default=1.0)
    ap.add_argument("--t-warn", type=float, default=85.0)
    ap.add_argument("--count", type=int, default=0)
    a = ap.parse_args()
    if a.parse:
        for line in lines_replay(a.parse, 0, loop=False):
            print(parse_tegrastats(line))
        return

    from pymavlink import mavutil
    mav = mavutil.mavlink
    m = mavutil.mavlink_connection(a.link, baud=a.baud, source_system=1,           # the vehicle's sysid,
                                   source_component=mav.MAV_COMP_ID_ONBOARD_COMPUTER)  # compid 191
    hb = m.wait_heartbeat(timeout=30)
    print(f"FC heartbeat: sysid={hb.get_srcSystem()} compid={hb.get_srcComponent()} autopilot={hb.autopilot}")
    sd_notify("READY=1")
    t0, n, warned = time.monotonic(), 0, False
    for line in lines_replay(a.replay, a.period) if a.replay else lines_tegrastats(a.period):
        d = parse_tegrastats(line)
        ms = int((time.monotonic() - t0) * 1000)
        m.mav.heartbeat_send(mav.MAV_TYPE_ONBOARD_CONTROLLER, mav.MAV_AUTOPILOT_INVALID, 0, 0, mav.MAV_STATE_ACTIVE)
        for name, key in (("CC_TEMP", "t_max"), ("CC_CPU", "cpu_pct"), ("CC_GPU", "gpu_pct"),
                          ("CC_RAM", "ram_pct"), ("CC_PWR_W", "p_in_w"), ("CC_GPU_MHZ", "gpu_mhz")):
            if key in d and d[key] == d[key]:                                      # skip absent and NaN
                m.mav.named_value_float_send(ms, name.encode(), float(d[key]))     # name: at most 10 chars
        hot = d["t_max"] >= a.t_warn
        if hot and not warned:                                                     # once per overheat episode
            m.mav.statustext_send(mav.MAV_SEVERITY_WARNING, f"CC hot {d['t_max']:.1f}C gpu {d.get('gpu_mhz', 0)}MHz".encode())
        warned = hot
        sd_notify("WATCHDOG=1")
        n += 1
        print(f"[{n}] T={d['t_max']}C cpu={d.get('cpu_pct')}% gpu={d.get('gpu_pct')}%@{d.get('gpu_mhz')} "
              f"ram={d.get('ram_pct')}% P={d.get('p_in_w')}W")
        if a.count and n >= a.count:
            break


if __name__ == "__main__":
    main()
```

SITL: SERIAL0 (TCP 5810) is the "ground station", SERIAL2 (TCP 5813) is "TELEM2", where the Jetson's UART arrives on board; `SERIAL2_PROTOCOL` is already 2 in SITL. The helper `sitl_tools.py`: `logon` sets `LOG_DISARMED = 1` (logging without arming), `gcs` counts the messages from compid 191 on the ground station port, `nval` reads the DataFlash log.

```python
"""SITL helpers: sitl_tools.py logon | gcs SECONDS | nval LOGFILE"""
import sys, time
from pymavlink import mavutil

if sys.argv[1] == "nval":                       # NVAL rows and companion STATUSTEXT from the DataFlash log
    log, n = mavutil.mavlink_connection(sys.argv[2]), 0
    while (msg := log.recv_match(type=["NVAL", "MSG"])) is not None:
        if msg.get_type() == "MSG":
            if "CC hot" in msg.Message:
                print(f"MSG  TimeUS={msg.TimeUS} {msg.Message}")
            continue
        n += 1
        if n <= 6 or msg.Name == "CC_GPU_MHZ":
            print(f"NVAL TimeUS={msg.TimeUS} TimeBootMS={msg.TimeBootMS} Name={msg.Name:<10} "
                  f"Value={msg.Value:.2f} SSys={msg.SSys} SCom={msg.SCom}")
    print("NVAL rows:", n)
    sys.exit()

m = mavutil.mavlink_connection("tcp:127.0.0.1:5810", source_system=255)      # SERIAL0 of SITL -I 5
m.wait_heartbeat()
m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
if sys.argv[1] == "logon":                      # log while disarmed
    m.mav.param_set_send(1, 1, b"LOG_DISARMED", 1, mavutil.mavlink.MAV_PARAM_TYPE_INT8)
    while (p := m.recv_match(type="PARAM_VALUE", blocking=True, timeout=5)) and p.param_id != "LOG_DISARMED":
        pass
    print(p.param_id, p.param_value)
else:                                           # gcs: count what arrives from the companion, compid 191
    t_end, seen = time.time() + float(sys.argv[2]), {}
    while time.time() < t_end:
        msg = m.recv_match(blocking=True, timeout=0.5)
        if msg is None or msg.get_srcComponent() != 191:
            continue
        t = msg.get_type()
        seen[t] = seen.get(t, 0) + 1
        if t == "NAMED_VALUE_FLOAT" and seen[t] <= 3:
            print(f"{t}: name={msg.name} value={msg.value:.2f} time_boot_ms={msg.time_boot_ms}")
        if t == "STATUSTEXT":
            print(f"{t}: severity={msg.severity} text={msg.text}")
    print("from compid 191:", seen)
```

```bash
mkdir sitl5 && cd sitl5
/tmp/ardupilot/build/sitl/bin/arducopter -w -S -I 5 --model + --speedup 1 \
  --home -35.363261,149.165230,584,353 --defaults /tmp/ardupilot/Tools/autotest/default_params/copter.parm &
cd ../lab
python3 sitl_tools.py logon                    # -> LOG_DISARMED 1.0
python3 sitl_tools.py gcs 10 > gcs_out.txt &
python3 cc_health.py --link tcp:127.0.0.1:5813 --replay tegrastats_sample.txt --count 6
python3 sitl_tools.py nval ../sitl5/logs/00000001.BIN      # after stopping SITL
```

Bridge output:

```
FC heartbeat: sysid=1 compid=1 autopilot=3
[1] T=36.0C cpu=11.8% gpu=0%@None ram=42.8% P=2.915W
[2] T=48.5C cpu=85.8% gpu=99%@844 ram=78.3% P=7.7W
[3] T=98.0C cpu=97.5% gpu=99%@537 ram=78.3% P=5.2W
[4] T=36.0C cpu=11.8% gpu=0%@None ram=42.8% P=2.915W
[5] T=48.5C cpu=85.8% gpu=99%@844 ram=78.3% P=7.7W
[6] T=98.0C cpu=97.5% gpu=99%@537 ram=78.3% P=5.2W
```

The ground station side (`gcs_out.txt`):

```
NAMED_VALUE_FLOAT: name=CC_TEMP value=36.00 time_boot_ms=0
NAMED_VALUE_FLOAT: name=CC_CPU value=11.80 time_boot_ms=0
NAMED_VALUE_FLOAT: name=CC_GPU value=0.00 time_boot_ms=0
STATUSTEXT: severity=4 text=CC hot 98.0C gpu 537MHz
STATUSTEXT: severity=4 text=CC hot 98.0C gpu 537MHz
from compid 191: {'HEARTBEAT': 6, 'NAMED_VALUE_FLOAT': 34, 'STATUSTEXT': 2}
```

34 = 6 cycles × 6 fields − 2 (in the lines without a GPU clock the `CC_GPU_MHZ` field was not sent). The flight controller forwarded the companion's messages to SERIAL0 by itself: that is ArduPilot's normal routing. And the main thing, the DataFlash log (`sitl_tools.py nval`, the `NVAL` and `MSG` messages):

```
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_TEMP    Value=36.00 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_CPU     Value=11.80 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_GPU     Value=0.00 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_RAM     Value=42.80 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_PWR_W   Value=2.91 SSys=1 SCom=191
NVAL TimeUS=6234172 TimeBootMS=1000 Name=CC_TEMP    Value=48.50 SSys=1 SCom=191
NVAL TimeUS=6234172 TimeBootMS=1000 Name=CC_GPU_MHZ Value=844.00 SSys=1 SCom=191
NVAL TimeUS=7234605 TimeBootMS=2001 Name=CC_GPU_MHZ Value=537.00 SSys=1 SCom=191
MSG  TimeUS=7234605 SRC=1/191:CC hot 98.0C gpu 537MHz
NVAL TimeUS=9237137 TimeBootMS=4002 Name=CC_GPU_MHZ Value=844.00 SSys=1 SCom=191
NVAL TimeUS=10236737 TimeBootMS=5002 Name=CC_GPU_MHZ Value=537.00 SSys=1 SCom=191
MSG  TimeUS=10236737 SRC=1/191:CC hot 98.0C gpu 537MHz
NVAL rows: 34
```

What this gives you: the companion's temperature and GPU clock sit in the same log as `ATT` and `CTUN`, on the common `TimeUS` axis, so after the flight you can see whether a tracking dropout coincided with throttling. `TimeBootMS` is the script's time, not the flight controller's; use `TimeUS` to line things up. In PX4 the same message lands in the uORB topic `debug_key_value`; it is written to the ULog when bit 5 (Debug) of `SDLOG_PROFILE` is set, and reaches the ground station with `MAV_1_FORWARD = 1` (not tested on PX4 SITL).

### Step 4. A unit with a watchdog
`/etc/systemd/system/cc-health.service` (syntax checked with `systemd-analyze verify`; not run on a board):

```ini
[Unit]
Description=Companion health to MAVLink (tegrastats)
After=mavlink-router.service
Wants=mavlink-router.service

[Service]
Type=notify
NotifyAccess=main
ExecStart=/usr/bin/python3 /opt/uav/cc_health.py --link tcp:127.0.0.1:5760
WatchdogSec=10
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

`READY=1` goes out after the first flight controller heartbeat, `WATCHDOG=1` on every `tegrastats` line: if `tegrastats` or the port hangs, systemd restarts the service after 10 s. Record in your notes the table of the three lines from step 2 and the `NVAL` count from your own log.

### Moving to real hardware
Props off until the last item; the flight controller on the desk, the Jetson powered from a bench supply or from the BEC that will go on board.

1. **Flashing.** Nano: a JetPack 4.6.x image on a microSD ≥ 32 GB, first setup over micro-USB (`/dev/ttyACM0`), power into the barrel jack with jumper J48. Orin Nano: JetPack 6.2 (the course's version) per the devkit guide, then `sudo nvpmodel -q`. Right away: `sudo systemctl set-default multi-user.target`, and record the free memory before and after (`free -m`).
2. **Power and heat per mode.** For each `nvpmodel` mode (Nano: 0 and 1; Orin: 0, 1, 2): `sudo nvpmodel -m N`, `tegrastats --interval 1000 --logfile mode_N.log`, 20 minutes of the detector (the Ultralytics container, `yolo predict` on a video file with an FP16 engine) in the enclosure the board will fly in. With a multimeter: the voltage on header pins 2/6 under load. Into the table: fps in the first and the twentieth minute, average and peak input power, maximum temperature, minimum GPU clock, minimum voltage.
3. **UART loopback.** Flight controller disconnected, a jumper between pins 8 and 10, `nvgetty` disabled: a line sent to `/dev/ttyTHS1` at 921600 baud must come back (the loopback script is in the "PX4 + Jetson Orin" module, step 2).
4. **MAVLink to the flight controller.** TX→RX, RX→TX, GND; do not connect the 5 V from TELEM. `SERIAL2_PROTOCOL = 2`, `SERIAL2_BAUD = 921`, reboot the flight controller. `python3 cc_health.py --link /dev/ttyTHS1 --baud 921600 --count 60`, this time with the real `tegrastats`; then mavlink-router and the unit from step 4.
5. **Failures.** Freeze the service (`sudo kill -STOP <PID>`): a restart after 10 s. Pull the Jetson's power: the flight controller keeps working, and the ground station sees the heartbeat of component 191 disappear. Ten cold starts in a row: the service comes up by itself every time.
6. **With props**: only a tethered or netted hover, 5 minutes, with the detector under load; afterwards, check `NVAL` in the log.

Hardware criteria: the board voltage ≥ 4.75 V at peak (Nano); the maximum temperature over 20 minutes at least 10 °C below software throttling (≤ 87 °C Nano, ≤ 89 °C Orin Nano); fps in the twentieth minute no lower than 90 % of the first; the GPU clock at ≥ 90 % load in the twentieth minute no lower than in the first; the UART loopback 100 out of 100 lines; `NVAL` with `SCom = 191` in the flight controller's log arrives at 1 Hz with no gaps longer than 3 s.

Self-check: the lab is done when: (SITL) the parser gives the same values as above on the three sample lines, and you can recompute `ram_pct` and `cpu_pct` by hand; the bridge in SITL produces `NVAL` with `SCom = 191` in the DataFlash log, a `HEARTBEAT` from component 191 and a `STATUSTEXT` on the ground station side, and the `NVAL` count is explained; the power budget of your build and the board voltage for your wire have been calculated with the formula; (hardware, if you have a board) the `nvpmodel` mode table is filled in and the hardware criteria above are met.

## diagnostics
- **Symptom:** the Nano shuts down or reboots when inference starts, but runs fine at idle
  - Possible cause: power through micro-USB or a long thin wire; less than 4.75 V at the input at 1.5–3 A.
  - What to do: the barrel jack or pins 2/4, with jumper J48 set accordingly, a 20 AWG pair no longer than 30 cm, a 5.0–5.25 V BEC rated for 5 A; measure the voltage on the header under load.
  - What the log shows: `NVAL CC_PWR_W` stops at the peak, and the heartbeat of component 191 disappears.
- **Symptom:** the barrel jack is connected, but the board does not start
  - Possible cause: no J48 jumper, so the input is switched to micro-USB.
  - What to do: fit the jumper; check the plug polarity (center positive).
- **Symptom:** the detector fps drops after 5–10 minutes, with no errors
  - Possible cause: software throttling at about 97 °C (Nano) or 99 °C (Orin Nano), a closed enclosure, the fan not running.
  - What to do: a heatsink with airflow, `jetson_clocks --fan` on the bench, a lower `nvpmodel` mode, a smaller model or resolution.
  - What the log shows: `CC_GPU_MHZ` drops while `CC_GPU` is around 99 %, and `CC_TEMP` is at the threshold.
- **Symptom:** `Killed` while building an engine or when starting a second process with a model
  - Possible cause: the 4 GB of shared memory ran out; the desktop takes hundreds of megabytes.
  - What to do: headless mode, swap while building the engine, one model, n/s size.
- **Symptom:** garbage or "Permission denied" on `/dev/ttyTHS1`
  - Possible cause: the `nvgetty` console holds the port; the user is not in `dialout`; the baud rate does not match `SERIAL2_BAUD`.
  - What to do: disable `nvgetty`, add the group, match the baud rate; check with the 8–10 loopback.
- **Symptom:** the flight controller heartbeat is there, but there is no `NVAL` in the log
  - Possible cause: no logging without arming (`LOG_DISARMED = 0`); the bridge sends with a foreign sysid; the port is not MAVLink 2.
  - What to do: `LOG_DISARMED = 1` for the bench session, `source_system` equal to the vehicle's sysid, `SERIAL2_PROTOCOL = 2`.
- **Symptom:** `nvv4l2h264enc` is not found or cannot open the device on the Orin Nano
  - Possible cause: the Orin Nano has no NVENC.
  - What to do: `x264enc tune=zerolatency speed-preset=ultrafast`, and budget about two CPU cores for it.
- **Symptom:** `pip install ultralytics` will not install on the Nano or pulls in an incompatible PyTorch
  - Possible cause: Ubuntu 18.04 with Python 3.6 and CUDA 10.2: there are no wheels for them.
  - What to do: the `ultralytics/ultralytics:latest-jetson-jetpack4` container; build the engine on the board itself.
- **Symptom:** an engine built on another Jetson or a PC will not load
  - Possible cause: an engine is tied to the GPU and the TensorRT version.
  - What to do: transfer the ONNX, and build the engine on the target board.
- **Symptom:** the service restarts every 10 s
  - Possible cause: `tegrastats` is not running or not found: no lines, so no `WATCHDOG=1`.
  - What to do: `journalctl -u cc-health`, run the script by hand, check the path to `tegrastats`.
  - Consequences: gaps in `NVAL` every 10 s, which also show it after the flight.
- **Symptom:** after a hard power-off the board does not boot
  - Possible cause: the microSD filesystem is corrupted.
  - What to do: shut down with the command before removing the battery, logs on a separate partition or drive, the systemd journal in RAM (the "Raspberry Pi + ArduPilot" module).

## checklist
- I know which board I have: the Nano (JetPack 4.6.x, EOL) or the Orin Nano (JetPack 6.x in the course; 7.2.x since 2026)
- Power: a separate BEC, 4.75–5.25 V at the Nano input at peak current, jumper J48 set accordingly
- The `nvpmodel` mode is chosen and recorded; headless boot is enabled
- 20 minutes under the detector in the flight enclosure: no throttling, a margin of ≥ 10 °C
- The camera and the video pipeline are tested; on the Orin Nano the software encoder is budgeted for
- The engine is built on the target board, FP16; INT8 only after checking mAP on your own data
- UART: `nvgetty` disabled, 3.3 V, the loopback passes, `SERIAL2_PROTOCOL = 2`, the baud rates match
- The health bridge runs as a service with a watchdog, and `NVAL` is in the flight controller's log
- A Jetson failure or shutdown on the bench does not affect the flight controller

## references
- Jetson Nano Developer Kit User Guide (power J25/J28/J48/J41, 4.75 V, IMX219) | https://developer.download.nvidia.com/embedded/L4T/r32-3-1_Release_v1.0/Jetson_Nano_Developer_Kit_User_Guide.pdf | primary | A
- Jetson Nano Data Sheet DS-09366-001 v1.1 (a distributor's copy) | https://openzeka.com/en/wp-content/uploads/2022/08/JetsonNano_DataSheet_DS09366001v1.1-1.pdf | primary | A
- Jetson Linux 32.7.6 Developer Guide — Power Management for Jetson Nano (nvpmodel, jetson_clocks, thermal thresholds) | https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3276/Tegra%20Linux%20Driver%20Package%20Development%20Guide/power_management_nano.html | primary | A
- Jetson Linux 32.7.6 Developer Guide — tegrastats Utility | https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3276/Tegra%20Linux%20Driver%20Package%20Development%20Guide/AppendixTegraStats.html | primary | A
- Jetson Linux 36.4.3 Developer Guide — Orin Nano: nvpmodel modes, thermal thresholds | https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html | primary | A
- Jetson Linux Developer Guide — Software Encode in Orin Nano | https://docs.nvidia.com/jetson/archives/r36.5.2/DeveloperGuide/SD/Multimedia/SoftwareEncodeInOrinNano.html | primary | A
- Jetson Linux Developer Guide — Accelerated GStreamer | https://docs.nvidia.com/jetson/l4t/Tegra%20Linux%20Driver%20Package%20Development%20Guide/accelerated_gstreamer.html | primary | A
- Jetson Product Lifecycle | https://www.developer.nvidia.com/embedded/lifecycle | primary | A
- Announcing End of Life for NVIDIA JetPack 4 with the release of JetPack 4.6.6 | https://forums.developer.nvidia.com/t/announcing-end-of-life-for-nvidia-jetpack-4-with-the-release-of-jetpack-4-6-6/314409 | primary | A
- JetPack 4.6.6 (component versions) | https://developer.nvidia.com/jetpack-sdk-466 | primary | A
- JetPack 4.6 Release Notes (IMX477 through Jetson-IO) | https://docs.nvidia.com/jetson/archives/jetpack-archived/jetpack-46/release-notes/index.html | primary | A
- JetPack 6.2 Release Notes (Super mode) | https://docs.nvidia.com/jetson/jetpack/6.2/release-notes/index.html | primary | A
- NVIDIA Jetson Orin — technical specifications | https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/ | primary | A
- Jetson Orin Nano Developer Kit Carrier Board Specification (a copy) | https://uelectronics.com/wp-content/uploads/2023/05/Jetson-Orin-Nano-DevKit-Carrier-Board-Specification.pdf | primary | B
- Jetson Orin Nano Developer Kit User Guide — Hardware Layout | https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html | primary | A
- Getting Started with Jetson Nano Developer Kit (microSD, headless) | https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-devkit | primary | A
- Jetson Nano Brings AI Computing to Everyone (NVIDIA benchmarks, encoder) | https://developer.nvidia.com/blog/jetson-nano-ai-computing/ | primary | B
- ArduPilot 4.7.3 — GCS_Common.cpp, handle_named_value → NVAL | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/GCS_MAVLink/GCS_Common.cpp | primary | A
- PX4 1.18 — mavlink_receiver.cpp, NAMED_VALUE_FLOAT → debug_key_value | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/mavlink/mavlink_receiver.cpp | primary | A
- MAVLink common.xml (NAMED_VALUE_FLOAT, MAV_COMP_ID_ONBOARD_COMPUTER, MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A
- ArduPilot Dev — Companion Computers | https://ardupilot.org/dev/docs/companion-computers.html | primary | A
- mavlink-router — source and README | https://github.com/mavlink-router/mavlink-router | primary | A
- Raspberry Pi — H.264 encoding performance on Raspberry Pi 5 | https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-010033-WP-1-H.264%20encoding%20performance%20on%20Raspberry%20Pi%205_series%20computers.pdf | primary | A
- Power supply considerations for Jetson Nano Developer Kit (NVIDIA forum) | https://forums.developer.nvidia.com/t/power-supply-considerations-for-jetson-nano-developer-kit/71637 | primary | B
- Ultralytics — NVIDIA Jetson guide (YOLO26 benchmarks, containers, memory) | https://docs.ultralytics.com/guides/nvidia-jetson/ | secondary | B
- Ultralytics — Raspberry Pi guide (YOLO26 benchmarks on the Pi 5) | https://docs.ultralytics.com/guides/raspberry-pi/ | secondary | B
- Ultralytics — TensorRT export (quantize, INT8 calibration) | https://github.com/ultralytics/ultralytics/blob/main/docs/en/integrations/tensorrt.md | secondary | B
- Q-engineering — YoloV8 TensorRT Jetson (Orin) Nano, FPS table | https://github.com/Qengineering/YoloV8-TensorRT-Jetson_Nano | secondary | B
- jetson-containers — ROS 2 images for L4T r32.7.1 | https://github.com/dusty-nv/jetson-containers/blob/master/packages/physicalAI/ros/README.md | secondary | B
- JetsonHacks — Jetson Nano UART (ttyTHS1, nvgetty) | https://jetsonhacks.com/2019/10/10/jetson-nano-uart/ | secondary | B
- NVIDIA forum — Power consumption monitoring (the tegrastats sample lines) | https://forums.developer.nvidia.com/t/power-consumption-monitoring/73608 | secondary | B
- JetPack 4.5 Release Notes (booting the Nano from USB/NVMe, microSD priority) | https://docs.nvidia.com/jetson/archives/jetpack-archived/jetpack-45/release-notes/index.html | primary | A
- JetsonHacks — CSI-Camera (nvarguscamerasrc sensor-id) | https://github.com/JetsonHacksNano/CSI-Camera | secondary | B
- NVIDIA forum — Weight of boards (module and devkit mass) | https://forums.developer.nvidia.com/t/weight-of-boards/175292 | secondary | C
- NVIDIA forum — Jetson Orin Nano 8GB: lowest operating power consumption (idle around 4 W) | https://forums.developer.nvidia.com/t/jetson-orin-nano-8gb-lowest-theoretical-operating-power-consumption/348662 | secondary | C
