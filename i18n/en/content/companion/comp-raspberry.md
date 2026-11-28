---
id: comp-raspberry
title: "Raspberry Pi + ArduPilot"
level: L3
readingTime: 30 min
firmware: ArduPilot 4.7 (checked against 4.7.3)
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
source_hash: bf1adb58b2fe
---

## summary
A Raspberry Pi on board is the classic first companion: Linux, Python, a camera, Wi-Fi. This module takes you from the wire to a working service: connecting to an ArduPilot telemetry port, setting up the UART on the Pi, checking with MAVProxy, routing MAVLink to several consumers at once, the power budget and throttling checks, protecting the SD card from power loss, and your own script as a system service with a watchdog.

## theory
### Wiring
An FC telemetry port (TELEM2 = `SERIAL2`, for example) ↔ the Pi UART: TX → RX, RX → TX, common GND. 3.3 V levels on both sides. On the FC:

- `SERIAL2_PROTOCOL = 2`: MAVLink 2;
- `SERIAL2_BAUD = 921`: 921600 baud; normal for short wires and heavy telemetry traffic; for long wires use 57 (57600).

Power the Pi from a dedicated 5 V BEC with current headroom (a Pi 4/5 under load draws more than an amp), not from the FC telemetry port.

### The UART on a Raspberry Pi
By default the UART is taken by the Linux console. In `raspi-config` → Interface Options → Serial Port: login shell over serial, **no**; serial port hardware, **yes**. After a reboot the port is available as `/dev/serial0`, on a Pi 3/4. **On a Pi 5**, `/dev/serial0` points to the debug connector (`/dev/ttyAMA10`), while the UART on GPIO 14/15 is enabled with the line `dtoverlay=uart0-pi5` (as the Raspberry Pi documentation has it; `dtparam=uart0=on` is also used) in `/boot/firmware/config.txt` and is called `/dev/ttyAMA0`; substitute it in the examples below. On a Pi 3/4 the primary UART is given to Bluetooth by default, which leaves the mini UART on the GPIO, and its baud rate "drifts" with the core clock: for a stable 921600, put `enable_uart=1` and `dtoverlay=disable-bt` in `config.txt`.

### Routing
One UART, several consumers: a GCS over Wi-Fi, your script, tlog recording. The answer is a MAVLink router: `mavlink-router` or `mavp2p` reads the port and hands the stream out over UDP/TCP to everyone connected. Your scripts then connect to a local UDP port instead of `/dev/serial0` directly, and they do not get in each other's way.

{{diagram:mavlink-routing|mavlink-router hands one FC UART stream to several consumers: the GCS, your scripts, and a logger.}}

### Power: a budget, not "some BEC"
A Raspberry Pi 5 is specified for 5.1 V / 5 A (27 W): it draws about 3 W idle and 7–8 W under full CPU load, plus the camera, a USB modem, or a Wi-Fi adapter on top. An example budget:

| Consumer | Power | Current at 5 V |
|---|---|---|
| Pi 5 under load | 8 W | 1.6 A |
| CSI camera | 1.5 W | 0.3 A |
| USB Wi-Fi / LTE modem | 2.5 W | 0.5 A |
| **Total** | **12 W** | **2.4 A** |

Pick a BEC rated at one and a half to two times the load at the very least (5 A), and keep the wire short and thick: 30 cm of a 22 AWG pair (≈ 53 mΩ/m per conductor, ≈ 32 mΩ out and back) loses ≈ 0.08 V at 2.4 A. Peak surges (the camera starting, the modem transmitting) pull the voltage down further than the average, which is why the Pi connector should see no less than ~4.9 V under load.

### Overheating and undervoltage show up in numbers
`vcgencmd get_throttled` returns a bit mask: bit 0 is undervoltage right now, 1 frequency capped, 2 throttled, 3 soft temperature limit; bits 16–19 are the same flags as "has occurred since boot". `0x0` means all is well, `0x50000` means there was undervoltage and throttling; `0x50005` means it is happening right now. Temperature is `vcgencmd measure_temp`; without a heatsink and airflow a Pi 5 under load starts throttling within minutes, and even more so inside a drone body with no airflow. A vision algorithm that "suddenly got slower in flight" almost always comes down to this.

{{diagram:rpi-throttled-bits|The get_throttled mask bit by bit: the high nibble repeats the low one as "has occurred since boot", so 0x50000 means it happened, and 0x50005 means it is happening now.}}

### Losing power without breaking the SD card
On a drone, power goes away without a `shutdown`: after a crash, on a battery swap. A write at the moment of power loss corrupts the SD card's file system. Two approaches that work:
- **Overlay File System** (`raspi-config` → Performance Options → Overlay File System): the root is read-only, changes live in RAM and vanish after a reboot. The system is indestructible, but logs and recordings have to go to a separate partition or a USB drive.
- **Writing properly**: logs on a separate partition or a USB SSD, `f.flush()` + `os.fsync()` for anything important, and the systemd journal in RAM (`Storage=volatile` in `/etc/systemd/journald.conf`) so it does not wear out the card.

### A service instead of "started it by hand", with a watchdog
A script started from a terminal over SSH dies with the session. On board, everything must start by itself: a `systemd` unit with `Restart=always`, logs in `journalctl`. If the script can hang rather than crash (a socket, a camera, an infinite loop), you also need a watchdog: `Type=notify` and `WatchdogSec=`, and systemd restarts the service when it stops reporting "I'm alive". Without those reports from the script, `WatchdogSec` simply kills it every N seconds; almost everyone falls into this trap. A working setup is in the practice section, step 3.

### Time and logs
A Pi without an RTC and without a network boots with a stale clock (the time saved at the last shutdown by fake-hwclock, or 1970 on a bare system): there is no accurate time after boot, and absolute timestamps before synchronization are meaningless. A practical approach: at startup the script records a pair (`SYSTEM_TIME.time_unix_usec` from MAVLink, the flight controller's GPS time, and its own `time.monotonic()`) and from then on uses monotonic timestamps (a `TimeUS`-like counter plus the recorded synchronization moment); during analysis the companion logs are matched to the flight controller's DataFlash log using that pair. The Pi 5 has an RTC battery connector; with a battery, the time survives a power-off without a network.

### Where it fits in the system

- **Takes in:** MAVLink from the FC telemetry port at 921600 (`comp-mavlink`); 5 V from a dedicated BEC with current headroom (`el-power-design`); GPS time through `SYSTEM_TIME`.
- **Puts out:** one FC stream to several clients through mavlink-router (`mav-routing`); setpoints from your scripts to the autopilot (`ap-companion`); logs with monotonic timestamps for matching against DataFlash (`ap-logs`).
- **If you get this wrong:** the mini UART is still in use on a Pi 3/4 → the baud rate drifts with the core clock, there is no stable 921600, and the GCS sees packet loss (`mav-routing`). Undervoltage or overheating → throttling, the vision algorithm "suddenly got slower", and the loop latency grows (`per-edge-ml`).

## practice
### Step 1. The port and a check
```
sudo raspi-config        # Interface Options -> Serial Port: login shell NO, hardware YES
sudo reboot
python3 -m venv ~/uav && . ~/uav/bin/activate && pip install pymavlink MAVProxy
mavproxy.py --master=/dev/serial0 --baudrate 921600
```

Since Bookworm, `pip` refuses to install packages outside a virtual environment (`externally-managed-environment`), hence the `~/uav` venv. If you see the heartbeat and the parameters, the link works. Only send the `arm throttle` command on the bench with the props off.

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

The GCS on the laptop receives the stream on 14550; local scripts connect to `udpout:127.0.0.1:14551` or `tcp:127.0.0.1:5760`.

### Step 3. Your own service with a watchdog
`/opt/uav/telemetry_logger.py` writes position and battery data to a CSV and tells systemd it is alive once per loop:

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
ExecStart=/home/pilot/uav/bin/python3 /opt/uav/telemetry_logger.py
WatchdogSec=10
Restart=always
RestartSec=2
User=pilot
LogsDirectory=uav

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now uav-telemetry
journalctl -u uav-telemetry -f
```
`pilot` is a placeholder: since 2022 Raspberry Pi OS has no default `pi` user, so put the user you created in Raspberry Pi Imager into `User=` and the `ExecStart=` path. `LogsDirectory=uav` makes systemd create `/var/log/uav` owned by that user; without it the script, running without root, cannot create the directory in `/var/log` and the service crash-loops. Testing the watchdog: `sudo kill -STOP $(systemctl show -p MainPID --value uav-telemetry)` freezes the process; after 10 s the journal shows `Watchdog timeout`, and systemd restarts the service.

### Step 4. Power and temperature under load
Load the CPU (`stress-ng --cpu 4 --timeout 300s` or your own vision algorithm) and record `vcgencmd measure_temp` and `vcgencmd get_throttled` every 10 s. Write down after how many seconds throttling started (if it did) and whether there was undervoltage. Repeat with a heatsink or a fan, and with a different BEC.

### Step 5. Rehearse the failure
Pull the Pi's power on the bench (the FC on the table with the props off): the FC keeps running, the GCS loses the stream, and after the Pi powers back up the service starts by itself. Repeat 10 times in a row: does the system boot every time? With Overlay File System, repeat once more and make sure the logs are written where they survive a reboot. This is the responsibility boundary from the introductory module.

Self-check: the lab is done when MAVLink goes through the router to several clients at once (the GCS on 14550 and a local script on 14551 or 5760); after `kill -STOP`, `Watchdog timeout` appears in the journal within 10 s and the service comes back by itself; the power budget is computed following the table from the theory section (a BEC rated at one and a half to two times the load at the very least, no less than ~4.9 V at the Pi connector under load); under load, the temperature and `get_throttled` are recorded every 10 s (`0x0` means all is well; `0x50000` means there was undervoltage and throttling, so change the BEC, the wire, or the cooling and rerun); and 10 power cuts are survived without manual intervention, with the service starting by itself every time.

## diagnostics
- **Symptom:** MAVProxy sees no heartbeat
  - Possible cause: the Linux console holds the port, the wrong baud rate, TX/RX swapped.
  - What to do: `raspi-config`, compare with `SERIAL2_BAUD`, check the wiring.
- **Symptom:** garbage in the data at 921600
  - Possible cause: long wires, interference, a bad GND.
  - What to do: shorten, shield, or drop to 57600.
- **Symptom:** a second script cannot open the port
  - Possible cause: `/dev/serial0` is held by the first one.
  - What to do: a MAVLink router, with clients over UDP/TCP.
- **Symptom:** the Pi reboots under throttle
  - Possible cause: a weak power supply.
  - What to do: a BEC with headroom, a capacitor, a separate line from the power bus.
- **Symptom:** garbage or no data on `/dev/serial0`
  - Possible cause: the console on the UART, the mini UART with its drifting baud rate, Bluetooth on the same port.
  - What to do: `raspi-config` (console off, UART on), `disable-bt`, 921600 only on the full UART.
- **Symptom:** the service restarts every few seconds with no errors in the log
  - Possible cause: `WatchdogSec` is set, but the script does not send `WATCHDOG=1` (or the unit is not `Type=notify`).
  - What to do: `sd_notify` in the main loop, or remove `WatchdogSec`.
- **Symptom:** the algorithm is slower on board than on the bench
  - Possible cause: throttling from temperature or undervoltage.
  - What to do: `vcgencmd get_throttled`, a heatsink and airflow, a BEC with headroom.
- **Symptom:** after a hard power cut the Pi does not boot
  - Possible cause: the SD card file system is corrupted.
  - What to do: Overlay File System or logs on a separate drive, `Storage=volatile` for the journal.
- **Symptom:** the script works over SSH and "dies" after you disconnect
  - Possible cause: it is not a service.
  - What to do: a systemd unit with Restart=always.

## references
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- Raspberry Pi — Configuration (UART, vcgencmd, power supply) | https://www.raspberrypi.com/documentation/computers/config_txt.html | primary | A
- systemd.service — Type=notify, WatchdogSec | https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html | primary | A
- mavlink-router — source code (GitHub) | https://github.com/mavlink-router/mavlink-router | primary | A
- mavp2p — source code (GitHub) | https://github.com/bluenviron/mavp2p | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A

## checklist
- The Linux console is off the UART, and `/dev/serial0` is available
- `SERIAL2_PROTOCOL`/`SERIAL2_BAUD` match the Pi's setting
- The Pi is powered from a dedicated BEC
- The router hands MAVLink out to several clients
- The script runs as a `systemd` service with automatic restart and a watchdog
- The power budget is computed, and throttling is checked under load
- The file system survives power loss
- A Pi failure on the bench does not affect the FC
