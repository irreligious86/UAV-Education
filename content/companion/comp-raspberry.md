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
Raspberry Pi на борту — классический первый companion: Linux, Python, камера, Wi-Fi. Модуль проводит от провода до рабочего сервиса: подключение к телеметрийному порту ArduPilot, настройка UART на Pi, проверка MAVProxy, маршрутизация MAVLink сразу нескольким потребителям, бюджет питания и контроль троттлинга, защита SD-карты от отключения питания и свой скрипт как системный сервис со сторожевым таймером.

## theory
### Подключение
Телеметрийный порт FC (например TELEM2 = `SERIAL2`) ↔ UART Pi: TX → RX, RX → TX, общий GND. Уровни 3.3 В с обеих сторон. На FC:

- `SERIAL2_PROTOCOL = 2` — MAVLink 2;
- `SERIAL2_BAUD = 921` — 921600 бод; для коротких проводов и большого потока телеметрии это норма, для длинных — 57 (57600).

Питание Pi — от отдельного BEC 5 В с запасом по току (Pi 4/5 под нагрузкой — больше ампера), не с порта телеметрии FC.

### UART на Raspberry Pi
По умолчанию UART занят консолью Linux. В `raspi-config` → Interfacing → Serial: консоль по serial — **нет**, аппаратный порт — **да**. После перезагрузки порт доступен как `/dev/serial0` — так на Pi 3/4. **На Pi 5** `/dev/serial0` указывает на отладочный разъём (`/dev/ttyAMA10`), а UART на GPIO 14/15 включается строкой `dtparam=uart0=on` в `/boot/firmware/config.txt` и называется `/dev/ttyAMA0` — в примерах ниже подставьте его. На Pi 3/4 основной UART по умолчанию отдан Bluetooth, а на GPIO остаётся mini-UART, скорость которого «плавает» вместе с частотой ядра: для стабильных 921600 — `enable_uart=1` и `dtoverlay=disable-bt` в `config.txt`.

### Маршрутизация
Один UART, а потребителей несколько: GCS по Wi-Fi, твой скрипт, запись tlog. Решение — маршрутизатор MAVLink: `mavlink-router` или `mavp2p` читает порт и раздаёт по UDP/TCP всем подключённым. Скрипты тогда подключаются к локальному UDP-порту, а не к `/dev/serial0` напрямую, и не мешают друг другу.

{{diagram:mavlink-routing|mavlink-router раздаёт один UART-поток FC нескольким потребителям: GCS, вашим скриптам и логгеру.}}

### Сервис вместо «запустил руками»
Скрипт, запущенный из терминала по SSH, умирает вместе с сессией. На борту всё должно стартовать само: `systemd`-юнит с `Restart=always`. Логи — в `journalctl`.

### Время и логи
У Pi без сети нет точного времени после загрузки. Для сопоставления логов companion с DataFlash FC используй `SYSTEM_TIME` из MAVLink (время GPS) или пиши в лог метки `TimeUS`-подобного монотонного счётчика и момент синхронизации.

### Питание: бюджет, а не «какой-нибудь BEC»
Raspberry Pi 5 рассчитан на 5.1 В / 5 А (27 Вт): в простое он берёт около 3 Вт, под полной нагрузкой CPU — 7–8 Вт, сверху камера, USB-модем или Wi-Fi-адаптер. Пример бюджета:

| Потребитель | Мощность | Ток при 5 В |
|---|---|---|
| Pi 5 под нагрузкой | 8 Вт | 1.6 А |
| Камера CSI | 1.5 Вт | 0.3 А |
| USB Wi-Fi / LTE-модем | 2.5 Вт | 0.5 А |
| **Итого** | **12 Вт** | **2.4 А** |

BEC берут с запасом минимум в полтора-два раза (5 А), провод — короткий и толстый: 30 см пары 22 AWG (≈ 53 мОм/м на жилу, туда и обратно ≈ 32 мОм) на 2.4 А теряют ≈ 0.08 В. Пиковые броски (запуск камеры, передача модема) просаживают напряжение сильнее среднего — поэтому у разъёма Pi должно быть не меньше ~4.9 В под нагрузкой.

### Перегрев и просадка видны в цифрах
`vcgencmd get_throttled` возвращает битовую маску: бит 0 — просадка питания сейчас, 1 — частота ограничена, 2 — троттлинг, 3 — мягкий температурный предел; биты 16–19 — то же «было с момента загрузки». `0x0` — всё хорошо, `0x50000` — была просадка питания и троттлинг; `0x50005` — это происходит прямо сейчас. Температура — `vcgencmd measure_temp`; без радиатора и обдува Pi 5 под нагрузкой уходит в троттлинг за минуты, в корпусе дрона без потока воздуха — тем более. Алгоритм зрения, который «вдруг стал медленнее в полёте», — почти всегда здесь.

### Отключение питания без сломанной SD-карты
На дроне питание пропадает без `shutdown` — после краша, при смене батареи. Запись в момент отключения портит файловую систему SD-карты. Два рабочих подхода:
- **Overlay File System** (`raspi-config` → Performance Options → Overlay File System): корень только для чтения, изменения живут в RAM и исчезают после перезагрузки. Система неубиваема, но логи и записи надо писать на отдельный раздел или USB-накопитель.
- **Запись по-взрослому**: логи на отдельный раздел или USB SSD, `f.flush()` + `os.fsync()` для важного, журнал systemd в RAM (`Storage=volatile` в `/etc/systemd/journald.conf`), чтобы он не трепал карту.

### Сервис со сторожевым таймером
Скрипт, запущенный из терминала по SSH, умирает вместе с сессией. На борту всё стартует само: `systemd`-юнит с `Restart=always`. Если скрипт может не упасть, а зависнуть (сокет, камера, бесконечный цикл), нужен ещё и сторожевой таймер: `Type=notify` и `WatchdogSec=` — systemd перезапускает сервис, если тот перестал сообщать «я жив». Без сообщений от скрипта `WatchdogSec` просто убивает его каждые N секунд — эту ловушку проходят почти все. Рабочий вариант — в практике, шаг 3.

### Время и логи
Pi без RTC и без сети стартует с 1970 года — абсолютные метки до синхронизации бессмысленны. Практично: скрипт при старте пишет пару (`SYSTEM_TIME.time_unix_usec` из MAVLink — время GPS от полётника, и свой `time.monotonic()`) и дальше использует монотонные метки; при разборе логи companion сопоставляются с DataFlash полётника по этой паре. На Pi 5 есть разъём батарейки RTC — с ней время переживает перезагрузку без сети.

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

GCS на ноутбуке получает поток на 14550, локальные скрипты подключаются к `udpout:127.0.0.1:14551` или `tcp:127.0.0.1:5760`.

### Шаг 3. Свой сервис со сторожевым таймером
`/opt/uav/telemetry_logger.py` — пишет позицию и батарею в CSV и раз в цикл сообщает systemd, что жив:

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
Проверка сторожевого таймера: `sudo kill -STOP $(systemctl show -p MainPID --value uav-telemetry)` замораживает процесс — через 10 с в журнале будет `Watchdog timeout`, и systemd перезапустит сервис.

### Шаг 4. Питание и температура под нагрузкой
Нагрузить CPU (`stress-ng --cpu 4 --timeout 300s` или свой алгоритм зрения) и раз в 10 с записывать `vcgencmd measure_temp` и `vcgencmd get_throttled`. Записать: через сколько секунд начался троттлинг (если начался), была ли просадка питания. Повторить с радиатором или обдувом и с другим BEC.

### Шаг 5. Отработать отказ
Выдерни питание Pi на стенде (FC на столе без пропов): FC продолжает работать, GCS теряет поток, после включения Pi сервис поднимается сам. Повторить 10 раз подряд: система загружается каждый раз? С Overlay File System — повторить ещё раз и убедиться, что логи пишутся туда, где переживают перезагрузку. Это и есть граница ответственности из вводного модуля.

Лабораторная засчитывается, когда MAVLink идёт через маршрутизатор нескольким клиентам, сервис со сторожевым таймером перезапускается после заморозки, бюджет питания посчитан и температура с флагами троттлинга записаны под нагрузкой, 10 отключений питания пережиты без ручного вмешательства.

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
- **Симптом:** сервис перезапускается каждые несколько секунд без ошибок в логе
  - Возможная причина: `WatchdogSec` задан, а скрипт не шлёт `WATCHDOG=1` (или юнит не `Type=notify`).
  - Что сделать: `sd_notify` в главном цикле или убрать `WatchdogSec`.
- **Симптом:** алгоритм на борту медленнее, чем на столе
  - Возможная причина: троттлинг по температуре или просадке питания.
  - Что сделать: `vcgencmd get_throttled`, радиатор и обдув, BEC с запасом.
- **Симптом:** после жёсткого отключения Pi не загружается
  - Возможная причина: повреждена файловая система SD-карты.
  - Что сделать: Overlay File System или логи на отдельный носитель, `Storage=volatile` для журнала.
- **Симптом:** скрипт работает по SSH и «умирает» после отключения
  - Возможная причина: не сервис.
  - Что сделать: systemd-юнит с Restart=always.

## references
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- Raspberry Pi — Configuration (UART, vcgencmd, power supply) | https://www.raspberrypi.com/documentation/computers/config_txt.html | primary | A
- systemd.service — Type=notify, WatchdogSec | https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html | primary | A
- mavlink-router — source code (GitHub) | https://github.com/mavlink-router/mavlink-router | primary | A
- mavp2p — source code (GitHub) | https://github.com/bluenviron/mavp2p | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A

## checklist
- Консоль Linux снята с UART, порт `/dev/serial0` доступен
- `SERIAL2_PROTOCOL`/`SERIAL2_BAUD` совпадают с настройкой Pi
- Pi питается от отдельного BEC
- Маршрутизатор раздаёт MAVLink нескольким клиентам
- Скрипт запущен как `systemd`-сервис с автоперезапуском и сторожевым таймером
- Бюджет питания посчитан, троттлинг проверен под нагрузкой
- Файловая система переживает отключение питания
- Отказ Pi в стенде не влияет на FC
