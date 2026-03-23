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
  - title: "How to Configure the Receiver in Betaflight — SpeedyBee"
    url: "https://support.speedybee.cn/?s=teched&l=en&t=a&p=0&i=124433541697114112"
    tier: secondary
    stack: betaflight
  - title: "How to Set Up Your Receiver in Betaflight — SpeedyBee F745AIO"
    url: "https://speedybee.zendesk.com/hc/en-us/articles/13844536933787-How-to-set-up-your-receiver-in-Betaflight-configurator-on-SpeedyBee-F745AIO-flight-controller"
    tier: secondary
    stack: betaflight
  - title: "How to Set Up Your SBUS Receiver in Betaflight — SpeedyBee F7 V3"
    url: "https://speedybee.zendesk.com/hc/en-us/articles/15739653255963-How-to-set-up-your-SBUS-receiver-in-Betaflight-configurator-on-SpeedyBee-F7-V3-flight-controller"
    tier: secondary
    stack: betaflight
  - title: "Common Issues with ELRS Receivers — SpeedyBee"
    url: "https://docs.speedybee.cn/fpv/receiver/common-issues-with-elrs-receivers/how-to-set-up-your-receiver-in-betaflight-configurator.html"
    tier: secondary
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
- **Serial Rx** + выбор протокола во вкладке **Configuration**;
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

С **4.4.0** при сборке через **Cloud Build** в прошивку попадают только выбранные **протоколы приёмника**. По умолчанию часто включены **SBUS**, **CRSF**, **GHST**. **IBUS**, **Spektrum** и др. нужно **явно отметить** при сборке — иначе приёмник «молчит» при любой распайке.

### Ограничения MSP

**MSP** нужен конфигуратору и части устройств. Ограничение: одновременно **не более трёх** UART с включённым **MSP**; четвёртый может привести к сбросу настроек MSP после перезагрузки.

**Совет:** соединение с ПК по **USB** обычно занимает отдельный канал; не переназначайте его под приёмник, не понимая схемы платы.

## practice

### Шаг 1. Идентификация UART на FC

1. Найдите **распиновку** (шёлк на плате или сайт производителя).
2. UART подписаны как **UART1…** или **RX1/TX1** и соответствуют строкам во вкладке **Ports**.

**Совет:** **USB** часто «сидит» на **UART1** или отдельном USB-мосте — этот порт не выбирайте под приёмник без чтения схемы.

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

1. После перезагрузки — **Configuration** → раздел **Receiver**.
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

## references

- Ports Tab — Betaflight Documentation | https://www.betaflight.com/docs/wiki/app/ports-tab | primary | A
- How to Configure the Receiver in Betaflight — SpeedyBee | https://support.speedybee.cn/?s=teched&l=en&t=a&p=0&i=124433541697114112 | secondary | B
- How to Set Up Your Receiver in Betaflight — SpeedyBee F745AIO | https://speedybee.zendesk.com/hc/en-us/articles/13844536933787-How-to-set-up-your-receiver-in-Betaflight-configurator-on-SpeedyBee-F745AIO-flight-controller | secondary | B
- How to Set Up Your SBUS Receiver in Betaflight — SpeedyBee F7 V3 | https://speedybee.zendesk.com/hc/en-us/articles/15739653255963-How-to-set-up-your-SBUS-receiver-in-Betaflight-configurator-on-SpeedyBee-F7-V3-flight-controller | secondary | B
- Common Issues with ELRS Receivers — SpeedyBee | https://docs.speedybee.cn/fpv/receiver/common-issues-with-elrs-receivers/how-to-set-up-your-receiver-in-betaflight-configurator.html | secondary | B
- Connecting EZ ID to Betaflight for GPS Passthrough — Flite Test | https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough | secondary | B
