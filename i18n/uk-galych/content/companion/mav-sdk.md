---
id: mav-sdk
title: "Бібліотеки над MAVLink: pymavlink, MAVSDK, MAVROS — шо й коли"
level: L3
readingTime: 40 хв
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - MAVSDK
  - pymavlink
  - MAVROS
  - async
  - архітектура
related:
  - mav-services
  - px4-ros2
  - ap-companion
next:
  - per-tracking
source: content/companion/mav-sdk.md
source_hash: 1c170941d38e
---

## summary
Після чотирьох модулів «по проводу» вже можна вибирати інструмент свідомо. pymavlink — прямий доступ до кожного повідомлення; MAVSDK — готові дії (`arm`, `takeoff`, `mission.upload`, offboard) поверх тих самих мікросервісів, асинхронний API і сервер на C++; MAVROS — міст MAVLink ↔ ROS; DroneKit — історичний, ніхто його вже не підтримує. Модуль порівнює їх за шарами, показує одну й ту саму місію в pymavlink і MAVSDK, розбирає асинхронну модель MAVSDK (підписки, скасування, таймаути) і шо ся діє при обриві зв'язку на кожному рівні. Лабораторна: місія й offboard-політ через MAVSDK у SITL з перевіркою, як воно ся поводить при розриві каналу.

## theory
### Шари
| Шар | Що дає | Чого не дає | Коли брати |
|---|---|---|---|
| Сирий протокол (mav-protocol) | усе | нічого готового | драйвер на МК, власний діалект, налагодження |
| **pymavlink** | кодек, з'єднання, `recv_match`, tlog | логіку діалогів (місії, ACK, повтори — самостійно) | скрипти, аналіз логів, тести, нестандартні повідомлення |
| **MAVSDK** (C++, Python, …) | дії й мікросервіси: action, telemetry, mission, offboard, param, ftp, camera, gimbal | екзотичні повідомлення прошивки (через `mavlink_passthrough` можна) | застосунки на companion, автотести польотів |
| **MAVROS** | MAVLink ↔ топіки/сервіси ROS 1/2, TF, setpoints | незалежність від ROS; накладні витрати | система на ROS з ArduPilot; PX4 + ROS 2 — краще uXRCE-DDS (модуль px4-ros2) |
| DroneKit-Python | — | не розвивається, проблеми із сучасним Python і прошивками | лише читання старого коду |

Всі верхні шари реалізують ті самі діалоги, шо ти писав руками: `mission.upload_mission()` усередині — то MISSION_COUNT/REQUEST_INT/ITEM_INT/ACK з повторами. Розуміти нижній шар треба, аби читати tlog, коли верхній шар каже «timeout».

### MAVSDK: як він є влаштований
MAVSDK — ядро на C++; Python-пакет `mavsdk` запускає вбудований `mavsdk_server` (gRPC) і з ним говорить. Звідси: (1) API асинхронний (`asyncio`); (2) потоки телеметрії — асинхронні генератори; (3) помилки — винятки з кодом результату плагіна (`ActionError`, `MissionError`) — той самий зміст, шо `MAV_RESULT`.

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

Конструктор `MissionItem` міняється між версіями MAVSDK (додаються поля) — звіряйся з документацією встановленої версії; то нормальна плата за високий рівень.

{{diagram:mav-sdk-ap-startup-seq|Скрипт MAVSDK против ArduCopter 4.7 сначала просит потоки (по умолчанию их нет), потом ждёт здоровья из EKF_STATUS_REPORT, а при загрузке миссии теряет seq 0 под дом — отсюда пункт-подставка.}}

### Асинхронність без несподіванок
- **Підписки нескінченні**: `async for x in telemetry.position()` сам ся не скінчить. Вихід — `break` за умовою або окрема задача зі скасуванням.
- **Таймаути — твої**: «чекати, доки GPS ok» без `asyncio.wait_for(..., timeout)` зависне навіки на апараті без GPS.
- **Паралельні задачі**: телеметрія, логування й керування — окремі `asyncio.create_task`; помилка в задачі без `await` її результату губиться мовчки.
- **Одна система — один ґазда**: два процеси з MAVSDK на одному порту — два mavsdk_server з однаковими ідентифікаторами; розведи їх роутером і різними compid.

### Offboard і GUIDED
Високорівневе керування з companion: у PX4 — режим Offboard (MAVSDK `offboard.set_velocity_ned(...)`, потім `offboard.start()`; уставки треба слати без перерви > 2 Гц, бо інакше PX4 вийде з Offboard за таймаутом), в ArduPilot — GUIDED із `SET_POSITION_TARGET_LOCAL_NED` (MAVSDK offboard теж працює з ArduPilot через ті самі повідомлення; підтримка набору полів може відрізнятися). Правило безпеки з модуля comp-intro: companion радить, автопілот вирішує; коли companion мовчить, апарат мусить сам перейти в безпечну поведінку — і то ся перевіряє тестом, а не вірою.

### Шо ся діє при обриві зв'язку
| Рівень | Поведінка |
|---|---|
| pymavlink | `recv_match` повертає None за таймаутом; рішення — твоє |
| MAVSDK | `connection_state` → `is_connected = False` (за зникненням heartbeat, ~3 с); дії завершуються помилкою; offboard-уставки не доходять |
| Автопілот | GCS failsafe (якщо ввімкнений і зв'язок із GCS), вихід з Offboard/GUIDED за таймаутом уставок (PX4 `COM_OF_LOSS_T`, ArduPilot — `GUID_TIMEOUT` для уставок швидкості/прискорення) |

Проєктуй так, аби безпеку забезпечував нижній рівень (автопілот), а верхній — лиш відновлював роботу.

{{diagram:mav-offboard-loss-timeline|После kill -9 скрипта PX4 через 1 с выходит из Offboard, а ArduPilot ещё 3 с летит с прежней скоростью и только потом останавливается, оставаясь в GUIDED.}}

{{diagram:mav-sdk-layers|pymavlink, MAVSDK і MAVROS — різні рівні абстракції над одним і тим самим MAVLink.}}

## practice
### Крок 1. Одна місія, два інструменти
Завантаж одну й ту саму місію з 5 точок у PX4 SITL (або ArduPilot SITL) двічі: своїм клієнтом з mav-services (pymavlink) і через MAVSDK. Запиши tlog обох сеансів (MAVProxy або mavlink-router) і порівняй послідовності повідомлень: шо MAVSDK шле додатково (запити версій, інтервали, `MISSION_CLEAR_ALL`)?

### Крок 2. Політ за місією з прогресом
Скрипт вище: арм, місія, прогрес, RTL. Додай таймаути на кожне очікування й запис CSV телеметрії в окремій задачі.

### Крок 3. Offboard-квадрат
Швидкості NED по 5 с у чотири сторони в Offboard (PX4) або GUIDED (ArduPilot). Потім «вбий» скрипт посеред квадрата (`kill -9`) і зафіксуй за логом, через скільки й у який режим перейшов автопілот. Порівняй зі значенням параметра таймауту.

### Крок 4. Обрив каналу
Між SITL і скриптом постав `tc netem loss 100%` на 5 с під час місії. Шо зробив MAVSDK (`connection_state`), шо зробив автопілот, ци скрипт ся відновив після повернення зв'язку без перезапуску? Дороби скрипт, аби відновлювався.

Лабораторна зараховується, коли є порівняння tlog двох клієнтів, місія з прогресом і таймаутами, offboard-квадрат із тестом «вбитого» скрипта й сценарій обриву з відновленням.

### Крок 5. MAVSDK 4.2.1 проти ArduCopter 4.7.2 SITL (журнал прогону)
Детальний розбір прогону (п'ять пасток ArduPilot, розшифрована сира місія) — в російськім оригіналі. Встановлення, скрипт і його справжній вивід:

```bash
python3 -m venv venv && ./venv/bin/pip install mavsdk==4.2.1 pymavlink
./venv/bin/python -c "import mavsdk; print(mavsdk.__version__)"
# 4.2.1
./venv/bin/python -c "from mavsdk import System; System()"
# TypeError: System is not constructed directly, get it from Mavsdk instead. Since v4, the 'mavsdk' package
# is the native MAVSDK binding ... To keep the old API, install 'mavsdk-grpc' ...
```

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

## diagnostics
- **Симптом:** скрипт MAVSDK висить на старті
  - Можлива причина: очікування `health` без таймауту на апараті без GPS/home; не та адреса підключення (udpin проти udpout, версія синтаксису).
  - Що зробити: `asyncio.wait_for`; перевір адресу й версію MAVSDK.
- **Симптом:** PX4 зара ж виходить з Offboard
  - Можлива причина: уставки не йшли до `offboard.start()` або йдуть рідше за 2 Гц.
  - Що зробити: відправ початкову уставку до старту; окрема задача з частотою 10–20 Гц.
- **Симптом:** `upload_mission` деколи падає з timeout по радіо
  - Можлива причина: втрати на повільному каналі, замало повторів за замовчуванням.
  - Що зробити: завантажуй швидким каналом/через companion; дивись у tlog — котрий пункт пропав.
- **Симптом:** два скрипти заважають один одному
  - Можлива причина: обидва займають один порт або один compid.
  - Що зробити: роутер з окремими endpoints, різні compid.

## references
- MAVSDK — Guide and Python API | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVSDK-Python (source, examples) | https://github.com/mavlink/MAVSDK-Python | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- PX4 — Offboard mode (timeouts, COM_OF_LOSS_T) | https://docs.px4.io/main/en/flight_modes/offboard.html | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- Вибираю шар (сирий протокол, pymavlink, MAVSDK, MAVROS) під задачу й пояснюю, чого саме той
- Розумію архітектуру MAVSDK (сервер, gRPC, async) і де шукати помилку
- Пишу асинхронний код із таймаутами й скасуванням задач
- Керую в Offboard/GUIDED і знаю таймаути уставок
- Перевіряю, як система ся поводить при обриві зв'язку й «смерті» скрипта
