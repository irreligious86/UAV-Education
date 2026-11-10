---
id: emb-basics
title: "Embedded: interrupts, timers, DMA, RTOS"
level: L3
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - embedded
  - FreeRTOS
  - interrupts
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
An STM32 flight controller polls the gyro 8000 times per second, computes the PID, sends DShot to four ESCs, receives CRSF, writes a log and draws the OSD — on a single core. This is only possible because the hardware does work without the CPU (DMA, timers), and events arrive as interrupts. This module explains these mechanisms at the level you need to read firmware and write your own devices: interrupts and priorities, timers and capture/generation, DMA, the Betaflight scheduler, FreeRTOS on the ESP32 and NuttX in PX4, jitter, and why a `delay()` in the loop is a disaster. The ESP32 lab: two FreeRTOS tasks, a queue, a hardware timer, a jitter measurement, a blocking call — shown and eliminated.

## theory
### What keeps the flight controller CPU busy
The budget at 8 kHz is 125 µs per cycle. A gyro on SPI at 8+ MHz reads 14 bytes in ~15 µs — if you wait in a loop; with DMA it's 0 µs of CPU time. The PID on three axes on an F4 (168 MHz) takes ~10–20 µs, the filters as much again, DShot goes via timer+DMA (0 µs), CRSF via UART with an interrupt/DMA. The remainder is for lower tasks (`src/main/fc/tasks.c`): `TASK_RX` — event-driven on frame arrival with a 33 Hz fallback period, `TASK_SERIAL` 100 Hz, `TASK_BATTERY_CURRENT` 50 Hz, `TASK_OSD` per `osd framerate_hz`, `TASK_GPS` depending on the port speed, blackbox — on a divider from the PID loop. Betaflight is a cooperative scheduler without an RTOS (`scheduler.c`): every task has a desired period, a priority and a time estimate; the critical tasks (gyro/PID) don't preempt anything — the scheduler simply doesn't start a lower task if its execution time estimate (`anticipatedExecutionTime`) doesn't fit before the next gyro cycle; the rest wait for a “gap”.

### Interrupts
An interrupt is a hardware signal that suspends the current code and calls a handler (ISR). Sources: a UART byte is ready, a DMA transfer has completed, a timer fired, an edge on a pin (EXTI — that's how the gyro reports “data ready”, Betaflight `gyro_sync` via EXTI). ISR rules: short (microseconds), no blocking calls and no `printf`, no memory allocation; heavy work goes to a task via a flag/queue. **Priorities** (the NVIC on Cortex-M): an interrupt with a higher priority preempts an ISR with a lower one; the gyro/DShot are higher, the UART log is lower. On the ESP32 — `ESP_INTR_FLAG_LEVEL1..3`, the ISR in IRAM (`IRAM_ATTR`), to the other core via a queue.

### Timers
A counter that ticks from the bus and can: generate an interrupt every period (the scheduler, periodic tasks), **PWM** (compare), **capture** an input edge (input capture — measuring the pulse width of a PWM receiver), trigger DMA on an event (DShot: a timer + DMA writes a sequence of durations into the compare register — that's how a 16-bit DShot frame goes out without the CPU's involvement). The resolution is the timer clock: at 84 MHz it's 12 ns.

### DMA
The direct memory access controller copies data peripheral ↔ memory on events without the CPU: UART reception into a ring buffer, reading the SPI gyro, DShot output, writing to the SD card. Limitations: the number of channels/streams and their binding to peripherals (on the STM32F4, DMA stream conflicts are the real reason why some boards can't run DShot on all motors and, say, an LED strip at the same time — that's exactly what the Betaflight target files describe), cache coherency on F7/H7 (buffers in non-cacheable memory or `SCB_Clean/InvalidateDCache`).

### RTOS: tasks, priorities, queues
FreeRTOS (ESP32; PX4 runs on NuttX — a different RTOS with the same concepts of tasks, priorities and queues): tasks with priorities and their own stack; a preemptive scheduler — a higher-priority task always gets the core when it's ready; equal ones share by time (the tick is 100 Hz by default in ESP-IDF, `CONFIG_FREERTOS_HZ`; 1000 Hz in Arduino-ESP32). Primitives: the **queue** (ISR → task, task → task, copies data, thread-safe), the **semaphore/notification** (an “event” signal), the **mutex** (protecting a shared resource — the I2C bus), the **timer** (software, in the daemon context — not for precise periods). A precise period: `vTaskDelayUntil` (a fixed period from the last wake-up, not from the end of the work) or a hardware timer + a notification.

### Jitter and blocking
Jitter is the spread of the actual period. Causes: an ISR doing long work, a higher-priority task, cache misses, `delay()`/waiting in a loop (busy-wait), logging with `printf` from a critical task, flash operations (on the ESP32 a flash write halts execution of code from flash on the other core unless it's in IRAM). The norm for a control loop: jitter < 5–10% of the period; PX4 and Betaflight measure and log it (`DEBUG_CYCLETIME`, PX4 `perf`).

**Why blocking in the loop is a disaster**: the control task waits for the UART for 50 ms → 400 missed cycles at 8 kHz → the gyro data is stale, the D-term jumps, the motors “twitch”; in the worst case the watchdog reboots the controller in flight. Hence the rule: the control loop waits for nothing — it only reads data that is ready.

### Watchdog
A hardware timer that reboots the MCU if it isn't “fed”. Betaflight/ArduPilot/PX4 use it: a hang = a reboot (better than an eternal “motors stuck at the last value”); ArduPilot writes the reason to `WDOG`/`BRD_OPTIONS`. On the ESP32 there's the task watchdog on the idle tasks: a task without `vTaskDelay` blocks idle → the TWDT fires.

{{diagram:fc-loop-125us|One 8 kHz cycle: gyro read via DMA, filters, PID and mixer, a DShot frame via DMA; a UART interrupt squeezes in, the rest of the cycle goes to slow tasks (orders of magnitude, not an exact profile).}}

## practice
### Step 1. Two tasks and a queue (ESP32, ESP-IDF or Arduino-FreeRTOS)
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
Build, run, 10 s of output to a file.

### Step 2. Jitter
From `dt_us`: the mean (≈1000), std, the maximum, a histogram. Expect std < 10 µs, max < 50.

### Step 3. Break it and fix it
In `uart_task` add a `vTaskDelay(0)`-free 5 ms busy-wait loop (for example, `while (esp_timer_get_time() < t0 + 5000) {}`) and raise its priority to 11 — watch the sensor jitter grow to milliseconds (or the TWDT fire). Put the priority back to 3 — the jitter recovers: preemption works. Then put a blocking flash write (NVS) into `sensor_task` — watch the dropout; move it to a separate task. Lab: two tasks via a queue, a jitter measurement, a blocking call shown and eliminated.

### Step 4. Read the firmware
In Betaflight `src/main/fc/core.c`: `taskMainPidLoop` → `subTaskPidController` → `subTaskMotorUpdate`; in `scheduler/scheduler.c` — how tasks are selected. In ArduPilot `ArduCopter/Copter.cpp` — the `scheduler_tasks[]` table: `FAST_TASK` (at the loop rate: INS update → `run_rate_controller_main` → `motors_output_main` → AHRS…) and `SCHED_TASK(rc_loop, 250, …)` with a rate, a time budget and a priority.

## diagnostics
- **Symptom:** the period jitter jumps up to ms
  - Possible cause: a higher-priority task/ISR does long work; busy-wait; printf in a critical task.
  - What to do: priorities, short ISRs, output in a separate task via a queue.
- **Symptom:** the ESP32 reboots with “Task watchdog got triggered”
  - Possible cause: a task doesn't yield the core (no vTaskDelay/blocking wait).
  - What to do: wait for events instead of polling; `vTaskDelay(1)` in background loops.
- **Symptom:** the data in the DMA buffer is “stale” on F7/H7
  - Possible cause: the data cache.
  - What to do: non-cacheable memory or invalidate after reception.
- **Symptom:** an ISR causes a crash
  - Possible cause: a non-ISR-safe call (printf, malloc, a plain xQueueSend) or code not in IRAM on the ESP32.
  - What to do: the FromISR versions, IRAM_ATTR, minimal work.
- **Symptom:** Betaflight: CPU load > 90%, skipped tasks
  - Possible cause: an F4 at 8 kHz with all features on.
  - What to do: 4 kHz, disable what you don't need, check `tasks` in the CLI.

## references
- FreeRTOS — Mastering the FreeRTOS Real Time Kernel (book, GitHub) | https://www.github.com/FreeRTOS/FreeRTOS-Kernel-Book/blob/main/toc.md | primary | A
- ESP-IDF — FreeRTOS (ESP-IDF additions, task watchdog) | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos.html | primary | A
- Betaflight — source: fc/core.c and scheduler | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A

## checklist
- I understand how DMA and timers free up the CPU
- I know the ISR rules and priorities
- Two FreeRTOS tasks via a queue work, jitter measured
- I showed how blocking breaks the period, and fixed it
- I found the main loop in Betaflight and the task table in ArduPilot
