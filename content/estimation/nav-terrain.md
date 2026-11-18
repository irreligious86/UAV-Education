---
id: nav-terrain
title: "Следование рельефу: terrain data, дальномер, TERRAIN_*, безопасность"
level: L2
readingTime: 40 мин
firmware: ArduCopter 4.7 (сверено с 4.7.2; лабораторная снята на 4.6.3) · ArduPlane 4.7 · PX4 1.17 (сверено с v1.17.0)
status: published
tags:
  - terrain following
  - SRTM
  - дальномер
  - RTL_ALT_TYPE
  - failsafe
related:
  - est-alt-sources
  - ap-missions
  - ap-safety-fs
  - ap-plane-tuning
  - aero-wing
next:
  - nav-resilience
---

## summary
«40 м над землёй» в холмах — это три системы отсчёта и два источника данных о земле: база SRTM на борту и дальномер. Модуль разбирает, как ArduPilot (и коротко PX4) следует рельефу, за что отвечают `TERRAIN_*`, `RNGFND*`, `SURFTRAK_*`, `RTL_ALT_TYPE`, что происходит без данных и почему SRTM не видит деревья. Лабораторная — миссия в SITL через гору Маджура (перепад 288 м) с базой и с дальномером, график истинной высоты над землёй по логу, удар о склон при RTL с неверным типом высоты и terrain failsafe при потере дальномера.

## theory
### Три высоты
Барометр, GPS и дальномер как источники высоты разобраны в est-alt-sources; здесь — что из них значит «над землёй». Frame точки миссии (модуль ap-missions): `MAV_FRAME_GLOBAL` (0) — над уровнем моря (AMSL); `MAV_FRAME_GLOBAL_RELATIVE_ALT` (3) — над точкой арма; `MAV_FRAME_GLOBAL_TERRAIN_ALT` (10, в Mission Planner «Terrain») — над землёй: `h_AGL = h_AMSL − h_terrain(lat, lon)`. Откуда взять `h_terrain` — и есть весь модуль.

| Источник | Что измеряет | Дальность / точность | Где врёт |
|---|---|---|---|
| База рельефа на SD-карте («SRTM») | модель поверхности (DSM), а не голой земли: SRTM — радарная съёмка 2000 г.; тайлы terrain.ardupilot.org собраны из JAXA ALOS, 0–84° широты; сетка `TERRAIN_SPACING` 100 м | типично ±10 м, на вершине лыжного склона замечено 35 м (документация ArduPilot) | деревья, здания, карьеры и отвалы новее съёмки |
| Дальномер вниз (лидар/радар) | расстояние до ближайшей поверхности под аппаратом | 7–180 м по модели; ±2–5 см | кроны и трава — «земля», вода и чёрный асфальт для лидара, наклон, не видит вперёд |

База даёт карту заранее (профиль проверяется до вылета), дальномер — реальную поверхность, но только под собой.

### База рельефа на борту
`TERRAIN_ENABLE = 1` включает базу. Полётник запрашивает недостающие клетки сообщением `TERRAIN_REQUEST`, GCS (Mission Planner, QGC, MAVProxy `module load terrain`) отвечает `TERRAIN_DATA` блоками 4×4 точки; данные пишутся в `APM/TERRAIN/S36E149.DAT` (файл на градус, 2.5 МБ при шаге 100 м) и остаются на SD. База SRTM3 у GCS — 100 м; `TERRAIN_SPACING` меньше 100 только тратит SD. Состояние — `TERRAIN_REPORT` (`pending`, `loaded`, `terrain_height`, `current_height`) и лог `TERR.TerrH/CHeight/Pending/Loaded/ROfs`. Пока `pending != 0` или нет высоты дома и точек миссии, terrain-миссия не армится: `PreArm: waiting for terrain data` (`AP_Terrain::pre_arm_checks`).

`TERRAIN_OFS_MAX` (30 м) — при арме база сдвигается так, чтобы высота дома совпала с GPS/баро (`TERR.ROfs`; в лаборатории +1.08 м), не больше этого значения. `TERRAIN_MARGIN` (0.05) — допуск по координатам при приёме блоков от GCS, не высота безопасности. Единица в метаданных — м, в описании — «centi-meters»; по коду (`TERRAIN_LATLON_EQUAL`: `margin × 100` в единицах 1e-7°) 0.05 ≈ 5 единиц ≈ 5.6 см, то есть фактически метры. `TERRAIN_CACHE_SZ` (12 блоков 32×28 по ≈1.8 кБ) — кэш в памяти. В 4.7 добавлен бит 2 `TERRAIN_OPTIONS` «Accept Old Terrain Data»: тайлы, созданные до 24 февраля 2026 г., содержат ошибки старого генератора, без бита 4.7 не армит («terrain data expired, possible errors») — папку `APM/TERRAIN` удалить и скачать заново.

### Как Copter держит высоту над рельефом
В AUTO точка с frame Terrain — это смещение `terr_offset` над EKF-началом; источник выбирает `AC_WPNav::get_terrain_source()`: **если дальномер вниз настроен и `WP_RFND_USE = 1` (по умолчанию 1; до 4.7 — `WPNAV_RFND_USE`, как и все `WPNAV_*`) — дальномер; иначе база, если `TERRAIN_ENABLE = 1`**. Фолбэка с дальномера на базу нет: нездоровый дальномер при `WP_RFND_USE = 1` означает «данных нет». Высота по дальномеру — `дистанция × cos(наклона)` (`AP_SurfaceDistance`, наклон ограничен 45°), затем фильтр `RNGFND_FILT` (0.5 Гц) и сглаживание `SURFTRAK_TC` (1 с). Copter не смотрит вперёд: цель меняется с землёй под аппаратом, климб ограничен `WP_SPD_UP` (2.5 м/с; до 4.7 — `WPNAV_SPEED_UP`, 250 см/с), спуск — `WP_SPD_DN` (1.5 м/с; до 4.7 — `WPNAV_SPEED_DN`, 150 см/с). Когда ошибка по высоте больше половины `WP_TER_MARGIN` (10 м), горизонтальная скорость линейно падает до 1 % (`AC_PosControl::terrain_scaler_D_m`, в 4.6 — `pos_offset_z_scaler`). Правило: на склоне `s` при скорости `V` нужен климб `V·s`; всё сверх `WP_SPD_UP` — потеря высоты, пока TER_MARGIN не затормозит.

В Loiter, AltHold, PosHold с дальномером работает surface tracking: `SURFTRAK_MODE` 1 — земля (по умолчанию), 0 — выключено, 2 — потолок. Цель — `CTUN.DSAlt`, измерение — `CTUN.SAlt`. Выше `RNGFND1_MAX` (метры; до 4.7 — `RNGFND1_MAX_CM`, сантиметры) датчик становится «OutOfRangeHigh», и трекинг молча отпускает цель в баро-высоту. Аплет `copter_terrain_brake.lua` (`TERR_BRK_ENABLE`, `TERR_BRK_ALT`, `TERR_BRK_HDIST`) переводит Loiter в BRAKE, если высота над базой упала ниже порога.

### RTL и возврат через гору
`RTL_ALT_TYPE = 0` (по умолчанию): `RTL_ALT_M` (до 4.7 — `RTL_ALT` в сантиметрах) — над домом, высота возврата `max(текущая, RTL_ALT_M)` с конусом `RTL_CONE_SLOPE`; гребень выше этого между аппаратом и домом — столкновение. `RTL_ALT_TYPE = 1`: `RTL_ALT_M` — над рельефом, источник как в AUTO. Pre-arm при типе 1: без источника — «RTL_ALT_TYPE is above-terrain but no terrain data», с дальномером — «RTL_ALT_TYPE is above-terrain but RTL_ALT_M above RNGFND_MAX», то есть нужно `RTL_ALT_M ≤ RNGFND1_MAX`. Документация называет тип 1 «not recommended»: если данных нет в момент RTL, полётник пишет «RTL: no terrain data, using alt-above-home» (с дальномером — «RTL: rangefinder unhealthy, using alt-above-home») и идёт на `RTL_ALT_M` над домом — снова через гребень. Компромисс для холмов: тип 0 и `RTL_ALT_M` выше самой высокой точки на пути домой плюс запас, либо rally-точки за гребнем.

### Terrain failsafe
Общая логика failsafe — в ap-safety-fs; у рельефа свой, с двумя триггерами (`ArduCopter/events.cpp`, `mode_auto.cpp`). Первый — таймаут: режим требует рельеф (AUTO, Guided, RTL) и `update_wpnav()` не получает высоту дольше `FS_TERRAIN_TIMEOUT_MS` = 5000 мс (документация пишет 2 с; в коде 4.6.3 и 4.7 — 5 с). Второй — мгновенный: очередная команда миссии с frame Terrain не может задать цель (`wp_start()` вернул false). Итог одинаков: «Failsafe: Terrain data missing», `ERR Subsys 23 ECode 1`, RTL (`MODE.Rsn = 11`), на земле — дизарм; RTL, потерявший рельеф, перезапускается через `restart_without_terrain()` и идёт на `RTL_ALT_M` над домом. Действие не настраивается, битов в `FS_OPTIONS` нет.

### Опасности, которых нет в параметрах
- **Деревья и здания.** База — DSM: кроны и крыши входят в неё частично, сетка 100 м сглаживает всё меньше 50 м. Лес 25 м + ошибка 10 м = 35 м из запаса. Документация: по SRTM — не ниже 60 м.
- **Дыры в данных.** В исходном SRTM есть пустоты (voids) на крутых склонах и воде; серверные тайлы заполнены, но подозрительно ровный участок посреди гор в профиле — повод не верить.
- **Дальномер над водой и травой.** Лидар над водой теряет отражение → `NoData` → при `WP_RFND_USE = 1` terrain failsafe через 5 с (или сразу на смене точки); над высокой травой «земля» поднимается на высоту травы. Радар 60 ГГц над водой работает.
- **Тайлы не загружены.** В поле без интернета pre-arm не пройдёт, а если точки миссии за краем загруженного — failsafe в воздухе.
- **Наклон.** При 29° тангажа дальномер видит 45.5 м там, где земля в 39.9 м; поправка есть, но `RNGFND1_MAX` нужен с запасом `H / cos θ`.

### Plane и PX4
ArduPlane: `TERRAIN_FOLLOW` — битовая маска (по умолчанию 0 — выключено; бит 0, значение 1 — все режимы; биты 1–11 — FBWB, Cruise, Auto, RTL, Avoid_ADSB, Guided, Loiter, Circle, QRTL, QLand, QLoiter; с 4.7 бит 12 — AUTOLAND), где высота считается над рельефом; точки миссии по-прежнему задаются своим frame; `TERRAIN_LOOKAHD` (2000 м) — самолёт смотрит вперёд по курсу и начинает набор до холма, потому что его климб ограничен тяговооружённостью (aero-wing, ap-plane-tuning). У Copter параметра `TERRAIN_FOLLOW` нет ни в 4.6, ни в 4.7 — только frame точек, `SURFTRAK_MODE` и `RTL_ALT_TYPE`.

PX4 1.17: базы рельефа на борту нет, следование только по дальномеру в Position/Altitude: `MPC_ALT_MODE` 0 — высота по EKF, 1 — Terrain following (по оценке расстояния до земли), 2 — Terrain hold (по умолчанию, как и в 1.15: над землёй, пока горизонтальная скорость меньше `MPC_HOLD_MAX_XY`, 0.8 м/с). Датчик вне диапазона — PX4 молча переходит на высоту по EKF (проверено на 1.15). Миссии над рельефом строит QGroundControl из своей карты; сам PX4 рельеф в миссии не знает.

### Что было иначе в 4.6
До 4.7 те же параметры назывались иначе: `WPNAV_RFND_USE`, `WPNAV_SPEED`, `WPNAV_SPEED_UP`, `WPNAV_SPEED_DN` (см/с), `WPNAV_TER_MARGIN` → `WP_RFND_USE`, `WP_SPD`, `WP_SPD_UP`, `WP_SPD_DN` (м/с), `WP_TER_MARGIN`; `RNGFND1_MIN_CM/MAX_CM` (см) → `RNGFND1_MIN/MAX` (м); `RNGFND1_GNDCLEAR` (см) → `RNGFND1_GNDCLR` (м); `RTL_ALT` (см) → `RTL_ALT_M` (м). Только в 4.7: `TERRAIN_OPTIONS` бит 2 и pre-arm на старые DAT; по release notes 4.7.0-beta6 (PR 32943) terrain failsafe срабатывает и тогда, когда не удалось получить высоту рельефа точки миссии: срыв `wp_start()` вызывал его и в 4.6.3, в 4.7.2 в `mode_auto.cpp` добавлены проверки на получение самой точки (10 вызовов `failsafe_terrain_on_event()` против 8). Выбор источника и 5-секундный таймаут те же. Лабораторная ниже снята на 4.6.3: числа в выводах не зависят от имён параметров.

### Место в системе

- **Получает:** высоту от баро, GPS и дальномера (`est-alt-sources`); frame каждой точки миссии (`ap-missions`); тайлы рельефа от GCS по телеметрии.
- **Отдаёт:** цель по высоте над землёй — контроллеру позиции в AUTO и RTL; terrain failsafe — общей схеме отказов (`ap-safety-fs`); запас высоты над деревьями и строениями — в планирование миссии (`ap-missions`).
- **Если ошибиться здесь:** `RTL_ALT_TYPE = 0` и гребень выше `RTL_ALT_M` между аппаратом и домом → при RTL по любому failsafe — столкновение со склоном (`ap-safety-fs`). Лидар над водой при `WP_RFND_USE = 1` → данных нет, через 5 с terrain failsafe и RTL; в логе `ERR` Subsys 23 (`ap-logs`). Тайлы не загружены до выезда → terrain-миссия не армится.

## practice
SITL из тега Copter-4.6.3 (сборка — модуль ap-sitl), ArduCopter запущен напрямую: `arducopter -S -I 2 --model + --speedup 8 --defaults copter.parm -w --home -35.238,149.150,588,90`. Дом — западное подножие горы Маджура (Канберра), 588 м по SRTM; вершина 876 м в 2.9 км на восток; восточная долина 625 м в 4.5 км. Миссия: `NAV_TAKEOFF` 40 м (frame 3), три `NAV_WAYPOINT` во frame 10 на 40 м — склон (1.4 км), вершина, долина — и `NAV_RETURN_TO_LAUNCH`.

Сервер terrain.ardupilot.org из контейнера недоступен (прокси отвечает 403), поэтому `TERRAIN_DATA` отдавал мой скрипт по алгоритму `install_terrain_handlers_context()` из `Tools/autotest/vehicle_test_suite.py` из тайлов SRTM3, лежащих в репозитории ArduPilot (`Tools/autotest/tilecache/srtm/S36E149.hgt.zip`, читает `MAVProxy...mp_elevation.ElevationModel(cachedir, offline=True)`). С интернетом то же делает MAVProxy: `module load terrain`, затем `terrain status` и `terrain check <lat> <lon>`.

### Шаг 1. Без данных — не армится
`TERRAIN_ENABLE = 1`, `RNGFND1_TYPE = 0`, миссия загружена, GCS на `TERRAIN_REQUEST` не отвечает:

```text
  [  42.3 s] PreArm: waiting for terrain data
  TERRAIN_REPORT: spacing=0 pending=336 loaded=0 terrain_height=0.0 current_height=588.1
== now serving terrain tiles (SRTM3 from Tools/autotest/tilecache/srtm)
  TERRAIN_REPORT: spacing=100 pending=0 loaded=392 terrain_height=587.0 current_height=1.1  (served 392 TERRAIN_DATA)
  ARM result: 0
```

336 блоков ждут дома и точек миссии; после 392 пакетов `TERRAIN_DATA` `pending = 0`; `terrain_height` 587.0 против 588 м дома по GPS — `TERR.ROfs = 1.08` м, это `TERRAIN_OFS_MAX` в работе. Запиши число блоков и время загрузки для своей миссии.

### Шаг 2. Миссия по базе рельефа
`RTL_ALT_TYPE = 0`, `RTL_ALT_M = 15` (в прогоне на 4.6.3 — `RTL_ALT = 1500`). Телеметрия раз в 40 с (`AGL_db` — `current_height` из `TERRAIN_REPORT`, `AGL_srtm` — `GLOBAL_POSITION_INT.alt` минус интерполяция сырого тайла в Python):

```text
  t= 419.8 AUTO lon=149.16316 AMSL= 654.3 relH=  66.3 terrDB= 614.5 AGL_db= 39.8 AGL_srtm= 39.8
  t= 541.3 AUTO lon=149.17653 AMSL= 773.9 relH= 185.9 terrDB= 738.4 AGL_db= 35.5 AGL_srtm= 35.0
  t= 581.5 AUTO lon=149.18001 AMSL= 865.8 relH= 277.8 terrDB= 833.0 AGL_db= 32.9 AGL_srtm= 28.8
  t= 662.3 AUTO lon=149.18605 AMSL= 831.8 relH= 243.7 terrDB= 783.8 AGL_db= 48.3 AGL_srtm= 46.8
  [ 837.0 s] Mission: 5 RTL
  t= 903.5 AUTO lon=149.19320 AMSL= 666.6 relH=  78.5 terrDB= 643.4 AGL_db= 23.2 AGL_srtm= 24.2
  [ 933.0 s] EKF3 lane switch 1
  t= 943.8 AUTO lon=149.18997 AMSL= 666.6 relH=  78.5 terrDB= 666.6 AGL_db=  0.0 AGL_srtm=  1.5
```

На пологом участке (0–1.7 км, уклон 3 %) истинная высота 40.5 м (39.0–41.6). На подъёме к вершине (2.5–2.85 км, в среднем 35 %, местами 45 %) при 10 м/с земля росла бы на 3.5 м/с, `WP_SPD_UP` даёт 2.5: аппарат отстаёт, `WP_TER_MARGIN` сбрасывает путевую скорость до 6.4 м/с, минимум — 23.5 м над сырым SRTM (`CTUN.TAlt` в этот момент 33.6: сетка 100 м сглаживает склон на 10 м). На спуске 40 % ограничивает `WP_SPD_DN` 1.5 м/с — до 52 м вместо 40, скорость падает до 4.7 м/с. RTL из долины: текущая 78.5 м над домом больше `RTL_ALT_M`, цель 666.6 м AMSL, восточный склон на 3.63 км выше — «EKF3 lane switch» в 933 с это удар о землю в симуляторе. На реальном аппарате — авария.

{{diagram:chart-terrain-profile|Профиль из лога: AUTO держит 40 м над рельефом, но RTL с RTL_ALT_TYPE 0 из долины идёт на 666.6 м AMSL и упирается в склон на 3.63 км; RTL_ALT_TYPE 1 с дальномером возвращается через вершину.}}

### Шаг 3. Та же миссия с дальномером
`RNGFND1_TYPE = 100` (SITL), `RNGFND1_MAX = 60`, `RNGFND1_MIN = 0.1`, `WP_RFND_USE = 1`, `RTL_ALT_TYPE = 1`, `RTL_ALT_M = 40` (в прогоне на 4.6.3 — `RNGFND1_MAX_CM = 6000`, `RNGFND1_MIN_CM = 10`, `WPNAV_RFND_USE = 1`, `RTL_ALT = 4000`). Pre-arm «waiting for terrain data» не появился — источник дальномер, база не обязательна (`AP_Arming_Copter::terrain_database_required`). Лог на 395 с: `RFND.Dist = 45.51`, `ATT.Pitch = −28.9°`, `CTUN.SAlt = 39.85` — 45.51·cos 28.9° = 39.8, поправка на наклон работает. Минимум на подъёме — 19.9 м истинных, на 3.6 м хуже базы: добавилось запаздывание `RNGFND_FILT` и `SURFTRAK_TC`. `SAlt` при этом показывал 30.9: дальномер SITL меряет до той же сетки 100 м, что лежит в базе (`SIM_Aircraft::ground_height_difference`), поэтому «видит» тот же сглаженный склон. Настоящий лидар показал бы настоящие 20 м — и это единственное, чем он здесь лучше. RTL типа 1: 27–49 м над рельефом через вершину, посадка дома, «SIM Hit ground at 0.50 m/s».

{{diagram:chart-terrain-agl|Истинная высота над землёй вдоль маршрута: на пологом участке база держит 39–41.6 м, дальномер 37.5–41 м; на подъёме 35 % при 10 м/с ограничение WP_SPD_UP роняет высоту до 24 м (база) и 20.5 м (дальномер), на спуске 40 % WP_SPD_DN поднимает до 51 м. Лекарство — скорость, а не датчик.}}

Скрипт `plot_agl.py` читает `.BIN` через `pymavlink.DFReader` (`SIM.Alt/Lat/Lng`, `CTUN.TAlt/SAlt/DAlt`, `TERR.*`, `RFND.Dist/Stat`), считает истинную AGL как `SIM.Alt − SRTM(lat, lon)` и рисует `matplotlib`. На железе вместо `SIM` — `GPS.Alt` и тот же тайл.

### Шаг 4. Потеря дальномера
`RNGFND1_MAX = 25` (на 4.6.3 — `RNGFND1_MAX_CM = 2500`), остальное как в шаге 3, `RTL_ALT_TYPE = 0`:

```text
t=287.8 RFND.Stat 4 -> 3  Dist=25.0  CTUN.Alt=23.8      # OutOfRangeHigh на наборе 40 м
t=296.0 MSG Mission: 2 WP                                 # первая точка frame Terrain
t=296.0 MSG Failsafe: Terrain data missing
t=296.0 ERR Subsys 23 ECode 1
t=296.0 MODE Mode 6 Rsn 11                                # RTL, причина TERRAIN_FAILSAFE
```

База была загружена (`loaded = 392`), но источник — дальномер, фолбэка нет. Пока шёл `NAV_TAKEOFF` (frame 3), рельеф не требовался; в 296.0 с миссия перешла к первой terrain-точке, `wp_start()` не получил высоту — failsafe сработал в ту же секунду, без 5-секундного таймаута. Аппарат ушёл в RTL и сел. Для миссий выше дальности датчика — `WP_RFND_USE = 0`.

### Переход на реальное железо
1. **Тайлы дома.** Миссия в Mission Planner с интернетом, полётник подключён (`TERRAIN_ENABLE = 1`), в `TERRAIN_REPORT` (MAVLink Inspector) `pending = 0`, `loaded = N`; профиль высот миссии (правый клик на карте Flight Plan → Map Tool → Elevation Graph) и MAVProxy `terrain check <lat> <lon>` для крайних точек. Альтернатива — тайлы с terrain.ardupilot.org в `APM/TERRAIN` на SD. Приёмка: `TERRAIN_REPORT.pending = 0` в поле без интернета.
2. **Дальномер на стенде, пропы сняты.** `RNGFND1_TYPE` по модели, `RNGFND1_ORIENT = 25`, `RNGFND1_MIN/MAX` по паспорту (TFmini-S: 0.1/12 м), `RNGFND1_GNDCLR` — высота датчика на стоянке в метрах (подключение — est-alt-sources); `RNGFND1_MIN` меньше неё, иначе на земле датчик «нездоров» и terrain failsafe дизармит сразу после арма. Аппарат в руках над полом, травой, тёмной плиткой и ведром воды: `RFND.Dist` против рулетки на 0.5 / 1 / 2 / 4 м, статус 4 (Good) везде, кроме воды; наклон 30° — `CTUN.SAlt` на месте, `RFND.Dist` × 1/cos 30° = 1.15. Приёмка: ошибка ≤ 3 % или 5 см, нет `NoData` над травой.
3. **Первый полёт над рельефом** — с наблюдателем, Loiter на 15–20 м над склоном без деревьев, `SURFTRAK_MODE = 1`, `TERR_BRK_ENABLE = 1` и `TERR_BRK_ALT = 10` (аплет работает по базе рельефа и только дальше `TERR_BRK_HDIST`, 100 м, от дома), `RTL_ALT_TYPE = 0`, `RTL_ALT_M` выше гребня + 30 м, батарея на полный возврат. Медленно (≤ 3 м/с) вверх по склону и вниз, в телеметрии `CTUN.SAlt` и `DSAlt`. Прерывание (AltHold и возврат): `SAlt` расходится с глазомером больше 5 м; статус дальномера не 4 дольше 2 с; любое `Failsafe`; на глаз меньше 10 м над землёй. Только потом — AUTO с terrain-точками на 60 м, `WP_SPD` 5 м/с, уклоны до 15 %.

Самопроверка: лабораторная выполнена, когда (SITL): есть три лога — база, дальномер, потеря дальномера; на графике истинной AGL назван минимум на подъёме, он близок к прогону модуля (около 24 м по базе, около 20 м с дальномером), а объяснение сходится с шагом 2: склон 35 % при 10 м/с требует набора 3.5 м/с, `WP_SPD_UP` даёт 2.5; в выводе есть pre-arm «waiting for terrain data», и он исчезает после загрузки (`pending = 0`); удар о склон при `RTL_ALT_TYPE = 0` воспроизведён и подобран `RTL_ALT_M` выше гребня, с которым RTL проходит; terrain failsafe найден в логе по `ERR Subsys 23` и `MODE Rsn 11`. (Железо): `TERRAIN_REPORT.pending = 0` в поле; стендовая таблица дальномера с ошибкой ≤ 3 %; лог Loiter над склоном с `SAlt` в ±2 м от `DSAlt`, ни один критерий прерывания не сработал.

## diagnostics
- **Симптом:** `PreArm: waiting for terrain data`, `TERRAIN_REPORT.pending` не уменьшается
  - Возможная причина: GCS не поддерживает `TERRAIN_DATA` или без интернета; `TERRAIN_SPACING` не тот, что у сервера.
  - Что сделать: Mission Planner/QGC/MAVProxy (`module load terrain`) с интернетом или тайлы на SD в `APM/TERRAIN`; `TERRAIN_SPACING = 100`.
- **Симптом:** `PreArm: terrain data expired, possible errors` после обновления на 4.7
  - Возможная причина: DAT-файлы от старого сервера (до 24.02.2026).
  - Что сделать: удалить `APM/TERRAIN`, скачать заново.
- **Симптом:** «Failsafe: Terrain data missing» и RTL в AUTO, хотя тайлы загружены
  - Возможная причина: источник — дальномер (`WP_RFND_USE = 1`), вышел за `RNGFND1_MAX` или потерял отражение (вода).
  - Что видно в логе: `RFND.Stat` 3 (OutOfRangeHigh) или 1 (NoData) за 5 с до `ERR Subsys 23 ECode 1` либо в момент «Mission: N WP»; `MODE.Rsn = 11`.
  - Что сделать: `WP_RFND_USE = 0` для высоты выше дальности датчика; радар над водой.
- **Симптом:** дизарм через секунды после арма в AUTO с «Failsafe: Terrain data missing»
  - Возможная причина: на земле дальномер читает меньше `RNGFND1_MIN` (статус 2, OutOfRangeLow) и считается нездоровым.
  - Что сделать: `RNGFND1_MIN` ниже высоты установки датчика (документация: 5 см).
- **Симптом:** в Loiter над склоном высота над землёй падает, пилот не трогал газ
  - Возможная причина: дальномер вышел из диапазона, surface tracking отпустил цель в баро-высоту; или `SURFTRAK_MODE = 0`.
  - Что сделать: ниже `RNGFND1_MAX` с запасом `H / cos θ`; `TERR_BRK_ENABLE = 1`.
- **Симптом:** на подъёме AGL ниже цели на 10–20 м, аппарат замедляется
  - Возможная причина: уклон × скорость больше `WP_SPD_UP`; `WP_TER_MARGIN` тормозит.
  - Что сделать: `WP_SPD` вниз или `WP_SPD_UP` вверх; цель выше на крутых участках.
- **Симптом:** RTL летит в гребень между аппаратом и домом
  - Возможная причина: `RTL_ALT_TYPE = 0` и `RTL_ALT_M` ниже гребня над домом; или тип 1, но «RTL: no terrain data, using alt-above-home».
  - Что сделать: `RTL_ALT_M` ≥ превышение гребня + 30 м; rally-точки за гребнем.
- **Симптом:** над лесом дальномер показывает 20 м, база — 45 м
  - Возможная причина: это не ошибка: дальномер видит кроны, SRTM — усреднённую поверхность.
  - Последствия: миссия по базе пройдёт на 20 м над кронами при цели 45.
  - Что сделать: цель по базе ≥ 60 м над лесом или дальномер как источник.

## checklist
- Три frame высоты; `h_AGL` из базы и из дальномера
- Источник рельефа при `WP_RFND_USE = 1`; фолбэка на базу нет
- Тайлы загружены до вылета, `pending = 0`
- `RTL_ALT_TYPE` и `RTL_ALT_M` под самый высокий гребень на пути домой
- Лимиты: SRTM ≥ 60 м, деревья, вода, `WP_SPD_UP` против уклона
- Terrain failsafe в логе: `ERR 23`, `MODE.Rsn 11`, `RFND.Stat`

## references
- ArduPilot Copter — Terrain Following (параметры, failsafe, SRTM, загрузка тайлов) | https://ardupilot.org/copter/docs/terrain-following.html | primary | A
- ArduPilot source — AP_Terrain parameters and pre-arm checks (`libraries/AP_Terrain/AP_Terrain.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_Terrain/AP_Terrain.cpp | primary | A
- ArduPilot source — terrain source selection and margin (`libraries/AC_WPNav/AC_WPNav.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_WPNav/AC_WPNav.cpp | primary | A
- ArduPilot source — terrain failsafe (`ArduCopter/events.cpp`, `config.h` FS_TERRAIN_TIMEOUT_MS) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/events.cpp | primary | A
- ArduPilot source — RTL altitude type (`ArduCopter/mode_rtl.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_rtl.cpp | primary | A
- ArduPilot source — Copter 4.7 release notes (WPNAV→WP, TERRAIN_OPTIONS, terrain failsafe) | https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/ReleaseNotes.txt | primary | A
- ArduPilot source — autotest terrain handler and SRTM3 tiles (`Tools/autotest/vehicle_test_suite.py`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/Tools/autotest/vehicle_test_suite.py | primary | B
- PX4 — Terrain Following/Holding (MPC_ALT_MODE) | https://docs.px4.io/v1.17/en/flying/terrain_following_holding.html | primary | A
- PX4 — Parameter Reference (MPC_ALT_MODE, MPC_HOLD_MAX_XY) | https://docs.px4.io/v1.17/en/advanced_config/parameter_reference.html | primary | A
- ArduPilot Terrain Generator — источник тайлов (JAXA ALOS, SRTM1 30 м / SRTM3 100 м, 0–84° широты) | https://terrain.ardupilot.org/ | primary | B
- ArduPilot Lua applet copter_terrain_brake (`libraries/AP_Scripting/applets/copter_terrain_brake.md`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_Scripting/applets/copter_terrain_brake.md | primary | B
