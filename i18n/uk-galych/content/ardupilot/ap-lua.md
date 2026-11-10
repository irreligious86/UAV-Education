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

## diagnostics
- **Симптом:** скрипт не запускається, у GCS тиша
  - Можлива причина: `SCR_ENABLE` не ввімкнено або не було перезавантаження, файл не в тій папці.
  - Що зробити: перевір параметр і шлях `scripts/` відносно папки, звідки запущено SITL.
- **Симптом:** pre-arm помилка про пам'ять скриптів
  - Можлива причина: замало `SCR_HEAP_SIZE` для завантажених скриптів.
  - Що зробити: підніми `SCR_HEAP_SIZE` або прибери зайві скрипти.
- **Симптом:** усі скрипти стали посеред польоту
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
