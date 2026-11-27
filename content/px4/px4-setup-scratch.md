---
id: px4-setup-scratch
title: "PX4 с нуля: Vehicle Setup в QGroundControl"
level: L2
readingTime: 55 мин
firmware: PX4 1.18 (сверено с v1.18.0 по исходникам; вывод SITL снят на v1.15.4, SIH)
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
Один мультиротор от пустого полётника до записанного первого висения на PX4 1.18 (лабораторный вывод снят на v1.15.4) — в порядке 17 шагов настройки. Половину шагов проходишь в SITL (`make px4_sitl sihsim_quadx` или `gz_x500` + QGroundControl): airframe, геометрия моторов, тест моторов, режимы, failsafe с инъекцией отказов, autotune, лог и экспорт параметров. Остальное — на столе без пропов и в поле: порты `*_CONFIG`, приёмник CRSF/ELRS, калибровка радио, DShot или PWM с калибровкой ESC, `BAT1_V_DIV` и `BAT1_A_PER_V` по мультиметру и зарядке, первое висение в Position. Лабораторная: экспортированные параметры, тест моторов по геометрии, RC loss и low battery в ULog, отчёт Flight Review первого полёта.

## theory
### Что здесь нового, а что — ссылка
Модуль px4-intro даёт общий порядок экранов QGC, px4-architecture — модули и uORB, px4-control — каскад и тюнинг. Протоколы моторов — f-motors-esc, приёмник и бинд ELRS — link-elrs, кадр CRSF и разводка UART — link-protocols. Здесь — то, чего в курсе для PX4 не было: порты, вход RC, Actuators, питание, failsafe с проверкой, висение, бэкап.

{{diagram:px4-setup-flow|Из 17 шагов SITL закрывает airframe, тест моторов, режимы, failsafe, RTL, autotune и лог; приёмник, ESC, датчики и питание делаются только на железе, пропы ставятся на шаге 15.}}

### Три вещи, которые в PX4 устроены иначе
- **Порт назначается функции, а не функция порту.** У каждой службы свой параметр `*_CONFIG` / `*_CFG`: `MAV_0_CONFIG` (по умолчанию TELEM1), `MAV_1_CONFIG` (обычно для TELEM2, по умолчанию 0 = Disabled), `GPS_1_CONFIG` (GPS1), `RC_PORT_CONFIG`, `RC_CRSF_PRT_CFG`, `MSP_OSD_CONFIG`, `DSHOT_TEL_CFG`. После выбора порта — перезагрузка, затем появляется скорость порта `SER_<порт>_BAUD`: `SER_GPS1_BAUD` (0 = Auto), для MAVLink на TELEM1 — `SER_TEL1_BAUD` (57600). `MAV_0_RATE` — не скорость порта, а потолок потока MAVLink в байтах/с (1200; 0 = baud/20). Два драйвера на одном порту PX4 не запретит и не предупредит: порт нужно освободить, поставив чужой `*_CONFIG` в Disabled. Номера портов fmu-v6x, параметры всей периферии — GPS, компаса, дальномеров, датчика скорости, DroneCAN, OSD — и способ найти конфликт портов по строке `Conflicting config` в `dmesg` разобраны в `px4-hardware-peripherals`.
- **Выход назначается функции.** В Actuators каждому выходу ставится функция: `PWM_MAIN_FUNCn` / `PWM_AUX_FUNCn` = 101…112 — Motor 1…12. Протокол выбирается на группу таймера (`PWM_MAIN_TIMx` / `PWM_AUX_TIMx`: −5 / −4 / −3 = DShot150 / 300 / 600, с 1.18 −8 / −7 / −6 = то же с bidirectional DShot, −1 = OneShot, 50…400 = PWM, Гц; значение −2 = DShot1200 было только в 1.15 и убрано в 1.16). Геометрия — в `CA_*`: `CA_ROTOR_COUNT`, `CA_ROTORn_PX/PY` (м, FRD от центра масс), `CA_ROTORn_KM` (> 0 — CCW, < 0 — CW).
- **Failsafe — с задержкой.** Большинство действий сначала дают Hold на `COM_FAIL_ACT_T` = 5 с (пилот может перехватить), потом — действие. SITL стартует с другими умолчаниями, чем полётник: `COM_RC_IN_MODE` = 1 (только MAVLink-джойстик), `COM_LOW_BAT_ACT` = 3 (до 1.16 — 2), `SYS_FAILURE_EN` = 1, `MC_AT_EN` = 1, `SDLOG_MODE` = 1. Файл `.params` из SITL на аппарат не переносят.

### Вход RC: CRSF/ELRS
Два драйвера. `crsf_rc` — отдельный драйвер CRSF: порт `RC_CRSF_PRT_CFG`, телеметрия `RC_CRSF_TEL_EN`. `rc_input` — общий: разбирает CRSF среди прочих (`RC_INPUT_PROTO`: −1 авто, 6 CRSF) на порту `RC_PORT_CONFIG`. Что есть в твоей прошивке, зависит от платы и версии и видно по тому, какой параметр показывает QGC. В 1.17 default-сборки fmu-v6x, fmu-v6xrt и fmu-v5x включают набор `crsf_rc`, `sbus_rc`, `dsm_rc`, `ghst_rc` и не включают `rc_input`: ELRS там настраивают через `RC_CRSF_PRT_CFG`. В fmu-v5 есть и этот набор, и `rc_input`; в fmu-v6c нет ни того, ни другого (проверено по `default.px4board` v1.17.0). До 1.17 было иначе: в default-сборке fmu-v6x стоял `rc_input` (`RC_PORT_CONFIG`), а `crsf_rc` требовал своей сборки через `make <board> boardconfig` с выключенным `rc_input` — страница CRSF Telemetry документации 1.17 всё ещё описывает этот порядок. Порт RC IN через IO-процессор Pixhawk понимает SBUS/DSM/PPM/ST24/SUMD, но не CRSF: ELRS подключают к UART (TELEM2, GPS2).

### Питание: как PX4 считает напряжение, ток и остаток
Из `analog_battery.cpp`: `V = V_adc · BAT1_V_DIV`, `I = (V_adc − BAT_V_OFFS_CURR) · BAT1_A_PER_V`. Оба коэффициента стоят в числителе, поэтому калибровка — пропорция:

| Что | Формула | Чем мерить |
|---|---|---|
| Делитель | `BAT1_V_DIV_new = BAT1_V_DIV_old × V_мультиметр / V_QGC` | мультиметр на балансире или XT60 |
| Ток | `BAT1_A_PER_V_new = BAT1_A_PER_V_old × мА·ч_зарядка / мА·ч_лог` | зарядка после полёта; клещи — для проверки |

Остаток (`battery.cpp`): напряжение элемента, исправленное на нагрузку (`+ R · I`, где R — `BAT1_R_INTERNAL`, если он ≥ 0, иначе сопротивление, которое PX4 оценивает в полёте; умолчание −1, стартовая оценка 0.005 Ом на элемент; без датчика тока поправки нет), линейно интерполируется между `BAT1_V_EMPTY` (3.6 В) и `BAT1_V_CHARGED` (4.05 В). С `BAT1_CAPACITY` > 0 к этому добавляется интеграл тока; документация советует ≈ 90 % паспортной ёмкости. Пороги: `BAT_LOW_THR` 0.15, `BAT_CRIT_THR` 0.07, `BAT_EMERGEN_THR` 0.05. До 1.16 формула была другой: `BAT1_R_INTERNAL` по умолчанию 0.005 Ом, а без датчика тока прибавлялось `газ · BAT1_V_LOAD_DROP` (параметр удалён в 1.16). Действие — `COM_LOW_BAT_ACT`: 0 предупреждение (умолчание на полётнике), 2 Land, 3 Return на critical и Land на emergency.

### Газ висения и тяговооружённость
`MPC_THR_HOVER` (0.5) — стартовое значение. В полёте его уточняет оценщик тяги висения (топик `hover_thrust_estimate`; в 1.18 он включён всегда, выключатель `MPC_USE_HTE` удалён). При линейной тяге доля висения = m·g / (n·T_max) = 1/(T/W). Реальный проп даёт тягу ближе к квадрату сигнала, это учитывает `THR_MDL_FAC`: `тяга = f·s² + (1 − f)·s`.

### Что сохраняется само, что ждёт перезагрузки и что ставит airframe
Правило на каждый изменённый параметр: вход — имя параметра; решение — по таблице; проверка — значение после перезагрузки в QGC → Parameters.

| Что меняешь | Когда действует | Как проверить |
|---|---|---|
| Обычный параметр (усиления, пороги, failsafe) | сразу; на flash/SD записывается сам — автосохранение (`autosave.cpp`), отдельный `param save` не нужен | значение видно после перезагрузки |
| Порт `*_CONFIG`, `BAT1_V_DIV` / `BAT1_A_PER_V`, `SENS_EN_*`, `MC_AT_EN` | только после перезагрузки: у первых трёх в описании стоит «reboot required», `MC_AT_EN` читает стартовый скрипт `rc.mc_apps` | драйвер виден в `<модуль> status`, порт — в `dmesg` |
| `SYS_AUTOSTART` (airframe) | после Apply and Restart: `SYS_AUTOCONFIG` = 1 сбрасывает все параметры, кроме калибровок `CAL_*`, `RC*` и `COM_FLTMODE*`, затем скрипт airframe заново ставит свои умолчания | `param show SYS_AUTOSTART` — новый номер; `param show-for-airframe` печатает только отличия от умолчаний — остаются калибровки и режимы |

Подробно — хранилище, BSON, `param reset` — в `px4-console-params`.

Airframe мультиротора поверх умолчаний параметров запускает `rc.mc_defaults` (v1.17.0; в v1.18.0 из него убрана строка `NAV_ACC_RAD`). Поэтому значение «из документации параметра» на квадрокоптере не то, что ты увидишь в QGC:

| Параметр | Умолчание параметра | Ставит `rc.mc_defaults` | Где важно |
|---|---|---|---|
| `IMU_GYRO_RATEMAX` | 400 Гц | 800 Гц (только если стоит 400) | частота цикла угловой скорости, `px4-control` |
| `RTL_RETURN_ALT` | 60 м | 30 м | шаг 11 ниже; самолёту `rc.fw_defaults` ставит 100 м |
| `RTL_DESCEND_ALT` | 30 м | 10 м | высота, на которой Return переходит к посадке |
| `NAV_ACC_RAD` | 10 м | 2 м — в 1.15–1.17; в 1.18 строка убрана, у мультиротора 10 м | радиус принятия точки миссии |
| `EKF2_RNG_FOG` | 3.0 м | 1.0 м (с 1.16) | дальномер, `nav-indoor` |
| `GPS_UBX_DYNMODEL` | 7 | 6 — в 1.15 и 1.16; в 1.17 строка убрана | `px4-hardware-peripherals` |

### Что поменялось в 1.16 и 1.17 (для старых инструкций и `.params`)
Переход 1.17 → 1.18 (перехват стиками, bidirectional DShot по группам, `NAV_ACC_RAD`, `FD_ACT_EN`, `SENS_MAG_AUTOCAL`, перевод `.params` скриптом `Tools/migrate_param_file.py`) — отдельной таблицей в `px4-intro`; здесь — более ранние изменения.

Вход — инструкция или файл `.params` под 1.15; решение — по строке таблицы; проверка — параметр есть или нет в QGC → Parameters прошивки 1.17.

| Было в 1.15 | В 1.16 / 1.17 | Что делать |
|---|---|---|
| `RC_MAP_ACRO_SW`, `RC_MAP_MAN_SW`, `RC_MAP_POSCTL_SW`, `RC_MAP_RATT_SW`, `RC_MAP_STAB_SW` | удалены в 1.16 | режимы — только через `RC_MAP_FLTMODE` + `COM_FLTMODE1…6`; `RC_MAP_ARM_SW`, `RC_MAP_KILL_SW`, `RC_MAP_RETURN_SW`, `RC_MAP_LOITER_SW` остались, в 1.17 добавлен `RC_MAP_TERM_SW` |
| `COM_POS_FS_DELAY` | удалён в 1.16 | потеря позиции — `px4-safety-return` |
| `BAT1_V_LOAD_DROP`, `BAT1_R_INTERNAL` = 0.005 | `BAT1_V_LOAD_DROP` удалён в 1.16, `BAT1_R_INTERNAL` = −1 (оценка в полёте) | см. «Питание» выше |
| eRPM — только телеметрия ESC по UART (`DSHOT_TEL_CFG`) | с 1.16 bidirectional DShot: `DSHOT_BIDIR_EN`; в 1.18 — значения −6/−7/−8 в `PWM_AUX_TIMx` группы | `px4-outputs-servos`, `px4-control` |
| `EKF2_OF_CTRL` = 0 | с 1.16 умолчание 1: оптический поток сливается, как только есть датчик | `nav-indoor` |
| DShot1200 (`PWM_*_TIMx` = −2) | удалён в 1.16 | DShot600 |
| Топики ROS 2 без версии | версионные сообщения получают суффикс `_vN`: в 1.16 — `vehicle_status_v1`, в 1.17 ещё `vehicle_local_position_v1`, `battery_status_v1` и др. | `px4-ros2` |

### Место в системе

- **Получает:** порядок экранов QGC и умолчания (`px4-intro`); протокол моторов (`f-motors-esc`); приёмник ELRS и кадр CRSF (`link-elrs`, `link-protocols`).
- **Отдаёт:** занятые и свободные порты — раскладке периферии (`px4-hardware-peripherals`); функции выходов и геометрию `CA_*` — control allocation (`px4-control`); `BAT1_V_DIV` и `BAT1_A_PER_V` — оценке остатка и `COM_LOW_BAT_ACT`; свободный порт TELEM2 — companion (`px4-companion-jetson`); первый ULog — Flight Review.
- **Если ошибиться здесь:** два драйвера на одном порту — QGroundControl не запретит; при загрузке стартует только первый, второй молча не запускается (в `dmesg` строка `Conflicting config`, на платах с урезанной прошивкой её нет — `px4-hardware-peripherals`) → молчит приёмник или мост к companion (`px4-companion-jetson`). `BAT1_A_PER_V` не откалиброван по зарядке → остаток считается неверно → low-battery failsafe срабатывает не вовремя; сверка — по мА·ч зарядки и логу ULog (`px4-intro`).

## practice
### Шаг 1. Прошивка → сборка SITL (шаг 1 из 17)
Вместо прошивки — сборка SITL. Я собирал v1.15.4 в контейнере (2 ядра, 7 ГБ): `make px4_sitl_default` — 1024 цели. Python-зависимости ставил в venv по `Tools/setup/requirements.txt`, а не скриптом `ubuntu.sh`. Gazebo в контейнере нет, поэтому основной путь здесь — SIH: физика считается внутри самого PX4. С Gazebo команда та же, что в px4-intro: `make px4_sitl gz_x500`.

Вывод снят на v1.15.4; в 1.17 и 1.18 цели `sihsim_quadx` и `gz_x500` называются так же, для целевого релиза клонируй `--branch v1.18.0` (SITL v1.18.0 c `sihsim_quadx` собран и запущен при подготовке перехода на 1.18; сам вывод ниже не переснимался).
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
В QGC → Flight Modes: канал `RC_MAP_FLTMODE`, слоты `COM_FLTMODE1…6` (0 Manual, 1 Altitude, 2 Position, 4 Hold, 5 Return, 8 Stabilized; в 1.17 добавлен 16 — Altitude Cruise). Арм-тумблер — `RC_MAP_ARM_SW`, `COM_ARM_SWISBTN` = 0 (тумблер) или 1 (кнопка). Kill — `RC_MAP_KILL_SW`. Без взлёта PX4 сам снимет арм через `COM_DISARM_PRFLT` = 10 с.

### Шаг 6. Failsafe с инъекцией отказов (12, 14)
Инъекция работает при `SYS_FAILURE_EN` = 1 (в SITL — по умолчанию). `failure rc_signal off` в SIH не реализован. Вывод этого шага снят на v1.15.4; в 1.17 и 1.18 обработчика инъекции `rc_signal` в исходниках симуляторов тоже нет (батарею обрабатывает `battery_simulator`, моторы — `FailureInjector`), текст ответа может отличаться:
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
Цепочка: 0.5 с `COM_RC_LOSS_T` (плюс задержка детектора) → Hold на `COM_FAIL_ACT_T` = 5 с → `NAV_RCL_ACT` = 2 (Return) → посадка → дизарм по посадке (`COM_DISARM_LAND` = 2 с). Аппарат был в 3 м от дома, поэтому RTL не набирал `RTL_RETURN_ALT`. В 1.18 у мультиротора `NAV_ACC_RAD` = 10 м (в 1.15–1.17 — 2 м), и ближе 10 м к дому высота возврата считается как 2·d (`px4-safety-return`): число в строке `RTL: start return` будет другим.

Батарея: `failure battery off` подменяет напряжение на 3.6 В/эл (14.4 В). С умолчаниями 1.15 (`BAT_CRIT_THR` 0.07) в висении приходит только LOW: компенсация нагрузки `BAT1_V_LOAD_DROP` добавляет 0.49 × 0.1 = 0.049 В, остаток (3.649 − 3.6)/0.45 = 0.109. В 1.17 и 1.18 этого параметра нет (поправка — `R · I` по току), а SITL сам ставит `COM_LOW_BAT_ACT` = 3, поэтому уровни и времена на 1.17 и 1.18 будут другими — журнал ниже снят на v1.15.4. В 1.18 значение 3 включает ещё и возврат по остатку времени полёта, но в SITL `BAT1_CAPACITY` = −1 (проверено `param show` на v1.18.0), оценки времени нет, и он не срабатывает. Для теста я поставил `COM_LOW_BAT_ACT 3`, `BAT_CRIT_THR 0.12`, `BAT_LOW_THR 0.20`:
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

Autotune: Position на 2.5 м, `MAV_CMD_DO_AUTOTUNE_ENABLE` (в QGC — PID Tuning → Autotune). По `autotune_attitude_control_status` идентификация заняла 26 с (35.4 → 61.2 с от арма), коэффициенты применились после дизарма (`MC_AT_APPLY` = 1). Таблица снята на v1.15.4: стартовое `MC_ROLL_P` там 6.5, в 1.17 умолчание — 4.0:

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
3. **Порты.** GPS — GPS1 (`GPS_1_CONFIG`), телеметрия — TELEM1 (`MAV_0_CONFIG`). Для ELRS на TELEM2: проверить, что `MAV_1_CONFIG` = Disabled (это умолчание; если TELEM2 был отдан companion — выключить), затем `RC_CRSF_PRT_CFG` = TELEM 2 (`crsf_rc`; default-сборка fmu-v6x в 1.17) или `RC_PORT_CONFIG` = TELEM 2 (`rc_input`; fmu-v6x до 1.17, fmu-v5), перезагрузка. TX контроллера идёт на RX приёмника, RX — на TX.
4. **Приёмник.** Бинд и packet rate — по link-elrs. Проверка: Radio — все ползунки двигаются, каналов ≥ 8.
5. **Калибровка радио.** QGC → Radio → Calibrate: пишутся `RC1_MIN/TRIM/MAX`…, `RC_MAP_*`. Норма — около 1000/1500/2000 мкс. Потом режимы и арм/kill из шага 5 SITL.
6. **Протокол.** Actuators: моторы на выходах FMU. На Pixhawk с IO DShot работает только на AUX, MAIN идёт через IO. Группа таймера → DShot600 (если ESC умеет) или PWM 400 Гц.
7. **Порядок и направление.** Слайдеры по одному на 10–15 %. Номер мотора — по таблице шага 2, направление — по стрелкам схемы. Неверное направление у DShot: `dshot reverse -m 2`, затем `dshot save -m 2`; у PWM — поменять два фазных провода. Disarmed — мотор стоит, minimum — едва крутится.
8. **Калибровка ESC (только PWM/OneShot).** FC от USB, АКБ отключена, QGC → Power → Calibrate, подключить АКБ по подсказке. Калибровка идёт по 1000/2000 мкс. После назначения функции Motor в Actuators драйвер сам записывает min/max = 1100/1900 мкс (умолчание параметров — 1000/2000); disarmed остаётся 1000 мкс. DShot калибровать не нужно. Пределы задаются на каждый выход отдельно: `PWM_MAIN_MINn` / `PWM_MAIN_MAXn` / `PWM_MAIN_DISn` / `PWM_MAIN_FAILn` (на AUX — `PWM_AUX_*`); правило «minimum поднимаешь, пока мотор не начнёт едва крутиться, на всех моторах одинаково» и разбор для серв — в `px4-outputs-servos`.
9. **Датчики.** Accelerometer (6 положений), Gyroscope (неподвижно), Compass (вращение, вдали от железа), Level Horizon (на ровной поверхности).
10. **Питание.** QGC → Power: `BAT1_N_CELLS` 4, `BAT1_V_EMPTY` 3.6, `BAT1_V_CHARGED` 4.05. Напряжение: QGC показывает 16.42 В, мультиметр — 16.71 В, `BAT1_V_DIV` 18.000 → 18.000 × 16.71 / 16.42 = 18.318 (ошибка была 0.072 В/эл). Кнопка Calculate в QGC считает ту же пропорцию. Умолчание `BAT1_V_DIV` и `BAT1_A_PER_V` в самом параметре — −1 («значение платы»): число ставит скрипт платы `rc.board_defaults` (fmu-v6c — 18.1 и 36.37), код `analog_battery.cpp` подстановки не делает. Если в QGC видишь −1, плата аналоговый делитель не задала — введи коэффициент из паспорта силового модуля, затем калибруй пропорцией; оба параметра требуют перезагрузки. Ток проверяется после первого полёта: в логе 2310 мА·ч, зарядка залила 2465 → `BAT1_A_PER_V` 36.0 × 2465 / 2310 = 38.416. `BAT1_CAPACITY` = 4500.
11. **Failsafe.** `COM_LOW_BAT_ACT` = 3 (в 1.18 с заданной на шаге 10 `BAT1_CAPACITY` это ещё и возврат по остатку времени полёта: Return может начаться раньше уровня critical; не нужен — 5), `NAV_RCL_ACT` = 2, `RTL_RETURN_ALT` выше препятствий (airframe мультиротора ставит 30 м, `RTL_DESCEND_ALT` 10 м; 60 м — умолчание самого параметра), `GF_ACTION` по задаче (умолчание 2 = Hold). Геозона по радиусу выключена, пока `GF_MAX_HOR_DIST` = 0 (и `GF_MAX_VER_DIST` = 0): для первого полёта поставь радиус и высоту с запасом над зоной полётов, например 150 м и 60 м. Потеря связи с QGC `NAV_DLL_ACT` = 0 — выключено. Решение: летаешь с пульта, телеметрия только для наблюдения — оставь 0 (иначе обрыв SiK-радио на краю зоны вызовет Return при живом пульте); летаешь миссию без пульта, QGC — единственный канал — ставь 2 (Return) после `COM_DL_LOSS_T` = 10 с. Вся матрица — в `px4-safety-return`. На столе без пропов и без арма: выключить пульт → в QGC сообщение о потере ручного управления, в консоли `listener failsafe_flags` → `manual_control_signal_lost: True`.
12. **OSD и телеметрия.** MSP OSD — `MSP_OSD_CONFIG` на свободный UART, если драйвер есть в сборке платы. В default-сборках v1.17.0 `msp_osd` есть у px4 fmu-v5x, fmu-v6x, fmu-v6xrt, ark fpv, cuav 7-nano, cuav fmu-v6x, cuav x25-evo, micoair h743 / h743-aio / h743-v2, radiolink PIX6, hkust nxt-dual, zeroone x6, accton-godwit ga1, nxp tropic-community и mr-tropic, modalai voxl2 (и SITL); в v1.18.0 к ним добавились новые платы aedrox aedroxh7, corvon 743v2, cuav x25-mega и x25-super, gearup airbrainh743, svehicle e2; в 1.15.4 — только fmu-v5x, fmu-v6x, fmu-v6xrt и voxl2 (и SITL). У fmu-v6c и fmu-v5 его нет: нет параметра `MSP_OSD_CONFIG` → нужна своя сборка (`px4-console-params`); с 1.16 драйвер шлёт MSP DisplayPort (до 1.16 — элементы DJI legacy MSP), совместимость с конкретными очками PX4 не документирует. Иначе телеметрия на пульте через CRSF (`RC_CRSF_TEL_EN`).
13. **Предполётная проверка и висение.** Пропы — по схеме CW/CCW. GPS ≥ 10 спутников, «Ready to fly», kill-тумблер под пальцем, 10 м до людей. Взлёт в Position, 2–3 м, 60 с висения, по 2 м в стороны, посадка. Прерывай (kill или Land), если: раскачка больше ±5°, дрейф больше 1 м при отпущенных стиках, «toilet bowl» (раскрутка по кругу — компас), газ висения выше 0.7.
14. **Тест failsafe в воздухе.** Position на 10 м, пульт выключить → Hold 5 с → Return. Включить пульт, сменой режима перехватить.
15. **Autotune.** Сначала `MC_AT_EN` = 1 и перезагрузка: на полётнике умолчание 0 и модуль не запущен, а SITL ставит 1 сам. Altitude, 4–20 м, штиль. Порядок — как в шаге 7 SITL, но фильтры и вибрации заранее проверены по px4-control.
16. **Лог и бэкап.** ULog в Flight Review: вибрации, газ висения, RC и батарея. `.params` из QGC — в репозиторий аппарата.

Самопроверка: лабораторная выполнена, когда:
- **SITL:** таблица моторов (номер, позиция, KM) совпадает с `CA_ROTOR*`; в журнале есть цепочка RC loss → Hold → Return → дизарм и battery → Hold → Return → Land с временами; HTE совпал с расчётом 1/(T/W) в пределах 0.01; таблица autotune до/после заполнена (в SIH `MC_ROLLRATE_D` после тюна около нуля — модель без задержек и шума) и сохранён вывод `param show-for-airframe`.
- **Железо:** экспортированный `.params`; таблица теста моторов совпадает с геометрией airframe; ошибка напряжения < 0.05 В/эл; мА·ч по логу в пределах 5 % от зарядки после правки `BAT1_A_PER_V`; RC loss и low battery видны в ULog (`failsafe_flags`, смена `nav_state`); отчёт Flight Review первого 60-секундного висения в Position.

## diagnostics
- **Симптом:** ELRS приёмник светится «связь есть», а в QGC Radio каналы не двигаются
  - Возможная причина: приёмник подключён к RC IN через IO (CRSF там не разбирается), порт занят MAVLink (`MAV_1_CONFIG`) или перепутаны TX/RX.
  - Что сделать: UART + `RC_PORT_CONFIG` или `RC_CRSF_PRT_CFG`, освободить порт, перезагрузка; в MAVLink Console — `rc_input status` или `crsf_rc status`.
- **Симптом:** `RC_CRSF_PRT_CFG` нет в списке параметров
  - Возможная причина: драйвер `crsf_rc` не собран для этой платы (до 1.17 — обычное дело; в 1.17 и 1.18 в fmu-v6x он есть, а нет уже `RC_PORT_CONFIG`).
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
  - Возможная причина: эта инъекция в симуляторах не обрабатывается (ответ снят на 1.15.4; в исходниках 1.17 и 1.18 обработчика тоже нет).
  - Что сделать: имитировать потерю, прекратив `MANUAL_CONTROL` (джойстик QGC или скрипт).

## references
- PX4 User Guide v1.17 — Actuator Configuration and Testing | https://docs.px4.io/v1.17/en/config/actuators.html | primary | A
- PX4 User Guide v1.17 — ESC Calibration | https://docs.px4.io/v1.17/en/advanced_config/esc_calibration.html | primary | A
- PX4 User Guide v1.17 — Battery Estimation Tuning | https://docs.px4.io/v1.17/en/config/battery.html | primary | A
- PX4 User Guide v1.17 — Serial Port Configuration | https://docs.px4.io/v1.17/en/peripherals/serial_configuration.html | primary | A
- PX4 User Guide v1.17 — CRSF Telemetry (TBS Crossfire / ExpressLRS) | https://docs.px4.io/v1.17/en/telemetry/crsf_telemetry.html | primary | A
- PX4 User Guide v1.17 — DShot ESCs | https://docs.px4.io/v1.17/en/peripherals/dshot.html | primary | A
- PX4 User Guide v1.15 — Safety Configuration (Failsafes) | https://docs.px4.io/v1.15/en/config/safety.html | primary | A
- PX4 User Guide v1.17 — System Failure Injection | https://docs.px4.io/v1.17/en/debug/failure_injection.html | primary | A
- PX4 User Guide v1.17 — Multicopter Auto-Tuning | https://docs.px4.io/v1.17/en/config/autotune_mc.html | primary | A
- PX4 User Guide v1.17 — Simulation-In-Hardware (SIH) | https://docs.px4.io/v1.17/en/sim_sih/ | primary | A
- PX4-Autopilot v1.17.0 — analog_battery.cpp (V_DIV, A_PER_V) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/battery_status/analog_battery.cpp | primary | A
- PX4-Autopilot v1.17.0 — battery.cpp (state of charge) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/lib/battery/battery.cpp | primary | A
- QGroundControl User Guide — Power Setup | https://docs.qgroundcontrol.com/Stable_V4.3/en/qgc-user-guide/setup_view/power.html | primary | A
- PX4 User Guide v1.17 — Radio Control Systems | https://docs.px4.io/v1.17/en/getting_started/rc_transmitter_receiver.html | primary | B

## checklist
- Сборка SITL работает, QGC подключена
- Геометрия `CA_ROTOR*` и тест моторов совпадают с рамой
- Порты освобождены и назначены через `*_CONFIG`, перезагрузка сделана
- ELRS на UART, каналы двигаются в Radio, калибровка радио сделана
- DShot на FMU-выходах или PWM ESC откалиброваны
- `BAT1_V_DIV` и `BAT1_A_PER_V` откалиброваны по мультиметру и зарядке
- RC loss и low battery проверены в SITL и на столе
- Первое висение в Position записано, лог в Flight Review, `.params` сохранён
