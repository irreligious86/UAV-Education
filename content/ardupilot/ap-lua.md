---
id: ap-lua
title: "Lua: сценарии и fault injection"
level: L3
readingTime: 35 мин
firmware: ArduPilot 4.7 (сверено с 4.7.3; лабораторная снята на SITL 4.7.2)
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
- Память для скриптов задаёт `SCR_HEAP_SIZE`. Мало — в 4.7 прошивка сама расширяет heap кусками по 20 КБ и пишет `Required SCR_HEAP_SIZE over N`; это сообщение хранится как ошибка скриптинга и блокирует арм (`Scripting: Required SCR_HEAP_SIZE over N`) — подними `SCR_HEAP_SIZE` до N с запасом. Если расширение невозможно или выключено битом 6 `SCR_DEBUG_OPTS`, скрипты падают с `out of memory`. Много — может не инициализироваться EKF.
- Если один скрипт упал с ошибкой (в том числе с нехваткой памяти внутри своего вызова), снимается только он. Все скрипты стоят, только если упала сама Lua-машина (`Lua: Engine Error …`, затем `Scripting: stopped`) — до перезапуска скриптинга.
- Скриптинг собирается только для плат с флешем больше 1 МБ (`AP_Scripting_config.h`): на F405/F411 с 1 МБ его нет, F427/F429 с 2 МБ (Pixhawk 1, Cube Black), F7 и H7 — с ним.

### Паттерн update()
Скрипт — это функция `update()`, которая делает работу и возвращает себя и задержку в миллисекундах до следующего вызова. Никаких бесконечных циклов: планировщик сам вызывает функцию снова.

Как это устроено внутри (`libraries/AP_Scripting/lua_scripts.cpp`, Copter-4.7.2). Все скрипты живут в одном потоке и одной Lua-машине с общей памятью `SCR_HEAP_SIZE`. Планировщик держит список скриптов, упорядоченный по времени следующего запуска, берёт ближайший и вызывает его функцию в защищённом режиме. После возврата он проверяет, что вернулись ровно два значения — функция и число, и ставит следующий запуск на `время начала вызова + задержка` (строка `next_run_ms = start_time_ms + …`). Отсюда три следствия:

- задержка — это **минимум**, а не период: в прогоне практики скрипт с `return update, 100` вызывался в среднем раз в ≈ 113 мс (112.8 мс в выводе шага 6; SITL, ускорение 5×). Для логики «раз в 0.1 с» это нормально; для измерений по времени бери `millis()`, а не счётчик вызовов;
- один вызов ограничен `SCR_VM_I_COUNT` инструкциями виртуальной машины (по умолчанию 10000); превысил — сообщение `<имя>.lua exceeded time limit`, скрипт снимается. Тяжёлую работу дели на порции между вызовами;
- если вызов вернул одно или больше двух значений либо не те типы, скрипт тоже снимается — с сообщением `did not return a delay` / `returned bad result count`, и это блокирует арм; `return` без значений — штатное завершение одноразового скрипта: он снимается молча, без сообщения и без блокировки арма.

### Ошибка в скрипте: что именно ломается
Ошибка выполнения (обращение к `nil`, неверный тип аргумента) **не** роняет прошивку и не останавливает другие скрипты, но снимает этот скрипт до перезагрузки. Последствия видны в прогоне шага 6: в GCS идёт `Lua: ./scripts/bad.lua:2: attempt to index a nil value (local 't')` — первый раз с важностью CRITICAL, дальше повтор раз в 10 с с важностью DEBUG, не больше 10 раз (сам текст остаётся для проверки арма). Арм блокируется сразу после ошибки; строку `PreArm: Scripting: …` GCS получает раз в 30 с — это период отчёта pre-arm, поэтому в прогоне она пришла на 30.3 с. Попытка арма получает `COMMAND_ACK` с результатом 4 (FAILED) и текстом `Arm: Scripting: …`. Это сделано специально: упавший скрипт мог быть защитой, и лететь без неё нельзя. Проверку можно выключить битом 4 `SCR_DEBUG_OPTS`, но для скрипта-защиты это значит лететь без защиты и не знать об этом.

Скрипты читаются только при старте. Новый или исправленный файл подхватывается после перезагрузки, по команде `MAV_CMD_SCRIPTING` (42701) с `param1 = 3` (`SCRIPTING_CMD_STOP_AND_RESTART`), тумблером `RCx_OPTION = 316` (Stop-Restart Scripting) или переключением `SCR_ENABLE` 0 → 1 — это перезапуск всей Lua-машины без перезагрузки полётника. Прошивка не проверяет, заармлен ли аппарат, поэтому правило курса — перезапускать скрипты только на земле: на время перезапуска все скриптовые защиты выключены (ориентир курса).

{{diagram:lua-script-lifecycle|Скрипт перепланируется, пока update() возвращает функцию и задержку; любая ошибка снимает его до перезагрузки и блокирует арм через PreArm: Scripting.}}

### Свои параметры и свои лог-сообщения
Скрипт может завести собственные параметры, которые видны в GCS и сохраняются, как обычные: `param:add_table(key, "FLT_", 2)` резервирует таблицу с префиксом (ключ — свой номер таблицы, у каждого скрипта разный), `param:add_param(key, 1, "DELAY", 5)` создаёт `FLT_DELAY` со значением по умолчанию 5. Значение, изменённое через `param set FLT_DELAY 7`, сохраняется в хранилище и переживает перезапуск, если скрипт заводит таблицу с тем же ключом и префиксом; прогон шага 6 этого не проверяет (там `FLT_*` не менялись), проверь сам: измени, перезапусти SITL без `-w`, прочитай (вывод из документации и кода). Префикс выбирай уникальным — два скрипта с одним префиксом не уживутся. `logger:write("FLT", "Alt,Mask", "fi", "m-", "0-", alt, mask)` пишет в `.BIN` своё сообщение `FLT` (имя до 4 символов, формат как в `AP_Logger`: `f` — float, `i` — int32) — его потом видно рядом с `RCOU` и `CTUN` в анализаторе логов.

### Справочник: параметры SCR_* (ArduPilot 4.7.2)
Источник — `libraries/AP_Scripting/AP_Scripting.cpp:65–200`, тег Copter-4.7.2.

| Параметр | По умолчанию | Что делает | Когда трогать |
|---|---|---|---|
| `SCR_ENABLE` | 0 | 1 — Lua; нужна перезагрузка | всегда первым |
| `SCR_HEAP_SIZE`, байт | 204800 на SITL/Linux и платах класса памяти ≥ 1000 КБ (H7); 102400 при ≥ 500 КБ; 44032 иначе | память всех скриптов | `Required SCR_HEAP_SIZE over N` — поставить N с запасом 20–50 КБ (ориентир курса) |
| `SCR_VM_I_COUNT` | 10000 | лимит инструкций на один вызов | `exceeded time limit` — сначала дробить работу, потом поднимать |
| `SCR_DEBUG_OPTS` | 0 | биты: 0 — сообщать «No scripts to run», когда все скрипты остановлены, 1 — сообщения о памяти и времени, 2 — не логировать скрипты, 3 — логировать память и время, 4 — выключить pre-arm проверку, 5 — сохранить CRC скриптов в `SCR_LD_CHECKSUM`/`SCR_RUN_CHECKSUM`, 6 — не расширять heap при нехватке | отладка; бит 4 — только осознанно |
| `SCR_DIR_DISABLE` | 0 | биты: 0 — не грузить из ROMFS, 1 — не грузить из `APM/scripts` | скрипты, вшитые в прошивку, без SD |
| `SCR_USER1…6` | 0 | свободные числа для скриптов | быстрые настройки без своей таблицы |
| `SCR_LD_CHECKSUM`, `SCR_RUN_CHECKSUM` | −1 (выкл.) | ожидаемая CRC загруженных / работающих скриптов, иначе pre-arm | аппарат в эксплуатации: никто не подложил чужой скрипт |
| `SCR_THD_PRIORITY` | 0 (Normal) | приоритет потока скриптинга | скрипты для драйверов (UART, CAN) |
| `RCx_OPTION` | 300…315, 316 | Scripting1…Scripting16 (в 4.6 — 300…307); 316 — Stop-Restart Scripting | тумблер для скрипта; аварийный перезапуск скриптинга |

### Привязка к тумблеру
Параметр `RCx_OPTION` назначает каналу пульта функцию. Значения 300–315 — Scripting1…Scripting16 (в 4.6 — только 300–307): зарезервированы для скриптов. Скрипт находит свой канал через `rc:find_channel_for_option(300)` и читает положение тумблера через `get_aux_switch_pos()` (0 — низ, 1 — середина, 2 — верх).

### Applets и examples
В репозитории ArduPilot есть готовые скрипты: `libraries/AP_Scripting/applets` (готовы к использованию, у каждого есть `.md`-описание) и `libraries/AP_Scripting/examples` (учебные примеры). Начинать стоит с applet `motor_failure_test.lua`: он останавливает моторы, заданные битовой маской `MOT_STOP_BITMASK`, когда тумблер Scripting1 вверх. Октокоптер должен лететь на одном отказавшем моторе.

### Что умеет API (по `docs/docs.lua` в AP_Scripting)
Чтение состояния: `ahrs:get_position()`, `ahrs:get_velocity_NED()`, `ahrs:get_yaw()`, `gps:num_sats()`, `battery:voltage()`, `rangefinder:distance_orient()` (в метрах; `distance_cm_orient` устарел), `esc_telem:get_rpm()`, `vehicle:get_mode()`, `arming:is_armed()`; действие: `vehicle:set_mode()`, `vehicle:set_target_velocity_NED()`, `vehicle:set_target_location()`, `mission:set_current_cmd()`, `SRV_Channels:set_output_pwm()`, `relay:on()`, `param:set()`/`param:add_param()` (свои параметры с префиксом), `gcs:send_text()`, `logger:write()` (свои лог-сообщения!), `notify:play_tune()`, `rc:get_aux_cached()` (тумблер `RCx_OPTION = 300..315` Scripting1..16; в 4.6 — 300..307), `serial:find_serial()` (свой протокол на UART), `CAN:get_device()` (DroneCAN), `periph` на AP_Periph. Таймеры — возврат `update, 100` (мс до следующего вызова). Параметры скриптинга: `SCR_ENABLE`, `SCR_HEAP_SIZE` (память; дефолт по классу памяти платы — 43, 100 или 200 КБ: на F427/F429 скрипты работают, но heap мал; с запасом — F7/H7), `SCR_VM_I_COUNT` (лимит инструкций на вызов — защита от зависания), `SCR_DEBUG_OPTS`.

### Applets как учебник
`libraries/AP_Scripting/applets/` — готовые, с `.md`-описанием: `motor_failure_test.lua` (останавливает моторы по битмаске `MOT_STOP_BITMASK` тумблером Scripting1 — тест отказа мотора на гексе/X8 в SITL и в поле), `VTOL-quicktune.lua` (QuikTune для мультикоптеров и VTOL), `rover-quicktune.lua`, `copter-deadreckon-home.lua` (возврат по счислению при потере GPS), `arming-checks.lua` (свои пред-армовые проверки), `ahrs-source-extnav-optflow.lua` (переключение источников EKF по качеству), `BattEstimate.lua`, `MissionSelector.lua`, `net_webserver.lua`, `crsf-calibrate.lua` (появился в 4.7, в 4.6.3 его нет), `SmartAudio.lua`. Три applet'а для поля — все на тумблере, все есть и в 4.6.3, и в 4.7.2:

| Applet | Тумблер | Что делает | Когда брать |
|---|---|---|---|
| `leds_on_a_switch.lua` | `RCx_OPTION = 300` (Scripting1) | пишет `NTF_LED_BRIGHT`: низ — 0 (выкл), середина — 1, верх — 3 (максимум) | ночью или на съёмке светодиоды надо гасить в полёте (`ap-notify`) |
| `revert_param.lua` | `PREV_RC_FUNC` (по умолчанию 300), включение `PREV_ENABLE = 1` | тумблер вверх возвращает значения, которые были при загрузке, для `ATC_RAT_*`, `ATC_ANG_*_P`, `ATC_RATE_*_MAX`, `INS_HNTCH_*`, `INS_GYRO_FILTER` (у QuadPlane — `Q_A_*`; у крыла — `RLL_RATE_*`, `PTCH_RATE_*`, `*2SRV_TCONST`, TECS); при старте пишет `Stored N parameters`, при откате — `Reverted N parameters`. `revert_param.md` обещает и `PSC_D_*`/`PSC_NE_*`, но код 4.7.2 ищет старые имена (`PSC_ACCZ_*`, `PSC_VELXY_*`), которых в 4.7 нет, поэтому контур положения не откатывается — проверь по числу в `Stored N` | ручная подстройка в полёте крутилкой `TUNE` или из GCS: тумблер — откат, если пошла раскачка (`ap-aux-tune`) |
| `Param_Controller.lua` | `RCx_OPTION = 302` (Scripting3) | грузит файл `params.param` из `scripts/1`, `scripts/2` или `scripts/3` по положению тумблера (низ, середина, верх); изменения не сохраняются после перезагрузки | несколько наборов параметров (с грузом и без) на одном аппарате |

Правило: два applet'а на одной функции `RCx_OPTION` (оба по умолчанию на 300) делят тумблер — переназначь одному из них функцию (`PREV_RC_FUNC = 301` и `RCx_OPTION = 301` на другом канале). Проверка после установки: перезагрузка, обновить список параметров (появились `PREV_*`), щелчок тумблера даёт сообщение или изменение параметра. Читать их — лучший способ выучить API и стиль (защитные проверки, `pcall`-подобные обёртки, параметры через `param:add_table`).

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

### Когда скрипт, а когда нет
Правило выбора (ориентир курса). Lua подходит для логики, которой хватает реакции за сотни миллисекунд: защиты по температуре, напряжению, геометрии, переключение наборов параметров, свои сообщения в лог, fault injection в SITL. Не подходит для всего, что должно работать в каждом цикле регулятора: период вызова не гарантирован (в прогоне — ≈ 113 мс вместо 100), а упавший скрипт снимается целиком. Если защита записана в FMEA как мера, у неё должен быть тест вне полёта (шаг 5) и проверка, что после загрузки она действительно работает — сообщение при старте и проверка арма. Если логике нужна камера, карта или тяжёлые вычисления — это работа компаньон-компьютера по MAVLink (`ap-companion`), а не скрипта.

{{diagram:lua-runtime|Как исполняется скрипт: файл из APM/scripts/ в Lua VM, update() возвращает себя и период; вызов защищён (pcall), поэтому ошибка не роняет прошивку, но сам скрипт снимается; действия идут через привязки API.}}

### Место в системе

- **Получает:** положение тумблера через `RCx_OPTION = 300…315`; состояние аппарата через API — `ahrs`, `battery`, `esc_telem` (телеметрия ESC — `f-motors-esc`); ресурсы платы: флеш больше 1 МБ и память `SCR_HEAP_SIZE` (`ap-intro`).
- **Отдаёт:** fault injection — остановку моторов для проверки X8 (`ap-heavy`) и сценариев в `ap-sitl`; свои защиты вроде температуры ESC — как меру в FMEA (`ap-safety-fs`); QuikTune — шагу 5 тюнинга (`ap-tuning`).
- **Если ошибиться здесь:** завысил `SCR_HEAP_SIZE` → может не инициализироваться EKF → аппарат не армится, и причину ищут в навигации (`ap-ekf`). Занизил → скрипт падает, и защита, записанная в FMEA как мера, в момент отказа не работает (`ap-safety-fs`).

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

### Шаг 6. Fault injection по таймеру — прогон в SITL
Этот шаг выполнен на ArduCopter 4.7.2 SITL (рама `hexa`, `--speedup 5`, pymavlink 2.4.50) без MAVProxy. Скрипт `fault_inject.lua` заводит свои параметры `FLT_DELAY` (с) и `FLT_MASK` (битовая маска моторов), раз в 50 вызовов сообщает средний период вызова, а через `FLT_DELAY` секунд после подъёма выше 8 м записывает `SIM_ENGINE_MUL = 0` и `SIM_ENGINE_FAIL = FLT_MASK` — моторы из маски перестают давать тягу — и пишет в лог своё сообщение `FLT`. Скрипт только для SITL: на реальном аппарате параметров `SIM_*` нет, `param:set` вернёт false.

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

Обвязка на Python делает два запуска. Первый — с дополнительным `scripts/bad.lua`, который на третьем вызове обращается к `nil`: так видно, что ошибка одного скрипта делает с армом. Второй — без него и без `-w`, как после обычной перезагрузки аппарата (`SCR_ENABLE` приходит из `lua.parm` в обоих запусках); взлёт на 15 м, ожидание отказа, 25 с наблюдения. Запуск: `mkdir -p run/scripts && cp fault_inject.lua run/scripts/ && cd run && python3 ../lua_lab.py ~/ardupilot`.

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

Вывод прогона (2026-11-26; время в квадратных скобках — по часам прошивки, после перезапуска отсчёт начинается заново, поэтому первые строки второго запуска ещё несут время первого):

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

Что читать в выводе. Первый запуск: `fault_inject.lua` загрузился (`FLT: loaded`) и работает, `bad.lua` упал на третьем вызове (5.3 с), ошибка повторяется раз в 10 с, арм заблокирован (строка `PreArm: Scripting` пришла с очередным отчётом на 30.3 с), попытка арма отклонена с результатом 4. Второй запуск: ошибок нет, арм прошёл; на 14.9 м скрипт отключил мотор 1, ШИМ всех шести моторов в этот момент 1594–1595 мкс. Через 3 с прошивка сообщила `Potential Thrust Loss (1)`. В снимке ШИМ мотор 1 упирается в 1950 мкс (команда есть, тяги нет), остальные четыре — 1862–1915 мкс, а противоположный ему мотор 2 (рама Hexa Plus: `copter-hexa.parm` задаёт только `FRAME_CLASS 2`, `FRAME_TYPE` 0 из `copter.parm`; мотор 1 — нос, 2 — хвост) — 1207 мкс: регулятор гасит тангаж и рыскание. Снимок сделан через 25 с после отказа, уже после касания земли; чтобы увидеть картину в полёте, снимай ШИМ через 2–5 с после отказа. Высоту эта модель гексы не удержала и через 24 с после отказа коснулась земли на 1.6 м/с — мягкая посадка, а не падение. Вывод для проекта: шестимоторник в этой модели переживает отказ мотора как управляемое снижение, а не как висение; для «долетим на отказе» нужен запас тяги или восьмимоторник (`ap-heavy`).

Самопроверка: лабораторная выполнена, когда в шаге 2 каждый щелчок тумблера даёт ровно одну строку `Scripting2 -> …`; в шаге 3 появился `MOT_STOP_BITMASK`; шаг 5 проходит `pytest` до и после твоей правки; в шаге 6 первый запуск отклоняет арм с результатом 4 и текстом `Scripting: ./scripts/bad.lua:2`, второй армится, сообщает `FLT: motors mask 1 cut at` на высоте 13–16 м (взлёт на 15 м; через 5 с после прохода 8 м аппарат уже на 15 м), средний период вызова лежит в 100–120 мс, а в снимке ШИМ после отказа мотор 1 стоит на 1950 мкс, хотя бы один из исправных — выше 1850 мкс, а мотор 2 — ниже 1400 мкс.

**Эталон для самопроверки.** Шаг 2: при каждом щелчке тумблера в сообщениях GCS появляется строка `Scripting2 -> <положение> (ARMED или disarmed)`; если вместо неё раз в 5 с идёт `switch_report: no channel with RCx_OPTION=301` — тумблер не назначен (`RC9_OPTION 301`) или SITL не перезапущен. Шаг 3: после перезагрузки появился параметр `MOT_STOP_BITMASK`; нет его — applet не лежит в `scripts/` или `SCR_ENABLE` не равен 1. Шаг 5: `python -m pytest -q examples/lua-protection/tests` проходит до твоих правок и после них, а у третьей защиты есть собственный тест, который падает, если её логику убрать. Шаг 6: типичные неверные результаты — (1) `FLT_DELAY` не появился: в `scripts/` нет файла или `SCR_ENABLE` не 1 в момент старта (параметр подействовал бы только после перезапуска); (2) отказ не наступает: аппарат не поднялся выше 8 м или не заармлен — скрипт ждёт оба условия; (3) во втором запуске арм снова отклонён — `bad.lua` остался в `scripts/`; (4) `FLT_DELAY` сбросился к 5 после твоей правки — второй запуск сделан с `-w`, который стёр `eeprom.bin`.

## diagnostics
- **Симптом:** скрипт не запускается, в GCS тишина
  - Возможная причина: `SCR_ENABLE` не включён или не было перезагрузки, файл не в той папке.
  - Что сделать: проверить параметр и путь `scripts/` относительно папки запуска SITL.
- **Симптом:** pre-arm ошибка о памяти скриптов
  - Возможная причина: мало `SCR_HEAP_SIZE` для загруженных скриптов.
  - Что сделать: поднять `SCR_HEAP_SIZE` или убрать лишние скрипты.
- **Симптом:** все скрипты перестали работать посреди полёта
  - Возможная причина: упала Lua-машина (`Lua: Engine Error …`, затем `Scripting: stopped`) или скриптинг перезапущен; ошибка одного скрипта снимает только его.
  - Что сделать: читать сообщения в GCS, исправить скрипт, перезапустить скриптинг (перезагрузка, `MAV_CMD_SCRIPTING`, `RCx_OPTION = 316`, `SCR_ENABLE` 0 → 1).
- **Симптом:** `find_channel_for_option` возвращает nil
  - Возможная причина: ни одному каналу не назначен нужный `RCx_OPTION`.
  - Что сделать: назначить опцию на канал с тумблером.
- **Симптом:** арм отклонён с `PreArm: Scripting: ./scripts/<имя>.lua:<строка>: …`
  - Возможная причина: скрипт упал с ошибкой выполнения и снят; прошивка не даёт лететь без него.
  - Что сделать: исправить строку из сообщения, перезагрузить или `MAV_CMD_SCRIPTING` с `param1 = 3`; бит 4 `SCR_DEBUG_OPTS` не трогать, если скрипт — защита.
  - Что видно в логе: сообщение `Lua: …` повторяется в GCS раз в 10 с (важность DEBUG, до 10 раз).
- **Симптом:** `add_table failed` при старте скрипта
  - Возможная причина: ключ таблицы или префикс уже занят другим скриптом, или префикс длиннее допустимого.
  - Что сделать: дать скрипту свой ключ `param:add_table` и уникальный префикс; проверить `param show <префикс>*`.
- **Симптом:** скрипт «тормозит»: `return update, 100`, а реакция заметно реже
  - Возможная причина: задержка — минимум, а не период; много скриптов или тяжёлый вызов растягивают очередь.
  - Что сделать: мерить реальный период через `millis()` (в прогоне ≈ 113 мс на 100 мс); критичное по времени не делать в Lua.
- **Симптом:** скрипт не запускается, «Lua: … out of memory»
  - Возможная причина: `SCR_HEAP_SIZE` мал, плата без запаса RAM.
  - Что сделать: увеличить heap (H7 — 200–300 КБ, ориентир курса), проверить, не выключено ли расширение битом 6 `SCR_DEBUG_OPTS`, упростить скрипт.
- **Симптом:** «<имя>.lua exceeded time limit»
  - Возможная причина: тяжёлый цикл в одном вызове update.
  - Что сделать: разбить работу по вызовам, `SCR_VM_I_COUNT` поднимать осторожно.

## references
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Script Setup and Use Examples — ArduPilot | https://ardupilot.org/copter/docs/common-scripting-step-by-step.html | primary | A
- AP_Scripting applets (GitHub) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Scripting/applets | primary | A
- Lua bindings reference — docs/docs.lua, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Scripting/docs/docs.lua | primary | A
- SCR_* parameters — AP_Scripting.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Scripting/AP_Scripting.cpp | primary | A
- Script scheduler and error handling — lua_scripts.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Scripting/lua_scripts.cpp | primary | A

## checklist
- Скриптинг включён в SITL, тестовый скрипт отвечает на тумблер
- Applet отказа мотора настроен и проверен на octa-quad
- Каждый хаос-скрипт на своём тумблере
- Понимаю, почему на F405 (1 МБ флеша) скриптинга нет
- Скрипты с `SIM_*` не попадают на реальный аппарат
- Знаю, почему упавший скрипт блокирует арм и как его перезапустить
- Свои параметры скрипта заведены через `param:add_table` с уникальным префиксом
