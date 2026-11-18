---
id: bf-features-tour
title: "Остальные режимы и функции Betaflight: turtle, launch control, 3D, acro trainer, Angle/Horizon, dynamic idle, camera control"
level: L2
readingTime: 55 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5); лабораторная снята на исходниках 4.5.6
status: published
added: 2026-11-15
tags:
  - Betaflight
  - режимы
  - turtle mode
  - dynamic idle
  - Angle
  - Horizon
  - launch control
  - 3D
related:
  - bf-modes-osd
  - bf-arming-safety
  - bf-pid-reg-in-bf
  - bf-pid
  - bf-rpm-filter
  - bf-rates-rc
  - f-esc-firmware
  - bf-setup-scratch
  - bf-adjustments
  - bf-ports
  - bf-cli
next:
  - bf-blackbox
---

## summary
Справочник по режимам и функциям Betaflight 2025.12 за пределами базовой настройки: turtle mode, launch control, 3D, acro trainer, Angle и Horizon (редакция 4.5, в 2025.12 та же), dynamic idle и `MOTOR_STOP`, camera control, PARALYZE и USER1–4. Для каждой функции: что делает код (файл и функция), переменные с умолчаниями и диапазонами, когда включать, ловушки. Есть таблица всех режимов с `permanentId` для `aux` и сводная таблица `set`-переменных. Лабораторная на Python повторяет математику прошивки: закон Angle и сила Horizon, регулятор dynamic idle на синтетических оборотах, выходы моторов в turtle. На железе: turtle на траве, launch control на земле, 3D сначала без пропов.

## theory
### Режимы: таблица `permanentId` для `aux`
Формат `aux` (`cli/cli.c`, одинаков в 4.5 и 2025.12): `aux <слот 0–19> <permanentId> <AUX-канал, 0 = AUX1> <начало> <конец> <логика 0 OR / 1 AND> <связанный режим>`. Второе поле берётся из `msp/msp_box.c`, не из `rc_modes.h`. Вкладка Modes показывает только режимы, разрешённые `initActiveBoxIds()`: нет режима — не выполнено условие из правой колонки.

| id | Режим | Что делает | Когда виден |
|---|---|---|---|
| 0 / 1 / 2 | ARM / ANGLE / HORIZON | арм; самовыравнивание; смешанный режим (ниже) | ARM всегда; ANGLE и HORIZON при акселерометре |
| 4 | ANTI GRAVITY | включает anti-gravity тумблером | только если `feature ANTI_GRAVITY` выключена (по умолчанию она включена) |
| 5 / 6 / 7 | MAG / HEADFREE / HEADADJ | удержание курса; управление относительно пилота; новый «нос» для headfree | MAG при компасе; 6 и 7 при акселерометре |
| 8 | CAMSTAB | стабилизация сервоподвеса | `feature SERVO_TILT` |
| 12 | PASSTHRU | ручное управление сервами | только самолётные миксеры |
| 13 / 52 | BEEPER / BEEPER MUTE | включить пищалку (поиск в траве) / заглушить её | всегда |
| 15 | LEDLOW | гасит LED-ленту (`ledStripDisable()`) | `feature LED_STRIP` |
| 17 | CALIB | калибровка акселерометра в полёте | `feature INFLIGHT_ACC_CAL` |
| 19 | OSD DISABLE | прячет OSD | всегда |
| 20 | TELEMETRY | телеметрия работает только при включённом тумблере | `feature TELEMETRY` |
| 23–25 | SERVO1–3 | сервовыходы самолёта | `mixer CUSTOMAIRPLANE` |
| 26 / 31 | BLACKBOX / BLACKBOX ERASE | лог только по тумблеру / стирание флеш | всегда; 31 при бортовой флеш |
| 27 | FAILSAFE | тест failsafe тумблером | всегда |
| 28 | AIR MODE | airmode тумблером | только если `feature AIRMODE` выключена |
| 29 | 3D DISABLE (в 4.5 — «3D DISABLE / SWITCH») | 3D: отключить реверс или реверс на тумблере (ниже) | `feature 3D` |
| 30 | FPV ANGLE MIX | смешивание рыскания и крена под наклон камеры `fpv_mix_degrees` | при акселерометре |
| 32–34 | CAMERA CONTROL 1–3 | кнопки камеры по RunCam Device Protocol (ниже) | всегда (`USE_RCDEVICE`) |
| 35 | FLIP OVER AFTER CRASH | turtle mode | только если выбран DShot |
| 36 | PREARM | второй ключ арма (bf-arming-safety) | всегда |
| 37 | GPS BEEP SATELLITE COUNT | пищалка считает спутники | `feature GPS` |
| 39 / 48 | VTX PIT MODE / VTX CONTROL DISABLE | пит-режим VTX / запрет менять VTX из OSD | при поддержке VTX в сборке |
| 40–43 | USER1–4 | переключают пины PINIO (питание VTX, камеры, BT-модуля) | только если `pinio_box` ссылается на 40–43 |
| 44 | PID AUDIO | звук состояния PID | только в сборках с `USE_PID_AUDIO` |
| 45 | PARALYZE | «парализовать» аппарат до перезагрузки (ниже) | всегда |
| 46 | GPS RESCUE | возврат домой (bf-failsafe) | `feature GPS`, не 3D, не самолёт |
| 47 | ACRO TRAINER | ограничение угла в ACRO (ниже) | акселерометр и опция сборки ACRO_TRAINER |
| 49 | LAUNCH CONTROL | старт с упора (ниже) | всегда (`USE_LAUNCH_CONTROL` в стандартных сборках) |
| 50 | MSP OVERRIDE | подмена каналов по MSP | `msp_override_channels_mask` ≠ 0 |
| 51 | STICK COMMANDS DISABLE | запрет стик-команд (арм стиками, сохранение, меню камеры) | всегда |
| 53 | READY | надпись READY в OSD до арма (для гонок) | всегда |
| 54 | LAP TIMER RESET | сброс GPS-таймера круга | сборки с `USE_GPS_LAP_TIMER` |

Номера 0–54 в 4.5 и 2025.12 одни и те же. В 2025.12 добавлены id 3 ALTHOLD (удержание высоты), id 11 POS HOLD (удержание позиции по GPS) и id 55 CHIRP (генератор чирпа, `ctl-sysid`) — каждый виден только с соответствующей опцией сборки; в 4.5 этих номеров нет. Включённые ALTHOLD и POS HOLD запрещают арм (флаги `ALT_HOLD_SW`, `POS_HOLD_SW`). USER1–4 стоят на 40–43, имя задаётся через `box_user_N_name` (до 16 символов, есть и в 4.5).

**PARALYZE (45)** — «липкий» режим (`fc/rc_modes.c`). Он взводится, только если тумблер хоть раз был выключен позже 5 с от старта (`STICKY_MODE_BOOT_DELAY_US`): включённый на старте тумблер ничего не делает. После срабатывания флаг `PARALYZE` запрещает арм, а без арма отключены стик-команды, подстройки и меню OSD. Снимается только перезагрузкой. В воздухе не дизармит. Назначение — гонки: разбитый аппарат не заармят случайно, пока несут с трассы.

**USER1–4 и PINIO.** Пин PINIO на многих платах коммутирует питание VTX или камеры. Связка: `set pinio_box = 40,255,255,255` (PINIO1 следует за USER1, 255 — не назначено), затем `aux` с id 40. `pinio_config` (1 — выход, +128 — инверсия) задан в target платы.

### Turtle mode (FLIP OVER AFTER CRASH)
Аппарат на спине, моторы крутятся назад, стик выбирает, какая сторона толкает. Код 2025.12: `tryArm()` и `updateArmingStatus()` в `fc/core.c`, `applyCrashFlipModeToMotors()` в `flight/mixer.c` (в 4.5 — `applyFlipOverAfterCrashModeToMotors()`; алгоритм там другой, он разобран в шаге 3 практики).

- **Требования.** Режим виден только при DShot. При арме с режимом FC шлёт всем ESC DShot-команду 21 `SPIN_DIRECTION_REVERSED`, при дизарме — 20 `SPIN_DIRECTION_NORMAL`: прошивка ESC должна их выполнять (Bluejay, BLHeli_32, AM32 — проверь на столе). Двунаправленный DShot не нужен. При `feature 3D` команды не шлются, миксер просто берёт обратную половину диапазона.
- **Вход.** Сначала тумблер turtle, потом ARM. Флаги `ANGLE` и `GPS` при включённом режиме не ставятся. OSD: до арма `CRASHFLIP SW`, после — `>CRASH FLIP<` (в 4.5 — `CRASH FLIP SWITCH` и `> CRASH FLIP <`), пищалка пищит.
- **Выход.** Дизарм, turtle выкл., снова ARM — это работает в любой версии. В 2025.12 можно и выключить тумблер turtle, не трогая ARM: при `crashflip_auto_rearm = OFF` (умолчание) FC дизармится сам и ставит флаг `FLIP_SWITCH`, который снимается только ручным дизармом (опустить ARM), после чего армишься заново; при `crashflip_auto_rearm = ON` аппарат остаётся в арме, моторы переключаются на нормальное вращение — пропы закрутятся вперёд сразу, руки и лицо убери заранее. В 4.5 выключенный при арме тумблер ничего не меняет: состояние сбрасывается только дизармом. С забытым тумблером аппарат после арма крутит моторы назад и не взлетит.
- **Стик.** Крен — пара моторов одной стороны, тангаж — передняя или задняя пара, диагональ (до 30° от биссектрисы) — один мотор, доминирует рыскание — диагональная пара. Моторы «другой стороны» стоят или крутятся на `crashflip_motor_percent`. Мёртвая зона стика 15 %; выше неё мощность в 2025.12 равна отклонению стика (линейно, без кривой), выход меньше 2 % диапазона — стоп. В 4.5 была кривая `crashflip_expo` (35): x' = (1 − e)·x + e·x³, e = expo/100, и стоп ниже «минимум + 20» DShot; в 2025.12 `crashflip_expo` удалён.
- **Автоостановка (`crashflip_rate`, с 2025.12).** 0 (умолчание) — выключено, моторы тянут, пока держишь стик. При значении больше 0 мощность снижается двумя множителями: по скорости вращения (без ослабления до половины порога `crashflip_rate` × 10 °/с, дальше линейно до нуля на пороге) и, если есть акселерометр, по пройденному углу (ноль после поворота примерно на 90° от исходного положения). Аппарат перестаёт толкать, когда уже переворачивается. В сборке RACE_PRO умолчания другие: `crashflip_rate = 30`, `crashflip_auto_rearm = ON`.
- **Почему греются моторы.** В turtle `motorRangeMax = motorOutputHigh`: полный стик — полный газ (2047; в 4.5 — 2027 из-за вычитаемой мёртвой зоны). Проп упирается в траву, ротор почти стоит, противо-ЭДС нет, ток ограничен сопротивлением обмотки. Таймера нет ни в 4.5, ни в 2025.12 (при `crashflip_rate = 0`). Правило: толчки по 0.5–1 с; не перевернулся за 3 попытки — иди пешком.
- Runaway takeoff в turtle не проверяется, а арм в turtle снова включает защиту для следующего взлёта.

Перенос настроек с 4.5: строку `set crashflip_expo = …` из старого `diff` 2025.12 не примет (`INVALID NAME`); `crashflip_motor_percent` переносится как есть.

### Launch control
Гоночный старт: аппарат стоит на батарее или стенде, наклонён вперёд и держит угол до газа. Код: `canUseLaunchControl()` и `processRx()` в `fc/core.c`, `applyLaunchControl()` в `flight/pid.c`.

- **Условия.** Режим 49 включён **в момент арма**, арм тумблером, режим ACRO, нет `feature 3D`, а при `MOTOR_STOP` — ещё и airmode. Пока launch активен, airmode считается включённым.
- **Что делает PID.** Стик задаёт скорость 100 °/с·2·x при ходе, ограниченном ±50 % (в `NORMAL` и `FULL` — по всем трём осям, в `PITCHONLY` — только тангаж): 100 °/с достигается на половине хода и не зависит от твоих рейтов. Поставил угол — отпустил стик, I держит позицию с собственным коэффициентом `launch_control_gain` (40). D и feedforward отключены. `NORMAL`: рыскание без удержания (I по рысканию обнуляется). `FULL`: рыскание тоже удерживается, I по рысканию ограничен ±50. `PITCHONLY`: работают только P и I тангажа, I не уходит в минус, а передние моторы в миксере зажаты на минимуме, чтобы аппарат не сполз со стенда.
- **Старт.** Газ выше `launch_trigger_throttle_percent` (20 %) — I сбрасывается, launch окончен, аппарат летит в обычном ACRO. `launch_angle_limit` > 0 (нужен акселерометр) запрещает наклон вперёд больше заданного. За 10° до предела скорость наклона плавно падает до 5 °/с.
- **Повтор.** `launch_trigger_allow_reset = ON` — после дизарма переключи тумблер режима; `OFF` — только перезагрузка. До старта арм и дизарм можно повторять. OSD: `LAUNCH 25` (тангаж), мигает за 10 % до порога.

По умолчанию `launch_control_mode = PITCHONLY` (в 4.5 умолчание было `NORMAL`); остальная логика launch control в 2025.12 не менялась.

### 3D (реверсивные моторы)
`feature 3D`: газ в центре — ноль, вниз — тяга назад, вверх — вперёд. Это **не** двунаправленный DShot из bf-rpm-filter: нужен ESC в режиме Bidirectional (3D) (f-esc-firmware). Betaflight сам ESC не переключает: это делают в конфигураторе ESC или `dshotprog 255 10 12` (3D_MODE_ON + сохранение), если прошивка ESC это поддерживает.

- **DShot.** Разделение задаёт протокол (`drivers/dshot.c`): 48–1047 — назад, 1048–2047 — вперёд, 0 — стоп. `3d_deadband_low/high`, `3d_neutral`, `3d_limit_low/high` при DShot **не используются**: это конечные точки для PWM/OneShot (`analogInitEndpoints()` в `drivers/motor.c`). Холостой ход `motor_idle` (до 2025.12 — `dshot_idle_value`) действует в обе стороны.
- **Стик.** `3d_deadband_throttle` (50 мкс) — мёртвая зона вокруг `mid_rc` и «газ внизу» для арма: арм только при 1451–1549 мкс. В зоне миксер держит направление, с которого стик вошёл. После смены направления I обнуляется на 250 мс. Дизарм тумблером — мгновенно (`processRx`).
- **Режим 29.** `3d_switched_mode = OFF`: режим отключает реверс, весь ход стика — вперёд. `ON`: тумблер выбирает направление, ход стика — от нуля до полного газа в эту сторону.
- **Что отключается:** dynamic idle (его код в ветке «не 3D»), `MOTOR_STOP`, launch control, GPS Rescue, команды turtle.

### Acro trainer
ACRO с ограничением крена и тангажа углом `acro_trainer_angle_limit` (20°), `applyAcroTrainer()` в `flight/pid.c`. Не действует в ANGLE, HORIZON и GPS Rescue. Нужен акселерометр и опция сборки ACRO_TRAINER в Cloud Build: без неё нет режима 47, а `set acro_trainer_*` даёт `INVALID NAME`. Угол за пределом и стик тянет дальше — уставка = (предел − угол)·`acro_trainer_gain`/10 (не больше ±1000 °/с), I обнуляется. До предела угол прогнозируется на `acro_trainer_lookahead_ms` (50 мс), окно пропорционально гиро до 500 °/с, и при выходе прогноза за предел уставка тормозит заранее. Стик в обратную сторону снимает ограничение. Флип невозможен по построению.

### Angle и Horizon (редакция 4.5, действует и в 2025.12)
Код `pidLevel()` и `calcHorizonLevelStrength()` в `flight/pid.c`, коэффициенты в `flight/pid_init.c`. Закон Angle:

- Цель = `angle_limit` · setpoint / max_rate, где setpoint — уставка ACRO по твоим рейтам, max_rate — скорость на полном стике. **Форма рейтов задаёт форму Angle:** при умолчаниях (Actual 7/67/0) полстика — 185 из 670 °/с, то есть 16.6°, а не 30° (шаг 1 практики).
- Скорость = (цель − угол) · `angle_p_gain`/10: 5 °/с на градус при 50. Плюс `angle_feedforward` (50) от движения стика, сглаженный PT3 (`angle_feedforward_smoothing_ms` 80 мс ≈ 2 Гц). Сумма проходит PT3 50 Гц и становится уставкой контура скорости.
- `angle_earth_ref` (100): рыскание в Angle умножается на cos(угла цели), часть переносится в крен и тангаж — разворот вокруг вертикали Земли. 0 — старое поведение.
- `level_race_mode = ON` (по умолчанию OFF) — Angle только по крену, тангаж в ACRO (гоночный «NFE»-режим).

Horizon: уставка = acro·(1 − s) + angle·s, где s = `horizon_level_strength`/100 · (1 − наклон/`horizon_limit_degrees`) · (1 − стик/`horizon_limit_sticks`), множители не меньше 0, наклон — больший из |крен|, |тангаж|. При 75/135/75: горизонт и стик в центре — s = 0.75; стик 75 % или наклон ≥ 135° — s = 0, чистый ACRO, поэтому флип проходит без «борьбы» на спине. Рост s сглажен PT1 `horizon_delay_ms` (500 мс), спад мгновенный. `horizon_ignore_sticks = ON` убирает зависимость от стика.

{{diagram:chart-bf-horizon-strength|В Horizon (4.5 и 2025.12) выравнивание линейно гаснет к наклону 135° и к 75 % хода стика: на полстика у горизонта остаётся только треть силы (0.25 из 0.75), а вверх ногами аппарат летит как в ACRO.}}

Переименования 4.4 → 4.5: `level_limit` (55, до 90) → `angle_limit` (60; до 85 в 4.5, до 80 в 2025.12); `angle_level_strength` → `angle_p_gain`; `horizon_transition` → `horizon_limit_sticks`; `horizon_tilt_effect` и `horizon_tilt_expert_mode` → `horizon_limit_degrees`; `roll_level_expo`/`pitch_level_expo` удалены, их роль играют рейты. Старый `diff all` из 4.4 эти строки не применит. В 2025.12 добавлен `angle_pitch_offset` (только в сборке WING), а в режиме POS HOLD угол, запрошенный стиком, ограничен половиной `ap_max_angle`.

Ещё одна функция из этой группы (появилась в 4.5) — EZ landing: при `mixer_type = EZLANDING` миксер ограничивает «подъём газа ради PID» (то, что делает airmode) при малом газе, стиках у центра и малой скорости по GPS. Пороги — `ez_landing_threshold/limit/speed` (25/15/50). Аппарат меньше подпрыгивает при посадке. Без этого типа миксера переменные ничего не делают.

### Dynamic idle и MOTOR_STOP
Без dynamic idle нижний предел мотора — `motor_idle` (550 = 5.5 % диапазона DShot; до 2025.12 — `dshot_idle_value`), обороты не контролируются: в плоском падении поток снизу тормозит пропы до порога desync. Dynamic idle (`calculateThrottleAndCurrentMotorEndpoints()` в `mixer.c`) читает обороты самого медленного мотора по двунаправленному DShot и регулятором PID поднимает **нижнюю границу всех моторов**:

- цель: `dyn_idle_min_rpm` × 100 об/мин (30 → 3000 об/мин = 50 об/с), по умолчанию 0 — выключено;
- P = ошибка (об/с) · `dyn_idle_p_gain` · 0.00015, I = Σ ошибка · `dyn_idle_i_gain` · 0.01 · dT (вниз I спускается медленно: ошибка ограничена −0.1 об/с), D — от сглаженных (~20 мс) оборотов с коэффициентом `dyn_idle_d_gain` · 3·10⁻⁷ · f_PID;
- прибавка ограничена `dyn_idle_max_increase` (150 = 15 %) после первого подъёма газа выше порога airmode, а до него, то есть на земле, — значением `motor_idle` (550 = 5.5 %). В 4.5 предел на земле задавала отдельная переменная `dyn_idle_start_increase` (50 = 5 %), в 2025.12 её нет;
- при включённом dynamic idle `motor_idle` как пол **не действует**: нижняя граница становится 48 (0 %) плюс прибавка, а газ не опускается ниже 1 %. В 2025.12 `motor_idle` при этом остаётся пределом прибавки на земле (пункт выше), в 4.5 `dshot_idle_value` игнорировался полностью;
- нужны `dshot_bidir = ON` и `motor_poles`. Без телеметрии `mixerInitProfile()` молча обнуляет цель: ошибки нет, функции тоже нет. В 3D функция не работает;
- все `dyn_idle_*` хранятся в профиле PID: в другом профиле может быть 0.

Документация советует 30–40 для 5″. Перед включением dynamic idle на вупах сначала подбери `motor_idle` так, чтобы моторы уверенно стартовали (комментарий в `mixer_init.c` 2025.12).

{{diagram:chart-bf-dyn-idle|Регулятор из mixer.c на синтетическом моторе: со статическим idle 5.5 % самый медленный мотор в плоском падении проседает до 2100 об/мин, dynamic idle добавляет 6.3 % тяги и держит 3000; на земле тот же регулятор опускает холостой ход с 6100 до 3000 об/мин.}}

**`feature MOTOR_STOP`**: моторы стоят при газе ниже `min_check`, но только без airmode, без 3D и вне GPS Rescue (`mixTable()`). Airmode включён по умолчанию, так что у большинства `MOTOR_STOP` ничего не делает. С ним связан `auto_disarm_delay` (bf-arming-safety). В полёте остановленный мотор стартует с задержкой — для фристайла и гонок это вред.

### Anti-gravity и I-term relax — коротко
**Anti-gravity** (`anti_gravity_gain` 80, 0–250; `anti_gravity_cutoff_hz` 5, 2–50; `anti_gravity_p_gain` 100, 0–250; `feature ANTI_GRAVITY` включена). Производная газа фильтруется PT2 с акцентом на нижнюю часть хода и временно ускоряет накопление I на крене и тангаже, плюс даёт прибавку к P при стиках у центра. Это против клевка носом при резком ударе газом. Настройка и логи — в bf-pid-reg-in-bf.

**I-term relax** (`iterm_relax = RP`, `iterm_relax_type = SETPOINT`, `iterm_relax_cutoff = 15`, 1–50). При быстром движении стика накопление I приостанавливается, чтобы после флипа I не «довёз» лишний угол (bounce-back). Отключается в launch control и crash recovery. Подробно — в bf-pid-reg-in-bf и bf-pid.

### Camera control: меню камеры с пульта
**RunCam Device Protocol** (`io/rcdevice*.c`, всегда в сборке). Камера (RunCam Split, Micro Swift 3, Racer 2, часть Caddx) на UART TX+RX, функция порта RunCam Device (бит 16384). При старте FC опрашивает её `rcdevice_init_dev_attempts` = 6 раз через 1000 мс. Режимы 32–34 срабатывают по фронту тумблера: 1 — кнопка Wi-Fi (без арма), 2 — питание или запись (и в полёте), 3 — смена режима (без арма). Меню камеры — стиками без арма (`rcdevice_cam.c`): газ 1350–1650, крен и тангаж в центре, рыскание > 1920 — вход; в меню крен и тангаж за 1080/1920 — стрелки, рыскание вправо — Enter, влево — выход. Меню Betaflight (CMS) — другой жест: рыскание влево + тангаж вверх.

**Эмуляция джойстика** (`drivers/*/camera_control.c`) — для камер с одним проводом OSD и резистивной клавиатурой (HS1177 и родственные). Опция сборки CAMERA_CONTROL, `resource CAMERA_CONTROL <пин с таймером>`, резистор 150–600 Ом в разрыв. Нажатие имитируется напряжением U = U_ref · R_кн / (R_вн + R_кн): `camera_control_ref_voltage` 330 (3.3 В), `camera_control_internal_resistance` 470 (47 кОм), `camera_control_button_resistance` 450,270,150,68,0 (×100 Ом: Enter, Left, Up, Right, Down), нажатие `camera_control_key_delay` 180 мс. Стики без арма (`rc_controls.c`): газ в середине + рыскание вправо — Enter, крен и тангаж — стрелки, газ вниз + тангаж вверх — «Up» на 2 с.

### Справочник параметров (2025.12)
| Параметр | По умолчанию | Диапазон | Смысл |
|---|---|---|---|
| `crashflip_motor_percent` | 0 | 0–100 % | доля для моторов «другой стороны» в turtle |
| `crashflip_rate` | 0 | 0–250 (×10 °/с) | автоостановка turtle по скорости и углу, 0 — выкл. (с 2025.12; в 4.5 на этом месте `crashflip_expo` 35, 0–100 — кривая стика) |
| `crashflip_auto_rearm` | OFF | OFF/ON | при выключении тумблера turtle остаться в арме (с 2025.12) |
| `launch_control_mode` | PITCHONLY | NORMAL / PITCHONLY / FULL | что удерживается (в 4.5 умолчание NORMAL) |
| `launch_trigger_throttle_percent` | 20 | 0–90 % | газ старта |
| `launch_angle_limit` | 0 | 0–80° | предел наклона вперёд (0 — нет) |
| `launch_control_gain` | 40 | 0–200 | I удержания позиции |
| `launch_trigger_allow_reset` | ON | OFF/ON | повтор через тумблер |
| `3d_deadband_throttle` | 50 | 1–100 мкс | мёртвая зона стика вокруг `mid_rc` |
| `3d_deadband_low` / `_high`, `3d_neutral`, `3d_limit_low` / `_high` | 1406 / 1514, 1460, 1000 / 2000 | 750–1500 / 1500–2250, 750–2250, 750–1500 / 1500–2250 | только PWM: границы реверса, импульс в дизарме, крайние импульсы |
| `3d_switched_mode` | OFF | OFF/ON | режим 29 выбирает направление |
| `acro_trainer_angle_limit` | 20 | 10–80° | предел угла |
| `acro_trainer_lookahead_ms` / `_gain` | 50 / 75 | 10–200 мс / 25–255 | прогноз; жёсткость (/10) |
| `acro_trainer_debug_axis` | ROLL | ROLL/PITCH | ось для debug |
| `angle_limit` | 60 | 10–80° | угол на полном стике (в 4.5 — до 85°) |
| `angle_p_gain` | 50 | 0–200 | °/с на градус ошибки ×10 |
| `angle_feedforward` / `_smoothing_ms` | 50 / 80 | 0–200 / 10–250 мс | FF от стика и его сглаживание |
| `angle_earth_ref` | 100 | 0–100 % | разворот в Angle относительно Земли |
| `horizon_level_strength` | 75 | 0–100 | сила выравнивания у горизонта |
| `horizon_limit_sticks` | 75 | 10–200 % | стик, на котором выравнивание = 0 |
| `horizon_limit_degrees` | 135 | 10–250° | наклон, на котором выравнивание = 0 |
| `horizon_ignore_sticks` | OFF | OFF/ON | не ослаблять по стику |
| `horizon_delay_ms` | 500 | 10–5000 мс | плавность нарастания выравнивания |
| `level_race_mode` | OFF | OFF/ON | Angle только по крену |
| `ez_landing_threshold` / `_limit` / `_speed` | 25 / 15 / 50 | 0–200 / 0–75 / 0–250 | EZ landing (`mixer_type = EZLANDING`) |
| `dyn_idle_min_rpm` | 0 | 0–200 (×100 об/мин) | цель dynamic idle, 0 = выкл |
| `dyn_idle_p_gain` / `_i_gain` / `_d_gain` | 50 / 50 / 50 | 1–250 / 1–250 / 0–250 | коэффициенты регулятора |
| `dyn_idle_max_increase` | 150 | 10–255 (×0.1 %) | предел прибавки после airmode |
| `motor_idle` | 550 | 0–2000 (×0.01 %) | статический idle (до 2025.12 — `dshot_idle_value`); при dynamic idle — предел прибавки на земле |
| `dyn_idle_start_increase` | — | — | только 4.5: 50, 10–255 (×0.1 %), предел прибавки до airmode; в 2025.12 удалён |
| `anti_gravity_gain` / `_cutoff_hz` / `_p_gain` | 80 / 5 / 100 | 0–250 / 2–50 / 0–250 | anti-gravity |
| `iterm_relax` / `_type` / `_cutoff` | RP / SETPOINT / 15 | OFF…RPY_INC / GYRO, SETPOINT / 1–50 | I-term relax |
| `camera_control_mode` | HARDWARE_PWM | HARDWARE_PWM / SOFTWARE_PWM / DAC | способ эмуляции (SOFTWARE_PWM — с конденсатором) |
| `camera_control_ref_voltage` / `_key_delay` | 330 / 180 | 200–400 (×10 мВ) / 100–500 мс | напряжение пина OSD; нажатие |
| `camera_control_internal_resistance` / `_button_resistance` | 470 / 450,270,150,68,0 | 10–1000 / массив (×100 Ом) | резистор камеры; кнопки Enter…Down |
| `camera_control_inverted` | OFF | OFF/ON | инверсия выхода |
| `rcdevice_init_dev_attempts` / `rcdevice_init_dev_attempt_interval` | 6 / 1000 | 0–10 / 0–5000 мс | опрос камеры при старте |
| `rcdevice_protocol_version` / `rcdevice_feature` | 0 / 0 | 0–1 / 0–65535 | версия протокола, маска функций |
| `pinio_box` | 255,255,255,255 | `permanentId` | какой режим ведёт PINIO1–4 |
| `box_user_1_name` … `_4_name` | пусто | до 16 символов | имена USER1–4 |

Функции: `feature 3D`, `feature MOTOR_STOP`, `feature ANTI_GRAVITY` (вкл.), `feature AIRMODE` (вкл.).

### Место в системе

- **Получает:** `permanentId` и диапазоны AUX (`bf-modes-osd`); обороты самого медленного мотора по двунаправленному DShot для dynamic idle (`bf-rpm-filter`); форму рейтов — она задаёт форму Angle (`bf-rates-rc`); DShot-команды разворота моторов, которые должна выполнять прошивка ESC (`f-esc-firmware`).
- **Отдаёт:** режимы, меняющие уставку и нижнюю границу моторов для PID и миксера (`bf-pid-reg-in-bf`); флаги `PARALYZE`, `FLIP_SWITCH` и запрет арма при включённых ALTHOLD и POS HOLD (`bf-arming-safety`).
- **Если ошибиться здесь:** включил dynamic idle без `dshot_bidir` → цель молча обнуляется: ошибки нет, функции тоже; проверяется телеметрией — `dshot_telemetry_info` (`bf-cli`), настройка bidir — в `bf-rpm-filter`. Забыл тумблер turtle включённым → после арма моторы крутятся назад, аппарат не взлетает; похоже на ошибку направления моторов из `bf-setup-scratch`.

## practice
Основной путь — Python, повторяющий математику прошивки построчно: те же формулы, константы и умолчания 4.5 (SITL Betaflight здесь не собирается). Что из этого действительно для 2025.12: шаг 1 (Angle, Horizon) — формулы не изменились в 2025.12; шаг 2 (dynamic idle) — регулятор тот же, но предел до взлёта там `motor_idle` (5.5 %), а не `dyn_idle_start_increase` (5 %); шаг 3 (turtle) — алгоритм 4.5, в 2025.12 он заменён (кривой `crashflip_expo` и вычитания 20 единиц DShot нет). Модели аппарата и мотора — учебные заглушки, так и помечены. Три блока ниже склеиваются в один файл `lab.py`.

### Шаг 1. Закон Angle и сила Horizon из `pidLevel()`
Цель: увидеть, что рейты меняют Angle, что `angle_p_gain` — это постоянная времени, и как Horizon 4.5 смешивает ACRO и Angle.

```python
# bf-features-tour lab: Betaflight 4.5 maths reproduced from the source (4.5-maintenance, 4.5.6).
# Part 1: Angle/Horizon setpoint law (flight/pid.c pidLevel, calcHorizonLevelStrength; flight/pid_init.c gains).
import math

def pt1_gain(f, dt):                      # common/filter.c pt1FilterGain
    w = 2 * math.pi * f * dt
    return w / (w + 1)

def pt3_gain(f, dt):                      # pt3FilterGain: cutoff shifted by CUTOFF_CORRECTION_PT3
    return pt1_gain(f * 1.961459177, dt)

RC_RATE, SRATE, EXPO = 7, 67, 0           # 4.5 default rates: Actual, roll_rc_rate 7, roll_srate 67, roll_expo 0

def actual_rate(x, rc=RC_RATE, sr=SRATE, ex=EXPO):   # fc/rc.c applyActualRates
    e = ex / 100
    expof = abs(x) * (x ** 5 * e + x * (1 - e))
    centre = rc * 10
    return x * centre + max(0, sr * 10 - centre) * expof

ANGLE_LIMIT, ANGLE_P = 60, 50             # angle_limit, angle_p_gain (pid[PID_LEVEL].P)
def angle_target(x, rc=RC_RATE, sr=SRATE):           # pidLevel: angleLimit * setpoint / maxRcRate
    return ANGLE_LIMIT * actual_rate(x, rc, sr) / actual_rate(1.0, rc, sr)

print("Part 1a. Angle target vs stick (angle_limit 60)")
print(" stick | setpoint 7/67 | target 4.5 defaults | target if rc_rate = srate (linear) | 4.4 level_limit 55 * stick")
for x in (0.1, 0.25, 0.5, 0.75, 1.0):
    print(f"  {x:4.2f} | {actual_rate(x):6.1f} deg/s  | {angle_target(x):6.1f} deg          |"
          f" {angle_target(x, 67, 67):6.1f} deg                          | {55 * x:5.1f} deg")

def angle_step(stick, p_gain=ANGLE_P, T=1.0, dt=125e-6, tau_rate=0.030):
    """Roll axis, stick step at t = 0. angleRate = (target - angle) * P/10 -> PT3 50 Hz (ATTITUDE_CUTOFF_HZ)
    -> rate setpoint. Inner rate loop: synthetic first-order lag tau_rate (stand-in for the rate PID + quad)."""
    k = pt3_gain(50, dt); s1 = s2 = s3 = 0.0
    gain = p_gain / 10.0                  # pid_init.c: angleGain = pid[PID_LEVEL].P / 10
    target = angle_target(stick)
    angle = rate = 0.0; t = 0.0; t63 = t90 = None; peak = 0.0; peak_rate = 0.0
    while t < T:
        cmd = (target - angle) * gain     # deg/s per deg of error
        s1 += k * (cmd - s1); s2 += k * (s1 - s2); s3 += k * (s2 - s3)
        rate += (s3 - rate) * dt / tau_rate
        angle += rate * dt; t += dt
        peak = max(peak, angle); peak_rate = max(peak_rate, rate)
        if t63 is None and angle >= 0.632 * target: t63 = t
        if t90 is None and angle >= 0.9 * target: t90 = t
    return target, t63, t90, peak, peak_rate

print("\nPart 1b. Step response: stick 0 -> 50 %, inner rate loop tau 30 ms (synthetic)")
for p in (25, 50, 100):
    tg, t63, t90, pk, pr = angle_step(0.5, p)
    print(f"  angle_p_gain {p:3d}: target {tg:5.1f} deg, 63 % at {t63*1e3:4.0f} ms, 90 % at {t90*1e3:4.0f} ms,"
          f" overshoot {max(0, pk - tg):4.1f} deg, peak rate {pr:5.0f} deg/s")

def horizon_strength(incl_deg, stick, level=75, lim_sticks=75, lim_deg=135, ignore_sticks=False):
    """calcHorizonLevelStrength (steady state, horizon_delay_ms PT1 not applied)."""
    s = max((lim_deg - incl_deg) / lim_deg, 0.0)
    ls = lim_sticks / 100
    s *= max((ls - stick) / ls, 1.0 if ignore_sticks else 0.0)
    return s * min(level / 100, 1.0)

print("\nPart 1c. Horizon level strength (4.5 defaults: level 75, limit_sticks 75, limit_degrees 135)")
print(" inclination |" + "".join(f" stick {x:4.2f} |" for x in (0, 0.25, 0.5, 0.75)))
for inc in (0, 30, 60, 90, 135, 180):
    print(f"   {inc:5d} deg |" + "".join(f"    {horizon_strength(inc, x):5.3f}   |" for x in (0, 0.25, 0.5, 0.75)))

dt = 125e-6
kh = pt1_gain(1e3 / (2 * math.pi * 500), dt)   # horizon_delay_ms 500 -> PT1 at 0.318 Hz on increases
st, t = 0.0, 0.0
while True:
    st += kh * (0.75 - st); t += dt
    if st >= 0.632 * 0.75: break
print(f"  horizon_delay_ms 500: after the stick returns to centre, strength reaches 63 % of 0.75 in {t*1e3:.0f} ms")
for a in (10, 30, 45):
    print(f"  angle_earth_ref 100, angle target {a:2d} deg: yaw setpoint x {math.cos(math.radians(a)):.3f}")
```

```text
Part 1a. Angle target vs stick (angle_limit 60)
 stick | setpoint 7/67 | target 4.5 defaults | target if rc_rate = srate (linear) | 4.4 level_limit 55 * stick
  0.10 |   13.0 deg/s  |    1.2 deg          |    6.0 deg                          |   5.5 deg
  0.25 |   55.0 deg/s  |    4.9 deg          |   15.0 deg                          |  13.8 deg
  0.50 |  185.0 deg/s  |   16.6 deg          |   30.0 deg                          |  27.5 deg
  0.75 |  390.0 deg/s  |   34.9 deg          |   45.0 deg                          |  41.2 deg
  1.00 |  670.0 deg/s  |   60.0 deg          |   60.0 deg                          |  55.0 deg

Part 1b. Step response: stick 0 -> 50 %, inner rate loop tau 30 ms (synthetic)
  angle_p_gain  25: target  16.6 deg, 63 % at  401 ms, 90 % at  873 ms, overshoot  0.0 deg, peak rate    36 deg/s
  angle_p_gain  50: target  16.6 deg, 63 % at  205 ms, 90 % at  410 ms, overshoot  0.0 deg, peak rate    67 deg/s
  angle_p_gain 100: target  16.6 deg, 63 % at  112 ms, 90 % at  184 ms, overshoot  0.1 deg, peak rate   122 deg/s

Part 1c. Horizon level strength (4.5 defaults: level 75, limit_sticks 75, limit_degrees 135)
 inclination | stick 0.00 | stick 0.25 | stick 0.50 | stick 0.75 |
       0 deg |    0.750   |    0.500   |    0.250   |    0.000   |
      30 deg |    0.583   |    0.389   |    0.194   |    0.000   |
      60 deg |    0.417   |    0.278   |    0.139   |    0.000   |
      90 deg |    0.250   |    0.167   |    0.083   |    0.000   |
     135 deg |    0.000   |    0.000   |    0.000   |    0.000   |
     180 deg |    0.000   |    0.000   |    0.000   |    0.000   |
  horizon_delay_ms 500: after the stick returns to centre, strength reaches 63 % of 0.75 in 500 ms
  angle_earth_ref 100, angle target 10 deg: yaw setpoint x 0.985
  angle_earth_ref 100, angle target 30 deg: yaw setpoint x 0.866
  angle_earth_ref 100, angle target 45 deg: yaw setpoint x 0.707
```

Что видно:
- **1a.** Полный стик — те же 60°, но полстика — только 16.6°. «Мёртвый» центр в Angle — это рейты, а не `angle_p_gain`. Линейный Angle даёт `roll_rc_rate` = `roll_srate`, но это меняет и ACRO; отдельный профиль рейтов переключается через `adjrange` (bf-adjustments).
- **1b.** `angle_p_gain` 50 — постоянная времени около 1/5 с (63 % за 205 мс). Удвоение ускоряет в 1.8 раза, не в 2: мешают PT3 50 Гц и внутренний контур. Перерегулирования нет. Миллисекунды модельные, соотношения переносятся.
- **1c.** Это график из теории. На спине Horizon не выравнивает; после флипа 63 % силы набирается за 0.5 с.

### Шаг 2. Dynamic idle на синтетических оборотах
Регулятор — из `calculateThrottleAndCurrentMotorEndpoints()`, коэффициенты — из `mixerInitProfile()` (PID 8 кГц), фильтр оборотов — PT1 `rpm_filter_lpf_hz` 150 Гц (`dshot.c`). Мотор — упрощённая модель: 26000·√u об/мин (u — доля диапазона DShot), инерция 40 мс, в плоском падении поток снизу отнимает 4000 об/мин. Сценарий: 0–0.3 с арм на земле (airmode не защёлкнут), 0.3–0.8 с набор на 35 %, газ в ноль, 0.9–1.6 с плоское падение.

```python
# Part 2: dynamic idle controller (flight/mixer.c calculateThrottleAndCurrentMotorEndpoints; mixer_init.c gains)
#         on a synthetic motor (the motor model is NOT from Betaflight, it is a stand-in to close the loop).
PID_HZ = 8000; DT = 1 / PID_HZ
def dyn_idle_gains(min_rpm=30, p=50, i=50, d=50, max_inc=150, start_inc=50):   # mixer_init.c mixerInitProfile
    return dict(min_rps=min_rpm * 100 / 60, P=p * 0.00015, I=i * 0.01 * DT, D=d * 0.0000003 * PID_HZ,
                max_inc=max_inc * 0.001, start_inc=start_inc * 0.001, k_delay=800 * DT / 20)

g = dyn_idle_gains()
print("\nPart 2a. Dynamic idle gains (dyn_idle_min_rpm 30, P/I/D 50, max 150, start 50; PID 8 kHz)")
print(f"  target {g['min_rps']:.1f} rps = {g['min_rps']*60:.0f} rpm; P {g['P']:.4f} /rps; I {g['I']:.3e} /rps per loop;"
      f" D {g['D']:.3f}; limits {g['max_inc']*100:.0f} % (airmode) / {g['start_inc']*100:.0f} % (before airmode)")
for rpm in (2900, 2500, 2000, 1500, 1000):
    err = g['min_rps'] - rpm / 60
    p_term = err * g['P']
    print(f"  slowest motor {rpm:4d} rpm: error {err:5.2f} rps -> P alone {p_term*100:5.2f} % of motor range"
          f" (cap {min(p_term, g['max_inc'])*100:5.2f} %)")

RPM_MAX = 26000.0                          # synthetic motor: rpm_ss = 26000 * sqrt(u) - inflow brake
IDLE = 0.055                               # dshot_idle_value 550 = 5.5 %
def motor_rpm_ss(u, inflow):
    return max(0.0, RPM_MAX * math.sqrt(max(u, 0.0)) - inflow)

def scenario(t):                           # (mixer output of the slowest motor 0..1, inflow brake rpm, airmode latched)
    if t < 0.3: return 0.0, 0.0, False     # armed on the ground, throttle low, airmode not latched
    if t < 0.8: return 0.35, 0.0, True     # take-off and climb (airmode latches above 25 % throttle)
    if 0.9 <= t < 1.6: return 0.0, 4000.0, True   # throttle chop, flat drop: air from below slows the props
    return 0.0, 0.0, True

def run_idle(dyn, T=2.0, g=g, tau_motor=0.040, rpm_lpf_hz=150):
    k_rpm = pt1_gain(rpm_lpf_hz, DT)       # dshot.c motorFreqLpf (rpm_filter_lpf_hz 150)
    rpm = motor_rpm_ss(IDLE, 0); f_rps = rpm / 60; prev = f_rps; I = 0.0; inc = 0.0
    rows = []; t = 0.0; n = 0; lowest = 1e9
    while t < T:
        m, inflow, airmode = scenario(t)
        if dyn:
            max_inc = g['max_inc'] if airmode else g['start_inc']
            min_rps = f_rps
            err = g['min_rps'] - min_rps
            min_rps = prev + g['k_delay'] * (min_rps - prev)          # PT1 delay for D (~20 ms)
            d_term = (prev - min_rps) * g['D']; prev = min_rps
            p_term = err * g['P']
            err = max(-0.1, err)                                      # "I rises fast, falls slowly"
            I = min(max(I + err * g['I'], 0.0), max_inc)
            inc = min(max(p_term + I + d_term, 0.0), max_inc)
            low = 0.0                                                 # motorOutputLow = DSHOT_MIN_THROTTLE
            m = max(m, 0.01)                                          # throttle = MAX(throttle, 0.01)
            u = low + inc * (1 - low) + m * (1 - low - inc * (1 - low))
        else:
            u = IDLE + m * (1 - IDLE)                                 # static idle: floor = dshot_idle_value
            p_term = d_term = 0.0
        rpm += (motor_rpm_ss(u, inflow) - rpm) * DT / tau_motor
        f_rps += k_rpm * (rpm / 60 - f_rps)
        if t > 0.2: lowest = min(lowest, rpm)
        if n % 800 == 0: rows.append((t, rpm, u, inc, p_term, I))
        t += DT; n += 1
    return rows, lowest

print("\nPart 2b. Slowest motor, synthetic flight: ground idle 0-0.3 s, climb 0.3-0.8 s, chop + flat drop 0.9-1.6 s")
st_rows, st_low = run_idle(False)
dy_rows, dy_low = run_idle(True)
print("   t s | static idle 5.5 %: rpm  drive | dynamic idle 30: rpm  drive  increase  P term  I term")
for a, b in zip(st_rows, dy_rows):
    print(f"  {a[0]:4.1f} | {a[1]:21.0f} {a[2]*100:5.1f} % | {b[1]:19.0f} {b[2]*100:5.1f} %  {b[3]*100:6.2f} %"
          f"  {b[4]*100:6.2f} %  {b[5]*100:5.2f} %")
print(f"  lowest rpm after 0.2 s: static idle {st_low:.0f}, dynamic idle {dy_low:.0f} (target 3000)")
```

```text
Part 2a. Dynamic idle gains (dyn_idle_min_rpm 30, P/I/D 50, max 150, start 50; PID 8 kHz)
  target 50.0 rps = 3000 rpm; P 0.0075 /rps; I 6.250e-05 /rps per loop; D 0.120; limits 15 % (airmode) / 5 % (before airmode)
  slowest motor 2900 rpm: error  1.67 rps -> P alone  1.25 % of motor range (cap  1.25 %)
  slowest motor 2500 rpm: error  8.33 rps -> P alone  6.25 % of motor range (cap  6.25 %)
  slowest motor 2000 rpm: error 16.67 rps -> P alone 12.50 % of motor range (cap 12.50 %)
  slowest motor 1500 rpm: error 25.00 rps -> P alone 18.75 % of motor range (cap 15.00 %)
  slowest motor 1000 rpm: error 33.33 rps -> P alone 25.00 % of motor range (cap 15.00 %)

Part 2b. Slowest motor, synthetic flight: ground idle 0-0.3 s, climb 0.3-0.8 s, chop + flat drop 0.9-1.6 s
   t s | static idle 5.5 %: rpm  drive | dynamic idle 30: rpm  drive  increase  P term  I term
   0.0 |                  6098   5.5 % |                6087   1.0 %    0.00 %  -38.72 %   0.00 %
   0.1 |                  6098   5.5 % |                2999   1.3 %    0.30 %    0.00 %   0.00 %
   0.2 |                  6098   5.5 % |                2999   1.3 %    0.34 %    0.01 %   0.32 %
   0.3 |                  6098   5.5 % |                3000   1.3 %    0.33 %    0.00 %   0.33 %
   0.4 |                 15326  38.6 % |               14369  35.0 %    0.00 %  -141.73 %   0.00 %
   0.5 |                 16081  38.6 % |               15299  35.0 %    0.00 %  -153.71 %   0.00 %
   0.6 |                 16143  38.6 % |               15375  35.0 %    0.00 %  -154.69 %   0.00 %
   0.7 |                 16148  38.6 % |               15381  35.0 %    0.00 %  -154.77 %   0.00 %
   0.8 |                 16117   5.5 % |               15342   1.0 %    0.00 %  -154.77 %   0.00 %
   0.9 |                  6904   5.5 % |                3634   1.0 %    0.00 %   -8.42 %   0.00 %
   1.0 |                  2491   5.5 % |                2997   7.3 %    6.32 %    0.04 %   6.26 %
   1.1 |                  2130   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.2 |                  2100   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.3 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.4 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.5 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.6 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.7 |                  5770   5.5 % |                3408   1.7 %    0.71 %   -5.10 %   5.81 %
   1.8 |                  6071   5.5 % |                3371   1.7 %    0.67 %   -4.65 %   5.31 %
   1.9 |                  6095   5.5 % |                3334   1.6 %    0.64 %   -4.19 %   4.81 %
   2.0 |                  6097   5.5 % |                3297   1.6 %    0.60 %   -3.72 %   4.31 %
  lowest rpm after 0.2 s: static idle 2098, dynamic idle 2734 (target 3000)
```

Разбор:
- **2a.** 100 об/мин недобора — 1.25 % тяги от одного P; предел 15 % (`dyn_idle_max_increase`) один P достигает при недоборе 1200 об/мин (мотор на 1800). При долгом desync это бережёт остальные моторы.
- **2b, земля.** Регулятор **снижает** холостой ход: 3000 об/мин при 1.3 % тяги против 6100 при 5.5 %. До airmode прибавка не больше 5 %.
- **2b, падение.** Статический idle проседает до 2100 об/мин, dynamic idle держит 3000 ценой 6.3 % прибавки — её держит I, P при нулевой ошибке ≈ 0. Провал до 2734 об/мин — задержка фильтра и инерция мотора.
- **2b, после.** I спускается медленно (−0.1 об/с в ошибке), но отрицательный P сразу гасит прибавку.

### Шаг 3. Turtle: что получает каждый мотор
Вывод снят на алгоритме 4.5; в 2025.12 функция называется `applyCrashFlipModeToMotors()`, `crashflip_expo` нет, мощность равна отклонению стика выше мёртвой зоны 15 %, полный стик даёт 2047. Перенос `applyFlipOverAfterCrashModeToMotors()` для QUADX (`mixerQuadX`: M1 задний правый, M2 передний правый, M3 задний левый, M4 передний левый), без dynamic idle, `dshot_idle_value` 5.5 % → нижняя граница 157.9.

```python
# Part 3: crash flip motor outputs (flight/mixer.c applyFlipOverAfterCrashModeToMotors, QUADX mixer).
QUADX = [(-1.0, 1.0, -1.0), (-1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (1.0, -1.0, -1.0)]  # roll, pitch, yaw: M1 RR, M2 FR, M3 RL, M4 FL
DSHOT_MIN, DSHOT_MAX = 48, 2047
def crashflip(roll, pitch, yaw, expo=35, motor_pct=0, idle=IDLE, yaw_reversed=False):
    low = DSHOT_MIN + idle * (DSHOT_MAX - DSHOT_MIN)          # motorOutputMin (no dynamic idle)
    rng = DSHOT_MAX - low                                     # motorRangeMax = motorOutputHigh while flipping
    f = 1 - expo / 100
    ex = lambda a: f * a + a ** 3 * (1 - f)
    ap, ar, ay = abs(pitch), abs(roll), abs(yaw)
    sp = 1 if pitch < 0 else -1; sr = 1 if roll < 0 else -1
    sy = (1 if yaw < 0 else -1) * (1 if yaw_reversed else -1)
    length = math.hypot(ap, ar); elen = math.hypot(ex(ap), ex(ar))
    if ay > max(ap, ar):
        length, elen, sr, sp = ay, ex(ay), 0, 0
    else:
        sy = 0
    cosphi = (ap + ar) / (math.sqrt(2) * length) if length > 0 else 0
    if cosphi < math.sqrt(3) / 2:
        if ar > ap: sp = 0
        else: sr = 0
    smin = f * 0.15 + 0.15 ** 3 * (1 - f)                     # CRASH_FLIP_STICK_MINF 0.15
    power = max(0.0, elen - smin) / (1 - smin)
    out = []
    for r, p, y in QUADX:
        v = sp * p + sr * r + sy * y
        if v < 0: v = -v * motor_pct / 100 if motor_pct > 0 else 0
        v = min(1.0, power * v)
        o = low + v * rng
        out.append(0 if o < low + 20 else round(o - 20))      # CRASH_FLIP_DEADBAND 20 -> DSHOT_CMD_MOTOR_STOP
    return out, power

print("\nPart 3. Crash flip DShot outputs (0 = stop; 48..2047 throttle), crashflip_expo 35, dshot_idle_value 5.5 %")
print("  stick (roll, pitch, yaw)       | M1 RR  M2 FR  M3 RL  M4 FL | flip power")
cases = [((0.10, 0, 0), {}), ((0.30, 0, 0), {}), ((0.60, 0, 0), {}), ((1.0, 0, 0), {}), ((0, 1.0, 0), {}),
         ((0, 0, 0.8), {}), ((0.7, 0.7, 0), {}), ((0.6, 0, 0), {"motor_pct": 30}), ((0.6, 0, 0), {"expo": 0})]
for (r, p, y), kw in cases:
    out, pw = crashflip(r, p, y, **kw)
    tag = (" " + ",".join(f"{k}={v}" for k, v in kw.items())) if kw else ""
    print(f"  ({r:4.2f}, {p:4.2f}, {y:4.2f}){tag:15s} | " + "  ".join(f"{o:5d}" for o in out) + f" | {pw:5.3f}")
```

```text
Part 3. Crash flip DShot outputs (0 = stop; 48..2047 throttle), crashflip_expo 35, dshot_idle_value 5.5 %
  stick (roll, pitch, yaw)       | M1 RR  M2 FR  M3 RL  M4 FL | flip power
  (0.10, 0.00, 0.00)                |     0      0      0      0 | 0.000
  (0.30, 0.00, 0.00)                |   360    360      0      0 | 0.117
  (0.60, 0.00, 0.00)                |   907    907      0      0 | 0.407
  (1.00, 0.00, 0.00)                |  2027   2027      0      0 | 1.000
  (0.00, 1.00, 0.00)                |     0   2027      0   2027 | 1.000
  (0.00, 0.00, 0.80)                |     0   1397   1397      0 | 0.666
  (0.70, 0.70, 0.00)                |     0   2027      0      0 | 0.793
  (0.60, 0.00, 0.00) motor_pct=30   |   907    907    369    369 | 0.407
  (0.60, 0.00, 0.00) expo=0         |  1138   1138      0      0 | 0.529
```

Что видно: 10 % стика — мёртвая зона. Крен вправо — правая пара, тангаж вперёд — передняя, диагональ — один M2, рыскание — M2+M3. Полный стик — 2027 из 2047, почти полный газ в упёртый винт. `crashflip_motor_percent = 30` раскручивает вторую сторону на 30 % от первой. `crashflip_expo = 0` даёт на 60 % стика мощность 0.53 вместо 0.41: expo смягчает начало хода, но не ограничивает максимум.

### Шаг 4. Конфигурация в CLI (процедура по исходнику, не запускалась на железе)
Формат строк — `cliAux()` (`cli/cli.c`), значения — по таблице режимов. Пример раскладки: ARM на AUX1, ANGLE/HORIZON на трёхпозиционном AUX2, turtle на AUX3, launch control на AUX4, BEEPER на AUX5, PARALYZE на AUX6.

```text
aux 0 0 0 1700 2100 0 0
aux 1 1 1 1300 1700 0 0
aux 2 2 1 1700 2100 0 0
aux 3 35 2 1700 2100 0 0
aux 4 49 3 1700 2100 0 0
aux 5 13 4 1700 2100 0 0
aux 6 45 5 1700 2100 0 0
set dshot_bidir = ON
set motor_poles = 14
set dyn_idle_min_rpm = 30
set crashflip_motor_percent = 0
set crashflip_rate = 0
set launch_trigger_throttle_percent = 20
save
```

`dyn_idle_*` и `launch_*` — переменные профиля PID: они записываются в текущий профиль (`profile`), остальные три PID-профиля остаются с умолчаниями. После `save` проверь `get dyn_idle_min_rpm` в каждом профиле, которым летаешь.

### Переход на реальное железо
Пропы сняты до пункта 3. АКБ на столе — через smoke stopper. Арм — без подключённого Betaflight App (иначе флаг `MSP`).

**1. Стол.** Вкладка Motors, ползунки на ~1100: у всех моторов есть обороты, ошибок DShot < 1 % (или CLI `dshot_telemetry_info`). Вкладка Modes: каждый тумблер подсвечивает только свой режим. Turtle: тумблер turtle, затем ARM — в OSD `> CRASH FLIP <`, пищит. Крен вправо — крутятся только правые моторы и **назад** (полоска скотча на колоколе). Дизарм, turtle выкл., ARM — моторы снова вперёд. Dynamic idle на столе не проверить: разгруженный мотор и на 1 % крутится быстрее цели. Его проверка — пункт 5.

**2. 3D — только без пропов, отдельной конфигурацией.** ESC в Bidirectional, `feature 3D`, `save`. Газ в центр, ARM. Вверх — моторы вперёд, вниз — назад, центр — холостой в направлении, откуда пришёл стик. Каждый мотор в обе стороны по номеру. ARM выкл. — моторы стоят мгновенно при любом газе. Симметричные 3D-пропы — только после этого.

**3. Turtle на траве, пропы стоят.** Аппарат на спине в траве, люди дальше 10 м. Turtle, ARM, крен в сторону переворота толчками 0.5–1 с; перевернулся — дизарм, turtle выкл., ARM. Прервать: не перевернулся за три толчка (иди пешком); запах горелого или мотор горячий на ощупь; после переворота моторы крутятся назад (забыт тумблер — дизарм).

**4. Launch control на ровной площадке.** ACRO, тумблер LAUNCH CONTROL, ARM — в OSD `LAUNCH 0`. Стиком тангажа наклони аппарат на батарею на 20–30°, отпусти: угол держится ±5° 5 с, моторы не разгоняются (разгоняются — `launch_control_gain` велик). Плавно газ: за 10 % до порога OSD мигает, выше 20 % аппарат уходит вперёд в ACRO. Прервать: кувырок через нос (меньший угол или `launch_angle_limit`), аппарат ползёт по земле, нет `LAUNCH` в OSD (смотри условия в теории).

**5. Dynamic idle в полёте.** `set dyn_idle_min_rpm = 30`, `debug_mode = DYN_IDLE`, Blackbox. Вертикально вверх, газ в ноль, плоское падение 2–3 с. В логе debug[3] (минимальные обороты, об/с ×10) не ниже 450 (−10 % от 500), сумма debug[0] + debug[1] + debug[2] (P, I и D прибавки, ×10000) меньше 1500. На выходе из падения нет хлопков и провалов.

**Критерии засчёта железной части:** turtle на столе крутит нужные моторы назад, после дизарма направление восстанавливается; на траве переворот за ≤ 3 толчка без перегрева. Launch control держит угол 5 с и стартует на пороге газа. 3D проверен без пропов в четырёх точках (вперёд, назад, центр, дизарм). Лог dynamic idle показывает удержание цели в плоском падении.

Лабораторная засчитывается, когда:
- **Расчётный путь (Python):** три части скрипта запущены, выводы совпадают с приведёнными. По шагу 1 для своих рейтов посчитан целевой угол Angle на 25/50/75 % стика и сила Horizon при наклоне 45° и стике 30 %. По шагу 2 найдена минимальная цель `dyn_idle_min_rpm`, при которой прибавка в падении из сценария упирается в 15 %, с объяснением. По шагу 3 посчитан выход DShot для своего `crashflip_expo` на 50 % стика (алгоритм 4.5) и рядом — что даст 2025.12 при том же стике.
- **Конфигурация:** строки `aux` для своей раскладки написаны по таблице `permanentId`, `get dyn_idle_min_rpm` проверен во всех используемых профилях.
- **Железо:** выполнены критерии засчёта железной части выше.

## diagnostics
- **Симптом:** режима FLIP OVER AFTER CRASH нет во вкладке Modes
  - Возможная причина: протокол моторов не DShot.
  - Что сделать: DSHOT300/600; без DShot turtle невозможен (ни в 4.5, ни в 2025.12).
- **Симптом:** turtle включён, а моторы при арме крутятся вперёд или стоят
  - Возможная причина: ESC не выполняет DShot-команды 20/21; тумблер turtle поднят после ARM; стик в мёртвой зоне 15 %.
  - Что сделать: порядок «turtle → ARM», выход — только дизармом; проверить на столе; обновить прошивку ESC (f-esc-firmware).
- **Симптом:** dynamic idle «не работает», хотя `dyn_idle_min_rpm` = 30
  - Возможная причина: нет eRPM (`dshot_bidir = OFF`, ESC без bidir) — цель молча обнуляется; значение в другом профиле PID; `feature 3D`.
  - Что видно в логе: debug `DYN_IDLE` [0] всегда 0.
  - Что сделать: `dshot_telemetry_info`, `profile`, `get dyn_idle`.
- **Симптом:** launch control не включается (нет `LAUNCH` в OSD)
  - Возможная причина: арм стиками; ANGLE/HORIZON; `feature 3D`; `MOTOR_STOP` без airmode; старт уже был при `launch_trigger_allow_reset = OFF`.
  - Что сделать: арм тумблером в ACRO; переключить тумблер режима или перезагрузиться.
- **Симптом:** 3D не армится, или правка `3d_deadband_low/high` ничего не меняет
  - Возможная причина: газ вне 1451–1549 мкс; `3d_deadband_*` действуют только на PWM, при DShot разделение фиксировано.
  - Что сделать: газ в центр; холостой при DShot — `motor_idle` (до 2025.12 — `dshot_idle_value`), он действует в обе стороны.
- **Симптом:** Angle вялый у центра стика, Horizon не выравнивает в крутых виражах
  - Возможная причина: Angle повторяет рейты (16.6° на полстика по умолчанию); Horizon гаснет к 75 % стика и 135°.
  - Что сделать: поднять `roll_rc_rate` или взять отдельный профиль рейтов; для Horizon — `horizon_limit_sticks` > 100 или `horizon_ignore_sticks = ON`.
- **Симптом:** `set acro_trainer_angle_limit` даёт `###ERROR IN set: INVALID NAME`, режима ACRO TRAINER нет
  - Возможная причина: сборка без опции ACRO_TRAINER или нет акселерометра.
  - Что сделать: пересобрать в Cloud Build с опцией (bf-custom).
- **Симптом:** меню камеры не открывается стиками
  - Возможная причина: аппарат заармлен; STICK COMMANDS DISABLE; газ не в 1350–1650; камера не ответила при старте FC.
  - Что сделать: порт RunCam Device и TX↔RX; `rcdevice_init_dev_attempts` больше; для джойстика — `resource CAMERA_CONTROL` и `camera_control_internal_resistance` своей камеры.
- **Симптом:** не армится, флаг `PARALYZE`, тумблер уже выключен
  - Возможная причина: режим «липкий».
  - Что сделать: перезагрузить FC.

## checklist
- Знаю формат `aux` (7 полей) и нахожу `permanentId` в таблице, а не в `rc_modes.h`
- Turtle: DShot, порядок «turtle → ARM», выход через дизарм; короткие толчки, нагрев проверен
- `crashflip_motor_percent` понимаю по выходам моторов (шаг 3); знаю, что `crashflip_expo` есть только в 4.5, а в 2025.12 — `crashflip_rate` и `crashflip_auto_rearm`
- Launch control: условия активации и `launch_trigger_allow_reset` под свою раскладку
- 3D: ESC в Bidirectional, `3d_deadband_*` только для PWM, проверка без пропов
- Acro trainer есть в сборке, предел угла задан
- Angle повторяет рейты; Horizon гаснет к 75 % стика и 135°
- Dynamic idle: bidir DShot работает, `dyn_idle_min_rpm` задан во всех профилях, `motor_idle` при нём — только предел прибавки на земле
- `MOTOR_STOP` без airmode понимаю как исключение, а не норму
- Camera control: тип камеры определён (UART или провод OSD), меню открывается без арма

## references
- Betaflight pid.c, 4.5-maintenance (pidLevel, calcHorizonLevelStrength, applyAcroTrainer, applyLaunchControl, умолчания профиля) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight pid_init.c, 4.5-maintenance (angleGain, horizon*, acroTrainer*, launchControlKi) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid_init.c | primary | A
- Betaflight mixer.c, 4.5-maintenance (3D, dynamic idle, crash flip, MOTOR_STOP) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c | primary | A
- Betaflight mixer_init.c, 4.5-maintenance (коэффициенты dynamic idle, crashflip, launchControlMixer) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer_init.c | primary | A
- Betaflight core.c, 4.5-maintenance (tryArm, disarm, canUseLaunchControl, PARALYZE, 3D) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c | primary | A
- Betaflight msp_box.c, 4.5-maintenance (permanentId режимов, initActiveBoxIds) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/msp/msp_box.c | primary | A
- Betaflight cli/settings.c, 4.5-maintenance (имена и диапазоны переменных) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/settings.c | primary | A
- Betaflight dshot.c, 4.5-maintenance (конечные точки DShot и 3D, обороты моторов) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/dshot.c | primary | A
- Betaflight rcdevice_cam.c, 4.5-maintenance (кнопки камеры, стики меню) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/rcdevice_cam.c | primary | A
- Betaflight rc_controls.c, 4.5-maintenance (стик-команды camera control, умолчания 3D) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc_controls.c | primary | A
- Betaflight mixer.c, тег 2025.12.5 (applyCrashFlipModeToMotors, crashflip_rate, dynamic idle) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/mixer.c | primary | A
- Betaflight core.c, тег 2025.12.5 (crashflip_auto_rearm, FLIP_SWITCH, ALT_HOLD_SW, POS_HOLD_SW) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/core.c | primary | A
- Betaflight cli/settings.c, тег 2025.12.5 (имена, умолчания и диапазоны) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight docs: Dynamic Idle | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Dynamic-Idle.md | primary | A
- Betaflight docs: Launch Control | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Launch-Control.md | primary | A
- Betaflight docs: 3D Setup | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/3D-Setup.md | primary | B
- Betaflight docs: Acro Trainer | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Acro-Trainer.md | primary | A
- Betaflight docs: RunCam Device Protocol | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/RunCam-Device-Protocol.md | primary | B
- Betaflight docs: FPV Camera Control (joystick emulation) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/FPV-Camera-Control-Joystick-Emulation.md | primary | B

## notes
Где документация расходится с исходником, модуль следует исходнику:
- Страница Dynamic Idle пишет, что до airmode прибавка ограничена «фиксированными 4 %». В 4.5 это `dyn_idle_start_increase` = 50, то есть 5 %, в 2025.12 — `motor_idle`, по умолчанию 5.5 %. Секцию «4.2» с подбором через `dshot_idle_value` к 4.3+ не применяй: как пол значение не действует.
- Страница 3D Setup описывает `3d_deadband_*` без оговорки про DShot. В коде они используются только в `analogInitEndpoints()`.
- Модели мотора (шаг 2) и внутреннего контура (шаг 1) учебные. Числа оборотов и миллисекунд на твоём аппарате будут другими, а логика регуляторов взята из прошивки построчно.
