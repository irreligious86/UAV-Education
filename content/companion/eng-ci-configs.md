---
id: eng-ci-configs
title: "CI и версионирование конфигов и кода"
level: L3
readingTime: 50 мин
firmware: "Betaflight 4.5.3 / 2025.12.5 · ArduPilot 4.7.2 · GitHub Actions: actions/checkout v7.0.1, actions/setup-python v7.1.0 · yamllint 1.38.0, check-jsonschema 0.39.0"
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
Конфигурация дрона — код: от неё зависит, полетит ли он. Значит, к ней применимо всё, что инженеры давно делают с кодом: история изменений с объяснением, ревью перед применением, автоматическая проверка, релизы и откат. Модуль ставит это для одного аппарата или парка: `diff all` Betaflight и `.param` ArduPilot в git с осмысленными коммитами, манифест парка под JSON Schema, скрипт инвариантов, который знает про переименования параметров между версиями и про «тихие» исправления прошивки, GitHub Actions с версиями действий, закреплёнными по SHA коммита, SITL-автотест failsafe, который грузит именно конфиг парка, pull request как форма ревью, теги релизов и откат. Лабораторная запускается локально теми же командами, что и CI, на настоящих выгрузках: `diff all` из SITL Betaflight 4.5.3 и 1015 параметров из лога ArduCopter 4.7.2 SITL; CI должен покраснеть на сломанном failsafe и позеленеть после починки.

## theory
### Что хранить
```
fleet/                     # repository root: CI runs every path below from here
  fleet.yaml               # manifest: site, craft list, firmware versions, config paths
  schema/fleet.schema.json # JSON Schema for fleet.yaml
  viking2/
    README.md              # что за аппарат, железо, версия прошивки
    betaflight/diff-all.txt  # diff all после каждого изменения
  hex1/
    ardupilot/params.param   # полный список параметров (Mission Planner / mavproxy param save)
    notes/CHANGELOG.md     # что и зачем менялось, датой
  tools/
    export_bf.py           # снимает diff all по MSP/CLI
    check_configs.py       # проверки инвариантов
    sitl_fs_test.py        # автотест failsafe в SITL
  .yamllint
  .github/workflows/config-ci.yml
```
Правила: один коммит — одно изменение с причиной («D roll 38→42: bounce-back 18%→9%, лог 2026-11-08-03»); без причины — не коммит. Бинарные логи — не в репозиторий (Git LFS или релизы).

Манифест `fleet.yaml` — единственное место, где записано, какой аппарат на какой прошивке летает и какой файл — его конфиг. Скрипт проверки берёт оттуда версию прошивки и высоту препятствий площадки, а не угадывает их; поэтому манифест сам проверяется схемой, и опечатка в нём ломает CI раньше, чем дойдёт до проверки конфигов.

### Снять конфиг автоматически
Betaflight: по USB в режиме CLI (не MSP: вход в CLI символом `#`) — `diff all` из Python (`pyserial`: `#` → ждать `# ` → `diff all` → читать до приглашения `\r\n# ` и 0.3 с тишины после него), либо через `betaflight-configurator` экспорт. Плату при этом ищут по `MSP_NAME`, а конец вывода определяют по приглашению и паузе — подробности и грабли в модуле про автоматизацию CLI. ArduPilot: в MAVProxy `param fetch`, дождаться окончания загрузки (команда асинхронная, счётчик полученных параметров в консоли должен дойти до общего числа), затем `param save params.param`; или pymavlink `param_fetch_all` с проверкой, что получено ровно `param_count` параметров, → отсортированный текстовый файл. `param save` сразу после `param fetch` может записать неполный список — тот самый случай «200 строк» ниже. Сортировка и нормализация (убрать `#` комментарии с датой) — иначе diff шумит.

{{lesson:bf-cli-automation|Как надёжно снять diff all скриптом, не потеряв конец вывода и не перезагрузив плату лишний раз, — там.}}

Что считать полным экспортом. В лабораторной параметры ArduCopter взяты из сообщений `PARM` лога SITL 4.7.2: 1370 строк, после удаления 355 параметров симулятора `SIM_*` осталось 1015. Если файл внезапно содержит 200 строк, это не «конфиг стал проще», а оборванная выгрузка, и скрипт проверки должен это ловить (правило «не меньше 300 параметров» — ориентир курса для Copter). Для Betaflight признак целого файла — последняя строка `save` в `diff all`.

### Инварианты: проверка конфигов
Скрипт, который читает конфиг и падает на нарушении правил, известных из курса:
- Betaflight: `failsafe_procedure` задан, `failsafe_delay` в разумных пределах, `motor_poles` = 14 для 2207, `dshot_bidir = ON` при rpm_filter, `vbat_min_cell_voltage` ≥ 330, нет `set debug_mode` в полётном профиле.
- ArduPilot: `FS_THR_ENABLE ≠ 0`, `BATT_FS_LOW_ACT ≠ 0`, `FENCE_ENABLE = 1` для полётов по правилам, `RTL_ALT_M` (метры; до 4.7 — `RTL_ALT`, сантиметры) ≥ высота препятствий площадки (в README), `ARMING_SKIPCHK = 0` (до 4.7 — `ARMING_CHECK = 1`), `INS_HNTCH_ENABLE = 1` если notch нужен, `BRD_SAFETY_DEFLT` по политике.
Реализация — JSON Schema/простой Python с таблицей правил; вывод — список нарушений с ссылкой на модуль курса.

Правило ценно, только если оно знает версию прошивки. Обе версии переименований выше проверены по исходникам ArduCopter 4.7.2: `RTL_ALT_M` объявлен в `ArduCopter/mode_rtl.cpp` с таблицей переноса «RTL_ALT moved to RTL_ALT_M» (умолчание 15 м, `config.h`), `ARMING_SKIPCHK` — в `libraries/AP_Arming/AP_Arming.cpp` (умолчание 0, «нет пропущенных проверок»). Скрипт держит оба имени: если в файле есть `RTL_ALT_M`, берёт его в метрах, иначе `RTL_ALT` делит на 100. Для Betaflight то же самое на другом уровне: строка версии в начале `diff all` (`# Betaflight / <плата> (<id>) 4.5.3 …`) сравнивается с версией в `fleet.yaml`, и если они разные, проверка падает сразу — правила 4.5 к файлу 2025.12 применять бессмысленно. Для 2025.12 отдельное правило ловит `d_min_<ось>`, которого больше нет (теперь `d_max_<ось>` с обратным смыслом).

Второй класс правил — те, что предсказывают «тихие» исправления прошивки. Betaflight при сохранении сам меняет несовместимые комбинации (`validateAndFixConfig()` в `config/config.c`): `failsafe_procedure = GPS-RESCUE` при `feature -GPS` на полётной плате с GPS-сборкой станет `DROP` (`config.c:370`/`:357`, вывод из кода), `d_max` меньше `d_` в 2025.12 обнулится. Такой файл «пройдёт» вставку без единой ошибки, но аппарат будет летать не с тем, что записано в git. Правило в CI должно сказать об этом до заливки: «firmware resets it to DROP on save». В лабораторной оно сработало на настоящем `diff all` 4.5.3.

Пороги в правилах бывают двух сортов, и в выводе их надо различать. Жёсткие — из документации и кода: `FS_THR_ENABLE = 0` выключает реакцию на потерю RC, это не обсуждается. Ориентиры курса — `failsafe_delay` ≤ 20 (2.0 с; единица — 0.1 с, умолчание 15, `flight/failsafe.c`), «не меньше 300 параметров», RTL не ниже препятствий площадки из манифеста. Ориентир записывают в правило с комментарием, откуда он взялся, и меняют осознанно, отдельным коммитом.

### Схемы и линтеры
Схема JSON (JSON Schema, draft 2020-12) описывает, каким должен быть манифест: обязательные поля, `stack` только `betaflight` или `ardupilot`, версия в виде `X.Y.Z`, имя — до 16 символов `[a-z0-9_-]` (как `craft_name`). Проверяет её `check-jsonschema` 0.39.0: `check-jsonschema --schemafile schema/fleet.schema.json fleet.yaml`. У того же инструмента есть встроенные схемы популярных форматов, и одна из них — схема workflow GitHub Actions: `check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml` ловит опечатку в ключе `runs-on` или `steps` локально, до пуша.

`yamllint` 1.38.0 проверяет стиль YAML (отступы, длину строк, дубли ключей). Его правило `truthy` по умолчанию ругается на ключ `on:` в каждом workflow: в YAML 1.1, который читает PyYAML, `on` — это булево `true`, и `yaml.safe_load` действительно возвращает ключ `True` вместо `"on"` (проверено: `['name', True, 'permissions', 'jobs']`). GitHub читает этот ключ правильно, поэтому в `.yamllint` ставят `truthy: {check-keys: false}`, а в своих YAML-файлах значения пишут только как `true`/`false`. С настройками по умолчанию тот же workflow дал 5 замечаний (нет `---`, `on` как truthy, три строки длиннее 80) — их правят в конфиге линтера один раз, а не глушат по месту.

Python: `ruff` (на ноябрь 2026 — 0.17.6) вместо связки `flake8` + `black`; Lua (ArduPilot): `luacheck` с конфигом ArduPilot (`Tools/scripts/run_luacheck.sh` в репозитории ArduPilot — тот же подход). Всё — в CI на каждый PR.

### GitHub Actions: закрепить версии
Workflow — тоже код, который выполняется с правами на твой репозиторий, поэтому версии в нём закрепляют так же строго, как прошивку. Тег вида `@v7` — подвижная ссылка: владелец действия может перевесить его на другой коммит (так работают «плавающие» мажорные теги). Неподвижна только ссылка на полный SHA коммита, рядом в комментарии — человекочитаемая версия. Версии проверены `git ls-remote` по репозиториям действий на 25.11.2026: `actions/checkout` v7.0.1 = `3d3c42e5aac5ba805825da76410c181273ba90b1` (коммит от 17.07.2026; тег `v7` указывает туда же), `actions/setup-python` v7.1.0 = `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` (21.10.2026); оба в `action.yml` объявляют `using: node24`. Остальное закрепляется так же: образ раннера `ubuntu-24.04` вместо `ubuntu-latest`, версии пакетов в `pip install` с `==`, `permissions: contents: read` (job только читает), `timeout-minutes`, чтобы зависший SITL не съедал минуты.

| Что | Версия / значение | Как проверено | Зачем закреплять |
|---|---|---|---|
| `actions/checkout` | v7.0.1, SHA `3d3c42e5…3ba90b1` | `git ls-remote`, `action.yml`: node24 | тег можно перевесить, SHA — нет |
| `actions/setup-python` | v7.1.0, SHA `6d4fd22b…c9ca0e0` | `git ls-remote`, `action.yml`: node24 | то же |
| `runs-on` | `ubuntu-24.04` | метка образа GitHub | `ubuntu-latest` однажды сменит Python и пакеты |
| `yamllint` | 1.38.0 | `pip index versions`, локальный прогон | правила стиля меняются между версиями |
| `check-jsonschema` | 0.39.0 (на `jsonschema` 4.26.0) | `pip index versions`, локальный прогон | встроенные схемы обновляются вместе с ним |
| PyYAML | 6.0.4 | зависимость yamllint; `yaml.safe_load` в скрипте | YAML 1.1: `on` → `True` |
| `ArduCopter` SITL | 4.7.2, `--defaults copter.parm,<aircraft>.param`, `-w` | прогон автотеста ниже | без `-w` в EEPROM остаются старые значения |
| `RTL_ALT_M` / `RTL_ALT` | 4.7 / до 4.7 (см) | `mode_rtl.cpp` | правило должно знать оба имени |
| `ARMING_SKIPCHK` / `ARMING_CHECK` | 4.7 / до 4.7 | `AP_Arming.cpp` | то же |

{{diagram:ci-config-check-chain|Job config-ci — четыре проверки подряд через &&: схема ловит опечатку в манифесте, скрипт инвариантов — сломанный failsafe и diff не той версии; любая красная проверка останавливает слияние.}}

### SITL-автотест
ArduPilot в CI (Ubuntu runner): собрать SITL (`./waf configure --board sitl && ./waf copter`) или взять готовый образ; запустить `sim_vehicle.py` без GUI с `--add-param-file params.param`; скрипт pymavlink: арм в Guided, взлёт 10 м, `SIM_RC_FAIL = 1` → ожидать режим RTL/LAND в течение 5 с → `assert`; затем отдельным прогоном (с `SIM_RC_FAIL = 0`) — миссия из 4 точек → `assert` достижение. Время — 2–4 минуты (ориентир курса; один прогон `sitl_fs_test.py` в лабораторной — около минуты). ArduPilot-овский `Tools/autotest` — пример, как это сделано у разработчиков (`autotest.py test.Copter.ThrottleFailsafe`).

Главная ловушка автотеста — он может проверять не твой конфиг. Тест, который сам выставляет `FS_THR_ENABLE = 1` перед проверкой (так сделан учебный `examples/sitl-pymavlink/test_failsafe.py` в репозитории курса — чтобы документировать ожидание), пройдёт при любом `.param` в репозитории. Тест парка должен только загрузить конфиг аппарата и ничего в нём не чинить: `arducopter -w --defaults copter.parm,hex1/ardupilot/params.param` (ключ `-w` стирает эмулированную EEPROM, и значения берутся из файлов умолчаний; без него в SITL останутся параметры прошлого запуска). Проверка, что тест умеет падать, — mutation test: подменить `FS_THR_ENABLE` на 0 и убедиться, что результат красный. В лабораторной оба прогона сделаны на ArduCopter 4.7.2 SITL: с исправленным конфигом — `PASS: mode RTL 1.0 s after RC loss`, с мутантом — `FAIL: mode still GUIDED 5 s after RC loss`, по минуте на прогон.

{{diagram:ci-sitl-failsafe-seq|SITL-автотест по шагам: после SIM_RC_FAIL = 1 режим обязан смениться на RTL или LAND за 5 с, иначе assert падает и PR не сливается.}}

Betaflight: SITL-сборка проверяет компиляцию и CLI; для PID-логики — юнит-тесты `make test`. Для конфигов — скрипт инвариантов. Сборка SITL Betaflight и прогон `diff all` через неё — в модуле про автоматизацию CLI: так можно проверить в CI, что `diff all` вставляется в нужную версию без ошибок `INVALID NAME`.

### Ревью
PR = изменение + причина + доказательство (лог до/после, спектр, число). Чек-лист self-review (ревьюер здесь — ты сам): причина понятна? риск (failsafe, моторы, лимиты)? проверено в SITL/на стенде? откат описан? Порядок для одного человека: PR с описанием, CI зелёный, мерж через день (ориентир курса: эффект «утро вечера мудренее») — и перед мержем пройти эти четыре вопроса по своему же PR.

### Релизы и откат
Тег `viking7-v12` на коммит, с которым летали; `CHANGELOG.md` по версиям; релиз в GitHub с приложенными `diff all`/`.param` и логом контрольного полёта. Откат — `git checkout viking7-v11 -- viking7/` и загрузка конфига. Прошивка — её версия и сборочный ключ (Betaflight: `version` и BUILD KEY из `status`; ArduPilot: сообщение `AUTOPILOT_VERSION` или `version` в MAVProxy) в README релиза.

{{diagram:config-ci|Изменение конфига как изменение кода: снять, закоммитить, проверить инварианты и SITL, отрецензировать, выпустить с возможностью отката.}}

### Место в системе

- **Получает:** `diff all` Betaflight (`bf-cli-automation`) и `.param` ArduPilot; правила-инварианты из модулей про failsafe (`bf-failsafe`, `ap-safety-fs`); таблицы переименований между версиями (`bf-intro`); SITL для автотеста (`ap-sitl`); функции анализа логов контрольных полётов (`data-python`).
- **Отдаёт:** тег конфигурации, с которым летали, — в журнал тестов и пакет документации (`eng-systems`); историю изменений с причиной и логом; проверенный откат; красный CI до того, как сломанный конфиг попадёт на аппарат.
- **Если ошибиться здесь:** конфиг после обновления прошивки залит без проверки инвариантов → параметр переименован, failsafe молча не работает; вскроется при потере RC в поле (`ap-safety-fs`). Автотест сам выставил `FS_THR_ENABLE` → зелёный CI при сломанном конфиге. Коммит без причины и лога → через месяц непонятно, зачем менялся D, и тюнинг начинают заново (`bf-pid`).

## practice
Главный путь — локальный прогон тех же команд, что в workflow, на настоящих файлах: `viking2/betaflight/diff-all.txt` — `diff all` из SITL Betaflight 4.5.3 (лабораторная модуля про автоматизацию CLI: `failsafe_delay = 10`, `failsafe_procedure = GPS-RESCUE`, `d_roll = 30`, `d_min_roll = 20`, `feature -GPS`); `hex1/ardupilot/params.param` — 1015 параметров ArduCopter 4.7.2 из лога SITL (лабораторная модуля «Python для анализа полётных данных», там `FS_THR_ENABLE = 0` ради RC override). Окружение: Python 3.13, `pip install yamllint==1.38.0 check-jsonschema==0.39.0` (PyYAML 6.0.4 приходит зависимостью).

### Шаг 1. Репозиторий
Структура выше; первый коммит — текущие конфиги с README (железо, версии). `.gitattributes` для LFS на `.bin/.BFL`. Манифест, схема и настройки линтера:

```text
# --- fleet.yaml ---
# Fleet manifest: one entry per aircraft; CI validates it against schema/fleet.schema.json
site:
  name: field-north
  obstacle_m: 25            # tallest obstacle around the field, m (RTL must clear it)
craft:
  - name: viking2
    stack: betaflight
    firmware: "4.5.3"
    config: viking2/betaflight/diff-all.txt
  - name: hex1
    stack: ardupilot
    firmware: "4.7.2"
    config: hex1/ardupilot/params.param

# --- schema/fleet.schema.json ---
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["site", "craft"],
  "additionalProperties": false,
  "properties": {
    "site": {
      "type": "object",
      "required": ["name", "obstacle_m"],
      "properties": {
        "name": {"type": "string"},
        "obstacle_m": {"type": "number", "minimum": 0, "maximum": 300}
      }
    },
    "craft": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["name", "stack", "firmware", "config"],
        "additionalProperties": false,
        "properties": {
          "name": {"type": "string", "pattern": "^[a-z0-9_-]{1,16}$"},
          "stack": {"enum": ["betaflight", "ardupilot"]},
          "firmware": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
          "config": {"type": "string"}
        }
      }
    }
  }
}

# --- .yamllint ---
extends: default
rules:
  line-length: {max: 120}
  truthy: {allowed-values: ["true", "false"], check-keys: false}
  comments: {min-spaces-from-content: 1}
  document-start: disable
```

### Шаг 2. Экспорт скриптом
`export_bf.py` или `param save` по команде; коммит «snapshot before tuning». Для лабораторной экспорт уже сделан: файлы выше взяты из двух SITL-прогонов без правки руками (у `.param` удалены только строки `SIM_*`).

### Шаг 3. Инварианты + CI
`check_configs.py` с 5+ правилами; `.github/workflows/config-ci.yml`: те же четыре проверки, что ты гоняешь локально. Сломать правило нарочно → CI красный → починить.

```python
"""Check every config listed in fleet.yaml against invariants. Exit 1 on any ERROR.
Betaflight: `diff all` text (4.5.x / 2025.12.x). ArduPilot: .param ("NAME,VALUE" or "NAME VALUE").
"""
import os, re, sys
import yaml  # PyYAML 6.0.4

BF_RENAMED_2025 = {f"d_min_{a}": f"d_max_{a}" for a in ("roll", "pitch", "yaw")}  # meaning flipped too


def load_bf(path):
    text = open(path, encoding="utf-8").read()
    ver = re.search(r"^# Betaflight / \S+ \(\S+\) (\S+)", text, re.M)
    ctx, vals = "master", {}
    for line in text.splitlines():
        if m := re.match(r"(profile|rateprofile) (\d)\s*$", line):
            ctx = f"{m[1]} {m[2]}"
        elif m := re.match(r"set (\S+) = (.*?)\s*$", line):
            vals[(ctx, m[1])] = m[2]
    features = set(re.findall(r"^feature (-?\w+)", text, re.M))
    return (ver[1] if ver else None), vals, features


def check_bf(craft, errs):
    ver, vals, feats = load_bf(craft["config"])
    if ver != craft["firmware"]:
        errs.append(f"firmware in file {ver} != fleet.yaml {craft['firmware']} (bf-cli-automation)")
    major = int(craft["firmware"].split(".")[0])
    master = {k: v for (c, k), v in vals.items() if c == "master"}
    if major >= 2025:
        for (c, k) in vals:
            if k in BF_RENAMED_2025:
                errs.append(f"{c}: {k} does not exist in 2025.12, now {BF_RENAMED_2025[k]} "
                            "with the opposite meaning (bf-intro)")
    if master.get("failsafe_procedure") == "GPS-RESCUE" and "-GPS" in feats:
        errs.append("failsafe_procedure = GPS-RESCUE without feature GPS: firmware resets it "
                    "to DROP on save (config.c validateAndFixConfig) (bf-failsafe)")
    if int(master.get("failsafe_delay", 15)) > 20:
        errs.append(f"failsafe_delay = {master['failsafe_delay']} x0.1 s > 2.0 s (bf-failsafe)")
    for (c, k), v in vals.items():
        if major >= 2025 and (m := re.match(r"d_max_(roll|pitch|yaw)$", k)):
            d = vals.get((c, f"d_{m[1]}"))
            if d is not None and 0 < int(v) < int(d):
                errs.append(f"{c}: {k} = {v} < d_{m[1]} = {d}: zeroed on save (bf-pid)")


def load_ap(path):
    params = {}
    for line in open(path, encoding="utf-8"):
        if m := re.match(r"\s*([A-Z][A-Z0-9_]*)[,\s]+(-?[\d.]+(?:[eE][-+]?\d+)?)\s*(#.*)?$", line):
            params[m[1]] = float(m[2])
    return params


def check_ap(craft, site, errs):
    p = load_ap(craft["config"])
    if len(p) < 300:
        errs.append(f"only {len(p)} parameters: partial export? (eng-ci-configs)")
    rtl_m = p["RTL_ALT_M"] if "RTL_ALT_M" in p else p.get("RTL_ALT", -100) / 100  # cm before 4.7
    skip = p.get("ARMING_SKIPCHK", 0 if p.get("ARMING_CHECK", 1) == 1 else 1)   # 4.7 rename
    rules = [("FS_THR_ENABLE", p.get("FS_THR_ENABLE", 0) != 0, "RC failsafe must act (ap-safety-fs)"),
             ("BATT_FS_LOW_ACT", p.get("BATT_FS_LOW_ACT", 0) != 0, "low battery must act (ap-safety-fs)"),
             ("FENCE_ENABLE", p.get("FENCE_ENABLE", 0) == 1, "geofence on for field flights (ap-safety-fs)"),
             ("RTL_ALT_M", rtl_m >= site["obstacle_m"],
              f"RTL altitude {rtl_m:g} m must clear obstacles {site['obstacle_m']} m (ap-safety-fs)"),
             ("ARMING_SKIPCHK", skip == 0, "no arming checks skipped (ap-safety-fs)"),
             ("INS_HNTCH_ENABLE", p.get("INS_HNTCH_ENABLE", 0) == 1, "harmonic notch configured (ap-tuning)")]
    errs += [f"{name}: {why}" for name, ok, why in rules if not ok]


if __name__ == "__main__":
    fleet = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[1])))
    bad = 0
    for craft in fleet["craft"]:
        errs = []
        if not os.path.isfile(craft["config"]):
            errs.append(f"config file {craft['config']} missing")
        elif craft["stack"] == "betaflight":
            check_bf(craft, errs)
        else:
            check_ap(craft, fleet["site"], errs)
        print(f"{craft['name']:8s} {craft['stack']:10s} {craft['firmware']:9s} "
              f"{'OK' if not errs else str(len(errs)) + ' ERROR(S)'}")
        for e in errs:
            print("   ERROR", e)
        bad += len(errs)
    sys.exit(1 if bad else 0)
```

```yaml
# .github/workflows/config-ci.yml
name: config-ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  validate:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0  # v7.1.0
        with:
          python-version: "3.13"
      - run: pip install yamllint==1.38.0 check-jsonschema==0.39.0
      - name: YAML style
        run: yamllint --strict .
      - name: Fleet manifest schema
        run: check-jsonschema --schemafile schema/fleet.schema.json fleet.yaml
      - name: Workflow schema
        run: check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml
      - name: Config invariants
        run: python3 tools/check_configs.py fleet.yaml
```

Правила, чьи параметры переименованы между версиями (`RTL_ALT` → `RTL_ALT_M` в 4.7), держите с обоими именами, или проверяйте версию прошивки из README аппарата. Для Betaflight — тот же подход по строкам `set name = value` из `diff all`.

### Шаг 4. Прогнать CI локально: пять случаев
Скрипт ниже выполняет цепочку проверок из workflow (через `&&`, как в job) пять раз: (A) снимок как выгружен; (B) починка — RC- и батарейный failsafe, геозона, RTL 30 м, notch, failsafe Betaflight `DROP`; (C) mutation test — `FS_THR_ENABLE` обратно в 0; (D) в манифесте прошивку viking2 подняли до 2025.12.5, а `diff all` оставили от 4.5.3; (E) опечатка в манифесте. Запуск: `bash run_ci_lab.sh <копия fleet/>` — копия, потому что скрипт правит файлы через `sed`.

```bash
#!/bin/bash
# Local run of the config-ci job, step by step (same commands as .github/workflows/config-ci.yml).
cd "$1" || exit 2
ci() { yamllint --strict . && check-jsonschema --schemafile schema/fleet.schema.json fleet.yaml \
       && check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml \
       && python3 -I tools/check_configs.py fleet.yaml; echo "CI exit code: $?"; }
p=hex1/ardupilot/params.param; d=viking2/betaflight/diff-all.txt
echo "== A. snapshot as exported"; ci
echo "== B. fix: RC/battery failsafe, fence, RTL 30 m, notch; BF failsafe DROP"
sed -i -e 's/^FS_THR_ENABLE,0$/FS_THR_ENABLE,1/' -e 's/^BATT_FS_LOW_ACT,0$/BATT_FS_LOW_ACT,2/' \
       -e 's/^FENCE_ENABLE,0$/FENCE_ENABLE,1/' -e 's/^RTL_ALT_M,15$/RTL_ALT_M,30/' \
       -e 's/^INS_HNTCH_ENABLE,0$/INS_HNTCH_ENABLE,1/' $p
sed -i 's/^set failsafe_procedure = GPS-RESCUE$/set failsafe_procedure = DROP/' $d; ci
echo "== C. mutation test: FS_THR_ENABLE back to 0"
sed -i 's/^FS_THR_ENABLE,1$/FS_THR_ENABLE,0/' $p; ci
sed -i 's/^FS_THR_ENABLE,0$/FS_THR_ENABLE,1/' $p
echo "== D. firmware bumped in fleet.yaml, diff left from 4.5.3"
sed -i 's/firmware: "4.5.3"/firmware: "2025.12.5"/' fleet.yaml; ci
echo "== E. typo in the manifest: stack: inav, firmware: 4.7"
sed -i -e 's/stack: ardupilot/stack: inav/' -e 's/firmware: "4.7.2"/firmware: "4.7"/' fleet.yaml; ci
```

```text
== A. snapshot as exported
ok -- validation done
ok -- validation done
viking2  betaflight 4.5.3     1 ERROR(S)
   ERROR failsafe_procedure = GPS-RESCUE without feature GPS: firmware resets it to DROP on save (config.c validateAndFixConfig) (bf-failsafe)
hex1     ardupilot  4.7.2     5 ERROR(S)
   ERROR FS_THR_ENABLE: RC failsafe must act (ap-safety-fs)
   ERROR BATT_FS_LOW_ACT: low battery must act (ap-safety-fs)
   ERROR FENCE_ENABLE: geofence on for field flights (ap-safety-fs)
   ERROR RTL_ALT_M: RTL altitude 15 m must clear obstacles 25 m (ap-safety-fs)
   ERROR INS_HNTCH_ENABLE: harmonic notch configured (ap-tuning)
CI exit code: 1
== B. fix: RC/battery failsafe, fence, RTL 30 m, notch; BF failsafe DROP
ok -- validation done
ok -- validation done
viking2  betaflight 4.5.3     OK
hex1     ardupilot  4.7.2     OK
CI exit code: 0
== C. mutation test: FS_THR_ENABLE back to 0
ok -- validation done
ok -- validation done
viking2  betaflight 4.5.3     OK
hex1     ardupilot  4.7.2     1 ERROR(S)
   ERROR FS_THR_ENABLE: RC failsafe must act (ap-safety-fs)
CI exit code: 1
== D. firmware bumped in fleet.yaml, diff left from 4.5.3
ok -- validation done
ok -- validation done
viking2  betaflight 2025.12.5 2 ERROR(S)
   ERROR firmware in file 4.5.3 != fleet.yaml 2025.12.5 (bf-cli-automation)
   ERROR profile 0: d_min_roll does not exist in 2025.12, now d_max_roll with the opposite meaning (bf-intro)
hex1     ardupilot  4.7.2     OK
CI exit code: 1
== E. typo in the manifest: stack: inav, firmware: 4.7
Schema validation errors were encountered.
  fleet.yaml::$.craft[1].stack: 'inav' is not one of ['betaflight', 'ardupilot']
  fleet.yaml::$.craft[1].firmware: '4.7' does not match '^[0-9]+\\.[0-9]+\\.[0-9]+$'
CI exit code: 1
```

Что доказывает вывод. В случае A пойманы все шесть нарушений, которые есть в файлах: пять у `hex1` и тихое исправление failsafe у `viking2`; exit code 1 — PR с таким снимком не сольётся. B — зелёный, и это единственный зелёный: значит, правила не «всегда красные». C — ровно одна ошибка на ровно одну мутацию. D — проверка версии сработала раньше правил: файл 4.5.3 под прошивку 2025.12.5 даёт и несовпадение версии, и устаревшее имя `d_min_roll`. E — схема остановила job до проверки конфигов, с указанием пути `$.craft[1].stack`.

### Шаг 5. SITL-тест failsafe на конфиге парка
`sitl_fs_test.py` — тест, который не трогает `FS_THR_ENABLE`, а грузит `.param` аппарата через `--defaults`. Запуск на исправленном конфиге и на мутанте:

```python
"""RC-failsafe test of the FLEET config in ArduCopter SITL: loads copter.parm + the aircraft's .param,
never sets FS_THR_ENABLE itself. Exit 0 = RTL/LAND within 5 s of SIM_RC_FAIL=1, else 1.
Usage: python3 -I sitl_fs_test.py <arducopter> <copter.parm> <aircraft.param> <workdir>
"""
import os, subprocess, sys, time
from pymavlink import mavutil

ardu, parm, fleet, work = sys.argv[1:5]
os.makedirs(work, exist_ok=True)
I = 23                                                 # TCP 5990
sitl = subprocess.Popen([ardu, "-S", "--model", "+", "--speedup", "1", "-I", str(I), "-w",
                         "--defaults", f"{parm},{os.path.abspath(fleet)}", "--home", "50.45,30.52,100,0"],
                        cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
code = 1
try:
    time.sleep(2)
    m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{5760 + 10 * I}")
    m.wait_heartbeat(timeout=30)
    m.mav.request_data_stream_send(m.target_system, m.target_component,
                                   mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    m.param_fetch_one("FS_THR_ENABLE")
    p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=5)
    print("FS_THR_ENABLE in SITL =", p.param_value)
    t_end = time.time() + 180
    while time.time() < t_end:                         # wait for GPS-based EKF
        msg = m.recv_match(type="STATUSTEXT", blocking=True, timeout=1)
        if msg and "using GPS" in msg.text:
            break
    m.set_mode("GUIDED")
    for _ in range(60):
        m.arducopter_arm(); time.sleep(1)
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if m.motors_armed():
            break
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
    time.sleep(12)
    m.mav.param_set_send(m.target_system, m.target_component, b"SIM_RC_FAIL", 1,
                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)  # simulated RC loss
    t0 = time.time(); seen = None
    while time.time() - t0 < 5:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        seen = mavutil.mode_string_v10(hb) if hb else seen
        if seen in ("RTL", "LAND", "SMART_RTL"):
            print(f"PASS: mode {seen} {time.time() - t0:.1f} s after RC loss"); code = 0
            break
    else:
        print(f"FAIL: mode still {seen} 5 s after RC loss")
finally:
    sitl.terminate(); sitl.wait()
sys.exit(code)
# python3 -I sitl_fs_test.py arducopter copter.parm run/hex1/ardupilot/params.param fs_ok   (after case B)
# FS_THR_ENABLE in SITL = 1.0
# PASS: mode RTL 1.0 s after RC loss          exit=0, 60 s
# python3 -I sitl_fs_test.py arducopter copter.parm mut.param fs_mut                     (FS_THR_ENABLE,0)
# FS_THR_ENABLE in SITL = 0.0
# FAIL: mode still GUIDED 5 s after RC loss   exit=1, 64 s
```

Сравнить с учебной заготовкой из репозитория курса: [examples/sitl-pymavlink](https://github.com/irreligious86/UAV-Education/tree/main/examples/sitl-pymavlink) (`test_failsafe.py` + `ci.yml`). Заготовка сама ставит `FS_THR_ENABLE = 1` и закреплена на `actions/checkout@v4` по тегу — для парка возьми подход из `sitl_fs_test.py` и SHA из таблицы теории. Один PR с изменением параметра, описанием, CI и мержем.

### Переход на реальное железо
CI проверяет файлы, а не аппарат, поэтому последний шаг — сверить, что на аппарате то же, что в git. Пропеллеры сняты. Betaflight: после заливки конфига снять `diff all` той же командой, что и для репозитория, и сравнить с файлом из тега по ключам (`parse_diff` из модуля про автоматизацию CLI) — разница должна быть пустой; если прошивка что-то исправила при `save`, разница это покажет. ArduPilot: `param fetch` + `param save` и `diff` с файлом из тега; затем на поле — контрольная проверка failsafe по модулю «Безопасность и failsafe» (выключить пульт на висении на безопасной высоте, ожидаемый режим — RTL или LAND за время `RC_FS_TIMEOUT`). Прервать: любое отличие файла на аппарате от тега — не летать, пока не объяснено. Критерии на железе: разница «аппарат − тег» пустая для обоих стеков; тег релиза указывает на коммит с зелёным CI; полевой failsafe-тест даёт тот режим, который проверял SITL.

Самопроверка: лабораторная выполнена, когда (локально) случай A печатает `1 ERROR(S)` у `viking2` и `5 ERROR(S)` у `hex1` с exit code 1; случай B — `OK` у обоих и exit code 0; C — ровно одна ошибка `FS_THR_ENABLE` и exit code 1; D — две ошибки у `viking2` (версия и `d_min_roll`); E — две ошибки схемы с путями `$.craft[1].stack` и `$.craft[1].firmware`; (SITL) исправленный конфиг даёт `PASS: mode RTL`, мутант с `FS_THR_ENABLE = 0` — `FAIL: mode still GUIDED`; в PR есть изменение, причина и доказательство, и перед мержем ты сам прошёл по нему чек-лист self-review из теории: на каждый из четырёх вопросов (причина, риск, проверка, откат) в описании PR есть письменный ответ.

**Эталон для самопроверки.** Верный результат — вывод шага 4 строка в строку (числа ошибок и exit code) и пара PASS/FAIL шага 5; время RTL после потери RC — около 1 с. Типичные неверные: (1) мутант тоже даёт PASS — тест выставляет `FS_THR_ENABLE` сам или SITL запущен без `-w` и взял параметры из EEPROM прошлого прогона; (2) в случае A у `hex1` нет ошибки `RTL_ALT_M` — в правиле стоит порог 15 м вместо высоты препятствий 25 м из манифеста, или скрипт ищет `RTL_ALT` и делит 15 на 100; (3) `yamllint` красный на workflow с `truthy` — нет `check-keys: false` в `.yamllint`; (4) случай E проходит схему — в схеме нет `additionalProperties: false` или `enum` у `stack`.

## diagnostics
- **Симптом:** diff all каждый раз отличается целиком
  - Возможная причина: порядок/комментарии/дата в выгрузке.
  - Что сделать: нормализация и сортировка перед коммитом; сравнение по ключам, а не по строкам.
- **Симптом:** SITL в CI не стартует/таймаут
  - Возможная причина: сборка долгая, нет `--no-mavproxy`/headless, порты.
  - Что сделать: кэш сборки или готовый образ, headless-запуск, ожидание heartbeat с таймаутом; `timeout-minutes` у job.
- **Симптом:** тест проходит, хотя failsafe сломан
  - Возможная причина: assert проверяет не то (режим не читается), тест не ждёт, или тест сам выставляет проверяемый параметр.
  - Что сделать: проверить, что тест падает при сломанном конфиге (mutation test); тест только загружает `.param` (`--defaults … -w`).
- **Симптом:** не помню, с каким конфигом летал в тот раз
  - Возможная причина: нет тегов/релизов.
  - Что сделать: тег на каждый полётный конфиг, лог к релизу.
- **Симптом:** CI «вдруг» покраснел без изменений в репозитории
  - Возможная причина: плавающие версии — `ubuntu-latest`, `@v7`, `pip install` без `==`.
  - Что сделать: закрепить образ, действия по SHA, пакеты по версии; обновлять их отдельным PR.
- **Симптом:** `yamllint` ругается на `on:` в workflow
  - Возможная причина: правило `truthy` проверяет ключи; в YAML 1.1 `on` — булево.
  - Что сделать: `truthy: {check-keys: false}` в `.yamllint`.
- **Симптом:** правило RTL проходит на старом конфиге с RTL 15 м
  - Возможная причина: конфиг до 4.7 — параметр `RTL_ALT` в сантиметрах, а правило читает только `RTL_ALT_M`.
  - Что сделать: правило с обоими именами и переводом единиц; версия прошивки — из манифеста.

## references
- GitHub Docs — GitHub Actions workflows | https://docs.github.com/en/actions/writing-workflows | primary | A
- actions/checkout (теги, action.yml) | https://github.com/actions/checkout | primary | A
- actions/setup-python (теги, action.yml) | https://github.com/actions/setup-python | primary | A
- check-jsonschema — documentation | https://check-jsonschema.readthedocs.io/ | primary | A
- yamllint — documentation (rules: truthy) | https://yamllint.readthedocs.io/ | primary | A
- ArduPilot — Autotest framework (Tools/autotest) | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A
- ArduPilot — source code 4.7.2 (ArduCopter/mode_rtl.cpp, libraries/AP_Arming/AP_Arming.cpp) | https://github.com/ArduPilot/ardupilot | primary | A
- Betaflight — Command Line Interface (CLI) | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A

## checklist
- Конфиги в git с коммитами «что и зачем», манифест парка под схемой
- Экспорт конфигов скриптом, нормализован, проверен на полноту
- Инварианты проверяются в CI и знают переименования между версиями
- Действия закреплены по SHA, образ и пакеты — по версии
- SITL-тест failsafe грузит конфиг парка и падает при сломанном конфиге
- Релизы тегами, откат отработан
