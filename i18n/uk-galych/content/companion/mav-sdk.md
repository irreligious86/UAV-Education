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
from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan

async def main():
    drone = System()
    await drone.connect(system_address="udpin://0.0.0.0:14540")    # older releases: "udp://:14540"
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            break
    items = [MissionItem(lat, lon, 20, 5, True, float("nan"), float("nan"),
                         MissionItem.CameraAction.NONE, float("nan"), float("nan"),
                         float("nan"), float("nan"), float("nan"), MissionItem.VehicleAction.NONE)
             for lat, lon in [(47.3978, 8.5456), (47.3982, 8.5460), (47.3980, 8.5465)]]
    await drone.mission.upload_mission(MissionPlan(items))
    await drone.action.arm()
    await drone.mission.start_mission()
    async for p in drone.mission.mission_progress():
        print(f"{p.current}/{p.total}")
        if p.current == p.total:
            break
    await drone.action.return_to_launch()

asyncio.run(main())
```

Конструктор `MissionItem` міняється між версіями MAVSDK (додаються поля) — звіряйся з документацією встановленої версії; то нормальна плата за високий рівень.

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
