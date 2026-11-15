---
id: bf-servos-pwm
title: "Сервы, PWM и таймеры: `resource SERVO`, `servo`, `smix`, SERVO_TILT и channel forwarding"
level: L2
readingTime: 50 мин
firmware: Betaflight 4.5 (исходник 4.5-maintenance, 4.5.6); отличия 2025.12 отмечены
status: published
added: 2026-11-14
tags:
  - Betaflight
  - сервы
  - PWM
  - таймеры
  - resource
  - подвес
  - CLI
related:
  - bf-cli
  - f-motors-esc
  - el-power-design
  - inav-setup-wing
  - ap-quadplane
  - payload-gimbal
  - bf-custom
next:
  - payload-gimbal
---

## summary
Серва на квадрике Betaflight — это не «подключил и работает»: прошивка должна уметь сервы (в Cloud Build — опция SERVOS), выход должен сидеть на таймере, который не занят DShot, питание — от отдельного BEC, а `smix` на квадрике вообще не применяется. Модуль разводит три разных «PWM» (моторный PWM/OneShot, DShot, сервоимпульс 1000–2000 мкс на 50–333 Гц), объясняет таймеры и каналы STM32/AT32, чтение `timer`, `resource`, `dma show` и перенос сервы на свободный пад, разбирает по исходнику 4.5 команды `servo` и `smix`, фичи SERVO_TILT и CHANNEL_FORWARDING и собирает простой подвес пан/тилт. Лабораторная: Python-скрипт разбирает настоящий конфиг SpeedyBee F405 V4 из ветки `4.5-config` и таблицу таймеров F405 из исходника, находит пады под 50 Гц при DShot600 на моторах и считает импульс сервы по формулам `servos.c`; затем стол без пропов, серва от отдельного BEC, тестер или осциллограф, и тест подвеса.

## theory
### Три разных «ШИМ» на одной плате
Новичок называет «ШИМом» всё, что идёт из пада. На деле это три разных сигнала:

| Сигнал | Что передаётся | Период / частота | В Betaflight 4.5 |
|---|---|---|---|
| Моторный PWM | импульс 1000–2000 мкс | `motor_pwm_rate` 480 Гц (200–32000); для PWM всегда асинхронно и не выше 480 Гц, для OneShot/Multishot — только при `use_unsynced_pwm` | `motor_pwm_protocol = PWM`, старые ESC с калибровкой |
| OneShot125 / 42 / Multishot | короткий импульс 125–250 / 42–84 / 5–25 мкс | раз в цикл PID (синхронно) | там же; аналог, нужна калибровка |
| DShot150/300/600 | **цифровой** 16-битный кадр с CRC; DShot600 = 600 кбит/с, бит 1.667 мкс, кадр ≈ 26.7 мкс | раз в цикл PID, «частоты» нет | `DSHOT600` по умолчанию; на F4/G4 с bidir прошивка сама ставит DSHOT300 (`config/config.c`) |
| Сервоимпульс | ширина 1000–2000 мкс (центр 1500) задаёт угол | 50 Гц (20 мс) у аналоговых, до ~333 Гц у цифровых | `servo_pwm_rate` 50 (50–498) |

DShot — не ШИМ: ESC читает биты, а не ширину импульса. Серве всё равно, как часто приходит импульс (в пределах её спецификации), важна **ширина**. Аналоговая серва на 333 Гц может гудеть и греться — частоту выше 50 Гц ставь только для цифровых и по паспорту (в описании `servo_pwm_rate` в INAV: «большинство цифровых серв поддерживают около 330 Гц»). На 498 Гц период 2008 мкс — импульс 2000 ещё влезает, но предел CLI `servo` (до 2500 мкс) уже нет.

PWM-*входы* тоже живы: `feature RX_PPM` и `RX_PARALLEL_PWM` (`input_filtering_mode`, по умолчанию OFF) захватывают импульсы приёмника таймером в режиме input capture. В 4.5 `USE_RX_PPM`/`USE_RX_PWM` стоят в некоудовом блоке `common_pre.h`, а в списке опций Cloud Build API их нет. Для облачной сборки считай, что их нет.

### Таймер, канал, пад
В STM32 (и AT32F435) ШИМ делает аппаратный **таймер** TIMx: счётчик с предделителем PSC и периодом ARR. У таймера до 4 **каналов** CH1–CH4 (у TIM1/TIM8 ещё инверсные CH1N–CH3N), каждый канал выведен на одну-две ножки через альтернативную функцию AF. Канал выбирает только **ширину** импульса (регистр CCR), а **период и тактирование общие** для всего таймера. Отсюда главное правило: все выходы одного таймера работают в одном протоколе и на одной частоте.

Цифры из лабораторной (F405, таймер на шине 84 МГц):
- DShot600: PSC 6, ARR 19 → бит 1.667 мкс (`MOTOR_DSHOT600_HZ` 12 МГц, `MOTOR_BITLENGTH` 20);
- серва 50 Гц: PSC 83, ARR 19999 → тик 1 мкс, кадр 20 мс (`servoDevInit()` → `pwmOutConfig(…, PWM_TIMER_1MHZ, 1 МГц / servo_pwm_rate, …)`).

Один таймер не может держать оба режима. Betaflight это **не проверяет**: `timerAllocate()` отказывает, только если занят тот же пин-канал, а соседний канал того же таймера отдаёт без вопросов. Сервы инициализируются после моторов (`fc/init.c`: `motorDevInit` раньше `servoDevInit`), поэтому серва на канале моторного таймера перепишет его базу времени, и DShot на этих моторах сломается. То же со всем, что живёт на таймере: LED_STRIP (800 кГц + DMA), CAMERA_CONTROL (аппаратный ШИМ 84 МГц / 128), PPM.

DShot бывает двух видов. **Timer + DMA**: каждый моторный пад — канал своего таймера плюс поток DMA. **Bitbang**: моторы дёргаются как GPIO по DMA, а такт задаёт таймер-«пейсер» TIM1 или TIM8 (`dshot_bitbang_timer` AUTO/TIM1/TIM8). При bitbang таймеры моторных падов свободны, но TIM1/TIM8 трогать нельзя. `dshot_bitbang = AUTO` на F4 включает bitbang только вместе с `dshot_bidir`, на F7/H7/G4/AT32 — всегда (`isDshotBitbangActive()`). Конфиг платы может это переопределить: у SpeedyBee F405 V4 `DEFAULT_DSHOT_BITBANG = OFF`. Серве DMA не нужен; у пада сервы dmaopt может быть −1.

### Как читать карту платы
- `resource` — какие функции назначены на какие пины (`resource SERVO 1 B15`). `resource show` — кто реально владеет пинами после загрузки, `resource show all` — плюс `timer show` и `dma show`.
- `timer show` — какие каналы каких таймеров заняты и кем (`TIM12: CH2 : SERVO 1`), `timer <pin> list` — какие таймеры есть у ножки (`# AF9: TIM12 CH2`), `timer <pin> AF<n>` — выбрать. `timer list` без пина в 4.5 печатает «NOT IMPLEMENTED YET».
- `dma show` — занятые потоки DMA, `dma pin <pin> <opt>` — сменить поток.
- Нумерация: `resource SERVO` и `resource MOTOR` считают **с 1**, а `servo`, `smix` и вкладка Servos — **с 0**. `resource SERVO 1` = серва 0 во вкладке.
- `resource SERVO 2 B10`, когда B10 держит `MOTOR 7`, только печатает `NOTE: B10 already assigned to MOTOR 7.` и не отвязывает мотор. Освобождай явно: `resource MOTOR 7 NONE`.
- `servoDevInit()` берёт `SERVO 1, 2, 3…` по порядку и останавливается на первом пустом. `SERVO 1 NONE` + `SERVO 2 B10` = ни одной сервы.

{{diagram:bf-servo-timer-map|На SpeedyBee F405 V4 моторы M1–M4 целиком занимают TIM4 и TIM3, поэтому серва идёт на TIM2 (пад M7) и TIM12 (S9), а TIM12 надо освободить от CAMERA_CONTROL.}}

### Питание: никогда от 5 В полётника (кроме микросервы)
Серва — мотор с редуктором. MG996R по паспорту берёт 500–900 мА в движении и **2.5 А на упоре** при 6 В. Две такие сервы на упоре — 5 А. BEC полётника рассчитан на единицы ампер (смотри паспорт своей платы) и уже кормит приёмник, камеру и GPS. Просадка 5 В перезагружает MCU в воздухе. Правила:
1. Серву больше микро (9 г класса) питай от **отдельного BEC** 5–6 В или 7.4–8.4 В для HV-серв, с запасом по току ≥ суммы токов упора.
2. **Общая земля** BEC, сервы и полётника обязательна: сигнал меряется относительно земли полётника.
3. От полётника к серве идёт только сигнал (и земля). Плюс от BEC.
4. Электролит 470–1000 мкФ на шине серв у разъёма гасит броски при старте. Если серва дёргается при газе — ищи общую землю и наводки, а не «баг прошивки».
5. Сервы двигаются **и в дизарме**: `writeServos()` идёт каждый цикл PID без проверки арма (кроме хвостовой сервы трикоптера при `tri_unarmed_servo = OFF`). Подвес дёрнется при подаче питания.

### Сервы в Betaflight 4.5: что собрано и как выходы раздаются
`USE_SERVOS` стоит в блоке `#if !defined(CLOUD_BUILD) && !defined(SITL)` файла `target/common_pre.h`. Локальная «полная» сборка сервы имеет, а **Cloud Build — только с опцией SERVOS** (Other Options в Cloud Build API; в 2025.12 их включает и пакет WING). SITL 4.5 серв не имеет вовсе, поэтому лабораторная — модель на Python. Нет команд `servo`/`smix` в CLI и вкладки Servos — значит, нет опции в сборке. До 8 серв (`MAX_SUPPORTED_SERVOS`), 1 при `USE_QUAD_MIXER_ONLY`.

Сервы включаются, если их требует миксер (`TRI`, `FLYING_WING`, `AIRPLANE`, `CUSTOMAIRPLANE`, `CUSTOMTRI`, `GIMBAL`…) или включена `feature SERVO_TILT` / `feature CHANNEL_FORWARDING`. Порядок физических выходов задаёт `writeServos()` (вывод модели, шаг 3):
- сначала сервы миксера (для `CUSTOMAIRPLANE`: SERVO 1 ← servo[2] FLAPS, SERVO 2 ← servo[3] FLAPPERON_1, … SERVO 6 ← servo[7] THROTTLE);
- потом две сервы подвеса (servo[0] — тангаж, servo[1] — крен), если SERVO_TILT;
- потом AUX-каналы, если CHANNEL_FORWARDING.

**`smix` на квадрике не делает ничего.** `servoTable()` вызывает `servoMixer()` только для самолётных и прочих «серво»-миксеров. Свои правила `smix` грузятся только для `CUSTOMAIRPLANE` и `CUSTOMTRI` (`servoConfigureOutput()`). У `QUADX` подвес работает по отдельной формуле SERVO_TILT.

### `servo`: конечные точки, rate, forward
`servo <i> <min> <max> <middle> <rate> <forward>` — 6 чисел, i = 0…7. По умолчанию `servo 0 1000 2000 1500 100 -1`. CLI требует 500 ≤ min ≤ middle ≤ max ≤ 2500 и rate −100…100. `forward` — индекс RC-канала с 0 (4 = AUX1, 5 = AUX2), −1 — нет. Документация betaflight.com (Mixer) даёт старый синтаксис с `angleMin/angleMax` — в 4.5 его нет. Если задан `forward`, вместо `middle` берётся канал, пересчитанный из 1000…2000 в min…max (`determineServoMiddleOrForwardFromChannel()`). Результат всегда обрезается в min…max. Реверс подвеса SERVO_TILT — отрицательным `rate`. Реверс forward-канала — на пульте: min > max CLI не примет.

`servo_center_pulse` (1500) в 4.5 используется только в `servoDevInit()` как начальное значение канала, и `pwmOutConfig()` тут же обнуляет CCR. Центр задаёт `middle` в `servo`.

### `smix`: правила миксера серв
`smix <rule> <servo> <source> <rate> <speed> <min> <max> <box>`: rule 0…15 (`MAX_SERVO_RULES` = 2 × 8), servo 0…7, source 0…13, rate −100…100, speed 0…255, min/max 0…100 (min < max), box 0…3. Источники: 0–2 — стабилизированные крен/тангаж/рыскание (`pidSum × 0.7`, в PASSTHRU — команда стика), 3 — газ, 4–7 — RC крен/тангаж/рыскание/газ, 8–11 — AUX1–AUX4, 12–13 — тангаж/крен подвеса. Правила суммируются. Каждое правило режется в min…max процентов хода **целевой** сервы (0 % = min, 50 % = центр). Сумма умножается на `rate` из `servo` и прибавляется к `middle`. Особенности кода:
- правило с `rate = 0` **обрывает** таблицу: всё после него игнорируется;
- `speed` — шаг на **цикл PID**: speed 10 на 8 кГц проходит 0 → 500 за 6.2 мс, практически без замедления;
- `smix reverse <servo> <source> r|n` переворачивает знак после ограничения правила; `smix reset` стирает правила и все реверсы;
- box 1–3 — правило работает только в режиме SERVO1–3 (есть в Modes только при `CUSTOMAIRPLANE`).

Таблица номеров серв на странице Mixer (2 = ELEVATOR, 6 = THROTTLE, 7 = FLAPS) **не совпадает** с `servoIndex_e` в 4.5: 2 = FLAPS, 3/4 = FLAPPERON_1/2, 5 = RUDDER, 6 = ELEVATOR, 7 = THROTTLE. Верь исходнику.

### SERVO_TILT, CAMSTAB и channel forwarding
`feature SERVO_TILT` даёт две сервы подвеса и режим CAMSTAB (id 8) в Modes. Без CAMSTAB сервы стоят в `middle` (или идут за forward-каналом). С CAMSTAB в режиме `gimbal_mode = NORMAL` (по умолчанию):

`импульс = constrain(middle_или_forward + rate × угол_в_десятых_градуса / 50, min, max)`

То есть **rate/5 мкс на градус** наклона рамы. Для сервы, проходящей 90° за 1000 мкс (11.1 мкс/°), нужен rate = 5 × 11.1 ≈ 56. С rate 100 подвес перекомпенсирует в 1.8 раза и упирается в 1000/2000 уже на ±25°. `MIXTILT` смешивает тангаж и крен для дифференциального подвеса. Если камера уходит не туда — меняй знак `rate`.

`feature CHANNEL_FORWARDING` выводит AUX-каналы на оставшиеся выходы серв **как есть**, начиная с `channel_forwarding_start` (по умолчанию 4 = AUX1). Значения не ограничиваются min/max — конечные точки задаются на пульте. С SERVO_TILT forwarding начинается с SERVO 3.

{{diagram:chart-bf-servo-tilt-pulse|SERVO_TILT добавляет rate/5 мкс на градус: при rate 100 подвес перекомпенсирует и упирается в 1000/2000 на ±25°, rate 56 для сервы 90°/1000 мкс держит камеру с ошибкой ≤ 0.3°.}}

### Справочная таблица
| Команда / переменная | По умолчанию | Диапазон | Смысл |
|---|---|---|---|
| `resource SERVO <n> <pin>` | из конфига платы (`SERVO1_PIN`…) | n 1–8, пин или NONE | пад сервы; номера с 1 |
| `servo <i> <min> <max> <mid> <rate> <fwd>` | `1000 2000 1500 100 -1` | i 0–7; 500–2500; rate ±100; fwd −1…17 | конечные точки, масштаб, forward-канал |
| `smix <r> <servo> <src> <rate> <speed> <min> <max> <box>` | пусто | r 0–15, src 0–13, speed 0–255, box 0–3 | правило миксера; только `CUSTOMAIRPLANE`/`CUSTOMTRI` |
| `smix reset` / `load <mixer>` / `reverse <s> <src> r\|n` | — | — | стереть / загрузить шаблон / реверс источника |
| `servo_pwm_rate` | 50 Гц | 50–498 | частота кадров всех серв |
| `servo_center_pulse` | 1500 | 750–2250 | начальное значение канала при инициализации |
| `servo_lowpass_hz` | 0 (выкл.) | 0–400 | biquad ФНЧ серв на частоте PID (в docs — `servo_lowpass_freq`/`_enable`, таких имён в 4.5 нет) |
| `channel_forwarding_start` | 4 (AUX1) | 4–18 | первый RC-канал для forwarding |
| `tri_unarmed_servo` | ON | OFF/ON | хвостовая серва трикоптера в дизарме |
| `gimbal_mode` | NORMAL | NORMAL/MIXTILT | формула SERVO_TILT |
| `feature SERVO_TILT` / `CHANNEL_FORWARDING` | выкл. | — | подвес (CAMSTAB, id 8) / AUX → сервы |
| `motor_pwm_protocol` | DSHOT600 (от платы) | PWM…DSHOT600, PROSHOT1000, DISABLED | протокол ESC |
| `motor_pwm_rate`, `use_unsynced_pwm` | 480, OFF | 200–32000 | частота аналогового PWM ESC |
| `dshot_bitbang`, `dshot_bitbang_timer` | AUTO, AUTO | OFF/ON/AUTO, AUTO/TIM1/TIM8 | bitbang и его таймер-пейсер |
| `camera_control_mode` | HARDWARE_PWM | HARDWARE_PWM/SOFTWARE_PWM/DAC | режим пада CAMERA_CONTROL (занимает таймер в HARDWARE_PWM) |
| `timer show`, `timer <pin> list`, `dma show` | — | — | карта таймеров, AF ножки, потоки DMA |

### INAV и ArduPilot для сравнения
| Задача | Betaflight 4.5 | INAV 8 | ArduPilot 4.6 |
|---|---|---|---|
| назначить выход | `resource SERVO n <pin>` + миксер/фича | вкладка Mixer, `timer_output_mode <timer> AUTO\|MOTORS\|SERVOS` | `SERVOn_FUNCTION` (7 — тилт подвеса, 8 — крен) |
| конечные точки | `servo i min max mid rate fwd` | `servo n min max middle rate` | `SERVOn_MIN/MAX/TRIM`, `SERVOn_REVERSED` |
| микшер | `smix … min max box`, только самолётные миксеры | `smix rule servo source rate speed conditionId` на любой платформе | функции выходов, без smix |
| частота | `servo_pwm_rate` 50 (50–498) | `servo_pwm_rate` 50 (50–498) | `SERVO_RATE` 50 (25–400) |
| подвес | SERVO_TILT + CAMSTAB | источники smix 12/13 (тангаж/крен подвеса) | `MNT1_TYPE = 1` + `SERVOn_FUNCTION` 7/8 |

Правило «один таймер — один протокол» общее для всех трёх (в ArduPilot — группы выходов, см. модуль про QuadPlane). Самолётные сервы INAV — модуль про настройку крыла, подвесы ArduPilot — модуль про полезную нагрузку.

**2025.12:** имена `servo_*`, `smix`, `servo` те же. Добавлены `SERVO5_PIN`…`SERVO8_PIN` в конфигах плат, пакет WING (включает SERVOS) и последовательный подвес `gimbal_*` (функция порта GIMBAL, опция GIMBAL). Последний к сервам не относится.

## practice
Основной путь — Python-модель. Betaflight SITL 4.5 собран без `USE_SERVOS` (условие `!defined(SITL)` в `common_pre.h`), а сборка SITL в этой среде всё равно запрещена политикой. Скрипт `bf-servos-pwm.servo_lab.py` (рабочая папка курса, этап 6) читает конфиг платы из `betaflight/config` ветки `4.5-config` и исходник 4.5: таблицу `fullTimerHardware[]` (`timer_stm32f4xx.c`), константы `servos.h`, `servos.c`, `dshot_dpwm.h`. Затем он повторяет `timerGetByTagAndIndex()`, `servoDevInit()`, `writeServos()`, `servoTable()` и `servoMixer()` с целочисленной арифметикой C. Всё ниже — реальный прогон.

### Шаг 1. Карта таймеров настоящей платы
```
python3 -I bf-servos-pwm.servo_lab.py configs/SPEEDYBEEF405V4/config.h ~/src/betaflight-4.5/src/main
```

Ядро разбора — номер вхождения пина в таблице таймеров (`TIMER_PIN_MAP(i, pin, occurrence, dmaopt)`):

```python
def timer_by_occurrence(rows, pin, occ):
    n = 0
    for p, tim, ch in rows:
        if p == pin:
            n += 1
            if n == occ:
                return tim, ch
```

```text
== 2. Timer map of SPEEDYBEEF405V4 (STM32F405), dshot_bitbang default DSHOT_BITBANG_OFF ==
resource         pin   timer  ch       clock  dmaopt
MOTOR1           B06   TIM4   CH1      84 MHz    0
MOTOR2           B07   TIM4   CH2      84 MHz    0
MOTOR3           B00   TIM3   CH3      84 MHz    0
MOTOR4           B01   TIM3   CH4      84 MHz    0
MOTOR5           C08   TIM8   CH3     168 MHz    0
MOTOR6           C09   TIM8   CH4     168 MHz    0
MOTOR7           B10   TIM2   CH3      84 MHz    0
MOTOR8           A15   TIM2   CH1      84 MHz    0
SERVO1           B15   TIM12  CH2      84 MHz   -1
CAMERA_CONTROL   B14   TIM12  CH1      84 MHz   -1
LED_STRIP        A08   TIM1   CH1     168 MHz    0
RX_PPM/UART2_RX  A03   TIM9   CH2     168 MHz   -1
```

Пад S9 (B15) уже назначен как `SERVO 1` в конфиге платы, но делит TIM12 с CAMERA_CONTROL (B14). `USE_CAMERA_CONTROL` включается автоматически, если у платы есть `CAMERA_CONTROL_PIN` и в сборке есть VTX (`common_post.h`).

### Шаг 2. Какие пады выдержат 50 Гц при DShot600
```text
TIM3: DShot600 needs PSC 6 ARR 19 (bit 1.667 us); a 50 Hz servo needs PSC 83 ARR 19999 (frame 20 ms) -> one timer cannot do both
pad/resource     timer  shares timer with  timer DShot (board)          dshot_bitbang = ON
MOTOR5           TIM8   MOTOR6             OK                           RISK: bitbang pacer
MOTOR7           TIM2   MOTOR8             OK                           OK
MOTOR8           TIM2   MOTOR7             OK                           OK
SERVO1           TIM12  CAMERA_CONTROL     only if CAMERA_CONTROL off   only if CAMERA_CONTROL off
LED_STRIP        TIM1   -                  OK                           RISK: bitbang pacer
RX_PPM/UART2_RX  TIM9   -                  NO: UART RX pin              NO: UART RX pin
== 4. servoDevInit(): outputs are taken in order until the first empty SERVO resource ==
SERVO 1 NONE, SERVO 2 B10              -> active: none
SERVO 1 B15, SERVO 2 NONE, SERVO 3 A15 -> active: SERVO 1=B15
```

Вывод: для подвеса из двух серв лучшие пады — S9 (TIM12, после отвязки камеры) и M7 (TIM2). M7 надёжнее M5: TIM2 не трогает ни DShot на TIM3/TIM4, ни bitbang, если его кто-то включит позже. Готовый конфиг (ответ на частый вопрос «как перенести серву на свободный пад, не сломав DShot»):

```
resource CAMERA_CONTROL NONE
resource MOTOR 7 NONE
resource SERVO 2 B10
feature SERVO_TILT
servo 0 1000 2000 1500 56 -1
servo 1 1000 2000 1500 56 -1
save
```

После перезагрузки `timer show` должен показать `TIM2: CH3 : SERVO 2`, `TIM12: CH2 : SERVO 1`, моторы на TIM3/TIM4 (формат строк — по `showTimers()` в `cli.c`).

### Шаг 3. Что окажется на каждом выходе
```text
QUADX + SERVO_TILT + CHANNEL_FORWARDING:
   SERVO 1 <- servo[0] GIMBAL_PITCH; SERVO 2 <- servo[1] GIMBAL_ROLL; SERVO 3 <- rcData[4] = AUX1 raw, not constrained; SERVO 4 <- rcData[5] = AUX2 raw, not constrained ...
CUSTOMAIRPLANE (no features):
   SERVO 1 <- servo[2] FLAPS; SERVO 2 <- servo[3] FLAPPERON_1; SERVO 3 <- servo[4] FLAPPERON_2; SERVO 4 <- servo[5] RUDDER ...
```

Пан (рысканье) камеры в SERVO_TILT нет. Для пан/тилт без стабилизации проще CHANNEL_FORWARDING: крутилка AUX1 → SERVO 1 (тилт), AUX2 → SERVO 2 (пан). Для тилта со стабилизацией — SERVO_TILT, а пан через forwarding ляжет на SERVO 3.

### Шаг 4. Импульс подвеса в CAMSTAB
```text
servo: 90 deg over 1000 us -> 11.11 us/deg; firmware adds rate/5 us per deg -> rate = 5*11.11 = 56
 pitch |  rate 100 servo° |   rate 56  error
  -30° |   1000 us -45.0° |   1164 us  -0.2°
  -10° |   1300 us -18.0° |   1388 us  -0.1°
   10° |   1700 us +18.0° |   1612 us  +0.1°
   20° |   1900 us +36.0° |   1724 us  +0.2°
   30° |   2000 us +45.0° |   1836 us  +0.2°
forward AUX pot at 1300 us as tilt offset, pitch +10 deg, rate 56: 1412 us; CAMSTAB off: 1300 us
```

С rate 100 при наклоне 20° серва уходит на 36° — камера «клюёт» в обратную сторону. Rate 56 держит горизонт с ошибкой ≤ 0.3°. Forward-канал (`servo 0 1000 2000 1500 56 4`) задаёт пилоту угол тилта крутилкой, стабилизация прибавляется сверху.

### Шаг 5. `smix` на самолётном миксере
Элевоны летающего крыла из RC-источников: `smix 0 3 4 100 0 0 100 0`, `smix 1 3 5 100 0 0 100 0`, `smix 2 4 4 -100 0 0 100 0`, `smix 3 4 5 100 0 0 100 0`.

```text
RC roll 1700 pitch 1300 -> servo3 (SERVO 2 pad) 1500 us, servo4 (SERVO 3 pad) 1100 us
servo 3 1100 1900 1480 60 -1, roll 1700 pitch 1300 -> servo3 1480 us (rate 60 % of 0, middle 1480)
same servo, roll 2000 pitch 2000 -> servo3 1900 us (each rule clamped to +-400 = width/2, 800*60/100 = 480, 1480+480 = 1960 -> max 1900)
rule min 30 max 70 (width 1000 -> limits -200..+200), roll 2000 -> servo3 1700 us
smix reverse 4 5 r, pitch 1300 -> servo3 1300 us, servo4 1700 us (servo 4 pitch reversed)
rule 1 with rate 0 -> table ends there: 1 of 4 rules active
speed 10, PID 8000 Hz: 0 -> 500 (1500 -> 2000 us) in 50 loops =    6.2 ms
```

Цепочка такая: правило → обрезка min/max правила → сумма → × `rate` сервы → + `middle` → обрезка min/max сервы. Серва 3 (FLAPPERON_1) выходит на пад SERVO 2: первый физический выход занят FLAPS.

### Шаг 6. Частота кадров
```text
333 Hz: period  3003 us, ARR  3002; 1000-2000 us: OK; CLI max OK
498 Hz: period  2008 us, ARR  2007; 1000-2000 us: OK; CLI max max 2500 us >= period
```

### Переход на реальное железо
**Стол, пропы сняты, АКБ через «дымоуловитель».**
1. `diff all` → файл «до». Проверь сборку: `servo` и `smix` есть в `help` (список опций — по BUILD KEY из `status`). Нет — пересобери с SERVOS.
2. Введи конфиг шага 2 под свою плату: сначала `timer <pin> list` и `resource show all`. Пад сервы не должен делить таймер с моторами, LED_STRIP, CAMERA_CONTROL и пейсером bitbang. После `save` проверь `timer show`.
3. Питание: отдельный BEC 5–6 В (по серве), земля BEC ↔ GND полётника, сигнал с пада. Конденсатор 470–1000 мкФ на шине. Мультиметром на упоре (рукой придержи качалку на 1 с) запиши ток. Он должен быть меньше номинала BEC.
4. Импульс: тестер серв в режиме измерения или осциллограф/логический анализатор на паде. Ожидаемо: период 20.0 мс (50 Гц), ширина 1500 ± 5 мкс в центре. Пульт → AUX: 1000/2000 мкс на краях forward-канала.
5. Configurator → Servos (номера с 0) или Motors: значения совпадают с замером. Подбери `min`/`max` так, чтобы серва не упиралась в механику: гул и ток на краю — признак упора. Сократи ход на 20–50 мкс.
6. Моторы: на вкладке Motors без пропов каждый мотор крутится от своего ползунка, DShot-ошибок нет. Серва при этом не дёргается.
7. Подвес: `feature SERVO_TILT`, CAMSTAB на тумблер. Наклони раму рукой на 20° по тангажу — камера должна остаться горизонтальной (уровень или приложение-уровнемер на камере, допуск ±3°). Уходит вдвое дальше — уменьши `rate`. Уходит не в ту сторону — смени знак.

**Прерывание:** запах, горячий BEC или серва, перезагрузка полётника при движении сервы, моторы дёргаются или не армятся после `resource`, серва гудит в покое дольше 2 с — отключи питание и верни `diff all` «до».

**Полёт (опционально):** висение 1–2 м в ANGLE, CAMSTAB включён. Прерывание: дрожь картинки сильнее, чем без стабилизации (включи `servo_lowpass_hz` 20–40), сброс полётника, просадка 5 В в OSD.

Лабораторная засчитывается, когда:
- (модель) скрипт запущен на конфиге своей или учебной платы и исходнике 4.5; приложена таблица таймеров и выбран пад сервы с объяснением, почему он не ломает DShot;
- (модель) посчитан `rate` SERVO_TILT для своей сервы (мкс/° из паспорта) и импульс при наклоне 10° и 20°;
- (железо) `timer show` после `save` показывает серву на своём таймере, моторы без ошибок, на осциллографе или тестере 20 мс и 1500 ± 5 мкс;
- (железо) серва питается от отдельного BEC с общей землёй, ток упора записан, наклон рамы на 20° компенсируется с ошибкой ≤ 3°.

## diagnostics
- **Симптом:** в CLI нет команд `servo`/`smix`, вкладки Servos нет
  - Возможная причина: Cloud Build без опции SERVOS (`USE_SERVOS` только в некоудовом блоке `common_pre.h`).
  - Что сделать: пересобрать с SERVOS, восстановить `diff all`.
- **Симптом:** серва не шевелится, `resource` выглядит правильно
  - Возможная причина: `SERVO 1` пуст (servoDevInit останавливается на первом пустом), не включена фича или миксер без серв, пин ещё держит `MOTOR n`.
  - Что сделать: `resource show` — владелец пина должен быть SERVO; назначать с SERVO 1 подряд; `resource MOTOR n NONE`; `feature SERVO_TILT` или `CHANNEL_FORWARDING`.
- **Симптом:** после переноса сервы два мотора не крутятся или дёргаются
  - Возможная причина: пад сервы на канале моторного таймера — `servoDevInit()` переписал базу времени DShot.
  - Что сделать: `timer show`, перенести серву на таймер без моторов (на SpeedyBee F405 V4 — TIM2/M7).
- **Симптом:** `smix` введён, а на квадрике ничего не происходит
  - Возможная причина: правила `smix` применяются только в `CUSTOMAIRPLANE`/`CUSTOMTRI`; правило с rate 0 обрывает таблицу.
  - Что сделать: для подвеса — SERVO_TILT и `servo … rate`; для самолёта — `mixer CUSTOMAIRPLANE`, правила подряд с 0.
- **Симптом:** камера стабилизируется слишком сильно или в обратную сторону
  - Возможная причина: `rate` 100 даёт 20 мкс/°; знак не тот.
  - Что сделать: rate = 5 × (мкс/° сервы), знак — по тесту наклоном.
- **Симптом:** серва упирается и гудит на краях forward-канала
  - Возможная причина: CHANNEL_FORWARDING выдаёт RC как есть, min/max `servo` не действуют.
  - Что сделать: ограничить ход на пульте (endpoints канала) или перейти на SERVO_TILT с forward-полем.
- **Симптом:** полётник перезагружается, когда серва двигается
  - Возможная причина: серва на 5 В полётника, просадка при токе упора.
  - Что сделать: отдельный BEC, общая земля, конденсатор; проверить ток упора.
  - Последствия: в полёте — дизарм и падение.
- **Симптом:** кнопки камеры через CAMERA_CONTROL перестали работать после настройки сервы
  - Возможная причина: CAMERA_CONTROL в HARDWARE_PWM на том же таймере (на SpeedyBee F405 V4 — TIM12).
  - Что сделать: `resource CAMERA_CONTROL NONE` или `set camera_control_mode = SOFTWARE_PWM` (есть на F405), либо серву на другой таймер.
- **Симптом:** аналоговая серва греется и гудит
  - Возможная причина: `servo_pwm_rate` выше её спецификации.
  - Что сделать: вернуть 50 Гц; 200–333 Гц — только для цифровых по паспорту.

## checklist
- В сборке есть SERVOS (команды `servo`/`smix` в CLI)
- Пад сервы проверен `timer <pin> list` и `timer show`: его таймер не делит ни мотор, ни LED_STRIP, ни CAMERA_CONTROL, ни пейсер bitbang
- `resource SERVO` назначены подряд с 1, старые владельцы пинов освобождены
- Серва питается от отдельного BEC, земля общая, конденсатор на шине
- Импульс проверен прибором: 20 мс и 1500 мкс в центре, края без упора
- Для подвеса `rate` посчитан по паспорту сервы, знак проверен наклоном
- Моторы на вкладке Motors без ошибок после изменения `resource`
- `diff all` до и после сохранён

## references
- servos.c — Betaflight 4.5-maintenance (servoTable, servoMixer, writeServos) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/servos.c | primary | A
- servos.h — servoIndex_e, input sources, defaults, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/servos.h | primary | A
- pwm_output.c — servoDevInit, pwmOutConfig, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/pwm_output.c | primary | A
- timer_common.c — timerAllocate, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/timer_common.c | primary | A
- timer_stm32f4xx.c — fullTimerHardware and timerClock for F4 | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/timer_stm32f4xx.c | primary | A
- cli.c — servo, smix, resource, timer, dma commands, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- common_pre.h — USE_SERVOS outside Cloud Build and SITL | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/target/common_pre.h | primary | A
- camera_control.c — CAMERA_CONTROL hardware PWM on a timer | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/camera_control.c | primary | B
- SPEEDYBEEF405V4 config.h — betaflight/config, branch 4.5-config | https://raw.githubusercontent.com/betaflight/config/4.5-config/configs/SPEEDYBEEF405V4/config.h | primary | A
- Servos & Servo Tilt — Betaflight docs | https://betaflight.com/docs/wiki/guides/current/Servos-And-SERVO_TILT-for-3-1 | primary | B
- Mixer (servo and smix sections) — Betaflight docs | https://betaflight.com/docs/wiki/guides/current/Mixer | primary | C
- Cloud Build API (build options SERVOS, WING) — Betaflight docs | https://betaflight.com/docs/development/API/Cloud-Build-API | primary | B
- INAV 8.0.1 settings.yaml (servo_pwm_rate, servo_lpf_hz) | https://raw.githubusercontent.com/iNavFlight/inav/8.0.1/src/main/fc/settings.yaml | primary | B
- ArduPilot SRV_Channels.cpp, ArduCopter-stable (SERVO_RATE) | https://raw.githubusercontent.com/ArduPilot/ardupilot/ArduCopter-stable/libraries/SRV_Channel/SRV_Channels.cpp | primary | B
- MG996R datasheet — Tower Pro (stall current 2.5 A at 6 V) | https://people.ece.cornell.edu/land/courses/ece4760/FinalProjects/f2017/kmv48_rp625/kmv48_rp625/kmv48_rp625/MG996RTowerPro.pdf | secondary | B

## notes
Страница Mixer на betaflight.com в части серв устарела относительно 4.5: синтаксис `servo` с `angleMin/angleMax` (в 4.5 — 6 чисел), `servo_lowpass_freq`/`servo_lowpass_enable` (в 4.5 — одна `servo_lowpass_hz`), таблица номеров серв для `smix` (в 4.5 2 = FLAPS, 6 = ELEVATOR, 7 = THROTTLE), «speed per loop (1 ms default)» (цикл PID сейчас 8 кГц), «smix reverse per-profile» (в 4.5 реверсы лежат в `servoParams`, профилей серв нет). Страница Servos & Servo Tilt верно говорит про нумерацию `resource` с 1, но её примеры для F1/F3 (NAZE32, SPRacing F3) к 4.5 не относятся. Аудит курса предполагал серво-лабораторную в SITL. В 4.5 SITL собран без `USE_SERVOS`, поэтому здесь модель.
