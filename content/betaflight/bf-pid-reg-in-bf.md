---
id: bf-pid-tuning
title: "PID-тюнинг в Betaflight"
level: L2
readingTime: 25 мин
firmware: Betaflight 4.5+
status: draft
tags:
  - PID
  - tuning
  - Betaflight
  - Blackbox
references:
  - title: "Betaflight PID Tuning Guide"
    url: "https://github.com/betaflight/betaflight/wiki/PID-Tuning-Guide"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.x PID Controller Explanation"
    url: "https://github.com/betaflight/betaflight/wiki/4.x-PID-Controller-Explanation"
    tier: primary
    stack: betaflight
  - title: "Betaflight RPM Filtering"
    url: "https://github.com/betaflight/betaflight/wiki/RPM-Filtering"
    tier: primary
    stack: betaflight
related:
  - bf-filters
  - bf-blackbox
next:
  - bf-cli
---

## summary

PID-регулятор — ядро стабилизации в Betaflight. Статья объясняет физический смысл коэффициентов P, I, D, их взаимодействие, влияние на поведение дрона и методы настройки с использованием Blackbox. После изучения читатель сможет диагностировать типовые проблемы (осцилляции, bounce-back, перегрев моторов) и целенаправленно корректировать параметры, избегая хаотичного подбора.

## theory

PID-регулятор (Proportional-Integral-Derivative) получает от гироскопа угловую скорость по осям roll, pitch, yaw и минимизирует ошибку между желаемой (setpoint, от стиков или навигации) и текущей скоростью вращения. Выход регулятора (PID sum) через миксер преобразуется в сигналы на моторы.

**P-term (пропорциональный)** реагирует на текущую ошибку: чем больше ошибка, тем сильнее коррекция. Определяет основную жёсткость дрона. Недостаток: не может полностью устранить статическую ошибку (дрейф). При завышении вызывает быстрые осцилляции (20–50 Гц).

**I-term (интегральный)** накапливает ошибку во времени, устраняя постоянное отклонение (дрейф от ветра, смещение центра масс). Работает медленнее P. При завышении вызывает медленные плавающие осцилляции (1–5 Гц) и эффект wind-up. Параметр `i_limit` ограничивает максимальное значение I-term.

**D-term (дифференциальный)** реагирует на скорость изменения ошибки, действуя как демпфер. Подавляет колебания, вызванные P-термом. Критически чувствителен к шуму гироскопа. Без фильтрации создаёт высокочастотный шум, перегревающий моторы. Правило: D-term настраивается после P-term; увеличение P требует увеличения D.

**Специфика Betaflight 4.5+:**

- **Feedforward** — независимый канал управления, подающий сигнал прямо на моторы на основе скорости движения стика. Ускоряет отклик без увеличения P-term.
- **TPA (Throttle PID Attenuation)** — снижение PID-коэффициентов на высоких оборотах. В BF 4.5+ работает в режиме `D` (снижает только D-term).
- **RPM Filtering** — использование данных с ESC для подавления шума от пропеллеров. Создаёт узкие фильтры на частоте вращения моторов, позволяя поднимать D-term.

## practice

**Подготовка**

Аппаратные требования: ESC с поддержкой RPM Filtering (BLHeli_32 или Bluejay), полетный контроллер F7/H7, карта памяти SD для Blackbox (минимум 4 ГБ).

Программные требования: Betaflight Configurator 10.10+, Blackbox Explorer.

**Настройка перед тюнингом**

1. Включите RPM Filtering: во вкладке Configuration включите *RPM Filter*, установите `rpm_notch_q = 500` (CLI).
2. Настройте Blackbox: выберите частоту записи 2 кГц, включите логирование gyro_scaled, pid, setpoint, motor.
3. Установите базовые параметры фильтрации:
set gyro_lowpass2_hz = 300
set gyro_lowpass2_type = PT2
set dterm_lowpass2_hz = 150
set dterm_lowpass2_type = PT2
set dynamic_notch_range = MEDIUM
set dynamic_notch_q = 250
save

text

**Пошаговая настройка**

1. Определите стартовые значения (для рамы 5" с моторами 2207–2306):
set p_pitch = 45, i_pitch = 50, d_pitch = 25
set p_roll = 42, i_roll = 45, d_roll = 23
set p_yaw = 70, i_yaw = 50, d_yaw = 20
set d_min_roll = 20, d_min_pitch = 22
save

text

2. Настройка P-term: выполните резкий рывок стиком с возвратом. В Blackbox смотрите график gyro (синий) и setpoint (зелёный). Если gyro пересекает setpoint в обратную сторону (bounce-back) — P низкий, увеличьте на 10. Если gyro колеблется вокруг setpoint — P высокий, уменьшите на 5.

3. Настройка D-term: после настройки P выполните то же движение. Добавьте график D-term. Если D-term дрожит высокочастотным шумом — снизьте D на 3–5. Если после движения gyro идёт с затухающими колебаниями — увеличьте D на 3.

4. Настройка I-term: зависните в режиме Angle/Horizon, слегка наклоните дрон и верните в ноль. Если дрон медленно дрейфует — увеличьте I на 10. Если проходит нейтраль и раскачивается — уменьшите I на 10.

5. Настройка Feedforward: выполните серию быстрых движений стиком. В Blackbox сравните setpoint и gyro. При большом отставании увеличьте `feedforward_boost`. При overshoot уменьшите `feedforward_boost`.

6. Настройка TPA: выполните punch-out (20% → 80% газа). Если motor выходит на 100% без снижения — проверьте `tpa_rate`. При высокочастотной пульсации увеличьте `tpa_rate` до 1.5, снизьте `tpa_breakpoint` до 1400.

**Заключительные шаги**

Сохраните финальные параметры: `diff all`. Выполните короткий полёт (2–3 минуты) и проверьте температуру моторов. Если моторы горячие, снизьте D-term на 10–15%.

## diagnostics

- **Симптом: Быстрые осцилляции на ховере (жужжание, дрожание)**
- Возможная причина: завышенный P-term, недостаточная фильтрация гироскопа.
- Что проверить/сделать: снять Blackbox. Если график gyro имеет частые пики 50–100 Гц — уменьшить P на 20%. Проверить работу dynamic notch и RPM filtering.

- **Симптом: Bounce-back после резкого движения**
- Возможная причина: низкий P-term, высокий D-term.
- Что проверить/сделать: в Blackbox сравнить setpoint и gyro: gyro не доходит до setpoint. Увеличить P на 10%. Если bounce-back не уходит — проверить D-term.

- **Симптом: Медленные плавающие колебания (~1–3 Гц)**
- Возможная причина: завышенный I-term, неверный anti-windup.
- Что проверить/сделать: уменьшить I на 15–20%. Проверить параметр `i_limit` (100–150 достаточно).

- **Симптом: Перегрев моторов**
- Возможная причина: высокий D-term, недостаточная фильтрация D-term.
- Что проверить/сделать: в Blackbox посмотреть график D-term — если похож на шум, снизить D на 20–30%. Увеличить `dterm_lowpass2` до 100–120 Гц.

- **Симптом: Дрон уходит при резком добавлении газа (punch-out)**
- Возможная причина: неверная настройка TPA, высокий P/D без аттенюации.
- Что проверить/сделать: в Blackbox на графике throttle найти punch-out. Если PID sum клиппирует — увеличить `tpa_rate` или снизить `tpa_breakpoint`.

- **Симптом: Шум на гироскопе в логах (пилообразный график)**
- Возможная причина: механические вибрации, неработающий RPM Filtering.
- Что проверить/сделать: проверить работу RPM Filtering (во вкладке Motors должна отображаться частота вращения). Включить `gyro_lowpass2` 250–300 Гц.

## references

- Betaflight PID Tuning Guide | https://github.com/betaflight/betaflight/wiki/PID-Tuning-Guide | primary | A
- Betaflight 4.x PID Controller Explanation | https://github.com/betaflight/betaflight/wiki/4.x-PID-Controller-Explanation | primary | A
- Betaflight RPM Filtering | https://github.com/betaflight/betaflight/wiki/RPM-Filtering | primary | A
- Betaflight Blackbox Log Interpretation | https://github.com/betaflight/betaflight/wiki/Blackbox-Log-Interpretation | primary | A
- Oscar Liang: Betaflight PID Tuning | https://oscarliang.com/betaflight-pid-tuning/ | secondary | B
- Joshua Bardwell: How to Tune PID with Blackbox | https://www.youtube.com/watch?v=YXpPajW9lCU | secondary | B