---
id: bf-ports
title: "Порти та приймач: налаштування UART і підключення RC-лінку"
level: L1
readingTime: "30 хв"
firmware: Betaflight 4.5+
status: published
tags:
  - ports
  - UART
  - receiver
  - Serial RX
  - wiring
references:
  - title: "Ports Tab — Betaflight Documentation"
    url: "https://www.betaflight.com/docs/wiki/app/ports-tab"
    tier: primary
    stack: betaflight
  - title: "Serial (UART) configuration — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/guides/current/Serial"
    tier: primary
    stack: betaflight
  - title: "Betaflight Setup Guide — receiver and ports"
    url: "https://betaflight.com/docs/wiki/getting-started/setup-guide"
    tier: primary
    stack: betaflight
  - title: "ExpressLRS — Configuring the flight controller"
    url: "https://www.expresslrs.org/quick-start/receivers/configuring-fc/"
    tier: primary
    stack: betaflight
  - title: "Connecting EZ ID to Betaflight for GPS Passthrough — Flite Test"
    url: "https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough"
    tier: secondary
    stack: betaflight
related:
  - bf-intro
  - bf-modes-osd
next:
  - bf-modes-osd
source: content/betaflight/bf-ports.md
source_hash: 381df4def8cc
---

## summary

**UART** — основа підключення приймача, GPS, телеметрії, VTX тощо до польотного контролера в Betaflight. Від вкладки **Ports** залежить, чи дійде керування до прошивки.

**У статті:**

- як читати **розпіновку** і не зайняти порт під USB;
- **розпаювання** під SBUS, CRSF/ELRS, FPort, IBUS, Spektrum;
- **Serial Rx** у вкладці **Ports** + вибір протоколу у вкладці **Receiver**;
- типові збої (**MSP**, ліміти, F4/SBUS).

## theory

### Що таке UART і навіщо налаштування портів

**UART** — послідовний інтерфейс: пара **TX** (передавання) і **RX** (приймання). У вкладці **Ports** кожному фізичному UART призначають роль: **Serial RX**, **GPS**, телеметрія, **MSP** тощо.

**Правило:** на одному UART в один момент — **одна основна роль** для потоку даних. Суміщення, наприклад, **Serial Rx** і **Telemetry Output** на одному порту без розуміння протоколу часто дає конфлікт і «ламає» збереження налаштувань.

### Типи приймачів і розпаювання

Протокол задає і проводку, і пункт **Serial Receiver Provider** у конфігураторі.

- **SBUS** (FrSky, Futaba, частина DJI) — у BF: **SBUS**. Сигнал із приймача → **RX** вибраного UART (не на TX).
- **CRSF** (TBS Crossfire, **ExpressLRS**) — у BF: **CRSF**. **RX приймача → TX FC**, **TX приймача → RX FC** (класичне перехресне з'єднання для повного дуплексу).
- **FPort** (FrSky) — **FrSky FPort**; один провід, інверсія/пін залежать від плати та версії — звіряйся з мануалом FC.
- **IBUS** (FlySky, Turnigy) — **IBUS**, сигнал → **RX**.
- **Spektrum DSM** — **SPEKTRUM1024** / **SPEKTRUM2048**, сигнальний провід за документацією приймача.

**F4 і SBUS:** на частині плат **немає** апаратного інвертора під інвертований SBUS — використовуй виділений пін **SBUS** на FC або інший протокол (**FPort** тощо), інакше знадобиться зовнішній інвертор.

### Betaflight 4.4+ і Cloud Build

З **4.4.0** під час збирання через **Cloud Build** у прошивку потрапляють лише вибрані **протоколи приймача**. За замовчуванням у Firmware Flasher позначено тільки **CRSF**; **SBUS** і **GHST** теж треба вибрати вручну. **IBUS**, **Spektrum** та ін. треба **явно позначити** під час збирання — інакше приймач «мовчить» за будь-якого розпаювання.

### Обмеження MSP

**MSP** потрібен конфігуратору та частині пристроїв. Обмеження: одночасно **не більше трьох** UART з увімкненим **MSP**; з четвертим конфігурація портів вважається невалідною і під час завантаження **вся** скидається до замовчувань.

**Порада:** з'єднання з ПК по **USB** зазвичай займає окремий канал; не перепризначай його під приймач, не розуміючи схеми плати.

### Команда `serial`: що зберігається насправді
Вкладка Ports — обгортка над `serial <id> <маска функций> <msp baud> <gps baud> <telemetry baud> <blackbox baud>`: ідентифікатор порту (у 4.5: 0 = UART1, 1 = UART2, … 20 = VCP/USB, 30+ = SoftSerial; у 2025.12 `diff` пише імена, наприклад `serial UART3 64 …`), бітова маска функцій (MSP = 1, GPS = 2, … Serial RX = 64, Blackbox = 128, ESC Sensor, SmartAudio, Tramp, MSP DisplayPort — свої біти; точні значення — перелік `serialPortFunction_e` у `src/main/io/serial.h`), і швидкості. Тому `diff all` містить рядки на кшталт `serial 2 64 115200 57600 0 115200` — UART3 = Serial RX. Читати їх корисно під час перенесення конфігів між платами: номери UART у різних плат різні.

### Функції за портами: сумісність
| Функція | Проводи | Може ділити порт з | Зауваження |
|---|---|---|---|
| Serial RX (CRSF) | TX+RX | ні з чим | повний дуплекс, телеметрія в тому самому порту |
| Serial RX (SBUS) | RX | — | інвертор на F4 |
| GPS | TX+RX | — | 57600/115200, UBX; `gps_auto_config` |
| MSP (конфігуратор/комп'ютер) | TX+RX | — | ≤ 3 портів з MSP |
| MSP DisplayPort (HD OSD) | TX+RX | — | 115200, VTX-налаштування через той самий порт |
| ESC Sensor (телеметрія ESC) | RX | — | один спільний провід від усіх ESC |
| VTX SmartAudio / Tramp | TX | — | один провід; SA 4800 бод |
| Telemetry (SmartPort/MAVLink/LTM) | TX (або TX+RX) | — | для пульта/наземки |
| Blackbox (зовнішній логер OpenLog) | TX | — | рідко |
| SoftSerial | будь-які 2 ноги | — | до 19200 (прошивка обмежує), MSP і Serial RX на ньому заборонені |
Немає ресурсів на все? `resource serial_tx 11 A09`/`resource serial_rx 11 A10` — softserial на вільних падах (LED, PPM), із застереженням щодо CPU.

### Розібраний приклад: розподілити 5 пристроїв по 4 UART на F405
Пристрої: ELRS (CRSF), GPS, цифровий VTX (DisplayPort), ESC-телеметрія, SmartAudio-VTX — ні: цифрового й аналогового VTX одночасно не буває; нехай аналоговий VTX зі SmartAudio + камера з RunCam-протоколом. UART1 — CRSF (не SBUS-порт потрібен), UART2 — GPS, UART3 — SmartAudio (TX-пін), UART4 — ESC Sensor (RX-пін), RunCam Device — на SoftSerial 11 через LED-пад. Правило: спершу повнодуплексні (CRSF, GPS, DisplayPort), потім однопровідні, потім softserial для некритичного.

{{diagram:bf-uart-plan|Розібраний приклад: п'ять пристроїв на чотирьох UART F405 — спершу повнодуплексні, потім однопровідні, потім softserial.}}

## practice

### Крок 1. Ідентифікація UART на FC

1. Знайди **розпіновку** (шовкографія на платі або сайт виробника).
2. UART підписані як **UART1…** або **RX1/TX1** і відповідають рядкам у вкладці **Ports**.

**Порада:** **USB** на STM32-платах — окремий віртуальний порт (рядок USB VCP у Ports), а не UART1; виняток — рідкісні плати із зовнішнім USB-UART мостом — цей порт не вибирай під приймач без читання схеми.

### Крок 2. Фізичне підключення приймача

1. **Знеструмити** FC перед паянням/вставлянням у роз'єм.
2. Для приймача взяти **вільний** UART (часто зручно залишити канал USB як є і зайняти **UART2/UART3**).
3. Розпаяти за таблицею вище (**SBUS → RX**, **CRSF → перехресно** тощо).
4. Перевірити **паяння**, відсутність **КЗ** між сусідніми пінами.

### Крок 3. Вкладка Ports

1. Підключити FC по **USB**, відкрити **Betaflight Configurator**.
2. **Ports** — знайти рядок **UART**, куди йде приймач.
3. **Не вимикати MSP** на тому UART, який одночасно потрібен для зв'язку з ПК (див. мануал плати).
4. Увімкнути тільки **Serial Rx** на вибраному UART; **решту функцій** на тому самому UART — вимкнути (**MSP**, зайва телеметрія тощо, якщо вони конфліктують з твоєю схемою).
5. **Save and Reboot**.

### Крок 4. Протокол приймача (Configuration)

1. Після перезавантаження — вкладка **Receiver**.
2. **Receiver Mode:** **Serial-based receiver** (як у підказці конфігуратора).
3. **Serial Receiver Provider** — строго під залізо:

   - TBS Crossfire / **ELRS** → **CRSF**
   - FrSky **SBUS** → **SBUS**
   - FrSky **FPort** → **FrSky FPort**
   - FlySky / Turnigy → **IBUS**
   - Spektrum → **SPEKTRUM1024** / **SPEKTRUM2048**

4. **Save and Reboot**.

### Крок 5. Перевірка Receiver

1. Приймач **зв'язаний** з пультом (індикація за інструкцією).
2. Вкладка **Receiver** — рух стиків і тумблерів **рухає повзунки** каналів.
3. Діапазон типово **~1000–2000**, центр **~1500**.

### Крок 6. Додатково

- Повзунки «не тих» каналів — **Channel Map** (**AETR**, **TAER** …) на **Receiver**.
- Краї діапазону криві — **endpoints** на пульті або `rxrange` у **CLI**.
- **Телеметрія на пульт** (CRSF/ELRS): зазвичай іде тим самим UART, що й керування; за потреби перевір опції **Telemetry** у **Configuration** для своєї зв'язки.

## diagnostics

- **Симптом:** Після збереження портів і перезавантаження налаштування «відкотилися».
  - Можлива причина: конфлікт функцій на одному UART (**Serial Rx** + зайвий **MSP** тощо) або ліміт **MSP** на трьох портах.
  - Що зробити: у вкладці **Ports** залишити на UART приймача тільки потрібне; переконатися, що не більше трьох портів з **MSP**; зберегти й перезавантажити.

- **Симптом:** У **Receiver** повзунки не рухаються, приймач у лінку.
  - Можлива причина: **Serial Rx** не на тому UART; неправильний **Provider**; прошивка без потрібного протоколу (**Cloud Build**).
  - Що зробити: перевірити **Ports** і **Configuration**; для BF **4.4+** перезібрати прошивку з потрібним протоколом приймача.

- **Симптом:** CRSF/ELRS працює, на пульті немає телеметрії.
  - Можлива причина: вимкнена телеметрія в налаштуваннях зв'язки або провайдер не **CRSF**.
  - Що зробити: **Serial Receiver Provider = CRSF**; увімкнути телеметрію за мануалом ELRS/пульта.

- **Симптом:** SBUS на F4 не запускається.
  - Можлива причина: немає інвертора, сигнал іде не на пін **SBUS** / не той UART.
  - Що зробити: пін **SBUS** на платі, **FPort**, зовнішній інвертор або зміна протоколу.

- **Симптом:** Повзунки рухаються, але не вкладаються в 1000–2000.
  - Можлива причина: **endpoints** на пульті; не налаштований `rxrange`.
  - Що зробити: виставити хід на пульті; за потреби **`rxrange`** у CLI.

- **Симптом:** Після налаштувань GPS passthrough «зникають» MSP-налаштування.
  - Можлива причина: перевищено ліміт **трьох** портів з **MSP**.
  - Що зробити: вимкнути **MSP** там, де не потрібен; залишити не більше трьох UART з MSP.
- **Симптом:** після збереження Ports конфігуратор «відвалюється»
  - Можлива причина: вимкнений MSP на порту USB/VCP або увімкнений MSP на 4-му порту.
  - Що зробити: підключення через інший порт/DFU, `serial 20 1 115200 …` для VCP.
- **Симптом:** ESC Sensor не дає телеметрії
  - Можлива причина: провід на TX замість RX, ESC без телеметрії, не увімкнений `esc_sensor`.
  - Що зробити: RX-пін, прошивка ESC, `feature ESC_SENSOR` у CLI (або bidirectional DShot як альтернатива для RPM).

## references

- Ports Tab — Betaflight Documentation | https://www.betaflight.com/docs/wiki/app/ports-tab | primary | A
- Serial (UART) configuration — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Serial | primary | A
- Betaflight Setup Guide — receiver and ports | https://betaflight.com/docs/wiki/getting-started/setup-guide | primary | A
- ExpressLRS — Configuring the flight controller | https://www.expresslrs.org/quick-start/receivers/configuring-fc/ | primary | A
- Connecting EZ ID to Betaflight for GPS Passthrough — Flite Test | https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough | secondary | B
