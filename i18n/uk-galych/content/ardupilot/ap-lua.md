---
id: ap-lua
title: "Lua: сценарії та fault injection"
level: L3
readingTime: 25 хв
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - Lua
  - fault injection
  - SITL
related:
  - ap-sitl
  - ap-heavy
next:
  - ap-heavy
source: content/ardupilot/ap-lua.md
source_hash: 2f6f17b88f3d
---

## summary
ArduPilot вміє виконувати Lua-скрипти просто на польотнику: додавати режими, читати датчики, реагувати на тумблери. У навчальному проєкті найголовніше застосування — fault injection: навмисно ламати мотор або сенсор у SITL і дивитися, як дрон і ти дасте собі раду. Модуль пояснює, як працює скриптинг, як прив'язати скрипт до тумблера пульта і як скласти набір «хаос-скриптів», кожен на своєму тумблері.

## theory
### Як влаштований скриптинг
- Вмикається параметром `SCR_ENABLE = 1` і перезавантаженням.
- Скрипти (`.lua`) лежать в `APM/scripts` на SD-карті; у SITL — у папці `scripts` там, звідки запущено симулятор.
- Кожен скрипт працює у своїй «пісочниці» та з низьким пріоритетом: польотний код важливіший, точного розкладу скриптові ніхто не обіцяє.
- Пам'ять для скриптів задає `SCR_HEAP_SIZE`. Замало — скрипти падають і вискакує pre-arm помилка про брак пам'яті. Забагато — може не ініціалізуватися EKF.
- Як один скрипт упав з помилкою, зупиняється лише він. Як скінчилася спільна пам'ять скриптів (або паніка), стають усі скрипти аж до перезавантаження.
- Скриптинг потребує щонайменше 2 МБ флешу і на F4-контролерах не працює.

### Патерн update()
Скрипт — то функція `update()`, котра робить свою роботу й повертає себе та затримку в мілісекундах до наступного виклику. Жодних нескінченних циклів: планувальник сам кличе функцію знову.

### Прив'язка до тумблера
Параметр `RCx_OPTION` призначає каналові пульта функцію. Значення 300–307 — Scripting1…Scripting8: зарезервовані для скриптів. Скрипт знаходить свій канал через `rc:find_channel_for_option(300)` і читає положення тумблера через `get_aux_switch_pos()` (0 — низ, 1 — середина, 2 — верх).

### Applets і examples
У репозиторії ArduPilot є готові скрипти: `libraries/AP_Scripting/applets` (готові до роботи, кожен має `.md`-опис) і `libraries/AP_Scripting/examples` (навчальні приклади). Починати варто з applet `motor_failure_test.lua`: він зупиняє мотори, задані бітовою маскою `MOT_STOP_BITMASK`, коли тумблер Scripting1 угорі. Октокоптер мусить летіти з одним мотором, що відмовив.

### Що вміє API (за `docs/docs.lua` в AP_Scripting)
Читання стану: `ahrs:get_position()`, `ahrs:get_velocity_NED()`, `ahrs:get_yaw()`, `gps:num_sats()`, `battery:voltage()`, `rangefinder:distance_orient()` (у метрах; `distance_cm_orient` застарів), `esc_telem:get_rpm()`, `vehicle:get_mode()`, `arming:is_armed()`; дії: `vehicle:set_mode()`, `vehicle:set_target_velocity_NED()`, `vehicle:set_target_location()`, `mission:set_current_cmd()`, `SRV_Channels:set_output_pwm()`, `relay:on()`, `param:set()`/`param:add_param()` (власні параметри з префіксом), `gcs:send_text()`, `logger:write()` (власні лог-повідомлення!), `notify:play_tune()`, `rc:get_aux_cached()` (тумблер `RCx_OPTION = 300..307` Scripting1..8), `serial:find_serial()` (власний протокол на UART), `CAN:get_device()` (DroneCAN), `periph` на AP_Periph. Таймери — повернення `update, 100` (мс до наступного виклику). Параметри скриптингу: `SCR_ENABLE`, `SCR_HEAP_SIZE` (пам'ять; на F4 не вистачає → лише H7/F7 із запасом), `SCR_VM_I_COUNT` (ліміт інструкцій на виклик — захист від зависання), `SCR_DEBUG_OPTS`.

### Applets як підручник
`libraries/AP_Scripting/applets/` — готові, з `.md`-описом: `motor_failure_test.lua` (зупиняє мотори за бітмаскою `MOT_STOP_BITMASK` тумблером Scripting1 — тест відмови мотора на гексі/X8 у SITL і в полі), `VTOL-quicktune.lua` (QuikTune для мультикоптерів і VTOL), `rover-quicktune.lua`, `copter-deadreckon-home.lua` (повернення за численням шляху при втраті GPS), `arming-checks.lua` (власні передармові перевірки), `ahrs-source-extnav-optflow.lua` (перемикання джерел EKF за якістю), `BattEstimate.lua`, `MissionSelector.lua`, `net_webserver.lua`, `crsf-calibrate.lua`, `SmartAudio.lua`. Читати їх — найліпший спосіб вивчити API і стиль (захисні перевірки, `pcall`-подібні обгортки, параметри через `param:add_table`).

### Розібраний приклад: захист за температурою ESC
```lua
-- esc_temp_guard.lua: warn at 80 C, switch to LAND at 100 C (any ESC), check every 500 ms
local WARN, CRIT = 80, 100
local MODE_LAND = 9
local warned = false
function update()
  for i = 0, 7 do
    local t = esc_telem:get_temperature(i)          -- nil if no telemetry; value in centi-degrees
    if t then
      t = t // 100
      if t >= CRIT and arming:is_armed() and vehicle:get_mode() ~= MODE_LAND then
        gcs:send_text(2, string.format("ESC %d %dC: LAND", i + 1, t))
        vehicle:set_mode(MODE_LAND)
      elseif t >= WARN and not warned then
        gcs:send_text(4, string.format("ESC %d temp %dC", i + 1, t)); warned = true
      end
    end
  end
  return update, 500
end
return update()
```
Перевірка в SITL: `SIM_ESC_TELEM = 1`, підміни поріг на 30 °C, переконайся, що спрацьовує; потім — на стенді. Запиши то у FMEA як захід з посиланням на тест (модуль «Відмовостійкість»).

{{diagram:lua-script-lifecycle|Скрипт перепланируется, пока update() возвращает функцию и задержку; любая ошибка снимает его до перезагрузки и блокирует арм через PreArm: Scripting.}}

{{diagram:lua-runtime|Як виконується скрипт: файл з APM/scripts/ іде в Lua VM, update() повертає себе й період, помилки ловить pcall, дії йдуть через прив'язки API.}}

## practice
### Крок 1. Увімкнути скриптинг у SITL
```
param set SCR_ENABLE 1
reboot
```

### Крок 2. Скрипт-індикатор на тумблері
Мінімальний скрипт: повідомляє в GCS, коли ся змінює положення тумблера Scripting2, і який стан арму.

```lua
-- switch_report.lua: report Scripting2 switch position and arming state to the GCS
local SWITCH_OPTION = 301  -- RCx_OPTION = 301 (Scripting2)
local switch = rc:find_channel_for_option(SWITCH_OPTION)
local last_pos = -1

function update()
  if not switch then
    gcs:send_text(4, "switch_report: no channel with RCx_OPTION=301")
    return update, 5000
  end
  local pos = switch:get_aux_switch_pos()
  if pos ~= last_pos then
    local armed = arming:is_armed() and "ARMED" or "disarmed"
    gcs:send_text(6, string.format("Scripting2 -> %d (%s)", pos, armed))
    last_pos = pos
  end
  return update, 200
end

return update, 1000
```

Поклади файл до `scripts/`, признач тумблер (`param set RC9_OPTION 301`), перезапусти SITL і поклацай тумблером.

### Крок 3. Відмова мотора за тумблером
1. Скопіюй applet `motor_failure_test.lua` до `scripts/`.
2. Признач тумблер на Scripting1: `RCx_OPTION = 300`.
3. Після перезавантаження з'явиться `MOT_STOP_BITMASK`. Постав 1 — відключатиметься мотор 1.
4. У SITL з рамою `octa-quad`: зліт, LOITER, тумблер угору. Ади, як дрон компенсує відмову.

### Крок 4. Набір хаос-скриптів
Ідея навчального набору: кожна «відмова» — окремий скрипт на своєму тумблері, аби вмикати їх незалежно:

- індикатор арму (світлодіод або повідомлення);
- ручна відмова мотора (applet);
- випадкові відмови сенсорів через параметри симулятора `SIM_*`;
- випадкова відмова 1–3 моторів.

Імена параметрів `SIM_*` міняються між версіями — дивись актуальні у своїй збірці командою `param show SIM_GPS*` у MAVProxy. Такі скрипти — лише для SITL: на реальному апараті параметрів `SIM_*` гет нема.

### Крок 5. Захист із тестами до SITL
Стартер проєкту №11 `examples/lua-protection`: `guard.lua` — захист за вібраціями (LAND), утримання всередині полігона із запасом (RTL) і обгортка `pcall`, котра після трьох помилок підряд у повітрі відводить апарат у RTL. Тести запускають **той самий** Lua-файл через `lupa` проти заглушки прив'язок (`millis`, `ahrs`, `vehicle`, `param`, `gcs`, `logger`) — помилки логіки ловляться за частки секунди, а SITL лишається приймальним тестом. Запусти `python -m pytest -q examples/lua-protection/tests`, а потім додай третій захист (наприклад, просідання напруги під навантаженням) разом із тестом.

Прогін цього кроку в SITL (ArduCopter 4.7.2); розбір і очікуваний результат — у російському оригіналі.

```lua
-- fault_inject.lua (SITL only): N s after climbing above 8 m, cut thrust of the motors in FLT_MASK
local PARAM_KEY = 72
assert(param:add_table(PARAM_KEY, "FLT_", 2), "add_table failed")
assert(param:add_param(PARAM_KEY, 1, "DELAY", 5), "add DELAY failed")   -- s after passing 8 m
assert(param:add_param(PARAM_KEY, 2, "MASK", 1), "add MASK failed")     -- bitmask, 1 = motor 1
local t_above, fired = nil, false
local calls, t_last, dt_sum = 0, millis(), 0

function update()
  local now = millis()
  calls = calls + 1
  dt_sum = dt_sum + (now - t_last):tofloat()
  t_last = now
  if calls % 50 == 0 then
    gcs:send_text(6, string.format("FLT: 50 calls, mean period %.1f ms", dt_sum / 50))
    dt_sum = 0
  end
  local d = ahrs:get_relative_position_D_home()       -- metres, positive down
  if not fired and d and arming:is_armed() and -d > 8 then
    t_above = t_above or now
    if (now - t_above):tofloat() > param:get("FLT_DELAY") * 1000 then
      local mask = math.floor(param:get("FLT_MASK"))
      param:set("SIM_ENGINE_MUL", 0)
      param:set("SIM_ENGINE_FAIL", mask)
      gcs:send_text(2, string.format("FLT: motors mask %d cut at %.1f m", mask, -d))
      logger:write("FLT", "Alt,Mask", "fi", "m-", "0-", -d, mask)
      fired = true
    end
  end
  return update, 100
end

gcs:send_text(6, "FLT: loaded")
return update, 100
```

```python
"""Lua lab: fault_inject.lua on a SITL hexa; run 1 adds a broken script to see what it does to arming.
Usage: python3 lua_lab.py ~/ardupilot   (run from a folder that holds scripts/fault_inject.lua)"""
import os, subprocess, sys, time
from pymavlink import mavutil

AP, DP = sys.argv[1], sys.argv[1] + "/Tools/autotest/default_params/"
open("lua.parm", "w").write("SCR_ENABLE 1\n")
open("scripts/bad.lua", "w").write(          # runtime error on the 3rd call
    "local n = 0\nfunction update() n = n + 1; if n == 3 then local t = nil; return t.x end\n"
    "  return update, 1000 end\nreturn update, 1000\n")


def start(wipe):
    sitl = subprocess.Popen([AP + "/build/sitl/bin/arducopter", "--model", "hexa", "--speedup", "5", *wipe,
                             "--defaults", DP + "copter.parm," + DP + "copter-hexa.parm,lua.parm",
                             "--home", "-35.363261,149.165230,584,353"],
                            stdout=open("sitl.out", "a"), stderr=subprocess.STDOUT)
    time.sleep(1)
    m = mavutil.mavlink_connection("tcp:127.0.0.1:5760"); m.wait_heartbeat()
    for msg_id in (33, 36):  # GLOBAL_POSITION_INT, SERVO_OUTPUT_RAW at 5 Hz
        m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, msg_id, 200000, 0, 0, 0, 0, 0)
    return sitl, m


def wait(m, sec, until=None):  # print STATUSTEXT for sec simulated seconds or until a text appears
    t_end = None
    while True:
        r = m.recv_match(type=["STATUSTEXT", "GLOBAL_POSITION_INT", "SERVO_OUTPUT_RAW"], blocking=True)
        if r.get_type() == "GLOBAL_POSITION_INT":
            wait.t, wait.alt = r.time_boot_ms / 1000, r.relative_alt / 1000
            t_end = t_end or wait.t + sec
            if wait.t > t_end:
                return
        elif r.get_type() == "SERVO_OUTPUT_RAW":
            wait.pwm = [getattr(r, f"servo{i}_raw") for i in range(1, 7)]
        elif "50 calls" not in r.text or "50 calls" not in wait.seen:
            print(f"[{wait.t:6.1f} s] {r.text}")
            wait.seen += r.text
            if until and until in r.text:
                return


wait.t, wait.seen = 0, ""
print("--- run 1: fault_inject.lua + bad.lua")
sitl, m = start(["-w"])
wait(m, 45)
m.set_mode("GUIDED"); m.arducopter_arm()
ack = m.recv_match(type="COMMAND_ACK", condition="COMMAND_ACK.command==400", blocking=True)
print(f"arm: COMMAND_ACK result {ack.result} (0 = accepted, 4 = failed)")
wait(m, 2); sitl.terminate(); sitl.wait()
os.remove("scripts/bad.lua")
print("--- run 2: bad.lua removed, same eeprom.bin (no -w)")
sitl, m = start([])
wait(m, 45)
m.set_mode("GUIDED")
while not m.motors_armed():
    m.arducopter_arm(); m.recv_match(type="HEARTBEAT", blocking=True); m.recv_match(type="HEARTBEAT", blocking=True)
m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 15)
wait(m, 300, until="cut at")
print(f"PWM at the cut: {wait.pwm}")
t_cut, low = wait.t, 99
while wait.t < t_cut + 25:
    wait(m, 0.2); low = min(low, wait.alt)
print(f"25 s after the cut: lowest alt {low:.1f} m, PWM {wait.pwm}")
sitl.terminate()
```

```text
--- run 1: fault_inject.lua + bad.lua
[   0.0 s] Barometer 1 calibration complete
[   0.0 s] Barometer 2 calibration complete
[   0.0 s] ArduPilot Ready
[   0.0 s] AHRS: DCM active
[   0.0 s] FLT: loaded
[   2.5 s] RC7: SaveWaypoint LOW
[   4.3 s] EKF3 IMU0 initialised
[   4.3 s] EKF3 IMU1 initialised
[   4.3 s] AHRS: EKF3 active
[   5.3 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[   5.3 s] alue (local 't')
[   5.7 s] EKF3 IMU0 tilt alignment complete
[   5.7 s] EKF3 IMU1 tilt alignment complete
[   5.7 s] EKF3 IMU0 MAG0 initial yaw alignment complete
[   5.7 s] EKF3 IMU1 MAG0 initial yaw alignment complete
[   7.9 s] FLT: 50 calls, mean period 112.8 ms
[   9.7 s] GPS 1: probing for u-blox at 230400 baud
[   9.7 s] GPS 1: detected u-blox
[  15.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  15.5 s] alue (local 't')
[  19.9 s] EKF3 IMU0 origin set
[  19.9 s] Field Elevation Set: 584m
[  20.1 s] EKF3 IMU1 origin set
[  25.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  25.5 s] alue (local 't')
[  30.3 s] PreArm: Scripting: ./scripts/bad.lua:2: attempt to
[  30.3 s]  index a
[  35.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  35.5 s] alue (local 't')
[  41.5 s] EKF3 IMU0 is using GPS
[  41.5 s] EKF3 IMU1 is using GPS
[  45.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  45.5 s] alue (local 't')
arm: COMMAND_ACK result 4 (0 = accepted, 4 = failed)
[  47.7 s] Arm: Scripting: ./scripts/bad.lua:2: attempt to in
[  47.7 s] dex a
--- run 2: bad.lua removed, same eeprom.bin (no -w)
[  50.1 s] Barometer 1 calibration complete
[  50.1 s] Barometer 2 calibration complete
[  50.1 s] ArduPilot Ready
[  50.1 s] AHRS: DCM active
[  50.1 s] FLT: loaded
[   2.6 s] RC7: SaveWaypoint LOW
[   4.2 s] EKF3 IMU0 initialised
[   4.2 s] EKF3 IMU1 initialised
[   4.2 s] AHRS: EKF3 active
[   5.6 s] EKF3 IMU1 tilt alignment complete
[   5.6 s] EKF3 IMU0 tilt alignment complete
[   5.8 s] EKF3 IMU1 MAG0 initial yaw alignment complete
[   5.8 s] EKF3 IMU0 MAG0 initial yaw alignment complete
[   9.6 s] GPS 1: probing for u-blox at 230400 baud
[   9.6 s] GPS 1: detected u-blox
[  19.8 s] EKF3 IMU1 origin set
[  19.8 s] Field Elevation Set: 584m
[  20.0 s] EKF3 IMU0 origin set
[  41.4 s] EKF3 IMU0 is using GPS
[  41.4 s] EKF3 IMU1 is using GPS
[  53.2 s] EKF3 IMU0 MAG0 in-flight yaw alignment complete
[  53.2 s] EKF3 IMU1 MAG0 in-flight yaw alignment complete
[  60.4 s] FLT: motors mask 1 cut at 14.9 m
PWM at the cut: [1594, 1594, 1594, 1594, 1594, 1595]
[  63.6 s] Potential Thrust Loss (1)
[  84.6 s] SIM Hit ground at 1.578218 m/s
25 s after the cut: lowest alt -0.0 m, PWM [1950, 1207, 1862, 1915, 1913, 1864]
```


## diagnostics
- **Симптом:** скрипт не запускається, у GCS тиша
  - Можлива причина: `SCR_ENABLE` не ввімкнено або не було перезавантаження, файл не в тій папці.
  - Що зробити: перевір параметр і шлях `scripts/` відносно папки, звідки запущено SITL.
- **Симптом:** pre-arm помилка про пам'ять скриптів
  - Можлива причина: замало `SCR_HEAP_SIZE` для завантажених скриптів.
  - Що зробити: підніми `SCR_HEAP_SIZE` або прибери зайві скрипти.
- **Симптом:** усі скрипти ся зупинили посеред польоту
  - Можлива причина: один скрипт упав з помилкою або вичерпав пам'ять.
  - Що зробити: читай повідомлення в GCS, виправ скрипт, перезавантаж.
- **Симптом:** `find_channel_for_option` повертає nil
  - Можлива причина: жодному каналові не призначено потрібний `RCx_OPTION`.
  - Що зробити: признач опцію на канал із тумблером.
- **Симптом:** скрипт не запускається, «Lua: … out of memory»
  - Можлива причина: `SCR_HEAP_SIZE` замалий, плата без запасу RAM.
  - Що зробити: збільш heap (H7 — 200–300 КБ), спрости скрипт.
- **Симптом:** «<ім'я>.lua exceeded time limit»
  - Можлива причина: важкий цикл в одному виклику update.
  - Що зробити: розбий роботу по викликах, `SCR_VM_I_COUNT` піднімай обережно.

## references
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Script Setup and Use Examples — ArduPilot | https://ardupilot.org/copter/docs/common-scripting-step-by-step.html | primary | A
- AP_Scripting applets (GitHub) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Scripting/applets | primary | A

## checklist
- Скриптинг увімкнено в SITL, тестовий скрипт відповідає на тумблер
- Applet відмови мотора налаштовано й перевірено на octa-quad
- Кожен хаос-скрипт сидить на своєму тумблері
- Розумію, чому на F4 скриптингу нема
- Скрипти з `SIM_*` не трафляють на реальний апарат
