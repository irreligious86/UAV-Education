---
id: ap-ahrs-choice
title: "EKF3, EKF2 или DCM: как ArduPilot оценивает положение и что выбрать"
level: L3
readingTime: 55 мин
firmware: ArduPilot 4.7 (сверено с 4.7.2)
status: published
added: 2026-11-23
tags:
  - AHRS
  - EKF3
  - DCM
  - EK3_SRC
  - GSF
  - lane switching
  - счисление пути
related:
  - ap-ekf
  - est-kalman
  - nav-resilience
  - per-visual-nav
  - ap-sensors
  - nav-indoor
  - est-gnss
  - est-alt-sources
  - est-attitude
  - ap-safety-fs
  - ap-quadplane
  - ap-logs
next:
  - est-alt-sources
---

## summary
В ArduPilot за вопрос «где я и как повёрнут» отвечает не один фильтр, а front end `AP_AHRS` с несколькими backend-ами: DCM, EKF3, EKF2, внешний AHRS и симулятор. Модуль разбирает, какой из них реально ведёт аппарат, когда прошивка сама переключается на DCM, жив ли ещё EKF2, как устроены ядра EKF3, наборы источников `EK3_SRC1..3_*`, курс без компаса (GSF), воздушная скорость и ветер у самолёта, EKF-failsafe и сообщения, которые видит пилот. Главный результат — правило выбора оценщика и источников для семи типовых аппаратов и дерево действий, когда EKF ведёт себя плохо. Лабораторная: семь опытов в SITL ArduCopter и ArduPlane 4.7.2 с реальным выводом — потеря GPS в Loiter, переключение на оптический поток, отказ IMU, коптер без компаса и самолёт без GPS в ветре с датчиком скорости и без него.

## theory
### AHRS в ArduPilot: один front end, несколько backend-ов
Контуры управления не спрашивают EKF3 напрямую. Они берут ориентацию, скорость и позицию у объекта `AP_AHRS` (`libraries/AP_AHRS`), а тот на каждом цикле решает, чей ответ отдать. Этот выбор называется активным backend-ом (`_active_EKF_type()`), и его смена видна в GCS сообщением `AHRS: EKF3 active` или `AHRS: DCM active`.

| Backend | Что это | Где есть в 4.7.2 | Как выбрать | Лог |
|---|---|---|---|---|
| DCM | комплементарный фильтр на матрице поворота (`est-attitude`) плюс позиция по GPS или счислению | везде, считается всегда | `AHRS_EKF_TYPE = 0` (только Plane и Rover) или автоматический откат | `AHR2`, когда активен EKF |
| EKF3 | расширенный фильтр Калмана, 24 состояния (`est-kalman`) | везде | `AHRS_EKF_TYPE = 3` (умолчание) | `XKF1…XKF5`, `XKFS`, `XKQ`, `XKY0` |
| EKF2 | предыдущее поколение фильтра | только SITL и сборки custom-сервера с опцией EKF2 | `AHRS_EKF_TYPE = 2`, `EK2_ENABLE = 1` | `NKF1…NKF5`, `NKQ` |
| External AHRS | готовый INS (VectorNav, MicroStrain, InertialLabs, SBG и др., `EAHRS_TYPE`) | на платах с драйвером | `AHRS_EKF_TYPE = 11` | сообщения драйвера |
| SIM | идеальная ориентация из симулятора | только SITL | `AHRS_EKF_TYPE = 10` (новое в 4.7) | — |

Три важных следствия. Первое: DCM обновляется на каждом цикле независимо от выбора (`AP_AHRS::update()` вызывает `update_DCM()` безусловно), поэтому он всегда готов подхватить управление. Второе: в логе `AHR2` пишется «второй» оценщик — DCM, когда активен EKF3, и EKF3, когда при `AHRS_EKF_TYPE = 3` сработал откат на DCM (при `AHRS_EKF_TYPE = 0` строк `AHR2` нет); сравнение `ATT` и `AHR2` — первая проверка, не врёт ли основной. Третье: EKF3 считается и тогда, когда он не активен (при `EK3_ENABLE = 1`), — самолёт на DCM пишет полный `XKF*` в лог.

### AHRS_EKF_TYPE: что допустимо на каком аппарате
Значения параметра в 4.7.2: 0 — Disabled (то есть DCM), 2 — EKF2, 3 — EKF3, 10 — Sim, 11 — ExternalAHRS. Значение 1 (EKF1) удалено давно: при нём плата выдаёт ошибку конфигурации `EKF1 not available`.

- **Copter, Heli, Sub.** В конструкторе `AP_AHRS` для них ставится флаг `FLAG_ALWAYS_USE_EKF`: летать на DCM они не умеют. `AHRS_EKF_TYPE = 0` прошивка молча превращает в EKF (EKF2, если он вкомпилирован, иначе EKF3), но pre-arm сравнивает сохранённое значение с фактическим и не даёт армить: `PreArm: AHRS: not using configured AHRS type` (проверено в SITL, шаг 2). DCM у коптера работает только первые секунды после загрузки, пока EKF3 не стартовал, и если EKF3 сообщает о числовых сбоях фильтра (`getFilterFaults` ≠ 0).
- **Plane и Rover.** `AHRS_EKF_TYPE = 0` — законная конфигурация: аппарат летает на DCM, режимы с позицией берут её прямо из GPS. Так летал HeeWing без компаса из `ap-ekf`. Цена: нет вариаций, ворот и счисления по воздушной скорости с оценкой ветра, ниже точность при GPS-глитчах.
- **Платы с Remote ID.** В `defaults.parm` сборок `*-ODID` стоит `AHRS_EKF_TYPE 3 @READONLY` — сменить оценщик на них нельзя.

### EKF2 в 4.7: честный вердикт
В `AP_AHRS_config.h` по умолчанию `HAL_NAVEKF2_AVAILABLE 0` с комментарием «compiled out by default in 4.5». В release notes Copter 4.5.0-beta1 — «EKF2 removed (can be re-enabled with Custom build server)». Ни одна плата в `libraries/AP_HAL_ChibiOS/hwdef` 4.7.2 его не включает; включает только waf-конфигурация SITL (`-DHAL_NAVEKF2_AVAILABLE=1`) и опция `EKF2` в `build_options.py` для custom.ardupilot.org. Если на обычной прошивке поставить `AHRS_EKF_TYPE = 2`, при следующей загрузке `AP_AHRS::init()` тихо заменит его на 3 (в памяти, без записи в параметры); до перезагрузки pre-arm будет отвечать `not using configured AHRS type`. Параметры `EK2_*` при этом видны в документации и в pdef — это не признак того, что фильтр есть на плате.

Вердикт: на 4.7 EKF2 — не выбор, а музей. Он нужен, только чтобы прочитать старый лог (`NKF*`) или сравнить фильтры в SITL. В SITL он реально работает: у Plane в нашем прогоне в лог шли `EKF2 IMU0 is using GPS` рядом с EKF3. Курс без компаса, наборы источников, оценка ветра коптера по сопротивлению, внешняя навигация с `reset_counter` — всё это развивается в EKF3, и переключение наборов источников (`set_posvelyaw_source_set`) в `AP_AHRS` вызывает только EKF3.

### DCM: что умеет и когда на него откатываются
DCM — комплементарный фильтр: гироскоп интегрируется в матрицу поворота, крен и тангаж подтягиваются к акселерометру (`AHRS_RP_P` = 0.2), курс — к компасу или GPS (`AHRS_YAW_P` = 0.2). Центростремительное ускорение в вираже компенсируется по скорости GPS (`AHRS_GPS_GAIN` = 1.0, не меньше `AHRS_GPS_MINSATS` = 6 спутников). Курс для аппарата, летящего вперёд: компас, но если курс компаса расходится с курсом GPS больше чем на 45° дольше 2 с при скорости от 3 м/с и ветре меньше 80 % путевой скорости, DCM переходит на курс GPS — защита от вылета с плохим компасом. Позицию DCM берёт из GPS (`AHRS_GPS_USE`: 0 — нет, 1 — позиция, 2 — позиция и высота), без GPS — счисление по воздушной скорости и оценённому в виражах ветру.

Автоматический откат на DCM есть только у самолётов (включая VTOL) и наземных аппаратов (`_active_EKF_type()`, ветка `FIXED_WING`/`GROUND`). Первым делом, до любых опций: если EKF3 нездоров (`EKF3.healthy()` = false — числовые сбои фильтра, все три test ratio скорости, позиции и высоты больше 1 или первая секунда после старта), активен DCM. Дальше условия в порядке проверки:

1. EKF3 не даёт ориентацию (наземному аппарату больше ничего не нужно; летающему — ещё вертикальную скорость и высоту) — DCM без вариантов. Обратный случай: если у DCM нет источника курса (компас не используется) и аппарат не летит вперёд, остаётся EKF3.
2. Откат запрещён битом `AHRS_OPTIONS`: бит 0 DisableDCMFallbackFW (полёт вперёд) или бит 1 DisableDCMFallbackVTOL (висение) — остаётся EKF3. На нездоровый EKF3 и пункт 1 этот запрет не действует.
3. Аппарат армлен, GPS видит 3D-фикс, EKF3 настроен на GPS, но GPS не сливает или потерял абсолютную позицию — DCM (DCM поедет по «сырому» GPS).
4. Аппарат армлен и EKF3 в режиме постоянной позиции (`const_pos_mode`) — DCM.
5. Нет горизонтальной скорости или позиции EKF3 — DCM; исключение: компас не используется, GPS с 3D-фиксом и признан годным, скорость меньше 2 м/с — так самолёт без компаса может армиться до выравнивания курса.

Умолчание `AHRS_OPTIONS`: 0 у Plane, 3 у Rover (оба отката запрещены), 16 у Sub. Значит, на 4.7 Rover по умолчанию при потере навигации (пункты 3–5) на DCM не откатывается — только при нездоровом EKF3 и по пункту 1, а Plane откатывается во всех случаях. Пилот видит откат строкой `AHRS: DCM active` и возврат — `AHRS: EKF3 active`; в SITL Plane без датчика скорости после выключения GPS эта пара мелькнула за один цикл, 20 мс (шаг 7). Отдельного «failsafe DCM» нет: режимы с позицией продолжают работать на том, что даёт DCM.

### EKF3 изнутри для начинающих
Математика фильтра — в `est-kalman`; здесь — как она разложена по параметрам. Каждый шаг IMU двигает предсказание (24 состояния: кватернион, скорость и позиция NED, bias гироскопа и акселерометра, магнитное поле Земли и борта, ветер NE). Измерения приходят с задержкой и сливаются «в прошлом», на задержанном горизонте. Перед слиянием каждое проходит тест инновации:

test ratio = y² / ((G/100)² · S),

где y — инновация (разница между предсказанием и измерением; знак для теста не важен), S — её дисперсия (неопределённость предсказания плюс шум измерения), G — параметр ворот в процентах от σ. Для позиции GPS числитель и S — суммы по северу и востоку (`AP_NavEKF3_PosVelFusion.cpp`). Отношение меньше 1 — измерение принято, больше 1 — отброшено. В `XKF4` и в `EKF_STATUS_REPORT` («вариации» в GCS) пишется корень из него: `SP` = |y| / ((G/100)·√S). При G = 500 значение 1.0 означает инновацию в 5σ.

| Измерение | Ворота | Умолчание | Шум измерения | Умолчание Copter / Plane |
|---|---|---|---|---|
| Скорость GPS | `EK3_VEL_I_GATE` | 500 | `EK3_VELNE_M_NSE` | 0.3 / 0.5 м/с |
| Позиция GPS | `EK3_POS_I_GATE` | 500 | `EK3_POSNE_M_NSE` | 0.5 / 0.5 м |
| Высота (баро, дальномер в роли высоты) | `EK3_HGT_I_GATE` | 500 | `EK3_ALT_M_NSE` | 2.0 / 3.0 м |
| Компас (3 оси) | `EK3_MAG_I_GATE` | 300 | `EK3_MAG_M_NSE` | 0.05 / 0.05 Гс |
| Курс (GPS-yaw, внешний) | `EK3_YAW_I_GATE` | 300 | `EK3_YAW_M_NSE` | 0.5 рад |
| Воздушная скорость | `EK3_EAS_I_GATE` | 400 | `EK3_EAS_M_NSE` | 1.4 м/с |
| Дальномер | `EK3_RNG_I_GATE` | 500 | `EK3_RNG_M_NSE` | 0.5 м |
| Оптический поток | `EK3_FLOW_I_GATE` | 300 / 500 | `EK3_FLOW_M_NSE` | 0.25 / 0.15 рад/с |
| Маяки | `EK3_BCN_I_GTE` | 500 | `EK3_BCN_M_NSE` | 1.0 м |

Глубже ворот работают ещё два механизма: `EK3_GLITCH_RAD` (25 м) — пока GPS отвергается воротами, неопределённость позиции растёт, и когда её σ (корень из суммы дисперсий по северу и востоку) превышает этот радиус, фильтр перестаёт спорить и сбрасывает позицию к GPS (то же — по тайм-ауту); и тайм-ауты — без измерений позиции 7 с (10 с, если есть скорость) позиция объявляется потерянной, без любого источника, ограничивающего наклон, 15 с — фильтр переходит в режим постоянной позиции, в GCS `EKF3 IMU0 stopped aiding`. Почему так быстро: ошибка наклона δθ превращает часть g в ложное горизонтальное ускорение g · sin δθ, и без коррекции позиция уходит на ½ · g · sin δθ · t² — при 0.5° это 4.3 м за 10 с.

### Ядра (lanes): EK3_IMU_MASK, EK3_PRIMARY и переключение
EKF3 запускает отдельное ядро на каждый IMU, отмеченный в `EK3_IMU_MASK` (по умолчанию 3 — первые два, биты 0–5 для шести IMU). Маска урезается до фактического числа акселерометров; на каждое ядро нужна память, и при нехватке будет `EKF3 not enough memory`. `EK3_PRIMARY` (0–2, умолчание 0) — индекс в маске, а не номер IMU: пока аппарат не армлен, прошивка принудительно держит это ядро, чтобы каждый полёт начинался одинаково.

Переключение в полёте (`NavEKF3::UpdateFilter`) идёт только у армленного аппарата и не раньше чем через 10 с здоровья основного ядра. У каждого ядра есть error score — максимум из ½·(test ratio скорости + позиции) и test ratio высоты (плюс воздушная скорость и компас, если включены биты `EK3_AFFINITY`). Ядро-кандидат должно быть здоровым и не быть основным последние 10 с. Переход происходит, если у основного score > 1, оно нездорово или кандидат стабильно лучше: на каждом шаге фильтра к относительной ошибке кандидата прибавляется разница score кандидата и основного, но выигрыш засчитывается, только если он больше `EK3_ERR_THRESH` (0.2); сумма ограничена ±1, и при ≤ −0.5 ядро меняется. Ещё одна попытка — от самого автопилота: за одну итерацию до EKF-failsafe он просит `check_lane_switch` (кандидат со score < 0.9, не чаще раза в 5 с). В GCS: `EKF3 lane switch 1` и `EKF primary changed:1`, в логе `ERR` подсистемы 24 с кодом нового ядра и `XKF4.PI`. `EK3_OPTIONS` бит 1 ManualLaneSwitching отключает автоматику полностью — в описании параметра стоит «DANGEROUS».

Главное для выбора: ядра защищают от отказа **одного IMU**. Все ядра видят одни и те же GPS, компас и баро, поэтому общий отказ датчика они не лечат. В SITL при выключенном GPS прошивка всё равно переключила ядро за 0.1 с до failsafe (шаг 3) — бесполезно, потому что второе ядро было в том же положении.

### Наборы источников EK3_SRC1..3 и их переключение
Набор — пять параметров: `EK3_SRCn_POSXY`, `_VELXY`, `_POSZ`, `_VELZ`, `_YAW`. Значения (`AP_NavEKF_Source.cpp`): POSXY — 0 None, 3 GPS, 4 Beacon, 6 ExternalNav; VELXY — те же плюс 5 OpticalFlow и 7 WheelEncoder; POSZ — 0, 1 Baro, 2 RangeFinder, 3 GPS, 4 Beacon, 6 ExternalNav; VELZ — 0, 3, 4, 6; YAW — 0 None, 1 Compass, 2 GPS, 3 GPS с откатом на компас, 6 ExternalNav, 8 GSF. Умолчания: набор 1 — 3/3/1/3/1, наборы 2 и 3 — всё 0, кроме POSZ = 1 (баро). Какие источники для потока, маяков и mocap — таблица в `nav-indoor`.

Активный набор меняют тремя способами, все в полёте:

- **Тумблер** `RCx_OPTION = 90` (EKF Source Set): нижнее положение — набор 1, среднее — 2, верхнее — 3. Только этот путь пишет в GCS `Using EKF Source Set 2`.
- **MAVLink** `MAV_CMD_SET_EKF_SOURCE_SET`, param1 = 1…3 (вне диапазона — `MAV_RESULT_DENIED`). Так переключает companion с VIO.
- **Lua** `ahrs:set_posvelyaw_source_set(0…2)`. Готовый скрипт `applets/ahrs-source-extnav-optflow.lua` выбирает между ExternalNav и потоком по их инновациям.

Текущий набор пишется в `XKFS.SS` (0, 1, 2). `EK3_SRC_OPTIONS`: бит 0 FuseAllVelocities (сливать скорости из всех наборов; в 4.7 по умолчанию снят), бит 1 AlignExtNavPosWhenUsingOptFlow, бит 3 UsePerCoreEKFSources (новое в 4.7: ядрам — разные наборы). Неверная комбинация ловится pre-arm строкой `AHRS: Check EK3_SRC1_POSXY` (так же `_VELXY`, `_POSZ`, `_VELZ`, `_YAW`), а выбранный, но не настроенный датчик — строкой `AHRS: EK3 sources require GPS` (OpticalFlow, RangeFinder, Compass и т. д.).

### Курс: компас, GPS-yaw и GSF
Курс — самое слабое место оценки (`est-attitude`): гравитация его не видит, на висении он не наблюдаем по GPS. Источники `EK3_SRC1_YAW`:

- **1 Compass** — умолчание. Как EKF учит поле в полёте, задаёт `EK3_MAG_CAL`: 0 When flying (умолчание Plane), 1 When manoeuvring, 2 Never (умолчание Rover), 3 After first climb yaw reset (умолчание Copter; в SITL это строка `EKF3 IMU0 MAG0 in-flight yaw alignment complete` через 5.6 с после арма), 4 Always. Старые значения 5 и 6 устарели с 4.1 и дают pre-arm `EK3_MAG_CAL and EK3_SRC1_YAW inconsistent`.
- **2 GPS, 3 GPS с откатом на компас** — курс из двух антенн (moving baseline, `nav-rtk`). При 3 компас подстраивается под GPS-курс и подхватывает после 50 согласных выборок подряд (10 с при 5 Гц).
- **6 ExternalNav** — курс из VIO или mocap (`nav-indoor`, `per-visual-nav`).
- **8 GSF** — оценщик курса по движению: банк из пяти маленьких фильтров с разными начальными курсами (`XKY0.Y0…Y4` и веса `W0…W4`), который по согласию ускорений IMU со скоростью GPS выбирает правильный. Результат `XKY0.YC`, его σ — `XKY0.YCS`.

GSF работает и при компасе: `EK3_GSF_RUN_MASK` = 3 запускает его на первых двух ядрах, `EK3_GSF_USE_MASK` = 3 разрешает аварийный сброс курса по нему, `EK3_GSF_RST_MAX` = 2 — не больше двух сбросов за полёт. Автопилот просит сброс за две итерации до EKF-failsafe (коптер — только если вариации выше порога, а не при потере позиции); в GCS тогда `EKF3 IMU0 emergency yaw reset`, а компас помечается отказавшим. При `EK3_SRC1_YAW = 8` (или без компаса) та же операция штатная: `EKF3 IMU0 yaw aligned using GPS`. Самолёты при плохом курсе компаса по умолчанию выравнивают курс по путевому углу GPS (`EKF3 IMU0 yaw aligned to GPS velocity`), а GSF для этого берут, только если выбран 8; аварийный сброс по запросу автопилота работает и у них.

Коптер без компаса (`COMPASS_USE = 0` у всех, `EK3_SRC1_YAW = 8`) армится только в режиме без позиции: в Loiter — `PreArm: Need Position Estimate`. После взлёта в AltHold нужен прямой полёт: в SITL GSF сошёлся (σ 14.5° → 1.5°) за 1.5 с после разгона выше 1 м/с, а курс был принят на скорости около 3.2 м/с после примерно 4.5 м прямого полёта (шаг 6).

### Самолёт и VTOL: воздушная скорость, скольжение, ветер и полёт без GPS
Для аппарата, который летит вперёд (`fly_forward`, не наземный), EKF3 предполагает малое скольжение (`assume_zero_sideslip()`). Это даёт три вещи, которых нет у коптера:

- **Состояния ветра.** Включаются в полёте, когда путевая скорость больше 5 м/с; начальный ветер берётся «в лоб» курсу — фильтр считает, что взлёт был против ветра. Скорость их изменения — `EK3_WIND_P_NSE` (0.1 м/с² у Plane, 0.2 у Copter), масштаб по вертикальной скорости `EK3_WIND_PSCALE` (1.0). Оценка в `XKF2.VWN/VWE`.
- **Слияние воздушной скорости** (`ARSPD_USE = 1`, шум `EK3_EAS_M_NSE` 1.4 м/с, ворота 400). Пока есть GPS, воздушная скорость уточняет ветер; без GPS она вместе с ветром даёт скорость относительно земли — так работает счисление пути.
- **Слияние скольжения** (`XKF2.IS`). При живом GPS по умолчанию корректирует только ветер; при счислении (нет позиции и скорости дольше 1 с) — все состояния. `EK3_BETA_MASK` бит 0 Always включает это всегда (аппарат без датчика курса), бит 1 WhenNoYawSensor — когда курса нет; описание параметра советует его только для полётов за пределами видимости, где мало разворотов.

Без датчика скорости EKF3 при счислении сливает последнюю оценённую воздушную скорость с огромной неопределённостью (σ не меньше половины самой скорости) — и ошибка растёт много быстрее. SITL ArduPlane 4.7.2, LOITER на 50 м, ветер 7.3 м/с, GPS выключен на 60 с: с датчиком скорости ошибка позиции EKF3 к истине 11.5 м, без датчика — 96.3 м (шаг 7). Это и есть ответ на вопрос «нужен ли самолёту датчик скорости»: для полёта с GPS — желателен, для любой потери GPS — решающий.

Что видят другие подсистемы. `AP_AHRS::airspeed_EAS()` отдаёт датчик, но если EKF3 отвергает его воздушную скорость (флаг `rejecting_airspeed`) в армленном полёте вперёд не во время счисления, датчик подменяется синтетической скоростью |v_земля − ветер| из EKF3 (запрет подмены — `AHRS_OPTIONS` бит 2). Без EKF3 синтетику считает DCM. Синтетика ограничивается путевой скоростью ± `AHRS_WIND_MAX`, если он не 0. На этой величине держатся TECS и порог помощи VTOL — подробности переходов в модулях про VTOL. У коптера ветер EKF3 оценивает по сопротивлению: `EK3_DRAG_BCOEF_X/Y` (масса/лобовая площадь, кг/м²) и `EK3_DRAG_MCOEF` (сопротивление винтов, 1/с), шум `EK3_DRAG_M_NSE` 0.5 м/с²; в SITL-файле `copter-wind-estimates.parm` — 9.5, 9.5 и 0.082.

EKF-failsafe у Plane (`ArduPlane/ekf_check.cpp`) работает только армленным и только в VTOL-режимах с управлением позицией: автоматический Q-режим → QLAND, пилотский → QHOVER. В самолётном полёте его нет — вместо него откат на DCM. Порог тот же `FS_EKF_THRESH` (0.8; у Plane диапазон 0.6–1.0), `FS_EKF_ACTION` у Plane нет. И в отличие от коптера, проверка Plane смотрит только на вариации: пункта «нет позиции» в ней нет.

### EKF-failsafe коптера и сообщения пилоту
`Copter::ekf_check()` вызывается 10 раз в секунду. Проверка не прошла, если (вариация позиции ≥ `FS_EKF_THRESH` и хотя бы одна из компаса или скорости тоже) или и компас, и скорость выше порога (скорость выше удвоенного порога без оптического потока считается за обе) — **или если у EKF нет позиции вообще**. Проверка начинается только после того, как у EKF появился origin и она хоть раз прошла. Десять неудачных проверок подряд (1 с) — failsafe: `EKF variance`, затем `EKF Failsafe: changed to Land Mode`; в логе `ERR` 16/2 и 17/1. На 8-й итерации автопилот просит сброс курса по GSF (только если вариации выше порога), на 9-й — смену ядра. Отбой — `EKF Failsafe Cleared` после того, как счётчик вернётся к нулю.

Пункт про позицию — ловушка: строка называется «EKF variance», а вариации могут быть нулевыми. В SITL после выключения GPS все четыре вариации оставались 0.01, а failsafe пришёл, когда из флагов EKF исчезли биты горизонтальной позиции (0x033f → 0x0025, шаг 3).

Порог в сигмах — `FS_EKF_THRESH` · G/100: 0.8 при воротах скорости и позиции 500 — это инновация 4σ, при воротах компаса 300 — 2.4σ.

`FS_EKF_ACTION`: 0 — только сообщение (новое в 4.7), 1 — Land, если режим требует позиции (умолчание), 2 — AltHold, если требует (при уже сработавшем RC failsafe или неудаче — Land), 3 — Land из любого режима. В режиме без позиции при 1 и 2 будет только `EKF Failsafe`. Land при этом переводится в посадку без GPS. `FS_EKF_THRESH` = 0.8 (0 отключает проверку), `FS_EKF_FILT` = 5 Гц — фильтр вариаций.

| Сообщение | Откуда | Что значит |
|---|---|---|
| `PreArm: AHRS: EKF3 not started` | `AP_AHRS::pre_arm_check` | EKF3 ещё не инициализирован (стартует не раньше 1 с после загрузки) или выключен `EK3_ENABLE = 0` |
| `PreArm: AHRS: not using configured AHRS type` | то же | значение `AHRS_EKF_TYPE` недопустимо для аппарата или активен не тот backend при используемом компасе |
| `PreArm: Need Position Estimate` | `AP_Arming_Copter` | режим требует позиции, а её нет: нет GPS, нет origin, курс без компаса ещё не выровнен |
| `PreArm: AHRS: EKF3 Yaw inconsistent 25 deg. Wait or reboot` | `attitudes_consistent` | ядра или DCM расходятся по курсу (по крену и тангажу — `Roll/Pitch`) |
| `PreArm: AHRS: GPS HDOP 3.1 (needs 2.5)` и соседние `GPS horiz error`, `GPS drift` | проверки `EK3_GPS_CHECK` | GPS ещё не годится для выравнивания; пороги масштабирует `EK3_CHECK_SCALE` |
| `PreArm: AHRS: EKF3[1] vel error 2.4` | `NavEKF3_core::pre_arm_check` | на земле инновация скорости GPS больше 2 м/с |
| `PreArm: EKF attitude is bad` | `AP_Arming_Copter` | ориентация EKF не сходится — чаще всего bias гироскопа после движения при загрузке |
| `EKF3 IMU0 stopped aiding` | ядро EKF3 | 15 с без источника, ограничивающего наклон: режим постоянной позиции |
| `AHRS: DCM active` | `AP_AHRS::update` | у Plane или Rover сработал откат; у Copter — до старта EKF3 |

### Логи: что открыть
- `XKF4` по ядрам (`C`): `SV`, `SP`, `SH`, `SM`, `SVT` — корни test ratio; `SS` — флаги решения (биты как у `nav_filter_status`: 0 ориентация, 1 гориз. скорость, 3 и 4 относительная и абсолютная позиция, 7 постоянная позиция, 13 используется GPS, 17 отвергается воздушная скорость, 18 счисление); `PI` — основное ядро; `FS`, `TS` — сбои и тайм-ауты.
- `XKF3` — инновации и `ErSc` (error score), `RErr` (относительная ошибка ядра); `XKF2` — bias акселерометра, ветер, поле, инновации сопротивления и скольжения; `XKF1` — состояние; `XKF5` — поток и дальномер; `XKFS` — выбранные компас, баро, GPS, airspeed и набор источников `SS`; `XKQ` — кватернион ядра; `XKY0/XKY1` — GSF.
- `AHR2` — второй оценщик (см. выше), `ATT` — что видели контуры. `NKF*` — то же для EKF2.
- `EK3_LOG_LEVEL`: 0 — всё (умолчание), 1 — только `XKF4`, 2 — `XKF4` и GSF, 3 — ничего потокового.
- Строки `MSG`: `EKF3 IMU0 is using GPS` (ядро начало слияние GPS, ждать её перед армом в режимах с позицией), `EKF3 IMU0 fusing optical flow`, `EKF3 IMU0 is using external nav data`, `EKF3 IMU0 initialised`, `tilt alignment complete`, `origin set`.

### Правила выбора
| Аппарат и условие | `AHRS_EKF_TYPE` | Набор 1 (POSXY/VELXY/POSZ/VELZ/YAW) | Запасные наборы и переключение | Ключевые параметры | Чего не делать |
|---|---|---|---|---|---|
| Коптер с GPS и компасом | 3 | 3/3/1/3/1 (умолчания) | не нужны | `EK3_IMU_MASK` на все исправные IMU, `FS_EKF_ACTION` 1 | поднимать `FS_EKF_THRESH` ради арма |
| Самолёт | 3 | 3/3/1/3/1, `ARSPD_USE = 1` | не нужны | `EK3_MAG_CAL` 0, `AHRS_OPTIONS` 0 (откат на DCM разрешён) | ставить 0 «потому что проще» без причины, как в кейсе HeeWing |
| VTOL (QuadPlane) | 3 | как у самолёта, компас для висения | не нужны | датчик скорости, EKF-failsafe Q-режимов → QLAND или QHOVER | летать Q-режимами с позицией без проверенного компаса |
| Без GPS в помещении | 3 | поток 0/5/1/0/1, UWB 4/0/4/0/1, mocap 6/6/6/6/6 | GPS в наборе 1 снаружи, помещение в наборе 2, `RCx_OPTION = 90` | origin через `SET_GPS_GLOBAL_ORIGIN`, `VISO_DELAY_MS`; маяки в 4.7 вкомпилированы только при флеше больше 2 МБ (`AP_BEACON_ENABLED`), на типичной H7 — сборка custom-сервера | Loiter по потоку выше дальности дальномера |
| Компас ненадёжен | 3 | 3/3/1/3/8, `COMPASS_USE = 0`; с двумя антеннами 3/3/1/3/2 или 3 | не нужны | арм в AltHold, прямой полёт до `yaw aligned using GPS` | армиться в Loiter (`Need Position Estimate`) |
| VIO на companion | 3 | GPS (3/3/1/3/1) | набор 2: 6/6 (или VELXY 0)/1 или 6/6 или 0/6, переключение `MAV_CMD_SET_EKF_SOURCE_SET` или Lua | `VISO_TYPE = 1`, `reset_counter` | слать «замёрзшую» позу при потере трекинга (`per-visual-nav`) |
| Плата 1 МБ (F405) | 3 | GPS (3/3/1/3/1), поток 0/5/1/0/1, компас или GSF (8) | наборы и тумблер есть | ExternalNav, VisualOdom, drag-оценка ветра и одометрия (у Copter и Plane) вырезаны: требуют больше 1024 КБ; в `minimize_common.inc` нет ещё MAVLink-GPS (`GPS_INPUT`) и двухантенного курса — VIO на такой плате на стандартной прошивке не подать | искать EKF2 или DCM-полёт коптера; планировать VIO на F405 |

{{diagram:ahrs-choice-tree|Решение принимается в два шага: тип аппарата задаёт, допустим ли DCM, а то, откуда берутся позиция и курс, задаёт набор EK3_SRC; во всех ветках оценщик — EKF3.}}

### Когда EKF ведёт себя плохо
1. **Прочитай строку целиком.** `PreArm: AHRS: …` — конфигурация или ожидание GPS; `EKF variance` — открывай `XKF4`; `EKF3 lane switch` — сравнивай ядра; `AHRS: DCM active` у самолёта — EKF3 потерял позицию или нездоров.
2. **Найди поле выше порога в `XKF4`.** `SM` — компас: помехи от тока, калибровка (`ap-sensors`), курс 3 или 8. `SV`/`SP` — GPS: спутники, `GPA.HAcc`, глитч, задержка `GPS1_DELAY_MS` (`nav-resilience`). `SH` — баро или вибрации.
3. **Если всё около нуля** — смотри `SS`: пропали биты 3 и 4 — источник позиции исчез, проблема не в «вариациях», а в данных (GPS отключился, набор источников без позиции).
4. **Lane switch без внешней причины** — сравни `XKF4` ядер `C=0` и `C=1`: одно ядро растёт, другое нет — виноват IMU, вибрации или клиппинг (`ap-logs`).
5. **Не трогай порог и ворота**, пока не нашёл причину: `FS_EKF_THRESH` 0.8 при воротах 500 — это уже 4σ.

{{diagram:ahrs-ekf-trouble-tree|Ветка «всё около нуля» — самая обманчивая: сообщение называется EKF variance, а причина — исчезнувший источник позиции, что видно по флагам SS, а не по вариациям.}}

### Место в системе

- **Получает:** IMU, GPS, компас, баро, воздушную скорость, дальномер и поток (`est-sensors`, `est-gnss`, `est-alt-sources`, `ap-sensors`); внешнюю позу от companion (`per-visual-nav`, `nav-indoor`).
- **Отдаёт:** ориентацию, скорость, позицию и ветер — контурам управления и режимам с позицией (`ap-missions`, `ap-quadplane`); вариации и флаги — в EKF-failsafe и pre-arm (`ap-safety-fs`); `XKF*`, `AHR2` — в лог (`ap-logs`).
- **Если ошибиться здесь:** коптер без компаса армят в Loiter → `Need Position Estimate`, а после взлёта в AltHold курс без прямого полёта не сходится (`nav-resilience`). Самолёт без датчика скорости теряет GPS → счисление уходит на 96 м за минуту, RTL ведёт не туда (`ap-safety-fs`).

## practice
Главный путь — SITL ArduCopter и ArduPlane 4.7.2 (сборка `./waf configure --board sitl && ./waf copter plane`, как в `ap-sitl`). Время в выводе — секунды от загрузки; при тех же параметрах времена событий в SITL повторяются с точностью до 0.1–0.5 с, а уход по `SIM` — с точностью около метра (полностью детерминированным SITL не является).

### Шаг 1. Кто активен при загрузке
Скрипт ниже (опыты шагов 3–5; шаги 2 и 6 выполнены теми же функциями `pump`, `setp`, `mode` с командами, перечисленными в шаге) запускает SITL, ведёт аппарат и печатает `STATUSTEXT`, смену режима и `EKF_STATUS_REPORT` (вариации и флаги). Положи его в корень дерева ArduPilot; для опыта `flow` рядом нужен `flow.parm` (шаг 4). Последний аргумент — номер экземпляра SITL.

```python
"""EKF3 behaviour in ArduCopter 4.7.2 SITL: GPS loss, source set switch, IMU fault.
Run: python3 ahrs_lab.py gpsloss|flow|lane [instance]   (arducopter built with ./waf copter; flow.parm next to it for 'flow')."""
import subprocess, sys, time
from pymavlink import mavutil

BIN, DEF = 'build/sitl/bin/arducopter', 'Tools/autotest/default_params/copter.parm'
exp = sys.argv[1]
I = int(sys.argv[2]) if len(sys.argv) > 2 else 5        # SITL instance: ports 5760 + 10*I
defaults = DEF + (',flow.parm' if exp == 'flow' else '')
sitl = subprocess.Popen([BIN, '-S', '-w', '--model', '+', '--defaults', defaults, f'-I{I}',
                         '--home', '50.45,30.52,100,0'], stdout=subprocess.DEVNULL)
time.sleep(3)
m = mavutil.mavlink_connection(f'tcp:127.0.0.1:{5760 + 10 * I}', source_system=255)
m.wait_heartbeat()
m.mav.request_data_stream_send(m.target_system, 1, mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
rc = [1500, 1500, 1000, 1500, 1800, 1000, 1000, 1000]   # RC override: throttle low, ch5 fixed
st = {'t': 0.0, 'mode': None, 'ekf': None}


def pump(sec, every=None, quiet=False):
    """Read MAVLink for sec seconds; print STATUSTEXT, mode changes and EKF_STATUS_REPORT."""
    t0 = last = time.time()
    while time.time() - t0 < sec:
        m.mav.rc_channels_override_send(m.target_system, 1, *rc)
        r = m.recv_match(blocking=True, timeout=0.1)
        if r is None:
            continue
        typ = r.get_type()
        if typ == 'SYSTEM_TIME':
            st['t'] = r.time_boot_ms / 1000
        elif typ == 'STATUSTEXT' and not quiet:
            print(f"{st['t']:7.1f} s  MSG  {r.text}")
        elif typ == 'HEARTBEAT' and r.get_srcComponent() == 1 and r.type != 6:
            md = mavutil.mode_string_v10(r)
            if md != st['mode'] and not quiet:
                print(f"{st['t']:7.1f} s  MODE {md}")
            st['mode'] = md
        elif typ == 'EKF_STATUS_REPORT':
            st['ekf'] = r
        if every and st['ekf'] and time.time() - last >= every:
            e, last = st['ekf'], time.time()
            print(f"{st['t']:7.1f} s  EKF  vel={e.velocity_variance:.2f} pos={e.pos_horiz_variance:.2f}"
                  f" hgt={e.pos_vert_variance:.2f} mag={e.compass_variance:.2f} flags=0x{e.flags:04x}")


def setp(name, value):
    m.mav.param_set_send(m.target_system, 1, name.encode(), value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    print(f"{st['t']:7.1f} s  SET  {name} = {value:g}")


def mode(name):
    m.mav.set_mode_send(m.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, m.mode_mapping()[name])
    pump(1)


pump(45, quiet=True)                                    # boot, EKF origin, "is using GPS"
mode('GUIDED')
m.mav.command_long_send(m.target_system, 1, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
pump(2)
alt = 10 if exp == 'flow' else 20
m.mav.command_long_send(m.target_system, 1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, alt)
pump(15)
rc[2] = 1500                                            # throttle to mid before LOITER
mode('LOITER')
pump(5, every=5)
if exp == 'gpsloss':
    setp('SIM_GPS1_ENABLE', 0); pump(40, every=2)
elif exp == 'flow':
    rc[6] = 1500                                        # RC7_OPTION = 90: middle = source set 2
    pump(10, every=5)
    setp('SIM_GPS1_ENABLE', 0); pump(40, every=5)
elif exp == 'lane':
    pump(10)
    setp('SIM_ACC1_BIAS_Z', 3); pump(30, every=3)       # first IMU gets +3 m/s^2 on Z
sitl.terminate()
```

Загрузка (первые 45 с, в моём прогоне печатались без `quiet`):

```
    0.0 s  MSG  AHRS: DCM active
    4.3 s  MSG  EKF3 IMU0 initialised
    4.3 s  MSG  EKF3 IMU1 initialised
    4.3 s  MSG  AHRS: EKF3 active
    5.8 s  MSG  EKF3 IMU0 tilt alignment complete
    5.8 s  MSG  EKF3 IMU0 MAG0 initial yaw alignment complete
   19.8 s  MSG  EKF3 IMU0 origin set
   41.5 s  MSG  EKF3 IMU0 is using GPS
   41.5 s  MSG  EKF3 IMU1 is using GPS
```

Два ядра — потому что в SITL два IMU и `EK3_IMU_MASK = 3`. Первые 4.3 с активен DCM — это единственная штатная его роль у Copter: армить в это время нельзя, EKF3 ещё не стартовал.

### Шаг 2. AHRS_EKF_TYPE = 0 на коптере
На земле, после `is using GPS`: `AHRS_EKF_TYPE = 0`, попытка арма в STABILIZE.

```
   46.0 s  SET  AHRS_EKF_TYPE = 0
   46.0 s  MSG  AHRS: DCM active
   47.0 s  MSG  EKF variance
   47.0 s  MSG  Arm: EKF attitude is bad
   47.0 s  MSG  Arm: AHRS: not using configured AHRS type
   52.3 s  SET  AHRS_EKF_TYPE = 3
   52.3 s  MSG  AHRS: EKF3 active
```

Коптер не армится даже в STABILIZE. Особенность SITL: в нём вкомпилирован EKF2, поэтому 0 превратился в «EKF2», который выключен (`EK2_ENABLE = 0`), — и активным стал DCM. На плате без EKF2 активным останется EKF3, но строка `not using configured AHRS type` будет та же: pre-arm сравнивает сохранённое значение с фактическим.

### Шаг 3. Потеря GPS в Loiter
`python3 ahrs_lab.py gpsloss`: взлёт в GUIDED на 20 м, LOITER, затем `SIM_GPS1_ENABLE = 0` (до 4.7 — `SIM_GPS_DISABLE = 1`).

```
   69.8 s  SET  SIM_GPS1_ENABLE = 0
   76.1 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x033f
   77.8 s  MSG  EKF3 lane switch 1
   77.8 s  MSG  EKF primary changed:1
   78.1 s  MODE LAND
   78.1 s  MSG  EKF variance
   78.1 s  MSG  EKF Failsafe: changed to Land Mode
   78.1 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x0025
   85.1 s  MSG  EKF3 IMU1 stopped aiding
   85.1 s  MSG  EKF3 IMU0 stopped aiding
   86.6 s  EKF  vel=0.00 pos=0.00 hgt=0.00 mag=0.01 flags=0x00a7
   92.1 s  MSG  SmartRTL deactivated: bad position
```

Расшифровка флагов (`EKF_STATUS_FLAGS`): 0x033f — ориентация, обе скорости, относительная и абсолютная позиция, высота, прогноз позиции; 0x0025 — осталось только 1 + 4 + 32: ориентация, вертикальная скорость, высота; 0x00a7 — добавился бит 128, режим постоянной позиции. Вариации ни разу не поднялись выше 0.01, а failsafe сработал по пункту «нет позиции»: в выводе скрипта через 8.3 с, по логу точнее — `PARM SIM_GPS1_ENABLE` в 70.06 с, `ERR` 17/1 в 78.14 с, то есть 8.1 с (печатное время отстаёт на 0.2–0.3 с: `SYSTEM_TIME` приходит несколько раз в секунду). Переключение ядра в 78.04 с, за 0.1 с до failsafe, — та самая попытка `check_lane_switch`, бесполезная при общем отказе. `stopped aiding` пришло в 85.21 с, через 15.2 с, — тайм-аут 15 с без источника наклона. По `SIM` в логе аппарат к моменту failsafe ушёл от точки на 1.2 м, к 16-й секунде — на 4.3 м (ветра нет): Land без GPS позицию не держит.

### Шаг 4. Набор источников 2 — оптический поток
`flow.parm` (поток SITL и дальномер, как в `Tools/autotest/default_params/copter-optflow.parm`, но поток — в наборе 2):

```
FLOW_TYPE 10
SIM_FLOW_ENABLE 1
RNGFND1_TYPE 1
RNGFND1_MIN 0
RNGFND1_MAX 40.00
RNGFND1_PIN 0
RNGFND1_SCALING 12.12
EK3_SRC2_POSXY 0
EK3_SRC2_VELXY 5
EK3_SRC2_POSZ 1
EK3_SRC2_VELZ 0
EK3_SRC2_YAW 1
RC7_OPTION 90
```

`python3 ahrs_lab.py flow`: Loiter на 10 м по GPS, тумблер RC7 в середину, потом выключение GPS.

```
   69.8 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.02 flags=0x037f
   70.3 s  MSG  Using EKF Source Set 2
   70.3 s  MSG  EKF3 IMU1 fusing optical flow
   70.3 s  MSG  EKF3 IMU0 fusing optical flow
   79.8 s  SET  SIM_GPS1_ENABLE = 0
   84.8 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x016f
  115.1 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x016f
```

0x016f = 1 + 2 + 4 + 8 + 32 + 64 + 256: абсолютная позиция ушла (сняты флаги 16 и 512), относительная осталась, режим LOITER, failsafe нет 35 с. Истинный уход от точки по `SIM` — около 1 м (без ветра; в трёх прогонах максимум 0.8–1.4 м за 36–40 с). Сравни с шагом 3: тот же отказ GPS, но запасной набор источников превратил посадку в продолжение полёта.

### Шаг 5. Отказ одного IMU и ядра
`python3 ahrs_lab.py lane`: в Loiter на 20 м первому IMU добавляется `SIM_ACC1_BIAS_Z = 3` м/с².

```
   79.8 s  SET  SIM_ACC1_BIAS_Z = 3
   80.8 s  MSG  EKF3 lane switch 1
   80.8 s  MSG  EKF primary changed:1
   82.8 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.02 flags=0x033f
```

Лог (`XKF4` двух ядер, тот же прогон):

```
 80.06 PARM SIM_ACC1_BIAS_Z 3.0
 80.64 XKF4 C=0 SV=0.44 SP=0.00 SH=0.01 PI=0
 80.64 XKF4 C=1 SV=0.02 SP=0.00 SH=0.00 PI=0
 80.81 MSG EKF3 lane switch 1
 80.81 ERR Subsys=24 ECode=1
 81.84 XKF4 C=0 SV=1.32 SP=0.00 SH=0.24 PI=1
 81.84 XKF4 C=1 SV=0.02 SP=0.00 SH=0.00 PI=1
```

Ядро 0 переключено через 0.75 с после применения параметра (80.06 → 80.81 с). Последняя запись перед переключением — `SV` = 0.44; к моменту переключения error score ядра 0 (`XKF3.ErSc`) дошёл до 0.21, это ½·SV² при SV ≈ 0.65. Разница с исправным ядром превысила `EK3_ERR_THRESH` = 0.2, относительная ошибка ядра 1 за доли секунды упёрлась в −1 (`XKF3.RErr`) — сработало правило «кандидат стабильно лучше», а не score > 1. Ещё через секунду `SV` испорченного ядра дошёл до 1.32: его измерения скорости уже отбрасывались бы. Посчитай руками, что значит 0.44: при `EK3_VEL_I_GATE = 500` инновация скорости равна 0.44 · 5 = 2.2σ. Аппарат режим не менял: на исправном IMU EKF здоров.

### Шаг 6. Коптер без компаса
Тот же SITL с `COMPASS_USE`, `COMPASS_USE2`, `COMPASS_USE3` = 0 и `EK3_SRC1_YAW = 8`. Арм в LOITER, затем в ALT_HOLD, подъём 6 с, тангаж 1300 мкс (полёт вперёд).

```
   47.0 s  MSG  Arm: Need Position Estimate
   51.0 s  MODE ALT_HOLD
   52.0 s  MSG  Arming motors
   60.0 s  EKF  vel=0.00 pos=0.00 hgt=0.00 mag=0.00 flags=0x00a7
   62.8 s  MSG  EKF3 IMU1 yaw aligned using GPS
   62.8 s  MSG  EKF3 IMU0 yaw aligned using GPS
   62.8 s  MSG  EKF3 IMU0 is using GPS
   63.0 s  EKF  vel=0.00 pos=0.00 hgt=0.00 mag=0.00 flags=0x033f
```

По логу `XKY0` (курс истинный 0°): в 60.5 с `YC` = 273.6°, `YCS` = 14.4°; в 61.0 с, при 1.0 м/с, — 356.3° и 5.1°; в 61.5 с — 357.3° и 2.6°; в 62.5 с — 357.8° и 1.5°. Курс принят в 62.8 с на скорости около 3.2 м/с, пройдено около 4.5 м от начала разгона (по `GPS`: 2.4 м/с и 2.2 м к 62.0 с, 3.4 м/с и 5.1 м к 63.0 с). После этого LOITER включился без отказа.

### Шаг 7. Самолёт без GPS в ветре
ArduPlane SITL (`--model plane`, `Tools/autotest/models/plane.parm`), `SIM_WIND_SPD 8`, `SIM_WIND_DIR 270`. Ветер в SITL растёт с высотой по корню до `SIM_WIND_T_ALT` = 60 м, поэтому на 50 м он 8 · √(50/60) = 7.30 м/с. Взлёт в TAKEOFF до 50 м, LOITER, `SIM_GPS1_ENABLE = 0` на 60 с. Два прогона: `ARSPD_USE = 1` и `ARSPD_USE = 0`. Ошибку позиции EKF3 к истине считает скрипт:

```python
"""EKF position error against SITL truth: python3 poserr.py <run dir> <t0 s> <t1 s> <step s>.
POS = AHRS position (EKF3 when active), SIM = simulator truth, XKF2.VWE = EKF wind estimate (moving-to-East)."""
import glob, math, sys
from pymavlink import mavutil

run, ta, tb, step = sys.argv[1], *map(float, sys.argv[2:5])
log = mavutil.mavlink_connection(sorted(glob.glob(run + '/logs/0*.BIN'))[-1])
sim = wind = xkf4 = None
last = -99
while (r := log.recv_match(type=['SIM', 'POS', 'XKF2', 'XKF4', 'MSG'])) is not None:
    t, typ = r.TimeUS / 1e6, r.get_type()
    if typ == 'SIM':
        sim = r
    elif typ == 'XKF2' and r.C == 0:
        wind = (r.VWN, r.VWE)
    elif typ == 'XKF4' and r.C == 0:
        xkf4 = r
    elif typ == 'MSG' and ta <= t <= tb:
        print(f'{t:7.1f} MSG {r.Message}')
    elif typ == 'POS' and sim and wind and xkf4 and ta <= t <= tb and t - last >= step:
        last = t
        dn = (r.Lat - sim.Lat) * 111320                                   # degrees -> metres
        de = (r.Lng - sim.Lng) * 111320 * math.cos(math.radians(sim.Lat))
        print(f'{t:7.1f} POS err vs truth {math.hypot(dn, de):.1f} m wind_est N={wind[0]:.1f} E={wind[1]:.1f}'
              f' SS=0x{xkf4.SS:x}')
```

Вывод (GPS выключен в 110.0 с, включён в 170.0 с) — выборка из двух прогонов рядом, часть строк и поля `N=` и `SS` опущены:

```
ARSPD_USE = 1                                         ARSPD_USE = 0
  110.0 POS err vs truth 1.0 m wind_est E=7.1           110.0 POS err vs truth 1.0 m wind_est E=6.0
  125.1 POS err vs truth 2.2 m SS=0x5812f               117.3 MSG AHRS: DCM active
  140.1 POS err vs truth 6.9 m                          117.3 MSG AHRS: EKF3 active
  155.2 POS err vs truth 7.8 m                          125.1 POS err vs truth 17.7 m SS=0x5812f
  165.3 POS err vs truth 11.8 m                         140.1 POS err vs truth 39.7 m
  170.3 POS err vs truth 11.5 m                         155.2 POS err vs truth 75.0 m
                                                        170.3 POS err vs truth 96.3 m
```

`SS = 0x5812f` — биты 0–3, 5, 8, 15, 16 и 18: позиция относительная, флаг счисления (бит 18) поднят, абсолютной позиции нет. С датчиком ветер оценён в 7.1 м/с при истинных 7.3; оценка ошибки Δw · t = 0.2 · 60 = 12 м совпала с измеренными 11.5–11.8 м. Без датчика ветер 6.4 м/с, а ошибка 96.3 м — заметно больше, чем объяснил бы ветер (0.9 · 60 = 54 м): неизвестна ещё и сама воздушная скорость.

{{diagram:chart-ahrs-deadreckon|С датчиком воздушной скорости ошибка счисления за минуту без GPS укладывается в оценку Δw·t ≈ 12 м, без датчика она в восемь раз больше — это и решает, нужен ли датчик.}}

### Переход на реальное железо
1. **Без пропов, на столе.** Подключи GCS, дождись `EKF3 IMU0 is using GPS` (на улице). Проверь `AHRS_EKF_TYPE = 3`, `EK3_IMU_MASK` по числу IMU (`INS_*` в списке датчиков), набор 1. Сравни `ATT.Yaw` и `AHR2.Yaw` в коротком логе с `LOG_DISARMED = 1`: расхождение больше 20° — компас или его ориентация. Поверни аппарат по кругу: `XKF4.SM` должен оставаться < 0.3.
2. **Тумблер набора источников.** Если есть поток или VIO: `RCx_OPTION = 90`, на земле щёлкни в среднее положение — `Using EKF Source Set 2`, затем `fusing optical flow` или `is using external nav data`. Без этой строки в воздух с набором 2 не выходить.
3. **Первый полёт с пропами.** Высота 5–10 м, AltHold на тумблере. Переключение на набор 2 — только над ровной текстурной поверхностью в пределах дальности дальномера; держи палец на AltHold. Коптер без компаса: взлёт в AltHold, прямой полёт 5–10 с на 3–5 м/с до `yaw aligned using GPS`, только потом Loiter.
4. **Самолёт.** До полёта без GPS проверь `ARSPD_USE = 1` и что `XKF4.SS` бит 17 (rejecting airspeed) не поднимается на прямой; оценка ветра `XKF2.VWN/VWE` за первые 2–3 виража должна сойтись с прогнозом погоды по направлению. Отключение GPS в воздухе на реальном аппарате не делай — используй лог реальной потери, если она была.

Критерии приёмки железа: `EKF3 IMU0 is using GPS` перед каждым армом в режимах с позицией; `XKF4.SV/SP/SM` < 0.5 в спокойном висении; ни одного `lane switch` за 10 полётов; у коптера без компаса курс выравнивается меньше чем за 10 с прямого полёта; у самолёта `XKF2` ветер отличается от прогноза не больше чем на 3 м/с.

Самопроверка: лабораторная выполнена, когда для SITL-пути: (1) в шаге 2 получена строка `AHRS: not using configured AHRS type` и арм не прошёл; (2) в шаге 3 переход в LAND с `EKF Failsafe: changed to Land Mode` наступил через 8.1 ± 0.5 с по логу (`PARM` → `ERR` 17/1; 8.3 с по выводу скрипта) после `SIM_GPS1_ENABLE = 0`, при вариациях не выше 0.02 и флагах 0x033f → 0x0025; (3) в шаге 4 после `Using EKF Source Set 2` и выключения GPS аппарат 35 с остаётся в LOITER с флагами 0x016f; (4) в шаге 5 переключение ядра наступило через 0.75 ± 0.3 с после `PARM SIM_ACC1_BIAS_Z` в логе, а 0.44 пересчитано в 2.2σ; (5) в шаге 6 `yaw aligned using GPS` пришло через 4–6 с прямого полёта; (6) в шаге 7 ошибка через 60 с равна 11.5 ± 2 м с датчиком и 96 ± 10 м без него, и оценка Δw · t = 12 м совпала с первым числом в пределах 3 м. Для железа — критерии приёмки выше.

**Эталон для самопроверки.**

| Результат | Верно | Типичная ошибка и причина |
|---|---|---|
| Шаг 3, время до LAND | 8.1 с по логу, вариации 0.01 | «failsafe не пришёл» — стоит `FS_EKF_ACTION = 0` или режим не требует позиции; «пришёл за 1 с» — выключен не GPS, а EKF (`EK3_ENABLE`) |
| Шаг 4, флаги | 0x016f, LOITER | 0x0025 и LAND — тумблер не в среднем положении или в `flow.parm` пропущен `RC7_OPTION 90`; нет `fusing optical flow` — не включён `SIM_FLOW_ENABLE` |
| Шаг 5, сигмы | 0.44 · 500/100 = 2.2σ | 0.44σ — забыта нормировка на ворота; 0.44² — путают корень test ratio с самим отношением |
| Шаг 7, ошибка 60 с | 11.5 и 96.3 м | одинаковые числа в двух прогонах — `ARSPD_USE` поменян без перезапуска; ошибка около нуля — не задан `SIM_WIND_SPD` |

## diagnostics
- **Симптом:** `PreArm: AHRS: not using configured AHRS type` на коптере
  - Возможная причина: `AHRS_EKF_TYPE = 0` или 2 на сборке без EKF2; у самолёта — EKF3 нездоров и активен DCM при используемом компасе.
  - Что сделать: `AHRS_EKF_TYPE = 3`, `EK3_ENABLE = 1`, перезагрузка; у самолёта — найти, почему EKF3 нездоров (`XKF4`).
- **Симптом:** `EKF variance` и Land, хотя в GCS все столбики вариаций зелёные
  - Возможная причина: у EKF нет горизонтальной позиции — GPS пропал или активный набор источников без позиции.
  - Что видно в логе: `XKF4.SS` без битов 3 и 4, `GPS.Status` упал, вариации около 0.
  - Что сделать: найти, почему пропал источник (питание GPS, разъём, набор `EK3_SRCn`), а не порог; запасной набор с потоком или VIO (шаг 4).
- **Симптом:** `EKF3 lane switch` в полёте без видимой причины
  - Возможная причина: один IMU шумнее — вибрации, клиппинг, нагрев.
  - Что видно в логе: `XKF4.SV/SH` одного ядра растут, у другого нет; `VIBE.Clip` у этого IMU.
  - Что сделать: механика и демпфирование (`ap-logs`); редкие переключения нормальны, частые — нет.
- **Симптом:** у самолёта в GCS `AHRS: DCM active`
  - Возможная причина: EKF3 не сливает GPS или потерял позицию при живом 3D-фиксе, либо ушёл в режим постоянной позиции.
  - Последствия: режимы с позицией идут по «сырому» GPS, без ворот против глитчей.
  - Что сделать: `XKF4.SP`, `GPA.HAcc`, глитчи; запрещать откат (`AHRS_OPTIONS` бит 0) только осознанно.
- **Симптом:** коптер без компаса не армится в Loiter, а в AltHold после взлёта «рыскает» и не входит в Loiter
  - Возможная причина: курс GSF не выровнен — аппарат висит или летит медленнее 1–2 м/с.
  - Что сделать: прямой полёт 5–10 с на 3–5 м/с до `EKF3 IMU0 yaw aligned using GPS`; смотреть `XKY0.YCS` < 5°.
- **Симптом:** `EKF3 IMU0 emergency yaw reset` в полёте
  - Возможная причина: курс компаса ушёл (помеха от тока), GSF спас курс и пометил компас отказавшим.
  - Что сделать: `ap-sensors` (CompassMot, вынос компаса); помнить, что сбросов не больше `EK3_GSF_RST_MAX` = 2 за полёт.
- **Симптом:** самолёт без GPS возвращается «не туда» на десятки метров
  - Возможная причина: нет датчика воздушной скорости или EKF отвергает его (бит 17 в `XKF4.SS`).
  - Что сделать: поставить и откалибровать датчик (`ap-sensors`); счисление с ним — около 12 м за минуту в ветре 7 м/с против 96 м без него.

## references
- ArduPilot source 4.7.2 — AP_AHRS (front end, fallback, pre-arm) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_AHRS/AP_AHRS.cpp | primary | A
- ArduPilot source 4.7.2 — AP_NavEKF3 (parameters, lanes, GSF, air data) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.2/libraries/AP_NavEKF3 | primary | A
- ArduPilot source 4.7.2 — EKF source sets (AP_NavEKF_Source.cpp) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_NavEKF/AP_NavEKF_Source.cpp | primary | A
- ArduPilot source 4.7.2 — Copter EKF failsafe (ekf_check.cpp) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/ekf_check.cpp | primary | A
- ArduPilot docs — Extended Kalman Filter navigation overview | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- ArduPilot docs — EKF Source Selection and Switching | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- ArduPilot docs — Compass-less Operation (EK3_SRC1_YAW = 8, GSF) | https://ardupilot.org/copter/docs/common-compassless.html | primary | A
