---
id: tools-overview
title: "Инструменты: Configurator, GCS, git"
level: L1
readingTime: 15 мин
firmware: любая прошивка
status: published
added: 2026-11-07
tags:
  - инструменты
  - git
  - GCS
related:
  - f-safety
  - bf-cli-automation
next:
  - bf-intro
---

## summary
Инженеру БПЛА нужен не один инструмент, а набор: конфигуратор под прошивку, наземная станция, анализатор логов, терминал и система контроля версий для конфигов. Модуль описывает минимальный стек на 2026 год, что чем делать, и одно правило, которое экономит больше всего нервов: конфиги и логи живут в папках с датами и в git.

## theory
### Конфигураторы прошивок
- **Betaflight App** — настройка Betaflight: порты, приёмник, режимы, PID, OSD, CLI, прошивка. Есть версии под Windows/macOS/Linux и веб-версия.
- **INAV Configurator** — то же для INAV, с планировщиком миссий.
- **Mission Planner** (Windows) и **QGroundControl** (кроссплатформенный) — наземные станции для ArduPilot и PX4: параметры, калибровки, миссии, телеметрия, логи. Для ArduPilot на Linux удобен и консольный **MAVProxy**.

### Прошивка и ESC
- **Betaflight App → Firmware Flasher** с Cloud Build.
- **ESC Configurator** (веб) или **Bluejay/AM32 Configurator** для прошивки ESC через passthrough.
- **ExpressLRS Configurator** — прошивка приёмников и модулей ELRS.
- Иногда нужен **Zadig** (Windows) для драйвера DFU при прошивке.

### Логи
- **Blackbox Explorer** (Betaflight) и **PIDtoolbox** — логи Betaflight.
- **Mission Planner / MAVExplorer / UAV Log Viewer** — DataFlash ArduPilot.
- **Python** с `orangebox` (Betaflight) и `pymavlink.DFReader` (ArduPilot) — когда нужны свои метрики.

### Терминал и Python
Linux-терминал или WSL на Windows: `picocom`/`minicom` для UART, `pyserial` для скриптов к CLI, `pymavlink` для MAVLink, `scipy`/`matplotlib` для спектров. Виртуальное окружение на проект (`python -m venv`), чтобы версии библиотек не мешали друг другу.

### Git для конфигов
Конфигурация дрона — это код. `diff all` Betaflight и `.param` ArduPilot — текстовые файлы, их можно хранить в git, сравнивать и откатывать. Структура:

```
drones/
  viking2/
    configs/   2026-11-03_viking2_F405_diff.txt
    logs/      2026-11-03_daylight_profiles/
    notes/     session_notes.md, SUMMARY_2026-11-03.md
  viking10/
```

Имя файла начинается с даты `ГГГГ-ММ-ДД` — сортировка по имени даёт хронологию. Перед любым изменением — файл «до», после — файл «после», разница видна `git diff`.

### SITL
Для ArduPilot — SITL, для PX4 — Gazebo/jMAVSim. Любой сценарий, скрипт и параметр сначала на симуляторе.

## practice
### Минимальная установка
1. Betaflight App, Mission Planner или QGroundControl.
2. Python 3 + `pip install pyserial pymavlink orangebox scipy matplotlib` в venv.
3. Git; репозиторий `drones/` по структуре выше.
4. Терминал последовательного порта.
5. Для ArduPilot — SITL по модулю «SITL: дрон без дрона».

### Первый коммит
1. Подключить дрон, `diff all` в CLI (или сохранить `.param`).
2. Сохранить в `drones/<имя>/configs/<дата>_<имя>_<плата>_diff.txt`.
3. `git add`, `git commit -m "<имя>: baseline <дата>"`.
4. После любого изменения — новый файл и коммит с описанием, что и зачем.

### Лабораторная
Сделай два дифа с разницей в один параметр и покажи `git diff` между ними. Это твой первый «код-ревью» собственного дрона.

## diagnostics
- **Симптом:** конфигуратор не видит плату
  - Возможная причина: драйвер (Windows), кабель только для зарядки, плата в DFU.
  - Что сделать: Zadig для DFU, другой кабель, проверить COM-порт.
- **Симптом:** не помню, что менял перед тем, как сломалось
  - Возможная причина: нет дифов «до/после».
  - Что сделать: правило «файл до изменений — всегда», git.
- **Симптом:** библиотеки Python конфликтуют между проектами
  - Возможная причина: всё ставится в системный Python.
  - Что сделать: venv на проект.

## references
- Betaflight App — Documentation | https://betaflight.com/docs/wiki/app | primary | A
- Mission Planner — Documentation | https://ardupilot.org/planner/ | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/master/en/ | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A
- Pro Git — book | https://git-scm.com/book/en/v2 | primary | A

## checklist
- Установлены конфигуратор и наземная станция под мои прошивки
- Python в venv с pyserial/pymavlink
- Репозиторий `drones/` с папкой на каждый дрон
- Каждый конфиг — файл с датой в имени, в git
- Перед изменениями всегда есть файл «до»
