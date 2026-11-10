---
id: emb-basics
title: "Embedded: переривання, таймери, DMA, RTOS"
level: L3
readingTime: 40 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-08
tags:
  - embedded
  - FreeRTOS
  - переривання
  - DMA
  - ESP32
related:
  - comp-esp32
  - emb-protocols
  - fw-reading
next:
  - emb-protocols
source: content/companion/emb-basics.md
source_hash: e6aef4dd323b
---

## summary
Польотний контролер на STM32 опитує гіроскоп 8000 разів на секунду, рахує PID, шле DShot чотирьом ESC, приймає CRSF, пише лог і малює OSD — на одному ядрі. То можливо лиш тому, що залізо робить роботу без процесора (DMA, таймери), а події приходять перериваннями. Модуль пояснює ці механізми настільки, щоб ти міг читати прошивки і робити власні пристрої: переривання і пріоритети, таймери та захоплення/генерування, DMA, планувальник Betaflight, FreeRTOS в ESP32 і NuttX у PX4, джитер і чому `delay()` у петлі — то аварія. Лабораторна на ESP32: дві задачі FreeRTOS, черга, апаратний таймер, вимірювання джитера, блокування — показане й усунене.

## theory
### Чим зайнятий процесор польотного контролера
Бюджет на 8 кГц — 125 мкс на цикл. Гіроскоп по SPI на 8+ МГц читає 14 байт за ~15 мкс — як чекати в циклі; з DMA — 0 мкс процесорного часу. PID за трьома осями на F4 (168 МГц) — ~10–20 мкс, фільтри — стільки ж, DShot — через таймер+DMA (0 мкс), CRSF — UART із перериванням/DMA. Решта — для нижчих задач (`src/main/fc/tasks.c`): `TASK_RX` — подійно, коли прийде кадр, із запасним періодом 33 Гц, `TASK_SERIAL` 100 Гц, `TASK_BATTERY_CURRENT` 50 Гц, `TASK_OSD` за `osd framerate_hz`, `TASK_GPS` за швидкістю порту, blackbox — на дільнику від PID-петлі. Betaflight — кооперативний планувальник без RTOS (`scheduler.c`): кожна задача має бажаний період, пріоритет і оцінку часу; критичні задачі (gyro/PID) ніц не витісняють — планувальник просто не запускає нижчу задачу, як її оцінка часу виконання (`anticipatedExecutionTime`) не вміщає ся до наступного циклу гіроскопа; решта чекають «дірки».

### Переривання
Переривання — апаратний сигнал, що призупиняє поточний код і викликає обробник (ISR). Джерела: готовий байт UART, завершив ся DMA, спрацював таймер, фронт на ніжці (EXTI — так гіроскоп каже «дані готові», Betaflight `gyro_sync` за EXTI). Правила ISR: коротко (мікросекунди), без блокувальних викликів і `printf`, без виділення пам'яті; важку роботу — у задачу через прапорець/чергу. **Пріоритети** (NVIC у Cortex-M): переривання з вищим пріоритетом витісняє ISR з нижчим; гіроскоп/DShot — вище, UART-лог — нижче. На ESP32 — `ESP_INTR_FLAG_LEVEL1..3`, ISR в IRAM (`IRAM_ATTR`), на інше ядро — через чергу.

### Таймери
Лічильник, що тікає від шини і вміє: генерувати переривання за періодом (планувальник, періодичні задачі), **PWM** (compare), **захоплення** вхідного фронту (input capture — вимірювання ширини імпульсу PWM-приймача), запускати DMA за подією (DShot: таймер + DMA пише послідовність тривалостей у регістр compare — так один кадр DShot із 16 біт іде без участі процесора). Роздільність — такт таймера: при 84 МГц — 12 нс.

### DMA
Контролер прямого доступу до пам'яті копіює дані периферія ↔ пам'ять за подіями без процесора: приймання UART у кільцевий буфер, читання SPI-гіроскопа, вивід DShot, запис на SD. Обмеження: кількість каналів/потоків та їхня прив'язка до периферії (у STM32F4 конфлікти DMA-потоків — то реальна причина, чому на деяких платах не можна разом DShot на всі мотори і, наприклад, LED-стрічку — target-файли Betaflight описують якраз то), когерентність кешу на F7/H7 (буфери в некешованій пам'яті або `SCB_Clean/InvalidateDCache`).

### RTOS: задачі, пріоритети, черги
FreeRTOS (ESP32; PX4 працює на NuttX — іншій RTOS з тими самими поняттями задач, пріоритетів і черг): задачі з пріоритетами і власним стеком; витіснювальний планувальник — задача з вищим пріоритетом завжди дістає ядро, коли готова; однакові — за часом (tick за замовчуванням 100 Гц в ESP-IDF, `CONFIG_FREERTOS_HZ`; в Arduino-ESP32 — 1000 Гц). Примітиви: **черга** (ISR → задача, задача → задача, копіює дані, потокобезпечна), **семафор/нотифікація** (сигнал «подія»), **м'ютекс** (захист спільного ресурсу — шини I2C), **таймер** (програмний, у контексті демона — не для точних періодів). Точний період: `vTaskDelayUntil` (фіксований період від останнього пробудження, а не від кінця роботи) або апаратний таймер + нотифікація.

### Джитер і блокування
Джитер — розкид фактичного періоду. Причини: ISR із довгою роботою, задача з вищим пріоритетом, кеш-промахи, `delay()`/очікування в циклі (busy-wait), логування в `printf` з критичної задачі, флеш-операції (на ESP32 запис у flash зупиняє виконання коду з flash на іншому ядрі, як то не IRAM). Норма для контуру керування: джитер < 5–10% періоду; PX4 і Betaflight то вимірюють і логують (`DEBUG_CYCLETIME`, PX4 `perf`).

**Чому блокування в петлі — аварія**: задача керування чекає UART 50 мс → 400 пропущених циклів на 8 кГц → дані гіроскопа застаріли, стрибок D-term, мотори «смикають ся»; у гіршому разі watchdog перезавантажує контролер просто в польоті. Звідси правило: контур керування ніц не чекає — лиш читає готові дані.

### Watchdog
Апаратний таймер, що перезавантажує МК, як його не «годувати». Betaflight/ArduPilot/PX4 його вживають: зависання = перезавантаження (ліпше, ніж вічне «мотори на останньому значенні»); ArduPilot пише причину у `WDOG`/`BRD_OPTIONS`. На ESP32 — task watchdog на idle-задачі: задача без `vTaskDelay` блокує idle → TWDT спрацьовує.

{{diagram:fc-loop-125us|Один цикл 8 кГц: читання гіроскопа по DMA, фільтри, PID і мікшер, кадр DShot по DMA; переривання UART вклинює ся, решта циклу — повільні задачі (порядок величин, не точний профіль).}}

## practice
### Крок 1. Дві задачі й черга (ESP32, ESP-IDF або Arduino-FreeRTOS)
```c
// sensor task: hardware timer notifies every 1 ms; reads IMU (or fakes it) and pushes a sample
static QueueHandle_t q;
static TaskHandle_t sensorTask;
static void IRAM_ATTR on_timer(void *arg) {           // ISR: just notify
  BaseType_t hp = pdFALSE;
  vTaskNotifyGiveFromISR(sensorTask, &hp);
  if (hp) portYIELD_FROM_ISR();
}
static void sensor_task(void *arg) {
  int64_t last = esp_timer_get_time();
  for (;;) {
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);          // wait for timer ISR
    int64_t now = esp_timer_get_time();
    sample_t s = { .t_us = now, .dt_us = (int32_t)(now - last) }; last = now;
    s.gyro = read_gyro();                             // SPI/I2C read, non-blocking driver
    xQueueSend(q, &s, 0);                             // never block the control task
  }
}
static void uart_task(void *arg) {                    // lower priority: formats and prints
  sample_t s;
  for (;;) if (xQueueReceive(q, &s, portMAX_DELAY)) printf("%lld,%ld,%.2f\n", s.t_us, (long)s.dt_us, s.gyro);
}
// app_main: q = xQueueCreate(64, sizeof(sample_t)); create sensor_task prio 10, uart_task prio 3;
// esp_timer periodic 1000 us -> on_timer with dispatch_method = ESP_TIMER_ISR (needs CONFIG_ESP_TIMER_SUPPORTS_ISR_DISPATCH_METHOD); default ESP_TIMER_TASK runs the callback in the esp_timer task, not an ISR
```
Збирання, запуск, 10 с виводу у файл.

### Крок 2. Джитер
З `dt_us`: середнє (≈1000), std, максимум, гістограма. Очікувано std < 10 мкс, max < 50.

### Крок 3. Зламати і полагодити
В `uart_task` додай вільний від `vTaskDelay(0)` цикл busy-wait 5 мс (наприклад, `while (esp_timer_get_time() < t0 + 5000) {}`) і підніми його пріоритет до 11 — ади, як джитер датчика виріс до мілісекунд (або спрацював TWDT). Верни пріоритет 3 — джитер ся відновив: витіснення працює. Потім поклади блокувальний запис у flash (NVS) у `sensor_task` — побачиш провал; винеси його в окрему задачу. Лабораторна: дві задачі через чергу, вимірювання джитера, блокування показане й усунене.

### Крок 4. Прочитати прошивку
У Betaflight `src/main/fc/core.c`: `taskMainPidLoop` → `subTaskPidController` → `subTaskMotorUpdate`; у `scheduler/scheduler.c` — як ся вибирають задачі. В ArduPilot `ArduCopter/Copter.cpp` — таблиця `scheduler_tasks[]`: `FAST_TASK` (на частоті петлі: INS update → `run_rate_controller_main` → `motors_output_main` → AHRS…) і `SCHED_TASK(rc_loop, 250, …)` з частотою, бюджетом часу і пріоритетом.

## diagnostics
- **Симптом:** джитер періоду скаче до мс
  - Можлива причина: пріоритетніша задача/ISR робить довгу роботу; busy-wait; printf у критичній задачі.
  - Що зробити: пріоритети, короткі ISR, вивід в окрему задачу через чергу.
- **Симптом:** ESP32 перезавантажує ся з «Task watchdog got triggered»
  - Можлива причина: задача не віддає ядро (нема vTaskDelay/блокувального очікування).
  - Що зробити: очікування подій замість опитування; `vTaskDelay(1)` у фонових циклах.
- **Симптом:** дані в буфері DMA «старі» на F7/H7
  - Можлива причина: кеш даних.
  - Що зробити: некешована пам'ять або invalidate після приймання.
- **Симптом:** ISR доводить до краху
  - Можлива причина: не-ISR-safe виклик (printf, malloc, звичайний xQueueSend) або код не в IRAM на ESP32.
  - Що зробити: FromISR-версії, IRAM_ATTR, мінімум роботи.
- **Симптом:** Betaflight: CPU load > 90%, пропуски задач
  - Можлива причина: F4 з 8 кГц і вшиткими функціями.
  - Що зробити: 4 кГц, вимкнути зайве, дивити ся `tasks` у CLI.

## references
- FreeRTOS — Mastering the FreeRTOS Real Time Kernel (book, GitHub) | https://www.github.com/FreeRTOS/FreeRTOS-Kernel-Book/blob/main/toc.md | primary | A
- ESP-IDF — FreeRTOS (ESP-IDF additions, task watchdog) | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos.html | primary | A
- Betaflight — source: fc/core.c and scheduler | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A

## checklist
- Розумію, як DMA і таймери звільняють процесор
- Знаю правила ISR і пріоритети
- Дві задачі FreeRTOS через чергу працюють, джитер виміряно
- Показав-єм, як блокування ламає період, і усунув
- Знайшов головний цикл у Betaflight і таблицю задач в ArduPilot
