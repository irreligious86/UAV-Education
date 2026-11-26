---
id: per-camera
title: "Камеры и видеопоток на companion"
level: L3
readingTime: 60 мин
firmware: ArduPilot · PX4 · OpenCV 5.0
status: published
added: 2026-11-08
tags:
  - камера
  - GStreamer
  - RTSP
  - OpenCV
  - задержка
  - GSD
  - калибровка
  - rolling shutter
related:
  - comp-raspberry
  - per-geometry
  - per-cv
  - link-vtx
next:
  - per-cv
---

## summary
Бортовое зрение начинается с кадра, который дошёл до программы вовремя. Модуль — про путь камера → память → алгоритм → GCS: CSI против USB, форматы (MJPEG/YUV/H.264), захват в Python с минимальной задержкой (libcamera/V4L2 через OpenCV или GStreamer), измерение реальной задержки и FPS, и передача потока в QGroundControl по RTSP/UDP через GStreamer с аппаратным кодированием. Вторая половина — оптика в числах: фокус в пикселях, угол обзора, GSD и пиксели на цели, смаз от скорости и от вращения, перекос rolling shutter, и что проверять в калибровке, кроме RMS. Лабораторная: расчёт оптики и настоящая калибровка OpenCV на синтетической доске (без камеры), затем кадры в OpenCV с замером FPS, RTSP-поток в QGC, измеренная задержка.

## theory
### Камеры и интерфейсы
- **CSI** (Raspberry Pi Camera v2/v3, HQ; Jetson IMX219/IMX477): прямой интерфейс к ISP, минимальная задержка (1–2 кадра), высокая частота (120 fps в низком разрешении), короткий шлейф (до ~30 см без усилителя — на дроне это ограничение). Управление через libcamera (Pi) / Argus (Jetson).
- **USB (UVC)**: любая веб-камера; задержка выше (буферы, USB-контроллер), часто только MJPEG на высоких fps (декодирование стоит CPU), зато кабель до 3–5 м и смена камеры без драйверов. Global shutter USB-камеры (например, на OV9281) — для быстрого движения и VIO.
- **IP-камеры/HDMI-захват**: для тяжёлых платформ; задержка 100+ мс — для телеметрии оператору, не для контура управления.
- **Затвор**: rolling (строки в разное время — «желе» при вибрации и быстром вращении; ломает VIO) против global (весь кадр одновременно). Для навигации — global.
- **Форматы**: YUV420 — сырой, дёшево для алгоритмов; MJPEG — сжат, каждый кадр независим, декодировать на CPU; H.264/H.265 — для передачи, кодировать аппаратно (Pi 4: H.264 до 1080p30; Jetson: NVENC).

{{diagram:camera-choice-tree|Выбор камеры начинается с вопроса, идёт ли кадр в контур: картинке оператору хватает IP-камеры со 100+ мс, навигации нужен global shutter, а CSI против USB решает длина кабеля — около 30 см против 3–5 м.}}

### Захват с минимальной задержкой
Принципы: (1) не копировать лишний раз, (2) короткая очередь буферов (1–2 кадра), (3) брать **последний** кадр, а не первый из очереди, (4) разрешение — по задаче (детектору хватает 640×480), (5) фиксированная экспозиция/усиление — иначе автоэкспозиция даёт рывки.

OpenCV + V4L2 (USB):
```python
import cv2, time
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 60); cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
t0 = time.perf_counter(); n = 0
while True:
    ok, frame = cap.read()                 # with BUFFERSIZE=1 this is the latest frame
    if not ok: break
    n += 1
    if n % 60 == 0: print(f"{n / (time.perf_counter() - t0):.1f} fps")
```
Pi CSI: `picamera2` (`Picamera2().configure(create_video_configuration(main={"size": (640, 480), "format": "RGB888"}, buffer_count=2))`, `capture_array()`); Jetson: GStreamer-пайплайн `nvarguscamerasrc ! nvvidconv ! video/x-raw,format=BGRx ! appsink` через `cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)`.

### Измерить задержку
«Glass-to-glass»: на экране телефона секундомер с миллисекундами (или мигающий LED с таймером), камера смотрит на него, программа показывает кадр рядом — фото обоих: разница = задержка захват+обработка+вывод. Для передачи в GCS — то же с экраном GCS. Типично: CSI + OpenCV локально 30–60 мс; USB MJPEG 60–120 мс; RTSP H.264 до QGC по Wi-Fi 150–300 мс (буферизация плеера — главный вклад; в QGC и GStreamer-приёмнике уменьшать `latency`).

FPS — считать по времени между кадрами, не по заявленному; дропы — по разнице номеров кадров/timestamp.

### Поток в GCS
GStreamer на борту (Pi 4, аппаратный H.264 через `v4l2h264enc`; Jetson — `nvv4l2h264enc`):
```bash
# UDP/RTP to the GCS (QGC: Video Source = UDP h.264, port 5600)
gst-launch-1.0 libcamerasrc ! video/x-raw,width=1280,height=720,framerate=30/1 \
  ! videoconvert ! v4l2h264enc extra-controls="controls,repeat_sequence_header=1,video_bitrate=2000000" \
  ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=192.168.1.10 port=5600 sync=false
```
RTSP-сервер (QGC: RTSP URL): `gst-rtsp-server` (`test-launch` из examples) или `mediamtx` с тем же пайплайном; RTSP удобен для нескольких клиентов и переподключений, UDP — минимальная задержка. Битрейт — по бюджету линка (2–4 Мбит/с для 720p30 на Wi-Fi/4G; для дальних линков 0.5–1 Мбит/с с 480p). Ключевые кадры чаще (`iframe period` 1 с) — быстрее восстановление после потерь.

### Камера и автопилот
Время кадра должно сопоставляться с данными полёта: timestamp кадра (монотонные часы) + MAVLink `SYSTEM_TIME`/`TIMESYNC` для синхронизации с FC; смещение и ориентация камеры относительно IMU (`CAM_*`/extrinsics) — для любой геометрии (VIO, слежение). Companion питается от своего BEC (модуль про периферию), камера и шлейф — вдали от силовых проводов.

{{diagram:glass-to-glass|Из чего складывается задержка видеопотока от света на сенсоре до экрана (типичные доли; измеряйте свою цепочку).}}

### Сенсор и объектив: фокус, угол обзора, пиксель
Камеру для задачи выбирают тремя числами. Первое — **размер пикселя p** (шаг сенсора, мкм). Второе — **фокусное расстояние f** объектива (мм). Третье — **разрешение режима** W×H, на котором реально работает алгоритм. Из них следует всё остальное:
- ширина активной области сенсора w = W_полн·p;
- горизонтальный угол обзора HFOV = 2·atan(w / 2f);
- фокусное расстояние в пикселях f_px = f / p_режима, где p_режима — эффективный пиксель выбранного режима. При биннинге 2×2 он удваивается, при кропе не меняется, но тогда сужается угол.

Почему важен именно f_px. Это коэффициент, переводящий углы в пиксели. Через него считаются и GSD, и смаз, и перекос rolling shutter, и та же величина стоит в матрице K калибровки (`per-geometry`).

| Камера (Raspberry Pi, паспорт; затвор — по сенсору) | Сенсор | Пиксель | Активная область | f | HFOV паспорт / формула | Затвор |
|---|---|---|---|---|---|---|
| Camera Module 2 | IMX219 (с ноября 2026 — IMX355) | 1.12 мкм | 3.68 × 2.76 мм | 3.04 мм | 62.2° / 62.4° | rolling |
| Camera Module 3 | IMX708, 4608×2592 | 1.4 мкм | 6.45 × 3.63 мм | 4.74 мм | 66° / 68.5° | rolling |
| Camera Module 3 Wide | IMX708 | 1.4 мкм | 6.45 × 3.63 мм | 2.75 мм | 102° / 99.1° | rolling |
| HQ Camera | IMX477 | 1.55 мкм | 6.287 × 4.712 мм | объектив C/CS | по объективу | rolling |
| Global Shutter Camera | IMX296, 1456×1088 | 3.45 мкм | 6.3 мм по диагонали | объектив C/CS | с 6 мм: 45.4° (формула) | global |

У CM3 и CM3 Wide паспорт и формула расходятся на 2.5–3° в разные стороны (у CM3 формула больше паспорта, у Wide — меньше), у CM2 — на 0.2°. Вероятные причины (вывод, в паспорте не объяснено): дисторсия объектива — у широкоугольника бочка расширяет реальный угол — и округлённое «номинальное» f. Поэтому f_px для геометрии берут из калибровки, а не из паспорта. Паспорт годится для выбора камеры, калибровка — для расчётов. Для CM3 в режиме 2304×1296 (биннинг 2×2, эффективный пиксель 2.8 мкм; список режимов показывает `rpicam-hello --list-cameras`) из паспортного f получается f_px = 4.74 мм / 2.8 мкм = 1693 px, а из паспортного HFOV 66° — (2304/2)/tan 33° = 1774 px. Разница почти 5 %, и только калибровка скажет, какое число верно для твоего экземпляра.

### GSD, след кадра и пиксели на объекте
Для камеры, смотрящей вниз (надир), с высоты h над ровной землёй:
- **GSD** (ground sample distance, метров на пиксель) = h·p_режима / f;
- **след кадра** = W·GSD × H·GSD;
- **пикселей на объекте** = размер объекта / GSD.

CM3, 2304×1296, f = 4.74 мм: на 30 м GSD = 1.77 см/px, след 41 × 23 м; на 50 м — 2.95 см/px, 68 × 38 м; на 100 м — 5.91 см/px, 136 × 77 м. Объект шириной 0.5 м занимает на 30, 50 и 100 м соответственно 28, 17 и 8 px, а с широкоугольной CM3 Wide (2.75 мм) — 16, 10 и 5 px. Детектору нужно хотя бы 20–30 px по меньшей стороне объекта (ориентир курса). Значит, поиск полуметровых целей с CM3 укладывается в высоту до 30–40 м. Широкий угол даёт больший след, но цели в нём «тают»: выбор объектива — это компромисс между площадью обзора и пикселями на цели, и решается он требованием, а не вкусом (`eng-method-101`). При наклонной камере GSD растёт к верху кадра. Поперёк направления взгляда GSD ≈ R·p/f, где R — дальность вдоль луча; вдоль направления взгляда пиксель на земле длиннее ещё в 1/cos θ раз (θ — угол луча от вертикали): GSD_вдоль ≈ h·p/(f·cos²θ). При θ = 45° это ещё ×1.41 к поперечному.

### Экспозиция и смаз движения
За время экспозиции t изображение смещается, и точка размазывается на полосу:
- от поступательного движения со скоростью v: смаз_px = v·t / GSD;
- от вращения с угловой скоростью ω поперёк оптической оси (крен и тангаж для камеры в надир, рыскание для камеры вперёд): смаз_px = ω·t·f_px.

CM3 на 50 м (GSD 2.95 см/px, f_px 1693), 10 м/с и поворот 90°/с:

| Экспозиция | Смаз от 10 м/с | Смаз от 90°/с |
|---|---|---|
| 1/2000 с | 0.17 px | 1.33 px |
| 1/1000 с | 0.34 px | 2.66 px |
| 1/500 с | 0.68 px | 5.32 px |
| 1/250 с | 1.35 px | 10.6 px |
| 1/60 с | 5.64 px | 44.3 px |

Вывод, который удивляет новичков: на высоте **смазывает вращение, а не полёт**. Поступательный смаз уходит под 0.5 px уже при 1/677 с, а вращение 90°/с даёт 1.3 px даже при 1/2000 с. Поэтому для зрения важнее плавные манёвры и демпфирование, чем скорость. Для трекинга признаков (VIO, оптический поток) держи смаз ≤ 0.5–1 px (ориентир курса); детектор крупных объектов терпит несколько пикселей.

{{diagram:camera-motion-blur|Смаз растёт линейно с экспозицией, но вращение 90°/с смазывает в восемь раз сильнее, чем полёт 10 м/с на высоте 50 м: при 1/500 с это 5.3 px против 0.7 px.}}

Короткая экспозиция не бесплатна. При том же свете сократить t вдвое — значит поднять усиление вдвое. Шум фотонов (shot noise) определяется числом собранных электронов N, SNR = √N, поэтому половина света — это SNR в √2 раз ниже (−3 дБ). В сумерках короткой выдержкой с приличным шумом не обойтись, и тогда выручают большой пиксель (у GS Camera 3.45 мкм против 1.4 мкм у CM3 — площадь в 6 раз больше; против 2.8 мкм в биннинге 2×2 — в 1.5 раза) или светосильный объектив. Автоэкспозиция на борту ограничивается сверху по времени (например, не длиннее 2 мс) и отдельно по усилению: иначе AE при наклоне к земле удлиняет выдержку и смаз «дышит» от кадра к кадру.

### Rolling и global shutter в числах
Сенсор с rolling shutter читает строки по очереди. Время считывания кадра t_r не превышает периода кадра: при 60 кадр/с t_r ≤ 16.7 мс (точное значение берётся из документации сенсора или драйвера). Верх и низ кадра сняты с разницей t_r, и при движении кадр перекашивается:
- при повороте поперёк оптической оси (крен и тангаж для камеры в надир, рыскание для камеры вперёд) перекос до ω·t_r·f_px: 90°/с, f_px 1693 → до 89 px при 30 кадр/с и до 44 px при 60 кадр/с;
- от поступательного движения на высоте до v·t_r/GSD: 10 м/с на 50 м → до 11.3 px при 30 кадр/с.

Для детектора перекос в десятки пикселей — искажение формы. Для VIO и геометрии это систематическая ошибка, которую фильтр примет за движение, поэтому навигационные камеры делают global shutter (IMX296 в таблице выше, OV9281 у USB-камер). Вибрация с периодом, сравнимым с t_r, превращает перекос в «желе»: прямые изгибаются волной. Лечится это механикой, а не софтом (`per-fpv-footage`, `f-frame-mech`).

### Дисторсия и калибровка: что проверять в результате
Модель дисторсии Brown–Conrady, процедура `cv2.calibrateCamera` и использование K в цепочке «пиксель → земля» разобраны в `per-geometry`. Здесь — проверка, которую делают сразу после калибровки. Лабораторная (шаг 2) прогоняет её на синтетике, где истина известна: f = 900 px, k₁ = −0.28.
- **RMS перепроекции мал — ещё не значит, что калибровка верна.** 25 почти фронтальных кадров (наклон доски до 3°) дали RMS 0.42 px, а f_x = 919.6 ± 79.0 px: ошибка 2 % при неопределённости 9 %. Фокус и расстояние до доски на фронтальных кадрах неразличимы. `cv2.calibrateCameraExtended` возвращает стандартные отклонения параметров (`stdDeviationsIntrinsics`), и смотреть надо на них: σ(f_x) должна быть меньше 1 % от f_x (ориентир курса).
- **Наклон доски до 40°** дал f_x = 899.4 ± 0.8 px и k₁ = −0.2793 при RMS 0.30 px.
- **Край кадра — экстраполяция.** Даже хорошая калибровка в углу кадра (1270, 710) ошибается на 4.5 px: доска туда не доходила. Без модели дисторсии ошибка в той же точке — 160 px. Кадры, где доска заходит в углы, ценнее десятка кадров в центре.
- **Калибровка привязана к режиму.** f_px в режиме 2304×1296 вдвое меньше, чем в 4608×2592; кроп сдвигает главную точку. Автофокус (у CM3 он есть) меняет f, поэтому на борту фокус фиксируют (`LensPosition` в picamera2) и калибруют при этой позиции.

{{lesson:per-geometry|Как калибровку используют: пиксель → луч → точка на земле, бюджет ошибок цепочки и синтетическая проверка «туда и обратно».}}

### Справочная таблица: формулы и инструменты

| Величина | Формула / инструмент | Пример модуля |
|---|---|---|
| Угол обзора | HFOV = 2·atan(W·p / 2f) | CM3: 2·atan(6.45/9.48) = 68.5° |
| Фокус в пикселях | f_px = f / p_режима = (W/2)/tan(HFOV/2) | 4.74 мм / 2.8 мкм = 1693 px |
| GSD (надир) | h·p_режима / f | 50 м → 2.95 см/px |
| Пикселей на объекте | размер / GSD | 0.5 м на 50 м → 17 px |
| Смаз от скорости | v·t / GSD | 10 м/с, 1/500 с → 0.68 px |
| Смаз от вращения | ω·t·f_px | 90°/с, 1/500 с → 5.3 px |
| Перекос rolling shutter | ω·t_r·f_px, t_r ≤ 1/fps | 90°/с, 30 кадр/с → 89 px |
| Шум при укорочении выдержки | SNR ∝ √(свет) | t/2 → SNR/√2 (−3 дБ) |
| Калибровка | `cv2.findChessboardCorners`, `cornerSubPix`, `calibrateCameraExtended` | OpenCV 5.0.0 (PyPI `opencv-python-headless`, актуальная 5.1.0.95) |
| Режимы и фокус Pi | `rpicam-hello --list-cameras`; picamera2 `LensPosition` | Raspberry Pi OS Bookworm и новее |

### Место в системе

- **Получает:** питание и вычислитель companion (`comp-raspberry`, `comp-jetson-nano`); время автопилота через `SYSTEM_TIME`/`TIMESYNC` (`mav-services`); битрейт по бюджету линка (`rf-link-budget`).
- **Отдаёт:** свежий кадр с меткой времени — детектору (`per-cv`); смещение и ориентацию камеры относительно IMU — геометрии (`per-geometry`); поток H.264 в QGC.
- **Если ошибиться здесь:** программа берёт первый кадр из очереди, а не последний → детектор работает по устаревшей картинке, контур слежения раскачивается (`per-tracking`). Rolling shutter при вибрации и быстром вращении → «желе», VIO теряет признаки (`per-visual-nav`); источник вибраций ищут в `f-frame-mech`.

## practice
Шаги 1–2 не требуют камеры: расчёт оптики и настоящая калибровка OpenCV на шахматной доске, отрисованной кодом. Они запущены в песочнице курса (Python 3.13, NumPy 2.5, OpenCV 5.0.0 из `pip install opencv-python-headless`), вывод вставлен без правок. Шагам 3–6 нужны камера и companion.

### Шаг 1. Оптика в числах
Скрипт считает по паспортным данным Raspberry Pi угол обзора, f_px, GSD и след кадра, смаз и перекос rolling shutter, пиксели на объекте 0.5 м. Подставь свою камеру (ширину сенсора, разрешение режима, пиксель, f), высоту и скорость своей задачи.

```python
"""per-camera: sensor/lens arithmetic with the module's worked numbers."""
import math
cams = {  # name: (sensor width mm, W px full, pixel um, focal mm)   -- RPi camera docs, hardware table
    "CM3 (IMX708) 4.74 mm": (6.45, 4608, 1.4, 4.74),
    "CM3 Wide 2.75 mm": (6.45, 4608, 1.4, 2.75),
    "GS (IMX296) + 6 mm": (1456 * 3.45e-3, 1456, 3.45, 6.0),
}
for name, (sw, wpx, pu, f) in cams.items():
    hfov = 2 * math.degrees(math.atan(sw / 2 / f))
    print(f"{name}: sensor {sw:.2f} mm, HFOV {hfov:.1f} deg, f_px(full {wpx}) {f / (pu * 1e-3):.0f}")
# CM3 in the 2304x1296 mode (2x2 binning, full field of view): effective pixel 2.8 um
W, Hh, p, f = 2304, 1296, 2.8e-6, 4.74e-3
fpx = f / p
print(f"\nCM3 2304x1296: f_px = {fpx:.0f} px; check via HFOV 66 deg (docs): {(W/2)/math.tan(math.radians(33)):.0f} px")
for h in (30, 50, 100):
    gsd = h * p / f
    print(f"  h={h:3d} m: GSD {gsd*100:.2f} cm/px, footprint {W*gsd:.0f} x {Hh*gsd:.0f} m")
h = 50; gsd = h * p / f
print(f"\nmotion blur at h=50 m, v=10 m/s (GSD {gsd*100:.2f} cm/px):")
for t in (1/2000, 1/1000, 1/500, 1/250, 1/60):
    print(f"  t=1/{1/t:.0f} s: translation {10*t/gsd:.2f} px, rotation 90 deg/s: {math.radians(90)*t*fpx:.2f} px")
t_max = 0.5 * gsd / 10
print(f"  t_exp for <=0.5 px at 10 m/s: {t_max*1e3:.2f} ms = 1/{1/t_max:.0f} s")
for fps in (30, 60):
    tr = 1 / fps
    print(f"rolling shutter, readout <= 1/{fps} s: roll/pitch 90 deg/s -> skew top-to-bottom up to {math.radians(90)*tr*fpx:.0f} px; "
          f"10 m/s at 50 m -> {10*tr/gsd:.1f} px")
# object 0.5 m wide: pixels on target
for h in (30, 50, 100):
    print(f"0.5 m object at {h} m: {0.5/(h*p/f):.0f} px  (wide lens 2.75 mm: {0.5/(h*p/2.75e-3):.0f} px)")
```

```text
CM3 (IMX708) 4.74 mm: sensor 6.45 mm, HFOV 68.5 deg, f_px(full 4608) 3386
CM3 Wide 2.75 mm: sensor 6.45 mm, HFOV 99.1 deg, f_px(full 4608) 1964
GS (IMX296) + 6 mm: sensor 5.02 mm, HFOV 45.4 deg, f_px(full 1456) 1739

CM3 2304x1296: f_px = 1693 px; check via HFOV 66 deg (docs): 1774 px
  h= 30 m: GSD 1.77 cm/px, footprint 41 x 23 m
  h= 50 m: GSD 2.95 cm/px, footprint 68 x 38 m
  h=100 m: GSD 5.91 cm/px, footprint 136 x 77 m

motion blur at h=50 m, v=10 m/s (GSD 2.95 cm/px):
  t=1/2000 s: translation 0.17 px, rotation 90 deg/s: 1.33 px
  t=1/1000 s: translation 0.34 px, rotation 90 deg/s: 2.66 px
  t=1/500 s: translation 0.68 px, rotation 90 deg/s: 5.32 px
  t=1/250 s: translation 1.35 px, rotation 90 deg/s: 10.64 px
  t=1/60 s: translation 5.64 px, rotation 90 deg/s: 44.32 px
  t_exp for <=0.5 px at 10 m/s: 1.48 ms = 1/677 s
rolling shutter, readout <= 1/30 s: roll/pitch 90 deg/s -> skew top-to-bottom up to 89 px; 10 m/s at 50 m -> 11.3 px
rolling shutter, readout <= 1/60 s: roll/pitch 90 deg/s -> skew top-to-bottom up to 44 px; 10 m/s at 50 m -> 5.6 px
0.5 m object at 30 m: 28 px  (wide lens 2.75 mm: 16 px)
0.5 m object at 50 m: 17 px  (wide lens 2.75 mm: 10 px)
0.5 m object at 100 m: 8 px  (wide lens 2.75 mm: 5 px)
```

Сверь с теорией: GSD 2.95 см/px на 50 м, смаз 0.68 / 5.32 px при 1/500 с, перекос 89 px при 30 кадр/с. Затем реши задачу выбора: нужно искать объект 0.5 м, детектору требуется ≥ 20 px. CM3 на 50 м даёт 17 px — мало. Варианты: высота ≤ 42 м (0.5 / 20 = 2.5 см/px → h = 0.025·4.74/0.0028 = 42 м) или полное разрешение 4608×2592 (34 px на 50 м, но вчетверо больше пикселей на инференс). Широкоугольная CM3 Wide на той же высоте даёт 10 px и не подходит совсем.

### Шаг 2. Калибровка на синтетической доске
Камера с известной истиной: 1280×720, f = 900 px, главная точка (652, 355), бочкообразная дисторсия k₁ = −0.28, k₂ = 0.09. Каждый кадр рисуется обратным отображением. Для каждого пикселя снимается дисторсия, строится луч, ищется его пересечение с плоскостью доски 9×6 (клетка 25 мм) и берётся цвет клетки. Затем немного размытия и шум σ = 2. Дальше настоящий конвейер: `findChessboardCorners` → `cornerSubPix` → `calibrateCameraExtended` (k₃ зафиксирован). Три прогона калибровки — (A) 25 кадров с наклоном доски до 40°; (B) 25 почти фронтальных кадров, до 3°; (C) как A, но с горизонтальным смазом 7 px — и проверка без модели дисторсии. Время прогона — около 20 с.

```python
"""per-camera lab: real OpenCV calibration on checkerboard images rendered in code.

Truth: 1280x720 camera, f = 900 px, c = (652, 355), k1 = -0.28, k2 = 0.09 (barrel, wide lens).
Board 9x6 inner corners, 25 mm squares. Each view: random pose -> exact projection with distortion
-> image rendered by inverse mapping (every output pixel -> undistort -> ray -> board plane).
"""
import sys
import numpy as np, cv2
cv2.setNumThreads(1)                             # deterministic results (course rule: reproducible numbers)

W, H = 1280, 720
K_true = np.array([[900.0, 0, 652.0], [0, 900.0, 355.0], [0, 0, 1]])
D_true = np.array([-0.28, 0.09, 0.0, 0.0, 0.0])
COLS, ROWS, SQ = 9, 6, 0.025                     # inner corners, square size m
obj = np.zeros((ROWS * COLS, 3), np.float32)
obj[:, :2] = np.mgrid[0:COLS, 0:ROWS].T.reshape(-1, 2) * SQ

# undistorted normalized coords of every output pixel (fixed for the camera)
uu, vv = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
pix = np.stack([uu.ravel(), vv.ravel()], 1).reshape(-1, 1, 2)
norm = cv2.undistortPoints(pix, K_true, D_true, criteria=(cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 40, 1e-9)).reshape(-1, 2)
rays = np.hstack([norm, np.ones((norm.shape[0], 1))])

def render(rvec, tvec, blur_px=0.0, noise=2.0, rng=None):
    R, _ = cv2.Rodrigues(rvec)
    n = R[:, 2]; d = n @ tvec.ravel()                      # board plane in camera frame: n.X = d
    s = d / (rays @ n)                                     # ray scale to hit the plane
    P = rays * s[:, None] - tvec.ravel()
    B = P @ R                                              # board coordinates
    i = np.floor(B[:, 0] / SQ + 1); j = np.floor(B[:, 1] / SQ + 1)
    inside = (B[:, 0] > -SQ) & (B[:, 0] < COLS * SQ) & (B[:, 1] > -SQ) & (B[:, 1] < ROWS * SQ) & (s > 0)
    img = np.full(W * H, 128.0)
    img[inside] = np.where(((i + j) % 2 == 0)[inside], 30.0, 225.0)
    img = img.reshape(H, W)
    img = cv2.GaussianBlur(img, (0, 0), 0.7)
    if blur_px > 0:                                        # horizontal motion blur
        k = np.zeros((1, int(blur_px) | 1)); k[:] = 1.0 / k.size
        img = cv2.filter2D(img, -1, k)
    img += rng.normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)

def views(rng, n, tilt_deg, spread=1.0):
    out = []
    while len(out) < n:
        rvec = np.deg2rad(rng.uniform(-tilt_deg, tilt_deg, 3)) * np.array([1, 1, 0.3])
        z = rng.uniform(0.35, 0.7)
        cx, cy = (COLS - 1) * SQ / 2, (ROWS - 1) * SQ / 2
        R, _ = cv2.Rodrigues(rvec)
        target = np.array([rng.uniform(-0.45, 0.45) * spread * z, rng.uniform(-0.25, 0.25) * spread * z, z])
        tvec = (target - R @ np.array([cx, cy, 0])).reshape(3, 1)
        pts, _ = cv2.projectPoints(obj, rvec, tvec, K_true, D_true)
        p = pts.reshape(-1, 2)
        if p[:, 0].min() < 20 or p[:, 0].max() > W - 20 or p[:, 1].min() < 20 or p[:, 1].max() > H - 20:
            continue
        out.append((rvec, tvec))
    return out

def calibrate(name, n, tilt, seed, blur=0.0, spread=1.0):
    rng = np.random.default_rng(seed)
    objp, imgp, cov = [], [], np.zeros((H // 40, W // 40), bool)
    for rvec, tvec in views(rng, n, tilt, spread):
        img = render(rvec, tvec, blur, rng=rng)
        ok, c = cv2.findChessboardCorners(img, (COLS, ROWS), cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not ok:
            continue
        c = cv2.cornerSubPix(img, c, (5, 5), (-1, -1), (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3))
        objp.append(obj); imgp.append(c)
        for u, v in c.reshape(-1, 2):
            cov[int(v) // 40, int(u) // 40] = True
    flags = cv2.CALIB_FIX_K3
    rms, K, D, rv, tv, sdi, sde, per = cv2.calibrateCameraExtended(objp, imgp, (W, H), None, None, flags=flags)
    sd = sdi.ravel()
    print(f"[{name}] views used {len(objp)}/{n}, coverage {cov.mean()*100:.0f}% of 40px cells")
    print(f"  RMS reprojection {rms:.3f} px")
    print(f"  fx {K[0,0]:.1f} (+-{sd[0]:.1f})  fy {K[1,1]:.1f}  cx {K[0,2]:.1f} (+-{sd[2]:.1f})  cy {K[1,2]:.1f}   truth 900/900/652/355")
    print(f"  k1 {D.ravel()[0]:+.4f} k2 {D.ravel()[1]:+.4f}   truth -0.2800 +0.0900")
    # what the error does at the frame corner: undistort the true corner pixel with both models
    corner = np.array([[[1270.0, 710.0]]])
    a = cv2.undistortPoints(corner, K_true, D_true, P=K_true).ravel()
    b = cv2.undistortPoints(corner, K, D, P=K_true).ravel()
    print(f"  corner pixel (1270,710) after undistort: error {np.hypot(*(a-b)):.2f} px vs truth")
    return K, D

if __name__ == "__main__":
    calibrate("A: 25 views, tilt up to 40 deg", 25, 40, 1)
    calibrate("B: 25 views, nearly frontal (tilt 3 deg)", 25, 3, 2)
    calibrate("C: 25 views, tilt 40, 7 px motion blur", 25, 40, 3, blur=7)
    # ignoring distortion entirely: how far is a corner-of-frame point?
    corner = np.array([[[1270.0, 710.0]]])
    a = cv2.undistortPoints(corner, K_true, D_true, P=K_true).ravel()
    print(f"no distortion model: corner pixel (1270,710) really maps to ({a[0]:.1f},{a[1]:.1f}) -> error {np.hypot(1270-a[0],710-a[1]):.1f} px")
```

```text
[A: 25 views, tilt up to 40 deg] views used 25/25, coverage 55% of 40px cells
  RMS reprojection 0.297 px
  fx 899.4 (+-0.8)  fy 900.2  cx 653.2 (+-1.4)  cy 352.7   truth 900/900/652/355
  k1 -0.2793 k2 +0.0874   truth -0.2800 +0.0900
  corner pixel (1270,710) after undistort: error 4.51 px vs truth
[B: 25 views, nearly frontal (tilt 3 deg)] views used 25/25, coverage 63% of 40px cells
  RMS reprojection 0.415 px
  fx 919.6 (+-79.0)  fy 919.5  cx 649.6 (+-2.4)  cy 353.0   truth 900/900/652/355
  k1 -0.2976 k2 +0.1057   truth -0.2800 +0.0900
  corner pixel (1270,710) after undistort: error 17.29 px vs truth
[C: 25 views, tilt 40, 7 px motion blur] views used 25/25, coverage 55% of 40px cells
  RMS reprojection 0.318 px
  fx 899.6 (+-1.2)  fy 899.4  cx 654.0 (+-1.7)  cy 356.4   truth 900/900/652/355
  k1 -0.2808 k2 +0.0929   truth -0.2800 +0.0900
  corner pixel (1270,710) after undistort: error 5.51 px vs truth
no distortion model: corner pixel (1270,710) really maps to (1409.0,789.9) -> error 160.3 px
```

Что читать. В прогоне A всё сходится с истиной в пределах σ: f_x 899.4 ± 0.8, k₁ −0.2793. В прогоне B RMS почти тот же (0.42 px), а f_x ушёл на 20 px с σ = 79 px. По одному RMS «плохую» калибровку не отличить, нужно смотреть на σ параметров. Многопоточный OpenCV менял σ в B от запуска к запуску на десятые доли пикселя. Поэтому в скрипте стоит `cv2.setNumThreads(1)`: вывод совпадает до последней цифры при каждом запуске (правило воспроизводимости из `eng-method-101`). Прогон C показывает, что симметричный смаз 7 px на синтетике почти не вредит: угол клетки смещается симметрично. На реальной камере смаз приходит вместе с rolling shutter и меняет форму доски, поэтому кадры со смазом отбрасывают. Последняя строка — цена забытой дисторсии: 160 px в углу кадра.

### Переход на реальное железо: калибровка своей камеры
Распечатай доску 9×6 с клеткой 25 мм и проверь линейкой, что клетка именно 25.0 мм: принтер масштабирует, и ошибка размера клетки уходит в масштаб t, а не в K. Наклей на жёсткую плоскую основу. Камеру переведи в рабочий режим (то же разрешение и биннинг, что в полёте), автофокус выключи и зафиксируй (`LensPosition`), экспозицию сделай короткой и фиксированной. Сними 25–40 резких кадров: наклон до 40°, доска в каждом углу кадра, разные расстояния. Запусти тот же конвейер с `calibrateCameraExtended`. Приёмка (ориентир курса): RMS < 0.5 px (до 1 px допустимо), σ(f_x) < 1 % от f_x, f_x ≈ f_y в пределах 1–2 %, f_x в пределах ~5 % от паспортной оценки (для CM3 в 2304×1296 — между 1693 и 1774 px), главная точка в пределах ~5 % от центра. Если σ(f_x) большая — добавь наклонных кадров. Если RMS большой — выброси смазанные кадры и проверь плоскость доски. Камера на дроне: калибруй до установки или со снятыми пропеллерами, АКБ не подключена.

### Шаг 3. Захват
USB или CSI: код выше, 640×480, фиксированная экспозиция; 30 с — средний FPS, дропы. Сравнить BUFFERSIZE 1 и 4.

### Шаг 4. Задержка glass-to-glass
Секундомер на телефоне → фото «экран vs окно OpenCV» ×5 → среднее. Затем с выводом через `cv2.imshow` отключённым (только захват + timestamp на кадре) — оценить вклад вывода.

Точнее и без фото — мигающий экран. Камера смотрит на окно, которое программа переключает между чёрным и белым; задержка = момент, когда камера увидела смену, минус момент переключения (одни и те же часы, поэтому синхронизация не нужна):
```python
import cv2, numpy as np, time
cap = cv2.VideoCapture(0); cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
cv2.namedWindow("flash", cv2.WINDOW_NORMAL)
lat = []
for k in range(20):
    white = k % 2 == 0
    cv2.imshow("flash", np.full((400, 400), 255 if white else 0, np.uint8)); cv2.waitKey(1)
    t_switch = time.perf_counter()
    while True:
        ok, f = cap.read()
        if ok and (f.mean() > 128) == white:          # the camera now sees the new colour
            lat.append((time.perf_counter() - t_switch) * 1000); break
    time.sleep(0.3)
print(f"latency median {np.median(lat):.0f} ms, p95 {np.percentile(lat, 95):.0f} ms")
```
Камеру направить так, чтобы окно занимало почти весь кадр; в результат входит и задержка самого монитора (5–20 мс) — для сравнения вариантов (USB против CSI, MJPEG против YUYV, BUFFERSIZE 1 против 4) это не мешает.

### Шаг 5. Поток в QGC
GStreamer UDP H.264 на QGC; задержка glass-to-glass до экрана GCS; битрейт против качества/задержки (2 Мбит vs 8 Мбит).

Порядок величин для настройки: 1280×720 при 30 кадр/с и 2 Мбит/с — в среднем ~8 КБ на кадр; ключевой кадр (I-frame) в 5–10 раз больше, и на слабом канале именно он приходит с опозданием или теряется. Отсюда настройки для низкой задержки: короткий интервал ключевых кадров (0.5–1 с), `config-interval=1` в `rtph264pay` (параметры потока повторяются — приёмник, подключившийся позже, сразу начинает декодировать), без B-кадров.

### Шаг 6. RTSP
mediamtx или gst-rtsp-server; подключиться из QGC и VLC одновременно. Сравни FPS, задержку (медиана и p95 мигающим экраном) для двух вариантов захвата, RTSP в QGC, битрейт и интервал ключевых кадров.

Самопроверка: лабораторная выполнена, когда для расчётной части (шаги 1–2, без камеры) скрипт шага 1 на данных примера выдаёт GSD 2.95 см/px на 50 м, смаз 0.68 и 5.32 px при 1/500 с, перекос 89 px при 30 кадр/с, а для своей камеры посчитаны GSD, пиксели на цели и выдержка, при которой поступательный смаз ≤ 0.5 px; калибровка шага 2 даёт в прогоне A f_x 899 ± 1 px, k₁ −0.279 ± 0.002, RMS около 0.3 px, в прогоне B — σ(f_x) порядка 80 px при RMS около 0.4 px, без модели дисторсии — 160 px в углу; калибровка своей камеры проходит приёмку из «Перехода на реальное железо» (RMS < 0.5–1 px, σ(f_x) < 1 %, f_x в пределах 5 % от паспорта). Для потоковой части (шаги 3–6, с камерой): FPS посчитан по времени между кадрами, а не взят из заявленного; медиана задержки сопоставлена с типичными значениями из теории (CSI + OpenCV локально 30–60 мс, USB MJPEG 60–120 мс, RTSP H.264 до QGC по Wi-Fi 150–300 мс) с учётом 5–20 мс монитора — если вышло в разы больше, смотри `BUFFERSIZE` и буферизацию плеера (`latency`); битрейт сверен с расчётом (~8 КБ на кадр при 2 Мбит/с и 30 кадр/с), интервал ключевых кадров 0.5–1 с.

**Эталон для самопроверки.** Верная оптика CM3 в 2304×1296: f_px ≈ 1693 px по паспортному f (1774 px по паспортному HFOV, правду скажет калибровка), GSD = h·2.8 мкм / 4.74 мм. Типичные ошибки: (1) GSD вдвое меньше верного (1.48 вместо 2.95 см/px на 50 м) — взят пиксель 1.4 мкм полного режима, хотя алгоритм работает в биннинге 2×2: цель кажется вдвое крупнее, чем её увидит детектор; (2) «смаз мал, значит, можно 1/250 с» — посчитан только поступательный смаз, а вращение 90°/с даёт 10.6 px; (3) калибровка «отличная, RMS 0.4 px», а f_x врёт на 2 % — все кадры фронтальные, σ(f_x) не проверена; (4) GSD считается по паспортному HFOV, а K для геометрии — по калибровке, и числа в одном отчёте расходятся на 5 %: в расчётах используй одно — калиброванное — значение.

## diagnostics
- **Симптом:** задержка растёт со временем
  - Возможная причина: алгоритм медленнее FPS — очередь буферов копится.
  - Что сделать: BUFFERSIZE 1, брать последний кадр, снизить разрешение/FPS, пропускать кадры.
- **Симптом:** «желе»/изгибы на движении
  - Возможная причина: rolling shutter + вибрации.
  - Что сделать: демпфирование камеры, global shutter, короче экспозиция.
- **Симптом:** в QGC поток дёргается
  - Возможная причина: битрейт выше пропускной способности, потери пакетов без ключевых кадров.
  - Что сделать: битрейт ниже, iframe чаще, проверить Wi-Fi/бюджет.
- **Симптом:** CSI-камера не определяется
  - Возможная причина: шлейф/разъём, длина, не включён overlay.
  - Что сделать: `rpicam-hello --list-cameras` (до Raspberry Pi OS Bookworm — `libcamera-hello`), шлейф короче, конфиг `dtoverlay`.
- **Симптом:** детектор уверенно видит цели на 20 м и теряет их на 50 м
  - Возможная причина: на высоте мало пикселей на цели (0.5 м на 50 м с CM3 в 2304×1296 — 17 px).
  - Что сделать: посчитать пиксели на цели по GSD (шаг 1); снизить высоту, поднять разрешение режима или взять объектив с большим f.
- **Симптом:** кадры резкие на прямой, смазанные на разворотах
  - Возможная причина: смаз от вращения ω·t·f_px — при 1/500 с и 90°/с это 5.3 px.
  - Что сделать: ограничить выдержку сверху (AE с пределом), плавнее разворачиваться, ограничить угловую скорость в режиме съёмки.
- **Симптом:** калибровка с малым RMS, а точки на земле врут на проценты дальности
  - Возможная причина: фронтальные кадры — f_x плохо определён (σ большая), или калибровка в другом режиме/фокусе.
  - Что сделать: `calibrateCameraExtended`, проверить σ(f_x) < 1 %; калибровать в рабочем режиме с зафиксированным `LensPosition`.
- **Симптом:** f_x из калибровки на 5 % отличается от расчёта по паспортному HFOV
  - Возможная причина: вероятно, паспортный угол округлён или учитывает дисторсию (у CM3: 1693 px по f против 1774 px по HFOV).
  - Что сделать: это нормально; если σ(f_x) мала, верь калибровке.
- **Симптом:** автоэкспозиция «мигает» при наклонах
  - Возможная причина: AE реагирует на небо/землю.
  - Что сделать: фиксированная экспозиция/усиление или ограничение диапазона.

## references
- Raspberry Pi — Camera software (libcamera, picamera2) | https://raspberrypi.com/documentation/computers/camera_software.html | primary | A
- GStreamer — Documentation | https://gstreamer.freedesktop.org/documentation/ | secondary | B
- Raspberry Pi — Camera hardware (таблица: сенсор, пиксель, f, HFOV) | https://www.raspberrypi.com/documentation/hardware/camera/computers/camera_software.html | primary | A
- Raspberry Pi — Camera Module 3 (IMX708, 4608×2592, 1.4 мкм) | https://www.raspberrypi.com/documentation/accessories/camera-module-3.html | primary | A
- OpenCV — Camera calibration tutorial (Python) | https://github.com/opencv/opencv/blob/5.x/doc/py_tutorials/py_calib3d/py_calibration/py_calibration.markdown | primary | A
- OpenCV — calib3d (calibrateCameraExtended, stdDeviationsIntrinsics) | https://docs.opencv.org/5.x/d9/d0c/group__calib3d.html | primary | A
- QGroundControl — Video settings (UDP/RTSP sources) | https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/settings_view/video.html | primary | A

## checklist
- Знаю разницу CSI/USB, rolling/global shutter и форматов
- Захват с очередью 1 кадр и фиксированной экспозицией
- FPS и glass-to-glass задержка измерены
- Поток H.264 в QGC по UDP и RTSP работает
- Понимаю, где теряется задержка в цепочке и как её уменьшить
- Считаю HFOV, f_px, GSD и пиксели на цели по паспорту камеры и режиму
- Выбираю выдержку по смазу от скорости и от вращения
- Оцениваю перекос rolling shutter и знаю, когда нужен global shutter
- Калибрую камеру и проверяю σ параметров, а не только RMS
