---
id: per-vision-pipeline
title: "Машинное зрение на борту от и до: калибровка → детекция → трекинг → геопривязка → команда"
level: L3
readingTime: 55 мин
firmware: ArduCopter 4.7 (сверено с 4.7.2; лабораторная снята на 4.6.3) · PX4 1.17 (сверено с v1.17.0)
status: published
tags:
  - машинное зрение
  - конвейер
  - задержка
  - геопривязка
  - GUIDED
  - интерлоки
related:
  - per-camera
  - per-geometry
  - per-cv
  - per-tracking
  - per-edge-ml
  - per-landing
next:
  - per-tracking
---

## summary
Модули перцепции разбирают звенья по одному: кадр (per-camera), геометрию (per-geometry), детектор (per-cv), контур слежения (per-tracking), профилирование (per-edge-ml). Здесь они собраны в конвейер «свет на сенсоре → команда автопилоту», где у каждой стадии есть бюджет задержки и описанный отказ. После модуля ты умеешь измерить glass-to-command по стадиям, оценить детектор и трекер по срезам, перевести детекцию в точку на земле с честной меткой времени и замкнуть это на автопилот так, чтобы потеря цели, зависший процесс или ложная цель заканчивались висением, а не улётом. Лабораторная: конвейер на синтетическом полёте (40 с, 1200 кадров) с логом задержек и координат цели, затем replay в ArduCopter SITL с GUIDED-слежением, режимом FOLLOW и проверкой таймаутов и геозоны.

## theory
### Конвейер и бюджет
Метка времени экспозиции идёт с кадром через все стадии: по ней выбирается ориентация и считается возраст данных.

| Стадия | Что делает | Типичная задержка | Отказ → что должна увидеть следующая стадия |
|---|---|---|---|
| Сенсор | экспозиция + readout | 10–30 мс | пересвет, смаз → детекций нет |
| Захват | V4L2/CSI → память | 1–10 мс; USB MJPEG +10–20 | кадр не пришёл → возраст растёт, watchdog |
| Undistort | точка или весь кадр | ≈ 0.02 / 1–5 мс | неверная калибровка → систематическая ошибка на краях |
| Детектор | bbox + уверенность | HSV 1–5 мс; YOLO-n на CPU 25–300 мс (x86 и 320 px в лабораторной — Pi 5 и 640 px у Ultralytics), с ускорителем в разы меньше (per-edge-ml) | пропуск или ложная цель |
| Трекер | ассоциация, ID, прогноз | < 1 мс | переключение ID → цель «прыгает» |
| Геопривязка | пиксель → луч → земля | < 1 мс | луч выше горизонта → `None`, не точка |
| Команда | скорость/цель, интерлоки | < 1 мс | NaN, выброс → отбросить |
| Линк + FC | MAVLink, цикл автопилота | 3–20 мс | обрыв → таймаут автопилота |

Сумма — glass-to-command `T_d`. Она, а не FPS, ограничивает усиление контура: `K_p,max ≈ π/(2·T_d)` без учёта динамики аппарата (вывод — per-tracking). Бюджет распределяют от задачи (per-edge-ml).

{{diagram:vision-pipeline-budget|Бюджет из лабораторной: на 2 ядрах x86 весь конвейер с HSV-детектором занимает 3.3 мс (p95), 36 мс glass-to-command набирают сенсор и линк; с YOLO11n на CPU — 65 мс, и главной статьёй становится инференс.}}

### Захват: V4L2, CSI, GStreamer
Интерфейсы — per-camera. Для конвейера важны три вещи. **Свежий кадр, а не очередь:** `appsink drop=true max-buffers=1` в GStreamer или `CAP_PROP_BUFFERSIZE = 1` в OpenCV, иначе обрабатывается кадр секундной давности. **Сырой формат:** `v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink drop=true max-buffers=1`; на Pi с CSI источник — `libcamerasrc`, на Jetson — `nvarguscamerasrc` (comp-jetson-nano). **Метка времени:** метка буфера V4L2 обычно идёт по `CLOCK_MONOTONIC` (флаг `V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC`) и у большинства драйверов ставится по приёму последнего пикселя кадра (`TSTAMP_SRC_EOF`); немногие ставят начало экспозиции (`TSTAMP_SRC_SOE`). Середина экспозиции не бывает ни там, ни там — проверь флаги буфера своей камеры. Разница почти постоянна, её измеряют один раз и вычитают. `time.time()` после `cap.read()` — метка обработки, а не кадра.

### Undistort: кадр или точка
Полный `cv2.remap` на 640×480 занял в лабораторной 0.9 мс (p50), на одноплатнике будет в разы больше — измерь; `cv2.undistortPoints` для одной точки — около 0.02 мс. Детектору bbox искажение обычно не мешает, геометрии нужна только исправленная точка; полный undistort оправдан для линий и маркеров у края кадра. Побочный эффект (в лабораторной — числом): remap растягивает объекты у краёв, и ворота по размеру пропускают чужое.

### Детектор под задачу
| Задача | Детектор | Что получаешь |
|---|---|---|
| Своя метка, посадка | ArUco/AprilTag (per-landing) | поза и ID, ложных почти нет; нужен контраст и ≥ 20 px на маркер |
| Яркий объект известного цвета и размера | HSV + контуры + ворота по площади из AGL | < 1 мс; слепнет в тени и на смазе, зато молчит, а не врёт |
| Люди, машины, произвольные классы | YOLO-n, дообученная на своих кадрах (per-cv) | устойчива к свету и смазу; 25–300 мс на CPU, выдаёт уверенные ложные цели |

Цель диаметром `D` на высоте `h` занимает `s = D·f/h` пикселей; ниже 8–10 px нейросеть работает ненадёжно, а ворота по площади теряют смысл. Выбирают по срезам (свет, смаз, перекрытие, фон), а не по среднему mAP: пропуск стоит секунду висения, ложная цель — полёт не туда.

### Трекер и постоянство ID
- **SORT:** фильтр Калмана с постоянной скоростью на каждый объект + венгерский алгоритм по IoU; сотни Гц, но ID теряется при пропусках детектора.
- **ByteTrack:** вторая ассоциация для детекций с низкой уверенностью — цель в тени остаётся в треке, а фон отсеивается.
- **KCF, CSRT** (OpenCV): трекеры одного объекта по шаблону между запусками медленного детектора. KCF быстрый, но не следит за масштабом; CSRT точнее и медленнее. Оба молча «уплывают» на фон — детектор перепроверяет их каждые 5–10 кадров.

Автопилоту нужен один объект с ID, переживающим пропуски. Четыре правила: подтверждение трека (в лабораторной 3 кадра), жизнь без детекций `max_age` (15 кадров = 0.5 с), ворота ассоциации (30 px), захват цели — держать выбранный ID, а после потери брать новый трек только в радиусе от последней позиции (лучше в метрах на земле: пиксели зависят от высоты и крена).

### Геопривязка и время
Цепочка «пиксель → луч → `R_bc` → `R_nb(roll, pitch, yaw)` → пересечение с землёй на `h`» — per-geometry (`camgeo.pixel_to_ground`). Здесь — откуда взять ориентацию и высоту **на момент экспозиции**:
- `ATTITUDE` (50 Гц через `MAV_CMD_SET_MESSAGE_INTERVAL`) и `GLOBAL_POSITION_INT` (10 Гц) несут `time_boot_ms` — часы автопилота. Кадр несёт часы companion.
- Смещение часов даёт `TIMESYNC` (#111): companion шлёт `ts1` = свои наносекунды, `tc1 = 0`; автопилот возвращает тот же `ts1` и свой `tc1`. `offset = tc1 − (ts1 + RTT/2)`, берут медиану по 10+ обменам. В SITL по TCP: RTT 4.8 мс, разброс смещения 2.5 мс.
- Ориентацию интерполируют между соседними `ATTITUDE` на метку кадра; «последнее пришедшее» при 50 Гц — до 20 мс возраста плюс линк.
- Ошибка от сдвига времени у надира: `δ ≈ h·tan(ω·Δt)`. 15 м, 27 °/с, 100 мс — 0.72 м при цене пикселя 3.75 см.
- `GLOBAL_POSITION_INT.relative_alt` — высота над точкой взлёта, а не над землёй под целью. На склоне нужен дальномер (`DISTANCE_SENSOR`, с поправкой на наклон) или карта высот.

### Что слать автопилоту
| Интерфейс | Когда | ArduPilot 4.7 | PX4 1.17 |
|---|---|---|---|
| `LANDING_TARGET` | точная посадка, Precision Loiter | `PLND_ENABLED = 1`, `PLND_TYPE = 1`; углы `angle_x/angle_y` либо `position_valid = 1`, frame `MAV_FRAME_BODY_FRD`, `distance > 0`; `PLND_LAG` (0.02–0.25 с) = твоя glass-to-command | с `position_valid = 1` — только `MAV_FRAME_LOCAL_NED` и `x, y, z`; с `position_valid = 0` углы идут как `irlock_report`; `PLD_BTOUT`, `PLD_SRCH_ALT` |
| `SET_POSITION_TARGET_LOCAL_NED`, скорости | слежение своим регулятором | GUIDED, `type_mask = 3527`; без обновлений `GUID_TIMEOUT` (3 с) → скорость 0 | Offboard, поток ≥ 2 Гц; `COM_OF_LOSS_T`, действие `COM_OBL_RC_ACT` |
| Координаты цели | слежение регулятором автопилота | режим FOLLOW: `GLOBAL_POSITION_INT` или `FOLLOW_TARGET` от `FOLL_SYSID`; `FOLL_POS_P`, `FOLL_DIST_MAX`; таймаут — `FOLL_TIMEOUT`, 3 с (параметр появился в 4.7, в 4.6 те же 3 с зашиты в коде) | Follow Me: `FOLLOW_TARGET`; `FLW_TGT_HT`, `FLW_TGT_DST` |

`LANDING_TARGET.time_usec` — момент экспозиции по часам companion: ArduPilot переводит его в свои часы (`correct_offboard_timestamp_usec_to_ms`), PX4 — через свой timesync. Подробности `PLND_*` и фаз посадки — per-landing.

### Интерлоки в три слоя
1. **Companion:** лимит скорости `v_max`; watchdog — нет подтверждённой цели 0.5 с → явная нулевая скорость; таймаут 3 с → запрос LOITER и защёлка: возврат к слежению только по команде оператора; отброс NaN и скачков.
2. **Автопилот:** `GUID_TIMEOUT`; геозона `FENCE_ENABLE`, `FENCE_TYPE`, `FENCE_RADIUS`, `FENCE_ALT_MAX`, `FENCE_ACTION`; `AVOID_ENABLE` (по умолчанию 3) останавливает GUIDED-скорость за `AVOID_MARGIN` (2 м) до границы. В PX4 — `GF_ACTION`, `GF_MAX_HOR_DIST`, `MPC_XY_VEL_MAX`.
3. **Пилот:** переключатель режима обрывает контур; companion после смены режима перестаёт слать команды.

Два факта из лабораторной. ArduCopter **не ограничивает** GUIDED-скорость параметром `WP_SPD` (до 4.7 — `WPNAV_SPEED`, см/с): в прогоне на 4.6.3 при `WPNAV_SPEED = 300` (3 м/с) команда 6 м/с исполняется как 6.1 м/с, в исходнике 4.7.2 путь скоростной цели тот же — лимит обязан стоять на companion. И LOITER держит высоту только при газе в середине: без пилота с пультом таймаут должен вести в BRAKE или оставаться нулевой скоростью в GUIDED.

### Место в системе

- **Получает:** кадр с меткой экспозиции (`per-camera`); калибровку и геометрию (`per-geometry`); детектор и трекер (`per-cv`); `ATTITUDE` и `TIMESYNC` от автопилота (`mav-services`).
- **Отдаёт:** `LANDING_TARGET` точной посадке (`per-landing`); скоростные уставки GUIDED или координаты цели для FOLLOW (`per-tracking`); измеренную glass-to-command — в `PLND_LAG` и предел K_p.
- **Если ошибиться здесь:** метка `time.time()` после чтения кадра вместо метки буфера → ориентация берётся не на тот момент, точка на земле «плавает» при манёврах (`per-geometry`). Цель потеряна, а watchdog нет → companion шлёт последнюю скорость, `GUID_TIMEOUT` не срабатывает, аппарат летит до геозоны (`ap-safety-fs`).

## practice
Код — `examples/vision-pipeline/` (`gen_video.py`, `pipeline.py`, `score.py`, `sitl_follow.py`, `make_dataset.py`), геометрия — из `examples/perception/camgeo.py`. Зависимости: `opencv-python`, `numpy`, `pymavlink`; для ветки YOLO — `ultralytics`. Числа — с 2 ядер Xeon 2.1 ГГц, Python 3.13, OpenCV 5.0; SITL — ArduCopter 4.6.3 (сборка — ap-sitl), экземпляр `-I 4`.

### Шаг 1. Данные
`gen_video.py` рисует полёт без датасета: надирная камера 640×480, 30 кадров/с, f = 400 px, дисторсия k1 = −0.10, k2 = 0.02, высота 15 ± 0.5 м, крен ±8° на 0.5 Гц и тангаж ±5° на 0.35 Гц (до 27 °/с). Цель — оранжевый диск R = 0.4 м (Ø 21 px), идёт по кругу 6 м со скоростью 0.6 м/с. Помехи: оранжевый камень R = 0.3 м, тени, провал экспозиции до 0.25 на 20–24 с, смаз на 28–30 с, перекрытие на 33–35 с. Рядом пишутся `telemetry.csv` (`ATTITUDE` 50 Гц, `GLOBAL_POSITION_INT` 10 Гц, каждое со своим `time_boot_ms`) и `truth.csv` для оценки.

```text
$ python3 gen_video.py data
wrote 1200 frames, K: fx=400.0, k1=-0.1, k2=0.02, AGL≈15.0 m, HFOV=77.3°
```

### Шаг 2. Конвейер и задержка по стадиям
`pipeline.py` на каждый кадр: чтение → undistort → HSV-детектор (маска, контуры, ворота по площади 0.8–1.3 от ожидаемого радиуса и по заполнению круга ≥ 0.6) → трекер (Калман + ближайший сосед, захват ID) → геопривязка с интерполяцией телеметрии на метку кадра → команда `v = 0.8·(n, e)`, ограниченная 2 м/с, с состояниями TRACK / HOLD / LOITER. Каждая стадия обёрнута в `time.perf_counter()`, строка на кадр уходит в `targets.csv`.

```text
$ python3 pipeline.py data --undistort frame
1200 frames @ 30 fps, detector=hsv, undistort=full frame, select=lock, att offset +0 ms
stage      p50 ms   p95 ms   max ms
cap          0.25     0.79     4.27
und          0.91     1.31     4.04
det          0.73     1.01     4.94
trk          0.04     0.08     1.19
geo          0.07     0.12     0.93
cmd          0.00     0.00     0.04
total        2.05     3.11     7.22
```

Записывай p95 и max, а не среднее: max 7.2 мс при p50 2.1 — планировщик ОС, на борту хвост длиннее. `cap` здесь — декодирование mp4, а не камера; экспозиция и линк входят в бюджет типичными значениями до стендового замера.

### Шаг 3. Оценка по срезам
`score.py` сравнивает `targets.csv` с `truth.csv`: кадр верный, если цель видна и точка на земле в пределах 1 м. Четыре прогона (`--undistort frame|point`, `--select maxhits`, `--detector yolo`):

| Конфигурация | nominal P / R | тёмный P / R | смаз P / R | перекрытие, ложных кадров | детектор p50, мс |
|---|---|---|---|---|---|
| HSV, undistort кадра | 0.91 / 0.91 | 1.00 / 0.03 | 1.00 / 0.05 | 37 | 0.73 |
| HSV, undistort точки | 1.00 / 0.99 | 1.00 / 0.03 | 1.00 / 0.05 | 3 | 0.83 |
| то же, выбор трека «max hits» | 1.00 / 0.99 | 1.00 / 0.03 | 1.00 / 0.05 | 16 | 0.82 |
| YOLO11n, дообученная | 0.98 / 0.98 | 1.00 / 1.00 | 1.00 / 1.00 | 36 | 25.2 |

```text
$ python3 pipeline.py data --undistort point > /dev/null && python3 score.py data
slice                 TP    FP    FN  precision  recall
nominal              952     0     8       1.00    0.99
dark (gain 0.25)       3     0   117       1.00    0.03
motion blur            3     0    57       1.00    0.05
occluded               0     3     0       0.00    0.00
geo error on TP frames: mean 0.13 m, p95 0.20 m, max 0.43 m
track IDs used on TP frames: [1, 13, 18, 22]  (ID switches = 3)
interlock states: {'HOLD': 210, 'TRACK': 961, 'LOITER': 29}
```

Что читать в таблице. **Undistort кадра уронил nominal до 0.91:** камень должен занимать 201 px² при нижней границе ворот 229 px², но после remap он проходит ворота в 564 кадрах из 1200 (без remap — в 119). После перекрытия на 33-й секунде трекер взял камень в 93 px от последней позиции цели (радиус переприхвата 100 px) и до конца записи выдавал его координаты: 77 ложных кадров и 79 пропусков. Среднее по записи это прячет, срез — нет. **HSV в темноте и на смазе слепнет** (recall 0.03–0.05), но ложных точек не даёт: watchdog переводит контур в HOLD, это безопасный отказ. **«Max hits» вместо захвата** даёт 16 ложных кадров в перекрытии против 3: неподвижный камень копит попадания. **YOLO** проходит тень и смаз, но во время перекрытия 36 кадров (1.2 с) отдаёт координаты, когда цели не видно, и стоит 25 мс. Оговорка: сеть дообучена на 240 кадрах этого же полёта (192/48, 8 эпох, `imgsz 320`, mAP50 0.994) — это замер задержки, а не обобщения; честная оценка требует другого полёта (per-cv). Три смены ID — по одной на каждую потерю дольше `max_age`.

### Шаг 4. Время
Тот же прогон, но ориентация берётся со сдвигом (`--att-offset-ms`), как если бы метка кадра была неверной:

```text
$ for o in 0 50 100; do python3 pipeline.py data --undistort point --att-offset-ms $o > /dev/null; python3 score.py data | grep geo; done
geo error on TP frames: mean 0.13 m, p95 0.20 m, max 0.43 m
geo error on TP frames: mean 0.34 m, p95 0.50 m, max 0.76 m
geo error on TP frames: mean 0.58 m, p95 0.85 m, max 0.99 m
```

{{diagram:chart-vision-timesync|Сдвиг 100 мс между кадром и ATTITUDE даёт 0.58 м средней ошибки и 0.85 м p95 на высоте 15 м — в 4.5 раза больше, чем вся остальная цепочка (0.13 м). Измеренный p95 ложится на оценку h·tan(ω·Δt).}}

Остаток 0.13 м при нулевом сдвиге — пиксель (3.75 см), высота на 10 Гц и линейная интерполяция.

### Шаг 5. Replay в SITL: слежение и таймауты
```text
$ arducopter -w -S --model + -I 4 --speedup 1 --home -35.363261,149.165230,584,353 --defaults copter.parm
$ python3 sitl_follow.py tcp:127.0.0.1:5800 data/targets.csv
heartbeat from sysid 1, firmware: 4.6.3
== 0. TIMESYNC
   RTT median 4.81 ms, FC clock - companion clock = -2213530.2 ms (spread 2.52 ms)
…
== 3. GUIDED velocity follow (replay of targets.csv at 30 fps, commands at 10 Hz)
   t=  0.0s None->TRACK  v_fc=(+0.0,+0.0) m/s  alt=14.6 m  mode=GUIDED
   t= 20.6s TRACK->HOLD  v_fc=(-0.8,+0.2) m/s  alt=14.9 m  mode=GUIDED
   t= 23.2s HOLD->LOITER  v_fc=(-0.0,-0.0) m/s  alt=14.9 m  mode=LOITER
   t= 24.3s target is back, operator re-enables follow:   mode GUIDED
   t= 24.3s LOITER->TRACK  v_fc=(+0.0,-0.0) m/s  alt=14.9 m  mode=GUIDED
   t= 28.7s TRACK->HOLD  v_fc=(-0.7,-0.5) m/s  alt=14.9 m  mode=GUIDED
   t= 30.1s HOLD->TRACK  v_fc=(-0.0,-0.0) m/s  alt=14.9 m  mode=GUIDED
   t= 33.6s TRACK->HOLD  v_fc=(-0.6,-0.5) m/s  alt=14.9 m  mode=GUIDED
   t= 35.1s HOLD->TRACK  v_fc=(-0.0,-0.0) m/s  alt=14.9 m  mode=GUIDED
   sent 289 velocity setpoints; interlock states: TRACK=248, HOLD=41, LOITER=8
   |v| before first HOLD 0.97 m/s, 1.5-2.5 s after 0.03 m/s
== 4. FOLLOW mode: pipeline publishes the target as sysid 200 GLOBAL_POSITION_INT
   horizontal distance to target: start 18.8 m, t=10 s 13.9 m, mean over the last 5 s 1.5 m; |v| max 2.6 m/s, alt 14.9-15.0 m
   target stream stops (dark slice: the pipeline has nothing to publish)
   …
   +3 s: pos=(-4.2,+5.3) m v=(-0.4,-0.1) m/s mode=FOLLOW
   +4 s: pos=(-4.4,+5.3) m v=(-0.0,+0.0) m/s mode=FOLLOW
```

Вывод сокращён (пропуски отмечены «…»). Скрипт выставляет `FENCE_ENABLE = 1`, `FENCE_TYPE = 3`, `FENCE_RADIUS = 60`, `FENCE_ALT_MAX = 30`, `FENCE_ACTION = 1`, `GUID_TIMEOUT = 3`, `FOLL_ENABLE = 1`, `FOLL_SYSID = 200`, `FOLL_POS_P = 0.3`, `FOLL_OFS_Z = -15`, взлетает на 15 м и читает `targets.csv` в реальном времени. Это replay без обратной связи: проверяется путь команды и интерлоки, а не качество слежения. Провал экспозиции (20–24 с): через 0.5 с после последней детекции уходит нулевая скорость (0.97 → 0.03 м/с), через 3 с — LOITER с защёлкой; смаз и перекрытие (по 2 с) укладываются в HOLD. В FOLLOW конвейер публикует координаты цели от имени sysid 200 с частотой 10 Гц: аппарат сокращает 18.8 м до 1.5 м, а когда поток прерывается, через 3 с останавливается сам — это `AP_FOLLOW_TIMEOUT_MS`. «Пилота» в SITL изображает `RC_CHANNELS_OVERRIDE` с газом 1500: без него LOITER после таймаута снижается.

### Шаг 6. Интерлоки автопилота
```text
== 5. speed limit and GUID_TIMEOUT: companion goes silent in GUIDED
   …
   6.0 m/s north commanded, +4 s: pos=(+17.3,+5.3) m v=(+6.1,+0.0) m/s mode=GUIDED
   1.5 m/s north commanded for 3 s: pos=(+30.1,+5.3) m v=(+1.4,-0.0) m/s mode=GUIDED; now silent
   …
   +3 s silence: pos=(+34.5,+5.3) m v=(+1.5,+0.0) m/s mode=GUIDED
   +4 s silence: pos=(+35.3,+5.3) m v=(+0.2,-0.0) m/s mode=GUIDED
   +5 s silence: pos=(+35.4,+5.3) m v=(+0.0,-0.0) m/s mode=GUIDED
== 6. geofence: companion keeps commanding 3 m/s north, FENCE_RADIUS = 60 m
   after 40 s: pos=(+58.0,+0.3) m v=(+0.0,-0.0) m/s mode=GUIDED
   fence shrinks to 30 m while the vehicle is outside it (the same as flying through a fence without avoidance)
   FC: Circle fence breached
   3 s later, still sending 3 m/s north: pos=(+54.4,+0.2) m v=(-2.6,-0.0) m/s mode=RTL
```

Три вывода. `WPNAV_SPEED = 300` (прогон на 4.6.3; в 4.7 — `WP_SPD = 3`) скорость GUIDED не ограничил: 6.1 м/с. Замолчавший companion обходится в `GUID_TIMEOUT` секунд полёта с последней скоростью — в логе 5.3 м при 1.5 м/с (30.1 → 35.4 м), при 6 м/с это 18 м, поэтому свой watchdog на 0.5 с обязателен. Геозона для GUIDED-скорости работает как стена: аппарат остановился на 58.0 м при радиусе 60 (`AVOID_MARGIN` 2 м) и остался в GUIDED; пересечённая граница даёт «Circle fence breached» и RTL, команды companion после этого игнорируются.

### Переход на реальное железо
1. **Калибровка и метка времени.** Шахматная доска, 20+ кадров, RMS репроекции < 1 px (per-geometry); `K` и `dist` — в `pipeline.py`. Задержку камеры измерь светодиодом (per-camera) — это поправка метки кадра.
2. **Стенд, пропеллеры сняты.** Companion и камера на раме, рама на штативе, камера вниз на 1.5 м над полом (рулеткой), на полу печатный оранжевый круг Ø 20 см и линейка. Автопилот от USB, `ATTITUDE` на 50 Гц. Запиши 60 с видео с метками кадров и `telemetry.csv`, прогони `pipeline.py`. Проверки: цель в пяти точках (центр и четыре по 0.5 м) — ошибка ≤ 5 см; раму качают рукой ±10° на 1 Гц — точка остаётся в 8 см, а подбор `--att-offset-ms` с минимальной ошибкой даёт остаточный сдвиг времени (должен быть в ±10 мс); цель накрыта — нулевая команда через 0.5 с, запрос LOITER через 3 с виден в GCS; сдвиг цели на север даёт `vn > 0`, на восток — `ve > 0`. Приёмка: p95 и glass-to-command записаны и укладываются в бюджет, `PLND_LAG` или `K_p` выставлены по измеренной задержке, знаки верны.
3. **Привязь или низкое висение — первый шаг с пропеллерами.** Открытая площадка, привязь 5 м к грузу или висение на 3 м; `v_max` = 1 м/с, `K_p` = 0.3, `FENCE_RADIUS = 30`, `FENCE_ALT_MAX = 10`, батарея ≥ 50 %. Пилот держит газ в середине и палец на переключателе Loiter, наблюдатель следит за привязью. Цель — на шесте 3 м или на радиоуправляемой машинке, не в руках; до 1 м/с. Прерывание (Loiter с пульта, затем посадка): колебания нарастают два периода подряд; аппарат смещается больше 1 м при неподвижной цели; после накрытия цели скорость не ноль через 1 с; горизонтальная скорость выше 1.5 м/с; высота ушла на 1 м; привязь натянулась; пропала телеметрия; companion троттлит. Приёмка: три прохода по 60 с без срабатывания критериев, отставание от цели ≤ 1 м, накрытие цели → HOLD ≤ 1 с и Loiter на 3-й секунде, логи companion и автопилота сведены по `TIMESYNC`.

Лабораторная засчитывается, когда (SITL): есть таблица p50/p95/max по стадиям и бюджет glass-to-command со своими числами; оценка по четырём срезам для двух конфигураций undistort, провал nominal объяснён через ворота по размеру и переприхват, после исправления nominal ≥ 0.95 / 0.95 и ошибка на земле p95 < 0.3 м; прогнаны сдвиги 0 / 50 / 100 мс и рост ошибки сопоставлен с `h·tan(ω·Δt)`; в выводе `sitl_follow.py` видны TRACK → HOLD через 0.5 с, LOITER через 3 с, остановка по `GUID_TIMEOUT` и по таймауту FOLLOW, остановка у геозоны и RTL при её нарушении, а также скорость выше `WP_SPD`. (Железо): RMS калибровки < 1 px; стендовая таблица — ошибка ≤ 5 см на 1.5 м, остаточный сдвиг времени в ±10 мс, знаки команд; три привязных прохода без критериев прерывания.

## diagnostics
- **Симптом:** точка на земле «плавает» на 0.5–1 м в такт крену, хотя цель неподвижна
  - Возможная причина: ориентация берётся из последнего `ATTITUDE`, а не интерполируется на метку экспозиции; метка кадра — время после `cap.read()`.
  - Что видно в логе: ошибка коррелирует с угловой скоростью, а не с углом.
  - Что сделать: метка буфера камеры + `TIMESYNC`, интерполяция; остаточный сдвиг подобрать на стенде качанием рамы.
- **Симптом:** после перекрытия или тени аппарат уверенно летит к камню, тени, чужой машине
  - Возможная причина: переприхват по пикселям без проверки на земле; ворота по размеру слишком широкие или кадр растянут полным undistort.
  - Что сделать: оценка по срезу «после потери»; undistort только точки; радиус переприхвата в метрах вокруг прогноза; после таймаута — защёлка до команды оператора.
- **Симптом:** команда отстаёт на секунду и больше, контур раскачивается
  - Возможная причина: очередь кадров в драйвере или GStreamer; инференс медленнее камеры.
  - Что сделать: `drop=true max-buffers=1`; детекция раз в 2–3 кадра с трекером между; пересчитать `K_p` по измеренной `T_d`.
- **Симптом:** companion завис, аппарат ещё три секунды летит с последней скоростью
  - Возможная причина: это штатное поведение `GUID_TIMEOUT`; watchdog был в том же процессе, что и завис.
  - Последствия: 18 м пути при 6 м/с.
  - Что сделать: `GUID_TIMEOUT` 0.5–1 с; watchdog отдельным процессом или systemd; геозона включена.
- **Симптом:** запрошено 6 м/с — летит 6 м/с при `WP_SPD = 3`
  - Возможная причина: `WP_SPD` не ограничивает скорости `SET_POSITION_TARGET_LOCAL_NED` (измерено на ArduCopter 4.6.3, код 4.7.2 тот же).
  - Что сделать: лимит `v_max` на companion, проверка в SITL до полёта.
- **Симптом:** после таймаута аппарат в LOITER снижается
  - Возможная причина: стик газа внизу или пульта нет.
  - Что сделать: пилот держит газ в середине; без пилота — BRAKE или нулевая скорость в GUIDED.
- **Симптом:** «Plnd: Frame not supported» либо PX4 пишет «Landing target: coordinate frame … unsupported»
  - Возможная причина: ArduPilot с `position_valid = 1` принимает только `MAV_FRAME_BODY_FRD`, PX4 — только `MAV_FRAME_LOCAL_NED`.
  - Что сделать: frame под стек; для ArduPilot проще углы `angle_x/angle_y` и `distance`.
- **Симптом:** FOLLOW включился, аппарат стоит на месте
  - Возможная причина: цель дальше `FOLL_DIST_MAX`; `FOLL_SYSID` не совпадает с отправителем; сообщения реже раза в 3 с.
  - Что сделать: проверить sysid и частоту потока; `FOLL_POS_P` по умолчанию 0.1 даёт медленное сближение.

## checklist
- Метка экспозиции идёт через весь конвейер; часы сведены `TIMESYNC`
- p50/p95/max по стадиям измерены, glass-to-command сложена и сравнена с бюджетом задачи
- Детектор и трекер оценены по срезам: свет, смаз, перекрытие, «после потери»
- Геопривязка: интерполяция `ATTITUDE`, источник AGL назван, ошибка от сдвига времени посчитана
- Интерлоки в трёх слоях: `v_max`, watchdog 0.5 с, таймаут 3 с с защёлкой; `GUID_TIMEOUT`, геозона; пилот
- В SITL проверены молчание companion, потеря цели, геозона и лимит скорости

## references
- ArduPilot Dev — Copter Commands in Guided Mode (type_mask 3527, остановка через 3 с) | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- ArduPilot source — GUIDED velocity control and timeout (`ArduCopter/mode_guided.cpp`, Copter-4.6.3) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_guided.cpp | primary | A
- ArduPilot source — AP_Follow: messages, FOLL_* parameters, 3 s timeout | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_Follow/AP_Follow.cpp | primary | A
- ArduPilot source — LANDING_TARGET handling in the companion backend | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_PrecLand/AC_PrecLand_Companion.cpp | primary | A
- ArduPilot source — fence avoidance for velocity commands (AVOID_ENABLE, AVOID_MARGIN) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_Avoidance/AC_Avoid.cpp | primary | A
- ArduPilot Copter — Precision Landing and Loiter (PLND_*) | https://ardupilot.org/copter/docs/precision-landing-and-loiter.html | primary | A
- ArduPilot Copter — Follow Mode | https://ardupilot.org/copter/docs/follow-mode.html | primary | A
- MAVLink — Common message set (LANDING_TARGET, SET_POSITION_TARGET_LOCAL_NED, FOLLOW_TARGET, TIMESYNC) | https://mavlink.io/en/messages/common.html | primary | A
- MAVLink — Time Synchronization Protocol | https://mavlink.io/en/services/timesync.html | primary | A
- PX4 — Offboard Mode (2 Гц proof of life, COM_OF_LOSS_T, COM_OBL_RC_ACT) | https://docs.px4.io/v1.17/en/flight_modes/offboard.html | primary | A
- PX4 — Precision Landing (LANDING_TARGET в MAV_FRAME_LOCAL_NED, PLD_*) | https://docs.px4.io/v1.17/en/advanced_features/precland.html | primary | A
- PX4 source — `mavlink_receiver.cpp`, handle_message_landing_target (v1.17.0) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/mavlink/mavlink_receiver.cpp | primary | A
- Linux kernel — V4L2 buffer: timestamp, TIMESTAMP_MONOTONIC, TSTAMP_SRC_EOF/SOE | https://docs.kernel.org/userspace-api/media/v4l/buffer.html | primary | A
- OpenCV — Camera calibration With OpenCV | https://docs.opencv.org/4.x/d4/d94/tutorial_camera_calibration.html | primary | B
- Bewley et al. — Simple Online and Realtime Tracking (SORT), 2016 | https://arxiv.org/abs/1602.00763 | primary | B
- Zhang et al. — ByteTrack: Multi-Object Tracking by Associating Every Detection Box, 2021 | https://arxiv.org/abs/2110.06864 | primary | B
