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
- Если один скрипт исчерпал память или упал с ошибкой, останавливаются все скрипты до перезагрузки.
- Скриптинг требует минимум 2 МБ флеша и не работает на F4-контроллерах.

### Паттерн update()
Скрипт — это функция `update()`, которая делает работу и возвращает себя и задержку в миллисекундах до следующего вызова. Никаких бесконечных циклов: планировщик сам вызывает функцию снова.

### Привязка к тумблеру
Параметр `RCx_OPTION` назначает каналу пульта функцию. Значения 300–307 — Scripting1…Scripting8: зарезервированы для скриптов. Скрипт находит свой канал через `rc:find_channel_for_option(300)` и читает положение тумблера через `get_aux_switch_pos()` (0 — низ, 1 — середина, 2 — верх).

### Applets и examples
В репозитории ArduPilot есть готовые скрипты: `libraries/AP_Scripting/applets` (готовы к использованию, у каждого есть `.md`-описание) и `libraries/AP_Scripting/examples` (учебные примеры). Начинать стоит с applet `motor_failure_test.lua`: он останавливает моторы, заданные битовой маской `MOT_STOP_BITMASK`, когда тумблер Scripting1 вверх. Октокоптер должен лететь на одном отказавшем моторе.

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
4. В SITL с рамой `octaquad`: взлёт, LOITER, тумблер вверх. Смотри, как дрон компенсирует отказ.

### Шаг 4. Набор хаос-скриптов
Идея учебного набора: каждый «отказ» — отдельный скрипт на своём тумблере, чтобы включать их независимо:

- индикатор арма (светодиод или сообщение);
- ручной отказ мотора (applet);
- случайные отказы сенсоров через параметры симулятора `SIM_*`;
- случайный отказ 1–3 моторов.

Имена параметров `SIM_*` меняются между версиями — смотри актуальные в своей сборке командой `param show SIM_GPS*` в MAVProxy. Такие скрипты — только для SITL: на реальном аппарате `SIM_*` параметров нет.

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

## references
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Script Setup and Use Examples — ArduPilot | https://ardupilot.org/copter/docs/common-scripting-step-by-step.html | primary | A
- AP_Scripting applets (GitHub) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Scripting/applets | primary | A

## checklist
- Скриптинг включён в SITL, тестовый скрипт отвечает на тумблер
- Applet отказа мотора настроен и проверен на octaquad
- Каждый хаос-скрипт на своём тумблере
- Понимаю, почему на F4 скриптинга нет
- Скрипты с `SIM_*` не попадают на реальный аппарат
