---
id: mav-sdk
title: "Библиотеки над MAVLink: pymavlink, MAVSDK, MAVROS — что и когда"
level: L3
readingTime: 40 мин
firmware: ArduPilot · PX4
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
После четырёх модулей «по проводу» можно выбирать инструмент осознанно. pymavlink — прямой доступ к каждому сообщению; MAVSDK — готовые действия (`arm`, `takeoff`, `mission.upload`, offboard) поверх тех же микросервисов, асинхронный API и сервер на C++; MAVROS — мост MAVLink ↔ ROS; DroneKit — исторический, не поддерживается. Модуль сравнивает их по слоям, показывает одну и ту же миссию в pymavlink и MAVSDK, разбирает асинхронную модель MAVSDK (подписки, отмена, таймауты) и что происходит при обрыве связи на каждом уровне. Лабораторная: миссия и offboard-полёт через MAVSDK в SITL с проверкой поведения при разрыве канала.

## theory
### Слои
| Слой | Что даёт | Чего не даёт | Когда брать |
|---|---|---|---|
| Сырой протокол (mav-protocol) | всё | ничего готового | драйвер на МК, свой диалект, отладка |
| **pymavlink** | кодек, соединения, `recv_match`, tlog | логику диалогов (миссии, ACK, повторы — сами) | скрипты, анализ логов, тесты, нестандартные сообщения |
| **MAVSDK** (C++, Python, …) | действия и микросервисы: action, telemetry, mission, offboard, param, ftp, camera, gimbal | экзотические сообщения прошивки (через `mavlink_passthrough` можно) | приложения на companion, автотесты полётов |
| **MAVROS** | MAVLink ↔ топики/сервисы ROS 1/2, TF, setpoints | ROS-независимость; накладные расходы | система на ROS с ArduPilot; PX4 + ROS 2 — предпочтительно uXRCE-DDS (модуль px4-ros2) |
| DroneKit-Python | — | не развивается, проблемы с современным Python и прошивками | только чтение старого кода |

Все верхние слои реализуют те же диалоги, что вы писали руками: `mission.upload_mission()` внутри — это MISSION_COUNT/REQUEST_INT/ITEM_INT/ACK с повторами. Понимание нижнего слоя нужно, чтобы читать tlog, когда верхний слой говорит «timeout».

### MAVSDK: как устроен
MAVSDK — C++-ядро; Python-пакет `mavsdk` запускает встроенный `mavsdk_server` (gRPC) и общается с ним. Отсюда: (1) API асинхронный (`asyncio`); (2) потоки телеметрии — асинхронные генераторы; (3) ошибки — исключения с кодом результата плагина (`ActionError`, `MissionError`) — тот же смысл, что `MAV_RESULT`.

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

Конструктор `MissionItem` меняется между версиями MAVSDK (добавляются поля) — сверяйтесь с документацией установленной версии; это нормальная плата за высокий уровень.

### Асинхронность без сюрпризов
- **Подписки бесконечны**: `async for x in telemetry.position()` не закончится сам. Выход — `break` по условию или отдельная задача с отменой.
- **Таймауты — ваши**: «ждать, пока GPS ok» без `asyncio.wait_for(..., timeout)` зависнет навсегда на аппарате без GPS.
- **Параллельные задачи**: телеметрия, логирование и управление — отдельные `asyncio.create_task`; ошибка в задаче без `await` её результата теряется молча.
- **Одна система — один владелец**: два процесса с MAVSDK на одном порту — два mavsdk_server с одинаковыми идентификаторами; разведите их роутером и разными compid.

### Offboard и GUIDED
Высокоуровневое управление с companion: в PX4 — режим Offboard (MAVSDK `offboard.set_velocity_ned(...)`, затем `offboard.start()`; уставки нужно слать непрерывно > 2 Гц, иначе PX4 выйдет из Offboard по таймауту), в ArduPilot — GUIDED с `SET_POSITION_TARGET_LOCAL_NED` (MAVSDK offboard тоже работает с ArduPilot через те же сообщения; поддержка набора полей может отличаться). Правило безопасности из модуля comp-intro: companion советует, автопилот решает; при молчании companion аппарат обязан перейти в безопасное поведение сам — это проверяется тестом, а не верой.

### Что происходит при обрыве связи
| Уровень | Поведение |
|---|---|
| pymavlink | `recv_match` возвращает None по таймауту; решение — ваше |
| MAVSDK | `connection_state` → `is_connected = False` (по пропаже heartbeat, ~3 с); действия завершаются ошибкой; offboard-уставки не доходят |
| Автопилот | GCS failsafe (если включён и связь с GCS), выход из Offboard/GUIDED по таймауту уставок (PX4 `COM_OF_LOSS_T`, ArduPilot — `GUID_TIMEOUT` для уставок скорости/ускорения) |

Проектируйте так, чтобы безопасность обеспечивал нижний уровень (автопилот), а верхний — только восстанавливал работу.

{{diagram:mav-sdk-layers|pymavlink, MAVSDK и MAVROS — разные уровни абстракции над одним и тем же MAVLink.}}

## practice
### Шаг 1. Одна миссия, два инструмента
Загрузите одну и ту же миссию из 5 точек в PX4 SITL (или ArduPilot SITL) дважды: своим клиентом из mav-services (pymavlink) и через MAVSDK. Запишите tlog обоих сеансов (MAVProxy или mavlink-router) и сравните последовательности сообщений: что MAVSDK шлёт дополнительно (запросы версий, интервалы, `MISSION_CLEAR_ALL`)?

### Шаг 2. Полёт по миссии с прогрессом
Скрипт выше: арм, миссия, прогресс, RTL. Добавьте таймауты на каждом ожидании и запись CSV телеметрии в отдельной задаче.

### Шаг 3. Offboard-квадрат
Скорости NED по 5 с в четыре стороны в Offboard (PX4) или GUIDED (ArduPilot). Затем «убейте» скрипт посреди квадрата (`kill -9`) и зафиксируйте по логу, через сколько и в какой режим перешёл автопилот. Сравните со значением параметра таймаута.

### Шаг 4. Обрыв канала
Между SITL и скриптом поставьте `tc netem loss 100%` на 5 с во время миссии. Что сделал MAVSDK (`connection_state`), что сделал автопилот, восстановился ли скрипт после возврата связи без перезапуска? Доработайте скрипт, чтобы восстанавливался.

Лабораторная засчитывается, когда есть сравнение tlog двух клиентов, миссия с прогрессом и таймаутами, offboard-квадрат с тестом «убитого» скрипта и сценарий обрыва с восстановлением.

## diagnostics
- **Симптом:** скрипт MAVSDK висит на старте
  - Возможная причина: ожидание `health` без таймаута на аппарате без GPS/home; не тот адрес подключения (udpin против udpout, версия синтаксиса).
  - Что сделать: `asyncio.wait_for`; проверить адрес и версию MAVSDK.
- **Симптом:** PX4 сразу выходит из Offboard
  - Возможная причина: уставки не шли до `offboard.start()` или идут реже 2 Гц.
  - Что сделать: отправить начальную уставку до старта; отдельная задача с частотой 10–20 Гц.
- **Симптом:** `upload_mission` иногда падает с timeout по радио
  - Возможная причина: потери на медленном канале, мало повторов по умолчанию.
  - Что сделать: загружать по быстрому каналу/через companion; смотреть tlog — какой пункт потерян.
- **Симптом:** два скрипта мешают друг другу
  - Возможная причина: оба занимают один порт или один compid.
  - Что сделать: роутер с отдельными endpoints, разные compid.

## references
- MAVSDK — Guide and Python API | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVSDK-Python (source, examples) | https://github.com/mavlink/MAVSDK-Python | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- PX4 — Offboard mode (timeouts, COM_OF_LOSS_T) | https://docs.px4.io/main/en/flight_modes/offboard.html | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- Выбираю слой (сырой протокол, pymavlink, MAVSDK, MAVROS) под задачу и объясняю почему
- Понимаю архитектуру MAVSDK (сервер, gRPC, async) и где искать ошибку
- Пишу асинхронный код с таймаутами и отменой задач
- Управляю в Offboard/GUIDED и знаю таймауты уставок
- Проверяю поведение системы при обрыве связи и «смерти» скрипта
