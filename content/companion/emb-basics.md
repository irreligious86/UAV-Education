---
id: emb-basics
title: "Embedded: прерывания, таймеры, DMA, RTOS"
level: L3
readingTime: 40 мин
firmware: любая прошивка
status: published
added: 2026-11-08
tags:
  - embedded
  - FreeRTOS
  - прерывания
  - DMA
  - ESP32
related:
  - comp-esp32
  - emb-protocols
  - fw-reading
next:
  - emb-protocols
---

## summary
Полётник на STM32 опрашивает гироскоп 8000 раз в секунду, считает PID, шлёт DShot четырём ESC, принимает CRSF, пишет лог и рисует OSD — на одном ядре. Это возможно только потому, что железо делает работу без процессора (DMA, таймеры), а события приходят прерываниями. Модуль объясняет эти механизмы на уровне, нужном для чтения прошивок и написания своих устройств: прерывания и приоритеты, таймеры и захват/генерация, DMA, планировщик Betaflight, FreeRTOS в ESP32 и NuttX в PX4, джиттер и почему `delay()` в петле — авария. Лабораторная на ESP32: две задачи FreeRTOS, очередь, аппаратный таймер, замер джиттера, блокировка — показана и устранена.

## theory
### Чем занят процессор полётника
Бюджет на 8 кГц — 125 мкс на цикл. Гироскоп по SPI на 8+ МГц читает 14 байт за ~15 мкс — если ждать в цикле; с DMA — 0 мкс процессорного времени. PID по трём осям на F4 (168 МГц) — ~10–20 мкс, фильтры — столько же, DShot — через таймер+DMA (0 мкс), CRSF — UART с прерыванием/DMA. Остаток — для задач пониже (`src/main/fc/tasks.c`): `TASK_RX` — событийно по приходу кадра с запасным периодом 33 Гц, `TASK_SERIAL` 100 Гц, `TASK_BATTERY_CURRENT` 50 Гц, `TASK_OSD` по `osd framerate_hz`, `TASK_GPS` по скорости порта, blackbox — на делителе от PID-петли. Betaflight — кооперативный планировщик без RTOS (`scheduler.c`): каждая задача имеет желаемый период, приоритет и оценку времени; критические задачи (gyro/PID) ничего не вытесняют — планировщик просто не запускает задачу пониже, если её оценка времени выполнения (`anticipatedExecutionTime`) не помещается до следующего цикла гироскопа; остальные ждут «дырки».

### Прерывания
Прерывание — аппаратный сигнал, который приостанавливает текущий код и вызывает обработчик (ISR). Источники: готов байт UART, завершился DMA, сработал таймер, фронт на ноге (EXTI — так гироскоп сообщает «данные готовы», Betaflight `gyro_sync` по EXTI). Правила ISR: коротко (микросекунды), без блокирующих вызовов и `printf`, без выделения памяти; тяжёлую работу — в задачу через флаг/очередь. **Приоритеты** (NVIC у Cortex-M): прерывание с большим приоритетом вытесняет ISR с меньшим; гироскоп/DShot — выше, UART-лог — ниже. На ESP32 — `ESP_INTR_FLAG_LEVEL1..3`, ISR в IRAM (`IRAM_ATTR`), на другом ядре — через очередь.

### Таймеры
Счётчик, который тикает от шины и умеет: генерировать прерывание по периоду (планировщик, period-задачи), **PWM** (compare), **захват** входного фронта (input capture — измерение ширины импульса PWM-приёмника), запускать DMA по событию (DShot: таймер + DMA пишет последовательность длительностей в регистр compare — так один кадр DShot из 16 бит уходит без участия процессора). Разрешение — такт таймера: при 84 МГц — 12 нс.

### DMA
Контроллер прямого доступа к памяти копирует данные периферия ↔ память по событиям без процессора: приём UART в кольцевой буфер, чтение SPI-гироскопа, вывод DShot, запись на SD. Ограничения: число каналов/потоков и их привязка к периферии (в STM32F4 конфликты DMA-потоков — реальная причина, почему на некоторых платах нельзя одновременно DShot на все моторы и, например, LED-ленту — target-файлы Betaflight описывают именно это), когерентность кэша на F7/H7 (буферы в некэшируемой памяти или `SCB_Clean/InvalidateDCache`).

### RTOS: задачи, приоритеты, очереди
FreeRTOS (ESP32; PX4 работает на NuttX — другой RTOS с теми же понятиями задач, приоритетов и очередей): задачи с приоритетами и своим стеком; вытесняющий планировщик — задача выше приоритетом всегда получает ядро, когда готова; одинаковые — по времени (tick по умолчанию 100 Гц в ESP-IDF, `CONFIG_FREERTOS_HZ`; в Arduino-ESP32 — 1000 Гц). Примитивы: **очередь** (ISR → задача, задача → задача, копирует данные, потокобезопасна), **семафор/нотификация** (сигнал «событие»), **мьютекс** (защита общего ресурса — шины I2C), **таймер** (программный, в контексте демона — не для точных периодов). Точный период: `vTaskDelayUntil` (фиксированный период от последнего пробуждения, не от конца работы) или аппаратный таймер + нотификация.

### Джиттер и блокировка
Джиттер — разброс фактического периода. Причины: ISR с длинной работой, задача с большим приоритетом, кэш-промахи, `delay()`/ожидание в цикле (busy-wait), логирование в `printf` из критичной задачи, флеш-операции (на ESP32 запись во flash останавливает выполнение кода из flash на другом ядре, если не IRAM). Норма для контура управления: джиттер < 5–10% периода; PX4 и Betaflight меряют и логируют (`DEBUG_CYCLETIME`, PX4 `perf`).

**Почему блокировка в петле — авария**: задача управления ждёт UART 50 мс → 400 пропущенных циклов на 8 кГц → гироскоп устарел, D-term скачок, моторы «дёргают»; в худшем случае watchdog перезагружает контроллер в полёте. Отсюда правило: контур управления не ждёт ничего — только читает готовые данные.

### Watchdog
Аппаратный таймер, который перезагружает МК, если его не «кормят». Betaflight/ArduPilot/PX4 используют: зависание = перезагрузка (лучше, чем вечный «моторы на последнем значении»); ArduPilot пишет причину в `WDOG`/`BRD_OPTIONS`. На ESP32 — task watchdog на idle-задачи: задача без `vTaskDelay` блокирует idle → TWDT срабатывает.

{{diagram:fc-loop-125us|Один цикл 8 кГц: чтение гироскопа по DMA, фильтры, PID и миксер, кадр DShot по DMA; прерывание UART вклинивается, остаток цикла — медленные задачи (порядок величин, не точный профиль).}}

## practice
### Шаг 1. Две задачи и очередь (ESP32, ESP-IDF или Arduino-FreeRTOS)
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
Сборка, запуск, 10 с вывода в файл.

### Шаг 2. Джиттер
Из `dt_us`: среднее (≈1000), std, максимум, гистограмма. Ожидаемо std < 10 мкс, max < 50.

### Шаг 3. Сломать и починить
В `uart_task` добавить `vTaskDelay(0)`-свободный цикл busy-wait 5 мс (например, `while (esp_timer_get_time() < t0 + 5000) {}`) и поднять его приоритет до 11 — увидеть, как джиттер датчика вырос до миллисекунд (или сработал TWDT). Вернуть приоритет 3 — джиттер восстановился: вытеснение работает. Затем положить блокирующую запись во flash (NVS) в `sensor_task` — увидеть провал; вынести в отдельную задачу. Лабораторная: две задачи через очередь, замер джиттера, блокировка показана и устранена.

### Шаг 4. Прочитать прошивку
В Betaflight `src/main/fc/core.c`: `taskMainPidLoop` → `subTaskPidController` → `subTaskMotorUpdate`; в `scheduler/scheduler.c` — как задачи выбираются. В ArduPilot `ArduCopter/Copter.cpp` — таблица `scheduler_tasks[]`: `FAST_TASK` (на частоте петли: INS update → `run_rate_controller_main` → `motors_output_main` → AHRS…) и `SCHED_TASK(rc_loop, 250, …)` с частотой, бюджетом времени и приоритетом.

## diagnostics
- **Симптом:** джиттер периода скачет до мс
  - Возможная причина: более приоритетная задача/ISR делает долгую работу; busy-wait; printf в критичной задаче.
  - Что сделать: приоритеты, короткие ISR, вывод в отдельную задачу через очередь.
- **Симптом:** ESP32 перезагружается с «Task watchdog got triggered»
  - Возможная причина: задача не отдаёт ядро (нет vTaskDelay/блокирующего ожидания).
  - Что сделать: ожидание событий вместо опроса; `vTaskDelay(1)` в фоновых циклах.
- **Симптом:** данные в буфере DMA «старые» на F7/H7
  - Возможная причина: кэш данных.
  - Что сделать: некэшируемая память или invalidate после приёма.
- **Симптом:** ISR вызывает крах
  - Возможная причина: не-ISR-safe вызов (printf, malloc, обычный xQueueSend) или код не в IRAM на ESP32.
  - Что сделать: FromISR-версии, IRAM_ATTR, минимум работы.
- **Симптом:** Betaflight: CPU load > 90%, пропуски задач
  - Возможная причина: F4 с 8 кГц и всеми функциями.
  - Что сделать: 4 кГц, отключить лишнее, смотреть `tasks` в CLI.

## references
- FreeRTOS — Mastering the FreeRTOS Real Time Kernel (book, GitHub) | https://www.github.com/FreeRTOS/FreeRTOS-Kernel-Book/blob/main/toc.md | primary | A
- ESP-IDF — FreeRTOS (ESP-IDF additions, task watchdog) | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos.html | primary | A
- Betaflight — source: fc/core.c and scheduler | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A

## checklist
- Понимаю, как DMA и таймеры освобождают процессор
- Знаю правила ISR и приоритеты
- Две задачи FreeRTOS через очередь работают, джиттер измерен
- Показал, как блокировка ломает период, и устранил
- Нашёл главный цикл в Betaflight и таблицу задач в ArduPilot
