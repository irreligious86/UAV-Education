---
id: bf-arming-safety
title: "Почему не армится и как не улететь: флаги арма, runaway takeoff, yaw spin recovery"
level: L2
readingTime: 45 мин
firmware: Betaflight 4.5 (исходники 4.5-maintenance, 4.5.6; отличия 2025.12 отмечены)
status: published
tags:
  - Betaflight
  - арм
  - безопасность
  - runaway takeoff
  - yaw spin
  - airmode
related:
  - bf-setup-scratch
  - f-safety
  - bf-modes-osd
  - bf-failsafe
  - bf-cli
  - bf-blackbox
  - bf-pid-reg-in-bf
  - f-motors-esc
  - diag-troubleshooting
next:
  - bf-filters
---

## summary
Справочный модуль по самому частому вопросу Betaflight: «почему не армится». Здесь полная таблица 26 флагов запрета арма версии 4.5 (`armingDisableFlagNames[]` в `fc/runtime_config.c`): что взводит каждый флаг в исходнике и как его снять. Разобрано, где эти флаги читать: вкладка Setup, `status` в CLI, `MSP_STATUS_EX`, предупреждение в OSD и код пищалки. Дальше — арм тумблером и стиками, PREARM, дизарм, airmode. Отдельно разобраны защиты, которые срабатывают уже после арма: runaway takeoff prevention (пороги и условия отключения взяты из `fc/core.c`), yaw spin recovery и crash recovery. Ещё один раздел — как выглядят на взлёте перепутанные моторы, неверное направление вращения и не тот проп. Лабораторная на Python: декодер маски флагов на реальных масках, включая ловушку с номерами битов в 2025.12, и логика runaway, воспроизведённая из исходника на синтетических данных. Затем на железе: снятие флагов по одному без пропов, тест порядка и направления моторов, первый арм без пропов и первое низкое висение с критериями прерывания.

## theory
### Где читать флаги
{{diagram:bf-arming-flag-groups|26 флагов 4.5 сводятся к пяти действиям: убрать тумблер или газ, дать датчикам успокоиться, закрыть Configurator/CLI/меню, починить моторный протокол или ESC, а после RUNAWAY, CRASH и PARALYZE — дизарм или перезагрузка.}}

Причины запрета арма хранятся в одной 32-битной маске (`armingDisableFlags_e`, `fc/runtime_config.h`). Видна она в четырёх местах:
- **Configurator → Setup → Arming Disable Flags.** Configurator получает маску через `MSP_STATUS_EX`. В ответе есть байт с числом флагов (26 в 4.5, 29 в 2025.12) и `uint32` самой маски (`msp/msp.c`).
- **CLI, команда `status`.** Строка `Arming disable flags:` перечисляет имена всех взведённых флагов от младшего бита к старшему (`cliStatus()`). Документация предупреждает, что на некоторых урезанных сборках печатается только hex. Тогда расшифровывай маску по таблице своей версии (шаг 1 практики).
- **OSD, элемент Warnings.** Флаги показываются, **только пока тумблер ARM включён** и арм запрещён. Имена сменяются каждые 0.5 с. `ARMSWITCH` скрыт, если есть другие причины (`osd/osd_warnings.c`).
- **Пищалка.** Код звучит при каждой неудачной попытке арма с новой причиной: `tryArm()` → `beeperWarningBeeps(ffs(flags))`. Сначала 5 быстрых сигналов по 50 мс, затем N/5 длинных (250 мс) и N%5 коротких (50 мс). N = номер бита + 1. Пищалка сообщает **только самый младший бит**, то есть самую критичную причину: флаги отсортированы по важности. Пример: 1 длинный + 1 короткий = 6 = `RUNAWAY`.

### Все 26 флагов Betaflight 4.5
Код — это номер для пищалки (бит + 1). Источник — файл, где флаг взводится.

| Код | Флаг | Когда взводится (4.5) | Что делать |
|---|---|---|---|
| 1 | `NOGYRO` | гироскоп не найден при старте (`fc/init.c`) | не тот target или мёртвый гиро; в строке датчиков `status` нет `GYRO=` |
| 2 | `FAILSAFE` | идёт Stage 2 failsafe (`flight/failsafe.c`) | вернуть связь; снимается после восстановления |
| 3 | `RXLOSS` | нет валидных RC-кадров 100 мс; после появления связи держится `failsafe_recovery_delay` = 5 (0.5 с) | проводка RX, bind, `serialrx_provider`, вкладка Receiver |
| 4 | `NOT_DISARMED` | связь вернулась, а тумблер ARM включён | выключить ARM |
| 5 | `BOXFAILSAFE` | включён тумблер режима FAILSAFE | выключить |
| 6 | `RUNAWAY` | сработала защита runaway takeoff | выключить ARM (или дизарм стиками), искать причину |
| 7 | `CRASH` | `crash_recovery = DISARM` увидел краш | выключить ARM, осмотреть аппарат |
| 8 | `THROTTLE` | газ ≥ `min_check` (1050) | газ вниз; проверить расходы, триммер, `rxrange` |
| 9 | `ANGLE` | наклон > `small_angle` (25°) или горизонт ещё не оценён (`isUpright()`) | поставить ровно, откалибровать акселерометр; при включённом FLIP OVER AFTER CRASH флаг не ставится |
| 10 | `BOOTGRACE` | прошло меньше `pwr_on_arm_grace` (5 с) после старта; при DShot — ещё и пока не разрешены DShot-команды | подождать |
| 11 | `NOPREARM` | задан диапазон PREARM, а режим выключен или не переключался с прошлого арма | выключить и включить PREARM |
| 12 | `LOAD` | за последнюю секунду опоздало больше `cpu_late_limit_permille` = 10 (1.0 %) задач | снизить нагрузку: частоту PID, лишние функции; смотреть `tasks` |
| 13 | `CALIB` | калибруется гиро, акселерометр, баро или компас; калибровка гиро перезапускается, если СКО > `gyro_calib_noise_limit` (48) | не трогать аппарат ~1.25 с (`gyro_calib_duration` = 125 × 10 мс) |
| 14 | `CLI` | открыт CLI; флаг держится до перезагрузки, `exit noreboot` его не снимает | `exit` или `save` |
| 15 | `CMS` | открыто меню OSD (CMS) | выйти из меню |
| 16 | `BST` | Black Sheep Telemetry; в 4.5 флаг нигде не взводится | — |
| 17 | `MSP` | Configurator прислал `MSP_ARMING_DISABLE` | кнопка Disconnect (по документации выдёргивание USB флаг не снимает) |
| 18 | `PARALYZE` | сработал режим PARALYZE; режим «липкий» | только перезагрузка |
| 19 | `GPS` | GPS Rescue настроен, а фикса или спутников < `gps_rescue_min_sats` (8) нет; только до первого арма | ждать спутники или `gps_rescue_allow_arming_without_fix = ON` |
| 20 | `RESCUE_SW` | включён тумблер GPS RESCUE | выключить |
| 21 | `DSHOT_TELEM` | `dshot_bidir = ON`, но какой-то ESC не шлёт eRPM | прошивка ESC с bidir (Bluejay, BLHeli_32, AM32) или `dshot_bidir = OFF` |
| 22 | `REBOOT_REQD` | изменена настройка, требующая перезагрузки | перезагрузить |
| 23 | `DSHOT_BBANG` | bit-bang DShot не запустился: конфликт таймеров или пинов | `dshot_bitbang`, `resource`, `timer` (bf-cli) |
| 24 | `NO_ACC_CAL` | акселерометр не калиброван, а им пользуется ANGLE, HORIZON, GPS RESCUE, ACRO TRAINER, OSD-элемент или failsafe GPS-RESCUE | Calibrate Accelerometer на ровном столе |
| 25 | `MOTOR_PROTO` | `motor_pwm_protocol = DISABLED` или протокол не запустился | выбрать DSHOT300/600 |
| 26 | `ARMSWITCH` | тумблер ARM включён, пока взведён любой другой флаг; после дизарма GPS Rescue | выключить ARM, сначала снять остальные флаги |

Старые имена с форумов: `RPMFILTER` = `DSHOT_TELEM`, `BADRX` = `NOT_DISARMED`; `RESC` — имя в enum для `RESCUE_SW`. Флага `LAUNCH` нет: launch control арм не запрещает.

**2025.12** добавляет флаги `FLIP_SWITCH` (бит 25), `ALT_HOLD_SW` (26) и `POS_HOLD_SW` (27). Флаг `ARMSWITCH` переименован в `ARM_SWITCH` и переехал с бита 25 на бит 28. В `master` добавлен ещё и `AUTOPILOT_SW`, а `ARM_SWITCH` стоит на бите 29. Номера битов и коды пищалки после 24-го зависят от версии, поэтому декодер выбирает таблицу по числу флагов из `MSP_STATUS_EX`.

### Арм тумблером и стиками, PREARM, дизарм
`fc/rc_controls.c`: арм стиками включается, только если **нет** диапазона ARM на вкладке Modes **и** `enable_stick_arming = ON` (по умолчанию OFF). Жест арма — газ вниз + рыскание вправо, жест дизарма — газ вниз + рыскание влево, оба удерживаются 500 мс (`ARM_DELAY_MS`). Жест арма игнорируется, если включён режим STICK COMMANDS DISABLE.

Арм тумблером: каждый цикл RC, пока ARM включён, вызывается `tryArm()`. Если в этот момент взведён любой флаг, ставится `ARMSWITCH`. Он не даст аппарату заармиться сам, когда исчезнет причина, — тумблер нужно опустить и поднять снова. Для дизарма тумблером нужно больше трёх подряд RC-кадров с выключенным ARM: случайный одиночный кадр дизарм не вызовет. При настоящей потере связи дизарм тумблером не сработает, пока не вернутся валидные данные (`failsafeIsReceivingRxData()`).

**PREARM**: если для него задан диапазон, арм возможен только при включённом PREARM. После каждого арма его нужно выключить и включить снова (флаг `WAS_ARMED_WITH_PREARM`). Для аппаратов 7″ и больше это второй ключ. В 2025.12 появился `prearm_allow_rearm` (по умолчанию OFF): он разрешает переарм без переключения PREARM.

`auto_disarm_delay` = 5 с работает только в одном сочетании: включён `MOTOR_STOP`, airmode выключен, арм стиками. Тогда после 5 с газа внизу аппарат дизармится сам. При арме тумблером в той же ситуации FC только пищит (`BEEPER_ARMED`). `gyro_cal_on_first_arm = ON` переносит калибровку гиро на момент первого арма. Пищалка сообщает об арме (`ARMING`; с GPS — `ARMING_GPS_FIX` или `ARMING_GPS_NO_FIX` по числу спутников) и о дизарме (`DISARMING`). После RUNAWAY и CRASH вместо сигнала дизарма звучит код флага. Отдельные события выключаются командой `beeper -ARMING` и аналогичными.

### Airmode: что делает PID сразу после арма
В 4.5 `feature AIRMODE` включена по умолчанию (`config/feature.c`), `pid_at_min_throttle = ON`. После арма на холостом ходу P и D уже работают, а I обнуляется, пока газ ниже `min_check` и airmode не «защёлкнулся». Airmode защёлкивается, когда газ хоть раз превысил `airmode_start_throttle_percent` = 25 %. С этого момента PID имеет полную власть и при нулевом газе — до самого дизарма (`processRx()`). Два следствия:
- Перепутанный мотор проявляется уже на холостом ходу: аппарат «ёрзает», а при отрыве сразу переворачивается.
- После посадки с защёлкнутым airmode аппарат подпрыгивает и может перевернуться: PID пытается держать горизонт, упираясь пропами в землю. Лечится дизармом сразу после касания, а не настройкой. В 2025.12 для этого есть `landing_disarm_threshold`.

### Runaway takeoff prevention
«Taz», runaway — аппарат после арма или на отрыве уходит в бешеное вращение. Защита в `fc/core.c` устроена так.

**Срабатывание** (`subTaskPidController`, каждый цикл PID): |pidSum| по любой оси ≥ 600 **и** гиро по крену или тангажу > 15 °/с либо по рысканию > 50 °/с. Условие должно держаться без перерыва 75 мс. После этого `setArmingDisabled(RUNAWAY)` и дизарм. Масштаб: pidSum 1000 = 100 % размаха мотора, миксер обрезает его до `pidsum_limit` = 500 (рыскание 400). Сам pidSum при этом не обрезается, так что 600 означает, что регулятор упёрся в предел и всё равно проигрывает. Гиро-пороги нужны для стола: без пропов pidSum растёт от одних стиков, а аппарат стоит — дизарма нет. Проверка не работает на самолётах, во время crash flip, в GPS Rescue и пока подключённый Configurator временно её выключил (`runawayTakeoffTemporaryDisable`). При `MOTOR_STOP` без airmode она не работает и на газе ниже `min_check`.

**Отключение** (`processRx`): копится время «нормального полёта». Это моменты, когда газ ≥ `runaway_takeoff_deactivate_throttle_percent` (20 %) и какой-то стик крена, тангажа или рыскания отклонён ≥ 15 %, либо газ ≥ 40 % (2 × 20, но не больше 75). Дополнительно |pidSum| по всем осям должен быть < 100. Когда накопится `runaway_takeoff_deactivate_delay` = 500 мс (250 мс при газе ≥ 75 %), защита отключается до перезагрузки. Исключение — арм в режиме crash flip: он включает её снова. Процент газа считается как (rc − `min_check`) × 100 / (2000 − `min_check`), то есть 20 % — это примерно 1240 мкс. Значит, при висении без движения стиков на газе 26 % защита не отключится никогда.

**Снятие флага `RUNAWAY`**: опустить ARM или сделать жест дизарма стиками. Затем ищи причину: ложные срабатывания редки, и если защита сработала на отрыве, почти всегда неверны моторы, пропы или ориентация платы. Отключать её (`runaway_takeoff_prevention = OFF`) документация прямо не советует.

{{diagram:chart-bf-runaway-trip|При инвертированной обратной связи по крену pidSum проходит 600 через 217 мс после отрыва, крен всего около 12°; через 75 мс подтверждения дизарм на 292 мс при крене 45° — до переворота.}}

### Как выглядят ошибки моторов на взлёте
| Ошибка | Что делает аппарат | RUNAWAY? | Проверка (bf-setup-scratch) |
|---|---|---|---|
| Левые и правые моторы переставлены (M1↔M3, M2↔M4) или плата повёрнута на 180° без `align_board_yaw` | мгновенный переворот через бок при отрыве | да, ~0.3 с | вкладка Motors по одному мотору; Setup — модель повторяет наклон |
| Переставлены два мотора одной стороны (M1↔M2) | теряет управление по тангажу и рысканию, кувырок вперёд или назад | да | то же |
| Один мотор крутится не в ту сторону или на нём проп другого направления | этот угол почти не тянет: переворот на него плюс рыскание | обычно да | полоска скотча на колоколе, `dshotprog <i> 7\|8 12` |
| `yaw_motors_reversed` не совпадает с пропами (props out/in) | пируэт по рысканию на отрыве | да (рыскание > 50 °/с) | рыскание стиком на холостом ходу без пропов: какие моторы ускоряются |
| Акселерометр не откалиброван (ANGLE) | дрейф в сторону, без переворота | нет | Calibrate Accelerometer |

В QUADX мотор 1 задний правый (CW при props in), 2 передний правый (CCW), 3 задний левый (CCW), 4 передний левый (CW). Порядок исправляет `motor_output_reordering` (диалог Reorder motors), направление — команды DShot 7/8 + 12. Подробно — в bf-setup-scratch.

### Yaw spin recovery и crash recovery
**Yaw spin recovery** (`sensors/gyro.c`). Если |гиро Z| > порога, включается режим спасения. В нём уставка рыскания = 0, I по всем осям обнуляется, P, D и FF по крену и тангажу обнуляются, предел pidSum по рысканию поднимается до 1000. Без airmode газ ставится в 0.5 (`flight/mixer.c`). Вся тяга идёт на остановку вращения. Режим выключается, когда скорость рыскания продержится ниже порога − 100 °/с дольше 20 мс. Порог зависит от `yaw_spin_recovery`: `ON` — ровно `yaw_spin_threshold` (1950, диапазон 500–1950); `AUTO` (по умолчанию) — max_yaw + max(max_yaw/4, 200), ограниченное 500…1950, где max_yaw — максимальная скорость рыскания текущего профиля рейтов. Для рейтов 4.5 по умолчанию (Actual, `yaw_srate` = 67 → 670 °/с) порог 870 °/с. `OFF` — функция выключена.

**Crash recovery** (`flight/pid.c`) по умолчанию `OFF`. Краш детектируется, когда одновременно: миксер в насыщении, |ΔD| > `crash_dthreshold` (50 °/с²), |ошибка| > `crash_gthreshold` (400 °/с), |уставка| < `crash_setpoint_threshold` (350 °/с). Реакция зависит от режима. `ON` — FC выравнивает аппарат к горизонту и обнуляет I. Выход — когда крен и тангаж меньше `crash_recovery_angle` (10°) и при этом либо прошло `crash_time` (500 мс), либо миксер вышел из насыщения, а скорости по всем осям меньше `crash_recovery_rate` (100 °/с). `BEEP` — по исходнику 4.5 то же выравнивание плюс пищалка (см. notes). `DISARM` — дизарм и флаг `CRASH`. В GPS Rescue детектор работает всегда. Для фристайла и гонок функцию обычно не включают: удар о ворота она примет за краш.

### Справочник параметров (4.5)
| Параметр | По умолчанию | Диапазон | Смысл |
|---|---|---|---|
| `small_angle` | 25 | 0–180° | максимальный наклон для арма (180 только в сборках RACE_PRO) |
| `pwr_on_arm_grace` | 5 | 0–30 с | запрет арма после включения (`BOOTGRACE`) |
| `enable_stick_arming` | OFF | OFF/ON | арм стиками, если нет диапазона ARM |
| `auto_disarm_delay` | 5 | 0–60 с | автодизарм при газе внизу (MOTOR_STOP, без airmode, стики) |
| `gyro_cal_on_first_arm` | OFF | OFF/ON | калибровать гиро при первом арме |
| `gyro_calib_duration` | 125 | 50–3000 (×10 мс) | длительность калибровки гиро |
| `gyro_calib_noise_limit` | 48 | 0–200 | СКО, при котором калибровка перезапускается |
| `min_check` | 1050 | 750–2250 мкс | порог «газ внизу» для арма и стик-команд |
| `airmode_start_throttle_percent` | 25 | 0–100 % | газ, после которого airmode защёлкивается |
| `pid_at_min_throttle` | ON | OFF/ON | P/D работают на холостом ходу |
| `cpu_late_limit_permille` | 10 | 0–100 ‰ | доля опоздавших задач для `LOAD` |
| `runaway_takeoff_prevention` | ON | OFF/ON | защита runaway |
| `runaway_takeoff_deactivate_delay` | 500 | 100–1000 мс | сколько «нормального полёта» накопить до отключения |
| `runaway_takeoff_deactivate_throttle_percent` | 20 | 0–100 % | минимальный газ для накопления |
| `yaw_spin_recovery` | AUTO | OFF/ON/AUTO | спасение из раскрутки по рысканию |
| `yaw_spin_threshold` | 1950 | 500–1950 °/с | порог для режима ON |
| `crash_recovery` | OFF | OFF/ON/BEEP/DISARM | реакция на краш (профиль PID) |
| `crash_dthreshold` / `crash_gthreshold` / `crash_setpoint_threshold` | 50 / 400 / 350 | 10–2000 / 100–2000 / 50–2000 | пороги детектора краша |
| `crash_time` / `crash_delay` | 500 / 0 | 100–5000 / 0–500 мс | длительность и задержка выравнивания |
| `crash_recovery_angle` / `crash_recovery_rate` / `crash_limit_yaw` | 10 / 100 / 200 | 5–30° / 50–255 °/с / 0–1000 °/с | критерии выхода; ограничение ошибки рыскания |
| `gps_rescue_allow_arming_without_fix` | OFF | OFF/ON | арм без фикса при настроенном GPS Rescue |
| `yaw_motors_reversed` | OFF | OFF/ON | props out |
| `motor_output_reordering` | 0,1,2,…,7 | массив | перестановка выходов моторов |
| `dshot_bidir` | OFF | OFF/ON | bidir DShot; при ON нужен eRPM от каждого ESC |

## practice
### Шаг 1. Декодер маски флагов
Маску ты увидишь как hex (урезанный `status`, сырой `MSP_STATUS_EX`, лог своего скрипта) или как список имён. Скрипт переводит маску в имена по таблице нужной версии, вычисляет код пищалки (по младшему биту) и показывает, что напишет OSD. Пять масок взяты из практики: SITL-конфиг из bf-setup-scratch, стол с подключённым Configurator, включение с поднятым газом и включённым ARM, дизарм после runaway, ESC без bidir. Шестая маска — та же ситуация «газ + тумблер» в 2025.12, расшифрованная сначала таблицей 4.5, а потом по числу флагов из ответа MSP.

```python
# Betaflight arming-disable flags: decode a mask from `status` / MSP_STATUS_EX (fc/runtime_config.c, msp/msp.c)
import struct
F45 = ("NOGYRO FAILSAFE RXLOSS NOT_DISARMED BOXFAILSAFE RUNAWAY CRASH THROTTLE ANGLE BOOTGRACE NOPREARM LOAD "
       "CALIB CLI CMS BST MSP PARALYZE GPS RESCUE_SW DSHOT_TELEM REBOOT_REQD DSHOT_BBANG NO_ACC_CAL "
       "MOTOR_PROTO ARMSWITCH").split()                                          # 4.5: 26 flags
F2512 = F45[:25] + ["FLIP_SWITCH", "ALT_HOLD_SW", "POS_HOLD_SW", "ARM_SWITCH"]  # 2025.12: 29 flags
TABLE = {26: F45, 29: F2512}

def decode(mask, count=26):
    names = TABLE[count]
    nm = lambda b: names[b] if b < len(names) else f"BIT{b}?"
    bits = [b for b in range(32) if mask >> b & 1]
    code = bits[0] + 1                       # tryArm(): beeperWarningBeeps(ffs(flags)) -> lowest bit only
    osd = [nm(b) for b in bits if b != count - 1] or [nm(count - 1)]   # osd_warnings.c hides ARMSWITCH
    print(f"0x{mask:08X} [{count}] {' '.join(nm(b) for b in bits)}")
    print(f"   beeper: 5 fast + {code // 5} long + {code % 5} short = {code} ({nm(bits[0])}); OSD: {' '.join(osd)}")

def mask_of(words, names=F45):
    return sum(1 << names.index(w) for w in words.split())

for words in ("RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO", "ANGLE MSP", "THROTTLE ARMSWITCH",
              "RUNAWAY ARMSWITCH", "DSHOT_TELEM ARMSWITCH"):
    decode(mask_of(words))

m = mask_of("THROTTLE ARM_SWITCH", F2512)        # the same situation on 2025.12
decode(m, 26)                                     # wrong table: bit 28 unknown
payload = struct.pack("<HHHIBHBBB", 125, 0, 0b100001, 0, 0, 120, 4, 0, 0) + struct.pack("<BIB", 29, m, 0)
nb = payload[15]; count, flags = struct.unpack_from("<BI", payload, 16 + nb)   # MSP_STATUS_EX layout
decode(flags, count)                              # flag count from the FC picks the right table
```

```text
0x01002304 [26] RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO
   beeper: 5 fast + 0 long + 3 short = 3 (RXLOSS); OSD: RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO
0x00010100 [26] ANGLE MSP
   beeper: 5 fast + 1 long + 4 short = 9 (ANGLE); OSD: ANGLE MSP
0x02000080 [26] THROTTLE ARMSWITCH
   beeper: 5 fast + 1 long + 3 short = 8 (THROTTLE); OSD: THROTTLE
0x02000020 [26] RUNAWAY ARMSWITCH
   beeper: 5 fast + 1 long + 1 short = 6 (RUNAWAY); OSD: RUNAWAY
0x02100000 [26] DSHOT_TELEM ARMSWITCH
   beeper: 5 fast + 4 long + 1 short = 21 (DSHOT_TELEM); OSD: DSHOT_TELEM
0x10000080 [26] THROTTLE BIT28?
   beeper: 5 fast + 1 long + 3 short = 8 (THROTTLE); OSD: THROTTLE BIT28?
0x10000080 [29] THROTTLE ARM_SWITCH
   beeper: 5 fast + 1 long + 3 short = 8 (THROTTLE); OSD: THROTTLE
```

Что видно в выводе:
- Из пяти флагов SITL пищалка сообщит только `RXLOSS` (код 3). Почини его, попробуй заармить и слушай следующий код.
- Коды 6 (`RUNAWAY`) и 21 (`DSHOT_TELEM`) совпадают с таблицей документации для 4.2+. Это проверка, что декодер и прошивка считают одинаково.
- Маска `0x10000080` из 2025.12 по таблице 4.5 даёт неизвестный бит 28. Hex без версии прошивки не расшифровать: номер версии берут из `version` или из числа флагов в `MSP_STATUS_EX`.

### Шаг 2. Логика runaway takeoff на синтетических данных
Класс `Runaway` — это построчный перенос двух кусков `fc/core.c` с теми же константами: накопление «нормального полёта» в `processRx()` и проверка срабатывания в `subTaskPidController()`. Модель аппарата намеренно простая: одна ось крена, P = 45 и I = 80 из умолчаний 4.5 (D и FF отброшены), 12 °/с² углового ускорения на единицу pidSum, задержка моторов 20 мс, ограничения `pidsum_limit` 500 и `iterm_limit` 400. Сценарии: A — нормальный взлёт, B — инвертированная обратная связь (перепутаны левые и правые моторы), C и D — стол без пропов, E — висение без движения стиков.

```python
# Betaflight 4.5 runaway takeoff prevention, reproduced from fc/core.c (processRx + subTaskPidController)
# and run on synthetic data. Constants are the firmware's #defines; settings are 4.5 defaults (flight/pid.c).
PIDSUM_TRIP, ACTIVATE_US = 600, 75_000          # RUNAWAY_TAKEOFF_PIDSUM_THRESHOLD, _ACTIVATE_DELAY
GYRO_RP, GYRO_YAW = 15, 50                      # RUNAWAY_TAKEOFF_GYRO_LIMIT_RP/_YAW, deg/s
STICK_PCT, PIDSUM_OK, HIGH_THR = 15, 100, 75    # _DEACTIVATE_STICK_PERCENT, _DEACTIVATE_PIDSUM_LIMIT, _HIGH_THROTTLE_PERCENT
DEACT_THR, DEACT_DELAY_MS = 20, 500             # runaway_takeoff_deactivate_throttle_percent, _deactivate_delay
MIN_CHECK = 1050

class Runaway:
    def __init__(s): s.trig = 0; s.deact = 0; s.acc = 0; s.off = False; s.off_at = None; s.disarmed_at = None
    def rx(s, t, thr_us, stick, pidsum):        # processRx(): learn "stable flight", then switch off
        if s.off: return
        pct = max(0, min(100, (thr_us - MIN_CHECK) * 100 // (2000 - MIN_CHECK)))
        mid = min(DEACT_THR * 2, HIGH_THR)       # constrain(low*2, low*2, 75)
        ok = ((pct >= DEACT_THR and stick >= STICK_PCT) or pct >= mid) and max(map(abs, pidsum)) < PIDSUM_OK
        if ok:
            if s.deact == 0: s.deact = t
            delay = DEACT_DELAY_MS // 2 if pct >= HIGH_THR else DEACT_DELAY_MS
            if t - s.deact + s.acc > delay * 1000: s.off = True; s.off_at = t
        else:
            if s.deact: s.acc += t - s.deact
            s.deact = 0
    def pid(s, t, pidsum, gyro):                 # subTaskPidController(): trip -> setArmingDisabled(RUNAWAY), disarm
        if s.off or s.disarmed_at is not None: return
        if max(map(abs, pidsum)) >= PIDSUM_TRIP and (abs(gyro[0]) > GYRO_RP or abs(gyro[1]) > GYRO_RP or abs(gyro[2]) > GYRO_YAW):
            if s.trig == 0: s.trig = t + ACTIVATE_US
            elif t > s.trig: s.disarmed_at = t
        else:
            s.trig = 0

# Roll axis of a 5" quad: P = 45, I = 80 (PTERM_SCALE 0.032029, ITERM_SCALE 0.244381, flight/pid.h), D/FF omitted.
# Plant: roll acceleration 12 deg/s^2 per pidSum unit (12 000 deg/s^2 at full authority), motor lag tau = 20 ms,
# I is clamped to iterm_limit = 400; mixer clamps the roll command to pidsum_limit = 500 (flight/mixer.c); pidSum itself is not clamped.
KP, KI = 0.032029 * 45, 0.244381 * 80
def fly(sign, thr_profile, stick_profile, setpoint_profile, props=True, hand=None, T=2.0, dt=125e-6):
    r = Runaway(); w = ang = cmd = I = 0.0; w = 5.0 if props else 0.0   # 5 deg/s disturbance at lift-off
    trace = []; t_us = 0; k = 0
    while t_us < T * 1e6:
        t = t_us / 1e6
        sp = setpoint_profile(t)
        err = sp - w
        I = max(-400, min(400, I + KI * err * dt))      # iterm_limit = 400 (flight/pid.c)
        P = KP * err; pidsum = P + I
        if r.disarmed_at is None and props:
            cmd += (max(-500, min(500, pidsum)) - cmd) * dt / 0.020
            w += sign * 12.0 * cmd * dt                 # sign = -1: left/right swapped -> positive feedback
            ang += w * dt
        elif not props:
            w = hand(t) if hand else 0.3                # props off: gyro sees noise or the hand
        if k % 8 == 0:                                  # PID loop 8 kHz, RX checks at ~1 kHz are enough here
            r.rx(t_us, thr_profile(t), stick_profile(t), (pidsum, 0, 0))
        r.pid(t_us, (pidsum, 0, 0), (w, 0, 0))
        if k % 80 == 0: trace.append((round(t, 3), round(pidsum), round(w), round(ang)))
        if r.disarmed_at is not None and t_us > r.disarmed_at + 50_000: break
        t_us += 125; k += 1
    return r, trace

ramp = lambda t: 1000 + min(t / 0.4, 1) * 330          # throttle 1000 -> 1330 us (29 %) in 0.4 s
roll_stick = lambda t: 25 if 0.6 < t < 1.6 else 0       # pilot moves roll 25 % between 0.6 and 1.6 s
sp_stick = lambda t: 100 if 0.6 < t < 1.6 else 0        # setpoint 100 deg/s while the stick is out

def report(name, r, tr, every=None):
    print(f"--- {name}")
    if r.disarmed_at is not None:
        row = min(tr, key=lambda x: abs(x[0] - r.disarmed_at / 1e6))
        print(f"  RUNAWAY: disarm at t = {r.disarmed_at/1e3:.0f} ms, pidSum {row[1]}, gyro {row[2]} deg/s, roll {row[3]} deg")
        trip_start = (r.trig - ACTIVATE_US) / 1e3
        print(f"  pidSum first >= 600 with gyro > 15 deg/s at {trip_start:.0f} ms, +75 ms confirmation")
    when = f" at t = {r.off_at/1e3:.0f} ms" if r.off else ""
    print(f"  prevention switched off for this battery: {r.off}{when}")
    print(f"  max |pidSum| {max(abs(x[1]) for x in tr)}, max |gyro| {max(abs(x[2]) for x in tr)} deg/s")
    if every:
        for row in tr[::every]: print("   t={:5.2f}s pidSum={:5d} gyro={:5d} roll={:4d}".format(*row))

r, tr = fly(+1, ramp, roll_stick, sp_stick)
report("A. correct motor order, normal take-off, roll stick 25 % from 0.6 s", r, tr)
r, tr = fly(-1, ramp, lambda t: 0, lambda t: 0, T=1.0)
report("B. roll feedback inverted (left/right motors swapped M1<->M3, M2<->M4)", r, tr, every=4)
r, tr = fly(+1, lambda t: 1300, lambda t: 60, lambda t: 300, props=False, T=2.0)
report("C. bench, props OFF, roll stick held 60 % (setpoint 300 deg/s), quad on the table", r, tr)
r, tr = fly(+1, lambda t: 1300, lambda t: 60, lambda t: 300, props=False, hand=lambda t: 40 if t > 1.0 else 0.3, T=2.0)
report("D. as C, but from 1.0 s the quad is tilted by hand at 40 deg/s", r, tr)
for lim in (20, 10):
    DEACT_THR = lim
    r, tr = fly(+1, lambda t: 1000 + min(t / 0.4, 1) * 300, lambda t: 0, lambda t: 0, T=3.0)
    print(f"--- E. hover at throttle 1300 us (26 %), sticks centred, deactivate_throttle_percent = {lim}")
    print(f"  prevention switched off: {r.off}")
```

```text
--- A. correct motor order, normal take-off, roll stick 25 % from 0.6 s
  prevention switched off for this battery: True at t = 1171 ms
  max |pidSum| 162, max |gyro| 147 deg/s
--- B. roll feedback inverted (left/right motors swapped M1<->M3, M2<->M4)
  RUNAWAY: disarm at t = 292 ms, pidSum -1361, gyro 667 deg/s, roll 45 deg
  pidSum first >= 600 with gyro > 15 deg/s at 217 ms, +75 ms confirmation
  prevention switched off for this battery: False
  max |pidSum| 1380, max |gyro| 680 deg/s
   t= 0.00s pidSum=   -7 gyro=    5 roll=   0
   t= 0.04s pidSum=  -16 gyro=    8 roll=   0
   t= 0.08s pidSum=  -36 gyro=   16 roll=   1
   t= 0.12s pidSum=  -82 gyro=   35 roll=   2
   t= 0.16s pidSum= -187 gyro=   79 roll=   4
   t= 0.20s pidSum= -425 gyro=  178 roll=   9
   t= 0.24s pidSum= -917 gyro=  374 roll=  19
   t= 0.28s pidSum=-1275 gyro=  608 roll=  39
   t= 0.32s pidSum=-1380 gyro=  680 roll=  47
--- C. bench, props OFF, roll stick held 60 % (setpoint 300 deg/s), quad on the table
  prevention switched off for this battery: False
  max |pidSum| 832, max |gyro| 0 deg/s
--- D. as C, but from 1.0 s the quad is tilted by hand at 40 deg/s
  RUNAWAY: disarm at t = 1075 ms, pidSum 775, gyro 40 deg/s, roll 0 deg
  pidSum first >= 600 with gyro > 15 deg/s at 1000 ms, +75 ms confirmation
  prevention switched off for this battery: False
  max |pidSum| 832, max |gyro| 40 deg/s
--- E. hover at throttle 1300 us (26 %), sticks centred, deactivate_throttle_percent = 20
  prevention switched off: False
--- E. hover at throttle 1300 us (26 %), sticks centred, deactivate_throttle_percent = 10
  prevention switched off: True
```

Разбор:
- **A.** До 0.6 с газ 29 % (меньше 40 %), стики в центре — время не копится. С 0.6 с стик крена на 25 %, но первые ~70 мс |pidSum| доходит до 162 (> 100), пока аппарат разгоняется до уставки. Поэтому защита отключается на 1171 мс, а не на 1100.
- **B.** Это и есть «переворот на взлёте». Ошибка в 5 °/с растёт экспоненциально, удваиваясь примерно каждые 35 мс. Порог 600 пройден на 217 мс при крене около 12°, дизарм — на 292 мс при крене 45°. Моторы гаснут раньше, чем аппарат ляжет на спину и уйдёт в сторону пилота. Это график в теории выше. В I-члене видно насыщение на 400: излом кривой около 245 мс.
- **C и D.** Без пропов pidSum доходит до 832, но гиро около нуля, поэтому стол с качанием стиков безопасен. Стоит наклонить аппарат рукой на 40 °/с — через 75 мс дизарм. Это совпадает с «Known issues» в документации.
- **E.** Ровное висение на 26 % газа без движения стиков защиту не отключает. С `runaway_takeoff_deactivate_throttle_percent = 10` порог «без стиков» падает до 20 %, и защита отключается. Не снижай этот параметр ради лёгкого аппарата без нужды: защита отключится раньше, чем ты убедишься, что аппарат летит правильно.

### Шаг 3. Порог yaw spin recovery в режиме AUTO
```python
# yaw_spin_recovery = AUTO threshold (sensors/gyro.c initYawSpinRecovery) from the max yaw rate
# of the rate profile (fc/rc.c: maxRcRate = applyRates(axis, 1.0, 1.0)); Actual rates: max = rates * 10 deg/s.
def auto_threshold(max_yaw):
    return max(500, min(1950, max_yaw + max(max_yaw // 4, 200)))   # YAW_SPIN_RECOVERY_THRESHOLD_MIN/MAX
for name, srate in (("4.5 default (yaw_srate 67)", 67), ("cinematic (40)", 40), ("freestyle (100)", 100), ("max (200)", 200)):
    m = srate * 10
    th = auto_threshold(m)
    print(f"{name:28s} max yaw {m:4d} deg/s -> trip {th:4d} deg/s, release below {th - 100} deg/s for 20 ms")
```

```text
4.5 default (yaw_srate 67)   max yaw  670 deg/s -> trip  870 deg/s, release below 770 deg/s for 20 ms
cinematic (40)               max yaw  400 deg/s -> trip  600 deg/s, release below 500 deg/s for 20 ms
freestyle (100)              max yaw 1000 deg/s -> trip 1250 deg/s, release below 1150 deg/s for 20 ms
max (200)                    max yaw 2000 deg/s -> trip 1950 deg/s, release below 1850 deg/s for 20 ms
```

AUTO держит порог на 25 %, но не меньше чем на 200 °/с выше твоей максимальной скорости рыскания. При рейтах 4.5 по умолчанию это 870 °/с — близко к значению 850, которое документация советовала ставить вручную при `ON`. Последняя строка — ловушка: рейты рыскания 2000 °/с выше потолка 1950. Длинный пируэт по стику будет запускать спасение, и аппарат начнёт «заикаться» по рысканию — именно так документация описывает слишком низкий порог.

### Переход на реальное железо
Пропы сняты до пункта 4. АКБ подключается через smoke stopper или с ограничением тока на первом включении после пайки.

**1. Снять флаги по одному (стол, пропы сняты).** Включи аппарат, подключи Configurator и запиши в таблицу флаги со вкладки Setup. Потом выполняй действия по порядку и после каждого снова смотри `status`:

| Действие | Флаг должен исчезнуть |
|---|---|
| Подождать 5 с, не трогая аппарат | `BOOTGRACE`, `CALIB` |
| Включить пульт, дождаться связи | `RXLOSS` (через 0.5 с) |
| Газ в ноль; проверить на Receiver, что < 1050 | `THROTTLE` |
| Поставить на ровный стол; калибровка акселерометра | `ANGLE`, `NO_ACC_CAL` |
| Выбрать DShot, сохранить, перезагрузить | `MOTOR_PROTO`, `REBOOT_REQD` |
| Выйти из CLI (`exit`) | `CLI` |
| Disconnect в Configurator | `MSP` |
| Тумблеры FAILSAFE и GPS RESCUE выключить, PREARM (если задан) включить | `BOXFAILSAFE`, `RESCUE_SW`, `NOPREARM` |

Последний `status` снимай через MSP-мост без Configurator или смотри в OSD: Configurator сам ставит `MSP`. Затем намеренно вызови три флага и проверь пищалку. ARM включён при поднятом газе → `THROTTLE` (1 длинный + 3 коротких). Аппарат наклонён на 40° → `ANGLE` (1 + 4). Тумблер ARM включён до появления связи → сначала `RXLOSS` (3 коротких), через 0.5 с `NOT_DISARMED` (4 коротких): пищалка повторяет код, когда меняется главная причина.

**2. Порядок и направление моторов.** Вкладка Motors, «I understand the risks». По очереди подними каждый ползунок до ~1100. Должен крутиться мотор 1 — задний правый CW, 2 — передний правый CCW, 3 — задний левый CCW, 4 — передний левый CW (props in). Направление видно по полоске скотча на колоколе. Исправление — Reorder motors и Motor direction (bf-setup-scratch, шаг 7). Потом проверка без Configurator, аппарат заармлен на столе. Наклони его рукой на 10–15° вправо: правые моторы должны ускориться, левые замедлиться. Если наоборот — это и есть «переворот на взлёте», дальше не иди. Наклони вперёд: передние должны ускориться. Рыскание стиком вправо: должны ускориться моторы, вращающиеся против часовой (2 и 3 при props in). Держи наклон не дольше 1–2 с: длинный наклон рукой — это сценарий D, и он закончится дизармом по `RUNAWAY`.

**3. Первый арм без пропов.** Configurator отключён (иначе `MSP`), ARM на тумблере. Ожидаемое: сигнал `ARMING`, моторы на холостом ходу одинаково. Проверь дизарм тумблером, затем повторный арм. Если GPS Rescue настроен — проверь, что без спутников висит `GPS`. Если стоит PREARM — проверь, что повторный арм без переключения PREARM запрещён (`NOPREARM`).

**4. Первое низкое висение — пропы ставятся здесь.** Проверь пропы по схеме props in и затяжку. Площадка — трава, люди не ближе 10 м, ты в 5 м позади аппарата. Арм в ANGLE, плавно газ до отрыва. Висение 0.3–0.5 м, 10–20 с, посадка, дизарм. Для крупного или тяжёлого аппарата (7″+) вместо свободного висения — привязь: 1.5–2 м шнура от центра рамы снизу к грузу массой не меньше 3 масс аппарата. Шнур не должен доставать до пропов. **Немедленный дизарм** при любом из признаков:
- на отрыве аппарат кренится сильнее 20° или крутится по рысканию;
- пищалка выдаёт RUNAWAY (1 длинный + 1 короткий);
- газ отрыва выше 60 % или ниже 12 %;
- слышны осцилляции;
- аппарат «ходит» по земле до отрыва.

После висения посадка и дизарм сразу после касания (airmode уже защёлкнут, см. теорию). Запиши газ отрыва и флаги после посадки.

**Критерии засчёта железной части:** таблица из пункта 1 заполнена, каждый флаг снят своим действием, три кода пищалки записаны и совпадают с декодером. Порядок, направление и реакция на наклон рукой соответствуют QUADX. Арм и дизарм тумблером проверены без пропов. Первое висение 10–20 с прошло без срабатывания критериев прерывания, газ отрыва записан.

Лабораторная засчитывается, когда:
- **Расчётный путь (Python)**: декодер из шага 1 запущен на пяти масках и на маске 2025.12 с выбором таблицы по числу флагов. Для своей маски из `status` (реальной или из SITL bf-setup-scratch) расписаны флаги, код пищалки и строка OSD. Скрипт шага 2 запущен, получены дизарм в сценарии B (217 → 292 мс) и отключение защиты в сценарии A. Добавлен свой сценарий — например, газ ≥ 75 % (задержка 250 мс) — с объяснением результата. Порог AUTO yaw spin посчитан для твоего профиля рейтов.
- **Железо**: выполнены критерии засчёта железной части выше.

## diagnostics
- **Симптом:** аппарат не армится, в Configurator флаг `MSP`
  - Возможная причина: Configurator сам запрещает арм, пока подключён.
  - Что сделать: Disconnect; по документации выдёргивание USB флаг не снимает. Арм проверять без Configurator.
- **Симптом:** на столе армится, на поле — нет (или наоборот)
  - Возможная причина: `ANGLE` на неровной земле (> 25°), `MSP`/`CLI` на столе, `GPS` без спутников на поле.
  - Что сделать: прочитать флаг в OSD при включённом ARM; не поднимать `small_angle` вместо того, чтобы найти ровное место.
- **Симптом:** флагов в `status` нет, но тумблер не армит
  - Возможная причина: `status` снят при выключенном ARM; диапазон ARM на вкладке Modes не совпадает с реальным значением канала; включён ARM и висит `ARMSWITCH` после прежней причины.
  - Что сделать: включить ARM и смотреть Setup/OSD; на Receiver проверить, что значение канала не ближе 50 мкс к границе диапазона; опустить и снова поднять тумблер.
- **Симптом:** при подъёме газа аппарат мгновенно переворачивается и дизармится, пищит 1 длинный + 1 короткий
  - Возможная причина: `RUNAWAY` — перепутаны моторы, направление вращения, пропы или ориентация платы.
  - Что сделать: снять пропы, пункт 2 практики, вкладка Setup (модель повторяет наклон?); `runaway_takeoff_prevention` не выключать.
  - Последствия: без защиты — переворот через 0.3 с, сломанные пропы, риск для пилота.
- **Симптом:** дизарм RUNAWAY на столе без пропов
  - Возможная причина: аппарат двигали рукой при заармленных моторах, или долгое рыскание стиком (порог 50 °/с).
  - Что сделать: не держать заармленный аппарат в руках; для долгих стендовых тестов — Motors tab.
  - Что видно в логе: `debug_mode = RUNAWAY_TAKEOFF`, debug[1] = 1 за 75 мс до дизарма.
- **Симптом:** `CALIB` не уходит
  - Возможная причина: аппарат качается или вибрирует (вентилятор, стол), СКО гиро > `gyro_calib_noise_limit`.
  - Что сделать: поставить неподвижно; не увеличивать лимит, пока не убедился, что гиро исправен.
- **Симптом:** `DSHOT_TELEM` после включения `dshot_bidir`
  - Возможная причина: ESC без bidir-прошивки (BLHeli_S без Bluejay) или один ESC не отвечает.
  - Что сделать: `dshot_telemetry_info`, прошить Bluejay/AM32 или `dshot_bidir = OFF` (bf-rpm-filter).
- **Симптом:** после клипа ворот аппарат крутится по рысканию и уходит вверх
  - Возможная причина: yaw spin; при `yaw_spin_recovery = OFF` или пороге 1950 спасение включается поздно.
  - Что сделать: `AUTO` или `ON` с порогом на 100–200 °/с выше max yaw; газ в ноль, стики в центр, при затяжной раскрутке больше 0.5 с — дизарм.
- **Симптом:** аппарат подпрыгивает или переворачивается после касания при посадке
  - Возможная причина: airmode защёлкнут, PID держит горизонт пропами в землю.
  - Что сделать: дизарм сразу после касания; в 2025.12 — `landing_disarm_threshold`.

## checklist
- Знаю четыре места, где читать флаги, и что OSD показывает их только при включённом ARM
- Могу по коду пищалки (длинные × 5 + короткие) найти флаг в таблице своей версии
- Декодер маски запущен; помню, что в 2025.12 `ARM_SWITCH` — бит 28
- `small_angle`, `pwr_on_arm_grace`, `min_check` — значения 4.5 по умолчанию известны и не менялись без причины
- Порядок, направление моторов и реакция на наклон рукой проверены без пропов
- `runaway_takeoff_prevention = ON`, `yaw_spin_recovery = AUTO` (или ON с порогом над max yaw)
- Первое висение — низко или на привязи, с критериями немедленного дизарма
- Дизарм сразу после касания при airmode

## references
- Betaflight runtime_config.c / runtime_config.h (имена и биты флагов), 4.5-maintenance | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/runtime_config.c | primary | A
- Betaflight core.c (updateArmingStatus, tryArm, runaway takeoff, auto-disarm), 4.5-maintenance | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c | primary | A
- Betaflight rc_controls.c (арм стиками и тумблером, дизарм) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/rc_controls.c | primary | A
- Betaflight gyro.c (yaw spin recovery, калибровка гиро) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/gyro.c | primary | A
- Betaflight pid.c (crash recovery, умолчания runaway и crash_*) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight beeper.c (коды предупреждений, сигналы арма) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/beeper.c | primary | A
- Betaflight runtime_config.h, 2025.12-maintenance (29 флагов, ARM_SWITCH = бит 28) | https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/fc/runtime_config.h | primary | A
- Betaflight docs: Arming Sequence & Safety | https://betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight docs: Runaway Takeoff Prevention | https://betaflight.com/docs/wiki/guides/current/Runaway-Takeoff-Prevention | primary | A
- Betaflight docs: Yaw Spin Recovery and Gyro Overflow Detect | https://betaflight.com/docs/wiki/guides/current/Yaw-Spin-Recovery-and-Gyro-Overflow-Detect | primary | A
- Oscar Liang: Why your Betaflight drone won't arm | https://oscarliang.com/quad-arming-issue-fix | secondary | B

## notes
Где документация расходится с исходником 4.5, модуль следует исходнику:
- Страница Crash Recovery пишет, что `crash_limit_yaw` «отменяет» спасение при превышении скорости рыскания. В `pid.c` он только ограничивает ошибку рыскания во время спасения.
- Та же страница называет `BEEP` режимом «только пищалка». В `handleCrashRecovery()` 4.5 выравнивание выполняется и при `BEEP`.
- Страница Yaw Spin Recovery описывает режимы ON/OFF и порог 1950 как умолчание. В 4.5 по умолчанию `AUTO`, и порог считается от рейтов.
- Страница Runaway Takeoff Prevention говорит, что подключённый Configurator временно выключает защиту. В прошивке это второй байт команды `MSP_ARMING_DISABLE`, когда Configurator разрешает арм. При каких действиях в интерфейсе он его шлёт, здесь не проверено.

Модель аппарата в шаге 2 учебная: времена на реальном аппарате будут другими, логика порогов — построчно из прошивки.
