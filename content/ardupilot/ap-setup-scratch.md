---
id: ap-setup-scratch
title: "ArduPilot с нуля: Copter через Mission Planner / QGC"
level: L2
readingTime: 55 мин
firmware: ArduCopter 4.6 (проверено на Copter-4.6.3, SITL)
status: published
tags:
  - ArduPilot
  - настройка с нуля
  - калибровка
  - Mission Planner
  - SITL
related:
  - ap-intro
  - ap-sitl
  - ap-safety-fs
  - ap-tuning
  - ap-logs
  - ap-ekf
  - link-elrs
  - f-motors-esc
next:
  - ap-tuning
---

## summary
Один квадрокоптер от пустого полётного контроллера до записанного в лог первого висения, в порядке 17 шагов настройки: прошивка с загрузчиком, карта портов `SERIALn_PROTOCOL`, ELRS-приёмник (`SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS`), калибровка радио, DShot или PWM с калибровкой ESC, Motor Test и `MOT_SPIN_ARM/MIN`, акселерометр и компас, калибровка датчика АКБ по мультиметру и зарядке, OSD, failsafe, висение Stabilize → AltHold → Loiter, `MOT_THST_HOVER`, QuikTune/AutoTune и бэкап `.param`. Основной путь — SITL (`sim_vehicle.py`, всё ниже прогнано на Copter-4.6.3), шаги, которых в симуляторе нет, — на столе без пропов и в поле. Лабораторная: `.param` до и после, лог висения с `MOT_THST_HOVER` 0.2–0.5 и записанные RC- и battery-failsafe.

## theory
### Что считаем аппаратом
Пример по всему модулю: квадрик X на 7" пропах, 1.4 кг, 6S LiPo 4000 мА·ч, H7-полётник с барометром и SD-картой, 4-в-1 ESC на BLHeli32/AM32, ELRS-приёмник, GPS с компасом на мачте, аналоговое видео. Тяга мотора 2806.5 с пропом 7×3.5 — около 1200 г (модуль f-aero-props), T/W ≈ 4 × 1.2 / 1.4 = 3.4, ожидаемый газ висения `MOT_THST_HOVER` ≈ 1/3.4 ≈ 0.29.

Версия: ArduCopter 4.6. Имена, которые в 4.7 переименованы (модуль ap-intro): `ARMING_CHECK` (в 4.7 — `ARMING_SKIPCHK`), `RTL_ALT` в см (`RTL_ALT_M`), `PSC_ACCZ_P/I` (`PSC_D_ACC_P/I`, значения ×0.1).

### 17 шагов и где каждый делается
| # | Шаг | Что в ArduCopter 4.6 | Где | Подробно |
|---|---|---|---|---|
| 1 | Прошивка, бэкап | `_with_bl.hex` по DFU, дальше `.apj`; `.param` до изменений | стол, SITL | этот модуль |
| 2 | Рама, ориентация | `FRAME_CLASS`, `FRAME_TYPE`, `AHRS_ORIENTATION` | SITL | ap-intro |
| 3 | Порты | `SERIALn_PROTOCOL`: 2 MAVLink2, 5 GPS, 23 RCIN, 16 ESC-телеметрия, 42 DisplayPort | SITL | этот модуль |
| 4 | Приёмник | `SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS`, `RC_OPTIONS`, `RSSI_TYPE = 3`, bind | стол | link-elrs |
| 5 | Каналы | `RCMAP_*`, калибровка `RCn_MIN/MAX/TRIM` | стол | этот модуль |
| 6 | Протокол моторов | `MOT_PWM_TYPE`, `SERVO_DSHOT_ESC`, `SERVO_BLH_*` | SITL, стол | f-motors-esc |
| 7 | Порядок, направление | Motor Test A–D, `SERVO_BLH_RVMASK` | SITL, стол | этот модуль |
| 8 | ESC, холостые | `ESC_CALIBRATION` (только PWM), `MOT_SPIN_ARM/MIN` | стол | этот модуль |
| 9 | Accel, компас | 6 положений, Onboard Mag Calibration | стол (SITL) | ap-ekf |
| 10 | Датчик АКБ | `BATT_MONITOR`, `BATT_VOLT_MULT`, `BATT_AMP_PERVLT`, `BATT_AMP_OFFSET` | SITL, стол | этот модуль |
| 11 | Режимы, арм | `FLTMODE_CH`, `FLTMODE1..6`, `RCx_OPTION`, pre-arm | SITL | ap-intro |
| 12 | Failsafe | `FS_THR_ENABLE/VALUE`, `BATT_FS_LOW_ACT/CRT_ACT` | SITL, стол | ap-safety-fs |
| 13 | OSD | `OSD_TYPE`: 1 MAX7456, 5 MSP DisplayPort | стол | этот модуль |
| 14 | GPS, дом, RTL | `GPS1_TYPE`, `RTL_ALT` | SITL | ap-ekf |
| 15 | Первое висение | Stabilize → AltHold → Loiter, `MOT_HOVER_LEARN = 2` | SITL → поле | этот модуль |
| 16 | Первый тюн | notch, QuikTune или AutoTune | поле | ap-tuning |
| 17 | Лог и бэкап | `.BIN`, `.param`, сравнение файлов | SITL, поле | ap-logs |

{{diagram:ap-setup-flow|17 шагов настройки ArduCopter 4.6: SITL проходит больше половины цепочки, а bind, калибровки радио и ESC, OSD и тюн существуют только на железе — и пропы появляются только на шаге 15.}}

### Загрузчик и два формата файла
ArduPilot на ChibiOS ставится в два этапа. Первый раз на плате нет загрузчика ArduPilot (стоит Betaflight или завод), поэтому пишут `arducopter_with_bl.hex` — загрузчик плюс прошивка — через DFU: зажать BOOT, вставить USB, STM32CubeProgrammer. Файл `.apj` этим путём не прошить: его понимает только загрузчик ArduPilot. Все следующие обновления — `.apj` через Mission Planner (Install Firmware или Load custom firmware) или QGroundControl (Vehicle Setup → Firmware, плату вставлять после открытия вкладки). Файлы лежат на firmware.ardupilot.org в папке Copter → stable-4.6.x → имя платы, совпадающее с её hwdef. DFU-загрузчик STM32 зашит в ПЗУ, поэтому вернуться на Betaflight можно тем же DFU; перед прошивкой сохрани `diff all` из Betaflight CLI.

### Калибровки, которые считаются формулами
Аналоговый датчик АКБ в `AP_BattMonitor_Analog.cpp`: V = (V_pin − `BATT_VLT_OFFSET`) × `BATT_VOLT_MULT`, I = (V_pin − `BATT_AMP_OFFSET`) × `BATT_AMP_PERVLT`. Отсюда:

- новый `BATT_VOLT_MULT` = старый × V_мультиметр / V_GCS;
- новый `BATT_AMP_OFFSET` = старый + I₀ / `BATT_AMP_PERVLT`, где I₀ — показание при нулевом токе;
- новый `BATT_AMP_PERVLT` = старый × I_клещи / I_GCS = старый × мА·ч_зарядки / мА·ч_полётника.

Сначала ноль, потом наклон: масштаб, подобранный при неверном нуле, верен только в одной точке.

{{diagram:chart-ap-batt-cal|Разобранный пример: датчик реально даёт 0.0125 В + I/44 А/В. С заводскими 0 В и 40 А/В GCS показывает 0.50 А в покое и 9.59 А при 10 А на клещах; смещение 0.0125 В убирает ноль (9.09 А), масштаб 40 × 10/9.09 = 44 даёт точные 10.0 А.}}

Моторы: выход = `MOT_SPIN_MIN` + (`MOT_SPIN_MAX` − `MOT_SPIN_MIN`) × r, где r — тяга после линеаризации `MOT_THST_EXPO`; PWM = `MOT_PWM_MIN` + выход × (`MOT_PWM_MAX` − `MOT_PWM_MIN`). `MOT_THST_HOVER` (0.125–0.6875, по умолчанию 0.35) — тяга висения в долях от максимальной, поэтому ≈ 1 / (T/W). Значение 0.2–0.5 соответствует T/W от 5 до 2: ниже — газ слишком «резкий», выше — нет запаса на манёвр и ветер.

## practice
Запуск SITL для всего раздела (модуль ap-sitl объясняет установку). Рама `-f X` — это Quad X; `-f quad` в 4.6 даёт Plus (`FRAME_TYPE = 0`), не перепутай.

```bash
sim_vehicle.py -v ArduCopter -f X --console --map -w
# Mission Planner / QGC: UDP 14550 (MAVProxy отдаёт туда сам)
# без MAVProxy, для своего скрипта: sim_vehicle.py -v ArduCopter -f X -w --no-mavproxy  -> tcp:127.0.0.1:5760
```

Все выводы ниже — из прогона скрипта на pymavlink (команды те же, что кнопки Mission Planner) против SITL, собранного из тега Copter-4.6.3: сборка `./waf copter` на 2 ядрах — 12 мин 24 с.

### Шаг 1. Прошивка и бэкап
В SITL прошивка — это сборка; на железе — DFU и `_with_bl.hex` (см. теорию). Сразу после первого подключения сохрани полный список: Mission Planner → Config → Full Parameter List → Save, QGC → Parameters → Tools → Save to file, MAVProxy `param save 00_defaults.param`.

```text
== step 1: backup
params received: 1397 of 1397
  FRAME_CLASS = 1        FRAME_TYPE = 1        MOT_PWM_TYPE = 0
  SERIAL2_PROTOCOL = 2   RC_PROTOCOLS = 1      RC_OPTIONS = 32
  BATT_MONITOR = 4       BATT_VOLT_MULT = 10.1 BATT_AMP_PERVLT = 17
  FS_THR_ENABLE = 1      FS_THR_VALUE = 975    BATT_FS_LOW_ACT = 0
```

`BATT_FS_LOW_ACT = 0` по умолчанию: низкая АКБ только пищит. Запиши это — на шаге 12 исправим.

### Шаг 2. Рама и ориентация
`FRAME_CLASS = 1` (Quad), `FRAME_TYPE = 1` (X); для рам с порядком моторов Betaflight — `FRAME_TYPE = 12` (BetaFlightX). `AHRS_ORIENTATION` — если плата повёрнута стрелкой не вперёд. Оба параметра рамы требуют перезагрузки.

### Шаг 3. Карта портов
`SERIALn` — логический номер, к физическому UARTx его привязывает hwdef платы (таблица UART в описании платы на ardupilot.org). Типичная раскладка для примера: SERIAL0 — USB, SERIAL1 — телеметрия (2, MAVLink2), SERIAL3 — GPS (5), SERIAL4 — DisplayPort (42) или ESC-телеметрия (16), SERIAL6 — приёмник (23). Протокол порта применяется после перезагрузки.

### Шаг 4. Приёмник ELRS
Порт: `SERIALn_PROTOCOL = 23` (RCIN), скорость не трогаем — прошивка выставляет её сама. `RC_PROTOCOLS = 512` (бит 9, CRSF; 1 = автоопределение всех) убирает ложное определение. `RC_OPTIONS` = 32 (по умолчанию) + 512 (бит 9, не ругаться на rate ELRS) + 8192 (бит 13, 420 кбод для ELRS) = 8736. `RSSI_TYPE = 3` — RSSI/LQ из протокола.

```text
  set SERIAL2_PROTOCOL = 23   set RC_PROTOCOLS = 512   set RC_OPTIONS = 8736   set RSSI_TYPE = 3
  after reboot SERIAL2_PROTOCOL = 23   RC_PROTOCOLS = 512   RC_OPTIONS = 8736
```

SITL подаёт RC по своему каналу, поэтому после проверки верни `RC_PROTOCOLS = 1`, `SERIAL2_PROTOCOL = 2`. Bind и проверка связи — только железо (link-elrs).

### Шаг 5. Каналы и калибровка радио
В SITL каналы уже откалиброваны (`RC1..8_MIN/MAX` = 1000/2000 в стандартных параметрах), шаг делается на железе: Mission Planner → Radio Calibration или QGC → Radio, все стики и тумблеры в крайние положения, затем центр. Порядок каналов по умолчанию AETR (`RCMAP_ROLL/PITCH/THROTTLE/YAW` = 1/2/3/4).

### Шаг 6. Протокол моторов
`MOT_PWM_TYPE`: 0 Normal (PWM), 1 OneShot, 2 OneShot125, 4/5/6/7 — DShot150/300/600/1200, перезагрузка обязательна. Для DShot: `SERVO_DSHOT_ESC = 1` (BLHeli32/AM32/Kiss) или 2 (BLHeli_S/Bluejay), `SERVO_BLH_AUTO = 1` (passthrough для BLHeliSuite/ESC Configurator на всех моторах), двунаправленный DShot — `SERVO_BLH_BDMASK` (битовая маска выходов, 15 = выходы 1–4) и `SERVO_BLH_POLES` (по умолчанию 14). В SITL параметр принимается, но `SERVO_BLH_*` в сборке нет:

```text
  set MOT_PWM_TYPE = 6   set SERVO_DSHOT_ESC = 1
  SERVO_BLH_AUTO: no such parameter in the SITL build (no BLHeli pass-through)
  after reboot MOT_PWM_TYPE = 6
```

Выходы одной таймерной группы должны быть одного типа: DShot и PWM в одной группе не смешиваются.

### Шаг 7. Порядок моторов — Motor Test
Буквы Motor Test идут по часовой стрелке от первого мотора справа от носа, а не по номерам выходов. Для Quad X номера моторов: 1 — передний правый (CCW), 2 — задний левый (CCW), 3 — передний левый (CW), 4 — задний правый (CW). Тест 10 % на 2 с (`MAV_CMD_DO_MOTOR_TEST`; MAVProxy `motortest 1 0 10 2`):

```text
  idle SERVO1-4 = [1000, 1000, 1000, 1000]
  seq 1 (A): ack 0, SERVO1-4 = [1100, 1000, 1000, 1000] -> output [1]
  seq 2 (B): ack 0, SERVO1-4 = [1000, 1000, 1000, 1100] -> output [4]
  seq 3 (C): ack 0, SERVO1-4 = [1000, 1100, 1000, 1000] -> output [2]
  seq 4 (D): ack 0, SERVO1-4 = [1000, 1000, 1100, 1000] -> output [3]
```

A → выход 1, B → 4, C → 2, D → 3: по кругу передний правый → задний правый → задний левый → передний левый. 10 % газа = 1000 + 0.10 × 1000 = 1100 мкс. Запиши таблицу «кнопка → выход → позиция → направление»: на железе её заполняешь глазами.

### Шаг 8. Холостые обороты: MOT_SPIN_ARM и MOT_SPIN_MIN
Заармили в Stabilize с газом в ноль:

```text
  armed=True, throttle stick low: SERVO1-4 = [1100, 1100, 1100, 1100]
```

Это `MOT_PWM_MIN` + `MOT_SPIN_ARM` × (2000 − 1000) = 1000 + 0.10 × 1000. Реальные значения подбираются на столе по порогу трогания (см. железо). Калибровка ESC в SITL не существует.

### Шаг 9. Акселерометр и компас
В SITL датчики «откалиброваны» стандартными параметрами; MAVProxy умеет `accelcal` и `magcal`, но учиться этому лучше на плате — USB достаточно, АКБ не нужна.

### Шаг 10. Датчик АКБ
SITL моделирует датчик 3DR Power Brick: V_pin = V / 10.1, I_pin = I / 17. Значит, неверный множитель виден так же, как на железе. В висении (ток есть только с моторами):

```text
  SIM_BATT_VOLTAGE = 12.6 V; GCS: 12.600 V, 28.10 A
  BATT_VOLT_MULT 11.0 -> GCS 13.722 V; new = 11.0 * 12.6 / 13.722 = 10.101
  BATT_VOLT_MULT 10.1 -> GCS 12.600 V
  current in hover: PERVLT 17 -> 28.10 A, 20 -> 33.09 A, back to 17 -> 28.10 A
```

Показание напряжения и тока прямо пропорционально множителю (33.09 / 28.10 = 1.178 ≈ 20/17), формула из теории сходится до третьего знака. Запиши «эталон» (здесь `SIM_BATT_VOLTAGE`), показание, расчёт и проверку.

### Шаг 11. Режимы и арм
`FLTMODE_CH = 5`, границы позиций 1230/1360/1490/1620/1749 мкс. Трёхпозиционный тумблер даёт ≈ 1000/1500/2000 мкс, то есть позиции 1, 4 и 6 — поэтому ставь парами: `FLTMODE1 = FLTMODE2 = 0` (Stabilize), `FLTMODE3 = FLTMODE4 = 2` (AltHold), `FLTMODE5 = FLTMODE6 = 5` (Loiter). Арм — тумблером `RCx_OPTION = 153` (ArmDisarm) или стиком (`ARMING_RUDDER = 2`); аварийный стоп — `RCx_OPTION = 31` (Motor Emergency Stop). `ARMING_CHECK = 1` не трогать.

### Шаг 12. Failsafe
RC: `FS_THR_ENABLE = 1` (RTL), `FS_THR_VALUE = 975`, `RC_FS_TIMEOUT = 1` с. АКБ для SITL: `BATT_LOW_VOLT = 11.0`, `BATT_LOW_TIMER = 5`, `BATT_FS_LOW_ACT = 2` (RTL). Ловушка SITL: RC-override от GCS или скрипта считается живым RC и маскирует `SIM_RC_FAIL` — отпусти override, он истекает через `RC_OVERRIDE_TIME` = 3 с.

```text
== step 12: RC failsafe (SIM_RC_FAIL=1) in Loiter
  mode after 1.7 s: RTL; texts: ['Radio Failsafe']
  alt 8 s into RTL: 12.6 m (RTL_ALT = 1500 cm)
  RC restored, texts: ['Radio Failsafe Cleared']
== step 12: battery failsafe in Loiter
  mode RTL; texts: ['Battery 1 is low 10.80V used 917 mAh', 'Battery Failsafe']
  disarmed after 29 s more
```

На земле тот же `SIM_RC_FAIL = 1` дал «Radio Failsafe - Disarming»: заармленный аппарат на земле при потере RC сразу дизармится — это и проверяют на столе. Полная матрица отказов — модуль ap-safety-fs.

### Шаг 13. OSD
`OSD_TYPE = 1` для MAX7456 (аналог), 5 — MSP DisplayPort (DJI O3, Walksnail, HDZero) вместе с `SERIALn_PROTOCOL = 42` на порту VTX; `OSD_CHAN` — канал переключения экранов, `OSDn_ENABLE` — дополнительные экраны. Окно OSD в SITL требует сборки с SFML (`sim_vehicle.py --osd`), поэтому здесь только параметр, проверка — на очках.

### Шаг 14. GPS и RTL
В SITL GPS есть сразу (`GPS1_TYPE = 1`): дождись «EKF3 IMU0 is using GPS» — без этого не включится Loiter. `RTL_ALT` в 4.6 в сантиметрах: 1500 = 15 м; выше самых высоких препятствий площадки.

### Шаг 15. Висение Stabilize → AltHold → Loiter
```text
  Stabilize liftoff: throttle stick 1510 us, alt 1.0 m, SERVO1-4 [1622, 1622, 1621, 1622]
  AltHold 20 s, stick centred: 6.7 -> 6.7 m
  Loiter 30 s: alt 6.7 m, SERVO1-4 [1591, 1590, 1590, 1591], MOT_THST_HOVER = 0.361
  MOT_THST_HOVER after flight = 0.429
```

В AltHold высота не ушла ни на 0.1 м, `MOT_THST_HOVER` обучается сам (`MOT_HOVER_LEARN = 2`): 0.39 → 0.361 в Loiter и 0.429 к концу полёта на просевшей до 10.8 В АКБ. Проверка формулы: при 0.361 и `MOT_THST_EXPO` 0.65 r = 0.523, выход 0.15 + 0.8 × 0.523 = 0.569, PWM ≈ 1569 мкс против 1590 в логе — разницу дают компенсация напряжения (`MOT_BAT_VOLT_MAX` = 12.8 в SITL) и манёвры удержания. Первая попытка этого прогона разбилась: override газа истёк через 3 с, в AltHold «газ в ноль» означает снижение с максимальной скоростью — «SIM Hit ground at 2.49 m/s».

### Шаг 16. Первый тюн
В SITL тюн бессмыслен: нет вибраций (`VIBE` = 0), PID не переносятся на реальный аппарат (ap-sitl). Порядок на железе — ap-tuning; кратко ниже.

### Шаг 17. Лог и .param
```text
VIBE p95 X/Y/Z: 0.0 / 0.0 / 0.0 m/s^2, clip total 0
CTUN.ThH in flight: first 0.390, last 0.429; MOT_THST_HOVER in log 0.429
events:
    141.6 s  ERR Subsys=5 ECode=1      141.6 s  MODE RTL (reason 3)
    151.9 s  ERR Subsys=5 ECode=0      167.8 s  ERR Subsys=6 ECode=1
    167.8 s  MODE RTL (reason 4)
```

ERR Subsys 5 — радио, 6 — АКБ; MODE reason 3 и 4 — RADIO_FAILSAFE и BATTERY_FAILSAFE. Курсовой проверяльщик `check_lab_log.py --lab failsafe` на этом логе: PASS (реакция 0.0 с). `--lab hover` дал FAIL по просадке АКБ (13.72 → 10.80 В) — её устроили мы сами в шагах 10 и 12, поэтому висение для зачёта пиши отдельным чистым логом. Второй `.param` после настройки и сравнение с первым (Mission Planner → Compare Params или `diff` двух файлов) — это и есть «diff all» ArduPilot.

### Переход на реальное железо
Пропы сняты до пункта 11. АКБ подключать только когда пункт этого требует, полётник — на USB.

1. **Прошивка.** Сохранить `diff all` из Betaflight. DFU, `arducopter_with_bl.hex` для своей платы, STM32CubeProgrammer. Mission Planner видит плату → сохранить `00_defaults.param`.
2. **Рама и порты.** `FRAME_CLASS = 1`, `FRAME_TYPE = 1` или 12; `SERIALn_PROTOCOL` по таблице UART платы; перезагрузка; Mission Planner → Messages без ошибок.
3. **Приёмник.** `SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS = 512`, `RC_OPTIONS = 8736`, `RSSI_TYPE = 3`. Bind (фраза ELRS или режим bind), пульт включать раньше приёмника. Radio Calibration: стики двигаются в нужную сторону, концы ≈ 988…2012 мкс у ELRS. Выключить пульт: каналы замирают, Mission Planner показывает failsafe; газ при выключенном пульте должен быть хотя бы на 10 мкс ниже `FS_THR_VALUE`, при включённом и стике вниз — хотя бы на 10 мкс выше.
4. **Протокол моторов.** DShot: `MOT_PWM_TYPE = 6`, `SERVO_DSHOT_ESC`, `SERVO_BLH_AUTO = 1`, перезагрузка — калибровка ESC не нужна, диапазон фиксирован. PWM-ESC: `MOT_PWM_TYPE = 0` и калибровка ESC: `ESC_CALIBRATION = 3`, отключить USB и АКБ, подключить АКБ, нажать safety (если есть), дождаться мелодии и писков по числу банок, отключить АКБ. Альтернатива из документации: газ вверх, подключить АКБ, переподключить, газ вниз после двух писков.
5. **Motor Test** с АКБ, 10 % (если не крутится — 15 %): A–D по часовой от переднего правого, направления CCW/CW по схеме рамы. Неверное направление: DShot — `SERVO_BLH_RVMASK` или ESC Configurator, PWM — поменять два провода мотора. Неверная позиция — `SERVOn_FUNCTION` (33–36 = Motor1–4) или перепайка, но не «поменять букву».
6. **Холостые.** В Motor Test поднимать % до уверенного старта всех четырёх: порог 6 % → `MOT_SPIN_ARM` = (6 + 2)/100 = 0.08, `MOT_SPIN_MIN` ≥ `MOT_SPIN_ARM` + 0.03 = 0.11. Заармить без пропов: все моторы крутятся ровно, никакой не стоит.
7. **Accel и компас.** Accel Calibration — 6 положений + Calibrate Level на ровном столе. Onboard Mag Calibration на улице, вдали от машин и арматуры: вращать, пока все стороны не смотрели вниз, Fitness по умолчанию, три восходящих тона, перезагрузка. Внутренний компас при мачтовом — `COMPASS_USE2 = 0` (или `COMPASS_USE3`), если он мешает. CompassMot — позже, с перевёрнутыми пропами и закреплённым аппаратом: < 30 % хорошо, 31–60 % серая зона, > 60 % переносить компас.
8. **Датчик АКБ.** `BATT_MONITOR = 4`, пины и масштабы — по описанию платы. (а) Ноль: USB, АКБ отключена, GCS показывает I₀ → `BATT_AMP_OFFSET` = старый + I₀/`BATT_AMP_PERVLT`. (б) Напряжение: АКБ, мультиметр на балансире; Mission Planner → Battery Monitor → Measured Battery Voltage или формула; цель — ошибка < 0.02 В на банку (0.12 В на 6S). (в) Ток: клещи на силовом проводе при ~10 А (Motor Test 30–40 % без пропов не даст 10 А — бери висение и сверку по мА·ч). (г) мА·ч: после полёта сравнить `BAT.CurrTot` с числом, которое вернула зарядка; пример — 1186 против 1310 мА·ч при `BATT_AMP_PERVLT` 40 → 40 × 1310/1186 = 44.2. Цель — расхождение < 5 %.
9. **Режимы и failsafe на столе.** Режимы парами (`FLTMODE1/2` Stabilize, `3/4` AltHold, `5/6` Loiter) — проверить по вкладке Flight Modes, что каждая позиция тумблера подсвечивает нужный режим; тумблер арма, E-Stop. АКБ 6S LiPo: `BATT_LOW_VOLT = 21.6` (3.6 В/банка под нагрузкой), `BATT_CRT_VOLT = 21.0` (3.5 В/банка), `BATT_FS_LOW_ACT = 2` (RTL), `BATT_FS_CRT_ACT = 1` (Land), `BATT_CAPACITY = 4000`, `BATT_LOW_MAH = 1000`, `BATT_ARM_VOLT = 22.1` — те же напряжения запишет Initial Parameter Setup в пункте 11 для 6S с минимумом 3.3 В/банка; `MOT_BAT_VOLT_MAX = 25.2`, `MOT_BAT_VOLT_MIN = 19.8`. Тест без пропов: Stabilize, арм, газ в ноль, выключить пульт → немедленный дизарм.
10. **OSD и видео.** `OSD_TYPE = 1` (аналог) или `5` + `SERIALn_PROTOCOL = 42` (цифра); на очках видно напряжение, режим, RSSI/LQ.
11. **Предполётная проверка.** Стартовые параметры тюна по размеру пропа и числу банок (Mission Planner → SETUP → Mandatory Hardware → Initial Parameter Setup, ap-tuning), `MOT_THST_HOVER = 0.25`, `ATC_THR_MIX_MAN = 0.1`, `MOT_HOVER_LEARN = 2`, `LOG_DISARMED = 0`, SD-карта есть. Пропы на место: направление лопастей по Motor Test, гайки затянуты. Площадка 20 × 20 м без людей, ветер < 5 м/с, наблюдатель.
12. **Первое висение.** Stabilize: арм → дизарм → арм (проверка дизарма), газ медленно до отрыва, сразу посадить и дизармить. Затем висение на 1 м с отклонениями стиков ±5°. Потом Stabilize до 5 м → AltHold ≥ 30 с без входов → посадка; `PSC_ACCZ_P` = `MOT_THST_HOVER`, `PSC_ACCZ_I` = 2 × `MOT_THST_HOVER` (масштаб 4.6). Потом Loiter 30 с: аппарат стоит в круге 1–2 м. Критерии прерывания: рывок или вращение на отрыве — газ в ноль, дизарм (порядок или направление моторов); слышимые или видимые колебания — посадка и все `ATC_RAT_RLL/PIT_P/I/D` −50 %; «унитаз» в Loiter — в AltHold и на посадку (компас); «PreArm»/«EKF variance» — не взлетать.
13. **Первый тюн.** `INS_LOG_BAT_MASK = 1`, висение 30 с → harmonic notch по спектру (ap-tuning). Потом QuikTune: `VTOL-quicktune.lua` в `APM/scripts`, `SCR_ENABLE = 1`, перезагрузка, `QUIK_ENABLE = 1`, тумблер `RCx_OPTION = 300`; Loiter на 3 м, тумблер в середину — тюн, вверх — сохранить. Lua нужно ≥ 2 МБ флеша: на F405 скриптов нет, там AutoTune (`RCx_OPTION = 17`, `AUTOTUNE_AXES = 1` для roll, AltHold/Loiter, сохранение при дизарме с включённым тумблером).
14. **Лог и бэкап.** Скачать `.BIN` (Mission Planner → DataFlash Logs), `check_lab_log.py --lab hover`, сохранить `01_after_setup.param` и сравнить с `00_defaults.param`.

Приёмка железа: Motor Test совпадает со схемой рамы по позиции и направлению; ошибка напряжения < 0.02 В/банка, мА·ч в пределах 5 % от зарядки; RC failsafe на земле дизармит, в воздухе на 5 м — RTL или Land; `MOT_THST_HOVER` 0.2–0.5; `VIBE` p95 < 30 м/с², `Clip` = 0.

Лабораторная засчитывается, когда:
- SITL: `00_defaults.param` и `01_after_setup.param` сохранены и сравнены, таблица Motor Test (A→1, B→4, C→2, D→3) записана, калибровка `BATT_VOLT_MULT` посчитана и проверена, в логе SITL есть `ERR Subsys=5` и `Subsys=6` с переходом в RTL, `MOT_THST_HOVER` из лога в пределах 0.2–0.5;
- железо: `.param` после настройки закоммичен вместе с `.BIN` первого висения (60 с, Stabilize → AltHold → Loiter), `MOT_THST_HOVER` 0.2–0.5, `VIBE` p95 < 30 м/с² без клиппинга, RC- и battery-failsafe записаны в лог (battery — порогом `BATT_LOW_VOLT` чуть ниже текущего напряжения на висении), ошибка напряжения < 0.02 В/банка, мА·ч в пределах 5 %.

## diagnostics
- **Симптом:** Mission Planner не видит плату после прошивки Betaflight-платы
  - Возможная причина: прошит `.apj` или `.hex` без загрузчика, либо плата не в DFU.
  - Что сделать: DFU (BOOT + USB), `arducopter_with_bl.hex`, STM32CubeProgrammer; дальше только `.apj`.
- **Симптом:** каналы RC не двигаются, приёмник показывает связь
  - Возможная причина: не тот `SERIALn` (hwdef), `RC_PROTOCOLS` без бита 9, RX/TX не перекрещены, UART без DMA на F4/F7.
  - Что сделать: сверить таблицу UART платы, `RC_PROTOCOLS = 1` для пробы, RX приёмника на TX платы.
  - Что видно в логе: `RCIN` стоит на одних значениях.
- **Симптом:** «Bad DShot» / моторы не отвечают после `MOT_PWM_TYPE = 6`
  - Возможная причина: не перезагрузили, выход на IOMCU MAIN (DShot только на AUX без `BRD_IO_DSHOT`), в таймерной группе смешаны DShot и PWM.
  - Что сделать: перезагрузка, моторы на выходы с DShot, однородные группы.
- **Симптом:** на отрыве коптер резко кренится или вращается
  - Возможная причина: мотор не на своей позиции или крутится не туда, пропы перепутаны.
  - Что сделать: газ в ноль, дизарм; повторить Motor Test без пропов, сверить со схемой рамы.
  - Последствия: переворот в первые 0.5 с, сломанные пропы.
- **Симптом:** после арма один мотор не крутится или дёргается
  - Возможная причина: `MOT_SPIN_ARM` ниже порога трогания этого мотора; для PWM — ESC не откалиброваны.
  - Что сделать: найти порог в Motor Test, `MOT_SPIN_ARM` = порог + 0.02; калибровка ESC для PWM.
- **Симптом:** напряжение в OSD отличается от мультиметра на 0.3–0.5 В
  - Возможная причина: `BATT_VOLT_MULT` по умолчанию для другого датчика.
  - Что сделать: новый = старый × V_мультиметр / V_GCS, проверить на двух уровнях заряда.
- **Симптом:** полётник насчитал на 15–20 % меньше мА·ч, чем вернула зарядка
  - Возможная причина: неверный `BATT_AMP_PERVLT` или смещение нуля.
  - Что сделать: сначала `BATT_AMP_OFFSET` по нулю, затем масштаб по мА·ч зарядки.
  - Последствия: `BATT_LOW_MAH` срабатывает поздно, аппарат садится на пустой АКБ.
- **Симптом:** в SITL `SIM_RC_FAIL = 1` не вызывает failsafe
  - Возможная причина: GCS или скрипт шлёт RC-override, он считается живым RC.
  - Что сделать: снять override (истекает за `RC_OVERRIDE_TIME` = 3 с), повторить.
- **Симптом:** в AltHold коптер сам садится или падает
  - Возможная причина: газ ниже мёртвой зоны (в SITL — истёкший override газа), неверный `MOT_THST_HOVER`, вибрации Z.
  - Что сделать: газ в центр перед переключением, `MOT_HOVER_LEARN = 2`, `VIBE.VibeZ` < 30.
- **Симптом:** «PreArm: Compass not calibrated» или «унитаз» в Loiter
  - Возможная причина: калибровка в помещении, помехи от силовых проводов, неверная ориентация внешнего компаса.
  - Что сделать: калибровка на улице, CompassMot, отключить внутренний компас.

## checklist
- Плата прошита `_with_bl.hex`, дальше обновляю только `.apj`
- `00_defaults.param` сохранён до первого изменения
- Порты расписаны по таблице UART платы, приёмник на `SERIALn_PROTOCOL = 23`
- Motor Test: A→B→C→D по часовой, направления по схеме рамы, пропы сняты
- `MOT_SPIN_ARM` = порог + 0.02, `MOT_SPIN_MIN` ≥ `MOT_SPIN_ARM` + 0.03
- Датчик АКБ: ноль, напряжение, ток, мА·ч — в этом порядке
- `BATT_FS_LOW_ACT` ≠ 0, RC failsafe проверен на земле и в SITL
- Первое висение Stabilize → AltHold → Loiter с критериями прерывания
- `.BIN` и `01_after_setup.param` сохранены и сравнены с исходным

## references
- Loading Firmware onto boards without existing ArduPilot firmware — ArduPilot Copter | https://ardupilot.org/copter/docs/common-loading-firmware-onto-chibios-only-boards.html | primary | A
- Loading Firmware (boards with ArduPilot bootloader) — ArduPilot Copter | https://ardupilot.org/copter/docs/common-loading-firmware-onto-pixhawk.html | primary | A
- Crossfire and ELRS RC Systems — ArduPilot Copter | https://ardupilot.org/copter/docs/common-tbs-rc.html | primary | A
- DShot and Bi-directional DShot — ArduPilot Copter | https://ardupilot.org/copter/docs/common-dshot-escs.html | primary | A
- Connect ESCs and Motors (Motor Test) — ArduPilot Copter | https://ardupilot.org/copter/docs/connect-escs-and-motors.html | primary | A
- ESC Calibration — ArduPilot Copter | https://ardupilot.org/copter/docs/esc-calibration.html | primary | A
- Set Motor Range (MOT_SPIN_ARM / MOT_SPIN_MIN) — ArduPilot Copter | https://ardupilot.org/copter/docs/set-motor-range.html | primary | A
- Power Module Configuration in Mission Planner — ArduPilot Copter | https://ardupilot.org/copter/docs/common-power-module-configuration-in-mission-planner.html | primary | A
- Compass Calibration — ArduPilot Copter | https://ardupilot.org/copter/docs/common-compass-calibration-in-mission-planner.html | primary | A
- Radio Failsafe — ArduPilot Copter | https://ardupilot.org/copter/docs/radio-failsafe.html | primary | A
- Onscreen Display (OSD) — ArduPilot Copter | https://ardupilot.org/copter/docs/common-osd-overview.html | primary | A
- Initial Tuning Flight — ArduPilot Copter | https://ardupilot.org/copter/docs/initial-tuning-flight.html | primary | A
- QuikTune — ArduPilot Copter | https://ardupilot.org/copter/docs/quiktune.html | primary | A
- ArduPilot source, tag Copter-4.6.3 (AP_BattMonitor_Analog.cpp, AP_MotorsMulticopter.cpp, RC_Channels_VarInfo.h, AP_SerialManager.cpp) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.6.3 | primary | A
- Firmware tab — QGroundControl User Guide | https://docs.qgroundcontrol.com/master/en/qgc-user-guide/setup_view/firmware.html | primary | A
- ArduPilot setup — ExpressLRS documentation | https://www.expresslrs.org/quick-start/ardupilot-setup | secondary | A
