---
id: ap-logs
title: "Логи ArduPilot: разбор полёта"
level: L3
readingTime: 30 мин
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - DataFlash
  - логи
  - диагностика
related:
  - ap-ekf
  - bf-blackbox
next:
  - ap-lua
---

## summary
ArduPilot пишет на SD-карту бинарный лог DataFlash (`.bin`) с сотнями типов сообщений: ориентация, высота, моторы, батарея, EKF, ошибки. Это чёрный ящик, который отвечает на вопрос «почему» после любого странного полёта. Модуль даёт порядок разбора — от вибраций до ошибок — с конкретными именами сообщений и полей, порогами из документации и скриптом на Python для своих графиков.

## theory
### Два вида логов
- **DataFlash** (`.bin`) — на борту, высокая частота, всё подряд. Основной инструмент.
- **Telemetry log** (`.tlog`) — то, что видела GCS по радио. Реже и с дырами, но есть даже если SD-карта сгорела вместе с аппаратом.

Параметр `LOG_BITMASK` задаёт, что писать; `LOG_DISARMED` включает запись до арма (полезно для разбора pre-arm проблем).

### Сообщения, с которых начинают
- `VIBE` — вибрации: `VibeX`, `VibeY`, `VibeZ` (м/с²) и `Clip` — счётчик насыщения акселерометра. Ниже 30 нормально, выше 60 почти наверняка проблемы с высотой и позицией. Клиппинг должен быть нулевым.
- `ATT` — `DesRoll` против `Roll`, `DesPitch` против `Pitch`: насколько аппарат успевает за желаемым. Резкое расхождение — механическая проблема или нехватка тяги.
- `CTUN` — управление высотой: `ThO` (выход газа), `ThH` (оценка газа висения), `DAlt`/`Alt` (желаемая и фактическая высота), `BAlt` (баро).
- `BAT` — `Volt`, `Curr`, `CurrTot`, `Res` (оценка внутреннего сопротивления). Просадка под током и реальный расход.
- `RCIN` — каналы с пульта `C1…C14`: что делал пилот.
- `MODE` — смена режимов и причина `Rsn`.
- `ERR` — ошибки: `Subsys` и `ECode`. Например, подсистема 2 (радио) с кодом 2 — нет кадров приёмника две секунды; 11 — GPS-глитч; 16 — плохая вариация EKF; 17 — EKF-failsafe; 29 — компенсация вибраций.
- `MSG` — текстовые сообщения, в том числе pre-arm.
- `GPS` — `NSats`, `HDop`: HDOP ниже 1.5 хорошо, выше 2.0 подозрительно; меньше 12 спутников — плохо.
- `XKF1…XKF4` — внутренности EKF3 по ядрам: оценки и вариации (`XKF4`: `SV`, `SP`, `SH`, `SM` — скорость, позиция, высота, компас).
- `POWR` — `VCC` платы: колебания больше 0.1–0.15 В намекают на проблемы питания.

### Порядок разбора
1. **Обрывается ли лог?** Лог, который кончается в воздухе, — потеря питания или перезагрузка.
2. **Вибрации** (`VIBE`). Всё остальное бессмысленно, пока они высокие.
3. **Ошибки** (`ERR`, `MSG`): что и когда сработало.
4. **Режимы** (`MODE`): кто менял режим — пилот или failsafe.
5. **Управление** (`ATT`, `CTUN`): успевал ли аппарат за командами.
6. **Питание** (`BAT`, `POWR`): просадки и их совпадение с событиями.
7. **Навигация** (`GPS`, `XKF4`): качество позиции и вариации в момент проблемы.

### Инструменты
Mission Planner (Review a Log), MAVExplorer из пакета MAVProxy (графики по именам полей, например `graph ATT.Roll ATT.DesRoll`), UAV Log Viewer в браузере. Для автоматизации — `pymavlink.DFReader`: читает `.bin` напрямую в Python.

## practice
### Скрипт: вибрации и клиппинг по логу
```python
import sys
from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1])
vibe = {"VibeX": [], "VibeY": [], "VibeZ": []}
clip_max = 0
errors = []
while True:
    m = log.recv_msg()
    if m is None:
        break
    t = m.get_type()
    if t == "VIBE" and m.IMU == 0:
        for k in vibe:
            vibe[k].append(getattr(m, k))
        clip_max = max(clip_max, m.Clip)
    elif t == "ERR":
        errors.append((m.TimeUS / 1e6, m.Subsys, m.ECode))

for k, v in vibe.items():
    v = sorted(v)
    print(f"{k}: median {v[len(v)//2]:.1f}  p95 {v[int(len(v)*0.95)]:.1f} m/s/s")
print("accel clipping events:", clip_max)
for t, sub, code in errors:
    print(f"ERR at {t:7.1f}s  subsys={sub} ecode={code}")
```

Запуск: `python vibe_report.py 00000012.BIN`. Медиана выше 30 или ненулевой клиппинг — сначала механика, потом всё остальное.

### Лабораторная
1. Сделай в SITL полёт с миссией и отказом мотора по тумблеру.
2. Скачай лог (в SITL — папка `logs/`).
3. Найди момент отказа по `RCIN` (тумблер) и посмотри, как разошлись `DesRoll`/`Roll` и выросли выходы моторов (`RCOU`).
4. Напиши отчёт на пять строк: что случилось, когда, как аппарат справился, какие параметры стоит поменять.

### Реальный лог
Повтори то же с логом реального висения: вибрации, газ висения (`CTUN.ThH`), просадка батареи. Сохрани лог и отчёт в папку дрона с датой.

## diagnostics
- **Симптом:** лог обрывается в воздухе
  - Возможная причина: потеря питания платы.
  - Что сделать: `POWR.VCC` перед обрывом, пайка силовых разъёмов, BEC.
- **Симптом:** `VIBE` высокие, `Clip` растёт
  - Возможная причина: дисбаланс пропов/моторов, жёсткое крепление FC.
  - Что сделать: балансировка, демпферы, проверка рамы — до любых фильтров.
- **Симптом:** `DesRoll` и `Roll` расходятся, один мотор на максимуме в `RCOU`
  - Возможная причина: отказ или слабость мотора/ESC, перегруз.
  - Что сделать: проверить мотор, пропеллер, ESC; сравнить выходы моторов на висении.
- **Симптом:** `ERR` 16/17 перед аварией
  - Возможная причина: плохие вариации EKF — компас, GPS или вибрации.
  - Что сделать: `XKF4` в тот момент, причина по предыдущему модулю.

## references
- Diagnosing problems using Logs — ArduPilot Copter | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A
- Downloading and Analyzing Data Logs — ArduPilot | https://ardupilot.org/copter/docs/common-downloading-and-analyzing-data-logs-in-mission-planner.html | primary | A
- Log message reference (LogStructure.h, GitHub) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Logger/LogStructure.h | primary | A
- MAVExplorer — MAVProxy | https://ardupilot.org/dev/docs/using-mavexplorer-for-log-analysis.html | primary | A

## checklist
- Знаю разницу DataFlash и tlog
- Разбор начинаю с обрыва лога и вибраций
- Умею найти `ERR` и расшифровать подсистему
- Скрипт на DFReader читает мой лог
- Логи и отчёты лежат в папке дрона с датой
