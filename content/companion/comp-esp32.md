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

enum class Mode { FLIGHT, CONFIG };
Mode mode = Mode::FLIGHT;            // undefined state == FLIGHT
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_TIMEOUT_MS = 3000;

void radioOff() {
  WiFi.mode(WIFI_OFF);
  esp_wifi_stop();                   // verifiable off, not assumed off
}

void enterConfig() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP("tx16s-companion", "change-me");
  mode = Mode::CONFIG;
}

void setup() {
  Serial.begin(115200);              // USB debug
  Serial1.begin(115200, SERIAL_8N1, 18, 17);  // RX, TX pins to the radio AUX port
  radioOff();
}

void loop() {
  if (Serial1.available()) {
    String line = Serial1.readStringUntil('\n');   // one line == one message
    lastHeartbeat = millis();
    // S,<mode>,<armed>,<vbat>,<rssi>  — the protocol above; armed is the third field
    if (line.startsWith("S,")) {
      int a = line.indexOf(',', 2);                 // end of <mode>
      bool armed = a > 0 && line.charAt(a + 1) == '1';
      if (armed && mode == Mode::CONFIG) { radioOff(); mode = Mode::FLIGHT; }
      else if (!armed && mode == Mode::FLIGHT) enterConfig();
    }
  }
  if (millis() - lastHeartbeat > HEARTBEAT_TIMEOUT_MS && mode == Mode::CONFIG) {
    radioOff(); mode = Mode::FLIGHT;  // lost the radio: fail safe
  }
}
```

### Шаг 3. Виджет EdgeTX с общим tick()
```lua
-- companion.lua (widget): send state every 500 ms whether visible or not
local lastSend = 0

local function tick()
  local now = getTime()                       -- 10 ms units
  if now - lastSend >= 50 then
    local armed = getValue("sa") > 0          -- example: arm switch on SA
    serialWrite(string.format("STATE %s\n", armed and "armed" or "disarmed"))
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

## checklist
- Уровни UART проверены мультиметром, GND общий
- Эхо-тест с USB-UART пройден на 200+ символах
- Heartbeat шлётся из `refresh()` и `background()`
- Неопределённое состояние = FLIGHT, Wi-Fi выключен проверяемо
- Защита от записи в полёте на обеих сторонах
- Бюджет питания посчитан по режимам
