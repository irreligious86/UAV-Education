---
id: bf-ports
title: "Порты и приёмник: настройка UART и подключение RC-линка"
level: L1
readingTime: "30 мин"
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
---

## summary

**UART** — основа подключения приёмника, GPS, телеметрии, VTX и др. к полётному контроллеру в Betaflight. От вкладки **Ports** зависит, дойдёт ли управление до прошивки.

**В статье:**

- как читать **распиновку** и не занять порт под USB;
- **распайка** под SBUS, CRSF/ELRS, FPort, IBUS, Spektrum;
- **Serial Rx** во вкладке **Ports** + выбор протокола во вкладке **Receiver**;
- типичные сбои (**MSP**, лимиты, F4/SBUS).

## theory

### Что такое UART и зачем настройка портов

**UART** — последовательный интерфейс: пара **TX** (передача) и **RX** (приём). Во вкладке **Ports** каждому физическому UART назначают роль: **Serial RX**, **GPS**, телеметрия, **MSP** и т.д.

**Правило:** на одном UART в один момент — **одна основная роль** для потока данных. Совмещение, например, **Serial Rx** и **Telemetry Output** на одном порту без понимания протокола часто даёт конфликт и «ломает» сохранение настроек.

### Типы приёмников и распайка

Протокол задаёт и проводку, и пункт **Serial Receiver Provider** в конфигураторе.

- **SBUS** (FrSky, Futaba, часть DJI) — в BF: **SBUS**. Сигнал с приёмника → **RX** выбранного UART (не на TX).
- **CRSF** (TBS Crossfire, **ExpressLRS**) — в BF: **CRSF**. **RX приёмника → TX FC**, **TX приёмника → RX FC** (классическое перекрёстное соединение для полного дуплекса).
- **FPort** (FrSky) — **FrSky FPort**; один провод, инверсия/пин зависят от платы и версии — сверяйтесь с мануалом FC.
- **IBUS** (FlySky, Turnigy) — **IBUS**, сигнал → **RX**.
- **Spektrum DSM** — **SPEKTRUM1024** / **SPEKTRUM2048**, сигнальный провод по документации приёмника.

**F4 и SBUS:** на части плат **нет** аппаратного инвертора под инвертированный SBUS — используйте выделенный пин **SBUS** на FC или другой протокол (**FPort** и т.д.), иначе понадобится внешний инвертор.

### Betaflight 4.4+ и Cloud Build

С **4.4.0** при сборке через **Cloud Build** в прошивку попадают только выбранные **протоколы приёмника**. По умолчанию в Firmware Flasher отмечен только **CRSF**; **SBUS** и **GHST** тоже нужно выбрать вручную. **IBUS**, **Spektrum** и др. нужно **явно отметить** при сборке — иначе приёмник «молчит» при любой распайке.

### Ограничения MSP

**MSP** нужен конфигуратору и части устройств. Ограничение: одновременно **не более трёх** UART с включённым **MSP**; с четвёртым конфигурация портов считается невалидной и при загрузке **вся** сбрасывается к умолчаниям.

**Совет:** соединение с ПК по **USB** обычно занимает отдельный канал; не переназначайте его под приёмник, не понимая схемы платы.

### Команда `serial`: что хранится на самом деле
Вкладка Ports — обёртка над `serial <id> <маска функций> <msp baud> <gps baud> <telemetry baud> <blackbox baud>`: идентификатор порта (в 4.5: 0 = UART1, 1 = UART2, … 20 = VCP/USB, 30+ = SoftSerial; в 2025.12 `diff` пишет имена, например `serial UART3 64 …`), битовая маска функций (MSP = 1, GPS = 2, … Serial RX = 64, Blackbox = 128, ESC Sensor, SmartAudio, Tramp, MSP DisplayPort — свои биты; точные значения — перечисление `serialPortFunction_e` в `src/main/io/serial.h`), и скорости. Поэтому `diff all` содержит строки вроде `serial 2 64 115200 57600 0 115200` — UART3 = Serial RX. Читать их полезно при переносе конфигов между платами: номера UART у разных плат разные.

### Функции по портам: совместимость
| Функция | Провода | Может делить порт с | Замечания |
|---|---|---|---|
| Serial RX (CRSF) | TX+RX | ни с чем | полный дуплекс, телеметрия в том же порту |
| Serial RX (SBUS) | RX | — | инвертор на F4 |
| GPS | TX+RX | — | 57600/115200, UBX; `gps_auto_config` |
| MSP (конфигуратор/компьютер) | TX+RX | — | ≤ 3 портов с MSP |
| MSP DisplayPort (HD OSD) | TX+RX | — | 115200, VTX-настройки через тот же порт |
| ESC Sensor (телеметрия ESC) | RX | — | один общий провод от всех ESC |
| VTX SmartAudio / Tramp | TX | — | один провод; SA 4800 бод |
| Telemetry (SmartPort/MAVLink/LTM) | TX (или TX+RX) | — | для пульта/наземки |
| Blackbox (внешний логгер OpenLog) | TX | — | редко |
| SoftSerial | любые 2 ноги | — | до 19200 (прошивка ограничивает), MSP и Serial RX на нём запрещены |
Нет ресурсов на всё? `resource serial_tx 11 A09`/`resource serial_rx 11 A10` — softserial на свободных падах (LED, PPM), с оговоркой по CPU.

### Разобранный пример: распределить 5 устройств по 4 UART на F405
Устройства: ELRS (CRSF), GPS, цифровой VTX (DisplayPort), ESC-телеметрия, SmartAudio-VTX — нет: цифровой и аналоговый VTX одновременно не бывает; пусть аналоговый VTX со SmartAudio + камера с RunCam-протоколом. UART1 — CRSF (не SBUS-порт нужен), UART2 — GPS, UART3 — SmartAudio (TX-пин), UART4 — ESC Sensor (RX-пин), RunCam Device — на SoftSerial 11 по LED-паду. Правило: сначала полнодуплексные (CRSF, GPS, DisplayPort), потом однопроводные, потом softserial для некритичного.

{{diagram:bf-uart-plan|Разобранный пример: пять устройств на четырёх UART F405 — сначала полнодуплексные, потом однопроводные, потом softserial.}}

## practice

### Шаг 1. Идентификация UART на FC

1. Найдите **распиновку** (шёлк на плате или сайт производителя).
2. UART подписаны как **UART1…** или **RX1/TX1** и соответствуют строкам во вкладке **Ports**.

**Совет:** **USB** на STM32-платах — отдельный виртуальный порт (строка USB VCP в Ports), а не UART1; исключение — редкие платы с внешним USB-UART мостом — этот порт не выбирайте под приёмник без чтения схемы.

### Шаг 2. Физическое подключение приёмника

1. **Обесточить** FC перед пайкой/вставкой в разъём.
2. Для приёмника взять **свободный** UART (часто удобно оставить канал USB как есть и занять **UART2/UART3**).
3. Распаять по таблице выше (**SBUS → RX**, **CRSF → перекрёстно** и т.д.).
4. Проверить **пайку**, отсутствие **КЗ** между соседними пинами.

### Шаг 3. Вкладка Ports

1. Подключить FC по **USB**, открыть **Betaflight Configurator**.
2. **Ports** — найти строку **UART**, куда идёт приёмник.
3. **Не отключать MSP** на том UART, который одновременно нужен для связи с ПК (см. мануал платы).
4. Включить только **Serial Rx** на выбранном UART; **остальные функции** на том же UART — выключить (**MSP**, лишняя телеметрия и т.д., если они конфликтуют с вашей схемой).
5. **Save and Reboot**.

### Шаг 4. Протокол приёмника (Configuration)

1. После перезагрузки — вкладка **Receiver**.
2. **Receiver Mode:** **Serial-based receiver** (как в подсказке конфигуратора).
3. **Serial Receiver Provider** — строго под железо:

   - TBS Crossfire / **ELRS** → **CRSF**
   - FrSky **SBUS** → **SBUS**
   - FrSky **FPort** → **FrSky FPort**
   - FlySky / Turnigy → **IBUS**
   - Spektrum → **SPEKTRUM1024** / **SPEKTRUM2048**

4. **Save and Reboot**.

### Шаг 5. Проверка Receiver

1. Приёмник **связан** с пультом (индикация по инструкции).
2. Вкладка **Receiver** — движение стиков и тумблеров **двигает ползунки** каналов.
3. Диапазон типично **~1000–2000**, центр **~1500**.

### Шаг 6. Дополнительно

- Ползунки «не те» каналы — **Channel Map** (**AETR**, **TAER** …) на **Receiver**.
- Края диапазона кривые — **endpoints** на пульте или `rxrange` в **CLI**.
- **Телеметрия на пульт** (CRSF/ELRS): обычно идёт тем же UART, что управление; при необходимости проверьте опции **Telemetry** в **Configuration** для вашей связки.

## diagnostics

- **Симптом:** После сохранения портов и перезагрузки настройки «откатились».
  - Возможная причина: конфликт функций на одном UART (**Serial Rx** + лишний **MSP** и т.п.) или лимит **MSP** на трёх портах.
  - Что сделать: во вкладке **Ports** оставить на UART приёмника только нужное; убедиться, что не больше трёх портов с **MSP**; сохранить и перезагрузить.

- **Симптом:** В **Receiver** ползунки не двигаются, приёмник в линке.
  - Возможная причина: **Serial Rx** не на том UART; неверный **Provider**; прошивка без нужного протокола (**Cloud Build**).
  - Что сделать: проверить **Ports** и **Configuration**; для BF **4.4+** пересобрать прошивку с нужным протоколом приёмника.

- **Симптом:** CRSF/ELRS работает, на пульте нет телеметрии.
  - Возможная причина: выключена телеметрия в настройках связки или не **CRSF** как провайдер.
  - Что сделать: **Serial Receiver Provider = CRSF**; включить телеметрию по мануалу ELRS/пульта.

- **Симптом:** SBUS на F4 не заводится.
  - Возможная причина: нет инвертора, сигнал идёт не на пин **SBUS** / не тот UART.
  - Что сделать: пин **SBUS** на плате, **FPort**, внешний инвертор или смена протокола.

- **Симптом:** Ползунки двигаются, но не укладываются в 1000–2000.
  - Возможная причина: **endpoints** на пульте; не настроен `rxrange`.
  - Что сделать: выставить ход на пульте; при необходимости **`rxrange`** в CLI.

- **Симптом:** После настроек GPS passthrough «пропадают» MSP-настройки.
  - Возможная причина: превышен лимит **трёх** портов с **MSP**.
  - Что сделать: отключить **MSP** там, где не нужен; оставить не более трёх UART с MSP.
- **Симптом:** после сохранения Ports конфигуратор «отваливается»
  - Возможная причина: отключён MSP на порту USB/VCP или включён MSP на 4-м порту.
  - Что сделать: подключение через другой порт/DFU, `serial 20 1 115200 …` для VCP.
- **Симптом:** ESC Sensor не даёт телеметрию
  - Возможная причина: провод на TX вместо RX, ESC без телеметрии, не включён `esc_sensor`.
  - Что сделать: RX-пин, прошивка ESC, `feature ESC_SENSOR` в CLI (или bidirectional DShot как альтернатива для RPM).

## references

- Ports Tab — Betaflight Documentation | https://www.betaflight.com/docs/wiki/app/ports-tab | primary | A
- Serial (UART) configuration — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Serial | primary | A
- Betaflight Setup Guide — receiver and ports | https://betaflight.com/docs/wiki/getting-started/setup-guide | primary | A
- ExpressLRS — Configuring the flight controller | https://www.expresslrs.org/quick-start/receivers/configuring-fc/ | primary | A
- Connecting EZ ID to Betaflight for GPS Passthrough — Flite Test | https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough | secondary | B
