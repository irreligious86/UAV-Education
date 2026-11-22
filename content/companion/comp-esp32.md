---
id: comp-esp32
title: "ESP32 и периферия"
level: L2
readingTime: 30 мин
firmware: ESP32 / EdgeTX
status: published
added: 2026-11-07
tags:
  - ESP32
  - EdgeTX
  - UART
related:
  - comp-mavlink
  - link-protocols
next:
  - comp-raspberry
---

## summary
ESP32 — идеальный «маленький companion»: UART, Wi-Fi, BLE, дисплей, копеечная цена и запуск за долю секунды. Модуль разбирает три типовых роли: периферия на борту (датчики, индикация), MAVLink-мост Wi-Fi ↔ FC и компаньон пульта. Последний — на примере проекта для RadioMaster TX16S: ESP32-S3 с экраном, который в полёте показывает телеметрию, а на земле поднимает точку доступа для настроек с телефона. Разобраны ловушки: lifecycle Lua-виджета EdgeTX, уровни UART, бюджет питания и проверяемое отключение радио.

## theory
### Три роли ESP32
1. **Бортовая периферия.** Опрос датчиков по I2C, адресные светодиоды, сервы, реле. Связь с FC по UART через MAVLink или простой текстовый протокол.
2. **MAVLink-мост.** ESP32 принимает MAVLink по UART от FC и раздаёт по Wi-Fi (UDP) телефону или ноутбуку. Так работают многие готовые Wi-Fi-телеметрии; своя версия — это несколько десятков строк.
3. **Компаньон пульта.** ESP32 подключён к AUX-порту пульта на EdgeTX, Lua-скрипт на пульте шлёт ему состояние (режим, арм, телеметрию), а ESP32 показывает это на своём дисплее и даёт интерфейс настроек.

### UART: уровни и провода
ESP32 работает на 3.3 В. Полётники и пульты на EdgeTX тоже 3.3 В на UART, но проверь мультиметром, прежде чем соединять. Провода крест-накрест, общий GND обязателен. Скорость с пультом — та, что задана в настройках порта, обычно 115200.

### EdgeTX: порт AUX и Lua
В настройках аппаратуры (Hardware) у портов AUX1/AUX2 есть режим «Lua»: тогда скрипты получают доступ к функциям `serialWrite(str)`, `serialRead([num])` и `setSerialBaudrate(baudrate)`. `serialRead` без аргумента читает до первого перевода строки, поэтому строковый протокол «одна строка — одно сообщение» ложится на него естественно.

### Ловушка: lifecycle виджета
У виджета EdgeTX две функции: `refresh()` вызывается, когда виджет виден на экране, `background()` — когда скрыт. Если положить отправку heartbeat только в `refresh()`, компаньон потеряет связь, как только пилот переключит экран. Решение: общая функция `tick()`, которую вызывают обе.

### Безопасность по умолчанию
Дизайн-решение проекта: неопределённое состояние = режим FLIGHT, Wi-Fi выключен. Точка доступа поднимается только когда ESP32 получил от пульта явное «disarmed». Любая запись настроек проходит в два шага: STAGE (подготовить) → APPLY (применить с автоматическим бэкапом), и защита от записи в полёте продублирована на обеих сторонах — и в Lua, и в прошивке ESP32.

Выключение радио должно быть проверяемым: `WiFi.mode(WIFI_OFF)` плюс `esp_wifi_stop()`, а не предположение «мы его не включали».

### Питание
ESP32-S3 с активным Wi-Fi потребляет пики в сотни миллиампер. От батареи пульта или BEC это ощутимо; в режиме FLIGHT с выключенным радио — в разы меньше. Бюджет считают по режимам, а не по среднему.

### Минимальный MAVLink-мост на ESP32 (идея кода)
UART2 (`Serial2.begin(921600, SERIAL_8N1, RX_PIN, TX_PIN)`) ↔ WiFi UDP: всё, что пришло с FC, — в UDP на адрес последнего клиента (или broadcast 14550); всё, что пришло по UDP, — в UART. Буферы 1 КБ, без парсинга MAVLink (мост прозрачен); задача на втором ядре FreeRTOS (модуль «Embedded»): ядро 0 — Wi-Fi стек, ядро 1 — UART-копирование с приоритетом выше `loop()`. Задержка такого моста — единицы мс; потери — при перегрузке Wi-Fi (2.4 ГГц делит эфир с ELRS 2.4 — на борту мост по Wi-Fi уместен только для наземной настройки, в полёте выключать).

### Датчик на борту через MAVLink
ESP32 как компонент системы: шлёт `HEARTBEAT` (свой component_id: `MAV_COMP_ID_PERIPHERAL` (158) или из диапазона USER1–USER75 (25–99)), данные — `NAMED_VALUE_FLOAT`/`NAMED_VALUE_INT` (видны в GCS и в логе `NVAL`), или `DISTANCE_SENSOR` (132) для своего дальномера — ArduPilot примет его как `RNGFND1_TYPE = 10` (MAVLink) и использует в EKF/посадке. Библиотека: `mavlink` C-headers из генератора (`common.xml`, 100 КБ flash), или минимальный ручной сборщик кадра с CRC (модуль «Протоколы MAVLink»).

### Разобранный пример: компаньон пульта (проект TX16S)
Протокол строк: пульт → ESP32 `S,<mode>,<armed>,<vbat>,<rssi>\n` каждые 500 мс; ESP32 → пульт `A,<cmd>,<arg>\n`. Состояния ESP32: FLIGHT (радио выкл; по умолчанию и при таймауте строк > 2 с) → GROUND (пульт прислал `armed=0` ≥ 3 с подряд: Wi-Fi AP, веб-настройки) → FLIGHT при любом `armed=1`. Настройки: STAGE (JSON в RAM) → APPLY (запись NVS с копией предыдущей версии) только в GROUND; Lua на пульте блокирует `APPLY`, если телеметрия показывает арм. Тест: эмулятор строк с ПК по USB-UART, сценарии переходов и таймаутов, затем реальный пульт без аппарата.

{{diagram:esp32-roles|Три роли ESP32 в курсе: мост UART ↔ Wi-Fi/BLE, собственный компонент MAVLink и компаньон пульта на порту AUX.}}

### ESP32 как полётный контроллер: что есть и чего ждать
Вопрос «можно ли ESP32 вместо полётника» решается не по цене платы, а по тому, есть ли твой чип в списке целей **той версии прошивки, на которой ты летаешь**. Состояние на 22.11.2026, проверено по исходникам целевых версий курса:

| Прошивка | ESP32 в целевой версии | Что это значит |
|---|---|---|
| ArduPilot 4.7.2 | есть HAL `AP_HAL_ESP32`, 10 описаний плат (`esp32buzz`, `esp32s3devkit`, `esp32s3m5stampfly` и др.) | только сборка из исходников под Linux; в README порта DShot, GPIO и телеметрия ESC — в списке «ещё не сделано»; у StampFly `SCHED_LOOP_RATE 150` с комментарием «flash won't go faster» при 400 Гц по умолчанию у Copter, коллекторные моторы, лог по MAVLink |
| Betaflight 2025.12.5 | нет: платформы STM32, AT32, APM32, PICO | в 2026.6 ESP32-S3 и ESP32-WROOM добавлены как **experimental** (DShot150/300, blackbox на SD; release notes, в исходниках не проверено) |
| INAV 9.1.0 | нет ни одной цели | — |
| PX4 1.17.0 | `boards/espressif/esp32`, версия 0.1 | в конфиге сборки нет ни EKF2, ни регуляторов ориентации: это заготовка, а не полётник |
| ESP-FC (отдельный проект, MIT, тег v0.2.1) | ESP32 и ESP32-S3 рекомендованы, S2, C3, RP2040, RP2350 — экспериментально | совместим с Betaflight Configurator; до 4 кГц цикла с SPI-гироскопом; ACRO, ANGLE, AIRMODE, только Quad X; удержания высоты и GPS нет; автор пишет, что это не Betaflight и часть вкладок Configurator не работает |
| ExpressLRS 4.1.0 | приёмники на ESP32, ESP32-C3, ESP32-S3 | выходы приёмника дают PWM 50–400 Гц и DShot300 прямо на ESC и сервы, но без стабилизации: для простого самолёта, не для коптера |

Почему ESP32 упирается в потолок: код исполняется из внешней SPI-флеш через кеш — отсюда 150 Гц у ArduPilot на StampFly. Радио Wi-Fi на том же кристалле делит 2.4 ГГц с ELRS (раздел про мост выше). У STM32 — встроенная флеш и DShot во всех четырёх прошивках курса.

**Правило выбора.**

1. Цель — разобраться в коде регулятора, комнатный коллекторный вуп, стенд → ESP32 подходит: ESP-FC или ArduPilot на StampFly.
2. GPS-навигация, масса больше 250 г, полёт вне прямой видимости, полезная нагрузка → STM32: F405 для Betaflight и INAV, H7 для ArduPilot и PX4 (`ap-intro`, раздел «Какую плату брать»).
3. Проверка: открой в исходниках своей версии список целей (`src/platform` у Betaflight, `libraries/AP_HAL_*/hwdef` у ArduPilot) и найди там свою плату. Не нашёл — плата не входит в релиз, и для задач из пункта 2 она не годится. На ArduPilot сверь фактическую частоту основного цикла `PM.LR` в логе с `SCHED_LOOP_RATE` и посмотри `PM.NLon` (число затянувшихся циклов): если `LR` заметно ниже заданной частоты, а `NLon` растёт — процессор не успевает.

### Место в системе

- **Получает:** MAVLink от FC по UART 3.3 В (`comp-mavlink`); строки состояния (режим, арм, батарея, RSSI) от Lua-скрипта пульта по порту AUX; питание от BEC или батареи пульта.
- **Отдаёт:** тот же поток по Wi-Fi UDP телефону или ноутбуку; `DISTANCE_SENSOR` и `NAMED_VALUE_FLOAT` как компонент системы (`mav-component`); телеметрию на свой дисплей.
- **Если ошибиться здесь:** Wi-Fi-мост оставлен включённым в полёте → он делит 2.4 ГГц с ELRS, страдает линк управления; LQ и RSSI читают в `link-elrs`. Heartbeat только в `refresh()` виджета → пилот сменил экран, компаньон потерял пульт и по таймауту ушёл в FLIGHT: настройки недоступны, хотя аппарат на земле.

## practice
### Шаг 1. Эхо между пультом и ESP32
1. На пульте: Hardware → AUX1 → режим Lua, 115200.
2. Скрипт `/SCRIPTS/TOOLS/echo.lua` на пульте шлёт строку и печатает ответ.
3. На ПК вместо ESP32 — USB-UART и терминал (`picocom -b 115200 /dev/ttyUSB0`). Критерий: строка 200+ символов ходит туда-обратно без потерь.
4. Только после этого — ESP32.

### Шаг 2. Каркас прошивки ESP32 (PlatformIO, Arduino)
```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>

enum class Mode { FLIGHT, GROUND };
Mode mode = Mode::FLIGHT;            // undefined state == FLIGHT
unsigned long lastLine = 0;          // last valid S-line from the radio
unsigned long disarmedSince = 0;     // 0 = not continuously disarmed
const unsigned long LINE_TIMEOUT_MS = 2000;
const unsigned long GROUND_AFTER_MS = 3000;

void radioOff() {
  WiFi.mode(WIFI_OFF);
  esp_wifi_stop();                   // verifiable off, not assumed off
}

void enterGround() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP("tx16s-companion", "change-me");
  mode = Mode::GROUND;
}

void enterFlight() {
  radioOff();
  mode = Mode::FLIGHT;
}

void setup() {
  Serial.begin(115200);              // USB debug
  Serial1.begin(115200, SERIAL_8N1, 18, 17);  // RX, TX pins to the radio AUX port
  radioOff();
}

void loop() {
  unsigned long now = millis();
  if (Serial1.available()) {
    String line = Serial1.readStringUntil('\n');   // one line == one message
    // S,<mode>,<armed>,<vbat>,<rssi>  — the protocol above; armed is the third field
    if (line.startsWith("S,")) {
      int a = line.indexOf(',', 2);                 // end of <mode>
      if (a > 0 && a + 1 < (int)line.length()) {
        lastLine = now;
        bool armed = line.charAt(a + 1) == '1';
        if (armed) {
          disarmedSince = 0;
          if (mode == Mode::GROUND) enterFlight();  // any armed=1 -> FLIGHT at once
        } else {
          if (disarmedSince == 0) disarmedSince = now;
          if (mode == Mode::FLIGHT && now - disarmedSince >= GROUND_AFTER_MS) enterGround();
        }
      }
    }
  }
  if (now - lastLine > LINE_TIMEOUT_MS) {
    disarmedSince = 0;                // a gap breaks "continuously disarmed"
    if (mode == Mode::GROUND) enterFlight();   // lost the radio: fail safe
  }
}
```

### Шаг 3. Виджет EdgeTX с общим tick()
```lua
-- companion.lua (widget): send the S-line every 500 ms whether visible or not
-- protocol: S,<mode>,<armed>,<vbat>,<rssi>\n  (see docs/protocol.md)
local lastSend = 0

local function tick()
  local now = getTime()                       -- 10 ms units
  if now - lastSend >= 50 then
    local _, fmName = getFlightMode()
    local armed = getValue("sa") > 0          -- example: arm switch on SA
    local vbat = getValue("RxBt") or 0        -- CRSF telemetry; 0 when the sensor is missing
    local rssi = getValue("1RSS") or 0
    serialWrite(string.format("S,%s,%d,%.2f,%d\n", fmName or "?", armed and 1 or 0, vbat, rssi))
    lastSend = now
  end
end

local function create(zone, options) return { zone = zone } end
local function update(widget, options) end
local function background(widget) tick() end
local function refresh(widget, event, touch)
  tick()
  lcd.drawText(widget.zone.x, widget.zone.y, "companion link", SMLSIZE)
end

return { name = "Companion", create = create, update = update, refresh = refresh, background = background }
```

Источник истины для «arm» — тумблер плюс heartbeat, а не состояние из телеметрии CRSF: оно может отсутствовать или запаздывать.

### Шаг 4. Структура репозитория
`firmware/` (PlatformIO), `lua/` (скрипты пульта), `web/` (страница настроек, отдаётся с ESP32), `docs/` (протокол сообщений). Протокол — отдельный документ: каждая строка, её поля и кто имеет право её слать.

### Что должно получиться и что записать
- **Эхо-тест.** 200+ символов уходят и возвращаются без потерь и искажений. Если теряются, почти всегда виновата скорость порта или земля. Сначала добейся чистого эха с USB-UART, только потом подключай ESP32 — иначе непонятно, чья ошибка.
- **Поток S-строк.** В отладочном выводе ESP32 (USB-порт, `Serial`) строки `S,…` приходят каждые 500 мс ± 50 мс, и видимость виджета на экране пульта на это не влияет: `tick()` вызывается и из `refresh()`, и из `background()`.
- **Переходы.** Запиши время каждого перехода по отладочным меткам `millis()`. Дизарм — через 3 с GROUND и точка доступа Wi-Fi. Арм — сразу FLIGHT, Wi-Fi выключен. Кабель от пульта выдернут в GROUND — через 2 с FLIGHT. Мусорная строка не меняет состояние.
- **Проверка на ПК без пульта.** Те же сценарии проверяются эмулятором: скрипт на ПК шлёт S-строки в USB-UART с нужным темпом и обрывом. Это быстрее и повторяемее, чем щёлкать тумблером.

### docs/protocol.md
Каждая строка протокола — отдельный раздел: формат (`S,<mode>,<armed>,<vbat>,<rssi>`), поля и единицы, кто шлёт и как часто, что делает получатель при ошибке формата и при отсутствии строк. Протокол, которого нет в документе, превращается в «как в коде» и ломается при первой правке.

Самопроверка: лабораторная выполнена, когда эхо-тест с USB-UART проходит на 200+ символах, виджет шлёт S-строки из `refresh()` и `background()`, ESP32 уходит в FLIGHT по таймауту строк, и времена по меткам `millis()` сходятся с заданными (S-строки каждые 500 мс ± 50 мс; дизарм → GROUND через 3 с; кабель выдернут → FLIGHT через 2 с; мусорная строка состояние не меняет), а в `docs/protocol.md` у каждой строки протокола записаны формат, поля с единицами, кто шлёт и как часто, реакция получателя на ошибку формата и на отсутствие строк.

## diagnostics
- **Симптом:** компаньон теряет связь при смене экрана пульта
  - Возможная причина: отправка только в `refresh()`.
  - Что сделать: общий `tick()` в `refresh()` и `background()`.
- **Симптом:** строки приходят обрезанными
  - Возможная причина: `serialRead` вызывается реже, чем приходят данные, буфер переполняется.
  - Что сделать: читать в каждом `tick()`, укоротить сообщения, снизить частоту.
- **Симптом:** точка доступа поднялась в полёте
  - Возможная причина: защита только на одной стороне.
  - Что сделать: проверка арма и в Lua, и в прошивке; таймаут heartbeat → FLIGHT.
- **Симптом:** ESP32 перезагружается при включении Wi-Fi
  - Возможная причина: просадка питания (пики 300–500 мА).
  - Что сделать: конденсатор 470 мкФ на 3.3 В, BEC/LDO с запасом, не питать от пина пульта без проверки тока.
- **Симптом:** Lua на пульте не видит ответов ESP32
  - Возможная причина: порт AUX не в режиме Lua, скорость, TX/RX.
  - Что сделать: Hardware → AUX = Lua, `setSerialBaudrate`, анализатор на линии.

## references
- EdgeTX Lua API Reference | https://luadoc.edgetx.org/ | primary | A
- EdgeTX Lua serial API source (api_general.cpp, GitHub) | https://github.com/EdgeTX/edgetx/blob/main/radio/src/lua/api_general.cpp | primary | A
- ESP32 Arduino core — Wi-Fi API (GitHub) | https://github.com/espressif/arduino-esp32 | primary | A
- PlatformIO — Documentation | https://docs.platformio.org/ | primary | A
- ArduPilot Copter-4.7.2 — AP_HAL_ESP32 README и hwdef esp32s3m5stampfly | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.2/libraries/AP_HAL_ESP32 | primary | A
- Betaflight 2026.6 Release Notes (ESP32 experimental; открыто 2026-11-22) | https://betaflight.com/docs/wiki/release/Betaflight-2026-6-Release-Notes | primary | A
- PX4 v1.17.0 — boards/espressif/esp32 | https://github.com/PX4/PX4-Autopilot/tree/v1.17.0/boards/espressif/esp32 | primary | A
- ExpressLRS 4.1.0 — src/targets и include/common.h (режимы выходов PWM/DShot) | https://github.com/ExpressLRS/ExpressLRS/blob/4.1.0/src/include/common.h | primary | A
- ESP-FC — README (MCU, функции, ограничения; открыто 2026-11-22) | https://github.com/rtlopez/esp-fc | primary | B

## checklist
- Уровни UART проверены мультиметром, GND общий
- Эхо-тест с USB-UART пройден на 200+ символах
- Heartbeat шлётся из `refresh()` и `background()`
- Неопределённое состояние = FLIGHT, Wi-Fi выключен проверяемо
- Защита от записи в полёте на обеих сторонах
- Бюджет питания посчитан по режимам
