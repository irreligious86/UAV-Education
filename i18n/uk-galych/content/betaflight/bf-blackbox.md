---
id: bf-blackbox
title: "Blackbox: діагностика та налаштування за польотними даними"
level: L2
readingTime: 45 хв
firmware: Betaflight 4.5+
status: published
tags:
  - Blackbox
  - logging
  - tuning
  - diagnostics
  - PID
references:
  - title: "Blackbox flight data recorder — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage"
    tier: primary
    stack: betaflight
  - title: "Blackbox logging internals"
    url: "https://www.betaflight.com/docs/development/Blackbox-Internals"
    tier: primary
    stack: betaflight
  - title: "How to Use Blackbox in Betaflight — Oscar Liang"
    url: "https://oscarliang.com/blackbox/"
    tier: secondary
    stack: betaflight
  - title: "How to Tune Filters & PID with Blackbox — Oscar Liang"
    url: "https://oscarliang.com/pid-filter-tuning-blackbox/"
    tier: secondary
    stack: betaflight
  - title: "Betaflight Blackbox Explorer"
    url: "https://github.com/betaflight/blackbox-log-viewer"
    tier: primary
    stack: betaflight
related:
  - bf-pid
  - bf-filters
  - bf-cli
next:
  - bf-custom
source: content/betaflight/bf-blackbox.md
source_hash: ac8c59ec5c3a
---

## summary

Blackbox — то система запису польотних даних у Betaflight, яка фіксує стан контролера на кожному циклі керування (до 8 кГц). У лозі є гіроскоп, акселерометр, сигнали стіків, робота PID-регулятора, виходи на мотори та параметри фільтрів. Стаття дає повне розуміння, як налаштувати логування, як читати графіки і як ґаздувати інструментами (Blackbox Explorer, PIDscope) для діагностики та тюнінгу. Опанувавши її, читач зможе виявляти шумову структуру дрона, оцінювати затримки фільтрів, налаштовувати PID і фільтри на основі об'єктивних даних, а не крутити навмання, аж поки щось не трафиться.

## theory

### Призначення та архітектура Blackbox

Blackbox записує внутрішній стан польотного контролера з найвищою можливою частотою, щоб потім можна було офлайн симулювати, налагоджувати й аналізувати алгоритми керування за даними реальних польотів. Лог будується з кадрів кількох типів:

- I‑кадри (intra) — повні кадри, що декодуються незалежно.
- P‑кадри (inter) — різницеві, використовують передбачення.
- G/H кадри — для GPS-даних.
- S кадри (slow) — стани, що рідко ся міняють.
- E кадри (event) — переходи станів.

Для стиснення застосовуються передбачувачі та кодування змінної довжини, тож великий обсяг даних вміщається в помірний потік.

### Що саме логується

Blackbox фіксує:
- час,
- значення P/I/D і сумарний вихід,
- setpoint (стіки),
- дані гіроскопа та акселерометра,
- напругу/струм, RSSI,
- команди на ESC,
- GPS-кадри (як є GPS).

### Формат логу та пристрої зберігання

Запис може вестися на:
- onboard flash (зазвичай 2–16 МБ),
- SD-карту (ліпше для довгих сесій),
- зовнішній логер через UART.

Для SD-карти радять FAT32 і карту з низькою затримкою запису.

### Вплив налаштувань на якість логу

- 1 кГц — базовий PID-аналіз;
- 2 кГц (або 1.6 кГц для BMI270) — детальний аналіз шумів/фільтрів.

Як looptime малий (висока частота PID), може знадобитися підняти baudrate або знизити частоту логування, бо інакше будуть пропуски.

### Фізичний зміст спектра шуму

- `<20 Гц` — корисна динаміка;
- `20–100 Гц` — вібрації/propwash/проблеми PID;
- `100–250 Гц` — резонанси рами/люфти;
- `>250 Гц` — шум моторів/пропелерів і гармоніки.

Мета фільтрації — придушити високочастотний шум і не вносити зайвої затримки в корисний діапазон.

### Параметри запису
`blackbox_device` (SPIFLASH / SDCARD / SERIAL), `blackbox_sample_rate` (1/1, 1/2, 1/4, … від частоти PID: за 8 кГц PID і 1/4 — 2 кГц логу), `blackbox_mode` (NORMAL — за армом; MOTOR_TEST; ALWAYS — і на землі: для вимірювання шуму/bias гіроскопа), `blackbox_high_resolution` (точніше gyro/setpoint), `blackbox_disable_*` (вимкнути групи полів: `acc`, `rc`, `gyrounfilt`, `rpm`, `gps`… — економія потоку), `debug_mode` (які 8 налагоджувальних значень писати: `GYRO_SCALED` — сирий гіроскоп до фільтрів (лише 4.5; у 2025.12 вилучено, використовуй поле `gyroUnfilt`), `RPM_FILTER`, `D_LPF`, `DSHOT_RPM_TELEMETRY`, `FEEDFORWARD`, `GPS_RESCUE_*`, `RTH`…). Потік: 2 кГц з повним набором полів — десь 60–100 КБ/с → 16 МБ flash вистачає на 3–4 хвилини; SD — на години. Зовнішній логер — функція Blackbox на UART у вкладці Ports (`serial <id> 128 …` з blackbox baud); окремих `blackbox_uart`/`blackbox_baud` у 4.5 і 2025.12 нема.

### Поля, які треба найчастіше
`gyroADC[0..2]` (після фільтрів), `gyroUnfilt[0..2]` (до, як поле ввімкнене), `setpoint[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[0..2]`, `motor[0..3]`, `eRPM[0..3]`, `vbatLatest`, `amperageLatest`, `rssi`, `debug[0..7]`, `flightModeFlags`, `stateFlags`, `failsafePhase`; події (E-кадри): арм/дизарм, зміна режиму, failsafe. Заголовок логу містить коло 190 ключових параметрів (PID, рейти, фільтри, мотори), але не весь `diff`: нема `aux`, `serial`, OSD, failsafe — повний бекап лиш через `diff all`.

### Метод читання логу за 5 хвилин
1. Blackbox Explorer: огляд — ци нема обривів (пропуски кадрів), `vbat` під навантаженням, `rssi/LQ`.
2. Спектрограма gyro (до/після) — мотори, резонанси (модуль «Сигнали та спектри»).
3. Накласти `setpoint` на `gyro` по roll — overshoot/bounce-back на око; `axisD` — шум.
4. `motor[0..3]` — симетрія (один вищий за інших = дисбаланс/механіка), насичення на 100%.
5. Числа — через Python (`data-python`), до таблиці рішень.

### Розібраний приклад: «один мотор гарячіший»
У лозі `motor[2]` на зависанні на 8% вищий за інші, `eRPM[2]` нижчий — мотор тягне гірше: пропелер пошкоджений, підшипник або перекіс рами; шум у `gyroUnfilt` на частоті 2×RPM цього мотора вищий. Рішення — механіка, а не PID. Без логу то виглядало б як «треба підкрутити D».

{{diagram:blackbox-chain|Де в контурі польотного контролера беруться основні поля Blackbox і як лог потрапляє в інструменти аналізу.}}

## practice

### Підготовка обладнання та ПЗ

Апаратно:
- FC із flash або SD-слотом,
- ESC з Bidirectional DShot (BLHeli_32/Bluejay),
- якісне й механічно жорстке складання.

Налаштування:
- увімкнути `BLACKBOX`,
- виставити `logging rate` (зазвичай 2 kHz),
- для шумового аналізу брати `debug_mode = GYRO_SCALED`,
- увімкнути RPM-фільтр.

### Запис логу та маневри

Blackbox зазвичай стартує при армі й зупиняється при дизармі. Для якісного аналізу зроби:
- hover і рівний політ,
- throttle sweep `20% -> 100%`,
- різкі roll/flip,
- throttle pump,
- різкі розвороти (перевірка propwash).

### Робота з Blackbox Explorer

1. Вивантаж `.bbl` (Mass Storage Mode).
2. Відкрий лог у Blackbox Explorer.
3. Глянь header (`i`) — там усі параметри прошивки.
4. Для аналізу вибери `Gyro`, `Setpoint`, `P/I/D`, `Motor`, `Debug`.
5. Виділяй ділянки однакової довжини через `I/O`.

### PIDscope (колишній PIDtoolbox)

PIDtoolbox з 2024 року поширюється як платний продукт за підпискою; відкрите продовження — **PIDscope** (GPL-3.0, працює в безкоштовній GNU Octave, підтримує логи Betaflight 4.x і 2025.12). Він ся придасть для:
- оцінювання затримки фільтрів,
- порівняння спектрів у dB,
- аналізу step response.

### Покрокове налаштування фільтрів

1. Запиши лог із `GYRO_SCALED` і `throttle sweep`.
2. Оціни спектр:
   - `<100 Гц` частіше розв'язується механікою/PID,
   - `100–250 Гц` — зона динамічного режектора,
   - `>250 Гц` — зона RPM-фільтра.
3. Переконайся, що bidirectional DShot працює (`E = 0%` у Motors).
4. Налаштуй lowpass за результатом спектра.
5. Міняй ітеративно: один параметр -> новий лог -> порівняння.

### Автоперевірка логу
Розшифруй лог `blackbox_decode` і прожени грейдер курсу: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab all --motor-range <motorOutput з заголовка логу>`. Він видає PASS/FAIL за кожною перевіркою (tracking, motors) зі значенням, порогом і поясненням; пороги — орієнтири для 5", їх можна перевизначити через `--set`, записавши причину. Потренуватися, заки дійде до своїх логів, можна на синтетиці: `make_bf_fixture.py --kind noisy` (або `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

## diagnostics

- Симптом: у лозі гіроскопа сильний пік на `100–250 Гц`.
  - Можлива причина: резонанс рами/люфт.
  - Що зробити (перевірити): перевірити механіку й переконатися, що dynamic notch активний.

- Симптом: шум вище `250 Гц` не придушено.
  - Можлива причина: RPM-фільтр вимкнено або хибно налаштовано bidirectional DShot.
  - Що зробити (перевірити): перевірити `E = 0%` у Motors, увімкнути RPM-фільтр (у 4.5 він є лиш на гіроскопі; окремого D-term RPM-фільтра нема).

- Симптом: сплески в `20–100 Гц`.
  - Можлива причина: замалі P/D або фест сильна фільтрація (затримка).
  - Що зробити (перевірити): перевірити затримку в PIDscope (або PIDtoolbox), скоригувати фільтри та PID.

- Симптом: дрон став «ватним» після фільтрації.
  - Можлива причина: занизькі частоти зрізу.
  - Що зробити (перевірити): підняти частоту зрізу gyro lowpass, перевірити D-term lowpass і затримку.

- Симптом: лог із пропусками/артефактами.
  - Можлива причина: швидкість запису/буфер.
  - Що зробити (перевірити): брати якісну SD-карту, як треба — знизити логрейт.

- Симптом: нема запису на onboard flash, хоч Blackbox увімкнений.
  - Можлива причина: пам'ять заповнена.
  - Що зробити (перевірити): `Erase Flash`, регулярно вивантажувати логи.

- Симптом: некоректні частоти в спектрі.
  - Можлива причина: порівнюються ділянки різної довжини.
  - Що зробити (перевірити): виділяти однакові інтервали через `I/O`.
- **Симптом:** лог обривається / «Log ends abruptly»
  - Можлива причина: flash заповнена або не встигає (DMA/швидкість), слабка SD.
  - Що зробити: стерти flash, `blackbox_sample_rate` нижче, вимкнути зайві поля, карта класу A1/U3.
- **Симптом:** у лозі нема gyro до фільтрів
  - Можлива причина: `blackbox_disable_gyrounfilt` або стара версія без поля.
  - Що зробити: увімкнути поле або `debug_mode = GYRO_SCALED`.

## references

- Blackbox flight data recorder — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Blackbox logging internals | https://www.betaflight.com/docs/development/Blackbox-Internals | primary | A
- Betaflight Blackbox Explorer | https://github.com/betaflight/blackbox-log-viewer | primary | A
- PIDscope — open-source GNU Octave continuation of PIDtoolbox | https://github.com/dzikus/PIDscope | secondary | B
- How to Use Blackbox in Betaflight — Oscar Liang | https://oscarliang.com/blackbox/ | secondary | B
- How to Tune FPV Drone Filters & PID with Blackbox — Oscar Liang | https://oscarliang.com/pid-filter-tuning-blackbox/ | secondary | B
