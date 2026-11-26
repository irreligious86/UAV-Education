---
id: eng-systems
title: "Системна інженерія: вимоги, FMEA, документація, тести"
level: L4
readingTime: 40 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-08
tags:
  - системна інженерія
  - вимоги
  - FMEA
  - документація
  - тести
related:
  - eng-method-101
  - ap-safety-fs
  - eng-ci-configs
  - el-redundancy
next:
  - eng-ci-configs
source: content/companion/eng-systems.md
source_hash: 69b1062cf401
---

## summary
«Інженерний метод 101» запровадив цикл вимоги → архітектура → тести → документація на одній збірці. А цей модуль — той самий цикл, але на повний зріст, для апарата або системи, яку потім буде вести інша людина: як писати вимоги, які можна перевірити (з ID, критерієм і методом), як вести трасування до тестів, як робити FMEA на рівні системи із заходами та їх перевіркою, як будувати план верифікації (SITL → стенд → поле) і як документувати так, щоби передача зайняла годину, а не місяць. Лабораторна — повний пакет документації власного проєкту.

## theory
### Вимоги
Добра вимога: **однозначна, перевірювана, з джерелом**. Структура: `ID | формулировка | критерий приёмки | метод проверки (анализ/симуляция/стенд/полёт) | источник (задача, правило, стандарт) | приоритет`.

- Погано: «Дрон має довго літати». Файно: `R-PWR-03 | Время висения с полезной нагрузкой 500 г не менее 25 мин при 20 °C | лог: ток висения, расчёт по ёмкости ≥ 25 мин; полёт: ≥ 25 мин до BATT_LOW | полёт | задача заказчика §2`.
- Класи: функціональні (що робить), продуктивності (скільки), обмеження (маса, бюджет, закон), безпека (failsafe, зони), інтерфейси (MAVLink, живлення навантаження), експлуатація (заміна АКБ ≤ 2 хв без інструмента).
- Вимоги безпеки **виводяться з FMEA і правил**, а не вигадуються з голови.
- Кожна вимога має власника і статус (чернетка/затверджено/перевірено/не виконано).

### Архітектура та інтерфейси
Схема системи: блоки (FC, companion, живлення, RC, відео, навантаження), **інтерфейси між ними** з протоколом, живленням, напрямком (таблиця інтерфейсів — головний документ під час інтеграції), бюджети: маси (із запасом 10%), потужності (за гілками, з модуля про живлення), зв'язку (бюджет лінку), обчислень (CPU companion). Рішення з альтернативами та причиною вибору (ADR — architecture decision record: контекст, варіанти, рішення, наслідки) — щоби через рік не сперечатися заново.

### FMEA на рівні системи
Відмінність від модуля про failsafe: розглядаються не лише відмови в польоті, а й інтеграційні (помилка в прошивці після оновлення, неправильна збірка, людський фактор під час підготовки), для кожної — **захід** (усунення, резервування, виявлення, процедура) і **як захід перевірено** (посилання на тест). RPN ся перераховує після заходів. Таблиця живе й оновлюється після кожного інциденту (розбір → новий рядок/оновлений захід).

### Розібраний приклад: FMEA на три рядки
Оцінки за шкалою 1–10: S — тяжкість наслідків, O — імовірність, D — наскільки важко виявити до шкоди (10 — не виявимо). RPN = S·O·D — то порядок, у якому закривати ризики, а не абсолютна міра.

| Відмова | Наслідок | S | O | D | RPN | Захід | Вимога / тест |
|---|---|---|---|---|---|---|---|
| Втрата RC на віддаленні | некерований політ | 9 | 4 | 2 | 72 | `FS_THR_ENABLE` = RTL, висота RTL вища за перешкоди | R-SAF-01 / SITL `SIM_RC_FAIL` |
| Холодне паяння фази мотора | падіння (квад), відхід по рисканню (X8) | 8 | 3 | 7 | 168 | перевірка навантаженням і вібротест у чек-листі збирання | R-MFG-04 / тест падіння напруги |
| Нова прошивка змінила імена параметрів | мовчки не працює failsafe | 9 | 3 | 8 | 216 | інваріанти в CI, diff параметрів після оновлення | R-PRC-02 / `check_params.py` |

Сюрприз у прикладі типовий, йой який: найстрашніший за відчуттями ризик (втрата зв'язку) закритий найкраще, а найвищі RPN — у збирання та процесу, де виявлення погане. FMEA якраз тим перекосом уваги і є цінна.

{{diagram:eng-trace-chain|Строка FMEA с RPN 216 проходит цепочку мера → требование R-PRC-02 → тест check_params.py → запись → матрица; результат теста возвращается в FMEA пересчётом RPN.}}

### ADR: рішення, яке можна перечитати
Architecture Decision Record — короткий файл на кожне незворотне рішення. Шаблон:
```
# ADR-003: Li-Ion 6S2P instead of LiPo for the survey airframe
Status: accepted (2026-11-08)
Context: requirement R-PWR-03 (25 min hover with 500 g); hover current 16 A (R-PWR-01); LiPo 6S 5000 gives 15 min at 80 % DoD.
Decision: 6S2P P42A, 8.4 Ah: 6.7 Ah usable at 80 % DoD / 16 A = 25 min.
Consequences: +180 g, sag under punch ~1.5 V, no aggressive manoeuvres; BATT_* thresholds for Li-Ion.
Alternatives: LiPo 6S 8000 (heavier, hover ~18 A, 21 min at 80 % DoD), hybrid (out of budget).
```
Через пів року на питання «чого тут Li-Ion?» відповідає файл, а не пам'ять.

### Верифікація та валідація
- **Верифікація** — «ци зробили правильно?»: кожна вимога → тест із методом; план тестів за щаблями: аналіз/розрахунок → SITL → стенд (без пропелерів) → прив'язний/низький політ → політ. Результат кожного тесту — запис із датою, конфігом (тег!), логом, вердиктом.
- **Валідація** — «ци зробили те, що треба?»: прогін реальної задачі із замовником/користувачем; часто трафляються вимоги, яких перше не було.
- Матриця трасування: вимога ↔ тест ↔ результат. Порожні клітинки — незакриті вимоги; тести без вимог — або зайві, або вимогу забули.
- Регресія: після будь-якої зміни — набір обов'язкових тестів (SITL-автотест із модуля про CI + короткий польотний чек-лист).

### Документація, яку можна передати
Мінімальний пакет:
1. `README` — що це, для чого, стан, як запустити за 15 хвилин.
2. Вимоги (таблиця) та ADR.
3. Архітектура: схема, таблиця інтерфейсів, бюджети.
4. Збирання: BOM з версіями, схема проводки, фото, моменти затягування, де важливо.
5. Конфігурація: репозиторій конфігів із тегами (модуль про CI).
6. FMEA та налаштування failsafe з обґрунтуванням.
7. План і журнал тестів, матриця трасування.
8. Експлуатація: чек-листи (перед/післяпольотний), журнал польотів, процедури (заміна АКБ, калібрування, оновлення прошивки з відкатом).
9. Журнал змін і відомі проблеми.
Критерій якості: інший інженер за пакетом відновлює апарат і виконує політ без питань до автора. Як то перевірити? Попроси когось спробувати.

### Процес змін
Запит → оцінка впливу на вимоги/FMEA → зміна в гілці → тести (регресія) → рев'ю → реліз із тегом → оновлення документації в тому самому PR. Документація, яку оновлюють «потім», не оновлюється гет ніколи.

{{diagram:eng-verify-method-tree|Метод проверки выбирают по трём вопросам: видно ли свойство без работы изделия, можно ли его безопасно запустить и нужно ли число с допуском; SITL попадает в анализ, поэтому требование безопасности им одним не закрывается.}}

{{diagram:v-model|V-модель: кожному рівню вимог і проєктування відповідає свій рівень перевірки — від модульних тестів до валідації в полі.}}

## practice
### Крок 1. Вимоги
Напиши 20–40 вимог для свого апарата за структурою; ≥ 5 щодо безпеки з FMEA; кожна з методом перевірки.

### Крок 2. Архітектура
Схема блоків, таблиця інтерфейсів, бюджети маси/потужності/зв'язку, 3 ADR за шаблоном вище (наприклад: Li-Ion vs LiPo; ELRS 900 vs 2.4; companion Pi vs Jetson).

### Крок 3. FMEA і план тестів
Системна FMEA (≥ 15 рядків) у форматі розібраного прикладу: S/O/D/RPN, захід, посилання на вимогу й тест; три ризики з найбільшим RPN закрий першими й покажи, як змінилися їхні O або D. План тестів за щаблями; матриця трасування.

### Крок 3a. Скрипт: лінтер вимог, матриця і ранжування FMEA (код і вивід як у вихідному модулі)

```python
#!/usr/bin/env python3
"""Traceability and FMEA checker for module eng-systems (stdlib only).

Keep requirements, tests, results and FMEA as CSV files in the project repo; this script is the
self-check: it lints requirement wording, finds holes in the trace matrix and ranks FMEA rows.
Exit code 1 when a hole is found, so the same script can run in CI (module eng-ci-configs).
Run: python3 trace_lab.py
"""
import csv
import io
import re
import sys

REQS = """id,text,method,source,test
R-SAF-01,When the RC signal is lost for more than 1 s the vehicle shall switch to RTL,T,FMEA F-07,T-12;T-31
R-PWR-01,Hover current with 500 g payload shall not exceed 16 A,T,power budget,T-05
R-PWR-03,Hover endurance with 500 g payload shall be at least 25 min at 20 C,A;T,customer 2,
R-OPS-02,Battery swap shall be fast and easy,D,operator,T-40
R-LNK-01,RC link margin at 3 km shall be at least 12 dB,A,mission 3 km,T-20
"""
TESTS = """id,stage,result,date
T-12,SITL,pass,2026-11-09
T-31,field,pass,2026-11-09
T-05,bench,pass,2026-11-10
T-20,analysis,pass,2026-11-10
T-40,bench,,
T-77,SITL,pass,2026-11-11
"""
FMEA = """id,failure,S,O,D,S_after,O_after,D_after
F-07,RC link lost far away,9,4,2,9,4,2
F-11,cold solder joint on motor phase,8,3,7,8,3,3
F-12,firmware update renamed failsafe parameters,9,3,8,9,3,2
F-14,BEC 5 V fails,9,3,6,9,3,3
F-15,battery strap fails in flight,10,2,3,10,2,3
"""

VAGUE = r"\b(fast|easy|quick|reliable|enough|good|user-friendly|as soon as possible|long)\b"
NUMBER = r"\d"


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


reqs, tests, fmea = rows(REQS), rows(TESTS), rows(FMEA)
test_ids = {t["id"]: t for t in tests}
holes = 0

print("1) Requirement lint (INCOSE R7 vague terms, R34 measurable, method in I/A/D/T):")
for r in reqs:
    issues = []
    if re.search(VAGUE, r["text"], re.I):
        issues.append("vague term")
    if not re.search(NUMBER, r["text"]):
        issues.append("no number")
    if not set(r["method"].split(";")) <= set("IADT"):
        issues.append("bad method")
    if not r["source"]:
        issues.append("no source")
    print(f"   {r['id']:<10} {'OK' if not issues else ', '.join(issues)}")
    holes += bool(issues)

print("2) Trace matrix:")
linked = set()
for r in reqs:
    ids = [x for x in r["test"].split(";") if x]
    linked.update(ids)
    if not ids:
        print(f"   {r['id']:<10} -> NO TEST")
        holes += 1
        continue
    res = [f"{i}:{test_ids[i]['result'] or 'not run'}" if i in test_ids else f"{i}:MISSING" for i in ids]
    print(f"   {r['id']:<10} -> {', '.join(res)}")
    holes += sum(1 for i in ids if i not in test_ids or test_ids[i]["result"] != "pass")
for t in tests:
    if t["id"] not in linked:
        print(f"   {t['id']:<10} -> test without requirement")
        holes += 1

print("3) FMEA ranking, RPN = S*O*D before -> after the measure:")
for f in sorted(fmea, key=lambda f: -int(f["S"]) * int(f["O"]) * int(f["D"])):
    before = int(f["S"]) * int(f["O"]) * int(f["D"])
    after = int(f["S_after"]) * int(f["O_after"]) * int(f["D_after"])
    flag = "  <- S>=9: review regardless of RPN" if int(f["S"]) >= 9 and before < 100 else ""
    print(f"   {f['id']} RPN {before:3} -> {after:3}  S={f['S']}{flag}")

distinct = {s * o * d for s in range(1, 11) for o in range(1, 11) for d in range(1, 11)}
print(f"4) RPN takes {len(distinct)} distinct values out of 1..1000; RPN 72 arises from "
      f"{sum(1 for s in range(1, 11) for o in range(1, 11) for d in range(1, 11) if s * o * d == 72)} (S,O,D) triples")

print(f"holes: {holes}")
sys.exit(1 if holes else 0)
```

```text
1) Requirement lint (INCOSE R7 vague terms, R34 measurable, method in I/A/D/T):
   R-SAF-01   OK
   R-PWR-01   OK
   R-PWR-03   OK
   R-OPS-02   vague term, no number
   R-LNK-01   OK
2) Trace matrix:
   R-SAF-01   -> T-12:pass, T-31:pass
   R-PWR-01   -> T-05:pass
   R-PWR-03   -> NO TEST
   R-OPS-02   -> T-40:not run
   R-LNK-01   -> T-20:pass
   T-77       -> test without requirement
3) FMEA ranking, RPN = S*O*D before -> after the measure:
   F-12 RPN 216 ->  54  S=9
   F-11 RPN 168 ->  72  S=8
   F-14 RPN 162 ->  81  S=9
   F-07 RPN  72 ->  72  S=9  <- S>=9: review regardless of RPN
   F-15 RPN  60 ->  60  S=10  <- S>=9: review regardless of RPN
4) RPN takes 120 distinct values out of 1..1000; RPN 72 arises from 24 (S,O,D) triples
holes: 4
```

### Крок 4. Пакет і передача
Збери пакет (п. 1–9), дай прочитати іншій людині (або собі через тиждень) із завданням «підготуй до польоту за документацією» — список питань, які ся виникли, → виправлення.

### Розібраний приклад: вимога, тест, трасування
- **Вимога:** `R-SAF-01` — у разі втрати сигналу пульта довше ніж 1 с апарат виконує RTL; перевірка — тест. Джерело: рядок FMEA `F-07` «втрата RC-лінку».
- **Тест:** `T-12` — SITL: вимкнення RC-входу в LOITER на 50 м від дому; очікування: режим RTL не пізніше ніж за 1.5 с, посадка в радіусі 3 м від дому. Щабель 2 — польовий тест на висоті 20 м зі спостерігачем.
- **Трасування** (фрагмент матриці):

| Вимога | Джерело | Тест | Результат |
|---|---|---|---|
| R-SAF-01 | FMEA F-07 | T-12 (SITL), T-31 (поле) | pass 2026-11-09 |
| R-PWR-01 | бюджет потужності | T-05 (стенд, струм зависання) | pass |

- **FMEA:** RPN = S × O × D (кожне 1–10). Рядок «відмова BEC 5 В: S 9, O 3, D 6 → RPN 162; захід — резервне живлення приймача, перевірка напруги в передпольотному чек-листі → D 3, RPN 81».

### Що має вийти
- Кожна вимога має ID, формулювання з числом, метод перевірки та принаймні один тест. Вимога без тесту і тест без вимоги — то два різновиди однієї діри.
- Три верхні ризики FMEA закрито заходами, і видно, як упав їхній RPN.
- README відповідає на питання «як підготувати апарат до польоту» без автора під боком. CHANGELOG — за датами: що змінено і чому, з посиланням на вимогу або тест.

Лабораторну зараховано, коли вимоги мають ID і трасуються до тестів у матриці, FMEA на 15+ рядків із заходами щодо трьох верхніх ризиків готова, а README і журнал змін пройшли перевірку читанням зі списком виправлених питань.

## diagnostics
- **Симптом:** вимоги є, але тести «за відчуттями»
  - Можлива причина: критерії приймання не числові.
  - Що зробити: переписати з числами й методом; вимога без методу — то не вимога.
- **Симптом:** після оновлення прошивки вшитко ся зламало
  - Можлива причина: нема регресії та відкату.
  - Що зробити: тег перед оновленням, регресійний набір, процедура відкату в документації.
- **Симптом:** передача проєкту зайняла тижні
  - Можлива причина: знання сидять у голові, а не в пакеті.
  - Що зробити: тест передачі, ADR, таблиця інтерфейсів.
- **Симптом:** FMEA написано один раз, і вона застаріла
  - Можлива причина: нема процесу оновлення після інцидентів.
  - Що зробити: розбір інциденту завершується рядком у FMEA і зміною заходу.

## references
- INCOSE — Technical publications (Systems Engineering Handbook) | https://www.incose.org/publications/products/technical-publications | secondary | B
- NASA — Systems Engineering Handbook, NASA/SP-2016-6105 Rev2 (NTRS) | https://ntrs.nasa.gov/citations/20170001761 | primary | A
- ArduPilot — Developer: testing and autotest as an example of verification practice | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A

## checklist
- Вимоги з ID, критерієм і методом перевірки
- Архітектура з таблицею інтерфейсів, бюджетами та ADR
- Системна FMEA із заходами й посиланнями на тести
- Матриця трасування без порожніх клітинок
- Пакет документації пройшов тест передачі
