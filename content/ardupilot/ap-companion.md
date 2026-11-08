---
id: ap-companion
title: "Companion + ArduPilot: управление из кода"
level: L3
readingTime: 30 мин
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - GUIDED
  - offboard
  - pymavlink
related:
  - comp-raspberry
  - ap-missions
next:
  - bf-custom
---

## summary
Режим GUIDED — дверь, через которую бортовой компьютер управляет аппаратом: «лети в точку», «держи скорость», «смотри туда». Модуль показывает, как из Python на companion задавать цели по позиции и скорости, как ArduPilot защищает себя от молчащего или спятившего companion и как построить цикл управления так, чтобы его можно было безопасно отлаживать в SITL. Итог — каркас для capstone трека: своя логика на борту.

## theory
### GUIDED и его таймауты
В GUIDED аппарат ждёт целей от внешнего источника. Цели бывают:

- **позиция** — `SET_POSITION_TARGET_GLOBAL_INT` (86) с координатами или `SET_POSITION_TARGET_LOCAL_NED` (84) в метрах относительно дома/аппарата;
- **скорость** — те же сообщения с битовой маской `type_mask`, которая говорит «игнорируй позицию, используй скорость»;
- **ориентация/тяга** — `SET_ATTITUDE_TARGET` для продвинутых случаев.

Цели по скорости действуют ограниченное время: если companion замолчал, ArduPilot через таймаут (порядка секунд, параметр `GUID_TIMEOUT`) переводит аппарат в зависание. Это защита, на которую надо опираться, а не обходить.

### Система координат
`LOCAL_NED`: X — север, Y — восток, Z — **вниз**. Подъём на 10 м — это Z = −10. Половина ошибок offboard-кода — знак оси Z. Для целей относительно носа аппарата есть `MAV_FRAME_BODY_OFFSET_NED`.

### Что проверяет FC
Геозона (`FENCE_*`), ограничения скорости и ускорения (`WPNAV_*`), батарейный failsafe, здоровье EKF. Companion может просить что угодно — выполнение всё равно в рамках параметров FC. Отсюда правило отладки: если аппарат «не слушается», сначала `STATUSTEXT`, потом параметры ограничений, и только потом свой код.

### Цикл управления
Хороший цикл companion:

1. Читать состояние (позиция, скорость, режим, арм) из телеметрии с заданной частотой.
2. Считать решение.
3. Отправлять цель **регулярно** (например, 5–10 Гц для скорости), даже если она не изменилась.
4. Проверять, что режим всё ещё GUIDED: пилот тумблером может забрать управление в любой момент, и код обязан это уважать.

### Безопасность при разработке
- Всё сначала в SITL. Тот же код, тот же порт, только адрес другой.
- Пилот с пультом и тумблером на LOITER/RTL — всегда, даже когда «точно работает».
- Геозона включена и проверена.
- Первые реальные тесты — только цели по позиции на малой высоте; скорость — потом.

### Пример: скорость в GUIDED (pymavlink)
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("udp:127.0.0.1:14551"); m.wait_heartbeat()
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
Проверки по порядку: (1) режим GUIDED (`HEARTBEAT.custom_mode`); (2) `type_mask` — не замаскирована ли скорость; (3) частота отправки ≥ 2 Гц (таймаут 3 с); (4) `WPNAV_SPEED`/`PSC_*` не ограничивают до нуля; (5) геозона не держит у границы; (6) `STATUSTEXT` — «EKF needs position» и т.п. В 80% случаев — (1) или (2).

## practice
### Шаг 1. Взлёт и цель по позиции (SITL)
```python
import time
from pymavlink import mavutil

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")  # on the drone: tcp:127.0.0.1:5760 via router
m.wait_heartbeat()

def ack(cmd):
    a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
    assert a and a.command == cmd and a.result == 0, f"command {cmd} failed: {a}"

m.set_mode(m.mode_mapping()["GUIDED"])
m.mav.command_long_send(m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
ack(400)
m.mav.command_long_send(m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
ack(22)
time.sleep(8)

# fly 20 m north, 0 east, stay at 10 m: LOCAL_NED, Z is DOWN
POS_ONLY = 0b0000_1111_1111_1000  # use x,y,z; ignore velocity, accel, yaw
m.mav.set_position_target_local_ned_send(
    0, m.target_system, m.target_component,
    mavutil.mavlink.MAV_FRAME_LOCAL_NED, POS_ONLY,
    20, 0, -10,  0, 0, 0,  0, 0, 0,  0, 0)
```

### Шаг 2. Цель по скорости, с регулярной отправкой
```python
VEL_ONLY = 0b0000_1111_1100_0111  # use vx,vy,vz; ignore position, accel, yaw
t_end = time.time() + 5
while time.time() < t_end:
    hb = m.recv_match(type="HEARTBEAT", blocking=False)
    if hb and m.mode_mapping_bynumber(hb.custom_mode) != "GUIDED":
        print("pilot took over, stop sending"); break
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED, VEL_ONLY,
        0, 0, 0,  1.0, 0, 0,  0, 0, 0,  0, 0)   # 1 m/s north
    time.sleep(0.2)                              # 5 Hz, inside GUID_TIMEOUT
```

Перестань слать — аппарат зависнет сам. Это и есть тест таймаута: выполни его намеренно.

### Шаг 3. Capstone-каркас
Собери из модулей трека: Raspberry Pi с маршрутизатором → сервис на Python → GUIDED-логика (например, «облететь точку интереса по кругу и вернуться»), ESP32 с индикацией состояния. Критерий сдачи: сценарий работает в SITL, документирован протокол и поведение при отказе companion, реальный полёт — только с геозоной и пилотом.

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
  - Возможная причина: геозона или ограничения `WPNAV_*`.
  - Что сделать: проверить `FENCE_*` и сообщения FC — это защита, а не баг.

## references
- Copter Commands in Guided Mode — ArduPilot Dev | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- MAVLink SET_POSITION_TARGET_LOCAL_NED (common.xml) | https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED | primary | A
- Guided Mode — ArduPilot Copter | https://ardupilot.org/copter/docs/ac2_guidedmode.html | primary | A

## checklist
- Все цели сначала в SITL
- Знак Z в NED проверен
- Цели по скорости шлются регулярно, таймаут проверен намеренно
- Код уважает смену режима пилотом
- Геозона включена, пилот с тумблером на LOITER/RTL
- Поведение при отказе companion задокументировано
