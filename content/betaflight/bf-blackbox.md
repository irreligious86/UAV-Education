---
id: bf-blackbox
title: "Blackbox: диагностика и настройка по полётным данным"
level: L2
readingTime: 45 мин
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
---

## summary

Blackbox — система записи полётных данных в Betaflight, позволяющая фиксировать состояние контроллера на каждом цикле управления (до 8 кГц). Лог содержит гироскоп, акселерометр, сигналы стиков, работу PID-регулятора, выходы на моторы и параметры фильтров. Статья даёт полное понимание настройки логирования, интерпретации графиков и использования инструментов (Blackbox Explorer, PIDToolbox) для диагностики и тюнинга. После изучения читатель сможет выявлять шумовую структуру дрона, оценивать задержки фильтров, настраивать PID и фильтры на основе объективных данных, а не методом случайного подбора.

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
`blackbox_device` (SPIFLASH / SDCARD / SERIAL), `blackbox_sample_rate` (1/1, 1/2, 1/4, … от частоты PID: при 8 кГц PID и 1/4 — 2 кГц лога), `blackbox_mode` (NORMAL — по арму; MOTOR_TEST; ALWAYS — и на земле: для измерения шума/bias гироскопа), `blackbox_high_resolution` (точнее gyro/setpoint), `blackbox_disable_*` (отключить группы полей: `acc`, `rc`, `gyrounfilt`, `rpm`, `gps`… — экономия потока), `debug_mode` (какие 8 отладочных значений писать: `GYRO_SCALED` — сырой гироскоп до фильтров (только 4.5; в 2025.12 удалён, используйте поле `gyroUnfilt`), `RPM_FILTER`, `D_LPF`, `DSHOT_RPM_TELEMETRY`, `FEEDFORWARD`, `GPS_RESCUE_*`, `RTH`…). Поток: 2 кГц с полным набором полей — порядка 60–100 КБ/с → 16 МБ flash хватает на 3–4 минуты; SD — часы. Внешний логгер — функция Blackbox на UART во вкладке Ports (`serial <id> 128 …` с blackbox baud); отдельных `blackbox_uart`/`blackbox_baud` в 4.5 и 2025.12 нет.

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

## practice

### Подготовка оборудования и ПО

Аппаратно:
- FC с flash или SD-слотом,
- ESC с Bidirectional DShot (BLHeli_32/Bluejay),
- качественная и механически жёсткая сборка.

Настройка:
- включить `BLACKBOX`,
- выставить `logging rate` (обычно 2 kHz),
- для шумового анализа использовать `debug_mode = GYRO_SCALED`,
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

### Использование PIDToolbox

PIDToolbox полезен для:
- оценки задержки фильтров,
- сравнения спектров в dB,
- анализа step response.

### Пошаговая настройка фильтров

1. Запишите лог с `GYRO_SCALED` и `throttle sweep`.
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
  - Что проверить/сделать: проверить `E = 0%` в Motors, включить RPM-фильтр (в 4.5 он есть только на гироскопе; отдельного D-term RPM-фильтра нет).

- Симптом: всплески в `20–100 Гц`.
  - Возможная причина: недостаточные P/D или избыточная фильтрация (задержка).
  - Что проверить/сделать: проверить задержку в PIDToolbox, скорректировать фильтры и PID.

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
  - Что сделать: включить поле или `debug_mode = GYRO_SCALED`.

## references

- Blackbox flight data recorder — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Blackbox logging internals | https://www.betaflight.com/docs/development/Blackbox-Internals | primary | A
- Betaflight Blackbox Explorer | https://github.com/betaflight/blackbox-log-viewer | primary | A
- How to Use Blackbox in Betaflight — Oscar Liang | https://oscarliang.com/blackbox/ | secondary | B
- How to Tune FPV Drone Filters & PID with Blackbox — Oscar Liang | https://oscarliang.com/pid-filter-tuning-blackbox/ | secondary | B
