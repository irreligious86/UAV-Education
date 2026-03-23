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
    url: "https://betaflight-com.pages.dev/docs/development/Blackbox"
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
  - title: "PIDToolbox User Guide"
    url: "https://github.com/bw1129/PIDtoolbox/wiki/PIDtoolbox-user-guide"
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

## diagnostics

- Симптом: в логе гироскопа сильный пик на `100–250 Гц`.
  - Возможная причина: резонанс рамы/люфт.
  - Что проверить/сделать: проверить механику и убедиться, что dynamic notch активен.

- Симптом: шум выше `250 Гц` не подавлен.
  - Возможная причина: RPM-фильтр отключён или неверно настроен bidirectional DShot.
  - Что проверить/сделать: проверить `E = 0%` в Motors, включить Gyro/D-term RPM filters.

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

## references

Blackbox flight data recorder — Betaflight Documentation | https://betaflight-com.pages.dev/docs/development/Blackbox | primary | A
Blackbox logging internals | https://www.betaflight.com/docs/development/Blackbox-Internals | primary | A
Betaflight Blackbox Explorer | https://github.com/betaflight/blackbox-log-viewer | primary | A
How to Use Blackbox in Betaflight — Oscar Liang | https://oscarliang.com/blackbox/ | secondary | B
How to Tune FPV Drone Filters & PID with Blackbox — Oscar Liang | https://oscarliang.com/pid-filter-tuning-blackbox/ | secondary | B
PIDToolbox User Guide | https://github.com/bw1129/PIDtoolbox/wiki/PIDtoolbox-user-guide | secondary | B
IntoFPV Forum — 3D Printed Frame Tuning Discussion | https://intofpv.com/archive/index.php/thread-22141-2.html | secondary | C