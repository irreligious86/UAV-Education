---
id: comp-raspberry
title: "Raspberry Pi + ArduPilot"
level: L3
readingTime: 30 хв
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
Raspberry Pi на борту — класичний перший companion: Linux, Python, камера, Wi-Fi. Модуль веде від проводу до робочого сервісу: підключення до телеметрійного порту ArduPilot, налаштування UART на Pi, перевірка MAVProxy, маршрутизація MAVLink одразу кільком споживачам, бюджет живлення і контроль тротлінгу, захист SD-карти від вимкнення живлення та власний скрипт як системний сервіс зі сторожовим таймером.

## theory
### Підключення
Телеметрійний порт FC (наприклад TELEM2 = `SERIAL2`) ↔ UART Pi: TX → RX, RX → TX, спільний GND. Рівні 3.3 В з обох боків. На FC:

- `SERIAL2_PROTOCOL = 2` — MAVLink 2;
- `SERIAL2_BAUD = 921` — 921600 бод; для коротких проводів і великого потоку телеметрії це норма, для довгих — 57 (57600).

Живлення Pi — від окремого BEC 5 В із запасом за струмом (Pi 4/5 під навантаженням — понад ампер), не з порту телеметрії FC.

### UART на Raspberry Pi
За замовчуванням UART зайнятий консоллю Linux. У `raspi-config` → Interfacing → Serial: консоль по serial — **ні**, апаратний порт — **так**. Після перезавантаження порт доступний як `/dev/serial0` — так на Pi 3/4. **На Pi 5** `/dev/serial0` вказує на налагоджувальний роз'єм (`/dev/ttyAMA10`), а UART на GPIO 14/15 вмикається рядком `dtparam=uart0=on` у `/boot/firmware/config.txt` і називається `/dev/ttyAMA0` — у прикладах нижче підстав його. На Pi 3/4 основний UART за замовчуванням віддано Bluetooth, а на GPIO лишається mini-UART, швидкість якого «пливе» разом із частотою ядра: для стабільних 921600 — `enable_uart=1` і `dtoverlay=disable-bt` у `config.txt`.

### Маршрутизація
Один UART, а споживачів кілька: GCS через Wi-Fi, твій скрипт, запис tlog. Рішення — маршрутизатор MAVLink: `mavlink-router` або `mavp2p` читає порт і роздає по UDP/TCP усім під'єднаним. Скрипти тоді під'єднуються до локального UDP-порту, а не до `/dev/serial0` напряму, і не заважають одне одному.

{{diagram:mavlink-routing|mavlink-router роздає один UART-потік FC кільком споживачам: GCS, твоїм скриптам і логеру.}}

### Сервіс замість «запустив руками»
Скрипт, запущений із термінала по SSH, помирає разом із сесією. На борту все має стартувати саме: `systemd`-юніт з `Restart=always`. Логи — у `journalctl`.

### Час і логи
У Pi без мережі немає точного часу після завантаження. Для зіставлення логів companion з DataFlash FC використовуй `SYSTEM_TIME` з MAVLink (час GPS) або пиши в лог мітки монотонного лічильника на кшталт `TimeUS` і момент синхронізації.

### Живлення: бюджет, а не «якийсь BEC»
Raspberry Pi 5 розрахований на 5.1 В / 5 А (27 Вт): у простої він бере близько 3 Вт, під повним навантаженням CPU — 7–8 Вт, зверху камера, USB-модем або Wi-Fi-адаптер. Приклад бюджету:

| Споживач | Потужність | Струм при 5 В |
|---|---|---|
| Pi 5 під навантаженням | 8 Вт | 1.6 А |
| Камера CSI | 1.5 Вт | 0.3 А |
| USB Wi-Fi / LTE-модем | 2.5 Вт | 0.5 А |
| **Разом** | **12 Вт** | **2.4 А** |

BEC беруть із запасом щонайменше в півтора-два рази (5 А), провід — короткий і товстий: 30 см пари 22 AWG (≈ 53 мОм/м на жилу, туди й назад ≈ 32 мОм) на 2.4 А втрачають ≈ 0.08 В. Пікові кидки (запуск камери, передавання модема) просаджують напругу сильніше за середнє — тому на роз'ємі Pi має бути не менше ~4.9 В під навантаженням.

### Перегрів і просідання видно в цифрах
`vcgencmd get_throttled` повертає бітову маску: біт 0 — просідання живлення зараз, 1 — частоту обмежено, 2 — тротлінг, 3 — м'яка температурна межа; біти 16–19 — те саме «було від моменту завантаження». `0x0` — усе добре, `0x50000` — було просідання живлення і тротлінг; `0x50005` — це відбувається просто зараз. Температура — `vcgencmd measure_temp`; без радіатора й обдуву Pi 5 під навантаженням іде в тротлінг за хвилини, у корпусі дрона без потоку повітря — тим паче. Алгоритм зору, який «раптом став повільнішим у польоті», — майже завжди тут.

### Вимкнення живлення без зламаної SD-карти
На дроні живлення зникає без `shutdown` — після крашу, при заміні батареї. Запис у момент вимкнення псує файлову систему SD-карти. Два робочі підходи:
- **Overlay File System** (`raspi-config` → Performance Options → Overlay File System): корінь лише для читання, зміни живуть у RAM і зникають після перезавантаження. Система невбивна, але логи й записи треба писати на окремий розділ або USB-накопичувач.
- **Запис по-дорослому**: логи на окремий розділ або USB SSD, `f.flush()` + `os.fsync()` для важливого, журнал systemd у RAM (`Storage=volatile` у `/etc/systemd/journald.conf`), щоб він не тріпав карту.

### Сервіс зі сторожовим таймером
Скрипт, запущений із термінала по SSH, помирає разом із сесією. На борту все стартує саме: `systemd`-юніт з `Restart=always`. Якщо скрипт може не впасти, а зависнути (сокет, камера, нескінченний цикл), потрібен ще й сторожовий таймер: `Type=notify` і `WatchdogSec=` — systemd перезапускає сервіс, якщо той перестав повідомляти «я живий». Без повідомлень від скрипта `WatchdogSec` просто вбиває його кожні N секунд — у цю пастку потрапляють майже всі. Робочий варіант — у практиці, крок 3.

### Час і логи
Pi без RTC і без мережі стартує з 1970 року — абсолютні мітки до синхронізації безглузді. Практично: скрипт під час старту пише пару (`SYSTEM_TIME.time_unix_usec` з MAVLink — час GPS від польотного контролера, і свій `time.monotonic()`) і далі використовує монотонні мітки; під час розбору логи companion зіставляються з DataFlash польотного контролера за цією парою. На Pi 5 є роз'єм батарейки RTC — з нею час переживає перезавантаження без мережі.

## practice
### Крок 1. Порт і перевірка
```
sudo raspi-config        # Interfacing Options -> Serial: console NO, hardware YES
sudo reboot
pip install --user pymavlink MAVProxy
mavproxy.py --master=/dev/serial0 --baudrate 921600
```

Побачив heartbeat і параметри — зв'язок є. Команду `arm throttle` на столі давати лише без пропелерів.

### Крок 2. Маршрутизатор
Приклад конфігурації `mavlink-router` (`/etc/mavlink-router/main.conf`):

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

GCS на ноутбуці отримує потік на 14550, локальні скрипти під'єднуються до `udpout:127.0.0.1:14551` або `tcp:127.0.0.1:5760`.

### Крок 3. Власний сервіс зі сторожовим таймером
`/opt/uav/telemetry_logger.py` — пише позицію і батарею в CSV і раз за цикл повідомляє systemd, що живий:

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
Перевірка сторожового таймера: `sudo kill -STOP $(systemctl show -p MainPID --value uav-telemetry)` заморожує процес — через 10 с у журналі буде `Watchdog timeout`, і systemd перезапустить сервіс.

### Крок 4. Живлення і температура під навантаженням
Навантажити CPU (`stress-ng --cpu 4 --timeout 300s` або свій алгоритм зору) і раз на 10 с записувати `vcgencmd measure_temp` і `vcgencmd get_throttled`. Записати: через скільки секунд почався тротлінг (якщо почався), чи було просідання живлення. Повторити з радіатором або обдувом і з іншим BEC.

### Крок 5. Відпрацювати відмову
Висмикни живлення Pi на стенді (FC на столі без пропелерів): FC продовжує працювати, GCS втрачає потік, після ввімкнення Pi сервіс піднімається сам. Повторити 10 разів поспіль: система завантажується щоразу? З Overlay File System — повторити ще раз і переконатися, що логи пишуться туди, де переживають перезавантаження. Це і є межа відповідальності зі вступного модуля.

Лабораторну зараховано, коли MAVLink іде через маршрутизатор кільком клієнтам, сервіс зі сторожовим таймером перезапускається після заморожування, бюджет живлення пораховано, а температуру з прапорцями тротлінгу записано під навантаженням, 10 вимкнень живлення пережито без ручного втручання.

## diagnostics
- **Симптом:** MAVProxy не бачить heartbeat
  - Можлива причина: консоль Linux тримає порт, не та швидкість, переплутано TX/RX.
  - Що зробити: `raspi-config`, порівняти `SERIAL2_BAUD`, перевірити проводи.
- **Симптом:** сміття в даних на 921600
  - Можлива причина: довгі проводи, завади, поганий GND.
  - Що зробити: скоротити, екранувати або знизити до 57600.
- **Симптом:** другий скрипт не може відкрити порт
  - Можлива причина: `/dev/serial0` зайнятий першим.
  - Що зробити: маршрутизатор MAVLink, клієнти по UDP/TCP.
- **Симптом:** Pi перезавантажується на газу
  - Можлива причина: слабке живлення.
  - Що зробити: BEC із запасом, конденсатор, окрема лінія від силової шини.
- **Симптом:** сміття або немає даних на `/dev/serial0`
  - Можлива причина: консоль на UART, mini-UART із плаваючою швидкістю, Bluetooth на тому самому порту.
  - Що зробити: `raspi-config` (консоль вимк., UART увімк.), `disable-bt`, 921600 лише на повному UART.
- **Симптом:** сервіс перезапускається кожні кілька секунд без помилок у логу
  - Можлива причина: `WatchdogSec` задано, а скрипт не надсилає `WATCHDOG=1` (або юніт не `Type=notify`).
  - Що зробити: `sd_notify` у головному циклі або прибрати `WatchdogSec`.
- **Симптом:** алгоритм на борту повільніший, ніж на столі
  - Можлива причина: тротлінг через температуру або просідання живлення.
  - Що зробити: `vcgencmd get_throttled`, радіатор і обдув, BEC із запасом.
- **Симптом:** після жорсткого вимкнення Pi не завантажується
  - Можлива причина: пошкоджено файлову систему SD-карти.
  - Що зробити: Overlay File System або логи на окремий носій, `Storage=volatile` для журналу.
- **Симптом:** скрипт працює по SSH і «помирає» після від'єднання
  - Можлива причина: не сервіс.
  - Що зробити: systemd-юніт з Restart=always.

## references
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- Raspberry Pi — Configuration (UART, vcgencmd, power supply) | https://www.raspberrypi.com/documentation/computers/config_txt.html | primary | A
- systemd.service — Type=notify, WatchdogSec | https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html | primary | A
- mavlink-router — source code (GitHub) | https://github.com/mavlink-router/mavlink-router | primary | A
- mavp2p — source code (GitHub) | https://github.com/bluenviron/mavp2p | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A

## checklist
- Консоль Linux знято з UART, порт `/dev/serial0` доступний
- `SERIAL2_PROTOCOL`/`SERIAL2_BAUD` збігаються з налаштуванням Pi
- Pi живиться від окремого BEC
- Маршрутизатор роздає MAVLink кільком клієнтам
- Скрипт запущено як `systemd`-сервіс з автоперезапуском і сторожовим таймером
- Бюджет живлення пораховано, тротлінг перевірено під навантаженням
- Файлова система переживає вимкнення живлення
- Відмова Pi на стенді не впливає на FC
