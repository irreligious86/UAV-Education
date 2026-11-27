---
id: px4-companion-jetson
title: "PX4 + Jetson Orin: companion по UART, MAVLink и uXRCE-DDS"
level: L3
readingTime: 45 мин
firmware: PX4 1.18 (сверено с исходниками v1.17.0; отличия 1.18.0 по параметрам отмечены, расчёт канала — по топикам 1.17.0) · JetPack 7.2.2 (Jetson Linux 39.2.2, Ubuntu 24.04) / JetPack 6.2.x (Ubuntu 22.04)
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
Jetson Orin Nano/NX — стандартный companion для зрения на PX4: CUDA и TensorRT в 7–40 Вт. Модуль собирает связку целиком: роли и граница ответственности, выбор JetPack и ROS 2 под одну Ubuntu (на ноябрь 2026 — JetPack 7.2.2 на Ubuntu 24.04 поддерживает всё семейство Orin), режимы мощности и Super Mode, питание и тепло, физическое подключение к TELEM2, как **найти** правильный UART на своей версии JetPack (имя устройства у разных версий разное), два канала связи — MAVLink и uXRCE-DDS — с параметрами PX4, пропускной способностью и проверкой, автозапуск агента через systemd, бюджет задержки цепочки «камера → команда». Лабораторная начинается с расчёта бюджета канала и питания (скрипт, запускается на любом компьютере), затем — подключение и измерения на железе. Первое поколение Jetson Nano снято с поддержки (JetPack 4, Ubuntu 18.04) — для новых проектов его не берут.

## theory
### Роли и граница
Pixhawk (PX4) — стабилизация, EKF, failsafe, миссии; Jetson — зрение, планирование, ROS 2, сеть. Граница та же, что в модуле «Companion: роль и границы»: без Jetson аппарат обязан лететь и возвращаться, а потеря companion в offboard обрабатывается failsafe PX4 (`COM_OF_LOSS_T`, `COM_OBL_RC_ACT`), а не надеждой. PX4 следит за companion и вторым способом: если по MAVLink перестал приходить HEARTBEAT от компонента типа «onboard controller», через 5 с (до 1.18 — `COM_OBC_LOSS_T`, 5 с по умолчанию) commander пишет «Connection to mission computer lost». Это только предупреждение, действия нет (`Commander.cpp`, v1.17.0 и v1.18.0) — реакцию задаёт offboard-failsafe. В 1.18 таймаут параметром не задаётся: 5 с зашиты в коде, `COM_OBC_LOSS_T` удалён.

### Какой Jetson и какая система
| Плата | Режимы мощности: исходные → Super (`nvpmodel`) | INT8 sparse, TOPS: исходно → Super | Что даёт |
|---|---|---|---|
| Orin Nano 4 ГБ | 7, 10 Вт → 7 (или 10), 25 Вт, MAXN SUPER | 20 → 34 | минимальный детектор |
| Orin Nano 8 ГБ | 7, 15 Вт → 15, 25 Вт, MAXN SUPER | 40 → 67 | основной выбор для детекции и трекинга |
| Orin NX 8 ГБ | 10, 15, 20 Вт, MAXN → +40 Вт, MAXN SUPER | 70 → 117 | тот же форм-фактор модуля, вдвое больше вычислений |
| Orin NX 16 ГБ | 10, 15, 25 Вт, MAXN → +40 Вт, MAXN SUPER | 100 → 157 | несколько моделей одновременно |
| Jetson Nano (2019) | снят с поддержки, JetPack 4 | — | не для новых проектов |

Цифры режимов и TOPS — из анонса Super Mode NVIDIA (JetPack 6.2, январь 2025). Для Orin Nano 4 ГБ анонс противоречит сам себе (10 или 7 Вт в нижнем режиме Super) — смотри `nvpmodel -q` на своей плате. TOPS — пиковые разреженные INT8; реальная скорость модели — в `per-edge-ml` и `comp-jetson-nano`.

Версия JetPack определяет Ubuntu, а значит и дистрибутив ROS 2. На ноябрь 2026 текущий — JetPack 7.2.2 (Jetson Linux 39.2.2): Ubuntu 24.04, ядро 6.8, CUDA 13.2.2, поддерживает Thor и всё семейство Orin; ему соответствует ROS 2 Jazzy и агент Micro XRCE-DDS v2.4.3. Предыдущая линия — JetPack 6.2.x на Ubuntu 22.04 с ROS 2 Humble и агентом v2.4.2. Документация PX4 1.17 называет рекомендуемой платформой Humble на 22.04, но Jazzy в ней тоже описан (таблица версий агента). Правило: выбирай пару «JetPack — ROS 2» по одной Ubuntu и не ставь ROS 2 «не своей» Ubuntu — это путь к сборке из исходников и вечным проблемам с зависимостями. Новый проект на Orin — JetPack 7.2.x + Jazzy; существующий стек на Humble переносить ради одного Jetson смысла нет.

Две ловушки JetPack 7.2.x для Orin Nano devkit. SD-образа больше нет — система ставится с ISO-образа или с x86-хоста. ISO не переводит в Super плату, загрузчик которой прошит без конфигурации `-super` (ответ инженера NVIDIA на форуме, июнь 2026): у таких плат — в том числе продаваемых как Super Developer Kit — в списке режимов остаются 7 и 15 Вт, а режим, выставленный вручную через `nvpmodel`, после перезагрузки откатывается на 15 Вт. Признак — в `/etc/nv_boot_control.conf` нет суффикса `-super`. Лечится перепрошивкой с x86-хоста с конфигурацией `jetson-orin-nano-devkit-super`; проверка — `sudo nvpmodel -q` показывает MAXN SUPER.

### Питание и тепло
- Jetson — **отдельный** BEC или DC-DC от силовой шины с запасом по мощности, не от полётного контроллера; общая земля с Pixhawk. Ток со стороны батареи I = P / (η·U_min). Пример лабораторной: модуль в режиме 25 Вт плюс 5 Вт на несущую плату и камеру, КПД 0.9: на 4S при 13.2 В (3.3 В на элемент) — 2.53 А, на 6S при 19.8 В — 1.68 А; преобразователь берут на 1.5 × 30 = 45 Вт (ориентир курса, как для BEC в `el-power-design`). Входной диапазон несущей платы смотри в её документации: devkit и сторонние платы отличаются.
- Режим мощности: `sudo nvpmodel -q` показывает текущий, `nvpmodel -m <N>` переключает (номера режимов зависят от модуля и описаны в `/etc/nvpmodel.conf`); `jetson_clocks` фиксирует частоты (стабильная задержка ценой энергии). Режим — это потолок частот, а не гарантия: при перегреве частоты снизятся и в MAXN.
- Тепло: в закрытом корпусе без обдува Orin троттлит через несколько минут, и задержка детекции растёт вдвое (модуль «ML на борту»). Радиатор с вентилятором или обдув от пропов, `tegrastats --interval 1000 --logfile tegra.log` в логе полёта: в строке видны загрузка и частоты CPU и GPU (`GR3D_FREQ`), температуры узлов и мощность по шинам. Троттлинг выглядит как падение частоты GPU при той же загрузке и температуре у верхней границы.

### Физическое подключение
- **UART (рекомендуется для полёта)**: TELEM2 Pixhawk — TX, RX, GND; Jetson — пины 8 (TX) и 10 (RX) 40-пиновой гребёнки, земля на пин 6. TX↔RX перекрёстно. Логика 3.3 В с обеих сторон; **5 В с разъёма TELEM2 к Jetson не подключать**.
- **Имя устройства зависит от платы и JetPack**: на Orin этот UART бывает `/dev/ttyTHS0` или `/dev/ttyTHS1`, на старом Nano — `/dev/ttyTHS1`; отладочная консоль Orin — `/dev/ttyTCU0`. Не верь статье — проверь петлёй (практика, шаг 2).
- **Ethernet** (Pixhawk 6X, 6X Pro и др.): MAVLink и uXRCE-DDS по UDP, без ограничения скорости UART — лучший вариант, если есть. На `px4/fmu-v6x` PX4 1.17 по умолчанию ставит `MAV_2_CONFIG` = 1000 (Ethernet, `rc.board_defaults`; там же `MAV_2_MODE` = 0 Normal — для companion поставь 2 Onboard).
- **USB** — для стенда; в полёте USB-соединение ненадёжно: вибрация разъёма и перезапуск энумерации обрывают связь.

### Два канала связи
1. **MAVLink** (MAVSDK, pymavlink, MAVROS): `MAV_1_CONFIG = TELEM2` (102), `MAV_1_MODE = Onboard` (набор потоков для companion), `SER_TEL2_BAUD = 921600`. По умолчанию второй экземпляр MAVLink выключен (экономия ОЗУ, комментарий в `src/modules/mavlink/module.yaml`), а `MAV_1_MODE` уже равен 2 — Onboard. `MAV_1_RATE` = 0 означает «половина теоретической полосы»: baud/20 = 46 080 байт/с при 921600. Плюс: стандарт, тот же код работает с ArduPilot; минус: ограниченный набор данных и частот.
2. **uXRCE-DDS**: `UXRCE_DDS_CFG = TELEM2` (102), та же скорость, MAVLink на этом порту выключен (`MAV_1_CONFIG = Disabled` или перенесён на другой порт). На Jetson — `MicroXRCEAgent serial --dev <порт> -b 921600`; топики `/fmu/out/*`, `/fmu/in/*` из `px4_msgs` **той же версии**, что прошивка (сообщения версионируются: в 1.17 у части топиков суффикс `_v1` — `vehicle_status_v1`, `vehicle_local_position_v1`, `battery_status_v1`; в 1.16 — только у `vehicle_status`, в 1.15 суффиксов нет; в 1.18 — уже `vehicle_status_v4`). Плюс: внутренние топики PX4 с малой задержкой; минус: только PX4, версии должны совпадать.

На одном порту живёт что-то одно. Нужны оба — MAVLink на TELEM1/USB/Ethernet, DDS на TELEM2. По Ethernet оба живут на одном кабеле, но на разных UDP-портах: `MAV_2_CONFIG` = 1000 для MAVLink и `UXRCE_DDS_CFG` = 1000 для DDS. Адрес агента клиент берёт из `UXRCE_DDS_AG_IP` — это IPv4, записанный как знаковое 32-битное целое (192.168.1.2 → −1062731518, 127.0.0.1 → 2130706433 — умолчание), порт — `UXRCE_DDS_PRT` (8888).

### Пропускная способность канала
UART 8N1 переносит байт за 10 бит: 921600 бод — 92 160 байт/с, 3 000 000 бод (предел ключа `-b` у `uxrce_dds_client`) — 300 000 байт/с. Клиент DDS шлёт все выходные топики своей сборки, независимо от подписчиков; по расчёту модуля `px4-ros2` все 27 выходных топиков PX4 1.17.0 на своих пределах частоты дают 107 495 байт/с, то есть 117 % от 921600 и 36 % от 3 Мбод. Подмножество, которое обычно нужно узлу (`vehicle_odometry`, `vehicle_local_position_v1`, `vehicle_status_v1`, `timesync_status`), — 26 835 байт/с, 29 % от 921600. Реальная частота части топиков ниже предела, поэтому настоящую нагрузку показывает `Payload tx` в `uxrce_dds_client status` — но только данные CDR, без ~23 байт заголовков на сэмпл (при всех топиках на пределах ~78 900 байт/с вместо 107 495 по проводу). Держи `Payload tx` ниже ~50 % ёмкости (ориентир курса: с заголовками это около 70 % линии; при 921600 — ниже ~46 000 байт/с). Время на передачу одного кадра уставки — t = 10·N / baud: `TrajectorySetpoint` (64 байта CDR плюс ~23 байта заголовков) при 921600 — 0.94 мс, при 3 Мбод — 0.29 мс. Сама передача почти ничего не стоит в бюджете задержки; дорого обходится очередь, когда канал перегружен.

{{diagram:jetson-link-choice|Ethernet снимает вопрос полосы; на UART DDS со всеми топиками не помещается в 921600 (117 %), поэтому либо 3 Мбод и контроль Payload tx, либо MAVLink, а два протокола — на разных портах.}}

### Разобранный пример: бюджет задержки
Камера CSI 60 кадр/с (до 16 мс до готового кадра) → TensorRT YOLO-nano FP16 ~12 мс → трекер 2 мс → DDS по UART 921600 ~2 мс (кадр 0.94 мс плюс ожидание цикла клиента) → контроллер скорости PX4 (постоянная времени ~0.5 с). Чистая задержка 16 + 12 + 2 + 2 = 32 мс, с округлением ~35 мс: контур слежения с Kp ≈ 1 1/с устойчив с запасом (модуль «Слежение»). USB-камера с MJPEG добавляет 40–80 мс (итого 72–112 мс), Wi-Fi-мост вместо провода — ещё 20–50 мс с джиттером (вместе 92–162 мс, в 3–5 раз больше, чем на проводе); две такие «мелочи» съедают весь запас. Отсюда правило: CSI и провод, не USB и радио.

{{diagram:jetson-latency-budget|На проводе и CSI цепочка укладывается в 32 мс; USB-камера и Wi-Fi-мост вместе дают 92–162 мс — в 3–5 раз больше.}}

{{diagram:px4-jetson-link|PX4 и Jetson: камера на Jetson, связь с полётным контроллером по TELEM2 через MAVLink или uXRCE-DDS.}}

{{lesson:per-edge-ml|Там — как честно измерить задержку и тепловой режим самой модели (прогрев, перцентили, 20 минут в корпусе), чтобы цифра 12 мс в этом бюджете была твоей, а не из рекламы.}}

### Справочник: параметры и команды
| Параметр / команда | Умолчание (PX4 1.17.0) | Значения | Зачем |
|---|---|---|---|
| `MAV_1_CONFIG` | выкл. | 102 TELEM2, 1000 Ethernet | порт MAVLink для companion |
| `MAV_1_MODE` | 2 (Onboard) | 0 Normal, 2 Onboard, 7 Minimal… | набор потоков |
| `MAV_1_RATE` | 0 | байт/с; 0 → baud/20 | полоса MAVLink |
| `SER_TEL2_BAUD` | 921600 | бод | скорость TELEM2 |
| `UXRCE_DDS_CFG` | 0 (выкл.) | 102 TELEM2, 1000 Ethernet | порт клиента DDS |
| `UXRCE_DDS_AG_IP` / `UXRCE_DDS_PRT` | 2130706433 / 8888 | int32 / 0–65535 | агент по Ethernet |
| — (до 1.18 `COM_OBC_LOSS_T`) | 5 с | в 1.18 не настраивается | предупреждение о потере companion (MAVLink) |
| `COM_OF_LOSS_T` / `COM_OBL_RC_ACT` | 1 с / 0 (Position) | с / 0–7 | потеря Offboard (`px4-ros2`) |
| `sudo nvpmodel -q` / `-m <N>` | — | режимы модуля | режим мощности |
| `sudo jetson_clocks` | — | — | частоты на максимум режима |
| `tegrastats --interval 1000 --logfile f` | — | мс | частоты, температуры, мощность |
| `MicroXRCEAgent serial --dev <порт> -b 921600` | — | агент v2.4.3 (Jazzy) / v2.4.2 (Humble) | сторона Jetson |

### Место в системе

- **Получает:** питание от отдельного BEC с запасом по току (`el-power-design`); топики и команды PX4 по TELEM2 (`px4-ros2`); кадры камеры CSI (`per-camera`); порт, освобождённый от других драйверов (`px4-setup-scratch`).
- **Отдаёт:** уставки Offboard — контроллеру скорости PX4 (`px4-control`); бюджет задержки «камера → команда» — контуру слежения (`per-tracking`); систему с ROS 2 — узлам (`ros2-px4`).
- **Если ошибиться здесь:** Jetson в закрытом корпусе без обдува → троттлинг → задержка детекции растёт вдвое → контур слежения теряет запас и раскачивается (`per-edge-ml`, `per-tracking`). MAVLink и uXRCE-DDS на одном TELEM2 → топиков `/fmu/*` нет, узел молчит (`px4-ros2`). DDS со всеми топиками на 921600 → канал переполнен, уставки ждут в очереди, пауза дольше `COM_OF_LOSS_T` выбивает из Offboard (`px4-ros2`).

## practice
### Шаг 0. Бюджет канала и питания (расчёт, без железа)
Перед пайкой посчитай, что именно пойдёт по проводу и сколько тока возьмёт Jetson. Скрипт ниже запускается на любом компьютере с Python 3; числа `DDS_ALL_CAPS` и `DDS_TYPICAL` — результат лабораторной `px4-ros2` для PX4 1.17.0. Сохрани как `link_lab.py`:
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
Вывод `python3 link_lab.py` (2026-11-26):
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
Как читать. Пункт 1 — ёмкость провода и полоса, которую MAVLink возьмёт сам при `MAV_1_RATE` = 0. Пункт 2 — решение по скорости: на 921600 полный набор DDS-топиков не помещается, на 1.5 Мбод занимает 72 %, на 3 Мбод — 36 %; если Pixhawk и Jetson на твоём кабеле устойчиво работают на 3 Мбод (проверяется петлёй шага 2 на этой скорости), это самый простой запас. Пункт 4 — значения для `UXRCE_DDS_AG_IP`, если связь по Ethernet: первые два совпадают с примерами из описания параметра в PX4, так что формула проверена. Пункт 6 — от него зависит выбор DC-DC и сечение провода питания Jetson.

### Шаг 1. Подготовка Jetson
```bash
sudo usermod -aG dialout $USER        # access to serial ports (log out and in)
systemctl status nvgetty              # on boards where the header UART is a console, stop it:
sudo systemctl disable --now nvgetty
sudo nvpmodel -q                      # current power mode
```
Запиши режим мощности. Для Orin Nano 8 ГБ, прошитого конфигурацией Super, ожидаемы режимы 15 Вт, 25 Вт и MAXN SUPER; если в списке только 7 и 15 Вт — плата прошита без Super (раздел «Какой Jetson и какая система»).

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
Ровно один порт должен ответить OK — это и есть пины 8/10 на вашей системе. «Permission denied» — группа dialout или консоль на порту; «no echo» на обоих — пины не те или UART выключен в device tree (Jetson-IO: `sudo /opt/nvidia/jetson-io/jetson-io.py`). Если планируешь 3 Мбод, повтори петлю с `3000000` вместо `921600`: петля проверяет UART Jetson, но не кабель до Pixhawk — финальная проверка скорости делается в шаге 4 по счётчику `Payload tx` без обрывов сессии.

### Шаг 3. MAVLink-канал
Параметры PX4 в QGC: `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard`, `SER_TEL2_BAUD = 921600`, перезагрузка. Перемычку снять, подключить TX/RX/GND (питание Jetson — от своего DC-DC, пропеллеры сняты на всё время шагов 3–6). Проверка:
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
MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600   # your port from step 2
ros2 topic list | grep fmu                     # versioned names, e.g. ..._v1 since PX4 1.16/1.17
ros2 topic hz /fmu/out/vehicle_attitude
ros2 topic echo --once /fmu/out/timesync_status
```
Сравнить частоту `vehicle_attitude` с ATTITUDE из шага 3. В консоли PX4 (MAVLink Shell в QGC через USB) — `uxrce_dds_client status`: записать `Payload tx` и сравнить с половиной ёмкости из шага 0 (~46 000 из 92 160 байт/с при 921600: `Payload tx` не считает заголовки).

### Шаг 5. Автозапуск агента
`/etc/systemd/system/xrce-agent.service` (в `ExecStart` — свой порт из шага 2, `ttyTHS0` или `ttyTHS1`):
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
`sudo systemctl enable --now xrce-agent`; проверить, что после `sudo kill` агента топики возвращаются сами — в пределах ~10 с (ориентир курса: 2 с `RestartSec` + ~3 с на три пропущенных пинга + пересоздание сессии); замерь и запиши своё время. Путь к бинарнику, пользователь и порт — свои. Клиент PX4 переподключается сам: при пропаже агента после трёх пропущенных пингов (~3 с) он пересоздаёт сессию, так что полётник перезагружать не нужно (вывод из кода; если `/fmu/in/*` после перезапуска не доходят — включи `UXRCE_DDS_RX_TO`).

### Шаг 6. Тепло под нагрузкой
Запустить детектор (модуль «Компьютерное зрение») на 20 минут в корпусе, писать `tegrastats --interval 1000 --logfile tegra.log`. Найти момент троттлинга (частота GPU падает, температура у предела) и задержку детекции до и после.

### Переход на реальное железо: отбой и приёмка
Шаги 1–6 и есть железо; порядок безопасности такой. Пропеллеры сняты до конца шага 6. Отбой и разбор, если: напряжение на входе Jetson под нагрузкой детектора проседает больше чем на 5 % от номинала DC-DC (ориентир курса), Jetson перезагружается при нагрузке моторов на стенде, `Payload tx` держится выше 50 % ёмкости (ориентир курса), сессия агента рвётся (в логе агента — повторное создание сессии) или `timesync converged: false`. Приёмка для полёта: 20 минут детектора в корпусе без троттлинга или с троттлингом, при котором задержка цепочки остаётся в бюджете модуля «Слежение»; агент поднимается сам после `kill` и после холодного старта.

Самопроверка: лабораторная выполнена, когда (расчёт) твой запуск шага 0 дал 92160 B/s и 46080 B/s для 921600, 117 % / 72 % / 36 % для трёх скоростей, −1062731518 для 192.168.1.2 и 2.53 A для 25 Вт на 4S; (железо) петля на пинах 8/10 дала OK ровно на одном порту, MAVLink-канал отдаёт ATTITUDE и LOCAL_POSITION_NED с записанными частотами, по uXRCE-DDS виден `vehicle_attitude` и его частота записана рядом с ATTITUDE из шага 3, `Payload tx` записан и ниже 50 % ёмкости выбранной скорости, после `sudo kill` агента топики возвращаются сами (время записано, ориентир курса — до ~10 с), а в 20-минутном `tegra.log` найден момент троттлинга (или видно, что его не было) и записана задержка детекции до и после.

**Эталон для самопроверки.** Верный результат: один порт, два канала с измеренными частотами, `Payload tx` ниже 50 % ёмкости, агент поднимается сам. Типичные неверные: (1) OK не ответил ни один порт — пины не те или UART выключен в device tree, а «Permission denied» — группа dialout или консоль на порту; (2) MAVLink работал, а топиков DDS нет — MAVLink остался на том же порту (`MAV_1_CONFIG` не Disabled), у агента другая скорость, агент ветки v3.x или `px4_msgs` другой версии; (3) задержка детекции выросла примерно вдвое через несколько минут — троттлинг в закрытом корпусе без обдува; (4) в шаге 0 вышло 115 200 байт/с для 921600 — посчитано 8 бит на байт вместо 10 (старт- и стоп-бит забыты); (5) для IP получилось 3232235778 — это беззнаковое значение, параметр ждёт знаковое int32.

## diagnostics
- **Симптом:** `Permission denied: /dev/ttyTHS*`
  - Возможная причина: пользователь не в dialout или на порту консоль.
  - Что сделать: `usermod -aG dialout`, перелогиниться, `systemctl disable --now nvgetty`.
- **Симптом:** порт открывается, данных нет
  - Возможная причина: не тот ttyTHS, TX/RX не перекрещены, нет общей земли, MAVLink на TELEM2 не включён.
  - Что сделать: петля из шага 2, проверка проводки, `MAV_1_CONFIG`.
- **Симптом:** MAVLink работает, uXRCE-DDS — нет
  - Возможная причина: MAVLink всё ещё на том же порту, агент не той скорости, агент v3.x, `px4_msgs` другой версии.
  - Что сделать: `MAV_1_CONFIG = Disabled`, одинаковый baud, агент v2.4.3/v2.4.2, `px4_msgs` из ветки, совпадающей с прошивкой.
- **Симптом:** топики есть, но `ros2 topic echo` молчит
  - Возможная причина: несовпадение QoS (PX4 публикует best effort).
  - Что сделать: подписчик с `qos_profile_sensor_data`, `ros2 topic echo --qos-reliability best_effort`.
- **Симптом:** топики то есть, то пропадают; частоты ниже ожидаемых
  - Возможная причина: UART переполнен — полный набор DDS-топиков требует 117 % от 921600.
  - Что сделать: `uxrce_dds_client status` → `Payload tx`; поднять скорость до 1.5–3 Мбод (обе стороны), Ethernet или урезанный `dds_topics.yaml`.
- **Симптом:** по Ethernet клиент не находит агента
  - Возможная причина: `UXRCE_DDS_AG_IP` введён как беззнаковое число или с переставленными октетами, агент слушает другой порт.
  - Что сделать: пересчитать IP в знаковое int32 (шаг 0), сверить `UXRCE_DDS_PRT` и `MicroXRCEAgent udp4 -p`.
- **Симптом:** после установки JetPack 7.2 нет режимов 25 Вт и MAXN SUPER, ручной режим сбрасывается после перезагрузки
  - Возможная причина: плата прошита без конфигурации Super; ISO не переводит её в Super.
  - Что сделать: перепрошить с x86-хоста конфигурацией `jetson-orin-nano-devkit-super`, проверить `nvpmodel -q`.
- **Симптом:** в QGC «Connection to mission computer lost»
  - Возможная причина: HEARTBEAT companion по MAVLink пропал дольше 5 с (до 1.18 — `COM_OBC_LOSS_T`): упал процесс, перезагрузка Jetson.
  - Что сделать: это предупреждение без действия — проверить, что offboard-failsafe (`COM_OBL_RC_ACT`) настроен; разобрать `journalctl` на Jetson.
- **Симптом:** задержка детекции растёт через 10 минут полёта
  - Возможная причина: троттлинг Jetson.
  - Что сделать: обдув, режим `nvpmodel`, `tegrastats` в логе полёта.
- **Симптом:** Jetson перезагружается на газу
  - Возможная причина: просадка общего BEC или DC-DC без запаса (расчёт тока — шаг 0).
  - Что сделать: отдельный DC-DC с запасом 1.5×, конденсатор на входе, измерить напряжение осциллографом под нагрузкой.

## references
- PX4 — Pixhawk + Companion Computer | https://docs.px4.io/v1.17/en/companion_computer/pixhawk_companion.html | primary | A
- PX4 — uXRCE-DDS (PX4–ROS 2/DDS bridge) | https://docs.px4.io/v1.17/en/middleware/uxrce_dds.html | primary | A
- PX4-Autopilot v1.17.0 — mavlink module.yaml (MAV_n_CONFIG, MAV_n_MODE, MAV_n_RATE) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/mavlink/module.yaml | primary | A
- PX4-Autopilot v1.17.0 — uxrce_dds_client module.yaml (UXRCE_DDS_AG_IP int32 encoding) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/uxrce_dds_client/module.yaml | primary | A
- NVIDIA — JetPack SDK / Jetson Linux 39.2.2 (JetPack 7.2.2) | https://developer.nvidia.com/embedded/jetson-linux | primary | A
- NVIDIA — JetPack 7.2.1 release notes and downloads | https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.2.1 | primary | A
- NVIDIA Technical Blog — JetPack 6.2 brings Super Mode to Orin Nano and Orin NX | https://developer.nvidia.com/blog/nvidia-jetpack-6-2-brings-super-mode-to-nvidia-jetson-orin-nano-and-jetson-orin-nx-modules | primary | A
- NVIDIA Developer Forums — 25W and MAXN SUPER not seen in JetPack 7.2 | https://forums.developer.nvidia.com/t/25w-and-maxn-super-not-seen-in-jetpack-7-2/372627 | secondary | B
- eProsima — Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | primary | A
- NVIDIA Developer Forums — UART1 on expansion pins 8/10 (Orin) | https://forums.developer.nvidia.com/t/how-to-access-uart1-on-expansion-pins-8-10/328934 | secondary | B

## checklist
- Понимаю границу Jetson и PX4 и что делает PX4 при потере companion
- Выбираю JetPack и ROS 2 под одну Ubuntu; проверяю, что Orin прошит с Super, если нужен 25 Вт
- Питаю Jetson отдельно с запасом 1.5×, считаю ток со стороны батареи, слежу за теплом и режимом мощности
- Нахожу свой UART петлёй, не по статье
- Настраиваю MAVLink и uXRCE-DDS на разных портах и проверяю частоты
- Считаю пропускную способность: `Payload tx` (без заголовков) ниже 50 % ёмкости канала
- Поднимаю агент через systemd с автоперезапуском
- Считаю бюджет задержки «камера → команда»
