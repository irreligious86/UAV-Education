---
id: bf-filters
title: "Фильтры"
level: L2
readingTime: 45 мин
firmware: Betaflight 4.5+
status: published
tags:
  - filters
  - Blackbox
  - tuning
  - diagnostics
  - PID
references:
  - title: "Betaflight CLI Documentation — Gyro & Filter Variables"
    url: "https://www.betaflight.com/docs/development/Cli"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.1 Tuning Notes — Filter Settings"
    url: "https://www.betaflight.com/docs/wiki/tuning/4-1-Tuning-Notes#new-filter-settings"
    tier: primary
    stack: betaflight
  - title: "PID Tuning Tab — Filter Settings"
    url: "https://www.betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings"
    tier: primary
    stack: betaflight
  - title: "Gyro and Dterm Filtering Recommendations 3.1 (archive)"
    url: "https://betaflight-com.pages.dev/docs/wiki/guides/archive/Gyro-And-Dterm-Filtering-Recommendations-3-1"
    tier: primary
    stack: betaflight
  - title: "PID ToolBox — Filter Analysis Tool"
    url: "https://github.com/PID-ToolBox"
    tier: secondary
    stack: betaflight
  - title: "How to Tune Filters & PID with Blackbox — Oscar Liang"
    url: "https://oscarliang.com/pid-filter-tuning-blackbox/"
    tier: secondary
    stack: betaflight
  - title: "Bare Minimum Tune Betaflight — Filter Workflow"
    url: "https://hackmd.io/@nerdCopter/rJzic_N-p"
    tier: secondary
    stack: betaflight
  - title: "Reglages Betaflight : filtres PT2, BIQUAD et sliders"
    url: "https://www.drone-fpv.fr/reglages-betaflight-vol-fluide/#Comparatif_des_approches_de_filtrage_et_choix_pragmatique"
    tier: secondary
    stack: betaflight
related:
  - bf-blackbox
  - bf-pid
  - bf-cli
next:
  - bf-custom
---

## summary

Фильтрация сигнала гироскопа и D-term — критически важный этап настройки дрона в Betaflight. Без корректной фильтрации шум от моторов, пропеллеров и резонансов рамы попадает в PID-регулятор, вызывая перегрев моторов, осцилляции и ухудшение управляемости.

Этот модуль объясняет физическую природу шумов, архитектуру фильтров (RPM, dynamic notch, lowpass PT1/PT2/BIQUAD), их влияние на задержку и поведение дрона. После изучения вы сможете настраивать фильтры по данным Blackbox, а не методом случайного подбора.

## theory

### Природа шумов в системе БПЛА

Сигнал гироскопа содержит полезную динамику и шум. Источники шума:

- моторы и пропеллеры (включая гармоники);
- резонанс рамы и креплений;
- электромагнитные помехи от силовой части;
- алиасинг при несоответствии частоты дискретизации.

D-term особенно чувствителен к высокочастотному шуму, поэтому при плохой фильтрации именно он чаще всего приводит к перегреву моторов.

### Архитектура фильтров в Betaflight

В Betaflight 4.5+ обычно используется каскад:

1. RPM Filter — самый эффективный фильтр шумов моторов.
2. Dynamic Notch — авто-подавление резонансных пиков.
3. Lowpass-фильтры (gyro и D-term) — финальная очистка.
4. Статические notch-фильтры — опционально, когда автофильтров недостаточно.

### Задержка vs чистота сигнала

Любой фильтр добавляет задержку.  
Слишком сильная фильтрация делает дрон "ватным"; слишком слабая — шумным и горячим.

Практическая цель: минимальная задержка при стабильной температуре моторов и чистом спектре.

## practice

### Подготовка

- ESC с Bidirectional DShot (BLHeli_32 / Bluejay).
- FC F4/F7/H7.
- Исправная механика: без люфтов, ровные пропеллеры.
- Логирование в Blackbox (flash/SD).

### Базовая настройка

1. Включите Blackbox и RPM filtering.
2. Убедитесь, что RPM телеметрия работает (`E = 0%` во вкладке Motors).
3. Сохраните текущую конфигурацию:

```text
diff all
```

4. Базовые параметры:

```text
set dyn_notch_width_percent = 0
set dyn_notch_q = 250
set dshot_bidir = ON
save
```

### Пошаговая настройка

1. Снимите лог с throttle sweep (`20% -> 100%`) и обычными маневрами.
2. Посмотрите спектр в Blackbox Explorer / PID ToolBox.
3. Определите шумовые зоны:
   - `<100 Гц` — часто механика/PID;
   - `100–250 Гц` — резонансы;
   - `>250 Гц` — моторный шум.
4. Корректируйте lowpass осторожно, по одному параметру за итерацию.
5. После каждого изменения — новый лог и сравнение.

### Пример ручной корректировки

```text
set gyro_lpf1_static_hz = 0
set gyro_lpf2_hz = 300
set dterm_lpf1_hz = 150
set dterm_lpf2_hz = 120
save
```

Если при активном RPM + dynamic notch статические notch не нужны:

```text
set gyro_notch1_hz = 0
set gyro_notch2_hz = 0
set dterm_notch_hz = 0
save
```

## diagnostics

- Симптом: моторы горячие после короткого полета.
  - Возможная причина: D-term шумит, RPM-фильтр не работает.
  - Что сделать: проверить `Bidirectional DShot`, активность RPM filter, усилить фильтрацию D-term.

- Симптом: дрон "дребезжит" на ховере.
  - Возможная причина: гирошум/резонанс попадает в PID.
  - Что сделать: проверить спектр, убедиться в работе dynamic notch и RPM filter.

- Симптом: при резком газе появляется визг и просадки по управлению.
  - Возможная причина: резонанс в рабочем диапазоне оборотов.
  - Что сделать: снять throttle sweep, локализовать частоту пика, при необходимости добавить статический notch.

- Симптом: после фильтрации дрон стал "ватным".
  - Возможная причина: избыточная фильтрация (высокая задержка).
  - Что сделать: постепенно поднимать частоты среза и контролировать температуру моторов.

- Симптом: в логах "пушистый" gyro (широкая шумовая полоса).
  - Возможная причина: RPM телеметрия отсутствует или невалидна.
  - Что сделать: проверить RPM и ошибку `E`, прошивку ESC, настройки bidirectional DShot.

## references

- Betaflight CLI Documentation — Gyro & Filter Variables | https://www.betaflight.com/docs/development/Cli | primary | A
- Betaflight 4.1 Tuning Notes — Filter Settings | https://www.betaflight.com/docs/wiki/tuning/4-1-Tuning-Notes#new-filter-settings | primary | A
- PID Tuning Tab — Filter Settings | https://www.betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings | primary | A
- Gyro and Dterm Filtering Recommendations 3.1 (archive) | https://betaflight-com.pages.dev/docs/wiki/guides/archive/Gyro-And-Dterm-Filtering-Recommendations-3-1 | primary | A
- PID ToolBox — Filter Analysis Tool | https://github.com/PID-ToolBox | secondary | B
- How to Tune Filters & PID with Blackbox — Oscar Liang | https://oscarliang.com/pid-filter-tuning-blackbox/ | secondary | B
- Bare Minimum Tune Betaflight — Filter Workflow | https://hackmd.io/@nerdCopter/rJzic_N-p | secondary | B
- Reglages Betaflight : filtres PT2, BIQUAD et sliders | https://www.drone-fpv.fr/reglages-betaflight-vol-fluide/#Comparatif_des_approches_de_filtrage_et_choix_pragmatique | secondary | B
