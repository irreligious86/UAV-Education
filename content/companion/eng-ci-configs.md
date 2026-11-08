---
id: eng-ci-configs
title: "CI и версионирование конфигов и кода"
level: L3
readingTime: 35 мин
firmware: Betaflight · ArduPilot
status: published
added: 2026-11-08
tags:
  - git
  - CI
  - diff all
  - SITL
  - ревью
related:
  - bf-cli-automation
  - ap-sitl
  - tools-overview
  - eng-method-101
next:
  - eng-systems
---

## summary
Конфигурация дрона — код: от неё зависит, полетит ли он. Значит, к ней применимо всё, что инженеры давно делают с кодом: история изменений с объяснением, ревью перед применением, автоматическая проверка, релизы и откат. Модуль ставит это для одного аппарата или парка: `diff all` Betaflight и `.param` ArduPilot в git с осмысленными коммитами, pull request как форма ревью, GitHub Actions с SITL-автотестом (миссия/failsafe), линтеры для скриптов и схемы для конфигов, теги релизов и журнал изменений. Лабораторная: CI, который падает, если failsafe сломан.

## theory
### Что хранить
```
fleet/
  viking7/
    README.md              # что за аппарат, железо, версия прошивки
    betaflight/diff-all.txt  # diff all после каждого изменения
    ardupilot/params.param   # полный список параметров (Mission Planner / mavproxy param save)
    notes/CHANGELOG.md     # что и зачем менялось, датой
    logs/                  # ссылки или small logs по релизам (большие — в Releases/LFS)
  tools/
    export_bf.py           # снимает diff all по MSP/CLI
    check_params.py        # проверки инвариантов
    sitl_test.py           # автотест в SITL
.github/workflows/ci.yml
```
Правила: один коммит — одно изменение с причиной («D roll 38→42: bounce-back 18%→9%, лог 2026-11-08-03»); без причины — не коммит. Бинарные логи — не в репозиторий (Git LFS или релизы).

### Снять конфиг автоматически
Betaflight: по USB в режиме CLI (не MSP: вход в CLI символом `#`) — `diff all` из Python (`pyserial`: `#` → ждать `# ` → `diff all` → читать до `# `), либо через `betaflight-configurator` экспорт. ArduPilot: `mavproxy.py --master=... --cmd="param fetch; param save params.param"` или pymavlink `param_fetch_all` → отсортированный текстовый файл. Сортировка и нормализация (убрать `#` комментарии с датой) — иначе diff шумит.

### Инварианты: проверка конфигов
Скрипт, который читает конфиг и падает на нарушении правил, известных из курса:
- Betaflight: `failsafe_procedure` задан, `failsafe_delay` в разумных пределах, `motor_poles` = 14 для 2207, `dshot_bidir = ON` при rpm_filter, `vbat_min_cell_voltage` ≥ 330, нет `set debug_mode` в полётном профиле.
- ArduPilot: `FS_THR_ENABLE ≠ 0`, `BATT_FS_LOW_ACT ≠ 0`, `FENCE_ENABLE = 1` для полётов по правилам, `RTL_ALT_M` ≥ высота препятствий площадки (в README), `ARMING_SKIPCHK = 0` (до 4.7 — `ARMING_CHECK = 1`), `INS_HNTCH_ENABLE = 1` если notch нужен, `BRD_SAFETY_DEFLT` по политике.
Реализация — JSON Schema/простой Python с таблицей правил; вывод — список нарушений с ссылкой на модуль курса.

### SITL-автотест
ArduPilot в CI (Ubuntu runner): собрать SITL (`./waf configure --board sitl && ./waf copter`) или взять готовый образ; запустить `sim_vehicle.py` без GUI с `--add-param-file params.param`; скрипт pymavlink: арм в Guided, взлёт 10 м, `SIM_RC_FAIL = 1` → ожидать режим RTL/LAND в течение 5 с → `assert`; затем миссия из 4 точек → `assert` достижение. Время — 2–4 минуты. ArduPilot-овский `Tools/autotest` — пример, как это сделано у разработчиков (`autotest.py test.Copter.ThrottleFailsafe`).
Betaflight: SITL-сборка проверяет компиляцию и CLI; для PID-логики — юнит-тесты `make test`. Для конфигов — скрипт инвариантов.

### Линтеры и схемы
Python: `ruff`/`flake8` + `black`; Lua (ArduPilot): `luacheck` с конфигом ArduPilot (`Tools/scripts/run_luacheck.sh` в репозитории ArduPilot — тот же подход); JSON-конфиги — JSON Schema (`check-jsonschema`); YAML — `yamllint`. Всё — в CI на каждый PR.

### Ревью
PR = изменение + причина + доказательство (лог до/после, спектр, число). Чек-лист ревьюера: причина понятна? риск (failsafe, моторы, лимиты)? проверено в SITL/на стенде? откат описан? Для одного человека — self-review: PR с описанием, CI зелёный, мерж через день (эффект «утро вечера мудренее» реален).

### Релизы и откат
Тег `viking7-v12` на коммит, с которым летали; `CHANGELOG.md` по версиям; релиз в GitHub с приложенными `diff all`/`.param` и логом контрольного полёта. Откат — `git checkout viking7-v11 -- viking7/` и загрузка конфига. Прошивка — её версия и сборочный ключ (`version` в CLI Betaflight; `ver` в ArduPilot) в README релиза.

{{diagram:config-ci|Изменение конфига как изменение кода: снять, закоммитить, проверить инварианты и SITL, отрецензировать, выпустить с возможностью отката.}}

## practice
### Шаг 1. Репозиторий
Структура выше; первый коммит — текущие конфиги с README (железо, версии). `.gitattributes` для LFS на `.bin/.BFL`.

### Шаг 2. Экспорт скриптом
`export_bf.py` или `param save` по команде; коммит «snapshot before tuning».

### Шаг 3. Инварианты + CI
`check_params.py` с 5+ правилами; `.github/workflows/ci.yml`: ruff, check_params на всех конфигах. Сломать правило нарочно → CI красный → починить.

### Шаг 4. SITL-тест в CI
Готовая заготовка — в репозитории курса: [examples/sitl-pymavlink](https://github.com/irreligious86/UAV-Education/tree/main/examples/sitl-pymavlink) (`test_failsafe.py` + `ci.yml`). Job с ArduPilot SITL и тестом (RC failsafe → RTL/LAND). Сломать `FS_THR_ENABLE = 0` в `.param` → тест падает. Один PR с изменением параметра, описанием, CI и мержем. Лабораторная: репозиторий с читаемой историей, SITL-тест в CI, одно изменение через PR.

## diagnostics
- **Симптом:** diff all каждый раз отличается целиком
  - Возможная причина: порядок/комментарии/дата в выгрузке.
  - Что сделать: нормализация и сортировка перед коммитом.
- **Симптом:** SITL в CI не стартует/таймаут
  - Возможная причина: сборка долгая, нет `--no-mavproxy`/headless, порты.
  - Что сделать: кэш сборки или готовый образ, headless-запуск, ожидание heartbeat с таймаутом.
- **Симптом:** тест проходит, хотя failsafe сломан
  - Возможная причина: assert проверяет не то (режим не читается) или тест не ждёт.
  - Что сделать: проверить, что тест падает при сломанном конфиге (mutation test).
- **Симптом:** не помню, с каким конфигом летал в тот раз
  - Возможная причина: нет тегов/релизов.
  - Что сделать: тег на каждый полётный конфиг, лог к релизу.

## references
- ArduPilot — Autotest framework (Tools/autotest) | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A
- GitHub Docs — GitHub Actions workflows | https://docs.github.com/fr/actions/writing-workflows | primary | A
- Betaflight — Command Line Interface (CLI) | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A

## checklist
- Конфиги в git с коммитами «что и зачем»
- Экспорт конфигов скриптом, нормализован
- Инварианты проверяются в CI
- SITL-тест failsafe в CI, падает при сломанном конфиге
- Релизы тегами, откат отработан
