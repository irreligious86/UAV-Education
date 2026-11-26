---
id: f-safety
title: "Безпека і передпольотна перевірка"
level: L1
readingTime: 25 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-07
tags:
  - безпека
  - чек-лист
  - LiPo
  - арм
related:
  - bf-failsafe
  - f-power
  - f-regulations
  - ops-field
next:
  - f-regulations
source: content/foundation/f-safety.md
source_hash: c3dbe1ced49d
---

## summary
П'ятидюймовий проп на кінчику рухається зі швидкістю близько 300 км/год і несе достатньо енергії, щоб розсікти шкіру до кістки; LiPo при пробої віддає сотні амперів і горить із власним окисником: полум'я мож збити, айбо горіння ся відновлює, доки комірки не охолонуть. Більшість травм у хобі стається не в повітрі, ай на столі: дрон заармився з пропами під час налаштування. Модуль дає фізику небезпеки в числах, правила, які не обговорюються, повний перелік прапорців заборони арму Betaflight (з вихідного коду, з розшифруванням) і аналог в ArduPilot, передпольотний і післяпольотний чек-листи та порядок дій при пожежі АКБ.

## theory
### Небезпека в числах
- **Пропелер.** Колова швидкість кінчика = π · D · n. Для 5" (D = 0.127 м) на зависанні при 14 000 об/хв (233 об/с): 0.40 м × 233 ≈ 93 м/с — близько 335 км/год; без навантаження до 30 000 об/хв — 200 м/с. Кінетична енергія 5" пропа (~4 г), що обертається, — одиниці джоулів: досить для глибоких порізів; у 7–10" — десятки джоулів, переломи пальців; 15" на X8 — травми, несумісні з продовженням хобі.
- **Мотори на столі.** Тест моторів у конфігураторі без знятих пропів — класична травма. Прошивка попереджає, айбо не зупинить.
- **LiPo.** Внутрішній опір 1–3 мОм на комірку: коротке замикання 6S-пакета — струм у сотні амперів, провід ся розжарює за секунду. Пробита під час падіння комірка може загорітися через хвилини або години після удару. Горіння — тепловий розгін із виділенням кисню з катода: збити полум'я (вогнегасник ABC, пісок), потім **охолоджувати великою кількістю води** або винести в негорючій ємності надвір і дати догоріти. Вогнегасник класу D розрахований на металевий літій — у LiPo та Li-Ion його немає. Здутий пакет — списаний, розрядити до 0 у солоній воді (кілька днів) і утилізувати.
- **Втрата зв'язку.** Кедь failsafe не перевірено на цьому апараті, вун чинить те, чого ніхто не обирав (модуль «Failsafe»).
- **Перший політ після будь-якої зміни** — переплутаний мотор, напрямок пропа, неправильний мікшер, неперевірений фільтр: статистично найнебезпечніший виліт.


{{diagram:safety-thermal-ladder|Окно заряда 10–45 °C и ступени разгона на одной шкале: от верха окна до саморазогрева всего 35 °C, а с 180 °C катод сам даёт кислород.}}

{{diagram:safety-bench-sequence|Порядок стенда: шаги 1–6 без пропов, пропы — последним шагом на площадке; любой непройденный шаг останавливает работу.}}

### Як прошивка захищає від арму (Betaflight master; у 2025.12 немає `AUTOPILOT_SW`, у 4.5 немає `FLIP_SWITCH`/`ALT_HOLD_SW`/`POS_HOLD_SW`/`AUTOPILOT_SW`, а `ARM_SWITCH` називається `ARMSWITCH`)
Арм неможливий, доки активний хоть один прапорець заборони. Їхній перелік — у `src/main/fc/runtime_config.c`, їх видно за `status` у CLI і в OSD (елемент «Warnings»):

{{diagram:arming-tree|Дерево діагностики «не армиться»: спершу читаємо прапорець, потім перевіряємо конкретну причину.}}

| Прапорець | Що означає | Що робити |
|---|---|---|
| `NOGYRO` | гіроскоп не виявлено | перевірити плату/target, не літати |
| `FAILSAFE` / `BOXFAILSAFE` | активний failsafe (немає RC) / увімкнено тумблер failsafe | відновити зв'язок, вимкнути тумблер |
| `RXLOSS` | немає сигналу приймача | бінд, живлення RX, протокол порту |
| `NOT_DISARMED` | не дизармлено після… | дизарм тумблером |
| `RUNAWAY` | спрацював захист runaway takeoff | дизарм; перевірити напрямок моторів/пропів |
| `CRASH` | детектор крашу | дизарм/перезавантаження |
| `THROTTLE` | газ не в мінімумі | стік газу вниз, перевірити `min_check` |
| `ANGLE` | нахил більший за `small_angle` | вирівняти, або `small_angle = 180` для Acro |
| `BOOTGRACE` | ще не минув час після ввімкнення | зачекати |
| `NOPREARM` | не ввімкнено PREARM | увімкнути PREARM |
| `LOAD` | перевантаження процесора | знизити частоту петлі/вимкнути функції |
| `CALIB` | триває калібрування | зачекати |
| `CLI`, `CMS`, `MSP`, `BST` | відкрито CLI / OSD-меню / підключено конфігуратор | закрити — і сесе правильно |
| `PARALYZE` | режим PARALYZE активовано | перезавантаження |
| `GPS` | GPS Rescue вимагає fix, а його немає | чекати fix або вимкнути вимогу |
| `RESCUE_SW` | тумблер GPS Rescue увімкнено під час арму | вимкнути |
| `DSHOT_TELEM` | RPM-фільтр увімкнено, а eRPM від ESC немає | `dshot_bidir`, прошивка ESC, дроти |
| `REBOOT_REQD` | потрібне перезавантаження після налаштування | перезавантажити |
| `DSHOT_BBANG` | помилка bitbang DShot | перевірити ресурси/таймери |
| `NO_ACC_CAL` | акселерометр не відкалібровано | калібрування |
| `MOTOR_PROTO` | протокол моторів не налаштовано | вибрати DShot |
| `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`, `AUTOPILOT_SW` | тумблер режиму ввімкнено під час арму | вимкнути |
| `ARM_SWITCH` | тумблер ARM був увімкнений під час підключення | вимкнути й увімкнути знову |

Ці прапорці — страховка, а не завада. Правило: усувати причину, а не вимикати перевірку. **ArduPilot**: `ARMING_SKIPCHK` (4.7+, бітова маска перевірок, які **пропускаються**; до 4.7 — `ARMING_CHECK`, бітова маска ввімкнених: баро, компас, GPS, INS, параметри, RC, напруга, геозона…), повідомлення «PreArm: …» у GCS — та сама логіка; пропуск перевірок допустимий лиш на стенді.

### Режими й пристрої для захисту
- **PREARM** — другий тумблер, без якого арм неможливий; обов'язковий на апаратах із пропами 7"+.
- **Failsafe** — що робити при втраті зв'язку; перевіряється на землі без пропів перед першим польотом кожної нової збірки.
- **Beeper** і **GPS в OSD** — знайти апарат, що впав.
- **Runaway takeoff prevention** (Betaflight `runaway_takeoff_prevention = ON`) — дизарм, кедь після арму гіроскоп показує зростання обертання без реакції на керування (переплутані мотори/пропи).
- **Пищалка при розряді, таймер** — щоб не відлітати на розрядженій АКБ.

### Майданчик і люди
Радіус безпечної зони довкола зльоту — не менше 10–15 м для 5", 30 м для важких; ніхто не стоїть у площині пропів під час арму; зліт — від себе. Правила й зони — модуль «Правила», організація команди — «Польові операції».

## practice

### Передпольотний чек-лист (роздрукувати)
1. Пропи: цілі, затягнуті, напрямок за схемою моторів, немає сторонніх предметів у площині.
2. АКБ: без здуття й пошкоджень, напруга по комірках у нормі (4.1–4.2 В/ком. повна), закріплена ременем, XT-роз'єм не оплавлений.
3. Антени RC і VTX: на місці, цілі, не в площині пропів; VTX з антеною (без неї — згорить).
4. Пульт: правильна модель, заряджений, тумблери ARM/PREARM вимкнені, failsafe-тест на цьому апараті зроблено.
5. Відео/OSD: напруга, LQ/RSSI, попередження — прапорців немає.
6. Зона: люди й тварини поза радіусом, зліт від себе, перешкоди враховано, правила майданчика.
7. Після арму: 2–3 с зависання на висоті 0.5–1 м — відгук, звук, немає тремтіння; за будь-якої дивності — посадка.

{{diagram:preflight-go-nogo|Предполётный чек-лист как цепочка «да/нет»: любой непройденный пункт останавливает вылет, а странность на первом висении заканчивается посадкой.}}

### Правила на столі
1. Пропи зняті до підключення АКБ. Завжди. Включно з «на секундочку».
2. Перше ввімкнення нової/перепаяної збірки — через smoke stopper, з мультиметром перед тим (модуль «Електрика 101»).
3. Тест моторів — лиш без пропів, з обмеженим газом, з рукою біля роз'єму АКБ.
4. Конфігуратор підключено → прапорець `MSP` → арм неможливий. Не обходити.
5. Заряджання LiPo — у вогнетривкому мішку/ящику, під наглядом, балансним зарядом, не на горючій поверхні; зберігання при 3.8 В/ком.

### При пожежі АКБ
1. Не торкатися руками, не дмухати. Відійти, дати відійти людям (дим токсичний).
2. Пісок/земля зверху, або відтягнути металевим предметом на негорючу поверхню.
3. Вогнегасник — збити полум'я, потім охолоджувати (горіння може відновлюватися).
4. Після — не залишати без нагляду годину; залишки — у металеву ємність.

### Після польоту
1. Дизарм, вимкнути пульт останнім (не першим!), від'єднати АКБ.
2. Температура моторів і ESC рукою; огляд пропів і рами.
3. Запис у журнал апарата: що змінював, як летів, що помітив; лог — кедь тестовий.

### Лабораторные (SITL ArduCopter 4.7.2 и расчёт; текст — в русской версии)

```python
"""f-safety lab: ArduCopter 4.7.2 SITL — what 'armed' means on the bench, and what an RC loss does
(1) on the ground, armed;  (2) in the air at 10 m in GUIDED.  RC loss = SIM_RC_FAIL=1 (no pulses)."""
import sys, time
from pymavlink import mavutil
m = mavutil.mavlink_connection(sys.argv[1]); m.wait_heartbeat()
t0 = time.time()
def T(): return f"t={time.time()-t0:6.1f}s"
def setp(n, v):
    m.mav.param_set_send(m.target_system, m.target_component, n.encode(), v, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    time.sleep(0.3)
def mode(name):
    m.set_mode(m.mode_mapping()[name])
def flush():
    while m.recv_match(blocking=False) is not None: pass
def armed():
    flush()
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    return bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED), mavutil.mode_string_v10(hb)
def pwm():
    flush()
    s = m.recv_match(type='SERVO_OUTPUT_RAW', blocking=True, timeout=3)
    return [s.servo1_raw, s.servo2_raw, s.servo3_raw, s.servo4_raw]
def drain(sec, tag=""):
    end = time.time() + sec; last = None
    while time.time() < end:
        msg = m.recv_match(type=['STATUSTEXT', 'HEARTBEAT'], blocking=True, timeout=0.5)
        if msg is None: continue
        if msg.get_type() == 'STATUSTEXT':
            print(f"{T()} {tag} STATUSTEXT: {msg.text}")
        else:
            st = (bool(msg.base_mode & 128), mavutil.mode_string_v10(msg))
            if st != last: print(f"{T()} {tag} armed={st[0]} mode={st[1]}"); last = st
m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
for n in ("MOT_SPIN_ARM", "MOT_SPIN_MIN", "FS_THR_ENABLE", "FS_THR_VALUE", "RC_FS_TIMEOUT", "DISARM_DELAY"):
    flush(); m.mav.param_request_read_send(m.target_system, m.target_component, n.encode(), -1)
    while True:
        p = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
        if p.param_id == n: break
    print(f"param {p.param_id} = {p.param_value:g}")
# wait until arming is possible (EKF + GPS) — try every 2 s
mode('STABILIZE')
for i in range(40):
    m.arducopter_arm(); time.sleep(1.5)
    if armed()[0]: break
flush(); print(f"{T()} (1) armed on the ground in STABILIZE, throttle stick 1000 us: motors PWM = {pwm()}")
time.sleep(2); print(f"{T()}     2 s later, still no throttle:                motors PWM = {pwm()}")
flush(); setp("SIM_RC_FAIL", 1); print(f"{T()}     SIM_RC_FAIL=1 (receiver silent)")
drain(4, "   ")
setp("SIM_RC_FAIL", 0); time.sleep(2)
# (2) in the air
mode('GUIDED')
for i in range(10):
    m.arducopter_arm(); time.sleep(1.5)
    if armed()[0]: break
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
while True:
    p = m.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    if p.relative_alt > 9500: break
print(f"{T()} (2) GUIDED, 10 m reached; now SIM_RC_FAIL=1")
flush(); tf = time.time(); setp("SIM_RC_FAIL", 1)
end = time.time() + 6; last = None
while time.time() < end:
    msg = m.recv_match(type=['STATUSTEXT', 'HEARTBEAT'], blocking=True, timeout=0.5)
    if msg is None: continue
    dt = time.time() - tf
    if msg.get_type() == 'STATUSTEXT': print(f"    +{dt:4.2f}s STATUSTEXT: {msg.text}")
    else:
        md = mavutil.mode_string_v10(msg)
        if md != last: print(f"    +{dt:4.2f}s mode={md}"); last = md
setp("SIM_RC_FAIL", 0); print(f"{T()} RC restored (SIM_RC_FAIL=0)"); drain(3, "   ")
```

```text
param MOT_SPIN_ARM = 0.1
param MOT_SPIN_MIN = 0.15
param FS_THR_ENABLE = 1
param FS_THR_VALUE = 975
param RC_FS_TIMEOUT = 1
param DISARM_DELAY = 10
t=  25.0s (1) armed on the ground in STABILIZE, throttle stick 1000 us: motors PWM = [1026, 1026, 1026, 1026]
t=  27.1s     2 s later, still no throttle:                motors PWM = [1100, 1100, 1100, 1100]
t=  27.5s     SIM_RC_FAIL=1 (receiver silent)
t=  28.0s     armed=True mode=STABILIZE
t=  28.2s     STATUSTEXT: Radio Failsafe - Disarming
t=  28.2s     STATUSTEXT: Disarming motors
t=  29.0s     armed=False mode=STABILIZE
t=  29.4s     STATUSTEXT: PreArm: Radio failsafe on
t=  50.8s (2) GUIDED, 10 m reached; now SIM_RC_FAIL=1
    +0.30s mode=GUIDED
    +0.99s mode=RTL
    +0.99s STATUSTEXT: Radio Failsafe
t=  57.9s RC restored (SIM_RC_FAIL=0)
t=  57.9s     STATUSTEXT: Radio Failsafe Cleared
t=  58.0s     armed=True mode=RTL
```

```python
import math
# 1) Energy of a pack and the IATA passenger category (Wh = Ah x V nominal; LiPo/Li-Ion 3.6-3.7 V per cell)
def wh(s, mah, v_cell): return s * v_cell * mah / 1000
def iata(e): return "<=100 Wh: ручная кладь, без согласования" if e <= 100 else (
    "100-160 Wh: ручная кладь, согласование, не больше 2" if e <= 160 else ">160 Wh: пассажиру нельзя, только груз")
packs = [("6S 1300 LiPo", 6, 1300, 3.7), ("6S 2200 LiPo", 6, 2200, 3.7), ("4S 5200 LiPo", 4, 5200, 3.7),
         ("6S2P P42A Li-Ion", 6, 8400, 3.6), ("6S4P P42A Li-Ion", 6, 16800, 3.6)]
for name, s, mah, v in packs:
    e = wh(s, mah, v); print(f"{name:18s} {e:6.1f} Wh  {iata(e)}")
# 2) Charging: current at 1C (course rule) and charger power at 4.2 V/cell
for name, s, mah in [("6S 1300", 6, 1300), ("4S 5200", 4, 5200)]:
    i = mah / 1000; p = s * 4.2 * i
    print(f"{name}: 1C = {i:.1f} A, P = {s}x4.2x{i:.1f} = {p:.0f} W")
# 3) Kinetic energy of a spinning prop, thin-rod model I = m L^2 / 12 (L = diameter)
for d_in, m_g, rpm in [(5, 4, 14000), (5, 4, 30000), (7, 9, 9000), (10, 18, 6000)]:
    L = d_in * 0.0254; I = m_g / 1000 * L**2 / 12; w = rpm * 2 * math.pi / 60
    print(f'{d_in}" {m_g} g @ {rpm} rpm: tip {math.pi*L*rpm/60:5.0f} m/s, E = {0.5*I*w*w:5.1f} J')
# 4) Temperature gate before charging (Gens Ace 10-45 C, course rule)
for t in (5, 25, 52):
    print(f"pack {t} C:", "заряжать" if 10 <= t <= 45 else "не заряжать: ждать/греть до 10-45 C")
```

```text
6S 1300 LiPo         28.9 Wh  <=100 Wh: ручная кладь, без согласования
6S 2200 LiPo         48.8 Wh  <=100 Wh: ручная кладь, без согласования
4S 5200 LiPo         77.0 Wh  <=100 Wh: ручная кладь, без согласования
6S2P P42A Li-Ion    181.4 Wh  >160 Wh: пассажиру нельзя, только груз
6S4P P42A Li-Ion    362.9 Wh  >160 Wh: пассажиру нельзя, только груз
6S 1300: 1C = 1.3 A, P = 6x4.2x1.3 = 33 W
4S 5200: 1C = 5.2 A, P = 4x4.2x5.2 = 87 W
5" 4 g @ 14000 rpm: tip    93 m/s, E =   5.8 J
5" 4 g @ 30000 rpm: tip   199 m/s, E =  26.5 J
7" 9 g @ 9000 rpm: tip    84 m/s, E =  10.5 J
10" 18 g @ 6000 rpm: tip    80 m/s, E =  19.1 J
pack 5 C: не заряжать: ждать/греть до 10-45 C
pack 25 C: заряжать
pack 52 C: не заряжать: ждать/греть до 10-45 C
```

## diagnostics
- **Симптом:** дрон не армиться
  - Можлива причина: активний прапорець заборони арму.
  - Що зробити: `status` у CLI або OSD Warnings; таблиця вище; усунути причину.
- **Симптом:** дрон заармився одразу після підключення АКБ
  - Можлива причина: тумблер ARM був увімкнений і захист `ARM_SWITCH` вимкнено/не спрацював, або арм призначено на неправильний канал.
  - Що зробити: перевірити Modes, діапазон каналу ARM, додати PREARM.
- **Симптом:** після арму апарат рвонув убік і дизармився
  - Можлива причина: runaway takeoff — переплутані мотори/напрямок пропів.
  - Що зробити: тест моторів без пропів, схема напрямків, `resource`/`motor` remap.
- **Симптом:** після падіння АКБ ся гріє без навантаження
  - Можлива причина: внутрішній пробій.
  - Що зробити: ізолювати на негорючій поверхні надворі, спостерігати, не заряджати, утилізувати.
- **Симптом:** VTX гарячий, відео немає
  - Можлива причина: вмикали без антени.
  - Що зробити: антена завжди до живлення; можливо, VTX уже пошкоджено.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight source — fc/runtime_config.c (armingDisableFlagNames) | https://github.com/betaflight/betaflight/blob/master/src/main/fc/runtime_config.c | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Safety — ArduPilot Copter (multicopter safety practices) | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A

## checklist
- На столі пропів немає — без винятків
- Знаю всі прапорці заборони арму і що чинити з кожним
- Передпольотний чек-лист роздруковано і вун використовується
- Failsafe перевірено на цьому дроні без пропів
- Знаю порядок дій при пожежі LiPo і де лежить пісок
- Після польоту веду запис у журналі апарата
