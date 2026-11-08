---
id: ap-lua
title: "Lua: сценарии и fault injection"
level: L3
readingTime: 25 мин
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
---

## summary
ArduPilot умеет выполнять Lua-скрипты прямо на полётнике: добавлять режимы, читать датчики, реагировать на тумблеры. В учебном проекте главное применение — fault injection: специально ломать мотор или сенсор в SITL и смотреть, как дрон и ты справляетесь. Модуль объясняет, как работает скриптинг, как привязать скрипт к тумблеру пульта и как построить набор «хаос-скриптов», каждый на своём тумблере.

## theory
### Как устроен скриптинг
- Включается параметром `SCR_ENABLE = 1` и перезагрузкой.
- Скрипты (`.lua`) лежат в `APM/scripts` на SD-карте; в SITL — в папке `scripts` там, откуда запущен симулятор.
- Каждый скрипт работает в своей «песочнице» и с низким приоритетом: полётный код важнее, точного расписания скрипту никто не обещает.
- Память для скриптов задаёт `SCR_HEAP_SIZE`. Мало — скрипты падают и появляется pre-arm ошибка о нехватке памяти. Много — может не инициализироваться EKF.
- Если один скрипт упал с ошибкой, останавливается только он. Если кончилась общая память скриптов (или паника), останавливаются все скрипты до перезагрузки.
- Скриптинг требует минимум 2 МБ флеша и не работает на F4-контроллерах.

### Паттерн update()
Скрипт — это функция `update()`, которая делает работу и возвращает себя и задержку в миллисекундах до следующего вызова. Никаких бесконечных циклов: планировщик сам вызывает функцию снова.

### Привязка к тумблеру
Параметр `RCx_OPTION` назначает каналу пульта функцию. Значения 300–307 — Scripting1…Scripting8: зарезервированы для скриптов. Скрипт находит свой канал через `rc:find_channel_for_option(300)` и читает положение тумблера через `get_aux_switch_pos()` (0 — низ, 1 — середина, 2 — верх).

### Applets и examples
В репозитории ArduPilot есть готовые скрипты: `libraries/AP_Scripting/applets` (готовы к использованию, у каждого есть `.md`-описание) и `libraries/AP_Scripting/examples` (учебные примеры). Начинать стоит с applet `motor_failure_test.lua`: он останавливает моторы, заданные битовой маской `MOT_STOP_BITMASK`, когда тумблер Scripting1 вверх. Октокоптер должен лететь на одном отказавшем моторе.

### Что умеет API (по `docs/docs.lua` в AP_Scripting)
Чтение состояния: `ahrs:get_position()`, `ahrs:get_velocity_NED()`, `ahrs:get_yaw()`, `gps:num_sats()`, `battery:voltage()`, `rangefinder:distance_orient()` (в метрах; `distance_cm_orient` устарел), `esc_telem:get_rpm()`, `vehicle:get_mode()`, `arming:is_armed()`; действие: `vehicle:set_mode()`, `vehicle:set_target_velocity_NED()`, `vehicle:set_target_location()`, `mission:set_current_cmd()`, `SRV_Channels:set_output_pwm()`, `relay:on()`, `param:set()`/`param:add_param()` (свои параметры с префиксом), `gcs:send_text()`, `logger:write()` (свои лог-сообщения!), `notify:play_tune()`, `rc:get_aux_cached()` (тумблер `RCx_OPTION = 300..307` Scripting1..8), `serial:find_serial()` (свой протокол на UART), `CAN:get_device()` (DroneCAN), `periph` на AP_Periph. Таймеры — возврат `update, 100` (мс до следующего вызова). Параметры скриптинга: `SCR_ENABLE`, `SCR_HEAP_SIZE` (память; на F4 не хватает → только H7/F7 с запасом), `SCR_VM_I_COUNT` (лимит инструкций на вызов — защита от зависания), `SCR_DEBUG_OPTS`.

### Applets как учебник
`libraries/AP_Scripting/applets/` — готовые, с `.md`-описанием: `motor_failure_test.lua` (останавливает моторы по битмаске `MOT_STOP_BITMASK` тумблером Scripting1 — тест отказа мотора на гексе/X8 в SITL и в поле), `VTOL-quicktune.lua` (QuikTune для мультикоптеров и VTOL), `rover-quicktune.lua`, `copter-deadreckon-home.lua` (возврат по счислению при потере GPS), `arming-checks.lua` (свои пред-армовые проверки), `ahrs-source-extnav-optflow.lua` (переключение источников EKF по качеству), `BattEstimate.lua`, `MissionSelector.lua`, `net_webserver.lua`, `crsf-calibrate.lua`, `SmartAudio.lua`. Читать их — лучший способ выучить API и стиль (защитные проверки, `pcall`-подобные обёртки, параметры через `param:add_table`).

### Разобранный пример: защита по температуре ESC
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
Проверка в SITL: `SIM_ESC_TELEM = 1`, подменить порог на 30 °C, убедиться в срабатывании; затем — на стенде. Запись в FMEA как мера с ссылкой на тест (модуль «Отказоустойчивость»).

{{diagram:lua-runtime|Как исполняется скрипт: файл из APM/scripts/ в Lua VM, update() возвращает себя и период, ошибки ловит pcall, действия идут через привязки API.}}

## practice
### Шаг 1. Включить скриптинг в SITL
```
param set SCR_ENABLE 1
reboot
```

### Шаг 2. Скрипт-индикатор на тумблере
Минимальный скрипт: сообщает в GCS об изменении положения тумблера Scripting2 и о состоянии арма.

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

Положи файл в `scripts/`, назначь тумблер (`param set RC9_OPTION 301`), перезапусти SITL и пощёлкай тумблером.

### Шаг 3. Отказ мотора по тумблеру
1. Скопируй applet `motor_failure_test.lua` в `scripts/`.
2. Назначь тумблер на Scripting1: `RCx_OPTION = 300`.
3. После перезагрузки появится `MOT_STOP_BITMASK`. Поставь 1 — будет отключаться мотор 1.
4. В SITL с рамой `octa-quad`: взлёт, LOITER, тумблер вверх. Смотри, как дрон компенсирует отказ.

### Шаг 4. Набор хаос-скриптов
Идея учебного набора: каждый «отказ» — отдельный скрипт на своём тумблере, чтобы включать их независимо:

- индикатор арма (светодиод или сообщение);
- ручной отказ мотора (applet);
- случайные отказы сенсоров через параметры симулятора `SIM_*`;
- случайный отказ 1–3 моторов.

Имена параметров `SIM_*` меняются между версиями — смотри актуальные в своей сборке командой `param show SIM_GPS*` в MAVProxy. Такие скрипты — только для SITL: на реальном аппарате `SIM_*` параметров нет.

### Шаг 5. Защита с тестами до SITL
Стартер проекта №11 `examples/lua-protection`: `guard.lua` — защита по вибрациям (LAND), удержание внутри полигона с запасом (RTL) и обёртка `pcall`, которая после трёх ошибок подряд в воздухе уводит аппарат в RTL. Тесты запускают **этот же** Lua-файл через `lupa` против заглушки привязок (`millis`, `ahrs`, `vehicle`, `param`, `gcs`, `logger`) — ошибки логики ловятся за доли секунды, а SITL остаётся приёмочным тестом. Запусти `python -m pytest -q examples/lua-protection/tests`, затем добавь третью защиту (например, просадка напряжения под нагрузкой) вместе с тестом.

## diagnostics
- **Симптом:** скрипт не запускается, в GCS тишина
  - Возможная причина: `SCR_ENABLE` не включён или не было перезагрузки, файл не в той папке.
  - Что сделать: проверить параметр и путь `scripts/` относительно папки запуска SITL.
- **Симптом:** pre-arm ошибка о памяти скриптов
  - Возможная причина: мало `SCR_HEAP_SIZE` для загруженных скриптов.
  - Что сделать: поднять `SCR_HEAP_SIZE` или убрать лишние скрипты.
- **Симптом:** все скрипты перестали работать посреди полёта
  - Возможная причина: один скрипт упал с ошибкой или исчерпал память.
  - Что сделать: читать сообщения в GCS, исправить скрипт, перезагрузить.
- **Симптом:** `find_channel_for_option` возвращает nil
  - Возможная причина: ни одному каналу не назначен нужный `RCx_OPTION`.
  - Что сделать: назначить опцию на канал с тумблером.
- **Симптом:** скрипт не запускается, «Lua: … out of memory»
  - Возможная причина: `SCR_HEAP_SIZE` мал, плата без запаса RAM.
  - Что сделать: увеличить heap (H7 — 200–300 КБ), упростить скрипт.
- **Симптом:** «<имя>.lua exceeded time limit»
  - Возможная причина: тяжёлый цикл в одном вызове update.
  - Что сделать: разбить работу по вызовам, `SCR_VM_I_COUNT` поднимать осторожно.

## references
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Script Setup and Use Examples — ArduPilot | https://ardupilot.org/copter/docs/common-scripting-step-by-step.html | primary | A
- AP_Scripting applets (GitHub) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Scripting/applets | primary | A

## checklist
- Скриптинг включён в SITL, тестовый скрипт отвечает на тумблер
- Applet отказа мотора настроен и проверен на octa-quad
- Каждый хаос-скрипт на своём тумблере
- Понимаю, почему на F4 скриптинга нет
- Скрипты с `SIM_*` не попадают на реальный аппарат
