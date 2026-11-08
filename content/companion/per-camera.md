---
id: per-camera
title: "Камеры и видеопоток на companion"
level: L3
readingTime: 35 мин
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - камера
  - GStreamer
  - RTSP
  - OpenCV
  - задержка
related:
  - comp-raspberry
  - per-cv
  - link-vtx
next:
  - per-cv
---

## summary
Бортовое зрение начинается с кадра, который дошёл до программы вовремя. Модуль — про путь камера → память → алгоритм → GCS: CSI против USB, форматы (MJPEG/YUV/H.264), захват в Python с минимальной задержкой (libcamera/V4L2 через OpenCV или GStreamer), измерение реальной задержки и FPS, и передача потока в QGroundControl по RTSP/UDP через GStreamer с аппаратным кодированием. Лабораторная: кадры в OpenCV с замером FPS, RTSP-поток в QGC, измеренная задержка.

## theory
### Камеры и интерфейсы
- **CSI** (Raspberry Pi Camera v2/v3, HQ; Jetson IMX219/IMX477): прямой интерфейс к ISP, минимальная задержка (1–2 кадра), высокая частота (120 fps в низком разрешении), короткий шлейф (до ~30 см без усилителя — на дроне это ограничение). Управление через libcamera (Pi) / Argus (Jetson).
- **USB (UVC)**: любая веб-камера; задержка выше (буферы, USB-контроллер), часто только MJPEG на высоких fps (декодирование стоит CPU), зато кабель до 3–5 м и смена камеры без драйверов. Global shutter USB-камеры (например, на OV9281) — для быстрого движения и VIO.
- **IP-камеры/HDMI-захват**: для тяжёлых платформ; задержка 100+ мс — для телеметрии оператору, не для контура управления.
- **Затвор**: rolling (строки в разное время — «желе» при вибрации и быстром вращении; ломает VIO) против global (весь кадр одновременно). Для навигации — global.
- **Форматы**: YUV420 — сырой, дёшево для алгоритмов; MJPEG — сжат, каждый кадр независим, декодировать на CPU; H.264/H.265 — для передачи, кодировать аппаратно (Pi 4: H.264 до 1080p30; Jetson: NVENC).

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

## practice
### Шаг 1. Захват
USB или CSI: код выше, 640×480, фиксированная экспозиция; 30 с — средний FPS, дропы. Сравнить BUFFERSIZE 1 и 4.

### Шаг 2. Задержка glass-to-glass
Секундомер на телефоне → фото «экран vs окно OpenCV» ×5 → среднее. Затем с выводом через `cv2.imshow` отключённым (только захват + timestamp на кадре) — оценить вклад вывода.

### Шаг 3. Поток в QGC
GStreamer UDP H.264 на QGC; задержка glass-to-glass до экрана GCS; битрейт против качества/задержки (2 Мбит vs 8 Мбит).

### Шаг 4. RTSP
mediamtx или gst-rtsp-server; подключиться из QGC и VLC одновременно. Лабораторная: FPS измерен, RTSP в QGC, задержка измерена с числами.

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
- **Симптом:** автоэкспозиция «мигает» при наклонах
  - Возможная причина: AE реагирует на небо/землю.
  - Что сделать: фиксированная экспозиция/усиление или ограничение диапазона.

## references
- Raspberry Pi — Camera software (libcamera, picamera2) | https://raspberrypi.com/documentation/computers/camera_software.html | primary | A
- GStreamer — Documentation and tutorials | https://people.freedesktop.org/~tsaunier/documentation/doc_index.html | secondary | B
- QGroundControl — Video settings (UDP/RTSP sources) | https://docs.qgroundcontrol.com/master/en/qgc-user-guide/settings_view/video.html | primary | A

## checklist
- Знаю разницу CSI/USB, rolling/global shutter и форматов
- Захват с очередью 1 кадр и фиксированной экспозицией
- FPS и glass-to-glass задержка измерены
- Поток H.264 в QGC по UDP и RTSP работает
- Понимаю, где теряется задержка в цепочке и как её уменьшить
