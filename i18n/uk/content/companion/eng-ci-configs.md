---
id: eng-ci-configs
title: "CI і версіонування конфігів та коду"
level: L3
readingTime: 35 хв
firmware: Betaflight · ArduPilot
status: published
added: 2026-11-08
tags:
  - git
  - CI
  - diff all
  - SITL
  - рев'ю
related:
  - bf-cli-automation
  - ap-sitl
  - tools-overview
  - eng-method-101
next:
  - eng-systems
source: content/companion/eng-ci-configs.md
source_hash: 7e2ce4e9c154
---

## summary
Конфігурація дрона — це код: від неї залежить, чи полетить він. Отже, до неї застосовне все, що інженери давно роблять із кодом: історія змін з поясненням, рев'ю перед застосуванням, автоматична перевірка, релізи та відкат. Модуль налаштовує це для одного апарата або парку: `diff all` Betaflight і `.param` ArduPilot у git з осмисленими комітами, pull request як форма рев'ю, GitHub Actions із SITL-автотестом (місія/failsafe), лінтери для скриптів і схеми для конфігів, теги релізів і журнал змін. Лабораторна: CI, який падає, якщо failsafe зламано.

## theory
### Що зберігати
```
fleet/
  viking7/
    README.md              # що за апарат, залізо, версія прошивки
    betaflight/diff-all.txt  # diff all після кожної зміни
    ardupilot/params.param   # повний список параметрів (Mission Planner / mavproxy param save)
    notes/CHANGELOG.md     # що і навіщо змінювалося, з датою
    logs/                  # посилання або small logs за релізами (великі — в Releases/LFS)
  tools/
    export_bf.py           # знімає diff all через MSP/CLI
    check_params.py        # перевірки інваріантів
    sitl_test.py           # автотест у SITL
.github/workflows/ci.yml
```
Правила: один коміт — одна зміна з причиною («D roll 38→42: bounce-back 18%→9%, лог 2026-11-08-03»); без причини — не коміт. Бінарні логи — не в репозиторій (Git LFS або релізи).

### Зняти конфіг автоматично
Betaflight: по USB у режимі CLI (не MSP: вхід у CLI символом `#`) — `diff all` з Python (`pyserial`: `#` → чекати `# ` → `diff all` → читати до `# `), або через експорт `betaflight-configurator`. ArduPilot: `mavproxy.py --master=... --cmd="param fetch; param save params.param"` або pymavlink `param_fetch_all` → відсортований текстовий файл. Сортування й нормалізація (прибрати `#` коментарі з датою) — інакше diff шумить.

### Інваріанти: перевірка конфігів
Скрипт, який читає конфіг і падає на порушенні правил, відомих із курсу:
- Betaflight: `failsafe_procedure` задано, `failsafe_delay` у розумних межах, `motor_poles` = 14 для 2207, `dshot_bidir = ON` при rpm_filter, `vbat_min_cell_voltage` ≥ 330, немає `set debug_mode` у польотному профілі.
- ArduPilot: `FS_THR_ENABLE ≠ 0`, `BATT_FS_LOW_ACT ≠ 0`, `FENCE_ENABLE = 1` для польотів за правилами, `RTL_ALT_M` ≥ висота перешкод майданчика (у README), `ARMING_SKIPCHK = 0` (до 4.7 — `ARMING_CHECK = 1`), `INS_HNTCH_ENABLE = 1` якщо notch потрібен, `BRD_SAFETY_DEFLT` за політикою.
Реалізація — JSON Schema/простий Python із таблицею правил; вивід — список порушень із посиланням на модуль курсу.

### SITL-автотест
ArduPilot у CI (Ubuntu runner): зібрати SITL (`./waf configure --board sitl && ./waf copter`) або взяти готовий образ; запустити `sim_vehicle.py` без GUI з `--add-param-file params.param`; скрипт pymavlink: арм у Guided, зліт 10 м, `SIM_RC_FAIL = 1` → очікувати режим RTL/LAND протягом 5 с → `assert`; потім місія з 4 точок → `assert` досягнення. Час — 2–4 хвилини. Ардупілотівський `Tools/autotest` — приклад, як це зроблено в розробників (`autotest.py test.Copter.ThrottleFailsafe`).
Betaflight: SITL-збірка перевіряє компіляцію та CLI; для PID-логіки — юніт-тести `make test`. Для конфігів — скрипт інваріантів.

### Лінтери та схеми
Python: `ruff`/`flake8` + `black`; Lua (ArduPilot): `luacheck` із конфігом ArduPilot (`Tools/scripts/run_luacheck.sh` у репозиторії ArduPilot — той самий підхід); JSON-конфіги — JSON Schema (`check-jsonschema`); YAML — `yamllint`. Усе — в CI на кожен PR.

### Рев'ю
PR = зміна + причина + доказ (лог до/після, спектр, число). Чек-лист рев'юера: причина зрозуміла? ризик (failsafe, мотори, ліміти)? перевірено в SITL/на стенді? відкат описано? Для однієї людини — self-review: PR з описом, CI зелений, мерж через день (ефект «ранок вечора мудріший» реальний).

### Релізи та відкат
Тег `viking7-v12` на коміт, з яким літали; `CHANGELOG.md` за версіями; реліз у GitHub із доданими `diff all`/`.param` і логом контрольного польоту. Відкат — `git checkout viking7-v11 -- viking7/` і завантаження конфігу. Прошивка — її версія та збірковий ключ (Betaflight: `version` і BUILD KEY зі `status`; ArduPilot: повідомлення `AUTOPILOT_VERSION` або `version` у MAVProxy) у README релізу.

{{diagram:config-ci|Зміна конфігу як зміна коду: зняти, закомітити, перевірити інваріанти й SITL, відрецензувати, випустити з можливістю відкату.}}

## practice
### Крок 1. Репозиторій
Структура вище; перший коміт — поточні конфіги з README (залізо, версії). `.gitattributes` для LFS на `.bin/.BFL`.

### Крок 2. Експорт скриптом
`export_bf.py` або `param save` за командою; коміт «snapshot before tuning».

### Крок 3. Інваріанти + CI
`check_params.py` з 5+ правилами; `.github/workflows/ci.yml`: ruff, check_params на всіх конфігах. Зламати правило навмисно → CI червоний → полагодити.

Заготовка для ArduPilot (`.param`: рядки `NAME,VALUE` або `NAME VALUE`):
```python
import re, sys

RULES = [  # (parameter, predicate, why — with the course module to read)
    ("FS_THR_ENABLE", lambda v: v != 0, "RC failsafe must act (ap-safety-fs)"),
    ("BATT_FS_LOW_ACT", lambda v: v != 0, "low battery must act (ap-safety-fs)"),
    ("FENCE_ENABLE", lambda v: v == 1, "geofence on for field flights (ap-safety-fs)"),
    ("RTL_ALT_M", lambda v: v >= 30, "RTL altitude above site obstacles (ap-safety-fs)"),
    ("INS_HNTCH_ENABLE", lambda v: v == 1, "harmonic notch configured (ap-tuning)"),
]

def load(path):
    params = {}
    for line in open(path):
        m = re.match(r"\s*([A-Z0-9_]+)[,\s]+(-?[\d.eE+-]+)", line)
        if m:
            params[m.group(1)] = float(m.group(2))
    return params

def check(params):
    errs = []
    for name, ok, why in RULES:
        if name not in params:
            errs.append(f"{name}: missing ({why})")
        elif not ok(params[name]):
            errs.append(f"{name} = {params[name]:g}: {why}")
    return errs

if __name__ == "__main__":
    bad = [f"{p}: {e}" for p in sys.argv[1:] for e in check(load(p))]
    print("\n".join(bad) or "all invariants hold")
    sys.exit(1 if bad else 0)
```
Правила, чиї параметри перейменовано між версіями (`RTL_ALT` → `RTL_ALT_M` у 4.7), тримай з обома іменами або перевіряй версію прошивки з README апарата. Для Betaflight — той самий підхід за рядками `set name = value` з `diff all`.

### Крок 4. SITL-тест у CI
Готова заготовка — в репозиторії курсу: [examples/sitl-pymavlink](https://github.com/irreligious86/UAV-Education/tree/main/examples/sitl-pymavlink) (`test_failsafe.py` + `ci.yml`). Job з ArduPilot SITL і тестом (RC failsafe → RTL/LAND). Зламати `FS_THR_ENABLE = 0` у `.param` → тест падає. Один PR зі зміною параметра, описом, CI і мержем. Лабораторна: репозиторій із читабельною історією, SITL-тест у CI, одна зміна через PR.

## diagnostics
- **Симптом:** diff all щоразу відрізняється цілком
  - Можлива причина: порядок/коментарі/дата у вивантаженні.
  - Що зробити: нормалізація та сортування перед комітом.
- **Симптом:** SITL у CI не стартує/таймаут
  - Можлива причина: збірка довга, немає `--no-mavproxy`/headless, порти.
  - Що зробити: кеш збірки або готовий образ, headless-запуск, очікування heartbeat із таймаутом.
- **Симптом:** тест проходить, хоча failsafe зламано
  - Можлива причина: assert перевіряє не те (режим не читається) або тест не чекає.
  - Що зробити: перевірити, що тест падає за зламаного конфігу (mutation test).
- **Симптом:** не пам'ятаю, з яким конфігом літав того разу
  - Можлива причина: немає тегів/релізів.
  - Що зробити: тег на кожен польотний конфіг, лог до релізу.

## references
- ArduPilot — Autotest framework (Tools/autotest) | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A
- GitHub Docs — GitHub Actions workflows | https://docs.github.com/en/actions/writing-workflows | primary | A
- Betaflight — Command Line Interface (CLI) | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A

## checklist
- Конфіги в git із комітами «що і навіщо»
- Експорт конфігів скриптом, нормалізований
- Інваріанти перевіряються в CI
- SITL-тест failsafe у CI, падає за зламаного конфігу
- Релізи тегами, відкат відпрацьовано
