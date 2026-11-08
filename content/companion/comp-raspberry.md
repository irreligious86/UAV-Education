---
id: comp-raspberry
title: "Raspberry Pi + ArduPilot"
level: L3
readingTime: 30 мин
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
---

## summary
Raspberry Pi на борту — классический первый companion: Linux, Python, камера, Wi-Fi. Модуль проводит от провода до рабочего сервиса: подключение к телеметрийному порту ArduPilot, настройка UART на Pi, проверка MAVProxy, маршрутизация MAVLink сразу нескольким потребителям и запуск своего скрипта как системного сервиса, который переживает перезагрузки.

## theory
### Подключение
Телеметрийный порт FC (например TELEM2 = `SERIAL2`) ↔ UART Pi: TX → RX, RX → TX, общий GND. Уровни 3.3 В с обеих сторон. На FC:

- `SERIAL2_PROTOCOL = 2` — MAVLink 2;
- `SERIAL2_BAUD = 921` — 921600 бод; для коротких проводов и большого потока телеметрии это норма, для длинных — 57 (57600).

Питание Pi — от отдельного BEC 5 В с запасом по току (Pi 4/5 под нагрузкой — больше ампера), не с порта телеметрии FC.

### UART на Raspberry Pi
По умолчанию UART занят консолью Linux. В `raspi-config` → Interfacing → Serial: консоль по serial — **нет**, аппаратный порт — **да**. После перезагрузки порт доступен как `/dev/serial0`.

### Маршрутизация
Один UART, а потребителей несколько: GCS по Wi-Fi, твой скрипт, запись tlog. Решение — маршрутизатор MAVLink: `mavlink-router` или `mavp2p` читает порт и раздаёт по UDP/TCP всем подключённым. Скрипты тогда подключаются к локальному UDP-порту, а не к `/dev/serial0` напрямую, и не мешают друг другу.

{{diagram:mavlink-routing|mavlink-router раздаёт один UART-поток FC нескольким потребителям: GCS, вашим скриптам и логгеру.}}

### Сервис вместо «запустил руками»
Скрипт, запущенный из терминала по SSH, умирает вместе с сессией. На борту всё должно стартовать само: `systemd`-юнит с `Restart=always`. Логи — в `journalctl`.

### Время и логи
У Pi без сети нет точного времени после загрузки. Для сопоставления логов companion с DataFlash FC используй `SYSTEM_TIME` из MAVLink (время GPS) или пиши в лог метки `TimeUS`-подобного монотонного счётчика и момент синхронизации.

### Конфигурация mavlink-router (пример)
```ini
# /etc/mavlink-router/main.conf
[General]
TcpServerPort = 5760
ReportStats = false
[UartEndpoint fc]
Device = /dev/serial0
Baud = 921600
[UdpEndpoint gcs]
Mode = Normal
Address = 192.168.1.20      # laptop with QGC
Port = 14550
[UdpEndpoint scripts]
Mode = Server
Address = 127.0.0.1
Port = 14551                # local scripts connect here (udpin)
[UdpEndpoint logger]
Mode = Normal
Address = 127.0.0.1
Port = 14552
```
`systemctl enable --now mavlink-router`; скрипты — `mavutil.mavlink_connection("udpin:127.0.0.1:14551")`. Pi 5 использует `/dev/ttyAMA0` на GPIO 14/15 после `dtparam=uart0=on`; на Pi 4 — `enable_uart=1` и отключённый Bluetooth на том же UART (`dtoverlay=disable-bt`) для стабильной скорости 921600 (mini-UART на Pi 3/4 без этого «плавает» по скорости).

### Сервис для своего скрипта
```ini
# /etc/systemd/system/uav-mission.service
[Unit]
Description=UAV mission script
After=mavlink-router.service network.target
[Service]
ExecStart=/home/pi/uav/.venv/bin/python /home/pi/uav/mission.py
Restart=always
RestartSec=2
WatchdogSec=30             # script must call sd_notify("WATCHDOG=1") or it is restarted
User=pi
[Install]
WantedBy=multi-user.target
```
Логи `journalctl -u uav-mission -f`; перезапуск при падении — норма, но контур управления обязан это переживать (GUIDED-таймаут, модуль «Companion»).

### Синхронизация времени и логов
`chrony` с GPS через MAVLink невозможен напрямую; практично: скрипт при старте пишет пару (`SYSTEM_TIME.time_unix_usec`, свой `time.monotonic()`) и далее использует монотонные метки; при разборе сопоставление с `TimeUS` в DataFlash идёт через `GPS.GMS`/`SYSTEM_TIME`. Pi без RTC стартует с 1970 года — любые «абсолютные» метки до синхронизации бессмысленны.

## practice
### Шаг 1. Порт и проверка
```
sudo raspi-config        # Interfacing Options -> Serial: console NO, hardware YES
sudo reboot
pip install --user pymavlink MAVProxy
mavproxy.py --master=/dev/serial0 --baudrate 921600
```

Увидел heartbeat и параметры — связь есть. Команду `arm throttle` на столе давать только без пропов.

### Шаг 2. Маршрутизатор
Пример конфигурации `mavlink-router` (`/etc/mavlink-router/main.conf`):

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

GCS на ноутбуке получает поток на 14550, локальные скрипты подключаются к `udpin:127.0.0.1:14551` или `tcp:127.0.0.1:5760`.

### Шаг 3. Свой сервис
`/opt/uav/telemetry_logger.py`:

```python
import csv, time
from pymavlink import mavutil

m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
m.wait_heartbeat()
with open("/var/log/uav/telemetry.csv", "a", newline="") as f:
    w = csv.writer(f)
    while True:
        msg = m.recv_match(type=["GLOBAL_POSITION_INT", "BATTERY_STATUS"], blocking=True)
        w.writerow([time.monotonic(), msg.get_type(), msg.to_dict()])
        f.flush()
```

`/etc/systemd/system/uav-telemetry.service`:

```
[Unit]
Description=UAV telemetry logger
After=mavlink-router.service
Requires=mavlink-router.service

[Service]
ExecStart=/usr/bin/python3 /opt/uav/telemetry_logger.py
Restart=always
RestartSec=2
User=pi

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl enable --now uav-telemetry
journalctl -u uav-telemetry -f
```

### Шаг 4. Отработать отказ
Выдерни питание Pi в SITL-подобном стенде (FC на столе без пропов): FC продолжает работать, GCS теряет поток, после включения Pi сервис поднимается сам. Это и есть граница ответственности из вводного модуля.

## diagnostics
- **Симптом:** MAVProxy не видит heartbeat
  - Возможная причина: консоль Linux держит порт, не та скорость, перепутаны TX/RX.
  - Что сделать: `raspi-config`, сравнить `SERIAL2_BAUD`, проверить провода.
- **Симптом:** мусор в данных на 921600
  - Возможная причина: длинные провода, помехи, плохой GND.
  - Что сделать: укоротить, экранировать или снизить до 57600.
- **Симптом:** второй скрипт не может открыть порт
  - Возможная причина: `/dev/serial0` занят первым.
  - Что сделать: маршрутизатор MAVLink, клиенты по UDP/TCP.
- **Симптом:** Pi перезагружается на газу
  - Возможная причина: слабое питание.
  - Что сделать: BEC с запасом, конденсатор, отдельная линия от силовой шины.
- **Симптом:** мусор или нет данных на `/dev/serial0`
  - Возможная причина: консоль на UART, mini-UART с плавающей скоростью, Bluetooth на том же порту.
  - Что сделать: `raspi-config` (консоль выкл, UART вкл), `disable-bt`, 921600 только на полном UART.
- **Симптом:** скрипт работает по SSH и «умирает» после отключения
  - Возможная причина: не сервис.
  - Что сделать: systemd-юнит с Restart=always.

## references
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- mavlink-router — source code (GitHub) | https://github.com/mavlink-router/mavlink-router | primary | A
- mavp2p — source code (GitHub) | https://github.com/bluenviron/mavp2p | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A

## checklist
- Консоль Linux снята с UART, порт `/dev/serial0` доступен
- `SERIAL2_PROTOCOL`/`SERIAL2_BAUD` совпадают с настройкой Pi
- Pi питается от отдельного BEC
- Маршрутизатор раздаёт MAVLink нескольким клиентам
- Скрипт запущен как `systemd`-сервис с автоперезапуском
- Отказ Pi в стенде не влияет на FC
