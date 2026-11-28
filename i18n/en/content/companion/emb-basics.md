---
id: emb-basics
title: "Embedded: interrupts, timers, DMA, RTOS"
level: L3
readingTime: 40 min
firmware: any firmware (examples checked against Betaflight 2026.6.2 and ArduPilot 4.7.3)
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
source_hash: 1f2679ecb171
---

## summary
An STM32 flight controller polls the gyro 8000 times a second, computes the PID loop, sends DShot to four ESCs, receives CRSF, writes a log, and draws the OSD, all on a single core. That is only possible because hardware does the work without the CPU (DMA, timers) and events arrive as interrupts. This module explains these mechanisms at the level you need to read firmware and build your own devices: interrupts and priorities, timers with capture and generation, DMA, the Betaflight scheduler, FreeRTOS on the ESP32 and NuttX in PX4, jitter, and why a `delay()` in the main loop is a disaster. The lab on an ESP32: two FreeRTOS tasks, a queue, a hardware timer, a jitter measurement, and a blocking call, shown and then fixed.

## theory
### What the flight controller's CPU is busy with
At 8 kHz the budget is 125 µs per loop. Reading 14 bytes from the gyro over SPI at 8+ MHz takes ~15 µs if you wait in the loop; with DMA it takes 0 µs of CPU time. The PID on three axes on an F4 (168 MHz) takes ~10–20 µs, the filters about as much, DShot goes through timer+DMA (0 µs), CRSF through a UART with an interrupt/DMA. What is left goes to lower tasks (`src/main/fc/tasks.c`): `TASK_RX` runs on events, when a frame arrives, with a fallback period of 33 Hz, `TASK_SERIAL` at 100 Hz, `TASK_BATTERY_CURRENT` at 50 Hz, `TASK_OSD` at `osd_framerate_hz`, `TASK_GPS` at 100 Hz (500 Hz while the receive buffer has bytes waiting), and blackbox on a divider of the PID loop. Betaflight uses a cooperative scheduler without an RTOS (`scheduler.c`): each task has a desired period, a priority, and an execution time estimate; the critical tasks (gyro/PID) preempt nothing; the scheduler simply does not start a lower task if its estimated execution time (`anticipatedExecutionTime`) does not fit before the next gyro cycle; the rest wait for a "gap".

### Interrupts
An interrupt is a hardware signal that suspends the running code and calls a handler (ISR). Sources: a UART byte is ready, a DMA transfer completed, a timer fired, an edge on a pin (EXTI: that is how the gyro says "data ready", Betaflight `gyro_sync` on EXTI). ISR rules: keep it short (microseconds), no blocking calls and no `printf`, no memory allocation; hand heavy work to a task through a flag/queue. **Priorities** (the NVIC on Cortex-M): a higher-priority interrupt preempts a lower-priority ISR; the gyro/DShot are higher, UART logging is lower. On an ESP32: `ESP_INTR_FLAG_LEVEL1..3`, the ISR in IRAM (`IRAM_ATTR`), work on the other core through a queue.

### Timers
A counter clocked from a bus that can: generate an interrupt every period (the scheduler, periodic tasks), produce **PWM** (compare), **capture** an input edge (input capture: measuring the pulse width from a PWM receiver), and trigger DMA on an event (DShot: the timer + DMA write a sequence of durations into the compare register, so one 16-bit DShot frame goes out with no CPU involvement). The resolution is one timer clock: at 84 MHz, 12 ns.

### DMA
A direct memory access controller copies data between peripherals and memory on events, without the CPU: UART reception into a ring buffer, reading an SPI gyro, DShot output, writing to the SD card. Limitations: the number of channels/streams and how they are tied to peripherals (on the STM32F4, DMA stream conflicts are the real reason some boards cannot run DShot on every motor and, say, an LED strip at the same time; Betaflight target files describe exactly this), and cache coherence on the F7/H7 (buffers in non-cacheable memory, or `SCB_Clean/InvalidateDCache`).

### RTOS: tasks, priorities, queues
FreeRTOS (ESP32; PX4 runs on NuttX, a different RTOS with the same concepts of tasks, priorities, and queues): tasks with priorities and their own stacks; a preemptive scheduler, so a higher-priority task always gets the core when it is ready; equal-priority tasks share it by time slices (the tick defaults to 100 Hz in ESP-IDF, `CONFIG_FREERTOS_HZ`; 1000 Hz in Arduino-ESP32). Primitives: the **queue** (ISR → task, task → task; copies the data, thread-safe), the **semaphore/notification** (an "event" signal), the **mutex** (protecting a shared resource, an I2C bus), and the **timer** (a software timer, running in the daemon task's context; not for precise periods). For a precise period: `vTaskDelayUntil` (a fixed period from the last wake-up, not from the end of the work) or a hardware timer + a notification.

### Jitter and blocking
Jitter is the spread of the actual period. Causes: an ISR doing long work, a higher-priority task, cache misses, `delay()`/waiting in a loop (busy-wait), `printf` logging from a critical task, flash operations (on an ESP32 a flash write stalls code executing from flash on the other core unless it is in IRAM). For a control loop, jitter should stay < 5–10% of the period; PX4 and Betaflight measure and log it (`DEBUG_CYCLETIME`, PX4 `perf`).

**Why blocking in the main loop is a disaster**: the control task waits 50 ms on a UART → 400 missed loops at 8 kHz → the gyro data is stale, the D-term jumps, the motors "twitch"; in the worst case the watchdog reboots the controller in flight. Hence the rule: the control loop never waits for anything; it only reads data that is already there.

{{diagram:emb-blocking-timeline|50 ms of waiting on a UART is 400 loops not run at 8 kHz; a correct loop never waits, and an interrupt or DMA collects the bytes into a ring buffer.}}

### Watchdog
A hardware timer that resets the MCU if it is not "fed". Betaflight/ArduPilot/PX4 use it: a hang means a reboot (better than motors stuck at their last value forever); ArduPilot controls it with `BRD_OPTIONS` bit 0 (on by default on ChibiOS boards) and logs the details in a `WDOG` message. On an ESP32 there is the task watchdog on the idle tasks: a task without `vTaskDelay` starves idle → the TWDT fires.

{{diagram:fc-loop-125us|One 8 kHz loop: gyro read by DMA, filters, PID and mixer, a DShot frame by DMA; a UART interrupt squeezes in, and the rest of the loop goes to slow tasks (orders of magnitude, not an exact profile).}}

### Where it fits in the system

- **Takes in:** the gyro's "data ready" signal and the data itself over SPI (`f-fc-sensors`, `emb-protocols`); CRSF frames over a UART (`link-protocols`).
- **Puts out:** the "gyro → PID → DShot" loop with low jitter, to the motors through the ESCs (`f-motors-esc`); the remaining time to the OSD, blackbox, and telemetry (`bf-intro`).
- **If you get this wrong:** a blocking wait in the control loop → missed loops, a D-term jump, twitching motors; it looks like bad tuning, but `tasks` shows it as overload and jitter (`bf-intro`). An LED strip on a motor's DMA stream or timer → DShot breaks, and the motor does not start; the timer map is in `bf-led-buzzer`.

## practice
### Step 1. Two tasks and a queue (ESP32, ESP-IDF or Arduino-FreeRTOS)
```c
// sensor task: hardware timer notifies every 1 ms; reads IMU (or fakes it) and pushes a sample
static QueueHandle_t q;
static TaskHandle_t sensorTask;
static void IRAM_ATTR on_timer(void *arg) {           // ISR: just notify
  BaseType_t hp = pdFALSE;
  vTaskNotifyGiveFromISR(sensorTask, &hp);
  if (hp) esp_timer_isr_dispatch_need_yield();   // not portYIELD_FROM_ISR() in an esp_timer ISR callback
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
  for (;;) if (xQueueReceive(q, &s, portMAX_DELAY)) printf("%lld,%ld,%.2f\n", (long long)s.t_us, (long)s.dt_us, s.gyro);
}
// app_main: q = xQueueCreate(64, sizeof(sample_t)); create sensor_task prio 10, uart_task prio 3;
// esp_timer periodic 1000 us -> on_timer with dispatch_method = ESP_TIMER_ISR (needs CONFIG_ESP_TIMER_SUPPORTS_ISR_DISPATCH_METHOD); default ESP_TIMER_TASK runs the callback in the esp_timer task, not an ISR
```
Build, run, and save 10 s of output to a file.

### Step 2. Jitter
From `dt_us`: the mean (≈1000), std, maximum, a histogram. Expect std < 10 µs, max < 50.

### Step 3. Break it and fix it
In `uart_task`, add a busy-wait loop of 5 ms with no `vTaskDelay(0)` (for example, `while (esp_timer_get_time() < t0 + 5000) {}`) and raise its priority to 11: watch the sensor jitter grow to milliseconds (or the TWDT fire). Set the priority back to 3, and the jitter recovers: preemption works. Then put a blocking flash write (NVS) into `sensor_task`, see the dropout, and move it to a separate task. Lab: two tasks through a queue, a jitter measurement, a blocking call shown and fixed. Self-check by the numbers: before breaking it, the mean `dt_us` ≈ 1000, std < 10 µs, max < 50 µs; with the busy-wait at priority 11, the sensor jitter grows to milliseconds (or the TWDT fires); after returning to priority 3 and moving the flash write to a separate task, the numbers return to the original ones. If std and max did not come back, a blocking call is still in `sensor_task`.

### Step 4. Read the firmware
In Betaflight `src/main/fc/core.c`: `taskMainPidLoop` → `subTaskPidController` → `subTaskMotorUpdate`; in `scheduler/scheduler.c`, how tasks are picked. In ArduPilot `ArduCopter/Copter.cpp`, the `scheduler_tasks[]` table: `FAST_TASK` (at the main loop rate: INS update → `run_rate_controller_main` → `motors_output_main` → AHRS…) and `SCHED_TASK(rc_loop, 250, …)` with a rate, a time budget, and a priority.

## diagnostics
- **Symptom:** the period jitter jumps to ms
  - Possible cause: a higher-priority task/ISR doing long work; a busy-wait; printf in a critical task.
  - What to do: priorities, short ISRs, output in a separate task through a queue.
- **Symptom:** the ESP32 reboots with "Task watchdog got triggered"
  - Possible cause: a task does not yield the core (no vTaskDelay/blocking wait).
  - What to do: wait on events instead of polling; `vTaskDelay(1)` in background loops.
- **Symptom:** data in a DMA buffer is "stale" on an F7/H7
  - Possible cause: the data cache.
  - What to do: non-cacheable memory, or invalidate after reception.
- **Symptom:** an ISR causes a crash
  - Possible cause: a call that is not ISR-safe (printf, malloc, plain xQueueSend), or code not in IRAM on the ESP32.
  - What to do: FromISR versions, IRAM_ATTR, minimal work.
- **Symptom:** Betaflight: CPU load > 90%, skipped tasks
  - Possible cause: an F4 at 8 kHz with every feature on.
  - What to do: 4 kHz, turn off what you do not need, check `tasks` in the CLI.

## references
- FreeRTOS — Mastering the FreeRTOS Real Time Kernel (book, GitHub) | https://www.github.com/FreeRTOS/FreeRTOS-Kernel-Book/blob/main/toc.md | primary | A
- ESP-IDF — FreeRTOS (ESP-IDF additions, task watchdog) | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos.html | primary | A
- Betaflight — source: fc/core.c and scheduler | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A

## checklist
- I understand how DMA and timers free up the CPU
- I know the ISR rules and priorities
- Two FreeRTOS tasks work through a queue, and the jitter is measured
- I showed how blocking breaks the period, and fixed it
- I found the main loop in Betaflight and the task table in ArduPilot
