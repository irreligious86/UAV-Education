---
id: px4-setup-scratch
title: "PX4 с нуля: Vehicle Setup в QGroundControl"
level: L2
readingTime: 55 мин
firmware: PX4 1.15 (проверено на v1.15.4, SITL SIH)
status: published
tags:
  - PX4
  - QGroundControl
  - настройка с нуля
  - failsafe
  - калибровка питания
related:
  - px4-intro
  - px4-architecture
  - px4-control
  - f-motors-esc
  - link-elrs
  - link-protocols
next:
  - px4-control
---

## summary
Один мультиротор от пустого полётника до записанного первого висения на PX4 1.15 — в порядке 17 шагов настройки. Половину шагов проходишь в SITL (`make px4_sitl sihsim_quadx` или `gz_x500` + QGroundControl): airframe, геометрия моторов, тест моторов, режимы, failsafe с инъекцией отказов, autotune, лог и экспорт параметров. Остальное — на столе без пропов и в поле: порты `*_CONFIG`, приёмник CRSF/ELRS, калибровка радио, DShot или PWM с калибровкой ESC, `BAT1_V_DIV` и `BAT1_A_PER_V` по мультиметру и зарядке, первое висение в Position. Лабораторная: экспортированные параметры, тест моторов по геометрии, RC loss и low battery в ULog, отчёт Flight Review первого полёта.

## theory
### Что здесь нового, а что — ссылка
Модуль px4-intro даёт общий порядок экранов QGC, px4-architecture — модули и uORB, px4-control — каскад и тюнинг. Протоколы моторов — f-motors-esc, приёмник и бинд ELRS — link-elrs, кадр CRSF и разводка UART — link-protocols. Здесь — то, чего в курсе для PX4 не было: порты, вход RC, Actuators, питание, failsafe с проверкой, висение, бэкап.

{{diagram:px4-setup-flow|Из 17 шагов SITL закрывает airframe, тест моторов, режимы, failsafe, RTL, autotune и лог; приёмник, ESC, датчики и питание делаются только на железе, пропы ставятся на шаге 15.}}

### Три вещи, которые в PX4 устроены иначе
- **Порт назначается функции, а не функция порту.** У каждой службы свой параметр `*_CONFIG` / `*_CFG`: `MAV_0_CONFIG` (по умолчанию TELEM1), `MAV_1_CONFIG` (TELEM2), `GPS_1_CONFIG` (GPS1), `RC_PORT_CONFIG`, `RC_CRSF_PRT_CFG`, `MSP_OSD_CONFIG`, `DSHOT_TEL_CFG`. После выбора порта — перезагрузка, затем появляется скорость: `SER_GPS1_BAUD` (0 = Auto), для MAVLink — `MAV_0_RATE`. Два драйвера на одном порту PX4 не запретит и не предупредит: порт нужно освободить, поставив чужой `*_CONFIG` в Disabled.
- **Выход назначается функции.** В Actuators каждому выходу ставится функция: `PWM_MAIN_FUNCn` / `PWM_AUX_FUNCn` = 101…112 — Motor 1…12. Протокол выбирается на группу таймера (`PWM_MAIN_TIMx` / `PWM_AUX_TIMx`: −5…−2 = DShot150…1200, −1 = OneShot, 50…400 = PWM, Гц). Геометрия — в `CA_*`: `CA_ROTOR_COUNT`, `CA_ROTORn_PX/PY` (м, FRD от центра масс), `CA_ROTORn_KM` (> 0 — CCW, < 0 — CW).
- **Failsafe — с задержкой.** Большинство действий сначала дают Hold на `COM_FAIL_ACT_T` = 5 с (пилот может перехватить), потом — действие. SITL стартует с другими умолчаниями, чем полётник: `COM_RC_IN_MODE` = 1 (только джойстик), `COM_LOW_BAT_ACT` = 2, `SYS_FAILURE_EN` = 1, `MC_AT_EN` = 1, `SDLOG_MODE` = 1. Файл `.params` из SITL на аппарат не переносят.

### Вход RC: CRSF/ELRS в PX4 1.15
Два драйвера. `rc_input` разбирает CRSF (`RC_INPUT_PROTO`: −1 авто, 6 CRSF) на порту `RC_PORT_CONFIG`. Отдельный `crsf_rc` (порт `RC_CRSF_PRT_CFG`, телеметрия `RC_CRSF_TEL_EN`) по документации 1.15 требует своей сборки через `make <board> boardconfig` с выключенным `rc_input`. Что есть в твоей прошивке, видно по тому, какой параметр показывает QGC. Порт RC IN через IO-процессор Pixhawk понимает SBUS/DSM/PPM/ST24/SUMD, но не CRSF: ELRS подключают к UART (TELEM2, GPS2). В default-сборке fmu-v6x `rc_input` есть, в fmu-v6c — нет (проверено по `default.px4board` v1.15.4).

### Питание: как PX4 считает напряжение, ток и остаток
Из `analog_battery.cpp`: `V = V_adc · BAT1_V_DIV`, `I = (V_adc − BAT_V_OFFS_CURR) · BAT1_A_PER_V`. Оба коэффициента стоят в числителе, поэтому калибровка — пропорция:

| Что | Формула | Чем мерить |
|---|---|---|
| Делитель | `BAT1_V_DIV_new = BAT1_V_DIV_old × V_мультиметр / V_QGC` | мультиметр на балансире или XT60 |
| Ток | `BAT1_A_PER_V_new = BAT1_A_PER_V_old × мА·ч_зарядка / мА·ч_лог` | зарядка после полёта; клещи — для проверки |

Остаток (`battery.cpp`): напряжение элемента, исправленное на нагрузку (`+ BAT1_R_INTERNAL · I`, а без датчика тока `+ газ · BAT1_V_LOAD_DROP`), линейно интерполируется между `BAT1_V_EMPTY` (3.6 В) и `BAT1_V_CHARGED` (4.05 В). С `BAT1_CAPACITY` > 0 к этому добавляется интеграл тока; документация советует ≈ 90 % паспортной ёмкости. Пороги: `BAT_LOW_THR` 0.15, `BAT_CRIT_THR` 0.07, `BAT_EMERGEN_THR` 0.05. Действие — `COM_LOW_BAT_ACT`: 0 предупреждение (умолчание на полётнике), 2 Land, 3 Return на critical и Land на emergency.

### Газ висения и тяговооружённость
`MPC_THR_HOVER` (0.5) — стартовое значение. В полёте его уточняет оценщик тяги висения (`MPC_USE_HTE` = 1, топик `hover_thrust_estimate`). При линейной тяге доля висения = m·g / (n·T_max) = 1/(T/W). Реальный проп даёт тягу ближе к квадрату сигнала, это учитывает `THR_MDL_FAC`: `тяга = f·s² + (1 − f)·s`.

## practice
### Шаг 1. Прошивка → сборка SITL (шаг 1 из 17)
Вместо прошивки — сборка SITL. Я собирал v1.15.4 в контейнере (2 ядра, 7 ГБ): `make px4_sitl_default` — 1024 цели. Python-зависимости ставил в venv по `Tools/setup/requirements.txt`, а не скриптом `ubuntu.sh`. Gazebo в контейнере нет, поэтому основной путь здесь — SIH: физика считается внутри самого PX4. С Gazebo команда та же, что в px4-intro: `make px4_sitl gz_x500`.

```
git clone --branch v1.15.4 --recursive https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot && bash ./Tools/setup/ubuntu.sh --no-nuttx
HEADLESS=1 make px4_sitl sihsim_quadx
```
```
INFO  [init] found model autostart file as SYS_AUTOSTART=10040
INFO  [simulator_sih] Simulation loop with 250 Hz (4000 us sim time interval)
INFO  [logger] Opened full log file: ./log/2026-11-10/20_22_32.ulg
pxh> INFO  [commander] Ready for takeoff!
```
QGC подключается сама по UDP 14550. Все команды ниже вводятся в `pxh>` или в QGC → Analyze Tools → MAVLink Console.

### Шаг 2. Airframe и геометрия (2)
Airframe задаётся `SYS_AUTOSTART`: 10040 — SIH Quad X, 4001 — gz_x500, на железе 4001 — Generic Quadcopter. Смена airframe перезаписывает параметры. Проверь геометрию:
```
pxh> param show CA_ROTOR0_KM
x   CA_ROTOR0_KM [132,252] : 0.0500
```
| Мотор | `PX` | `PY` | `KM` | Где и куда |
|---|---|---|---|---|
| 1 | 1 | 1 | 0.05 | перед-право, CCW |
| 2 | −1 | −1 | 0.05 | зад-лево, CCW |
| 3 | 1 | −1 | −0.05 | перед-лево, CW |
| 4 | −1 | 1 | −0.05 | зад-право, CW |

Это нумерация PX4, не Betaflight: там мотор 1 — зад-право. `PWM_MAIN_FUNC1…4` = 101…104.

### Шаг 3. Порты, приёмник, радио, протокол (3–6) — чего SITL не умеет
В SITL нет UART: MAVLink идёт по UDP, вход RC — джойстик QGC (`COM_RC_IN_MODE` = 1). Шаги 3–6, 8–10 и 13 SITL не проходит. Они ниже, в «Переходе на реальное железо».

### Шаг 4. Тест моторов (7)
```
pxh> actuator_test set -m 3 -v 0.15 -t 3
pxh> listener actuator_outputs -n 1
    output: [900.00000, 900.00000, 1150.00000, 900.00000, ...]
```
Крутится только выход 3: 900 мкс — disarmed, 1000 + 0.15 × 1000 = 1150 мкс. В QGC это Actuators → Enable sliders. Запиши таблицу «слайдер → какой мотор → куда крутится». В SITL проверяется только номер, направление — на столе.

### Шаг 5. Режимы и арм (11; шаги 8–10 — только железо)
```
pxh> commander check
INFO  [commander] Preflight check: OK
```
В QGC → Flight Modes: канал `RC_MAP_FLTMODE`, слоты `COM_FLTMODE1…6` (0 Manual, 1 Altitude, 2 Position, 4 Hold, 5 Return, 8 Stabilized). Арм-тумблер — `RC_MAP_ARM_SW`, `COM_ARM_SWISBTN` = 0 (тумблер) или 1 (кнопка). Kill — `RC_MAP_KILL_SW`. Без взлёта PX4 сам снимет арм через `COM_DISARM_PRFLT` = 10 с.

### Шаг 6. Failsafe с инъекцией отказов (12, 14)
Инъекция работает при `SYS_FAILURE_EN` = 1 (в SITL — по умолчанию). `failure rc_signal off` в SIH 1.15 не реализован:
```
pxh> failure rc_signal off
ERROR [failure] Timeout waiting for ack
```
Поэтому потерю RC я делал честно: скрипт pymavlink (`udpin:0.0.0.0:14550`) шлёт `MANUAL_CONTROL` 20 Гц как джойстик, взлёт, Position, через 25 с отправка прекращается. Реальный журнал:
```
[  38.0 s] >>> joystick (manual control) stopped
[  39.4 s] mode=HOLD armed=True
[  44.5 s] mode=RTL armed=True
[  54.6 s] mode=POSCTL armed=False
WARN  [failsafe] Failsafe activated: entering Hold for 5 seconds
INFO  [navigator] RTL: start return at 35 m (3 m above destination)
INFO  [commander] Disarmed by landing
```
Цепочка: 0.5 с `COM_RC_LOSS_T` (плюс задержка детектора) → Hold на `COM_FAIL_ACT_T` = 5 с → `NAV_RCL_ACT` = 2 (Return) → посадка → дизарм по посадке (`COM_DISARM_LAND` = 2 с). Аппарат был в 3 м от дома, поэтому RTL не набирал `RTL_RETURN_ALT`.

Батарея: `failure battery off` подменяет напряжение на 3.6 В/эл (14.4 В). С умолчаниями (`BAT_CRIT_THR` 0.07) в висении приходит только LOW: компенсация нагрузки добавляет 0.49 × 0.1 = 0.049 В, остаток (3.649 − 3.6)/0.45 = 0.109. Для теста я поставил `COM_LOW_BAT_ACT 3`, `BAT_CRIT_THR 0.12`, `BAT_LOW_THR 0.20`:
```
[  38.0 s] failure cmd output: WARN  [failure] inject failure unit: battery (100), type: off (1), instance: 0
[  40.1 s] vehicle_status: nav_state=POSCTL armed; battery 14.40000 V warning=1
[  42.2 s] vehicle_status: nav_state=AUTO_LOITER(Hold) armed; battery 14.40000 V warning=2
[  47.2 s] vehicle_status: nav_state=AUTO_RTL armed; battery 14.40000 V warning=2
[  59.4 s] vehicle_status: nav_state=AUTO_RTL armed; battery 14.40000 V warning=3
[  60.0 s] vehicle_status: nav_state=AUTO_LAND armed; battery 14.40000 V warning=3
[  62.5 s] vehicle_status: nav_state=POSCTL disarmed; battery 14.40000 V warning=3
```
Вывод: пороги проверяют на реальном напряжении под нагрузкой, а не по таблице.

### Шаг 7. Висение, autotune, лог и бэкап (15–17)
Расчёт для SIH: `SIH_MASS` 1 кг, `SIH_T_MAX` 5 Н на мотор → T/W = 20 / 9.81 = 2.04 → доля висения 0.4905. Оценщик в логе:

{{diagram:chart-px4-hte|HTE сходится к 0.488–0.493 за ~25 с и совпадает с расчётом 1/(T/W) = 0.4905; MPC_THR_HOVER = 0.5 — только стартовая точка.}}

Autotune: Position на 2.5 м, `MAV_CMD_DO_AUTOTUNE_ENABLE` (в QGC — PID Tuning → Autotune). По `autotune_attitude_control_status` идентификация заняла 26 с (35.4 → 61.2 с от арма), коэффициенты применились после дизарма (`MC_AT_APPLY` = 1):

| Параметр | До | После |
|---|---|---|
| `MC_ROLLRATE_P` | 0.1500 | 0.1564 |
| `MC_ROLLRATE_D` | 0.0030 | 0.0001 |
| `MC_PITCHRATE_P` | 0.1500 | 0.1567 |
| `MC_ROLL_P` | 6.5000 | 6.1074 |

D около нуля — свойство SIH: модель без задержек и шума. На реальной раме так не бывает.

Бэкап. `param save <файл>` пишет бинарный BSON. Текстовый `.params` сохраняет QGC → Parameters → Tools → Save to file. Изменения относительно airframe в консоли:
```
pxh> param show-for-airframe
param set-default BAT_CRIT_THR 0.1200
param set-default COM_LOW_BAT_ACT 3
param set-default MC_ROLLRATE_P 0.1564
# Make sure to add all params from the current airframe (ID=10040) as well
```
Лог SITL лежит в `build/px4_sitl_default/rootfs/log/<дата>/`, с железа — QGC → Analyze Tools → Log Download, потом загрузка на review.px4.io.

### Переход на реальное железо
Пример: рама 450–500 мм, Pixhawk FMUv6, 4S 5000 мА·ч, взлётная масса 1.6 кг, ESC с PWM или DShot. **Пропы сняты до пункта 13.**

1. **Прошивка.** QGC → Vehicle Setup → Firmware, USB подключаешь после открытия экрана, PX4 Pro Stable. Если прошивка уже стояла — сначала Parameters → Save to file (старый конфиг).
2. **Airframe** (Generic Quadcopter, 4001) → Apply and Restart. Ориентация платы `SENS_BOARD_ROT`, компас GPS определяется сам (`SENS_MAG_AUTOROT` = 1).
3. **Порты.** GPS — GPS1 (`GPS_1_CONFIG`), телеметрия — TELEM1 (`MAV_0_CONFIG`). Для ELRS на TELEM2: `MAV_1_CONFIG` = Disabled, затем `RC_PORT_CONFIG` = TELEM 2 (`rc_input`) или `RC_CRSF_PRT_CFG` = TELEM 2 (`crsf_rc`), перезагрузка. TX контроллера идёт на RX приёмника, RX — на TX.
4. **Приёмник.** Бинд и packet rate — по link-elrs. Проверка: Radio — все ползунки двигаются, каналов ≥ 8.
5. **Калибровка радио.** QGC → Radio → Calibrate: пишутся `RC1_MIN/TRIM/MAX`…, `RC_MAP_*`. Норма — около 1000/1500/2000 мкс. Потом режимы и арм/kill из шага 5 SITL.
6. **Протокол.** Actuators: моторы на выходах FMU. На Pixhawk с IO DShot работает только на AUX, MAIN идёт через IO. Группа таймера → DShot600 (если ESC умеет) или PWM 400 Гц.
7. **Порядок и направление.** Слайдеры по одному на 10–15 %. Номер мотора — по таблице шага 2, направление — по стрелкам схемы. Неверное направление у DShot: `dshot reverse -m 2`, затем `dshot save -m 2`; у PWM — поменять два фазных провода. Disarmed — мотор стоит, minimum — едва крутится.
8. **Калибровка ESC (только PWM/OneShot).** FC от USB, АКБ отключена, QGC → Power → Calibrate, подключить АКБ по подсказке. Калибровка идёт по 1000/2000 мкс. Умолчания выходов мотора — min/max/disarmed = 1100/1900/1000 мкс. DShot калибровать не нужно.
9. **Датчики.** Accelerometer (6 положений), Gyroscope (неподвижно), Compass (вращение, вдали от железа), Level Horizon (на ровной поверхности).
10. **Питание.** QGC → Power: `BAT1_N_CELLS` 4, `BAT1_V_EMPTY` 3.6, `BAT1_V_CHARGED` 4.05. Напряжение: QGC показывает 16.42 В, мультиметр — 16.71 В, `BAT1_V_DIV` 18.000 → 18.000 × 16.71 / 16.42 = 18.318 (ошибка была 0.072 В/эл). Кнопка Calculate в QGC считает ту же пропорцию. Ток проверяется после первого полёта: в логе 2310 мА·ч, зарядка залила 2465 → `BAT1_A_PER_V` 36.0 × 2465 / 2310 = 38.416. `BAT1_CAPACITY` = 4500.
11. **Failsafe.** `COM_LOW_BAT_ACT` = 3, `NAV_RCL_ACT` = 2, `RTL_RETURN_ALT` выше препятствий (умолчание 60 м), `GF_ACTION` по задаче. На столе без пропов и без арма: выключить пульт → в QGC сообщение о потере ручного управления, в консоли `listener failsafe_flags` → `manual_control_signal_lost: True`.
12. **OSD и телеметрия.** MSP OSD (DJI/Walksnail) — `MSP_OSD_CONFIG` на свободный UART, если драйвер есть в сборке платы. Иначе телеметрия на пульте через CRSF (`RC_CRSF_TEL_EN`).
13. **Предполётная проверка и висение.** Пропы — по схеме CW/CCW. GPS ≥ 10 спутников, «Ready to fly», kill-тумблер под пальцем, 10 м до людей. Взлёт в Position, 2–3 м, 60 с висения, по 2 м в стороны, посадка. Прерывай (kill или Land), если: раскачка больше ±5°, дрейф больше 1 м при отпущенных стиках, «toilet bowl» (раскрутка по кругу — компас), газ висения выше 0.7.
14. **Тест failsafe в воздухе.** Position на 10 м, пульт выключить → Hold 5 с → Return. Включить пульт, сменой режима перехватить.
15. **Autotune.** Altitude, 4–20 м, штиль. Порядок — как в шаге 7 SITL, но фильтры и вибрации заранее проверены по px4-control.
16. **Лог и бэкап.** ULog в Flight Review: вибрации, газ висения, RC и батарея. `.params` из QGC — в репозиторий аппарата.

Лабораторная засчитывается, когда:
- **SITL:** таблица моторов (номер, позиция, KM) совпадает с `CA_ROTOR*`; в журнале есть цепочка RC loss → Hold → Return → дизарм и battery → Hold → Return → Land с временами; HTE совпал с расчётом 1/(T/W) в пределах 0.01; есть таблица autotune до/после и вывод `param show-for-airframe`.
- **Железо:** экспортированный `.params`; таблица теста моторов совпадает с геометрией airframe; ошибка напряжения < 0.05 В/эл; мА·ч по логу в пределах 5 % от зарядки после правки `BAT1_A_PER_V`; RC loss и low battery видны в ULog (`failsafe_flags`, смена `nav_state`); отчёт Flight Review первого 60-секундного висения в Position.

## diagnostics
- **Симптом:** ELRS приёмник светится «связь есть», а в QGC Radio каналы не двигаются
  - Возможная причина: приёмник подключён к RC IN через IO (CRSF там не разбирается), порт занят MAVLink (`MAV_1_CONFIG`) или перепутаны TX/RX.
  - Что сделать: UART + `RC_PORT_CONFIG` или `RC_CRSF_PRT_CFG`, освободить порт, перезагрузка; в MAVLink Console — `rc_input status` или `crsf_rc status`.
- **Симптом:** `RC_CRSF_PRT_CFG` нет в списке параметров
  - Возможная причина: драйвер `crsf_rc` не собран для этой платы.
  - Что сделать: `rc_input` на UART или своя сборка через `boardconfig`.
- **Симптом:** мотор не крутится в тесте Actuators, остальные крутятся
  - Возможная причина: выход не назначен Motor N или DShot стоит на MAIN через IO.
  - Что сделать: `PWM_AUX_FUNCn` = 10x, протокол на группу AUX.
- **Симптом:** при арме один мотор не запускается или стартует позже
  - Возможная причина: PWM ESC без калибровки, min 1100 мкс ниже точки старта.
  - Что сделать: калибровка ESC в Power (USB, без пропов) или поднять minimum, пока мотор не начнёт едва крутиться.
- **Симптом:** аппарат сразу переворачивается на взлёте
  - Возможная причина: порядок моторов или направление не совпадают с `CA_ROTOR*`, пропы перепутаны.
  - Что сделать: повторить тест моторов по таблице, сверить CW/CCW.
  - Последствия: сломанные пропы, риск для людей рядом.
- **Симптом:** в полёте «Low battery», хотя АКБ полная; или наоборот — садится на 3.3 В/эл без предупреждения
  - Возможная причина: не откалиброван `BAT1_V_DIV`, не задан `BAT1_N_CELLS`, `COM_LOW_BAT_ACT` = 0.
  - Что сделать: калибровка по мультиметру, пороги, действие 3.
  - Что видно в логе: `battery_status.voltage_v` расходится с мультиметром на постоянный процент.
- **Симптом:** мА·ч в логе на 7–10 % меньше, чем залила зарядка
  - Возможная причина: `BAT1_A_PER_V` от другого силового модуля.
  - Что сделать: умножить на мА·ч_зарядка / мА·ч_лог, проверить ещё одним полётом.
- **Симптом:** после потери RC аппарат 5 с висит и только потом идёт домой
  - Возможная причина: это норма — Hold на `COM_FAIL_ACT_T`.
  - Что сделать: учитывать при планировании дистанции; уменьшать задержку осознанно.
- **Симптом:** `failure rc_signal off` в SITL отвечает «Timeout waiting for ack»
  - Возможная причина: в SIH/gz 1.15 эта инъекция не обрабатывается.
  - Что сделать: имитировать потерю, прекратив `MANUAL_CONTROL` (джойстик QGC или скрипт).

## references
- PX4 User Guide v1.15 — Actuator Configuration and Testing | https://docs.px4.io/v1.15/en/config/actuators.html | primary | A
- PX4 User Guide v1.15 — ESC Calibration | https://docs.px4.io/v1.15/en/advanced_config/esc_calibration.html | primary | A
- PX4 User Guide v1.15 — Battery Estimation Tuning | https://docs.px4.io/v1.15/en/config/battery.html | primary | A
- PX4 User Guide v1.15 — Serial Port Configuration | https://docs.px4.io/v1.15/en/peripherals/serial_configuration.html | primary | A
- PX4 User Guide v1.15 — CRSF Telemetry (TBS Crossfire / ExpressLRS) | https://docs.px4.io/v1.15/en/telemetry/crsf_telemetry.html | primary | A
- PX4 User Guide v1.15 — DShot ESCs | https://docs.px4.io/v1.15/en/peripherals/dshot.html | primary | A
- PX4 User Guide v1.15 — Safety Configuration (Failsafes) | https://docs.px4.io/v1.15/en/config/safety.html | primary | A
- PX4 User Guide v1.15 — System Failure Injection | https://docs.px4.io/v1.15/en/debug/failure_injection.html | primary | A
- PX4 User Guide v1.15 — Autotuning | https://docs.px4.io/v1.15/en/config/autotune.html | primary | A
- PX4 User Guide v1.15 — Simulation-In-Hardware (SIH) | https://docs.px4.io/v1.15/en/sim_sih/ | primary | A
- PX4-Autopilot v1.15.4 — analog_battery.cpp (V_DIV, A_PER_V) | https://github.com/PX4/PX4-Autopilot/blob/v1.15.4/src/modules/battery_status/analog_battery.cpp | primary | A
- PX4-Autopilot v1.15.4 — battery.cpp (state of charge) | https://github.com/PX4/PX4-Autopilot/blob/v1.15.4/src/lib/battery/battery.cpp | primary | A
- QGroundControl User Guide — Power Setup | https://docs.qgroundcontrol.com/Stable_V4.3/en/qgc-user-guide/setup_view/power.html | primary | A
- PX4 User Guide v1.15 — Radio Control Systems | https://docs.px4.io/v1.15/en/getting_started/rc_transmitter_receiver.html | primary | B

## checklist
- Сборка SITL работает, QGC подключена
- Геометрия `CA_ROTOR*` и тест моторов совпадают с рамой
- Порты освобождены и назначены через `*_CONFIG`, перезагрузка сделана
- ELRS на UART, каналы двигаются в Radio, калибровка радио сделана
- DShot на FMU-выходах или PWM ESC откалиброваны
- `BAT1_V_DIV` и `BAT1_A_PER_V` откалиброваны по мультиметру и зарядке
- RC loss и low battery проверены в SITL и на столе
- Первое висение в Position записано, лог в Flight Review, `.params` сохранён
