---
id: comp-raspberry
title: "Raspberry Pi + ArduPilot"
level: L3
readingTime: 30 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - Raspberry Pi
  - MAVLink
  - Linux
related:
  - comp-mavlink
  - ap-companion
next:
  - ap-companion
source: content/companion/comp-raspberry.md
source_hash: f323785e3f3a
---

## summary
An onboard Raspberry Pi is the classic first companion: Linux, Python, a camera, Wi-Fi. This module takes you from the wire to a working service: connecting to an ArduPilot telemetry port, setting up the UART on the Pi, checking with MAVProxy, routing MAVLink to several consumers at once, the power budget and throttling control, protecting the SD card from power loss, and your own script as a system service with a watchdog timer.

## theory
### Wiring
The FC telemetry port (for example TELEM2 = `SERIAL2`) ↔ the Pi UART: TX → RX, RX → TX, common GND. 3.3 V levels on both sides. On the FC:

- `SERIAL2_PROTOCOL = 2` — MAVLink 2;
- `SERIAL2_BAUD = 921` — 921600 baud; for short wires and a heavy telemetry stream this is normal, for long ones use 57 (57600).

Power the Pi from a separate 5 V BEC with current headroom (a Pi 4/5 under load draws more than an amp), not from the FC telemetry port.

### UART on the Raspberry Pi
By default the UART is taken by the Linux console. In `raspi-config` → Interfacing → Serial: login shell over serial — **no**, hardware port — **yes**. After a reboot the port is available as `/dev/serial0` — that's on the Pi 3/4. **On the Pi 5** `/dev/serial0` points to the debug connector (`/dev/ttyAMA10`), while the UART on GPIO 14/15 is enabled with the line `dtparam=uart0=on` in `/boot/firmware/config.txt` and is called `/dev/ttyAMA0` — substitute it in the examples below. On the Pi 3/4 the main UART is given to Bluetooth by default, and the GPIO gets the mini-UART, whose baud rate “floats” with the core clock: for a stable 921600 use `enable_uart=1` and `dtoverlay=disable-bt` in `config.txt`.

### Routing
One UART, but several consumers: the GCS over Wi-Fi, your script, tlog recording. The solution is a MAVLink router: `mavlink-router` or `mavp2p` reads the port and serves it over UDP/TCP to everyone connected. Scripts then connect to a local UDP port rather than to `/dev/serial0` directly, and don't get in each other's way.

{{diagram:mavlink-routing|mavlink-router serves one FC UART stream to several consumers: the GCS, your scripts and a logger.}}

### A service instead of “I started it by hand”
A script started from a terminal over SSH dies with the session. Onboard, everything must start by itself: a `systemd` unit with `Restart=always`. Logs go to `journalctl`.

### Time and logs
A Pi without a network has no accurate time after boot. To match companion logs with the FC DataFlash, use `SYSTEM_TIME` from MAVLink (GPS time) or write `TimeUS`-like monotonic counter stamps and the moment of synchronization to the log.

### Power: a budget, not “some BEC”
The Raspberry Pi 5 is rated for 5.1 V / 5 A (27 W): idle it draws about 3 W, under full CPU load 7–8 W, plus the camera, a USB modem or a Wi-Fi adapter on top. An example budget:

| Consumer | Power | Current at 5 V |
|---|---|---|
| Pi 5 under load | 8 W | 1.6 A |
| CSI camera | 1.5 W | 0.3 A |
| USB Wi-Fi / LTE modem | 2.5 W | 0.5 A |
| **Total** | **12 W** | **2.4 A** |

Pick the BEC with at least one and a half to two times headroom (5 A), and the wire short and thick: 30 cm of a 22 AWG pair (≈ 53 mΩ/m per conductor, out and back ≈ 32 mΩ) loses ≈ 0.08 V at 2.4 A. Peak surges (camera start, modem transmission) sag the voltage more than the average — so you need at least ~4.9 V at the Pi connector under load.

### Overheating and voltage sag show up in numbers
`vcgencmd get_throttled` returns a bitmask: bit 0 — undervoltage right now, 1 — frequency capped, 2 — throttling, 3 — soft temperature limit; bits 16–19 — the same, “has occurred since boot”. `0x0` — all good, `0x50000` — there was undervoltage and throttling; `0x50005` — it's happening right now. Temperature — `vcgencmd measure_temp`; without a heatsink and airflow a Pi 5 under load starts throttling within minutes, and even more so inside a drone body with no airflow. A vision algorithm that “suddenly got slower in flight” is almost always this.

### Power loss without a broken SD card
On a drone the power disappears without a `shutdown` — after a crash, when swapping batteries. A write at the moment of power loss corrupts the SD card's file system. Two approaches that work:
- **Overlay File System** (`raspi-config` → Performance Options → Overlay File System): the root is read-only, changes live in RAM and vanish after a reboot. The system is unkillable, but logs and records have to be written to a separate partition or a USB drive.
- **Writing like a grown-up**: logs on a separate partition or a USB SSD, `f.flush()` + `os.fsync()` for anything important, the systemd journal in RAM (`Storage=volatile` in `/etc/systemd/journald.conf`) so it doesn't wear out the card.

### A service with a watchdog timer
A script started from a terminal over SSH dies with the session. Onboard, everything starts by itself: a `systemd` unit with `Restart=always`. If the script can hang rather than crash (a socket, the camera, an infinite loop), you also need a watchdog timer: `Type=notify` and `WatchdogSec=` — systemd restarts the service if it stops reporting “I'm alive”. Without messages from the script, `WatchdogSec` simply kills it every N seconds — almost everyone falls into this trap. A working version is in the practice section, step 3.

### Time and logs
A Pi without an RTC and without a network boots into 1970 — absolute timestamps before synchronization are meaningless. The practical way: at startup the script writes a pair (`SYSTEM_TIME.time_unix_usec` from MAVLink — the GPS time from the flight controller, and its own `time.monotonic()`) and then uses monotonic stamps; during analysis the companion logs are matched to the flight controller's DataFlash using this pair. The Pi 5 has an RTC battery connector — with a battery the time survives a reboot without a network.

## practice
### Step 1. The port and a check
```
sudo raspi-config        # Interfacing Options -> Serial: console NO, hardware YES
sudo reboot
pip install --user pymavlink MAVProxy
mavproxy.py --master=/dev/serial0 --baudrate 921600
```

If you see the heartbeat and the parameters, the link works. Give the `arm throttle` command on the bench only with the props off.

### Step 2. The router
An example `mavlink-router` configuration (`/etc/mavlink-router/main.conf`):

```
[General]
TcpServerPort=5760
ReportStats=false

[UartEndpoint fc]
Device=/dev/serial0
Baud=921600

[UdpEndpoint gcs]
Mode=Normal
Address=192.168.4.20
Port=14550

[UdpEndpoint local]
Mode=Server
Address=127.0.0.1
Port=14551
```

The GCS on the laptop receives the stream on 14550, local scripts connect to `udpout:127.0.0.1:14551` or `tcp:127.0.0.1:5760`.

### Step 3. Your own service with a watchdog timer
`/opt/uav/telemetry_logger.py` writes the position and battery to a CSV and once per loop tells systemd it's alive:

```python
import csv, os, socket, time
from pymavlink import mavutil

def sd_notify(msg: str) -> bool:
    """Send a state line to systemd (READY=1, WATCHDOG=1, STATUS=...). No-op outside systemd."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    if addr[0] == "@":                      # abstract socket namespace
        addr = "\0" + addr[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
        s.connect(addr)
        s.sendall(msg.encode())
    return True

m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
m.wait_heartbeat()
sd_notify("READY=1")
os.makedirs("/var/log/uav", exist_ok=True)
with open("/var/log/uav/telemetry.csv", "a", newline="") as f:
    w = csv.writer(f)
    while True:
        msg = m.recv_match(type=["GLOBAL_POSITION_INT", "BATTERY_STATUS"], blocking=True, timeout=1)
        if msg is not None:
            w.writerow([time.monotonic(), msg.get_type(), msg.to_dict()])
            f.flush()
        sd_notify("WATCHDOG=1")             # the loop is alive even when no message came
```

`/etc/systemd/system/uav-telemetry.service`:

```ini
[Unit]
Description=UAV telemetry logger
After=mavlink-router.service
Requires=mavlink-router.service

[Service]
Type=notify
NotifyAccess=main
ExecStart=/usr/bin/python3 /opt/uav/telemetry_logger.py
WatchdogSec=10
Restart=always
RestartSec=2
User=pi

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now uav-telemetry
journalctl -u uav-telemetry -f
```
Testing the watchdog timer: `sudo kill -STOP $(systemctl show -p MainPID --value uav-telemetry)` freezes the process — after 10 s the journal shows `Watchdog timeout`, and systemd restarts the service.

### Step 4. Power and temperature under load
Load the CPU (`stress-ng --cpu 4 --timeout 300s` or your own vision algorithm) and record `vcgencmd measure_temp` and `vcgencmd get_throttled` every 10 s. Record: after how many seconds throttling started (if it did), and whether there was undervoltage. Repeat with a heatsink or a fan and with a different BEC.

### Step 5. Rehearse a failure
Pull the Pi's power on the bench (the FC on the table, props off): the FC keeps working, the GCS loses the stream, and after the Pi powers back on the service comes up by itself. Repeat 10 times in a row: does the system boot every time? With the Overlay File System — repeat once more and make sure the logs are written where they survive a reboot. This is exactly the boundary of responsibility from the introductory module.

The lab counts as done when MAVLink goes through the router to several clients, the service with the watchdog timer restarts after being frozen, the power budget is calculated and the temperature with the throttling flags is recorded under load, and 10 power cuts are survived without manual intervention.

## diagnostics
- **Symptom:** MAVProxy doesn't see a heartbeat
  - Possible cause: the Linux console holds the port, the wrong baud rate, TX/RX swapped.
  - What to do: `raspi-config`, compare with `SERIAL2_BAUD`, check the wires.
- **Symptom:** garbage in the data at 921600
  - Possible cause: long wires, interference, a bad GND.
  - What to do: shorten, shield or drop to 57600.
- **Symptom:** a second script can't open the port
  - Possible cause: `/dev/serial0` is taken by the first one.
  - What to do: a MAVLink router, clients over UDP/TCP.
- **Symptom:** the Pi reboots under throttle
  - Possible cause: weak power.
  - What to do: a BEC with headroom, a capacitor, a separate line from the power bus.
- **Symptom:** garbage or no data on `/dev/serial0`
  - Possible cause: the console on the UART, the mini-UART with a floating baud rate, Bluetooth on the same port.
  - What to do: `raspi-config` (console off, UART on), `disable-bt`, 921600 only on the full UART.
- **Symptom:** the service restarts every few seconds with no errors in the log
  - Possible cause: `WatchdogSec` is set, but the script doesn't send `WATCHDOG=1` (or the unit isn't `Type=notify`).
  - What to do: `sd_notify` in the main loop, or remove `WatchdogSec`.
- **Symptom:** the algorithm is slower onboard than on the bench
  - Possible cause: throttling due to temperature or undervoltage.
  - What to do: `vcgencmd get_throttled`, a heatsink and airflow, a BEC with headroom.
- **Symptom:** after a hard power cut the Pi doesn't boot
  - Possible cause: the SD card file system is corrupted.
  - What to do: Overlay File System or logs on a separate medium, `Storage=volatile` for the journal.
- **Symptom:** the script works over SSH and “dies” after disconnecting
  - Possible cause: it isn't a service.
  - What to do: a systemd unit with Restart=always.

## references
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- Raspberry Pi — Configuration (UART, vcgencmd, power supply) | https://www.raspberrypi.com/documentation/computers/config_txt.html | primary | A
- systemd.service — Type=notify, WatchdogSec | https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html | primary | A
- mavlink-router — source code (GitHub) | https://github.com/mavlink-router/mavlink-router | primary | A
- mavp2p — source code (GitHub) | https://github.com/bluenviron/mavp2p | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A

## checklist
- The Linux console is removed from the UART, the `/dev/serial0` port is available
- `SERIAL2_PROTOCOL`/`SERIAL2_BAUD` match the Pi setup
- The Pi is powered from a separate BEC
- The router serves MAVLink to several clients
- The script runs as a `systemd` service with auto-restart and a watchdog timer
- The power budget is calculated, throttling checked under load
- The file system survives a power cut
- A Pi failure on the bench doesn't affect the FC
