---
id: nav-rtk
title: "RTK/PPK: база и ровер, NTRIP, moving baseline, GPS yaw"
level: L3
readingTime: 45 мин
firmware: ArduPilot 4.6 · PX4 1.15+
status: published
added: 2026-11-10
tags:
  - RTK
  - RTCM
  - NTRIP
  - moving baseline
  - GPS yaw
  - F9P
related:
  - est-gnss
  - ap-ekf
  - est-kalman
  - nav-resilience
  - per-landing
next:
  - per-landing
---

## summary
В модуле «GNSS» RTK был одним абзацем. Здесь — вся цепочка: как база узнаёт свою точку (survey-in или известные координаты), какие сообщения RTCM3 она шлёт, как они доезжают до ровера (NTRIP-кастер → Mission Planner/QGC → `GPS_RTCM_DATA` → UART приёмника), что значат float/fixed и возраст поправок, и как два F9P на раме дают курс без компаса (moving baseline, «GPS for yaw»). Разобраны параметры ArduPilot 4.6 (`GPS1_TYPE = 17/18`, `GPS1_POS_*`, `GPS1_MB_*`, `GPS_DRV_OPTIONS`, `EK3_SRC1_YAW = 2`) и PX4-эквиваленты (`GPS_UBX_MODE`, `GPS_YAW_OFFSET`, `EKF2_GPS_CTRL`). Лабораторная: moving baseline в SITL с реальным выводом `GPS2_RAW.yaw`, лог с `GPS.Status = 6`, скрипт «тип fix → точность» на сгенерированном логе ровера, затем стенд из двух F9P.

## theory
### RTK и PPK — одна математика, разное время
Обе убирают общие для базы и ровера ошибки (ионосфера, тропосфера, орбиты, часы) через разности фазы несущей и фиксируют целочисленные неоднозначности (integer ambiguities). Разница — когда.

| | RTK (real-time kinematic) | PPK (post-processed kinematic) |
|---|---|---|
| Когда | в полёте, каждую эпоху | после полёта, по двум сырым логам |
| Нужна связь база→ровер | да, непрерывно (радио, 4G, NTRIP) | нет |
| Что даёт автопилоту | позицию 1–3 см в EKF, точную посадку, GPS yaw | ничего в полёте; координаты снимков для фотограмметрии |
| Что логировать | обычный лог; статус fix | RXM-RAWX с обоих приёмников: ArduPilot `GPS_RAW_DATA = 1` (сообщения `GRAW/GRXH/GRXS`), PX4 `GPS_DUMP_COMM = 2` |

Цифры для ZED-F9P (data sheet ZED-F9P-04B): стандартный PVT 1.5 м CEP (1.0 м с SBAS), RTK 0.01 м + 1 ppm (1 ppm = 1 мм на километр базовой линии; для 20 км — 3 см), сходимость < 10 с при нескольких созвездиях, скорость 0.05 м/с. Из-за «1 ppm» NTRIP-станцию берут не дальше ~50–100 км: на 100 км это 11 см и худшая сходимость.

### База: survey-in или известная точка
Ошибка координат базы **целиком** переносится на ровер — RTK даёт сантиметры *относительно базы*. Два способа задать точку (u-blox `CFG-TMODE-MODE`):
- **Survey-in** (`SURVEY_IN`): приёмник усредняет свою позицию, пока не выполнены оба условия — минимальная длительность `CFG-TMODE-SVIN_MIN_DUR` и предел 3D-точности `CFG-TMODE-SVIN_ACC_LIMIT`. В Mission Planner это поля «SurveyIn Acc (m)» и «Time (s)»; типично 2 м и 60 с. Абсолютная точность такой базы — метры, относительная точность ровера — сантиметры: для посадки на ту же площадку хватает, для карты в государственной системе координат — нет. Во время survey-in базе нельзя подавать чужие поправки.
- **Известные координаты** (`FIXED`, `CFG-TMODE-POS_TYPE` + `_HP`-ключи с миллиметровой точностью): точка от геодезиста, от многочасового survey-in или от PPK по сети постоянных станций. Mission Planner хранит её («Save»/«Use») — годится, только если база стоит на том же месте.

### RTCM3: что именно летит от базы
Набор, который u-blox рекомендует для базы F9P и который включает Mission Planner (`ubx_m8p.cs`: 1005 и 1230 каждые 5 с, MSM раз в секунду):

| Сообщение | Содержание | Зачем |
|---|---|---|
| 1005 | координаты антенны базы (ECEF); 1006 — то же плюс высота антенны | без неё ровер не знает, относительно чего считать |
| 1074 / 1084 / 1094 / 1124 | MSM4: наблюдения GPS / GLONASS / Galileo / BeiDou (псевдодальность, фаза, C/N0) | сами поправки; MSM4 компактнее |
| 1077 / 1087 / 1097 / 1127 | MSM7: те же созвездия с полной точностью и доплером | альтернатива MSM4, набор QGC/PX4; не смешивать с MSM4 в одном потоке |
| 1230 | смещения кодовой фазы GLONASS | без 1230 (или 1033) GLONASS остаётся float даже при RTK fixed |
| 4072.0 | проприетарное u-blox: PVT базы для moving baseline | обязательно в каждой эпохе для режима MB; для статичной базы не нужно |

Поток на 1 Гц при четырёх созвездиях — единицы кБ/с; F9P поднимает MB до 5 Гц, но тогда UART2 нужен 460800 бод, а задержка доставки должна быть меньше периода навигации минус 50 мс (≈150 мс для 5 Гц). Ровер перестаёт использовать поправки старше `CFG-NAVSPG-CONSTR_DGNSSTO` (по умолчанию 60 с) и падает в 3D/DGNSS.

### Доставка: NTRIP, Mission Planner, MAVLink
**NTRIP** — HTTP-подобный протокол: кастер (caster) на порту 2101 отдаёт sourcetable с точками монтирования (mount points), клиент логинится и получает поток RTCM. Публичный пример — RTK2go (бесплатный, логин — валидный e-mail, пароль `none`); коммерческие сети дают виртуальную станцию рядом с тобой. Строка в Mission Planner: `http://user:pass@host:2101/MOUNT`.

Дальше поправки едут в аппарат по телеметрии: **Mission Planner → Setup → Optional Hardware → RTK/GPS Inject** режет поток на пакеты `GPS_RTCM_DATA` (id 233; `flags`: бит 0 — фрагментирован, биты 1–2 — номер фрагмента, биты 3–7 — sequence id; `data[180]`). Старый `GPS_INJECT_DATA` (id 123, 110 байт) в MAVLink помечен superseded с 2022-05, ArduPilot его ещё принимает. На борту `AP_GPS::handle_gps_rtcm_fragment()` собирает фрагменты и пишет байты в UART приёмника, выбранного `GPS_INJECT_TO` (0 — первый, 1 — второй, 127 — все). `GPA.RTCMFU/RTCMFD` в логе — фрагменты использованные/выброшенные. При двух источниках RTCM драйвер начинает полный разбор сообщений; бит 6 `GPS_DRV_OPTIONS` включает его принудительно, бит 7 — запрещает. Альтернатива без GCS: радиомодем базы прямо в UART2 ровера.

### Состояния fix и возраст поправок
`GPS_RAW_INT.fix_type` и `GPS.Status` в логе — одна шкала `AP_GPS::GPS_Status`: 0 нет GPS, 1 нет fix, 2 — 2D, 3 — 3D, 4 — DGPS, **5 — RTK float**, **6 — RTK fixed**. Float — неоднозначности ещё вещественные, точность порядка 10–50 см и «плывёт» (практический ориентир, в data sheet u-blox такой цифры нет); fixed — целочисленные, 1–3 см. У u-blox статус берётся из `carrSoln` в UBX-NAV-PVT. Важно: драйвер u-blox в ArduPilot 4.6 не заполняет `rtk_age_ms`, поэтому `GPS2_RAW.dgps_age` для F9P всегда 0 (в `GPS_RAW_INT` такого поля нет вовсе) — возраст поправок смотри в Mission Planner (окно RTK) или по `RTCMFU`; `dgps_age` честно заполняют только драйверы ERB, NOVA и SBF. EKF3 не различает float и fixed: шум измерения позиции он берёт как `max(GPA.HAcc, EK3_POSNE_M_NSE)²`, а `EK3_POSNE_M_NSE` у Copter по умолчанию 0.5 м (`AP_NavEKF3_PosVelFusion.cpp`, `R_OBS[3]`). Сантиметры RTK попадают в фильтр, только если снизить этот параметр (0.1–0.2 м для посадки); то же для скорости — `EK3_GPS_V_NSE` 0.3 м/с.

### Moving baseline: курс по двум антеннам
Если «база» стоит на самой раме, RTK решает вектор между антеннами с точностью около сантиметра; его направление — курс. Погрешность: σ_yaw ≈ atan(σ_rel / L); при σ_rel = 1 см и L = 1 м — 0.57°. Data sheet ZED-F9P-04B (табл. «moving base») даёт heading accuracy 0.4° без указания длины линии в таблице — зависимость от длины показана отдельным графиком; при L = 30 см по той же формуле выходит около 2° (оценка, не спецификация). ArduPilot требует ≥ 30 см между антеннами, u-blox для дрона называет 20–30 см. Курс есть **стоя на земле** — преимущество перед GSF (`EK3_SRC1_YAW = 8`), которому нужно движение, и перед компасом у силовых проводов.

{{diagram:rtk-mb-yaw-chain|База шлёт роверу 4072.0 + MSM4 по UART2, ровер отдаёт RELPOSNED, драйвер проверяет длину базовой линии против GPSx_POS и только при RTK fixed отдаёт курс в EKF3; любой сбой превращает GPS2_RAW.yaw в 65535.}}

ArduPilot 4.6 (до 4.6 имена без индекса: `GPS_TYPE`, `GPS_TYPE2`, `GPS_POS1_X`, `GPS_MB1_TYPE` — апгрейд переименовывает автоматически):
- `GPS1_TYPE = 17` (uBlox-MovingBaseline-Base), `GPS2_TYPE = 18` (Rover); DroneCAN — 22/23; Unicore UM982 — 25; Septentrio dual antenna — 26.
- `GPS1_POS_X/Y/Z`, `GPS2_POS_X/Y/Z` — фазовые центры антенн относительно центра аппарата (X вперёд, Y вправо, Z вниз); из них драйвер считает ожидаемую линию. Или `GPS1_MB_TYPE = 1` и `GPS1_MB_OFS_X/Y/Z` — вектор базы относительно ровера напрямую. `GPS_YAW_OFFSET` в ArduPilot нет — ориентацию линии задают эти офсеты.
- Проверки в `calculate_moving_base_yaw()`: линия ≥ 5 см, расхождение измеренной и заданной длины ≤ 20 % от меньшей из них, вертикальная составляющая — в пределах ожидаемой по наклону рамы ± 20 % длины, у ровера `fix = 6`. Иначе курс не отдаётся.
- `GPS_AUTO_SWITCH = 1` (UseBest); **не 2 (Blend)**. `GPS_DRV_OPTIONS` бит 0 — RTCM между модулями по кроссоверу UART2↔UART2 (иначе ArduPilot гоняет поправки базы через свой UART); бит 3 — то же по отдельному CAN.
- `EK3_SRC1_YAW = 2` (GPS) или `3` (GPS с откатом на компас). EKF3 ограничивает заявленную точность снизу 5° (`min_yaw_accuracy_deg`), ворота — `EK3_YAW_I_GATE`. В логе: `GPS.Yaw`, `GPA.YAcc`, `XKF3.IYAW` (градусы), `XKF4.SM`.
- `GPS2_RAW.yaw`: 0 — курс не настроен, 65535 — настроен, но сейчас недоступен, 1…36000 — сотые доли градуса (36000 = север). F9H как ровер сообщает фиктивную длину 1 м — проверка по длине линии с ним не работает.

### PX4 — коротко
`GPS_UBX_MODE = 2` на базе, `1` на ровере (UART1 обоих — в автопилот, UART2 базы → UART2 ровера, 5 Гц; режимы 3/4 — RTCM по UART1), `GPS_YAW_OFFSET` — угол линии «база→ровер» от носа (0 — ровер впереди, 90 — справа), `EKF2_GPS_CTRL` бит 3 «Dual antenna heading» (по умолчанию 7, с курсом 15). Поправки идут из QGroundControl через `GPS_RTCM_DATA`; QGC настраивает базу на 1005 (0.2 Гц), 1077, 1087, 1097, 1127, 1230 (1 Гц).

## practice
Главный путь — SITL ArduCopter 4.6.3 (`arducopter -S --model + --defaults copter.parm,copter-gps-for-yaw.parm`). Симулятор u-blox всегда отдаёт `carrSoln = fixed` (`SIM_GPS_UBLOX.cpp`, `pvt.flags = 0b10000011`), поэтому `fix_type = 6` появляется без базы — конвенция SITL, не достижение. Зато moving baseline честный: при `SIM_GPS2_HDG = 1` второй приёмник считает RELPOSNED из `SIM_GPS_POS_Y`/`SIM_GPS2_POS_Y` и истинного курса модели. SIM-параметры первого приёмника в 4.6.3 без индекса (`SIM_GPS_ACC`), второго — с индексом (`SIM_GPS2_ACC`).

### Шаг 1. Параметры стенда
`Tools/autotest/default_params/copter-gps-for-yaw.parm` — эталон: `EK3_SRC1_YAW 2`, `GPS_AUTO_CONFIG 0`, `GPS1_TYPE 17`, `GPS2_TYPE 18`, `GPS1_POS_Y -0.2`, `GPS2_POS_Y 0.2`, те же `SIM_GPS_POS_Y`/`SIM_GPS2_POS_Y`, `SIM_GPS2_DISABLE 0`, `SIM_GPS2_HDG 1`. Линия 0.4 м поперёк рамы: база слева, ровер справа. Читаем параметры через pymavlink (фрагмент вывода):

```
== params (copter-gps-for-yaw.parm)
  GPS1_TYPE = 17.0
  GPS2_TYPE = 18.0
  GPS1_POS_Y = -0.20000000298023224
  GPS2_POS_Y = 0.20000000298023224
  GPS1_MB_TYPE = 0.0
  GPS_AUTO_SWITCH = 1.0
  GPS_DRV_OPTIONS = 0.0
  EK3_SRC1_YAW = 2.0
  SIM_GPS_HDG = 0.0
  SIM_GPS2_HDG = 1.0
  SIM_GPS_ACC = 0.30000001192092896
```

### Шаг 2. Дождаться fix 6 и курса
Цикл по `GPS2_RAW`, пока `fix_type < 6` — так же делает автотест `GPSForYaw` (`wait_gps_fix_type_gte(6, message_type="GPS2_RAW")`, затем yaw 270 ± 5° при доме с курсом 270). Наш дом задан с курсом 353°:

```
  t+ 8.4s fix_type=1 sats=3 yaw=35306 (cdeg) h_acc=0 mm dgps_age=0 ms
  t+ 8.6s fix_type=6 sats=10 yaw=35300 (cdeg) h_acc=300 mm dgps_age=0 ms
== GPS_RAW_INT (base, instance 1) vs GPS2_RAW (rover, instance 2)
  GPS_RAW_INT: fix_type=6 sats=10 eph=121 h_acc=300 mm v_acc=300 mm vel_acc=0 mm/s yaw=0
  GPS2_RAW:    fix_type=6 sats=10 eph=121 h_acc=300 mm yaw=35300 cdeg dgps_numch=0 dgps_age=0
== GPS yaw vs EKF yaw, 10 samples
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw= 344.48 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw=   0.00 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw=   0.01 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw= 353.00 deg
  GPS2_RAW.yaw= 353.00 deg   ATTITUDE.yaw= 353.01 deg
```

Записать: у базы `yaw = 0` (курс не настроен), у ровера 35300; EKF на земле держит 0°, затем выравнивается на 353° без единого метра движения. `h_acc = 300 мм` — это `SIM_GPS_ACC = 0.3`, не RTK; `dgps_age = 0` — драйвер u-blox поле не заполняет.

### Шаг 3. Сломать базовую линию
`GPS2_POS_Y 0.2 → 0.5`: заданная линия становится 0.7 м, приёмник по-прежнему меряет 0.4 м, разница 0.3 м > 20 % от меньшей длины (0.08 м):

```
== B. GPS2_POS_Y -> 0.5
  [bad-ofs] GPS2_RAW.yaw=35300 cdeg fix=6 h_acc=300 mm   EKF yaw=353.09 deg
  [bad-ofs] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.10 deg
  [bad-ofs] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.21 deg
== C. restored 0.2
  [restored] GPS2_RAW.yaw=35300 cdeg fix=6 h_acc=300 mm   EKF yaw=353.20 deg
== D. SIM_GPS2_HDG -> 0: rover stops sending UBX-NAV-RELPOSNED
  [no-relposned] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.17 deg
  [no-relposned] GPS2_RAW.yaw=65535 cdeg fix=6 h_acc=300 mm   EKF yaw=353.31 deg
```

Для паспорта: при 65535 аппарат **не падает** — EKF3 ведёт курс по гироскопу (дрейф 0.1–0.2° за 10 с в SITL, на реальном IMU — градусы в минуту), и при `EK3_SRC1_YAW = 2` отката на компас нет. Повтори с `= 3` и посмотри `XKF4.SM`.

### Шаг 4. Точность в SITL и лог
`SIM_GPS2_ACC 0.3 → 0.02`: через секунду `h_acc = 20 mm` — так выглядит RTK-fixed приёмник в `GPS2_RAW` (в EKF3 это число упрётся в `EK3_POSNE_M_NSE = 0.5`, пока его не снизить). Включи `LOG_DISARMED = 1` на 20 с и прочитай `.BIN` через `DFReader`:

```
GPS {'I': 0, 'Status': 6, 'NSats': 10, 'HDop': 1.21, 'Yaw': 353.0, 'U': 1}
GPA {'I': 0, 'HAcc': 0.3, 'VAcc': 0.3, 'SAcc': 0.0, 'YAcc': 0.0, 'Delta': 200, 'RTCMFU': 0, 'RTCMFD': 0}
GPS {'I': 1, 'Status': 6, 'NSats': 10, 'HDop': 1.21, 'Yaw': 353.0, 'U': 0}
XKF3 {'C': 0, 'IVN': 0.01, 'IPN': 0.0, 'IMX': 0, 'IYAW': -0.29, 'IVT': 0.0}
XKF4 {'C': 0, 'SV': 0.0, 'SP': 0.0, 'SM': 0.01, 'SS': 107327, 'PI': 0}
```

`GPS.Status = 6` у обоих экземпляров, `GPA.Delta = 200` мс (5 Гц), `XKF3.IYAW = −0.29°` — инновация курса, `GPA.YAcc = 0` — SITL не моделирует `accHeading`; на железе здесь будет `accHeading` из RELPOSNED — порядка десятых долей градуса–единиц градусов в зависимости от длины линии и неба (ориентир, не спецификация).

### Шаг 5. Тип fix против точности на логе ровера
Реального F9P-лога у курса нет, поэтому скрипт генерирует 300-секундный CSV (`t, fix_type, hacc_m, nsats, corr_age_s`): 3D → поправки с 20-й секунды → DGPS → float → fixed на 60-й; с 150-й обрыв NTRIP на 25 с, возраст поправок растёт до 26 с, fix откатывается fixed → float → 3D; повторная сходимость 15 с. hAcc по состояниям — из data sheet (1.5 м / 0.014 м) и типичного float 0.25 м. Тот же скрипт принимает настоящий CSV из u-center или из `GPS`+`GPA` лога:

```python
rows = load(sys.argv[1]) if len(sys.argv) > 1 else generate()
for k in sorted(FIX):
    h = sorted(r[2] for r in rows if r[1] == k)
    if h:
        print(f"{FIX[k]:10} {len(h):4d} {len(h)/len(rows):6.1%} {sum(h)/len(h):8.3f} m {h[int(len(h)*0.95)]:7.3f} m")
lost = [r for r in rows if r[4] >= 10]
print(f"samples with correction age >= 10 s: {len(lost)}, worst age {max(r[4] for r in rows):.0f} s")
```

```
300 fixes, 299 s
fix           n  share  hAcc mean  hAcc p95
3D           27   9.0%    1.435 m   1.945 m
DGPS         15   5.0%    0.587 m   0.836 m
RTK float    50  16.7%    0.250 m   0.358 m
RTK fixed   208  69.3%    0.014 m   0.019 m
time-to-fixed from first correction: 40 s
samples with correction age >= 10 s: 17, worst age 26 s, fix during them: ['3D', 'RTK float']
```

{{diagram:chart-rtk-fix-hacc|Точность скачет на два порядка между состояниями: float 25 см не годится для посадки с порогом 5 см, а 25-секундный обрыв поправок отбрасывает ровер к метрам — следи за возрастом поправок, а не только за флагом fixed.}}

Для паспорта: доля fixed (здесь 69 %), время до fixed (40 с), худший возраст поправок (26 с) и состояние во время обрыва.

### Переход на реальное железо
Стенд: два ZED-F9P (прошивка ≥ 1.3.2), две антенны с ground plane ≥ 40 мм на рейке 50 см, автопилот с двумя свободными UART, Mission Planner, 4G для NTRIP. **Пропы сняты на всех шагах** — курс и RTK проверяются на столе и тележке, полёт не нужен.
1. **Одиночный RTK.** Один F9P как `GPS1_TYPE = 2`, в RTK/GPS Inject — NTRIP `http://email:none@rtk2go.com:2101/MOUNT` с точкой ≤ 50 км. Критерий: `fix_type` 3 → 5 → 6 за < 60 с, `h_acc` ≤ 30 мм, `GPA.RTCMFU` растёт, `RTCMFD = 0`. Выдерни 4G на 30 с и запиши, через сколько секунд fix упал до 5 и до 3 (предел 60 с по `CONSTR_DGNSSTO`).
2. **Своя база.** Второй F9P на штативе через USB в Mission Planner, survey-in 2 м / 60 с до «Position is Valid», сохранить позицию. Ровер по телеметрии должен выйти в 6. Критерий: fixed держится 10 мин, разброс позиции на месте < 3 см (скрипт из модуля «GNSS» на `GPS.Lat/Lng`).
3. **Moving baseline.** Оба модуля на раме: `GPS1_TYPE 17`, `GPS2_TYPE 18`, `GPS1_POS_Y −0.25`, `GPS2_POS_Y +0.25` (0.5 м поперёк, рулеткой до фазовых центров), `GPS_AUTO_SWITCH 1`, `EK3_SRC1_YAW 3`, кроссовер UART2↔UART2 и `GPS_DRV_OPTIONS = 1`. Критерий: `GPS2_RAW.yaw` ≠ 0 и ≠ 65535 в течение 5 мин; поворачивай рейку по 90° по разметке на столе — `GPS.Yaw` отличается от разметки ≤ 2°; откалиброванный компас (`ATTITUDE.yaw` при `EK3_SRC1_YAW = 1`) и GPS-курс расходятся ≤ 3° с учётом склонения. Затем впиши `GPS2_POS_Y 0.55` — курс должен пропасть (65535): проверка, что офсеты читаются.
4. **Лог-критерии** для всех трёх: `GPS.Status` ≥ 5 не менее 95 % времени, `GPA.Delta` ≈ 200 мс без пропусков > 400 мс, `GPA.SAcc` < 0.1 м/с, `GPA.YAcc` < 2°, `XKF3.IYAW` < 5° по модулю, `XKF4.SM` < 0.5, отсутствие `EKF3 ... yaw re-aligned` в сообщениях после первых 30 с.

Лабораторная засчитывается, когда (SITL) в выводе скрипта есть `GPS2_RAW.fix_type = 6` и `yaw` в пределах ±1° от курса дома, показан переход в 65535 при сломанном офсете и при отключённом RELPOSNED с продолжением курса EKF, лог содержит `GPS.Status = 6` и `XKF3.IYAW`, а таблица «тип fix → hAcc mean/p95» и график построены по CSV с указанием доли fixed и худшего возраста поправок; (железо) одиночный RTK дошёл до fix 6 с `h_acc` ≤ 30 мм и зафиксировано время деградации при обрыве NTRIP, своя база держит fixed 10 мин, moving baseline даёт курс в пределах 2° от разметки и 3° от компаса, а лог-критерии п. 4 выполнены.

## diagnostics
- **Симптом:** fix застрял на 5 (float), fixed не наступает
  - Возможная причина: база дальше 50–100 км, нет 1230 (GLONASS float), антенна ровера без ground plane / под пропами, многолучёвость.
  - Что сделать: ближайший mount point, проверить состав RTCM в окне RTK (должны идти 1005 + MSM + 1230), поднять антенну, отключить GLONASS в `GPS1_GNSS_MODE` на пробу.
- **Симптом:** fix 6 есть, но позиция в Loiter уходит на метры
  - Возможная причина: база после survey-in с ошибкой 2 м — это относительная точность; либо перезапущенный survey-in дал другую точку.
  - Что сделать: для абсолютной точности — известные координаты базы; дом/миссию задавать уже при fixed.
- **Симптом:** `GPS2_RAW.yaw = 65535` при fix 6
  - Возможная причина: длина линии по `GPSx_POS` расходится с измеренной > 20 %, антенны ближе 5 см, разная высота антенн, RELPOSNED не приходит (нет 4072.0 на UART2, не тот `GPS_DRV_OPTIONS`).
  - Что видно в логе: `GPS[1].Yaw = 0`, `GPA[1].YAcc = 0`, EKF курс медленно дрейфует.
  - Что сделать: перемерить офсеты до фазовых центров, проверить кроссовер UART2 и бод (38400 для 1 Гц, 460800 для 5 Гц), `GPS_AUTO_CONFIG = 1`.
- **Симптом:** `GPS2_RAW.yaw = 0`
  - Возможная причина: ровер не сконфигурирован как 18/23/25, или ровер и база перепутаны (RELPOSNED отдаёт только ровер).
  - Что сделать: `GPS2_TYPE = 18`, база 17; на PX4 — `GPS_UBX_MODE` 2 у базы и 1 у ровера.
- **Симптом:** курс по GPS отличается от компаса на 90° или 180°
  - Возможная причина: перепутаны знаки `GPS1_POS_Y`/`GPS2_POS_Y` (на PX4 — неверный `GPS_YAW_OFFSET`).
  - Что сделать: база слева → `GPS1_POS_Y` отрицательный; повернуть рейку и сверить направление изменения.
- **Симптом:** в логе `RTCMFD` растёт, `RTCMFU` стоит
  - Возможная причина: телеметрия теряет фрагменты `GPS_RTCM_DATA` (низкий бод, перегруженный канал), sequence id не сходится.
  - Что сделать: 57600+ на телеметрии, MSM4 вместо MSM7, снизить частоту базы до 1 Гц, или радиомодем в UART2 ровера.
- **Симптом:** EKF3 «yaw inconsistent» / `XKF4.SM` > 1 при `EK3_SRC1_YAW = 3`
  - Возможная причина: компас врёт (силовые провода), а GPS-курс верный — конфликт источников.
  - Что сделать: compassmot или перенос компаса; на стенде временно `EK3_SRC1_YAW = 2`, сравнить `XKF3.IYAW`.

## references
- ArduPilot — GPS for Yaw (moving baseline) | https://ardupilot.org/copter/docs/common-gps-for-yaw.html | primary | A
- ArduPilot — RTK correction: Mission Planner RTK/GPS Inject, NTRIP | https://ardupilot.org/copter/docs/common-rtk-correction.html | primary | A
- ArduPilot source 4.6.3 — AP_GPS params, moving-base checks, SITL GPS (`libraries/AP_GPS/AP_GPS.cpp`, `GPS_Backend.cpp`, `libraries/SITL/SIM_GPS_UBLOX.cpp`, `Tools/autotest/default_params/copter-gps-for-yaw.parm`) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.6.3 | primary | A
- MAVLink common.xml — GPS_RTCM_DATA (233), GPS_INJECT_DATA (123), GPS_FIX_TYPE, GPS_RTK | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A
- u-blox — ZED-F9P-04B Data sheet (RTK accuracy, MB heading 0.4°, update rates) | https://content.u-blox.com/sites/default/files/ZED-F9P-04B_DataSheet_UBX-21044850.pdf | primary | A
- u-blox — ZED-F9H-01B Data sheet (heading rover) | https://content.u-blox.com/sites/default/files/ZED-F9H-01B_DataSheet_UBX-21025012.pdf | primary | A
- u-blox — ZED-F9P Integration manual (TMODE survey-in, RTCM set, DGNSS timeout) | https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf | primary | A
- u-blox — ZED-F9P Moving base application note | https://content.u-blox.com/sites/default/files/documents/ZED-F9P-MovingBase_AppNote_UBX-19009093.pdf | primary | A
- PX4 — RTK GPS heading with dual u-blox F9P | https://docs.px4.io/main/en/gps_compass/u-blox_f9p_heading.html | primary | A
- PX4 — RTK GPS integration (QGC, GPS_RTCM_DATA, RTCM set) | https://docs.px4.io/main/en/advanced/rtk_gps.html | primary | A
- PX4 source v1.15 — `src/drivers/gps/params.c`, `src/modules/ekf2/module.yaml` | https://github.com/PX4/PX4-Autopilot/tree/v1.15.4 | primary | A
- Mission Planner source — `ConfigSerialInjectGPS.cs`, `ExtLibs/Utilities/ubx_m8p.cs` (survey-in, RTCM rates, GPS_RTCM_DATA fragments) | https://github.com/ArduPilot/MissionPlanner | primary | B
- RTK2go — community NTRIP caster | http://rtk2go.com/ | secondary | B

## checklist
- Различаю RTK и PPK, знаю, что логировать для PPK
- Понимаю разницу survey-in и известных координат базы и куда уходит ошибка базы
- Знаю минимальный набор RTCM3 (1005, MSM4 ×4, 1230; 4072.0 для MB) и его частоты
- Умею подать поправки через NTRIP → Mission Planner → `GPS_RTCM_DATA` и прочитать `RTCMFU/RTCMFD`
- Читаю fix 5/6 и возраст поправок; знаю, что `dgps_age` у u-blox в 4.6 не заполняется
- Настраиваю moving baseline (`GPS1_TYPE 17/18`, `GPSx_POS`, `EK3_SRC1_YAW 2/3`) и понимаю проверки 5 см / 20 %
- Проверил GPS-курс в SITL и на стенде против разметки и компаса
