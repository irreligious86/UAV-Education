---
id: px4-companion-jetson
title: "PX4 + Jetson Orin: companion по UART, MAVLink и uXRCE-DDS"
level: L3
readingTime: 35 мин
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
---

## summary
Jetson Orin Nano/NX — стандартный companion для зрения на PX4: CUDA и TensorRT в 7–25 Вт. Модуль собирает связку целиком: роли и граница ответственности, питание и тепло, физическое подключение к TELEM2, как **найти** правильный UART на своей версии JetPack (имя устройства у разных версий разное), два канала связи — MAVLink и uXRCE-DDS — с параметрами PX4 и проверкой, автозапуск агента через systemd, бюджет задержки цепочки «камера → команда». Первое поколение Jetson Nano снято с поддержки (JetPack 4, Ubuntu 18.04) — для новых проектов его не берут.

## theory
### Роли и граница
Pixhawk (PX4) — стабилизация, EKF, failsafe, миссии; Jetson — зрение, планирование, ROS 2, сеть. Граница та же, что в модуле «Companion: роль и границы»: без Jetson аппарат обязан лететь и возвращаться, а потеря companion в offboard обрабатывается failsafe PX4 (`COM_OF_LOSS_T`, `COM_OBL_RC_ACT`), а не надеждой.

### Какой Jetson и какая система
| Плата | Что даёт | Система |
|---|---|---|
| Orin Nano 4/8 ГБ | основной выбор для детекции и трекинга; режимы 7–25 Вт (`nvpmodel`) | JetPack 6 (Ubuntu 22.04 → ROS 2 Humble) или JetPack 7 (Ubuntu 24.04 → ROS 2 Jazzy) |
| Orin NX 8/16 ГБ | в 2 раза больше вычислений, тот же форм-фактор модуля | то же |
| Jetson Nano (2019) | снят с поддержки, JetPack 4 | не для новых проектов |

Версия JetPack определяет Ubuntu, а значит и дистрибутив ROS 2: ставить ROS 2 «не своей» Ubuntu — путь к сборке из исходников и вечным проблемам с зависимостями.

### Питание и тепло
- Jetson — **отдельный** BEC или DC-DC от силовой шины с запасом по току, не от полётного контроллера; общая земля с Pixhawk.
- Режим мощности: `sudo nvpmodel -q` показывает текущий, `nvpmodel -m <N>` переключает; `jetson_clocks` фиксирует частоты (стабильная задержка ценой энергии).
- Тепло: в закрытом корпусе без обдува Orin троттлит через несколько минут, и задержка детекции растёт вдвое (модуль «ML на борту»). Радиатор с вентилятором или обдув от пропов, `tegrastats` в логе полёта.

### Физическое подключение
- **UART (рекомендуется для полёта)**: TELEM2 Pixhawk — TX, RX, GND; Jetson — пины 8 (TX) и 10 (RX) 40-пиновой гребёнки, земля на пин 6. TX↔RX перекрёстно. Логика 3.3 В с обеих сторон; **5 В с разъёма TELEM2 к Jetson не подключать**.
- **Имя устройства зависит от платы и JetPack**: на Orin этот UART бывает `/dev/ttyTHS0` или `/dev/ttyTHS1`, на старом Nano — `/dev/ttyTHS1`; отладочная консоль Orin — `/dev/ttyTCU0`. Не верь статье — проверь петлёй (практика, шаг 2).
- **Ethernet** (Pixhawk 6X, 6X Pro и др.): MAVLink и uXRCE-DDS по UDP, без ограничения скорости UART — лучший вариант, если есть.
- **USB** — для стенда; в полёте USB-соединение ненадёжно: вибрация разъёма и перезапуск энумерации обрывают связь.

### Два канала связи
1. **MAVLink** (MAVSDK, pymavlink, MAVROS): `MAV_1_CONFIG = TELEM2`, `MAV_1_MODE = Onboard` (набор потоков для companion), `SER_TEL2_BAUD = 921600`. Плюс: стандарт, тот же код работает с ArduPilot; минус: ограниченный набор данных и частот.
2. **uXRCE-DDS**: `UXRCE_DDS_CFG = TELEM2`, та же скорость, MAVLink на этом порту выключен (`MAV_1_CONFIG = Disabled` или перенесён на другой порт). На Jetson — `MicroXRCEAgent serial --dev <порт> -b 921600`; топики `/fmu/out/*`, `/fmu/in/*` из `px4_msgs` **той же версии**, что прошивка (с 1.16 сообщения версионируются, у части топиков суффикс `_v1`). Плюс: внутренние топики PX4 с малой задержкой; минус: только PX4, версии должны совпадать.

На одном порту живёт что-то одно. Нужны оба — MAVLink на TELEM1/USB/Ethernet, DDS на TELEM2.

### Разобранный пример: бюджет задержки
Камера CSI 60 кадр/с (до 16 мс до готового кадра) → TensorRT YOLO-nano FP16 ~12 мс → трекер 2 мс → DDS по UART 921600 ~2 мс → контроллер скорости PX4 (постоянная времени ~0.5 с). Чистая задержка ~35 мс: контур слежения с Kp ≈ 1 1/с устойчив с запасом (модуль «Слежение»). USB-камера с MJPEG добавляет 40–80 мс, Wi-Fi-мост вместо провода — 20–50 мс с джиттером; две такие «мелочи» съедают весь запас. Отсюда правило: CSI и провод, не USB и радио.

{{diagram:px4-jetson-link|PX4 и Jetson: камера на Jetson, связь с полётным контроллером по TELEM2 через MAVLink или uXRCE-DDS.}}

## practice
### Шаг 1. Подготовка Jetson
```bash
sudo usermod -aG dialout $USER        # access to serial ports (log out and in)
systemctl status nvgetty              # on boards where the header UART is a console, stop it:
sudo systemctl disable --now nvgetty
sudo nvpmodel -q                      # current power mode
```

### Шаг 2. Найти «свой» UART петлёй
Перемычка между пинами 8 и 10, Pixhawk не подключён. Для каждого кандидата:
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
Ровно один порт должен ответить OK — это и есть пины 8/10 на вашей системе. «Permission denied» — группа dialout или консоль на порту; «no echo» на обоих — пины не те или UART выключен в device tree (Jetson-IO: `sudo /opt/nvidia/jetson-io/jetson-io.py`).

### Шаг 3. MAVLink-канал
Параметры PX4 в QGC: `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard`, `SER_TEL2_BAUD = 921600`, перезагрузка. Перемычку снять, подключить TX/RX/GND. Проверка:
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
Записать частоты ATTITUDE и LOCAL_POSITION_NED.

### Шаг 4. uXRCE-DDS-канал
`MAV_1_CONFIG = Disabled`, `UXRCE_DDS_CFG = TELEM2`, перезагрузка. На Jetson:
```bash
MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600
ros2 topic list | grep fmu                     # versioned names, e.g. ..._v1 since PX4 1.16/1.17
ros2 topic hz /fmu/out/vehicle_attitude
ros2 topic echo --once /fmu/out/timesync_status
```
Сравнить частоту `vehicle_attitude` с ATTITUDE из шага 3.

### Шаг 5. Автозапуск агента
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
`sudo systemctl enable --now xrce-agent`; проверить, что после `sudo kill` агента топики возвращаются за 2–3 с. Путь к бинарнику, пользователь и порт — свои.

### Шаг 6. Тепло под нагрузкой
Запустить детектор (модуль «Компьютерное зрение») на 20 минут в корпусе, писать `tegrastats --interval 1000 --logfile tegra.log`. Найти момент троттлинга (частота GPU падает, температура у предела) и задержку детекции до и после.

Лабораторная засчитывается, когда найден порт петлёй, оба канала проверены с записанными частотами, агент поднимается сам после падения, есть 20-минутный тепловой лог.

## diagnostics
- **Симптом:** `Permission denied: /dev/ttyTHS*`
  - Возможная причина: пользователь не в dialout или на порту консоль.
  - Что сделать: `usermod -aG dialout`, перелогиниться, `systemctl disable --now nvgetty`.
- **Симптом:** порт открывается, данных нет
  - Возможная причина: не тот ttyTHS, TX/RX не перекрещены, нет общей земли, MAVLink на TELEM2 не включён.
  - Что сделать: петля из шага 2, проверка проводки, `MAV_1_CONFIG`.
- **Симптом:** MAVLink работает, uXRCE-DDS — нет
  - Возможная причина: MAVLink всё ещё на том же порту, агент не той скорости, `px4_msgs` другой версии.
  - Что сделать: `MAV_1_CONFIG = Disabled`, одинаковый baud, `px4_msgs` из ветки, совпадающей с прошивкой.
- **Симптом:** топики есть, но `ros2 topic echo` молчит
  - Возможная причина: несовпадение QoS (PX4 публикует best effort).
  - Что сделать: подписчик с `qos_profile_sensor_data`, `ros2 topic echo --qos-reliability best_effort`.
- **Симптом:** задержка детекции растёт через 10 минут полёта
  - Возможная причина: троттлинг Jetson.
  - Что сделать: обдув, режим `nvpmodel`, `tegrastats` в логе полёта.
- **Симптом:** Jetson перезагружается на газу
  - Возможная причина: просадка общего BEC.
  - Что сделать: отдельный DC-DC с запасом, конденсатор на входе, измерить напряжение осциллографом под нагрузкой.

## references
- PX4 — Pixhawk + Companion Computer | https://docs.px4.io/main/en/companion_computer/pixhawk_companion.html | primary | A
- PX4 — uXRCE-DDS (PX4–ROS 2/DDS bridge) | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- eProsima — Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | primary | A
- NVIDIA Developer Forums — UART1 on expansion pins 8/10 (Orin) | https://forums.developer.nvidia.com/t/how-to-access-uart1-on-expansion-pins-8-10/328934 | secondary | B

## checklist
- Понимаю границу Jetson и PX4 и что делает PX4 при потере companion
- Выбираю JetPack и ROS 2 под одну Ubuntu
- Питаю Jetson отдельно, слежу за теплом и режимом мощности
- Нахожу свой UART петлёй, не по статье
- Настраиваю MAVLink и uXRCE-DDS на разных портах и проверяю частоты
- Поднимаю агент через systemd с автоперезапуском
- Считаю бюджет задержки «камера → команда»
