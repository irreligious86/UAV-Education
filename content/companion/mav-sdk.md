---
id: mav-sdk
title: "Библиотеки над MAVLink: pymavlink, MAVSDK, MAVROS — что и когда"
level: L3
readingTime: 55 мин
firmware: ArduPilot 4.7 (сверено с 4.7.3; лабораторная снята на SITL 4.7.2) · PX4 1.18 (параметры сверены с v1.18.0) · MAVSDK 4.2.1 · pymavlink 2.4.50
status: published
added: 2026-11-08
tags:
  - MAVSDK
  - pymavlink
  - MAVROS
  - async
  - архитектура
related:
  - mav-services
  - px4-ros2
  - ap-companion
next:
  - per-tracking
---

## summary
После четырёх модулей «по проводу» можно выбирать инструмент осознанно. pymavlink — прямой доступ к каждому сообщению; MAVSDK — готовые действия (`arm`, `takeoff`, `upload_mission`, offboard) поверх тех же микросервисов; MAVROS — мост MAVLink ↔ ROS; DroneKit — исторический, не поддерживается. С осени 2026 у MAVSDK для Python новая архитектура: пакет `mavsdk` 4.x — нативная привязка к C++-ядру без gRPC и без `mavsdk_server`, со своим API; старый код живёт в пакете `mavsdk-grpc`. Модуль сравнивает библиотеки по слоям, разбирает асинхронную модель MAVSDK 4 (подписки, отмена, таймауты), пять ловушек связки MAVSDK + ArduPilot 4.7, найденных прогоном в SITL, и что происходит при обрыве связи на каждом уровне. Лабораторная: скрипт на MAVSDK 4.2.1 против ArduCopter 4.7.2 SITL — подключение, здоровье, миссия, взлёт в GUIDED, прогресс и RTL, с разбором сырого содержимого миссии.

## theory
### Слои
| Слой | Что даёт | Чего не даёт | Когда брать |
|---|---|---|---|
| Сырой протокол (mav-protocol) | всё | ничего готового | драйвер на МК, свой диалект, отладка |
| **pymavlink** | кодек, соединения, `recv_match`, tlog | логику диалогов (миссии, ACK, повторы — сами) | скрипты, анализ логов, тесты, нестандартные сообщения |
| **MAVSDK** (C++, Python, Kotlin, …) | действия и микросервисы: action, telemetry, mission, offboard, param, ftp, camera, gimbal | экзотические сообщения прошивки (через плагин `MavlinkDirect`; `MavlinkPassthrough` объявлен устаревшим) | приложения на companion, автотесты полётов |
| **MAVROS** | MAVLink ↔ топики/сервисы ROS 1/2, TF, setpoints | ROS-независимость; накладные расходы | система на ROS с ArduPilot; PX4 + ROS 2 — предпочтительно uXRCE-DDS (модуль px4-ros2) |
| DroneKit-Python | — | не развивается, проблемы с современным Python и прошивками | только чтение старого кода |

Все верхние слои реализуют те же диалоги, что ты писал руками: `upload_mission()` внутри — это MISSION_COUNT/REQUEST_INT/ITEM_INT/ACK с повторами. Понимание нижнего слоя нужно, чтобы читать tlog, когда верхний слой говорит «timeout» или, хуже, молча делает не то.

{{lesson:mav-services|Диалоги миссии, параметров и команд с ACK и повторами — то, что MAVSDK прячет внутри; без них tlog не прочитать.}}

### MAVSDK 4: нативная привязка вместо gRPC
До версии 3.x включительно `pip install mavsdk` ставил MAVSDK-Python: асинхронную обёртку, которая запускала встроенный процесс `mavsdk_server` и говорила с ним по gRPC. С MAVSDK v4 имя `mavsdk` на PyPI занял другой продукт — нативная привязка, которая через C-обёртку `libcmavsdk` вызывает C++-ядро прямо в процессе Python (ctypes). Выпуски на PyPI: 3.17.4 — 17.09.2026 (последний старого типа), 4.0.0 — 22.09.2026, 4.2.1 — 17.11.2026 (текущий на ноябрь 2026; ядро сообщает `MAVSDK v4.2.1`). Старый gRPC-клиент продолжает развиваться под именем `mavsdk-grpc` (импорт `mavsdk_grpc`, тоже 4.2.1).

Что из этого следует на практике:

- **Нет второго процесса.** Нет `mavsdk_server`, нет порта 50051, нет зависимости `grpcio`. Меньше движущихся частей на companion, но и меньше изоляции: падение ядра роняет процесс Python.
- **Два интерфейса из одного пакета.** `mavsdk` — синхронный API с колбэками, `mavsdk.asyncio` — асинхронный. Асинхронная обёртка выносит блокирующие вызовы в пул потоков (`run_in_executor`), а колбэки ядра приходят из его собственного потока и передаются в цикл событий через `call_soon_threadsafe` (вывод из кода пакета 4.2.1, `mavsdk/asyncio/plugins/*`).
- **Обнаружение систем отдельно от подключения.** `add_any_connection(url)` только открывает канал; аппарат появляется через `first_autopilot(timeout_s)` или `get_systems()`. Это важно, когда в сети больше одного аппарата.
- **Плагины создаются явно.** Было `drone.action.arm()`, стало `ActionAsync(drone).arm()`.
- **Подписка и разовое чтение разделены.** В gRPC-пакете `telemetry.position()` был бесконечным потоком; в 4.x поток — `subscribe_position()`, а `position()` возвращает последнее значение один раз. Перенесённый «как есть» цикл `async for p in telemetry.position()` упадёт.

Старый код не ломается молча: пакет 4.x перехватывает импорт старых модулей и вызов `System()` и печатает подсказку (проверено: `TypeError: System is not constructed directly, get it from Mavsdk instead…`). Три пути: заменить импорт на `import mavsdk_grpc as mavsdk` (ничего больше не трогать), закрепить `mavsdk<4` в `requirements.txt` (обновлений не будет), или переписать на нативный API — он выигрывает на companion без лишнего процесса и с синхронным вариантом для простых утилит.

| Было (gRPC, `mavsdk<4`) | Стало (`mavsdk.asyncio`, 4.x) |
|---|---|
| `drone = System()` | `sdk = Mavsdk(Configuration.create_with_component_type(ComponentType.GROUND_STATION))` |
| `await drone.connect(system_address=url)` | `await sdk.add_any_connection(url)` |
| неявно внутри `connect()` | `drone = await sdk.first_autopilot(timeout_s)` → `System` или `None` |
| `drone.core.connection_state()` | `drone.is_connected_state()` |
| `drone.action`, `drone.telemetry` | `ActionAsync(drone)`, `TelemetryAsync(drone)` |
| `async for p in drone.telemetry.position()` | `async for p in tel.subscribe_position()` |
| `e._result.result` в `ActionError` | `e.result` |

Тот же сценарий, что в старой редакции модуля (миссия из трёх точек, арм, старт, прогресс, RTL), на API 4.x:

```python
import asyncio
from mavsdk.asyncio import Mavsdk, Configuration, ComponentType
from mavsdk.asyncio.plugins.action import ActionAsync
from mavsdk.asyncio.plugins.telemetry import TelemetryAsync
from mavsdk.asyncio.plugins.mission import MissionAsync, MissionItem, MissionPlan

async def main():
    cfg = Configuration.create_with_component_type(ComponentType.GROUND_STATION)
    async with Mavsdk(cfg) as sdk:
        await sdk.add_any_connection("udpin://0.0.0.0:14540")      # older gRPC package: drone.connect(...)
        drone = await sdk.first_autopilot(timeout_s=10.0)
        if drone is None:
            raise SystemExit("no autopilot in 10 s")
        tel, act, mis = TelemetryAsync(drone), ActionAsync(drone), MissionAsync(drone)
        async def ready():
            async for h in tel.subscribe_health():
                if h.is_global_position_ok and h.is_home_position_ok:
                    return
        await asyncio.wait_for(ready(), 120)                        # never wait without a timeout
        items = [MissionItem(latitude_deg=lat, longitude_deg=lon, relative_altitude_m=20, speed_m_s=5,
                             is_fly_through=True, vehicle_action=MissionItem.VehicleAction.NONE)
                 for lat, lon in [(47.3978, 8.5456), (47.3982, 8.5460), (47.3980, 8.5465)]]
        await mis.upload_mission(MissionPlan(items))
        await act.arm()
        await mis.start_mission()
        async for p in mis.subscribe_mission_progress():
            print(f"{p.current}/{p.total}")
            if p.current == p.total:
                break
        await act.return_to_launch()

asyncio.run(main())
```

Конструктор `MissionItem` в 4.x принимает именованные аргументы со значениями по умолчанию (NaN для «не задано»), поэтому длинный позиционный вызов из gRPC-версии больше не нужен. Так выглядит путь для PX4; для ArduPilot этого кода недостаточно — следующий раздел.

### MAVSDK и ArduPilot 4.7: пять ловушек
MAVSDK исторически писали вокруг PX4, а ArduPilot поддерживают ветки `if (autopilot == ArduPilot)` в ядре. Прогон лабораторной этого модуля против ArduCopter 4.7.2 SITL показал пять мест, где «работает в примере» и «работает с ArduPilot» расходятся. Все пять — вывод из прогона, подтверждённый исходниками MAVSDK v4.2.1 и ArduPilot Copter-4.7.2.

**1. Потоки телеметрии по умолчанию выключены.** В 4.7 параметры частот потоков переехали из `SRn_*` в `MAVn_*` (`MAV1_EXT_STAT`, `MAV1_POSITION`, …), и для Copter их умолчания — 0 (`libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp`, блок `APM_BUILD_COPTER_OR_HELI`). Наземная станция сама запрашивает потоки, поэтому в Mission Planner всё «как раньше». Скрипт MAVSDK без запроса получает от ArduCopter почти только HEARTBEAT; первый прогон лабораторной без запросов простоял 120 с с `global_pos=False`. Лечится вызовами `set_rate_*` до подписки: `set_rate_health(2)` запрашивает SYS_STATUS и EKF_STATUS_REPORT, `set_rate_position(5)` — GLOBAL_POSITION_INT. Для сообщений, у которых нет своего `set_rate_*` (MISSION_CURRENT, от которого зависит прогресс миссии), — `MAV_CMD_SET_MESSAGE_INTERVAL` (511) через `MavlinkDirectAsync.send_command`. Запрос действует на тот канал, по которому пришёл.

**2. Здоровье позиции у ArduPilot — из EKF, а не из GPS.** Для ArduPilot `is_global_position_ok` вычисляется из флагов EKF_STATUS_REPORT: пока аппарат не заармлен, достаточно `EKF_POS_HORIZ_ABS` или предсказанной `EKF_PRED_POS_HORIZ_ABS`, после арма — только `EKF_POS_HORIZ_ABS` и не в режиме постоянной позиции (`telemetry_impl.cpp`, `process_ekf_status_report`). Это правильнее, чем флаг GPS в SYS_STATUS (ArduPilot ставит его, как только приёмник жив), но означает: без потока EKF_STATUS_REPORT флаг основан на GPS, а с ним — честно ждёт EKF. В прогоне `home=True` пришёл на 20.0 с, `armable` (бит `MAV_SYS_STATUS_PREARM_CHECK`) — на 23.5 с, `global_pos` — на 42.0 с, после «EKF3 IMU0 is using GPS».

**3. Пункт seq 0 — это дом.** ArduPilot хранит в элементе 0 миссии точку дома и затирает то, что туда загрузили. Плагин Mission отправляет первый `MissionItem` именно в seq 0, поэтому без пункта-подставки первая точка пропадает: в первом прогоне из трёх точек долетели две, а seq 0 при скачивании содержал координаты дома. Решение — первым пунктом класть подставку (например, копию первой точки) или работать через `MissionRaw` с явным домом.

**4. Скачивание миссии плагином Mission не поддерживается.** `download_mission()` на ArduPilot возвращает `UNSUPPORTED` (лог ядра: `Waypoint frame 0 not supported` — дом в seq 0 записан в кадре MAV_FRAME_GLOBAL). Сырой путь `MissionRawAsync(drone).download_mission()` работает и показывает правду: каждый `MissionItem` со скоростью превратился в два элемента — `MAV_CMD_NAV_WAYPOINT` (16) и `MAV_CMD_DO_CHANGE_SPEED` (178), поэтому 4 пункта плана стали 8 элементами. Неприятная деталь: после неудачного `download_mission()` плагин забыл загруженный план — прогресс показывал `-1/0`, хотя MISSION_CURRENT шёл; повторная загрузка вернула нормальный прогресс `1/4 … 4/4` (вывод из прогона).

**5. Режимы называются по-PX4-шному.** Телеметрия MAVSDK отдаёт `FlightMode` из словаря PX4: GUIDED у ArduCopter приходит как `OFFBOARD`, AUTO — как `MISSION`, STABILIZE — как `STABILIZED`, а `Hold` при переключении превращается в BRAKE (не LOITER: тот берёт вертикаль со стика и без пилота снижается; комментарий в `system_impl.cpp`). `action.arm()` армит в текущем режиме, а `action.takeoff()` для ArduPilot сам переключает в GUIDED и шлёт `MAV_CMD_NAV_TAKEOFF` с высотой из `set_takeoff_altitude()` (`action_impl.cpp`, `takeoff_async_apm`). Если аппарат стоит в AUTO, RTL или LAND, `arm()` сначала переключит его в Hold, то есть в BRAKE.

{{diagram:mav-sdk-ap-startup-seq|Скрипт MAVSDK против ArduCopter 4.7 сначала просит потоки (по умолчанию их нет), потом ждёт здоровья из EKF_STATUS_REPORT, а при загрузке миссии теряет seq 0 под дом — отсюда пункт-подставка.}}

### Асинхронность без сюрпризов
- **Подписки бесконечны**: `async for x in tel.subscribe_position()` не закончится сам. Выход — `break` по условию, `asyncio.wait_for` вокруг корутины с циклом или отдельная задача с отменой. При выходе из генератора обёртка 4.x сама отписывается в ядре (блок `finally` с `unsubscribe_*`).
- **Таймауты — твои**: «ждать, пока GPS ok» без `asyncio.wait_for(..., timeout)` зависнет навсегда на аппарате без GPS — или, как показал пункт 1 выше, на ArduPilot без запрошенных потоков.
- **Очередь не ограничена**: каждая подписка в обёртке 4.x — `asyncio.Queue()` без предела (вывод из кода пакета). Медленный потребитель потока 50 Гц не теряет данные, а копит их в памяти и обрабатывает всё более старые значения. Если нужен только последний отсчёт, читай его разовым методом (`await tel.position()`) или сбрасывай очередь сам.
- **Параллельные задачи**: телеметрия, логирование и управление — отдельные `asyncio.create_task`; ошибка в задаче без `await` её результата теряется молча.
- **Одна система — один владелец канала**: два процесса на одном UDP-порту или на одном TCP-порту SITL мешают друг другу (TCP-порт SITL принимает одного клиента: второй скрипт в прогоне получил `no autopilot in 10 s`). Разводи клиентов роутером и разными compid (`mav-routing`).

### Offboard и GUIDED
Высокоуровневое управление с companion: в PX4 — режим Offboard (`OffboardAsync.set_velocity_ned(...)`, затем `start()`; уставки нужно слать непрерывно чаще 2 Гц, иначе PX4 выйдет из Offboard по таймауту), в ArduPilot — GUIDED с `SET_POSITION_TARGET_LOCAL_NED` (плагин Offboard MAVSDK тоже работает с ArduPilot через те же сообщения, `FlightMode.OFFBOARD` для него и есть GUIDED; поддержка набора полей может отличаться). Правило безопасности из модуля comp-intro: companion советует, автопилот решает; при молчании companion аппарат обязан перейти в безопасное поведение сам — это проверяется тестом, а не верой.

{{lesson:ap-companion|Таймауты GUIDED по типу цели, параметры порта и замер остановки после молчания companion — на ArduPilot 4.7.2 SITL.}}

### Что происходит при обрыве связи
| Уровень | Поведение |
|---|---|
| pymavlink | `recv_match` возвращает None по таймауту; решение — твоё |
| MAVSDK 4.x | `is_connected_state()` выдаёт `False` после пропажи heartbeat автопилота; действия завершаются ошибкой; offboard-уставки не доходят |
| Автопилот | GCS failsafe (если включён и связь с GCS), PX4 выходит из Offboard через `COM_OF_LOSS_T` (умолчание 1 с) в режим `COM_OBL_RC_ACT` (умолчание 0 — Position; без пульта — действие `NAV_RCL_ACT`, умолчание 2 — Return); ArduPilot остаётся в GUIDED и через `GUID_TIMEOUT` (умолчание 3 с; только для уставок скорости, ускорения и углов) обнуляет уставку — при уставках скорости аппарат останавливается, при угловых выравнивается |

Проектируй так, чтобы безопасность обеспечивал нижний уровень (автопилот), а верхний — только восстанавливал работу.

{{diagram:mav-offboard-loss-timeline|После kill -9 скрипта PX4 через 1 с выходит из Offboard, а ArduPilot ещё 3 с летит с прежней скоростью и только потом останавливается, оставаясь в GUIDED.}}

{{diagram:mav-sdk-layers|pymavlink, MAVSDK и MAVROS — разные уровни абстракции над одним и тем же MAVLink.}}

### Справочник: пакеты, вызовы, версии
| Что | Значение (проверено) | Источник |
|---|---|---|
| `mavsdk` (PyPI) | 4.2.1, нативная привязка, `import mavsdk` / `mavsdk.asyncio` | PyPI, пакет 4.2.1 |
| `mavsdk-grpc` | 4.2.1, старый API, `import mavsdk_grpc as mavsdk` | PyPI; README MAVSDK v4.2.1 |
| последний `mavsdk` старого типа | 3.17.4 (`pip install "mavsdk<4"`) | PyPI |
| `pymavlink` | 2.4.50 | PyPI |
| URL соединений | `udpin://0.0.0.0:14540`, `tcpout://127.0.0.1:5760`, `serial:///dev/ttyUSB0:57600` | migration.md, docstring `add_any_connection`, прогон |
| `first_autopilot(timeout_s)` | `System` или `None`; 0 — проверить один раз, < 0 — ждать вечно | `mavsdk/asyncio/mavsdk.py` |
| `TelemetryAsync.set_rate_health(hz)` | SYS_STATUS (+ EKF_STATUS_REPORT для ArduPilot) | `telemetry_impl.cpp` |
| `MavlinkDirectAsync.send_command()` | COMMAND_LONG/INT из JSON, ждёт COMMAND_ACK, сам повторяет | `mavlink_direct.py` |
| `MissionRawAsync.download_mission()` | список сырых элементов: `seq`, `frame`, `command`, `x`/`y` (градусы·10⁷), `z` | прогон |
| ArduCopter: потоки | `MAVn_RAW_SENS … MAVn_ADSB`, Copter по умолчанию 0; до 4.7 — `SRn_*` | `GCS_MAVLink_Parameters.cpp` |
| ArduCopter: свой sysid | `MAV_SYSID` (до 4.7 — `SYSID_THISMAV`) | прогон, `ArduCopter/Parameters.cpp` |

### Место в системе

- **Получает:** диалоги команд, параметров и миссий, которые SDK прячет внутри (`mav-services`); поток через роутер со своим compid (`mav-routing`); heartbeat автопилота и потоки телеметрии, которые на ArduPilot 4.7 нужно запросить самому.
- **Отдаёт:** действия и миссии автопилоту; уставки Offboard и GUIDED (`px4-ros2`, `ap-companion`); основу для контура слежения (`per-tracking`).
- **Если ошибиться здесь:** ожидание «GPS ok» без таймаута и без запроса потоков → приложение висит, уставки не идут, автопилот по своему таймауту выходит из Offboard (PX4) или останавливается в GUIDED (ArduPilot) (`ap-companion`). Миссия без пункта-подставки → на ArduPilot первая точка молча заменена домом, маршрут короче задуманного (`ap-missions`). Два процесса MAVSDK на одном порту → одинаковые идентификаторы, маршрутизация непредсказуема; разводят роутером и разными compid (`mav-routing`).

## practice
### Шаг 1. Установить MAVSDK 4 и убедиться, что это нужная версия
Отдельное виртуальное окружение, чтобы не смешать с `mavsdk<4` из чужих проектов. Проверка версии и того, что старый вызов `System()` даёт подсказку, а не загадочную ошибку:

```bash
python3 -m venv venv && ./venv/bin/pip install mavsdk==4.2.1 pymavlink
./venv/bin/python -c "import mavsdk; print(mavsdk.__version__)"
# 4.2.1
./venv/bin/python -c "from mavsdk import System; System()"
# TypeError: System is not constructed directly, get it from Mavsdk instead. Since v4, the 'mavsdk' package
# is the native MAVSDK binding ... To keep the old API, install 'mavsdk-grpc' ...
```

В установленном пакете нет каталога `bin` с `mavsdk_server`, только `lib/libcmavsdk.so` — так и должно быть в 4.x.

### Шаг 2. SITL и скрипт с таймаутом на каждом ожидании
ArduCopter 4.7.2 SITL (собранный `./waf copter` или через `sim_vehicle.py -v ArduCopter`) с параметрами `copter.parm`, дом — CMAC (−35.363261, 149.165230). В прогоне использован экземпляр `-I 7`, поэтому TCP-порт SERIAL0 — 5760 + 70 = 5830. Скрипт ниже прогонялся целиком; каждый шаг ожидания обёрнут в `first()` с таймаутом, потоки запрошены явно (ловушка 1), миссия — с пунктом-подставкой (ловушка 3), скачивание — через `MissionRaw` (ловушка 4).

```python
"""MAVSDK-Python 4.x lab against ArduCopter 4.7.2 SITL: connect, health, GUIDED arm, takeoff,
telemetry subscription, mission upload + progress, RTL. Every wait has a timeout."""
import asyncio, json, sys, time
from mavsdk import log_subscribe, LogLevel
from mavsdk.asyncio import Mavsdk, Configuration, ComponentType
from mavsdk.asyncio.plugins.action import ActionAsync
from mavsdk.asyncio.plugins.telemetry import TelemetryAsync, FlightMode
from mavsdk.asyncio.plugins.mission import MissionAsync, MissionItem, MissionPlan, MissionError
from mavsdk.asyncio.plugins.mission_raw import MissionRawAsync
from mavsdk.asyncio.plugins.mavlink_direct import MavlinkDirectAsync, MavlinkMessage

URL = sys.argv[1] if len(sys.argv) > 1 else "tcpout://127.0.0.1:5830"
T0 = time.monotonic()
# keep only warnings/errors of the C++ core; print autopilot STATUSTEXT ourselves
log_subscribe(lambda lvl, msg, f, l: lvl < LogLevel.WARN)
def log(*a): print(f"[{time.monotonic()-T0:6.1f} s]", *a, flush=True)

async def first(gen, cond, timeout, what):
    """First item of an endless subscription that satisfies cond, or TimeoutError."""
    async def run():
        async for x in gen:
            if cond(x):
                return x
    try:
        return await asyncio.wait_for(run(), timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"{what}: no result in {timeout} s") from None

async def main():
    cfg = Configuration.create_with_component_type(ComponentType.GROUND_STATION)
    async with Mavsdk(cfg) as sdk:
        log("MAVSDK", await sdk.version())
        await sdk.add_any_connection(URL)
        drone = await sdk.first_autopilot(timeout_s=10.0)
        if drone is None:
            raise TimeoutError("no autopilot in 10 s")
        log("autopilot:", (await drone.autopilot_type()).name, "sysid", await drone.get_system_id(),
            "vehicle:", (await drone.vehicle_type()).name)
        tel, act, mis = TelemetryAsync(drone), ActionAsync(drone), MissionAsync(drone)
        # ArduCopter 4.7: MAVn_* stream rates default to 0 -> ask for what we subscribe to
        await tel.set_rate_health(2.0)        # SYS_STATUS + EKF_STATUS_REPORT
        await tel.set_rate_position(5.0)      # GLOBAL_POSITION_INT
        # Mission progress comes from MISSION_CURRENT (id 42): no MAVSDK set_rate_* for it -> raw command
        ack = await MavlinkDirectAsync(drone).send_command(MavlinkMessage(
            message_name="COMMAND_LONG", system_id=245, component_id=190, target_system_id=1, target_component_id=1,
            fields_json=json.dumps({"target_system": 1, "target_component": 1, "command": 511,   # SET_MESSAGE_INTERVAL
                                    "param1": 42, "param2": 500000})))                       # 42 = MISSION_CURRENT, 2 Hz
        log("rates requested: health 2 Hz, position 5 Hz, MISSION_CURRENT 2 Hz -> ack", json.loads(ack.fields_json)["result"])
        last = None
        def ready(h):
            nonlocal last
            k = (h.is_global_position_ok, h.is_home_position_ok, h.is_armable)
            if k != last:
                log(f"health: global_pos={k[0]} home={k[1]} armable={k[2]}"); last = k
            return k[0] and k[1]
        await first(tel.subscribe_health(), ready, 120, "health")

        home = await tel.home()
        wp = lambda dn: MissionItem(latitude_deg=home.latitude_deg + dn / 111_320, longitude_deg=home.longitude_deg,
                                        relative_altitude_m=20, speed_m_s=5, is_fly_through=True,
                                        vehicle_action=MissionItem.VehicleAction.NONE)
        # ArduPilot keeps seq 0 for home and overwrites it: without a placeholder the first point is lost
        plan = MissionPlan([wp(0)] + [wp(dn) for dn in (40, 80, 120)])
        t = time.monotonic(); await mis.upload_mission(plan)
        log(f"mission uploaded: {len(plan.mission_items)} items in {time.monotonic()-t:.2f} s")
        try:
            await mis.download_mission()
        except MissionError as e:
            log("Mission.download_mission ->", e.result.name)   # ArduPilot item 0 = home
            await mis.upload_mission(plan)                       # the failed download dropped the plan: upload again
            log("re-uploaded after the failed download")
        raw = await MissionRawAsync(drone).download_mission()
        for it in raw:
            log(f"  raw seq={it.seq} frame={it.frame} cmd={it.command} x={it.x} y={it.y} z={it.z:.1f}")

        await act.set_takeoff_altitude(10.0)
        await act.arm(); log("armed in", FlightMode(await tel.flight_mode()).name)
        await act.takeoff(); log("takeoff accepted, mode now", FlightMode(await tel.flight_mode()).name, "(= ArduCopter GUIDED)")
        p = await first(tel.subscribe_position(), lambda p: p.relative_altitude_m > 9.0, 40, "climb to 9 m")
        log(f"altitude {p.relative_altitude_m:.1f} m reached")

        await mis.start_mission(); log("mission started, mode:", FlightMode(await tel.flight_mode()).name, "(= AUTO)")
        n = 0
        async def progress():
            async for pr in mis.subscribe_mission_progress():
                log(f"progress {pr.current}/{pr.total}")
                if pr.current == pr.total:
                    return
        async def pos_log():
            nonlocal n
            async for p in tel.subscribe_position():
                n += 1
        async def raw_current():
            async for msg in MavlinkDirectAsync(drone).subscribe_message("MISSION_CURRENT"):
                f = json.loads(msg.fields_json)
                if f["seq"] != getattr(raw_current, "seq", None):
                    raw_current.seq = f["seq"]; log(f"MISSION_CURRENT seq={f['seq']} total={f.get('total')} state={f.get('mission_state')}")
        logger = asyncio.create_task(pos_log()); rc = asyncio.create_task(raw_current())
        await asyncio.wait_for(progress(), 150); rc.cancel()
        logger.cancel()
        log(f"position samples received during mission: {n}")
        await act.return_to_launch(); log("RTL sent, mode:", FlightMode(await tel.flight_mode()).name)
        await first(tel.subscribe_armed(), lambda a: not a, 120, "disarm after RTL")
        log("landed and disarmed")

asyncio.run(main())
```

Вывод прогона (MAVSDK 4.2.1, ArduCopter 4.7.2 SITL, 25.11.2026; строка `[Error]` — лог ядра MAVSDK уровня ERROR, её пропускает фильтр):

```text
[   0.0 s] MAVSDK v4.2.1
[   0.9 s] autopilot: ARDUPILOT sysid 1 vehicle: MULTICOPTER
[   1.1 s] rates requested: health 2 Hz, position 5 Hz, MISSION_CURRENT 2 Hz -> ack 0
[   1.9 s] health: global_pos=False home=False armable=False
[  20.0 s] health: global_pos=False home=True armable=False
[  23.5 s] health: global_pos=False home=True armable=True
[  42.0 s] health: global_pos=True home=True armable=True
[  42.1 s] mission uploaded: 4 items in 0.09 s
[09:25:53|Error] Waypoint frame 0 not supported (mission_impl.cpp:709)
[  42.1 s] Mission.download_mission -> UNSUPPORTED
[  42.2 s] re-uploaded after the failed download
[  42.3 s]   raw seq=0 frame=0 cmd=16 x=-353632610 y=1491652299 z=584.1
[  42.3 s]   raw seq=1 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s]   raw seq=2 frame=3 cmd=16 x=-353629017 y=1491652299 z=20.0
[  42.3 s]   raw seq=3 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s]   raw seq=4 frame=3 cmd=16 x=-353625424 y=1491652299 z=20.0
[  42.3 s]   raw seq=5 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s]   raw seq=6 frame=3 cmd=16 x=-353621830 y=1491652299 z=20.0
[  42.3 s]   raw seq=7 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s] armed in STABILIZED
[  42.3 s] takeoff accepted, mode now OFFBOARD (= ArduCopter GUIDED)
[  50.8 s] altitude 9.2 m reached
[  50.8 s] mission started, mode: MISSION (= AUTO)
[  51.0 s] progress 1/4
[  51.0 s] MISSION_CURRENT seq=2 total=7 state=3
[  61.5 s] progress 2/4
[  61.5 s] MISSION_CURRENT seq=4 total=7 state=3
[  69.5 s] progress 3/4
[  69.5 s] MISSION_CURRENT seq=6 total=7 state=3
[  80.0 s] progress 4/4
[  80.0 s] position samples received during mission: 146
[  80.0 s] RTL sent, mode: RETURN_TO_LAUNCH
[ 137.0 s] landed and disarmed
```

### Шаг 3. Прочитать сырую миссию и прогресс
Разбери вывод, а не верь ему на слово. Координаты в сырых элементах — градусы·10⁷: seq 2 отличается от дома по широте на −353629017 − (−353632610) = 3593 единицы = 0.0003593°, это 3593·10⁻⁷·111 320 м ≈ 40.0 м к северу; seq 4 — 7186 единиц ≈ 80.0 м, seq 6 — 10 780 единиц ≈ 120.0 м. Пункт-подставка (0 м) лёг в seq 0 и был заменён домом: `frame=0` (MAV_FRAME_GLOBAL, высота AMSL 584.1 м), а все настоящие точки — `frame=3` (MAV_FRAME_GLOBAL_RELATIVE_ALT, 20 м над домом). Нечётные seq — `cmd=178` (DO_CHANGE_SPEED), их добавил MAVSDK из `speed_m_s=5`. MISSION_CURRENT показывает сырой seq (2, 4, 6) и `total=7` (8 элементов минус дом — так поле определено в common.xml), а плагин Mission — свой счёт пунктов плана (1/4 … 4/4); `state=3` — MISSION_STATE_ACTIVE. 146 отсчётов позиции за 80.0 − 50.8 = 29.2 с дают 5.0 Гц — ровно запрошенное `set_rate_position(5)`.

### Шаг 4. Расширение на своей машине: offboard и обрыв канала
Не прогонялось в этой редакции модуля, критерии — из теории. (а) Скорости NED по 5 с в четыре стороны через `OffboardAsync` (PX4: Offboard; ArduPilot: тот же GUIDED). Посреди квадрата `kill -9` скрипта и по логу — время до смены режима (PX4, сравни с `COM_OF_LOSS_T` = 1 с) или до остановки в GUIDED (ArduPilot; замер на SITL 4.7.2 в модуле ap-companion: спад скорости начинается через 3.2–3.3 с после последней цели при `GUID_TIMEOUT` = 3 с, остановка < 0.2 м/с — через 4.3 с). (б) Между SITL и скриптом `tc netem loss 100%` на 5 с во время миссии: что выдал `is_connected_state()`, что сделал автопилот, продолжил ли скрипт без перезапуска.

### Переход на реальное железо
Тот же скрипт на companion с адресом `serial:///dev/ttyAMA0:921600` или, лучше, `udpin://0.0.0.0:14540` за mavlink-router (модуль comp-raspberry). Порядок: пропеллеры сняты; запуск до шага `arm()` — проверить, что здоровье приходит и что потоки запрошены на этом канале (в Mission Planner MAVLink Inspector видны частоты, которые попросил скрипт); миссию загрузить и скачать обратно через `MissionRaw`, сверить координаты по методике шага 3. Пропеллеры ставятся только для полёта, который выполняет пилот с пультом и тумблером на LOITER/RTL, на высоте 10 м и с геозоной. Приёмка на железе: скачанная миссия совпадает с загруженной до 0.5 м по каждой точке; прогресс доходит до N/N; после RTL аппарат дизармится сам.

Самопроверка: лабораторная выполнена, когда (SITL) `mavsdk.__version__` = 4.2.1 и в пакете есть `lib/libcmavsdk.so`, но нет `mavsdk_server`; скрипт проходит до `landed and disarmed` без единого TimeoutError; в сырой миссии 2·N элементов для N пунктов со скоростью, seq 0 — дом с `frame=0`, а смещения точек по широте, пересчитанные по формуле Δ·10⁻⁷·111 320, совпадают с заданными 40/80/120 м с точностью ±0.5 м; прогресс плагина идёт 1/N … N/N, а MISSION_CURRENT — по чётным seq; частота отсчётов позиции = запрошенной ±10 %. На железе дополнительно выполнены три критерия приёмки из предыдущего подраздела.

**Эталон для самопроверки.** Верный прогон выглядит как вывод шага 2: здоровье за 40–45 с после старта SITL (EKF начинает использовать GPS), 8 сырых элементов для 4 пунктов, прогресс 1/4 … 4/4, 5 Гц позиции. Типичные неверные результаты: (1) `TimeoutError: health: no result in 120 s` при живом SITL — не вызваны `set_rate_health`/`set_rate_position`, потоки ArduCopter 4.7 по умолчанию 0; (2) из трёх точек маршрута облетаются две, а seq 0 содержит координаты дома — нет пункта-подставки; (3) прогресс `-1/0` при идущем MISSION_CURRENT — план «забыт» после неудачного `download_mission()`, его нужно загрузить снова; (4) `no autopilot in 10 s` при работающем SITL — TCP-порт уже занят другим клиентом.

## diagnostics
- **Симптом:** скрипт MAVSDK висит на старте или падает по таймауту здоровья
  - Возможная причина: на ArduPilot 4.7 не запрошены потоки (`MAVn_*` = 0 у Copter); ожидание `health` без таймаута на аппарате без GPS/home; не тот адрес подключения (udpin против udpout).
  - Что сделать: `set_rate_health`, `set_rate_position` до подписки; `asyncio.wait_for`; проверить адрес и версию MAVSDK.
- **Симптом:** `ModuleNotFoundError`/`ImportError: No module named 'mavsdk.action'` или `TypeError: System is not constructed directly`
  - Возможная причина: код под gRPC-пакет (`mavsdk<4`) запущен с `mavsdk` 4.x.
  - Что сделать: `import mavsdk_grpc as mavsdk` после `pip install mavsdk-grpc`, или `mavsdk<4` в requirements, или переписать по таблице соответствия.
- **Симптом:** на ArduPilot маршрут короче, первая точка пропала
  - Возможная причина: seq 0 занят домом, первый `MissionItem` затёрт.
  - Что сделать: пункт-подставка первым или `MissionRaw` с явным домом; проверять скачиванием через `MissionRaw`.
  - Что видно в логе: в скачанной миссии seq 0 с `frame=0` и координатами дома.
- **Симптом:** `download_mission()` → `UNSUPPORTED`, после этого прогресс `-1/0`
  - Возможная причина: плагин Mission не принимает дом в MAV_FRAME_GLOBAL; неудачное скачивание сбросило сохранённый план.
  - Что сделать: скачивать через `MissionRawAsync`, план загрузить заново.
- **Симптом:** PX4 сразу выходит из Offboard
  - Возможная причина: уставки не шли до `offboard.start()` или идут реже 2 Гц.
  - Что сделать: отправить начальную уставку до старта; отдельная задача с частотой 10–20 Гц.
- **Симптом:** `upload_mission` иногда падает с timeout по радио
  - Возможная причина: потери на медленном канале, мало повторов по умолчанию.
  - Что сделать: загружать по быстрому каналу/через companion; смотреть tlog — какой пункт потерян.
- **Симптом:** два скрипта мешают друг другу, второй не видит автопилот
  - Возможная причина: оба занимают один порт (TCP-порт SITL принимает одного клиента) или один compid.
  - Что сделать: роутер с отдельными endpoints, разные compid.

## references
- MAVSDK — Guide and Python API | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVSDK v4.2.1 — README (bindings, mavsdk-grpc) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/README.md | primary | A
- MAVSDK v4.2.1 — Migrating from MAVSDK-Python (docs source) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/docs/en/python/migration.md | primary | A
- MAVSDK v4.2.1 — telemetry_impl.cpp (ArduPilot health from EKF_STATUS_REPORT) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/cpp/src/mavsdk/plugins/telemetry/telemetry_impl.cpp | primary | A
- MAVSDK v4.2.1 — action_impl.cpp (takeoff on ArduPilot) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/cpp/src/mavsdk/plugins/action/action_impl.cpp | primary | A
- mavsdk on PyPI (release dates) | https://pypi.org/project/mavsdk/ | primary | A
- ArduPilot Copter-4.7.2 — GCS_MAVLink_Parameters.cpp (MAVn_* stream rates) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp | primary | A
- MAVSDK-Python (gRPC client, now mavsdk-grpc) | https://github.com/mavlink/MAVSDK-Python | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- PX4 — Offboard mode (timeouts, COM_OF_LOSS_T) | https://docs.px4.io/v1.17/en/flight_modes/offboard.html | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- Выбираю слой (сырой протокол, pymavlink, MAVSDK, MAVROS) под задачу и объясняю почему
- Знаю, какой пакет MAVSDK стоит (`mavsdk` 4.x нативный или `mavsdk-grpc`), и переношу код по таблице соответствия
- На ArduPilot 4.7 запрашиваю потоки, кладу пункт-подставку в seq 0, скачиваю миссию через MissionRaw
- Пишу асинхронный код с таймаутами и отменой задач, помню про неограниченные очереди подписок
- Управляю в Offboard/GUIDED и знаю таймауты уставок
- Проверяю поведение системы при обрыве связи и «смерти» скрипта
