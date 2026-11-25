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

{{diagram:guided-silence-tree|Таймаут есть только у целей скорости, ускорения и углов: после цели по позиции замолчавший companion оставляет аппарат лететь в точку и висеть там.}}

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
```bash
./run_sitl.sh 8 > sitl8.log 2>&1 &      # arducopter -S --model + -I 8 -w --defaults copter.parm --home -35.363261,149.165230,584,353
sleep 2
mavproxy.py --master=tcp:127.0.0.1:5840 --out=udp:127.0.0.1:14650 --out=udp:127.0.0.1:14651 \
  --streamrate=-1 --daemon --non-interactive --state-basedir=./mp8 > mavproxy8.log 2>&1 &
sleep 4
python3 -u companion_lab.py udpin:127.0.0.1:14650
```

### Крок 2. Ціль за швидкістю, з регулярним надсиланням
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

### Крок 6. Журнал прогону ArduCopter 4.7.2 SITL
Стенд (блок кроку 1: SITL -> маршрутизатор MAVProxy -> companion) і скрипт лабораторної (блок кроку 2) прогнано; кожен рядок цього виводу пояснено в російському оригіналі.

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

{{diagram:chart-ap-guided-silence-stop|Скорость держится все 3 с GUID_TIMEOUT после последней цели и падает до нуля примерно за секунду торможения: остановка < 0.2 м/с — через 4.4 с.}}

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
