---
id: bf-blackbox
title: "Blackbox: диагностика и настройка по полётным данным"
level: L2
readingTime: 45 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5)
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
---

## summary

Blackbox — система записи полётных данных в Betaflight, позволяющая фиксировать состояние контроллера на каждом цикле управления (до 8 кГц). Лог содержит гироскоп, акселерометр, сигналы стиков, работу PID-регулятора, выходы на моторы и параметры фильтров. Статья даёт полное понимание настройки логирования, интерпретации графиков и использования инструментов (Blackbox Explorer, PIDscope) для диагностики и тюнинга. После изучения читатель сможет выявлять шумовую структуру дрона, оценивать задержки фильтров, настраивать PID и фильтры на основе объективных данных, а не методом случайного подбора.

## theory

### Назначение и архитектура Blackbox

Blackbox записывает внутреннее состояние полётного контроллера с максимально возможной частотой, чтобы позволить офлайн-симуляцию, отладку и анализ алгоритмов управления по данным реальных полётов. Лог строится из кадров нескольких типов:

- I‑кадры (intra) — полные кадры, независимо декодируемые.
- P‑кадры (inter) — разностные, используют предсказание.
- G/H кадры — для GPS-данных.
- S кадры (slow) — редко меняющиеся состояния.
- E кадры (event) — переходы состояний.

Для сжатия применяются предсказатели и кодирование переменной длины, что позволяет хранить большой объём данных при умеренном потоке.

### Что именно логируется

Blackbox фиксирует:
- время,
- значения P/I/D и суммарный выход,
- setpoint (стики),
- данные гироскопа и акселерометра,
- напряжение/ток, RSSI,
- команды на ESC,
- GPS-кадры (при наличии).

### Формат лога и устройства хранения

Запись может вестись на:
- onboard flash (обычно 2–16 МБ),
- SD-карту (предпочтительно для длинных сессий),
- внешний логгер через UART.

Для SD-карты рекомендуется FAT32 и карта с низкой задержкой записи.

### Влияние настроек на качество лога

- 1 кГц — базовый PID-анализ;
- 2 кГц (или 1.6 кГц для BMI270) — детальный анализ шумов/фильтров.

Если looptime мал (высокая частота PID), может потребоваться поднять baudrate или снизить частоту логирования, иначе возможны пропуски.

### Физический смысл спектра шума

- `<20 Гц` — полезная динамика;
- `20–100 Гц` — вибрации/propwash/проблемы PID;
- `100–250 Гц` — резонансы рамы/люфты;
- `>250 Гц` — шум моторов/пропов и гармоники.

Цель фильтрации — подавлять высокочастотный шум, не внося лишнюю задержку в полезный диапазон.

### Параметры записи
`blackbox_device` (SPIFLASH / SDCARD / SERIAL; с 2025.12 ещё VIRTUAL — для SITL), `blackbox_sample_rate` (1/1, 1/2, 1/4, … от частоты PID: при 8 кГц PID и 1/4 — 2 кГц лога), `blackbox_mode` (NORMAL — по арму; MOTOR_TEST; ALWAYS — и на земле: для измерения шума/bias гироскопа), `blackbox_high_resolution` (точнее gyro/setpoint), `blackbox_disable_*` (отключить группы полей: `acc`, `rc`, `gyrounfilt`, `rpm`, `gps`… — экономия потока), `debug_mode` (какие 8 отладочных значений писать: `RPM_FILTER`, `D_LPF`, `DSHOT_RPM_TELEMETRY`, `FEEDFORWARD`, `GPS_RESCUE_*`, `AUTOPILOT_ALTITUDE` (до 2025.12 — `GPS_RESCUE_THROTTLE_PID`), `RTH`…; режима `GYRO_SCALED` — сырой гироскоп до фильтров — в 2025.12 нет, его заменяет поле `gyroUnfilt`; в 4.5 он есть). Поток: 2 кГц с полным набором полей — порядка 60–100 КБ/с → 16 МБ flash хватает на 3–4 минуты; SD — часы. Внешний логгер — функция Blackbox на UART во вкладке Ports (`serial <id> 128 …` с blackbox baud); отдельных `blackbox_uart`/`blackbox_baud` в 4.5 и 2025.12 нет.

Группы полей и `blackbox_disable_*` (`cli/settings.c`; в 2025.12 к перечисленным в таблице добавились `blackbox_disable_attitude` — поле `imuQuaternion[0..2]`, при наличии акселерометра, и `blackbox_disable_servos` — `servo[0..7]`, только при сервах в миксере; условия полей — `testBlackboxConditionUncached()` в `blackbox/blackbox.c`). По умолчанию всё включено (`fields_disabled_mask = 0`); группа без датчика не пишется и так. Число — сколько значений в каждом основном кадре (для квадрокоптера, 4 мотора):

| Параметр | Что отключает | Значений | Когда отключать |
|---|---|---|---|
| `blackbox_disable_pids` | `axisP`, `axisI`, `axisD`, `axisF` | до 12 (`axisD` по рысканью — только при `d_yaw` ≠ 0) | почти никогда: без них не разобрать тюн |
| `blackbox_disable_rc` | `rcCommand[0..3]` | 4 | если есть `setpoint` и стики не нужны |
| `blackbox_disable_setpoint` | `setpoint[0..3]` | 4 | никогда для тюна |
| `blackbox_disable_bat` | `vbatLatest`, `amperageLatest` | 2 | редко: нужны для просадки |
| `blackbox_disable_mag` | `magADC[0..2]` | 3 (если есть компас) | компас есть, но не анализируется |
| `blackbox_disable_alt` | `baroAlt`, `surfaceRaw` | 1–2 (баро/дальномер) | нет задач по высоте |
| `blackbox_disable_rssi` | `rssi` | 1 | — |
| `blackbox_disable_gyro` | `gyroADC[0..2]` (после фильтров) | 3 | никогда |
| `blackbox_disable_gyrounfilt` | `gyroUnfilt[0..2]` (до фильтров) | 3 | после настройки фильтров, чтобы сэкономить поток |
| `blackbox_disable_acc` | `accSmooth[0..2]` | 3 | первый кандидат при нехватке потока на acro-квадрокоптере |
| `blackbox_disable_debug` | `debug[0..7]` | 8 (только при `debug_mode` ≠ NONE) | `debug_mode = NONE` даёт то же |
| `blackbox_disable_motors` | `motor[0..3]` | 4 | никогда |
| `blackbox_disable_rpm` | `eRPM[0..3]` | 4 (только с DShot-телеметрией) | после проверки RPM-фильтра |
| `blackbox_disable_gps` | отдельные GPS-кадры (G/H) | — | нет GPS-анализа |

Обслуживание носителя из CLI: `flash_info` — размер и заполнение встроенной flash; `flash_erase` — стереть (печатает точки до конца; то же — кнопка Erase Flash во вкладке Blackbox или режим BLACKBOX ERASE, id 31); `sd_info` — состояние SD (`Not configured`, `None inserted`, `Startup failed` или производитель, объём и дата выпуска карты); `msc` — перезагрузка FC в режим USB-накопителя, логи копируются как файлы и с flash, и с SD (если носитель не готов — `Storage not present or failed to initialize!`).

События в логе (E-кадры) включают и подстройки в полёте: смена значения через Adjustments пишется событием `INFLIGHT_ADJUSTMENT` (номер функции и новое значение; в шаговом и абсолютном режиме — для всех функций, из функций выбора — только рейт-профиль и HORIZON_STRENGTH, `fc/rc_adjustments.c`), в Blackbox Explorer видно, в какой момент полёта D стал 42. Слоты и функции — bf-adjustments.

### Поля, которые нужны чаще всего
`gyroADC[0..2]` (после фильтров), `gyroUnfilt[0..2]` (до, при включённом поле), `setpoint[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[0..2]`, `motor[0..3]`, `eRPM[0..3]`, `vbatLatest`, `amperageLatest`, `rssi`, `debug[0..7]`, `flightModeFlags`, `stateFlags`, `failsafePhase`; события (E-кадры): арм/дизарм, смена режима, failsafe. Заголовок лога содержит около 190 ключевых параметров (PID, рейты, фильтры, моторы), но не весь `diff`: нет `aux`, `serial`, OSD, failsafe — полный бэкап только через `diff all`.

### Метод чтения лога за 5 минут
1. Blackbox Explorer: обзор — нет ли обрывов (пропуски кадров), `vbat` под нагрузкой, `rssi/LQ`.
2. Спектрограмма gyro (до/после) — моторы, резонансы (модуль «Сигналы и спектры»).
3. Наложить `setpoint` на `gyro` по roll — overshoot/bounce-back на глаз; `axisD` — шум.
4. `motor[0..3]` — симметрия (один выше остальных = дисбаланс/механика), насыщение на 100%.
5. Числа — через Python (`data-python`), в таблицу решений.

### Разобранный пример: «один мотор горячее»
В логе `motor[2]` в висении на 8% выше остальных, `eRPM[2]` ниже — мотор тянет хуже: проп повреждён, подшипник или перекос рамы; шум в `gyroUnfilt` на частоте 2×RPM этого мотора выше. Решение — механика, а не PID. Без лога это выглядело бы как «надо подкрутить D».

{{diagram:blackbox-chain|Где в контуре полётного контроллера берутся основные поля Blackbox и как лог попадает в инструменты анализа.}}

### Место в системе

- **Получает:** гироскоп до и после фильтров (`bf-filters`), setpoint из цепочки стика (`bf-rates-rc`), члены P, I, D, F и команды моторам (`bf-pid-reg-in-bf`), eRPM по DShot-телеметрии (`bf-rpm-filter`).
- **Отдаёт:** спектр «до/после» — настройке фильтров (`bf-filters`); наложение setpoint и гироскопа и числа метрик — тюнингу (`bf-pid`, `data-python`); события подстроек — проверке того, что меняли в полёте (`bf-adjustments`).
- **Если ошибиться здесь:** отключено поле `gyroUnfilt` или `eRPM` → гироскоп после фильтров не с чем сравнить и нечем проверить, покрывает ли RPM-фильтр реальные обороты; решение о фильтрах принимается вслепую (`bf-filters`, `bf-rpm-filter`). Лог записан на 1 кГц вместо 2 кГц → для базового PID-анализа его хватает, для детального разбора шумов и фильтров — нет (`bf-filters`).

## practice

### Подготовка оборудования и ПО

Аппаратно:
- FC с flash или SD-слотом,
- ESC с Bidirectional DShot (BLHeli_32/Bluejay),
- качественная и механически жёсткая сборка.

Настройка:
- включить `BLACKBOX`,
- выставить `logging rate` (обычно 2 kHz),
- для шумового анализа оставить включённым поле `gyroUnfilt` (в 4.5 — либо оно, либо `debug_mode = GYRO_SCALED`; в 2025.12 этого режима нет),
- включить RPM-фильтр.

### Запись лога и манёвры

Blackbox обычно стартует при арме и останавливается при дизарме. Для качественного анализа выполняйте:
- hover и ровный полёт,
- throttle sweep `20% -> 100%`,
- резкие roll/flip,
- throttle pump,
- резкие развороты (проверка propwash).

### Работа с Blackbox Explorer

1. Выгрузите `.bbl` (Mass Storage Mode).
2. Откройте лог в Blackbox Explorer.
3. Проверьте header (`i`) — там все параметры прошивки.
4. Для анализа выберите `Gyro`, `Setpoint`, `P/I/D`, `Motor`, `Debug`.
5. Используйте `I/O` для выделения участков одинаковой длины.

### PIDscope (бывший PIDtoolbox)

PIDtoolbox с 2024 года распространяется как платный продукт по подписке; открытое продолжение — **PIDscope** (GPL-3.0, работает в бесплатной GNU Octave, поддерживает логи Betaflight 4.x и 2025.12). Он полезен для:
- оценки задержки фильтров,
- сравнения спектров в dB,
- анализа step response.

### Пошаговая настройка фильтров

1. Запишите лог с полем `gyroUnfilt` (в 4.5 — можно `debug_mode = GYRO_SCALED`) и `throttle sweep`.
2. Оцените спектр:
   - `<100 Гц` чаще решается механикой/PID,
   - `100–250 Гц` — зона динамического режектора,
   - `>250 Гц` — зона RPM-фильтра.
3. Убедитесь, что bidirectional DShot работает (`E = 0%` в Motors).
4. Настройте lowpass по результату спектра.
5. Делайте изменения итеративно: один параметр -> новый лог -> сравнение.

### Автопроверка лога
Расшифруйте лог `blackbox_decode` и прогоните грейдер курса: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab all --motor-range <motorOutput из заголовка лога>`. Он выдаёт PASS/FAIL по каждой проверке (tracking, motors) со значением, порогом и объяснением; пороги — ориентиры для 5", их можно переопределить через `--set`, записав причину. Потренироваться до своих логов можно на синтетике: `make_bf_fixture.py --kind noisy` (или `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

## diagnostics

- Симптом: в логе гироскопа сильный пик на `100–250 Гц`.
  - Возможная причина: резонанс рамы/люфт.
  - Что проверить/сделать: проверить механику и убедиться, что dynamic notch активен.

- Симптом: шум выше `250 Гц` не подавлен.
  - Возможная причина: RPM-фильтр отключён или неверно настроен bidirectional DShot.
  - Что проверить/сделать: проверить `E = 0%` в Motors, включить RPM-фильтр (он есть только на гироскопе — и в 4.5, и в 2025.12; отдельного D-term RPM-фильтра нет).

- Симптом: всплески в `20–100 Гц`.
  - Возможная причина: недостаточные P/D или избыточная фильтрация (задержка).
  - Что проверить/сделать: проверить задержку в PIDscope (или PIDtoolbox), скорректировать фильтры и PID.

- Симптом: дрон стал «ватным» после фильтрации.
  - Возможная причина: слишком низкие частоты среза.
  - Что проверить/сделать: поднять частоту среза gyro lowpass, проверить D-term lowpass и задержку.

- Симптом: лог с пропусками/артефактами.
  - Возможная причина: скорость записи/буфер.
  - Что проверить/сделать: использовать качественную SD-карту, при необходимости снизить логрейт.

- Симптом: нет записи на onboard flash при включённом Blackbox.
  - Возможная причина: память заполнена.
  - Что проверить/сделать: `Erase Flash`, регулярно выгружать логи.

- Симптом: некорректные частоты в спектре.
  - Возможная причина: сравниваются участки разной длины.
  - Что проверить/сделать: выделять одинаковые интервалы через `I/O`.
- **Симптом:** лог обрывается / «Log ends abruptly»
  - Возможная причина: flash заполнена или не успевает (DMA/скорость), слабая SD.
  - Что сделать: стереть flash, `blackbox_sample_rate` ниже, отключить лишние поля, карта класса A1/U3.
- **Симптом:** в логе нет gyro до фильтров
  - Возможная причина: `blackbox_disable_gyrounfilt` или старая версия без поля.
  - Что сделать: включить поле (`set blackbox_disable_gyrounfilt = OFF`); на 4.5 можно также `debug_mode = GYRO_SCALED`.

## references

- Blackbox flight data recorder — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Blackbox logging internals | https://www.betaflight.com/docs/development/Blackbox-Internals | primary | A
- Betaflight Blackbox Explorer | https://github.com/betaflight/blackbox-log-viewer | primary | A
- PIDscope — open-source GNU Octave continuation of PIDtoolbox | https://github.com/dzikus/PIDscope | secondary | B
- How to Use Blackbox in Betaflight — Oscar Liang | https://oscarliang.com/blackbox/ | secondary | B
- How to Tune FPV Drone Filters & PID with Blackbox — Oscar Liang | https://oscarliang.com/pid-filter-tuning-blackbox/ | secondary | B
