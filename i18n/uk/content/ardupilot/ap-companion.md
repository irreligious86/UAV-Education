---
id: ap-companion
title: "Companion + ArduPilot: керування з коду"
level: L3
readingTime: 30 хв
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
source: content/ardupilot/ap-companion.md
source_hash: ee44ca670ea8
---

## summary
Режим GUIDED — двері, через які бортовий комп'ютер керує апаратом: «лети в точку», «тримай швидкість», «дивись туди». Модуль показує, як із Python на companion задавати цілі за позицією і швидкістю, як ArduPilot захищає себе від companion, що замовк або збожеволів, і як побудувати цикл керування так, щоб його можна було безпечно налагоджувати в SITL. Підсумок — каркас для capstone треку: власна логіка на борту.

## theory
### GUIDED і його таймаути
У GUIDED апарат чекає цілей від зовнішнього джерела. Цілі бувають:

- **позиція** — `SET_POSITION_TARGET_GLOBAL_INT` (86) з координатами або `SET_POSITION_TARGET_LOCAL_NED` (84) у метрах відносно дому/апарата;
- **швидкість** — ті самі повідомлення з бітовою маскою `type_mask`, яка каже «ігноруй позицію, використовуй швидкість»;
- **орієнтація/тяга** — `SET_ATTITUDE_TARGET` для просунутих випадків.

Цілі за швидкістю діють обмежений час: якщо companion замовк, ArduPilot після таймауту (порядку секунд, параметр `GUID_TIMEOUT`) переводить апарат у зависання. Це захист, на який треба спиратися, а не обходити його.

### Система координат
`LOCAL_NED`: X — північ, Y — схід, Z — **вниз**. Підйом на 10 м — це Z = −10. Половина помилок offboard-коду — знак осі Z. Для цілей відносно носа апарата є `MAV_FRAME_BODY_OFFSET_NED`.

### Що перевіряє FC
Геозона (`FENCE_*`), обмеження швидкості й прискорення (`WP_*`, до 4.7 — `WPNAV_*`), батарейний failsafe, справність EKF. Companion може просити що завгодно — виконання все одно в межах параметрів FC. Звідси правило налагодження: якщо апарат «не слухається», спершу `STATUSTEXT`, потім параметри обмежень, і лише потім власний код.

### Цикл керування
Добрий цикл companion:

1. Читати стан (позиція, швидкість, режим, арм) із телеметрії із заданою частотою.
2. Обчислювати рішення.
3. Надсилати ціль **регулярно** (наприклад, 5–10 Гц для швидкості), навіть якщо вона не змінилася.
4. Перевіряти, що режим досі GUIDED: пілот тумблером може забрати керування будь-якої миті, і код зобов'язаний це поважати.

### Код companion як скінченний автомат
Скрипт «надіслав команду, поспав 10 секунд, надіслав наступну» працює в SITL і ламається в полі: команду не прийнято, пілот перемкнув режим, GPS зник. Надійна форма — автомат станів, де кожен перехід перевіряє умову і має таймаут:

| Стан | Що робить | Перехід далі | Якщо не вийшло |
|---|---|---|---|
| WAIT_READY | чекає GPS fix і EKF OK за телеметрією | готовність | чекати, нічого не надсилати |
| ARM_TAKEOFF | GUIDED, арм, `MAV_CMD_NAV_TAKEOFF`, чекає ACK і висоту ≥ 90 % цілі | висоту досягнуто | за 20 с немає висоти → LAND |
| TASK | надсилає цілі з частотою 5–10 Гц, перевіряє режим на кожній ітерації | завдання виконано | режим не GUIDED → PILOT |
| RETURN | `RTL` командою зміни режиму | дизарм | — |
| PILOT | **мовчить**, лише читає телеметрію | пілот повернув GUIDED і підтвердив | — |

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
Такий код легко тестувати: підміни `m` фейковим з'єднанням (як у `examples/mavlink/tests`) і перевір кожен рядок таблиці, зокрема «пілот забрав керування посеред TASK».

### Безпека під час розробки
- Усе спершу в SITL. Той самий код, той самий порт, лише інша адреса.
- Пілот із пультом і тумблером на LOITER/RTL — завжди, навіть коли «точно працює».
- Геозону ввімкнено й перевірено.
- Перші реальні тести — лише цілі за позицією на малій висоті; швидкість — потім.

### Приклад: швидкість у GUIDED (pymavlink)
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
Повний стартовий проєкт (квадрат, тест failsafe, CI) — `examples/sitl-pymavlink` у репозиторії курсу. `GUID_TIMEOUT` = 3.0 с за замовчуванням (діапазон 0.1–5); біти `GUID_OPTIONS`: 0 — дозволити арм із пульта в GUIDED, 2 — ігнорувати yaw пілота, 6 — навігація за точками для позиційних цілей, 7 — флюгування.

### Розібраний приклад: «апарат не рухається за командою швидкості»
Перевірки по черзі: (1) режим GUIDED (`HEARTBEAT.custom_mode`); (2) `type_mask` — чи не замаскована швидкість; (3) частота надсилання ≥ 2 Гц (таймаут 3 с); (4) `WP_SPD` (до 4.7 — `WPNAV_SPEED`)/`PSC_*` не обмежують до нуля; (5) геозона не тримає біля межі; (6) `STATUSTEXT` — «EKF needs position» тощо. У 80% випадків — (1) або (2).

{{diagram:guided-timeout|Ціль за швидкістю в GUIDED діє GUID_TIMEOUT (3 с за замовчуванням): companion зобов'язаний повторювати її частіше, інакше апарат зупиниться і зависне.}}

## practice
### Крок 1. Зліт і ціль за позицією (SITL)
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

### Крок 2. Ціль за швидкістю, з регулярним надсиланням
```python
VEL_ONLY = 0b0000_1111_1100_0111  # use vx,vy,vz; ignore position, accel, yaw
t_end = time.time() + 5
while time.time() < t_end:
    hb = m.recv_match(type="HEARTBEAT", blocking=False)
    if hb and hb.type != mavutil.mavlink.MAV_TYPE_GCS and mavutil.mode_string_v10(hb) != "GUIDED":
        print("pilot took over, stop sending"); break
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED, VEL_ONLY,
        0, 0, 0,  1.0, 0, 0,  0, 0, 0,  0, 0)   # 1 m/s north
    time.sleep(0.2)                              # 5 Hz, inside GUID_TIMEOUT
```

Перестань надсилати — апарат зависне сам. Це і є тест таймауту: виконай його навмисно.

### Крок 2б. Автомат на фейковому з'єднанні
Дописати переходи з таблиці й тест: фейк віддає HEARTBEAT із режимом LOITER посеред TASK — автомат має перейти в PILOT і не надіслати більше жодної цілі. Другий тест: висота не зростає 20 с після зльоту — автомат командує LAND. Обидва тести — у CI, як у стартері `examples/sitl-pymavlink`.

### Крок 3. Capstone-каркас
Збери з модулів треку: Raspberry Pi з маршрутизатором → сервіс на Python → GUIDED-логіка (наприклад, «облетіти точку інтересу по колу й повернутися»), ESP32 з індикацією стану. Критерій здачі: сценарій працює в SITL, задокументовано протокол і поведінку при відмові companion, реальний політ — лише з геозоною і пілотом.

### Що має вийти і що записати
- **Позиція.** Після цілі `POS_ONLY` апарат летить у точку й висить там, а не повертається: ціль за позицією не потребує потоку. Запиши час прильоту й похибку позиції наприкінці (`GLOBAL_POSITION_INT` проти цілі).
- **Швидкість і таймаут.** Цілі `VEL_ONLY` надсилаються з частотою 5–10 Гц. Припини надсилати — через `GUID_TIMEOUT` (за замовчуванням 3 с) апарат зупиняється і зависає. Запиши за логом час від останньої цілі до зупинки: він має збігтися з параметром.
- **Зміна режиму пілотом.** Перемкни режим у LOITER посеред завдання: код бачить це за `HEARTBEAT.custom_mode`, переходить у стан PILOT і більше не надсилає жодної цілі. Перевірка — у MAVLink Inspector після перемикання немає `SET_POSITION_TARGET_*` від companion.
- **Геозона.** `FENCE_ENABLE = 1`, тип — висота і коло, радіус 50 м, дія RTL. Надішли ціль за межами кола: залежно від версії ціль відхиляється або апарат долітає до межі й іде в RTL. Запиши, що саме сталося в тебе, і збережи лог — це доказ, що захист працює і без твого коду.

Лабораторна зараховується, коли зліт і ціль за позицією виконано в SITL, цілі за швидкістю надсилаються з частотою 5–10 Гц і таймаут перевірено навмисно з часом за логом, код припиняє надсилати цілі при зміні режиму пілотом, а геозону ввімкнено й перевірено.

## diagnostics
- **Симптом:** апарат не реагує на цілі
  - Можлива причина: не GUIDED, не заармлений, `type_mask` ігнорує потрібні поля.
  - Що зробити: перевірити режим і арм у heartbeat, маску, `STATUSTEXT`.
- **Симптом:** летить угору замість униз (або навпаки)
  - Можлива причина: знак Z у NED.
  - Що зробити: Z униз додатний; підйом — від'ємне Z.
- **Симптом:** через кілька секунд зависає, хоча команда була
  - Можлива причина: ціль за швидкістю надіслано один раз, спрацював таймаут.
  - Що зробити: надсилати регулярно (5–10 Гц).
- **Симптом:** зупиняється на межі, не долетівши до цілі
  - Можлива причина: геозона або обмеження `WPNAV_*`.
  - Що зробити: перевірити `FENCE_*` і повідомлення FC — це захист, а не баг.

## references
- Copter Commands in Guided Mode — ArduPilot Dev | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- MAVLink SET_POSITION_TARGET_LOCAL_NED (common.xml) | https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED | primary | A
- Guided Mode — ArduPilot Copter | https://ardupilot.org/copter/docs/ac2_guidedmode.html | primary | A

## checklist
- Усі цілі спершу в SITL
- Знак Z у NED перевірено
- Цілі за швидкістю надсилаються регулярно, таймаут перевірено навмисно
- Код поважає зміну режиму пілотом
- Геозону ввімкнено, пілот із тумблером на LOITER/RTL
- Поведінку при відмові companion задокументовано
