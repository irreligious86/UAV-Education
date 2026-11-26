---
id: px4-companion-jetson
title: "PX4 + Jetson Orin: companion через UART, MAVLink і uXRCE-DDS"
level: L3
readingTime: 35 хв
firmware: PX4 1.15+ · JetPack 6/7
status: published
tags:
  - Jetson
  - companion
  - uXRCE-DDS
  - offboard
related:
  - comp-intro
  - px4-ros2
  - per-cv
  - per-edge-ml
next:
  - per-cv
source: content/px4/px4-companion-jetson.md
source_hash: 53438f964c4d
---

## summary
Jetson Orin Nano/NX — стандартний companion для зору на PX4: CUDA і TensorRT у 7–25 Вт. Модуль складає зв'язку від початку до кінця: ролі й межа відповідальності, живлення й тепло, фізичне підключення до TELEM2, як **знайти** правильний UART на своїй версії JetPack (ім'я пристрою в різних версіях різне), два канали зв'язку — MAVLink і uXRCE-DDS — з параметрами PX4 і перевіркою, автозапуск агента через systemd, бюджет затримки ланцюжка «камера → команда». Перше покоління Jetson Nano знято з підтримки (JetPack 4, Ubuntu 18.04) — для нових проєктів його вже не беруть.

## theory
### Ролі й межа
Pixhawk (PX4) — стабілізація, EKF, failsafe, місії; Jetson — зір, планування, ROS 2, мережа. Межа та сама, шо в модулі «Companion: роль і межі»: без Jetson апарат мусить летіти й вертатися, а втрату companion в offboard обробляє failsafe PX4 (`COM_OF_LOSS_T`, `COM_OBL_RC_ACT`), а не надія.

### Який Jetson і яка система
| Плата | Що дає | Система |
|---|---|---|
| Orin Nano 4/8 ГБ | основний вибір для детекції й трекінгу; режими 7–25 Вт (`nvpmodel`) | JetPack 6 (Ubuntu 22.04 → ROS 2 Humble) або JetPack 7 (Ubuntu 24.04 → ROS 2 Jazzy) |
| Orin NX 8/16 ГБ | удвічі більше обчислень, той самий форм-фактор модуля | те саме |
| Jetson Nano (2019) | знято з підтримки, JetPack 4 | не для нових проєктів |

Версія JetPack визначає Ubuntu, а отже, і дистрибутив ROS 2: ставити ROS 2 для «не своєї» Ubuntu — то пряма дорога до збирання з вихідного коду й вічних проблем із залежностями.

### Живлення й тепло
- Jetson — **окремий** BEC або DC-DC від силової шини із запасом за струмом, не від польотного контролера; спільна земля з Pixhawk.
- Режим потужності: `sudo nvpmodel -q` показує поточний, `nvpmodel -m <N>` перемикає; `jetson_clocks` фіксує частоти (стабільна затримка ціною енергії).
- Тепло: у закритому корпусі без обдуву Orin тротлить уже за кілька хвилин, і затримка детекції росте вдвічі (модуль «ML на борту»). Радіатор із вентилятором або обдув від пропелерів, `tegrastats` у логу польоту — і пантруй температуру.

### Фізичне підключення
- **UART (рекомендовано для польоту)**: TELEM2 Pixhawk — TX, RX, GND; Jetson — піни 8 (TX) і 10 (RX) 40-пінової гребінки, земля на пін 6. TX↔RX навхрест. Логіка 3.3 В з обох боків; **5 В з роз'єму TELEM2 до Jetson не підключати**.
- **Ім'я пристрою залежить від плати й JetPack**: на Orin цей UART буває `/dev/ttyTHS0` або `/dev/ttyTHS1`, на старому Nano — `/dev/ttyTHS1`; налагоджувальна консоль Orin — `/dev/ttyTCU0`. Не вір статті на слово — перевір петлею (практика, крок 2).
- **Ethernet** (Pixhawk 6X, 6X Pro тощо): MAVLink і uXRCE-DDS через UDP, без обмеження швидкості UART — найфайніший варіант, якщо є.
- **USB** — для стенда; у польоті USB-з'єднання ненадійне: вібрація роз'єму й повторна енумерація рвуть зв'язок.

### Два канали зв'язку
1. **MAVLink** (MAVSDK, pymavlink, MAVROS): `MAV_1_CONFIG = TELEM2`, `MAV_1_MODE = Onboard` (набір потоків для companion), `SER_TEL2_BAUD = 921600`. Плюс: стандарт, той самий код працює з ArduPilot; мінус: обмежений набір даних і частот.
2. **uXRCE-DDS**: `UXRCE_DDS_CFG = TELEM2`, та сама швидкість, MAVLink на цьому порту вимкнений (`MAV_1_CONFIG = Disabled` або перенесений на інший порт). На Jetson — `MicroXRCEAgent serial --dev <порт> -b 921600`; топіки `/fmu/out/*`, `/fmu/in/*` з `px4_msgs` **тієї самої версії**, шо й прошивка (з 1.16 повідомлення версіонуються, у частини топіків суфікс `_v1`). Плюс: внутрішні топіки PX4 з малою затримкою; мінус: лиш PX4, версії мусять збігатися.

На одному порту живе шось одне. Треба обидва — MAVLink на TELEM1/USB/Ethernet, DDS на TELEM2.

{{diagram:jetson-link-choice|Ethernet снимает вопрос полосы; на UART DDS со всеми топиками не помещается в 921600 (117 %), поэтому либо 3 Мбод и контроль Payload tx, либо MAVLink, а два протокола — на разных портах.}}

### Розібраний приклад: бюджет затримки
Камера CSI 60 кадр/с (до 16 мс до готового кадру) → TensorRT YOLO-nano FP16 ~12 мс → трекер 2 мс → DDS через UART 921600 ~2 мс → контролер швидкості PX4 (стала часу ~0.5 с). Чиста затримка ~35 мс: контур стеження з Kp ≈ 1 1/с стійкий із запасом (модуль «Стеження»). USB-камера з MJPEG додає 40–80 мс, Wi-Fi-міст замість дроту — 20–50 мс із джитером; дві такі «дрібнички» з'їдають цілий запас. Звідси правило: CSI і дріт, а не USB і радіо.

{{diagram:jetson-latency-budget|На проводе и CSI цепочка укладывается в 32 мс; USB-камера и Wi-Fi-мост вместе дают 92–162 мс — в 3–5 раз больше.}}

{{diagram:px4-jetson-link|PX4 і Jetson: камера на Jetson, зв'язок із польотним контролером через TELEM2 за MAVLink або uXRCE-DDS.}}

## practice
### Крок 0. Бюджет каналу й живлення (розрахунок, без заліза)
Запускається на будь-якому комп'ютері з Python 3. `DDS_ALL_CAPS` і `DDS_TYPICAL` — результат лабораторної `px4-ros2` для PX4 1.17.0. Збережи як `link_lab.py`:
```python
"""Jetson <-> PX4 link budget: UART capacity, MAVLink auto rate, uXRCE-DDS load, agent IP, latency, power."""
import ipaddress
import struct

BAUDS = (921600, 1500000, 3000000)       # 921600 = SER_TEL2_BAUD default; 3000000 = uxrce_dds_client -b max
DDS_ALL_CAPS = 107495                    # B/s, px4-ros2 lab: all 27 /fmu/out topics of PX4 1.17.0 at their caps
DDS_TYPICAL = {"vehicle_odometry": 13700, "vehicle_local_position_v1": 11950,
               "vehicle_status_v1": 515, "timesync_status": 670}     # same lab, B/s at cap
SETPOINT_FRAME = 64 + 23                 # TrajectorySetpoint CDR 64 B + ~23 B XRCE/serial overhead (course estimate)

print("1) UART capacity (8N1 = 10 bit per byte) and MAV_1_RATE = 0 (PX4 uses baud/20):")
for b in BAUDS:
    print(f"   {b:>8} baud: {b // 10:>6} B/s raw, MAVLink auto rate {b // 20:>6} B/s")

print("\n2) uXRCE-DDS load on the same UART:")
typ = sum(DDS_TYPICAL.values())
for b in BAUDS:
    print(f"   {b:>8}: all topics at caps {100 * DDS_ALL_CAPS / (b / 10):5.0f} %, "
          f"odometry+local_position+status+timesync {100 * typ / (b / 10):4.0f} %")

print("\n3) Time to send one TrajectorySetpoint frame (%d B):" % SETPOINT_FRAME)
for b in BAUDS:
    print(f"   {b:>8}: {SETPOINT_FRAME * 10 / b * 1000:.2f} ms")

print("\n4) UXRCE_DDS_AG_IP is the IPv4 address as a signed int32:")
for ip in ("127.0.0.1", "192.168.1.2", "10.41.10.1"):
    u = int(ipaddress.IPv4Address(ip))
    s = struct.unpack("<i", struct.pack("<I", u))[0]
    print(f"   {ip:>12} -> {s}")

print("\n5) Latency budget camera -> setpoint, ms (module worked example):")
chains = {"CSI + wire": [16, 12, 2, 2], "USB MJPEG + wire": [16 + 40, 12, 2, 2], "USB MJPEG + Wi-Fi": [16 + 80, 12, 2, 2 + 50]}
for name, parts in chains.items():
    print(f"   {name:18s} {' + '.join(map(str, parts))} = {sum(parts)} ms")

print("\n6) Battery-side current of the Jetson DC-DC (module + 5 W carrier/camera, efficiency 0.9):")
for mode_w in (15, 25):
    for cells, vmin in ((4, 13.2), (6, 19.8)):
        i = (mode_w + 5) / 0.9 / vmin
        print(f"   {mode_w} W mode, {cells}S at {vmin} V: {i:.2f} A, size the converter for {1.5 * (mode_w + 5):.0f} W")
```
Вивід `python3 link_lab.py` (2026-11-26):
```
1) UART capacity (8N1 = 10 bit per byte) and MAV_1_RATE = 0 (PX4 uses baud/20):
     921600 baud:  92160 B/s raw, MAVLink auto rate  46080 B/s
    1500000 baud: 150000 B/s raw, MAVLink auto rate  75000 B/s
    3000000 baud: 300000 B/s raw, MAVLink auto rate 150000 B/s

2) uXRCE-DDS load on the same UART:
     921600: all topics at caps   117 %, odometry+local_position+status+timesync   29 %
    1500000: all topics at caps    72 %, odometry+local_position+status+timesync   18 %
    3000000: all topics at caps    36 %, odometry+local_position+status+timesync    9 %

3) Time to send one TrajectorySetpoint frame (87 B):
     921600: 0.94 ms
    1500000: 0.58 ms
    3000000: 0.29 ms

4) UXRCE_DDS_AG_IP is the IPv4 address as a signed int32:
      127.0.0.1 -> 2130706433
    192.168.1.2 -> -1062731518
     10.41.10.1 -> 170461697

5) Latency budget camera -> setpoint, ms (module worked example):
   CSI + wire         16 + 12 + 2 + 2 = 32 ms
   USB MJPEG + wire   56 + 12 + 2 + 2 = 72 ms
   USB MJPEG + Wi-Fi  96 + 12 + 2 + 52 = 162 ms

6) Battery-side current of the Jetson DC-DC (module + 5 W carrier/camera, efficiency 0.9):
   15 W mode, 4S at 13.2 V: 1.68 A, size the converter for 30 W
   15 W mode, 6S at 19.8 V: 1.12 A, size the converter for 30 W
   25 W mode, 4S at 13.2 V: 2.53 A, size the converter for 45 W
   25 W mode, 6S at 19.8 V: 1.68 A, size the converter for 45 W
```

### Крок 1. Підготовка Jetson
```bash
sudo usermod -aG dialout $USER        # access to serial ports (log out and in)
systemctl status nvgetty              # on boards where the header UART is a console, stop it:
sudo systemctl disable --now nvgetty
sudo nvpmodel -q                      # current power mode
```

### Крок 2. Знайти «свій» UART петлею
Перемичка між пінами 8 і 10, Pixhawk не підключений. Для кожного кандидата:
```python
import serial, sys
for dev in ("/dev/ttyTHS0", "/dev/ttyTHS1"):
    try:
        with serial.Serial(dev, 921600, timeout=0.2) as s:
            s.reset_input_buffer(); s.write(b"loopback-test\n")
            print(dev, "OK" if s.readline() == b"loopback-test\n" else "no echo")
    except serial.SerialException as e:
        print(dev, "error:", e)
```
Рівно один порт мусить відповісти OK — то і є піни 8/10 у твоїй системі. «Permission denied» — група dialout або консоль на порту; «no echo» на обох — не ті піни або UART вимкнений у device tree (Jetson-IO: `sudo /opt/nvidia/jetson-io/jetson-io.py`).

### Крок 3. MAVLink-канал
Параметри PX4 у QGC: `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard`, `SER_TEL2_BAUD = 921600`, перезавантаження. Перемичку зняти, підключити TX/RX/GND. Перевірка:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("/dev/ttyTHS1", baud=921600)   # your port from step 2
m.wait_heartbeat(); print("sys", m.target_system, "comp", m.target_component)
import time, collections
cnt, t0 = collections.Counter(), time.time()
while time.time() - t0 < 10:
    msg = m.recv_match(type=["ATTITUDE", "LOCAL_POSITION_NED"], blocking=True, timeout=1)
    if msg: cnt[msg.get_type()] += 1
print({k: v / 10 for k, v in cnt.items()}, "Hz")
```
Записати частоти ATTITUDE і LOCAL_POSITION_NED.

### Крок 4. uXRCE-DDS-канал
`MAV_1_CONFIG = Disabled`, `UXRCE_DDS_CFG = TELEM2`, перезавантаження. На Jetson:
```bash
MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600
ros2 topic list | grep fmu                     # versioned names, e.g. ..._v1 since PX4 1.16/1.17
ros2 topic hz /fmu/out/vehicle_attitude
ros2 topic echo --once /fmu/out/timesync_status
```
Порівняти частоту `vehicle_attitude` з ATTITUDE із кроку 3.

### Крок 5. Автозапуск агента
`/etc/systemd/system/xrce-agent.service`:
```ini
[Unit]
Description=Micro XRCE-DDS Agent for PX4
After=network.target

[Service]
ExecStart=/usr/local/bin/MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600
Restart=always
RestartSec=2
User=nvidia

[Install]
WantedBy=multi-user.target
```
`sudo systemctl enable --now xrce-agent`; перевірити, шо після `sudo kill` агента топіки вертаються самі, у межах ~10 с (орієнтир курсу: 2 с `RestartSec` + ~3 с на три пропущені пінги + перестворення сесії); заміряй і запиши свій час. Шлях до бінарника, користувач і порт — свої.

### Крок 6. Тепло під навантаженням
Запустити детектор (модуль «Комп'ютерний зір») на 20 хвилин у корпусі, писати `tegrastats --interval 1000 --logfile tegra.log`. Знайти момент тротлінгу (частота GPU падає, температура біля межі) і затримку детекції до і після.

Лабораторна ся зараховує, коли порт знайдено петлею, обидва канали перевірені із записаними частотами, агент сам ся піднімає після падіння, є 20-хвилинний тепловий лог.

## diagnostics
- **Симптом:** `Permission denied: /dev/ttyTHS*`
  - Можлива причина: користувач не в групі dialout або на порту сидить консоль.
  - Що зробити: `usermod -aG dialout`, перелогінитися, `systemctl disable --now nvgetty`.
- **Симптом:** порт відкривається, а даних нема
  - Можлива причина: не той ttyTHS, TX/RX не перехрещені, нема спільної землі, MAVLink на TELEM2 не ввімкнений.
  - Що зробити: петля з кроку 2, перевірка проводки, `MAV_1_CONFIG`.
- **Симптом:** MAVLink працює, uXRCE-DDS — ні
  - Можлива причина: MAVLink досі на тому самому порту, агент на іншій швидкості, `px4_msgs` іншої версії.
  - Що зробити: `MAV_1_CONFIG = Disabled`, однаковий baud, `px4_msgs` з гілки, шо збігається з прошивкою.
- **Симптом:** топіки є, але `ros2 topic echo` мовчить
  - Можлива причина: розбіжність QoS (PX4 публікує best effort).
  - Що зробити: підписник із `qos_profile_sensor_data`, `ros2 topic echo --qos-reliability best_effort`.
- **Симптом:** затримка детекції росте через 10 хвилин польоту
  - Можлива причина: тротлінг Jetson.
  - Що зробити: обдув, режим `nvpmodel`, `tegrastats` у логу польоту.
- **Симптом:** Jetson ся перезавантажує на газу
  - Можлива причина: просідання спільного BEC.
  - Що зробити: окремий DC-DC із запасом, конденсатор на вході, виміряти напругу осцилографом під навантаженням.

## references
- PX4 — Pixhawk + Companion Computer | https://docs.px4.io/main/en/companion_computer/pixhawk_companion.html | primary | A
- PX4 — uXRCE-DDS (PX4–ROS 2/DDS bridge) | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- eProsima — Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | primary | A
- NVIDIA Developer Forums — UART1 on expansion pins 8/10 (Orin) | https://forums.developer.nvidia.com/t/how-to-access-uart1-on-expansion-pins-8-10/328934 | secondary | B

## checklist
- Розумію межу між Jetson і PX4 і шо робить PX4, коли пропаде companion
- Обираю JetPack і ROS 2 під одну Ubuntu
- Живлю Jetson окремо, пантрую тепло й режим потужності
- Знаходжу свій UART петлею, а не за статтею
- Налаштовую MAVLink і uXRCE-DDS на різних портах і перевіряю частоти
- Піднімаю агент через systemd з автоперезапуском
- Рахую бюджет затримки «камера → команда»
