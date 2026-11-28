---
id: ap-companion
title: "Companion + ArduPilot: управление из кода"
level: L3
readingTime: 50 мин
firmware: ArduPilot 4.7 (сверено с 4.7.3; лабораторная — Copter SITL 4.7.2 + MAVProxy 1.8.75 + pymavlink 2.4.50)
status: published
added: 2026-11-07
tags:
  - GUIDED
  - offboard
  - pymavlink
  - SERIAL
  - маршрутизация
related:
  - comp-raspberry
  - ap-missions
  - mav-routing
  - mav-sdk
next:
  - bf-custom
---

## summary
Режим GUIDED — дверь, через которую бортовой компьютер управляет аппаратом: «лети в точку», «держи скорость», «смотри туда». Модуль показывает, как из Python на companion задавать цели по позиции и скорости, как ArduPilot защищает себя от молчащего или спятившего companion и как построить цикл управления так, чтобы его можно было безопасно отлаживать в SITL. Перед этим — провод: какой порт FC отдать companion, какие `SERIALn_*` поставить, какие параметры 4.7.2 переименованы (`SRn_*` → `MAVn_*`, `SYSID_THISMAV` → `MAV_SYSID`), почему ArduCopter 4.7 по умолчанию не шлёт companion никакой телеметрии и кто из участников сети считается наземной станцией для failsafe. Лабораторная прогнана на ArduCopter 4.7.2 SITL через MAVProxy-роутер: аудит параметров, GUIDED-арм и взлёт с проверкой COMMAND_ACK, поток целей по скорости, замер остановки после молчания companion (спад через 3.2–3.3 с, стоп < 0.2 м/с через 4.3 с) и перехват управления пилотом. Итог — каркас для capstone трека: своя логика на борту.

## theory
### Канал companion ↔ FC: порт, протокол, скорость
Companion подключают к свободному телеметрийному UART полётного контроллера (обычно TELEM2 = `SERIAL2`; USB FC оставляют для настройки). На стороне FC три настройки порта: протокол `SERIALn_PROTOCOL = 2` (MAVLink2; значение 1 — MAVLink1, 45 — DDS XRCE для ROS 2), скорость `SERIALn_BAUD` и аппаратное управление потоком `BRD_SERn_RTSCTS`. Скорость задаётся кодом, а не числом бод: 57 = 57600, 115 = 115200, 460 = 460800, 921 = 921600, 1500 = 1.5 Мбод (`AP_SerialManager.cpp`, `@Values` у `SERIAL1_BAUD`). Умолчания 4.7.2 для `SERIAL1` и `SERIAL2` — MAVLink2 на 57 (`AP_SerialManager.cpp:47–64`, подтверждено аудитом параметров в SITL). Для companion 57600 мало, и это видно из арифметики.

UART 8N1 передаёт 10 бит на байт, значит 921600 бод — это 92 160 байт/с, а 57600 бод — 5 760 байт/с. Кадр MAVLink2 добавляет к полезной нагрузке 12 байт (10 байт заголовка и 2 байта CRC; подпись — ещё 13). LOCAL_POSITION_NED и ATTITUDE несут по 28 байт нагрузки, на проводе — до 40 байт каждое. Companion, которому для контура слежения нужны поза и ориентация по 50 Гц, забирает 2 × 50 × 40 = 4000 байт/с: это 69 % канала 57600 и 4.3 % канала 921600. На 57600 к этому добавятся поток GCS через роутер, параметры и миссии — канал переполнится, сообщения начнут теряться, и отказ будет выглядеть как «случайные таймауты» в коде. Ориентир курса: 921 для companion на коротком проводе (до ~30 см), загрузка канала не выше 50 %, при 1500 — только с `BRD_SERn_RTSCTS = 1` и проверкой потерь.

Управление потоком: `BRD_SER1_RTSCTS` — 0 выключено, 1 включено, 2 автоопределение, 3 — вывод RTS как разрешение драйвера RS-485; у `BRD_SER1_RTSCTS`…`BRD_SER3_RTSCTS` умолчание 2, автоопределение (`AP_BoardConfig.cpp`); параметра нет, если у порта на этой плате нет линий RTS/CTS (`HAL_HAVE_RTSCTS_SERIALn`). Если линии RTS/CTS не разведены до companion, ставь 0 явно, чтобы не зависеть от автоопределения. Уровни UART — 3.3 В у FC и у Raspberry Pi; земля общая, провод TX FC → RX companion и наоборот.

В 4.7 два бита `SERIALn_OPTIONS` переехали в `MAVn_OPTIONS`: «не пересылать MAVLink в этот порт и из него» (было бит 10, стало бит 1) и «игнорировать запросы частот потоков» (было бит 12, стало бит 2); бит 0 `MAVn_OPTIONS` — принимать неподписанные MAVLink2 (`GCS_MAVLink_Parameters.cpp`, `@Bitmask` у `_OPTIONS`). Конвертация при обновлении делается один раз (скрытый `MAVn_OPTIONSCNV`).

{{lesson:comp-raspberry|UART Raspberry Pi, конфигурация mavlink-router, бюджет питания и systemd-сторож — сторона companion того же провода.}}

### Каналы MAVn и потоки телеметрии в 4.7
Параметры канала MAVLink в 4.7 собраны в группу `MAV`: `MAV1_*`, `MAV2_*` … по одному блоку на канал. Номер канала — это не номер `SERIALn`: канал 1 — консоль (`SERIAL0`, USB), а дальше каналы раздаются портам с протоколом MAVLink по порядку их номеров (вывод из кода: консоль — `GCS::setup_console`, `GCS_Common.cpp:2808–2819`; остальные — `GCS::setup_uarts`, `GCS_Common.cpp:2844–2853`). Если MAVLink стоит на `SERIAL0`, `SERIAL1` и `SERIAL2`, то companion на `SERIAL2` — это `MAV3_*`; если `SERIAL1` переключить на GPS, тот же провод станет `MAV2_*`.

В каждом блоке — частоты групп потоков `_RAW_SENS`, `_EXT_STAT`, `_RC_CHAN`, `_RAW_CTRL`, `_POSITION`, `_EXTRA1`, `_EXTRA2`, `_EXTRA3`, `_PARAMS`, `_ADSB` (до 4.7 — `SR0_*` … `SR6_*`, нумерация с нуля). Для Copter все умолчания — 0 (блок `APM_BUILD_COPTER_OR_HELI` в `GCS_MAVLink_Parameters.cpp`), у Plane — в основном 1 Гц (PARAMS 10, ADSB 5), у Sub — 2…10 Гц для основных групп (RAW_CTRL, PARAMS, ADSB — 0). Аудит SITL 4.7.2 это подтверждает: `MAV1_EXT_STAT = 0`, `MAV2_POSITION = 0`, а `SR0_EXT_STAT` и `SYSID_THISMAV` отвечают «нет такого параметра». Практический вывод: companion, который молча слушает порт ArduCopter 4.7, не получит ни позиции, ни режима сверх HEARTBEAT. Варианты: (а) запросить нужные сообщения `MAV_CMD_SET_MESSAGE_INTERVAL` (511) после подключения — запрос действует на канал, по которому пришёл, и до перезагрузки; (б) прописать `MAVn_*` для своего канала (требуют перезагрузки); (в) получать поток через роутер, которому его уже запросила наземная станция — но тогда частоты определяет GCS, а не твой контур.

### Кто есть кто: sysid, compid и GCS failsafe
Companion — часть аппарата: тот же sysid, что у автопилота (`MAV_SYSID`, до 4.7 — `SYSID_THISMAV`, умолчание 1), и свой compid — по соглашению 191 (`MAV_COMP_ID_ONBOARD_COMPUTER`). ArduPilot принимает пакеты от своих компонентов всегда (`GCS_Common.cpp:7181`, «accept packets from our own components (e.g. mavlink-connected companion computers)»); от остальных sysid — тоже, пока не включён бит 0 `MAV_OPTIONS` (принимать только от `MAV_GCS_SYSID…_HI`); с ним companion на sysid аппарата остаётся допущенным. Наземная станция для ArduPilot — тот, чей sysid попадает в диапазон `MAV_GCS_SYSID`…`MAV_GCS_SYSID_HI` (до 4.7 — `SYSID_MYGCS`, умолчание 255). От этого зависят три вещи:

- HEARTBEAT companion **не** обновляет таймер GCS failsafe: его сбрасывают только пакеты от sysid наземной станции — HEARTBEAT, а также RC_CHANNELS_OVERRIDE и MANUAL_CONTROL (`GCS_Common.cpp:4342, 4224, 7456`). Companion не может «держать живым» GCS failsafe и не должен — иначе отказ радиоканала станции останется незамеченным.
- `MANUAL_CONTROL` и `RC_CHANNELS_OVERRIDE` принимаются только от sysid станции (`GCS_Common.cpp:4179, 7439`). Companion, который хочет «рулить стиками», выдаёт себя за станцию — плохая идея; для управления есть GUIDED.
- `FS_GCS_ENABLE` (умолчание 0 — выключено; 1 — RTL, 5 — LAND и т. д.) с таймаутом `FS_GCS_TIMEOUT` (умолчание 5 с, диапазон 2–120 с) следит за станцией, а не за companion. Отдельного «companion failsafe» в ArduCopter нет: от молчащего companion защищают `GUID_TIMEOUT` (только для целей скорости, ускорения и углов) и пилот.

### Маршрутизатор на companion
Один UART FC, а потребителей несколько: твой сервис, наземная станция по Wi-Fi или 4G, запись tlog. Порт `/dev/serial0` открывает только маршрутизатор (mavlink-router, MAVProxy, mavp2p), остальные подключаются к нему по UDP. В лабораторной роль маршрутизатора играет MAVProxy 1.8.75: `mavproxy.py --master=tcp:127.0.0.1:5840 --out=udp:127.0.0.1:14650 --out=udp:127.0.0.1:14651 --streamrate=-1 --daemon` — один вход от SITL, два UDP-выхода (companion и «станция»). Без `--streamrate=-1` MAVProxy запрашивает свои потоки 4 Гц и этим сбрасывает частоты, которые companion задал `SET_MESSAGE_INTERVAL` (проверено: 4.0–4.2 Гц вместо 10 Гц; с ключом — 10.0–10.2 Гц). На борту стандарт — mavlink-router как systemd-сервис (конфигурация в модуле comp-raspberry; в этой лабораторной не запускался — в окружении не установлен). Маршрутизатор пересылает пакеты по тем же правилам sysid/compid, что ArduPilot, поэтому скрипт без собственного HEARTBEAT может не получить адресованные ему ответы. И ещё одна причина держать роутер: TCP-порт SITL (и один `/dev/serial0`) принимает одного клиента, второй скрипт получит тишину.

{{lesson:mav-routing|Правила пересылки по sysid/compid, mavlink-router против MAVProxy, UDP против TCP и замер потерь под netem.}}

### GUIDED и его таймауты
В GUIDED аппарат ждёт целей от внешнего источника. Цели бывают:

- **позиция** — `SET_POSITION_TARGET_GLOBAL_INT` (86) с координатами или `SET_POSITION_TARGET_LOCAL_NED` (84) в метрах относительно дома/аппарата;
- **скорость** — те же сообщения с битовой маской `type_mask`, которая говорит «игнорируй позицию, используй скорость»;
- **ориентация/тяга** — `SET_ATTITUDE_TARGET` для продвинутых случаев.

Что будет, если companion замолчит, зависит от типа последней цели (`ArduCopter/mode_guided.cpp`, 4.7.2; `get_timeout_ms()` = `GUID_TIMEOUT` × 1000, не меньше 100 мс, и используется «только для скорости, ускорения, углов и угловых скоростей» — комментарий в коде):

- **позиция** (`pos_control_run`) — таймаута нет: аппарат долетает до последней точки и висит там сколько угодно; по таймауту только прекращается вращение по yaw rate;
- **скорость, ускорение, скорость + ускорение** (`velaccel_control_run`, `accel_control_run`) — через `GUID_TIMEOUT` уставки обнуляются: аппарат тормозит и висит;
- **позиция + скорость + ускорение** (`posvelaccel_control_run`) — скорость и ускорение обнуляются, позиция держится;
- **углы и тяга** (`SET_ATTITUDE_TARGET`, `angle_control_run`) — через `GUID_TIMEOUT` углы наклона → горизонт с прежним курсом, вертикальная скорость → 0.

`GUID_TIMEOUT` = 3.0 с по умолчанию, диапазон 0.1–5 с (`ArduCopter/Parameters.cpp`, `guided_timeout`). Замер в SITL (практика, шаг 3, телеметрия 10 Гц): при цели 2 м/с, шедшей 5 Гц, скорость держится 1.98–1.99 м/с до 3.21 с после последней цели, первый спад виден на 3.31 с, ниже 0.2 м/с — на 4.32 с. Это защита, на которую надо опираться, а не обходить; и это аргумент давать с companion цели скорости, а не позиции, там, где отказ companion должен останавливать аппарат.

{{diagram:guided-silence-tree|Таймаут есть только у целей скорости, ускорения и углов: после цели по позиции замолчавший companion оставляет аппарат лететь в точку и висеть там.}}

### Система координат
`LOCAL_NED`: X — север, Y — восток, Z — **вниз**. Подъём на 10 м — это Z = −10. Половина ошибок offboard-кода — знак оси Z. Для целей относительно носа аппарата есть `MAV_FRAME_BODY_OFFSET_NED`.

### Что проверяет FC
Геозона (`FENCE_*`), ограничения скорости и ускорения (`WP_*`, до 4.7 — `WPNAV_*`), батарейный failsafe, здоровье EKF. Companion может просить что угодно — выполнение всё равно в рамках параметров FC. Отсюда правило отладки: если аппарат «не слушается», сначала `STATUSTEXT`, потом параметры ограничений, и только потом свой код.

### Цикл управления
Хороший цикл companion:

1. Читать состояние (позиция, скорость, режим, арм) из телеметрии с заданной частотой.
2. Считать решение.
3. Отправлять цель **регулярно** (например, 5–10 Гц для скорости), даже если она не изменилась.
4. Проверять, что режим всё ещё GUIDED: пилот тумблером может забрать управление в любой момент, и код обязан это уважать.

### Код companion как конечный автомат
Скрипт «отправил команду, поспал 10 секунд, отправил следующую» работает в SITL и ломается в поле: команда не принята, пилот переключил режим, GPS пропал. Надёжная форма — автомат состояний, где каждый переход проверяет условие и имеет таймаут:

| Состояние | Что делает | Переход дальше | Если не вышло |
|---|---|---|---|
| WAIT_READY | ждёт GPS fix и EKF OK по телеметрии | готовность | ждать, ничего не слать |
| ARM_TAKEOFF | GUIDED, арм, `MAV_CMD_NAV_TAKEOFF`, ждёт ACK и высоту ≥ 90 % цели | высота достигнута | за 20 с нет высоты → LAND |
| TASK | шлёт цели с частотой 5–10 Гц, проверяет режим каждую итерацию | задача выполнена | режим не GUIDED → PILOT |
| RETURN | `RTL` по команде смены режима | дизарм | — |
| PILOT | **молчит**, только читает телеметрию | пилот вернул GUIDED и подтвердил | — |

Каркас:
```python
import time
from pymavlink import mavutil

class Mission:
    def __init__(self, m):
        self.m, self.state, self.t0 = m, "WAIT_READY", time.time()
        self.alt, self.mode, self.armed = 0.0, "", False

    def go(self, state):
        print(f"{self.state} -> {state}"); self.state, self.t0 = state, time.time()

    def read(self):
        while (msg := self.m.recv_match(blocking=False)) is not None:
            t = msg.get_type()
            if t == "GLOBAL_POSITION_INT": self.alt = msg.relative_alt / 1000
            elif t == "HEARTBEAT" and msg.type != mavutil.mavlink.MAV_TYPE_GCS:
                self.mode = mavutil.mode_string_v10(msg)
                self.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def step(self):
        self.read()
        if self.state in ("TASK", "ARM_TAKEOFF") and self.mode not in ("GUIDED", ""):
            return self.go("PILOT")                       # the pilot always wins
        if self.state == "ARM_TAKEOFF" and time.time() - self.t0 > 20 and self.alt < 9:
            self.m.set_mode(self.m.mode_mapping()["LAND"]); return self.go("PILOT")
        # ... the remaining transitions follow the table
```
Такой код легко тестировать: подмените `m` фейковым соединением (как в `examples/mavlink/tests`) и проверьте каждую строку таблицы, включая «пилот забрал управление посреди TASK».

### Безопасность при разработке
- Всё сначала в SITL. Тот же код, тот же порт, только адрес другой.
- Пилот с пультом и тумблером на LOITER/RTL — всегда, даже когда «точно работает».
- Геозона включена и проверена.
- Первые реальные тесты — только цели по позиции на малой высоте; скорость — потом.

### Питание, загрузка и сторож companion
Companion питают от отдельного BEC 5 В с запасом по току (Raspberry Pi 4/5 под нагрузкой — больше ампера, Jetson — несколько ампер), а не от телеметрийного порта FC: просадка при старте камеры или модема перезагрузит компьютер посреди полёта, и для автопилота это будет просто тишина на канале. Земля у FC и companion общая (через сигнальный провод UART и силовую шину), иначе UART ловит помехи.

Вторая гонка — время загрузки. FC готов через секунды, Linux-компьютер — через десятки секунд, а сервис с маршрутизатором ещё позже. Отсюда правила кода: ждать HEARTBEAT автопилота с таймаутом и повторять, а не падать; запрашивать потоки (`SET_MESSAGE_INTERVAL`) после каждого переподключения, потому что они живут до перезагрузки FC; никогда не армить «по старту сервиса» — только по явной команде и проверенному состоянию (автомат `WAIT_READY`).

Третье — зависание. Процесс жив, но не шлёт цели (deadlock, исчерпана память, троттлинг по температуре). Снаружи это выглядит так же, как смерть, и ловится двумя слоями: на companion — systemd `WatchdogSec` с перезапуском сервиса и, при желании, аппаратный сторож SoC; на FC — то, что уже есть: `GUID_TIMEOUT` для целей скорости и пилот. Если нужна реакция FC именно на пропажу companion (например, LAND после 5 с без его HEARTBEAT), это пишется Lua-скриптом: в 4.7.2 у скриптов есть приём MAVLink (`mavlink:init`, `mavlink:register_rx_msgid`, `mavlink:receive_chan` — `libraries/AP_Scripting/docs/docs.lua:4006–4017`). Это вывод из документации API, готового скрипта-сторожа в составе 4.7.2 нет — проверяй свой в SITL так же, как тест таймаута ниже.

### Пример: скорость в GUIDED (pymavlink)
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762"); m.wait_heartbeat()
m.set_mode(m.mode_mapping()["GUIDED"]); m.arducopter_arm(); m.motors_armed_wait()
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0,0,0,0,0,0, 10)
import time; time.sleep(10)
for _ in range(50):                          # 10 s at 5 Hz: forward 1 m/s in body frame
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
        0b0000111111000111,                    # use velocity only (bits: ignore pos x/y/z, acc, yaw, yaw_rate)
        0,0,0,  1.0,0.0,0.0,  0,0,0,  0,0)
    time.sleep(0.2)
# stop sending -> after GUID_TIMEOUT (3 s default) the copter stops and hovers
```
Полный стартовый проект (квадрат, тест failsafe, CI) — `examples/sitl-pymavlink` в репозитории курса. `GUID_TIMEOUT` = 3.0 с по умолчанию (диапазон 0.1–5); `GUID_OPTIONS` биты: 0 — разрешить арм с пульта в GUIDED, 2 — игнорировать yaw пилота, 6 — навигация по точкам для позиционных целей, 7 — флюгирование.

### Разобранный пример: «аппарат не двигается по команде скорости»
Проверки по порядку: (1) режим GUIDED (`HEARTBEAT.custom_mode`); (2) `type_mask` — не замаскирована ли скорость; (3) частота отправки ≥ 2 Гц (таймаут 3 с); (4) `WP_SPD` (до 4.7 — `WPNAV_SPEED`)/`PSC_*` не ограничивают до нуля; (5) геозона не держит у границы; (6) `STATUSTEXT` — «Mode change to Guided failed: requires position», «PreArm: Need Position Estimate» и т.п. Ориентир курса: чаще всего виноваты (1) или (2).

{{diagram:guided-timeout|Цель по скорости в GUIDED действует GUID_TIMEOUT (3 с по умолчанию): companion обязан повторять её чаще, иначе аппарат остановится и зависнет.}}

### Справочник параметров (ArduCopter 4.7.2)
| Параметр | Умолчание | Диапазон / значения | Старое имя (до 4.7) | Зачем companion |
|---|---|---|---|---|
| `SERIALn_PROTOCOL` | 2 (MAVLink2) на SERIAL1/2 | 1 MAVLink1, 2 MAVLink2, 45 DDS XRCE, −1 нет | — | протокол порта companion |
| `SERIALn_BAUD` | 57 (57600) на SERIAL1/2 | 57, 115, 230, 460, 921, 1500, 2000 | — | 921 для companion |
| `BRD_SERn_RTSCTS` | SER2: 2 (авто) | 0 выкл, 1 вкл, 2 авто, 3 RS-485 | — | 1, если RTS/CTS разведены, иначе 0 |
| `MAVn_EXT_STAT`, `MAVn_POSITION`, `MAVn_EXTRA1…3` | Copter: 0 Гц | 0–50 Гц, перезагрузка | `SRn_*` (n с нуля) | статические потоки канала |
| `MAVn_OPTIONS` | 0 | бит 0 неподписанные, 1 не пересылать, 2 игнорировать частоты | биты 10, 12 в `SERIALn_OPTIONS` | изоляция канала |
| `MAV_SYSID` | 1 | 1–255 | `SYSID_THISMAV` | sysid companion = этому |
| `MAV_GCS_SYSID`, `MAV_GCS_SYSID_HI` | 255, 0 | 1–255, 0–255 | `SYSID_MYGCS` | кто считается станцией |
| `GUID_TIMEOUT` | 3.0 с | 0.1–5 с | — | таймаут целей скорости, ускорения, углов |
| `GUID_OPTIONS` | 0 | биты 0, 2–7 | — | арм с пульта, yaw, навигация по точкам |
| `FS_GCS_ENABLE` | 0 | 0 выкл, 1 RTL, 3 SmartRTL/RTL, 4 SmartRTL/LAND, 5 LAND, 6 DO_LAND_START/RTL, 7 BRAKE/LAND | — | failsafe станции, не companion |
| `FS_GCS_TIMEOUT` | 5 с | 2–120 с | — | порог failsafe станции |

### Место в системе

- **Получает:** провод и питание companion (`comp-raspberry`), поток через маршрутизатор (`mav-routing`); состояние аппарата (позиция, режим, арм) из телеметрии MAVLink, которую на ArduCopter 4.7 надо запросить самому (`comp-mavlink`); здоровую оценку позиции, без которой GUIDED не работает (`ap-ekf`); рамки, в которых FC исполняет любую просьбу, — геозону и failsafe (`ap-safety-fs`).
- **Отдаёт:** цели по позиции и скорости — регулятору позиции автопилота; тот же GUIDED с `GUID_TIMEOUT` — основа контура слежения (`per-tracking`) и узла ROS 2 (`ros2-ardupilot`); код для прогона в `ap-sitl`.
- **Если ошибиться здесь:** перепутал знак Z в `LOCAL_NED` → вместо набора высоты цель уходит вниз; разбор осей — в `math-linalg-rot`. Цели по скорости приходят реже `GUID_TIMEOUT` → аппарат останавливается и зависает посреди задачи, что выглядит как отказ автопилота; ловится прогоном в `ap-sitl`. Порт на 57600 при потоках 50 Гц → потери пакетов и «случайные» таймауты в библиотеке (`mav-sdk`).

## practice
### Шаг 1. Стенд: SITL → маршрутизатор → companion
ArduCopter 4.7.2 SITL (экземпляр `-I 8`, поэтому TCP-порт SERIAL0 = 5760 + 80 = 5840, параметры `copter.parm`), MAVProxy 1.8.75 как маршрутизатор с двумя UDP-выходами и скрипт companion на первом из них. Второй выход изображает наземную станцию: с него в шаге 3 «пилот» переключит режим. Ключ `--streamrate=-1` обязателен: без него MAVProxy сам запрашивает на своём входе потоки 4 Гц (REQUEST_DATA_STREAM), а каждый такой запрос сбрасывает интервалы сообщений группы (`initialise_message_intervals_for_stream`, `GCS_Param.cpp` / `GCS_Common.cpp`) — и 10 Гц, запрошенные companion через `SET_MESSAGE_INTERVAL`, превращаются в 4 Гц. Так прогонялось:

```bash
./run_sitl.sh 8 > sitl8.log 2>&1 &      # arducopter -S --model + -I 8 -w --defaults copter.parm --home -35.363261,149.165230,584,353
sleep 2
mavproxy.py --master=tcp:127.0.0.1:5840 --out=udp:127.0.0.1:14650 --out=udp:127.0.0.1:14651 \
  --streamrate=-1 --daemon --non-interactive --state-basedir=./mp8 > mavproxy8.log 2>&1 &
sleep 4
python3 -u companion_lab.py udpin:127.0.0.1:14650
```

### Шаг 2. Скрипт companion: аудит, GUIDED, поток, тишина, перехват
Скрипт представляется компонентом 191 своего аппарата (sysid 1), читает параметры по имени (несуществующее имя возвращает None — так видно переименования 4.7), запрашивает LOCAL_POSITION_NED на 10 Гц (потоки Copter 4.7 по умолчанию 0), переводит в GUIDED, армит и взлетает с проверкой COMMAND_ACK, шлёт 2 м/с на север 5 Гц 8 с, замолкает и пишет скорость по времени, затем проверяет, что после смены режима станцией не уходит ни одной цели.

```python
"""ap-companion lab: ArduCopter 4.7.2 SITL -> MAVProxy (router) -> companion (this script, compid 191).
Param audit, GUIDED arm/takeoff with COMMAND_ACK, velocity stream at 5 Hz, then silence:
measure time from the last setpoint to the stop (GUID_TIMEOUT)."""
import math, sys, time
from pymavlink import mavutil

URL = sys.argv[1] if len(sys.argv) > 1 else "udpin:127.0.0.1:14650"
m = mavutil.mavlink_connection(URL, source_system=1, source_component=191)  # MAV_COMP_ID_ONBOARD_COMPUTER
hb = m.wait_heartbeat(timeout=20)
print(f"FC heartbeat: sysid={m.target_system} compid={m.target_component} autopilot={hb.autopilot} type={hb.type}")
L = mavutil.mavlink

def param(name, timeout=3):
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    t = time.time() + timeout
    while time.time() < t:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if p and p.param_id == name:
            return p.param_value
    return None

print("--- param audit (4.7.2 names; None = no such parameter)")
for n in ["SERIAL1_PROTOCOL", "SERIAL1_BAUD", "SERIAL2_PROTOCOL", "SERIAL2_BAUD", "MAV1_EXT_STAT", "MAV2_POSITION",
          "MAV_SYSID", "MAV_GCS_SYSID", "SYSID_THISMAV", "SR0_EXT_STAT", "GUID_TIMEOUT", "GUID_OPTIONS",
          "FS_GCS_ENABLE", "FS_GCS_TIMEOUT", "DDS_ENABLE"]:
    v = param(n)
    print(f"{n:17s} = {v if v is None else round(v, 3)}")

def cmd(command, *p, timeout=3):
    m.mav.command_long_send(m.target_system, m.target_component, command, 0, *(list(p) + [0] * (7 - len(p))))
    a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout,
                     condition=f"COMMAND_ACK.command=={command}")
    return None if a is None else a.result

state = {"mode": "", "armed": False, "alt": 0.0, "v": 0.0}
def pump(dt=0.0):
    end = time.time() + dt
    while True:
        msg = m.recv_match(blocking=dt > 0, timeout=max(0.01, end - time.time()))
        if msg is not None:
            t = msg.get_type()
            if t == "HEARTBEAT" and msg.get_srcComponent() == 1:
                state["mode"] = mavutil.mode_string_v10(msg)
                state["armed"] = bool(msg.base_mode & L.MAV_MODE_FLAG_SAFETY_ARMED)
            elif t == "LOCAL_POSITION_NED":
                state["alt"], state["v"] = -msg.z, math.hypot(msg.vx, msg.vy)
        if time.time() >= end and msg is None:
            return

# 4.7: MAVn_* stream rates are 0 by default -> ask for the message we control by, 10 Hz
print("SET_MESSAGE_INTERVAL LOCAL_POSITION_NED 10 Hz ACK =", cmd(L.MAV_CMD_SET_MESSAGE_INTERVAL, 32, 100000))
print("--- wait for EKF / GPS (pre-arm)")
t0 = time.time()
while time.time() - t0 < 90:
    m.set_mode(m.mode_mapping()["GUIDED"]); pump(1.0)
    if state["mode"] == "GUIDED":
        r = cmd(L.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        if r == 0:
            break
print(f"GUIDED + arm ACK=0 after {time.time()-t0:.1f} s, mode={state['mode']}")
print("takeoff ACK =", cmd(L.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 10))
t0 = time.time()
while state["alt"] < 9.5 and time.time() - t0 < 30:
    pump(0.2)
print(f"alt {state['alt']:.1f} m after {time.time()-t0:.1f} s")

VEL_ONLY = 0b0000_1111_1100_0111
print("--- 2 m/s north at 5 Hz for 8 s, then silence")
t0 = time.time(); last = 0
while time.time() - t0 < 8:
    if state["mode"] != "GUIDED":
        print("pilot took over"); break
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, L.MAV_FRAME_LOCAL_NED,
                                             VEL_ONLY, 0, 0, 0, 2.0, 0, 0, 0, 0, 0, 0, 0)
    last = time.time(); pump(0.2)
print(f"speed at last setpoint: {state['v']:.2f} m/s")
t_dec = t_stop = None; trace = []
while time.time() - last < 10:
    pump(0.1); dt = time.time() - last; trace.append((round(dt, 2), round(state["v"], 2)))
    if t_dec is None and state["v"] < 1.8: t_dec = dt
    if t_stop is None and state["v"] < 0.2: t_stop = dt
    if t_stop and dt > t_stop + 1: break
open("guided_timeout_trace.csv", "w").write("t_s,v_ms\n" + "".join(f"{a},{b}\n" for a, b in trace))
print("t after last setpoint, s : " + " ".join(f"{a:4.1f}" for a, _ in trace[4::5]))
print("ground speed, m/s        : " + " ".join(f"{b:4.2f}" for _, b in trace[4::5]))
print(f"speed < 1.8 m/s after {t_dec:.1f} s; < 0.2 m/s after {t_stop:.1f} s from the last setpoint; mode={state['mode']}")
print("--- pilot takeover: GCS (sysid 255, port 14651) switches to LOITER 3 s into a new velocity stream")
import threading
def gcs():
    g = mavutil.mavlink_connection("udpin:127.0.0.1:14651", source_system=255, source_component=190)
    g.wait_heartbeat(timeout=10); time.sleep(3.0)
    g.set_mode(g.mode_mapping()["LOITER"]); gcs.t = time.time()
threading.Thread(target=gcs, daemon=True).start()
t0 = time.time(); sent_after = 0; gcs.t = None; seen = None
while time.time() - t0 < 10:
    pump(0.2)
    if state["mode"] != "GUIDED":
        seen = seen or time.time()
        if time.time() - seen > 2: break
        continue                                   # PILOT state: read only, send nothing
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, L.MAV_FRAME_LOCAL_NED,
                                             VEL_ONLY, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 0, 0)
    if gcs.t: sent_after += 1
print(f"mode {state['mode']} seen {seen - gcs.t:.2f} s after the GCS command; setpoints sent after it: {sent_after}")
m.set_mode(m.mode_mapping()["GUIDED"]); pump(1.0)
print("LAND ACK =", cmd(L.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0))
t0 = time.time()
while state["armed"] and time.time() - t0 < 60:
    pump(0.5)
print(f"disarmed after landing: {not state['armed']} ({time.time()-t0:.0f} s)")
```

### Шаг 3. Вывод прогона и как его читать
```text
FC heartbeat: sysid=1 compid=0 autopilot=3 type=2
--- param audit (4.7.2 names; None = no such parameter)
SERIAL1_PROTOCOL  = 2.0
SERIAL1_BAUD      = 57.0
SERIAL2_PROTOCOL  = 2.0
SERIAL2_BAUD      = 57.0
MAV1_EXT_STAT     = 0.0
MAV2_POSITION     = 0.0
MAV_SYSID         = 1.0
MAV_GCS_SYSID     = 255.0
SYSID_THISMAV     = None
SR0_EXT_STAT      = None
GUID_TIMEOUT      = 3.0
GUID_OPTIONS      = 0.0
FS_GCS_ENABLE     = 0.0
FS_GCS_TIMEOUT    = 5.0
DDS_ENABLE        = None
SET_MESSAGE_INTERVAL LOCAL_POSITION_NED 10 Hz ACK = 0
--- wait for EKF / GPS (pre-arm)
GUIDED + arm ACK=0 after 28.1 s, mode=GUIDED
takeoff ACK = 0
alt 9.5 m after 8.8 s
--- 2 m/s north at 5 Hz for 8 s, then silence
speed at last setpoint: 1.99 m/s
t after last setpoint, s :  0.7  1.2  1.7  2.2  2.7  3.2  3.7  4.2  4.7  5.2
ground speed, m/s        : 1.99 1.99 1.99 1.98 1.98 1.98 1.33 0.27 0.04 0.02
speed < 1.8 m/s after 3.5 s; < 0.2 m/s after 4.3 s from the last setpoint; mode=GUIDED
--- pilot takeover: GCS (sysid 255, port 14651) switches to LOITER 3 s into a new velocity stream
mode LOITER seen 0.08 s after the GCS command; setpoints sent after it: 0
LAND ACK = 0
disarmed after landing: True (13 s)
```

Читаем по блокам. Аудит: порты `SERIAL1`/`SERIAL2` — MAVLink2 на 57600, потоки канала нулевые, старые имена `SYSID_THISMAV` и `SR0_EXT_STAT` не существуют, `GUID_TIMEOUT` = 3.0 с, failsafe станции выключен, `DDS_ENABLE` нет — эта сборка SITL без AP_DDS (модуль ros2-ardupilot). `compid=0` в первой строке — pymavlink взял широковещательный адрес компонента; команды с ним ArduPilot принимает, что подтверждают ACK = 0. Арм прошёл через 28.1 с — столько SITL ждёт EKF и GPS; до этого переход в GUIDED (ему нужна позиция от EKF) или арм отклоняются, и цикл повторяет попытку раз в секунду. Тишина: при 1.99 м/с на момент последней цели скорость держится до 3.2 с, на 3.7 с уже 1.33 м/с, ниже 0.2 м/с — через 4.3 с. Телеметрия шла 10 Гц (в CSV значения меняются каждые 0.1 с: 3.21 с — ещё 1.98, 3.31 с — 1.96, 3.41 с — 1.89), поэтому начало торможения определено с точностью ±0.1 с: 3.2–3.3 с, то есть `GUID_TIMEOUT` плюс задержка телеметрии и шаг опроса скрипта (0.1 с). В первом прогоне без `--streamrate=-1` телеметрия шла 4 Гц, и та же граница размывалась до 3.0–3.4 с. Перехват: станция переключила LOITER, скрипт увидел новый режим в HEARTBEAT через 0.08 с и не отправил после этого ни одной цели.

{{diagram:chart-ap-guided-silence-stop|Скорость держится все 3 с GUID_TIMEOUT после последней цели и падает до нуля примерно за секунду торможения: остановка < 0.2 м/с — через 4.3 с.}}

### Шаг 4. Автомат на фейковом соединении
Дописать переходы из таблицы и тест: фейк отдаёт HEARTBEAT с режимом LOITER посреди TASK — автомат должен перейти в PILOT и не отправить больше ни одной цели. Второй тест: высота не растёт 20 с после взлёта — автомат командует LAND. Оба теста — в CI, как в стартере `examples/sitl-pymavlink`.

### Шаг 5. Capstone-каркас
Собери из модулей трека: Raspberry Pi с маршрутизатором → сервис на Python → GUIDED-логика (например, «облететь точку интереса по кругу и вернуться»), ESP32 с индикацией состояния. Критерий готовности: сценарий работает в SITL, документирован протокол и поведение при отказе companion, реальный полёт — только с геозоной и пилотом.

### Переход на реальное железо
Провод: TELEM2 FC ↔ UART companion (TX→RX, RX→TX, GND), `SERIAL2_PROTOCOL = 2`, `SERIAL2_BAUD = 921`, `BRD_SER2_RTSCTS = 0` (или 1 с разведёнными RTS/CTS); перезагрузка FC. Companion — от своего BEC 5 В. Порядок с критериями и условиями прерывания:

1. **Стол, пропеллеры сняты, FC и companion от батареи.** Запустить скрипт до блока «wait for EKF» (арм закомментирован). Приёмка: аудит печатает те же значения, что ты выставил; `MAV3_*` (или твой номер канала) — нули, если не прописывал; запрос `SET_MESSAGE_INTERVAL` даёт ACK = 0 и LOCAL_POSITION_NED идёт 10 Гц ± 1 Гц (посчитать за 10 с); если вышло ~4 Гц — маршрутизатор (MAVProxy без `--streamrate=-1` или наземная станция) перезапросил потоки и сбросил интервал. Прерывание: потери пакетов на канале > 1 % по счётчику seq — снизить скорость или укоротить провод.
2. **Стол, пропеллеры сняты, арм.** GUIDED и арм с проверкой ACK, без взлёта: в ArduCopter без пропеллеров моторы раскрутятся до холостых — так и должно быть. Приёмка: ACK = 0, режим GUIDED в HEARTBEAT. Прерывание: любой ACK ≠ 0 — читать `STATUSTEXT` «PreArm: …», не обходить.
3. **Поле, пропеллеры, пилот с пультом, тумблер LOITER/RTL, геозона.** Взлёт 10 м, цель по скорости 1 м/с на 3 с и тишина. Приёмка: торможение начинается через `GUID_TIMEOUT` ± 0.5 с по логу DataFlash (цель — сообщение `GUIP`, отработка — `PSCN`/`PSCE`), аппарат висит; после переключения пилотом в LOITER companion не шлёт целей (tlog маршрутизатора). Прерывание: пилот забирает управление при любом движении не в ту сторону (знак оси, кадр) — разбор на земле.

### Что должно получиться и что записать
- **Аудит.** Таблица из 15 параметров совпадает с выводом шага 3 (в SITL) или с тем, что ты выставил (на железе); старые имена 4.6 отвечают None.
- **Скорость и таймаут.** Цели `VEL_ONLY` шлются 5 Гц. После тишины скорость держится ~3 с (`GUID_TIMEOUT`) и падает до < 0.2 м/с примерно за секунду торможения: в прогоне 3.2–3.3 с до начала спада и 4.3 с до остановки. Сохрани CSV `guided_timeout_trace.csv`.
- **Смена режима пилотом.** Станция переключает LOITER посреди потока: скрипт видит режим по `HEARTBEAT.custom_mode` за доли секунды (в прогоне 0.08 с) и не отправляет больше ни одной цели — счётчик `setpoints sent after it` = 0.
- **Позиция (расширение).** Цель `SET_POSITION_TARGET_LOCAL_NED` с маской `0b0000_1111_1111_1000` (только x, y, z) на (20, 0, −10): аппарат летит в точку 20 м к северу на высоте 10 м и висит там без потока целей — у позиционной цели нет таймаута. Запиши время прилёта и ошибку позиции по `LOCAL_POSITION_NED`.
- **Геозона (расширение).** `FENCE_ENABLE = 1`, тип — высота и круг, радиус 50 м, действие RTL. Цель за пределами круга отвергается или аппарат долетает до границы и уходит в RTL; сохрани лог — это доказательство, что защита работает и без твоего кода.

Самопроверка: лабораторная выполнена, когда (SITL) аудит показывает `SERIAL1/2_PROTOCOL = 2`, `SERIAL1/2_BAUD = 57`, `MAV1_EXT_STAT = 0`, `MAV_SYSID = 1`, `MAV_GCS_SYSID = 255`, `GUID_TIMEOUT = 3.0`, а `SYSID_THISMAV`, `SR0_EXT_STAT` — None; `SET_MESSAGE_INTERVAL`, арм, взлёт и посадка дают ACK = 0; после последней цели 2 м/с скорость не ниже 1.9 м/с до 3.0 с и ниже 0.2 м/с не позже 5.0 с; LOCAL_POSITION_NED в CSV меняется с шагом 0.1 с (10 Гц); после переключения LOITER станцией скрипт отправил 0 целей; оба теста автомата на фейковом соединении (шаг 4) проходят. Расширения засчитывай себе отдельно: позиционная цель — прилёт в точку (20, 0, −10) с ошибкой < 1 м и зависание без потока; геозона — цель за кругом 50 м отвергнута или закончилась RTL. На железе — три критерия приёмки из предыдущего подраздела.

**Эталон для самопроверки.** Верный результат совпадает с выводом шага 3: спад скорости через 3.2–3.3 с, стоп через ~4.3 с, после смены режима пилотом companion молчит. Типичные неверные: (1) LOCAL_POSITION_NED приходит ~4 Гц вместо 10 Гц — MAVProxy запущен без `--streamrate=-1` и своими REQUEST_DATA_STREAM сбросил интервал; (2) скрипт висит на «wait for EKF» больше 90 с, а в SITL всё готово — не получен ни один HEARTBEAT с режимом: потоки и маршрутизатор не настроены или скрипт слушает не тот UDP-порт; (3) аппарат дёргается и зависает, пока скрипт ещё работает, — пауза между целями превысила `GUID_TIMEOUT` (3 с): держи частоту не ниже 2 Гц; (4) после тишины аппарат не останавливается, а долетает куда-то и висит — последняя цель была позиционной, у неё таймаута нет; (5) аппарат уходит не туда по высоте — перепутан знак Z (в LOCAL_NED ось Z вниз, высота 10 м — это z = −10) или в `type_mask` замаскировано не то поле.

## diagnostics
- **Симптом:** аппарат не реагирует на цели
  - Возможная причина: не GUIDED, не заармлен, `type_mask` игнорирует нужные поля.
  - Что сделать: проверить режим и арм в heartbeat, маску, `STATUSTEXT`.
- **Симптом:** летит вверх вместо вниз (или наоборот)
  - Возможная причина: знак Z в NED.
  - Что сделать: Z вниз положительный; подъём — отрицательное Z.
- **Симптом:** через пару секунд зависает, хотя команда была
  - Возможная причина: цель по скорости отправлена один раз, сработал таймаут.
  - Что сделать: слать регулярно (5–10 Гц).
- **Симптом:** останавливается на границе, не долетая до цели
  - Возможная причина: геозона или ограничения `WP_*`.
  - Что сделать: проверить `FENCE_*` и сообщения FC — это защита, а не баг.
- **Симптом:** скрипт companion получает только HEARTBEAT, позиции и режима нет
  - Возможная причина: ArduCopter 4.7 — потоки `MAVn_*` по умолчанию 0; скрипт слушает порт напрямую, без станции, которая запросила бы потоки.
  - Что сделать: `MAV_CMD_SET_MESSAGE_INTERVAL` на нужные сообщения после каждого подключения или прописать `MAVn_*` своего канала (с перезагрузкой).
  - Что видно в логе: в tlog маршрутизатора от sysid 1 только HEARTBEAT раз в секунду.
- **Симптом:** после обновления на 4.7 «пропали» параметры `SR2_*`, `SYSID_THISMAV`, `SYSID_MYGCS`
  - Возможная причина: переименование в 4.7: `MAVn_*` (номер канала MAVLink, а не SERIAL), `MAV_SYSID`, `MAV_GCS_SYSID`.
  - Что сделать: искать новые имена; номер канала считать по порядку MAVLink-портов (консоль — MAV1).
- **Симптом:** случайные таймауты команд и миссий, потерянные пакеты при 50 Гц телеметрии
  - Возможная причина: порт companion на 57600 (умолчание SERIAL1/2), загрузка канала выше 50 %.
  - Что сделать: `SERIALn_BAUD = 921`, посчитать загрузку (байты кадра × частота), при 1500 — RTS/CTS.
- **Симптом:** companion замолчал посреди полёта, аппарат продолжил лететь к точке
  - Возможная причина: последняя цель — позиция, у неё нет `GUID_TIMEOUT`; часто причина тишины — просадка питания companion.
  - Что сделать: в режимах, где отказ companion должен останавливать аппарат, давать цели скорости; отдельный BEC; при необходимости — Lua-сторож по HEARTBEAT companion.
- **Симптом:** GCS failsafe не срабатывает, хотя наземная станция пропала, или срабатывает при живом companion
  - Возможная причина: путаница sysid: failsafe следит только за sysid из `MAV_GCS_SYSID`…`_HI`, heartbeat companion (sysid 1) его не сбрасывает; станция с нестандартным sysid вне диапазона.
  - Что сделать: проверить sysid станции и `MAV_GCS_SYSID`; companion оставить на sysid аппарата, compid 191.

## references
- Copter Commands in Guided Mode — ArduPilot Dev | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- MAVLink SET_POSITION_TARGET_LOCAL_NED (common.xml) | https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED | primary | A
- Guided Mode — ArduPilot Copter | https://ardupilot.org/copter/docs/ac2_guidedmode.html | primary | A
- ArduPilot Copter-4.7.2 — mode_guided.cpp (timeouts per target type) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/mode_guided.cpp | primary | A
- ArduPilot Copter-4.7.2 — AP_SerialManager.cpp (SERIALn_PROTOCOL/BAUD, defaults) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_SerialManager/AP_SerialManager.cpp | primary | A
- ArduPilot Copter-4.7.2 — GCS_MAVLink_Parameters.cpp (MAVn_* streams, options) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp | primary | A
- ArduPilot Copter-4.7.2 — GCS_Common.cpp (own-sysid acceptance, GCS heartbeat) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/GCS_MAVLink/GCS_Common.cpp | primary | A
- MAVProxy | https://ardupilot.org/mavproxy/ | primary | A

## checklist
- Все цели сначала в SITL
- Знак Z в NED проверен
- Цели по скорости шлются регулярно, таймаут проверен намеренно
- Код уважает смену режима пилотом
- Геозона включена, пилот с тумблером на LOITER/RTL
- Поведение при отказе companion задокументировано
- Порт companion: MAVLink2, 921, RTS/CTS по факту разводки; номер канала `MAVn` посчитан
- Потоки запрошены самим companion (`SET_MESSAGE_INTERVAL`), не надеюсь на станцию
- Companion на sysid аппарата, compid 191; GCS failsafe настроен на станцию
- Companion питается от своего BEC, сервис под сторожем, ожидание FC с таймаутом
