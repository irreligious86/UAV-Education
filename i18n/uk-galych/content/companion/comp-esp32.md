---
id: comp-esp32
title: "ESP32 і периферія"
level: L2
readingTime: 30 хв
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
source: content/companion/comp-esp32.md
source_hash: 0985c735e3ff
---

## summary
ESP32 — то файний «маленький companion»: UART, Wi-Fi, BLE, дисплей, копійчана ціна й запуск за частку секунди. Модуль розбирає три типові ролі: периферія на борту (датчики, індикація), MAVLink-міст Wi-Fi ↔ FC і компаньйон пульта. Останню — на прикладі проєкту для RadioMaster TX16S: ESP32-S3 з екраном, який у польоті показує телеметрію, а на землі піднімає точку доступу для налаштувань із телефона. Розібрано пастки, на які легко ся трафити: lifecycle Lua-віджета EdgeTX, рівні UART, бюджет живлення та перевірюване вимкнення радіо.

## theory
### Три ролі ESP32
1. **Бортова периферія.** Опитування датчиків по I2C, адресні світлодіоди, серви, реле. Зв'язок із FC по UART через MAVLink або простий текстовий протокол.
2. **MAVLink-міст.** ESP32 приймає MAVLink по UART від FC і роздає через Wi-Fi (UDP) телефону або ноутбуку. Так працює багато готових Wi-Fi-телеметрій; власна версія — то кілька десятків рядків.
3. **Компаньйон пульта.** ESP32 під'єднано до AUX-порту пульта на EdgeTX, Lua-скрипт на пульті шле йому стан (режим, арм, телеметрію), а ESP32 показує то на своєму дисплеї й дає інтерфейс налаштувань.

### UART: рівні та дроти
ESP32 працює на 3.3 В. Польотні контролери й пульти на EdgeTX теж мають 3.3 В на UART, але перевір мультиметром, заки будеш з'єднувати. Дроти навхрест, спільний GND обов'язковий. Швидкість із пультом — та, що задана в налаштуваннях порту, зазвичай 115200.

### EdgeTX: порт AUX і Lua
У налаштуваннях апаратури (Hardware) у портів AUX1/AUX2 є режим «Lua»: тоді скрипти дістають доступ до функцій `serialWrite(str)`, `serialRead([num])` і `setSerialBaudrate(baudrate)`. `serialRead` без аргументу читає до першого переведення рядка, тож рядковий протокол «один рядок — одне повідомлення» лягає на нього якраз природно.

### Пастка: lifecycle віджета
У віджета EdgeTX дві функції: `refresh()` ся викликає, коли віджет видно на екрані, `background()` — коли його сховано. Як покладеш надсилання heartbeat лиш у `refresh()`, компаньйон втратить зв'язок, щойно пілот перемкне екран. Рішення: спільна функція `tick()`, яку викликають обидві.

### Безпека за замовчуванням
Дизайн-рішення проєкту: невизначений стан = режим FLIGHT, Wi-Fi вимкнено. Точка доступу ся піднімає лиш тоді, коли ESP32 дістав від пульта явне «disarmed». Кожен запис налаштувань іде у два кроки: STAGE (підготувати) → APPLY (застосувати з автоматичним бекапом), а захист від запису в польоті продубльовано з обох боків — і в Lua, і в прошивці ESP32.

Вимкнення радіо мусить бути перевірюваним: `WiFi.mode(WIFI_OFF)` плюс `esp_wifi_stop()`, а не здогад «та ми його не вмикали».

### Живлення
ESP32-S3 з активним Wi-Fi бере піки в сотні міліампер. Від батареї пульта ци BEC то відчутно; у режимі FLIGHT з вимкненим радіо — в рази менше. Бюджет рахують за режимами, а не за середнім.

### Мінімальний MAVLink-міст на ESP32 (ідея коду)
UART2 (`Serial2.begin(921600, SERIAL_8N1, RX_PIN, TX_PIN)`) ↔ WiFi UDP: вшитко, що прийшло з FC, — в UDP на адресу останнього клієнта (або broadcast 14550); вшитко, що прийшло по UDP, — в UART. Буфери 1 КБ, без парсингу MAVLink (міст прозорий); задача на другому ядрі FreeRTOS (модуль «Embedded»): ядро 0 — стек Wi-Fi, ядро 1 — UART-копіювання з пріоритетом вищим за `loop()`. Затримка такого моста — одиниці мс; втрати — коли Wi-Fi перевантажений (2.4 ГГц ділить ефір з ELRS 2.4 — на борту міст через Wi-Fi доречний хіба для наземного налаштування, у польоті вимикати).

### Датчик на борту через MAVLink
ESP32 як компонент системи: шле `HEARTBEAT` (свій component_id: `MAV_COMP_ID_PERIPHERAL` (158) або з діапазону USER1–USER75 (25–99)), дані — `NAMED_VALUE_FLOAT`/`NAMED_VALUE_INT` (видно в GCS і в логу `NVAL`), або `DISTANCE_SENSOR` (132) для власного далекоміра — ArduPilot прийме його як `RNGFND1_TYPE = 10` (MAVLink) і вжиє в EKF/посадці. Бібліотека: `mavlink` C-headers з генератора (`common.xml`, 100 КБ flash), або мінімальний ручний збирач кадру з CRC (модуль «Протоколи MAVLink»).

### Розібраний приклад: компаньйон пульта (проєкт TX16S)
Протокол рядків: пульт → ESP32 `S,<mode>,<armed>,<vbat>,<rssi>\n` кожні 500 мс; ESP32 → пульт `A,<cmd>,<arg>\n`. Стани ESP32: FLIGHT (радіо вимк.; за замовчуванням і при таймауті рядків > 2 с) → GROUND (пульт надіслав `armed=0` ≥ 3 с поспіль: Wi-Fi AP, веб-налаштування) → FLIGHT при будь-якому `armed=1`. Налаштування: STAGE (JSON у RAM) → APPLY (запис NVS з копією попередньої версії) лиш у GROUND; Lua на пульті блокує `APPLY`, як телеметрія показує арм. Тест: емулятор рядків із ПК через USB-UART, сценарії переходів і таймаутів, потім справжній пульт без апарата.

{{diagram:esp32-roles|Три ролі ESP32 у курсі: міст UART ↔ Wi-Fi/BLE, власний компонент MAVLink і компаньйон пульта на порту AUX.}}

## practice
### Крок 1. Ехо між пультом і ESP32
1. На пульті: Hardware → AUX1 → режим Lua, 115200.
2. Скрипт `/SCRIPTS/TOOLS/echo.lua` на пульті шле рядок і друкує відповідь.
3. На ПК замість ESP32 — USB-UART і термінал (`picocom -b 115200 /dev/ttyUSB0`). Критерій: рядок 200+ символів ходить туди й назад без втрат.
4. Лиш потім — ESP32.

### Крок 2. Каркас прошивки ESP32 (PlatformIO, Arduino)
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

### Крок 3. Віджет EdgeTX зі спільним tick()
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

Джерело правди для «arm» — тумблер плюс heartbeat, а не стан із телеметрії CRSF: його може не бути, або він може спізнювати ся.

### Крок 4. Структура репозиторію
`firmware/` (PlatformIO), `lua/` (скрипти пульта), `web/` (сторінка налаштувань, віддає ся з ESP32), `docs/` (протокол повідомлень). Протокол — окремий документ: кожен рядок, його поля і хто має право його слати.

### Що має вийти і що записати
- **Ехо-тест.** 200+ символів ідуть і вертають ся без втрат і спотворень. Як ся гублять, то майже завжди винна швидкість порту або земля. Спершу добий ся чистого еха з USB-UART, лиш потім під'єднуй ESP32 — інакше не зрозумієш, чия то помилка.
- **Потік S-рядків.** У налагоджувальному виводі ESP32 (USB-порт, `Serial`) рядки `S,…` приходять кожні 500 мс ± 50 мс, і видимість віджета на екрані пульта на то не впливає: `tick()` ся викликає і з `refresh()`, і з `background()`.
- **Переходи.** Запиши час кожного переходу за налагоджувальними мітками `millis()`. Дизарм — через 3 с GROUND і точка доступу Wi-Fi. Арм — зразу FLIGHT, Wi-Fi вимкнено. Кабель від пульта висмикнуто в GROUND — через 2 с FLIGHT. Сміттєвий рядок стану не міняє.
- **Перевірка на ПК без пульта.** Ті самі сценарії перевіряють емулятором: скрипт на ПК шле S-рядки в USB-UART з потрібним темпом і обривом. То шпаркіше й повторюваніше, ніж клацати тумблером.

### docs/protocol.md
Кожен рядок протоколу — окремий розділ: формат (`S,<mode>,<armed>,<vbat>,<rssi>`), поля й одиниці, хто шле і як часто, що робить отримувач, як формат хибний або рядків нема. Протокол, якого нема в документі, стає «як у коді» й ламає ся за першої правки.

Лабораторну зараховано, коли ехо-тест з USB-UART проходить на 200+ символах, віджет шле S-рядки з `refresh()` і `background()`, ESP32 переходить у FLIGHT за таймаутом рядків із виміряним часом, а протокол описано в `docs/`.

## diagnostics
- **Симптом:** компаньйон втрачає зв'язок, коли міняєш екран пульта
  - Можлива причина: надсилання лиш у `refresh()`.
  - Що зробити: спільний `tick()` у `refresh()` і `background()`.
- **Симптом:** рядки приходять обрізані
  - Можлива причина: `serialRead` ся викликає рідше, ніж надходять дані, буфер переповнює ся.
  - Що зробити: читати в кожному `tick()`, скоротити повідомлення, знизити частоту.
- **Симптом:** точка доступу піднялася в польоті
  - Можлива причина: захист лиш з одного боку.
  - Що зробити: перевірка арму і в Lua, і в прошивці; таймаут heartbeat → FLIGHT.
- **Симптом:** ESP32 перезавантажує ся, як вмикаєш Wi-Fi
  - Можлива причина: просідання живлення (піки 300–500 мА).
  - Що зробити: конденсатор 470 мкФ на 3.3 В, BEC/LDO із запасом, не живити від піна пульта без перевірки струму.
- **Симптом:** Lua на пульті не бачить відповідей ESP32
  - Можлива причина: порт AUX не в режимі Lua, швидкість, TX/RX.
  - Що зробити: Hardware → AUX = Lua, `setSerialBaudrate`, аналізатор на лінії.

## references
- EdgeTX Lua API Reference | https://luadoc.edgetx.org/ | primary | A
- EdgeTX Lua serial API source (api_general.cpp, GitHub) | https://github.com/EdgeTX/edgetx/blob/main/radio/src/lua/api_general.cpp | primary | A
- ESP32 Arduino core — Wi-Fi API (GitHub) | https://github.com/espressif/arduino-esp32 | primary | A
- PlatformIO — Documentation | https://docs.platformio.org/ | primary | A

## checklist
- Рівні UART перевірено мультиметром, GND спільний
- Ехо-тест з USB-UART пройдено на 200+ символах
- Heartbeat ся шле з `refresh()` і `background()`
- Невизначений стан = FLIGHT, Wi-Fi вимкнено перевірювано
- Захист від запису в польоті з обох боків
- Бюджет живлення пораховано за режимами
