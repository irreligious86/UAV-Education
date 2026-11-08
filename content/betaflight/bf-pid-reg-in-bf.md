---
id: bf-pid-reg-in-bf
title: "PID-тюнинг в Betaflight"
level: L2
readingTime: 25 мин
firmware: Betaflight 4.5+
status: published
tags:
  - PID
  - tuning
  - Betaflight
  - Blackbox
references:
  - title: "Betaflight PID Tuning Guide"
    url: "https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide"
    tier: primary
    stack: betaflight
  - title: "Betaflight DShot RPM Filtering"
    url: "https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering"
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

**I-term (интегральный)** накапливает ошибку во времени, устраняя постоянное отклонение (дрейф от ветра, смещение центра масс). Работает медленнее P. При завышении вызывает медленные плавающие осцилляции (1–5 Гц) и эффект wind-up. Параметр `iterm_limit` (в 2025.12 — `iterm_windup`) ограничивает максимальное значение I-term.

**D-term (дифференциальный)** реагирует на скорость изменения ошибки, действуя как демпфер. Подавляет колебания, вызванные P-термом. Критически чувствителен к шуму гироскопа. Без фильтрации создаёт высокочастотный шум, перегревающий моторы. Правило: D-term настраивается после P-term; увеличение P требует увеличения D.

**Специфика Betaflight 4.5+:**

- **Feedforward** — независимый канал управления, подающий сигнал прямо на моторы на основе скорости движения стика. Ускоряет отклик без увеличения P-term.
- **TPA (Throttle PID Attenuation)** — снижение PID-коэффициентов на высоких оборотах. В BF 4.5+ по умолчанию `tpa_mode = D` (снижает только D-term); доступен и `PD`.
- **RPM Filtering** — использование данных с ESC для подавления шума от пропеллеров. Создаёт узкие фильтры на частоте вращения моторов, позволяя поднимать D-term.

### Формула, как она реализована в `flight/pid.c`
Для каждой оси в каждом цикле (на частоте PID): ошибка e = setpoint − gyro (отфильтрованный);
- P = Kp·e;
- I += Ki·e·dt с ограничением `iterm_limit` (анти-windup) и «релаксацией» (ниже);
- D = −Kd·d(gyro_D)/dt — производная **от гироскопа**, не от ошибки (движение стика не создаёт удара по D), после D-фильтров (модуль «Фильтры»), с множителем `d_min`-логики;
- FF = Kff·d(setpoint)/dt с усреднением/сглаживанием (`feedforward_averaging`, `feedforward_smooth_factor`, `feedforward_jitter_factor`, `feedforward_boost` — добавка от второй производной, `feedforward_max_rate_limit`);
- сумма → TPA → `pidSum` → миксер.
Коэффициенты из конфигуратора («45») умножаются на масштабы в `pid_init.c` (P ≈ 0.032, I ≈ 0.244, D ≈ 0.00053, FF ≈ 0.0138) — это и есть «безразмерность» Betaflight; физический смысл восстанавливается только через отклик (модуль «Теория управления»).

### Механизмы, которых нет в учебнике по PID
- **I-term relax** (`iterm_relax = RP`, `iterm_relax_type = SETPOINT`, `iterm_relax_cutoff = 15`): во время быстрых движений стика накопление I приостанавливается — иначе после флипа I «довозит» лишний поворот (bounce-back одного из типов). Cutoff ниже → релакс агрессивнее.
- **I-term rotation** (`iterm_rotation`): при вращении по yaw накопленные I по roll/pitch поворачиваются вместе с рамой.
- **Anti-gravity** (`anti_gravity_gain`, `anti_gravity_p_gain`, `anti_gravity_cutoff_hz`): временно поднимает I (и P) при резких изменениях газа — против «клевка» при ударе по газу.
- **D_min / D_max** (4.5: `d_min_*` — база, `d_*` — пик; 2025.12: `d_*` — база, `d_max_*` — пик; плюс `d_max_gain`, `d_max_advance`): D низкий в спокойном полёте (меньше шума/нагрева), растёт на быстрых движениях и пропвоше по гироскопу/setpoint.
- **TPA** (`tpa_mode = D` по умолчанию в 4.5, `tpa_rate`, `tpa_breakpoint`; в 4.5+ есть и `tpa_low_*` для низкого газа): снижает D (или PD) выше точки газа — при высоком газу тяга линейнее и шум выше.
- **Thrust linearization** (`thrust_linear`) и **throttle boost**: компенсация нелинейности тяги от газа и кратковременное усиление отклика газа.
- **Air mode**: PID работает и на нулевом газу (`feature AIRMODE` или режим AIR MODE), с минимальным idle (`dshot_idle_value`; в 2025.12 — `motor_idle`) — иначе на спуске без газа аппарат неуправляем.

### Разобранный пример: откуда bounce-back
Лог: после резкой остановки стика по roll гироскоп уходит на −18% от амплитуды манёвра. Проверяем по порядку: (1) D-фильтры не слишком низкие (задержка) — `dterm_lpf1_dyn_max_hz` 150 → ок; (2) D достаточно? слайдер Damping 1.0 → 1.15 — bounce-back 18 → 11%, моторы тёплые; (3) I-relax включён (`iterm_relax = RP`) — да; (4) механика — спектр чистый. Итог: Damping 1.15, запись в таблицу решений. Если бы моторы грелись — путь был бы обратный: фильтры/механика, а не D.

{{diagram:bf-pid-terms|PID в Betaflight: P и I от ошибки, D — по гироскопу (с d_min), FF — от производной setpoint; всё складывается в pidSum.}}

## practice

{{widget:pid-sim}}


**Подготовка**

Аппаратные требования: ESC с поддержкой RPM Filtering (BLHeli_32 или Bluejay), полетный контроллер F7/H7, карта памяти SD для Blackbox (минимум 4 ГБ).

Программные требования: Betaflight Configurator 10.10+, Blackbox Explorer.

**Настройка перед тюнингом**

1. Включите RPM Filtering: во вкладке Motors включите **Bidirectional DShot** и задайте Motor poles (RPM-фильтр включится сам); `rpm_filter_q = 500` — значение по умолчанию (CLI).
2. Настройте Blackbox: выберите частоту записи 2 кГц, включите логирование gyro_scaled, pid, setpoint, motor.
3. Установите базовые параметры фильтрации:
set gyro_lpf2_static_hz = 300
set gyro_lpf2_type = PT2
set dterm_lpf2_static_hz = 150
set dterm_lpf2_type = PT2
set dyn_notch_max_hz = 600
set dyn_notch_q = 250
save

text

**Пошаговая настройка**

1. Определите стартовые значения (для рамы 5" с моторами 2207–2306):
set p_pitch = 45\nset i_pitch = 50\nset d_pitch = 25
set p_roll = 42, i_roll = 45, d_roll = 23
set p_yaw = 70, i_yaw = 50, d_yaw = 20
set d_min_roll = 20\nset d_min_pitch = 22\n# 2025.12: d_roll/d_pitch — базовый D, d_max_roll/d_max_pitch — пиковый
save

text

2. Настройка P-term: выполните резкий рывок стиком с возвратом. В Blackbox смотрите график gyro (синий) и setpoint (зелёный). Если gyro пересекает setpoint в обратную сторону (bounce-back) — P низкий, увеличьте на 10. Если gyro колеблется вокруг setpoint — P высокий, уменьшите на 5.

3. Настройка D-term: после настройки P выполните то же движение. Добавьте график D-term. Если D-term дрожит высокочастотным шумом — снизьте D на 3–5. Если после движения gyro идёт с затухающими колебаниями — увеличьте D на 3.

4. Настройка I-term: зависните в режиме Angle/Horizon, слегка наклоните дрон и верните в ноль. Если дрон медленно дрейфует — увеличьте I на 10. Если проходит нейтраль и раскачивается — уменьшите I на 10.

5. Настройка Feedforward: выполните серию быстрых движений стиком. В Blackbox сравните setpoint и gyro. При большом отставании увеличьте `feedforward_boost`. При overshoot уменьшите `feedforward_boost`.

6. Настройка TPA: выполните punch-out (20% → 80% газа). Если motor выходит на 100% без снижения — проверьте `tpa_rate`. При высокочастотной пульсации увеличьте `tpa_rate` (проценты, 0–100; дефолт 65) до 70–80, снизьте `tpa_breakpoint` до 1400.

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
- Что проверить/сделать: уменьшить I на 15–20%. Проверить `iterm_limit` (дефолт 400; в 2025.12 — `iterm_windup`).

- **Симптом: Перегрев моторов**
- Возможная причина: высокий D-term, недостаточная фильтрация D-term.
- Что проверить/сделать: в Blackbox посмотреть график D-term — если похож на шум, снизить D на 20–30%. Снизить `dterm_lpf2_static_hz` до 100–120 Гц.

- **Симптом: Дрон уходит при резком добавлении газа (punch-out)**
- Возможная причина: неверная настройка TPA, высокий P/D без аттенюации.
- Что проверить/сделать: в Blackbox на графике throttle найти punch-out. Если PID sum клиппирует — увеличить `tpa_rate` или снизить `tpa_breakpoint`.

- **Симптом: Шум на гироскопе в логах (пилообразный график)**
- Возможная причина: механические вибрации, неработающий RPM Filtering.
- Что проверить/сделать: проверить работу RPM Filtering (во вкладке Motors должна отображаться частота вращения). Опустить `gyro_lpf2_static_hz` до 250–300 Гц.
- **Симптом:** после удара по газу аппарат «клюёт» носом
  - Возможная причина: I не успевает, anti-gravity мал.
  - Что сделать: `anti_gravity_gain` выше, проверить `thrust_linear`.
- **Симптом:** I-term виден в логе как рост после флипа и «довоз»
  - Возможная причина: I-term relax выключен или cutoff высок.
  - Что сделать: `iterm_relax = RP`, cutoff 10–15.

## references

- Betaflight PID Tuning Guide | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A
- Betaflight DShot RPM Filtering | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- Betaflight Blackbox logging and usage | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Oscar Liang: Betaflight PID Tuning | https://oscarliang.com/betaflight-pid-tuning/ | secondary | B
- Joshua Bardwell: How to Tune PID with Blackbox | https://www.youtube.com/watch?v=YXpPajW9lCU | secondary | B