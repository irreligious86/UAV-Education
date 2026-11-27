---
id: f-safety
title: "Безопасность и предполётный чек"
level: L1
readingTime: 25 мин
firmware: любая прошивка
status: published
added: 2026-11-07
tags:
  - безопасность
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
Пятидюймовый проп на кончике движется со скоростью около 300 км/ч и несёт достаточно энергии, чтобы рассечь кожу до кости; LiPo при пробое отдаёт сотни ампер и горит с собственным окислителем: пламя можно сбить, но горение возобновляется, пока элементы не остынут. Большинство травм в хобби случается не в воздухе, а на столе: дрон заармился с пропами во время настройки. Модуль даёт физику опасности в числах, правила, которые не обсуждаются, полный список флагов запрета арма Betaflight (из исходников, с расшифровкой) и аналог в ArduPilot, предполётный и послеполётный чек-листы и порядок действий при пожаре АКБ.

## theory
### Опасность в числах
- **Пропеллер.** Окружная скорость кончика = π · D · n. Для 5" (D = 0.127 м) на висении при 14 000 об/мин (233 об/с): 0.40 м × 233 ≈ 93 м/с — около 335 км/ч; без нагрузки до 30 000 об/мин — 200 м/с. Кинетическая энергия вращающегося 5" пропа (~4 г) — единицы джоулей: достаточно для глубоких порезов; у 7–10" — десятки джоулей, переломы пальцев; 15" на X8 — травмы, несовместимые с продолжением хобби.
- **Моторы на столе.** Тест моторов в конфигураторе без снятых пропов — классическая травма. Прошивка предупреждает, но не остановит.
- **LiPo.** Внутреннее сопротивление 1–3 мОм на элемент: короткое замыкание 6S-пакета — ток в сотни ампер, провод раскаляется за секунду. Пробитый при падении элемент может загореться через минуты или часы после удара. Горение — термический разгон с выделением кислорода из катода: сбить пламя (огнетушитель ABC, песок), затем **охлаждать большим количеством воды** или вынести в негорючей ёмкости на улицу и дать прогореть. Огнетушитель класса D рассчитан на металлический литий — в LiPo и Li-Ion его нет. Вздутый пакет — списан, разрядить до 0 через нагрузку (резистор или лампа, не солёная вода — процедура в `f-power`) и утилизировать.
- **Потеря связи.** Если failsafe не проверен на этом аппарате, он делает то, что никто не выбирал (модуль «Failsafe»).
- **Первый полёт после любого изменения** — перепутанный мотор, направление пропа, неверный миксер, непроверенный фильтр: статистически самый опасный вылет.


{{diagram:safety-thermal-ladder|Окно заряда 10–45 °C и ступени разгона на одной шкале: от верха окна до саморазогрева всего 35 °C, а с 180 °C катод сам даёт кислород.}}

{{diagram:safety-bench-sequence|Порядок стенда: шаги 1–6 без пропов, пропы — последним шагом на площадке; любой непройденный шаг останавливает работу.}}

### Как прошивка защищает от арма (Betaflight master; в 2025.12 нет `AUTOPILOT_SW`, в 4.5 нет `FLIP_SWITCH`/`ALT_HOLD_SW`/`POS_HOLD_SW`/`AUTOPILOT_SW`, а `ARM_SWITCH` называется `ARMSWITCH`)
Арм невозможен, пока активен хотя бы один флаг запрета. Их список — в `src/main/fc/runtime_config.c`, видны по `status` в CLI и в OSD (элемент «Warnings»):

{{diagram:arming-tree|Дерево диагностики «не армится»: сначала читаем флаг, потом проверяем конкретную причину.}}

| Флаг | Что значит | Что делать |
|---|---|---|
| `NOGYRO` | гироскоп не обнаружен | проверить плату/target, не летать |
| `FAILSAFE` / `BOXFAILSAFE` | активен failsafe (нет RC) / включён тумблер failsafe | восстановить связь, выключить тумблер |
| `RXLOSS` | нет сигнала приёмника | бинд, питание RX, протокол порта |
| `NOT_DISARMED` | не дизармлен после… | дизарм тумблером |
| `RUNAWAY` | сработала защита runaway takeoff | дизарм; проверить направление моторов/пропов |
| `CRASH` | детектор краша | дизарм/перезагрузка |
| `THROTTLE` | газ не в минимуме | стик газа вниз, проверить `min_check` |
| `ANGLE` | наклон больше `small_angle` | выровнять, или `small_angle = 180` для Acro |
| `BOOTGRACE` | ещё не прошло время после включения | подождать |
| `NOPREARM` | не включён PREARM | включить PREARM |
| `LOAD` | перегрузка процессора | снизить частоту петли/отключить функции |
| `CALIB` | идёт калибровка | подождать |
| `CLI`, `CMS`, `MSP`, `BST` | открыт CLI / OSD-меню / подключён конфигуратор | закрыть — и это правильно |
| `PARALYZE` | режим PARALYZE активирован | перезагрузка |
| `GPS` | GPS Rescue требует fix, его нет | ждать fix или отключить требование |
| `RESCUE_SW` | тумблер GPS Rescue включён при арме | выключить |
| `DSHOT_TELEM` | RPM-фильтр включён, а eRPM от ESC нет | `dshot_bidir`, прошивка ESC, провода |
| `REBOOT_REQD` | требуется перезагрузка после настройки | перезагрузить |
| `DSHOT_BBANG` | ошибка bitbang DShot | проверить ресурсы/таймеры |
| `NO_ACC_CAL` | акселерометр не откалиброван | калибровка |
| `MOTOR_PROTO` | протокол моторов не настроен | выбрать DShot |
| `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`, `AUTOPILOT_SW` | тумблер режима включён при арме | выключить |
| `ARM_SWITCH` | тумблер ARM был включён при подключении | выключить и включить снова |

Эти флаги — страховка, не помеха. Правило: устранять причину, не отключать проверку. **ArduPilot**: `ARMING_SKIPCHK` (4.7+, битмаска **пропускаемых** проверок; до 4.7 — `ARMING_CHECK`, битмаска включённых: баро, компас, GPS, INS, параметры, RC, напряжение, геозона…), сообщения «PreArm: …» в GCS — та же логика; пропуск проверок допустим только на стенде.

### Режимы и устройства для защиты
- **PREARM** — второй тумблер, без которого арм невозможен; обязателен на аппаратах с пропами 7"+.
- **Failsafe** — что делать при потере связи; проверяется на земле без пропов перед первым полётом каждой новой сборки.
- **Beeper** и **GPS в OSD** — найти упавший аппарат.
- **Runaway takeoff prevention** (Betaflight `runaway_takeoff_prevention = ON`) — дизарм, если после арма гироскоп показывает рост вращения без реакции на управление (перепутанные моторы/пропы).
- **Пищалка при разряде, таймер** — чтобы не улететь на разряженной АКБ.

### Площадка и люди
Радиус безопасной зоны вокруг взлёта — не меньше 10–15 м для 5", 30 м для тяжёлых; никто не стоит в плоскости пропов при арме; взлёт — от себя. Правила и зоны — модуль «Правила», организация команды — «Полевые операции».

## practice

### Предполётный чек-лист (распечатать)
1. Пропы: целые, затянуты, направление по схеме моторов, нет посторонних предметов в плоскости.
2. АКБ: без вздутий и повреждений, напряжение по элементам в норме (4.1–4.2 В/эл. полный), закреплена ремнём, XT-разъём не оплавлен.
3. Антенны RC и VTX: на месте, целые, не в плоскости пропов; VTX с антенной (без неё — сгорит).
4. Пульт: правильная модель, заряжен, тумблеры ARM/PREARM выключены, failsafe-тест на этом аппарате сделан.
5. Видео/OSD: напряжение, LQ/RSSI, предупреждения — нет флагов.
6. Зона: люди и животные вне радиуса, взлёт от себя, препятствия учтены, правила площадки.
7. После арма: 2–3 с висения на высоте 0.5–1 м — отклик, звук, нет дрожи; при любой странности — посадка.

{{diagram:preflight-go-nogo|Предполётный чек-лист как цепочка «да/нет»: любой непройденный пункт останавливает вылет, а странность на первом висении заканчивается посадкой.}}

### Правила на столе
1. Пропы сняты до подключения АКБ. Всегда. Включая «на секунду».
2. Первое включение новой/перепаянной сборки — через smoke stopper, с мультиметром до того (модуль «Электричество 101»).
3. Тест моторов — только без пропов, с ограниченным газом, с рукой у разъёма АКБ.
4. Конфигуратор подключён → `MSP` флаг → арм невозможен. Не обходить.
5. Заряд LiPo — в несгораемом мешке/ящике, под присмотром, балансирным зарядом, не на горючей поверхности; хранение при 3.8 В/эл.

### При пожаре АКБ
1. Не трогать руками, не дуть. Отойти, дать людям отойти (дым токсичен).
2. Песок/земля сверху, или оттащить металлическим предметом на негорючую поверхность.
3. Огнетушитель — сбить пламя, затем охлаждать (горение может возобновляться).
4. После — не оставлять без присмотра час; остатки — в металлическую ёмкость.

### После полёта
1. Дизарм, выключить пульт последним (не первым!), отключить АКБ.
2. Температура моторов и ESC рукой; осмотр пропов и рамы.
3. Запись в журнал аппарата: что меняли, как летел, что заметили; лог — если тестовый.

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
- **Симптом:** дрон не армится
  - Возможная причина: активен флаг запрета арма.
  - Что сделать: `status` в CLI или OSD Warnings; таблица выше; устранить причину.
- **Симптом:** дрон заармился сразу после подключения АКБ
  - Возможная причина: тумблер ARM был включён и защита `ARM_SWITCH` отключена/не сработала, либо арм назначен на неверный канал.
  - Что сделать: проверить Modes, диапазон канала ARM, добавить PREARM.
- **Симптом:** после арма аппарат рванул вбок и дизармился
  - Возможная причина: runaway takeoff — перепутанные моторы/направление пропов.
  - Что сделать: тест моторов без пропов, схема направления, `resource`/`motor` remap.
- **Симптом:** после падения АКБ греется без нагрузки
  - Возможная причина: внутренний пробой.
  - Что сделать: изолировать на негорючей поверхности на улице, наблюдать, не заряжать, утилизировать.
- **Симптом:** VTX горячий, видео нет
  - Возможная причина: включали без антенны.
  - Что сделать: антенна всегда до питания; возможно, VTX уже повреждён.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight source — fc/runtime_config.c (armingDisableFlagNames) | https://github.com/betaflight/betaflight/blob/master/src/main/fc/runtime_config.c | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Safety — ArduPilot Copter (multicopter safety practices) | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A

## checklist
- На столе пропов нет — без исключений
- Знаю все флаги запрета арма и что делать с каждым
- Предполётный чек-лист распечатан и используется
- Failsafe проверен на этом дроне без пропов
- Знаю порядок действий при пожаре LiPo и где лежит песок
- После полёта веду запись в журнале аппарата
