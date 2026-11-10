---
id: per-camera
title: "Камери й відеопотік на companion"
level: L3
readingTime: 35 хв
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - камера
  - GStreamer
  - RTSP
  - OpenCV
  - затримка
related:
  - comp-raspberry
  - per-cv
  - link-vtx
next:
  - per-cv
source: content/companion/per-camera.md
source_hash: 123e3eec0657
---

## summary
Бортовий зір починається з кадру, який дійшов до програми вчасно. Модуль — про шлях камера → пам'ять → алгоритм → GCS: CSI проти USB, формати (MJPEG/YUV/H.264), захоплення в Python із мінімальною затримкою (libcamera/V4L2 через OpenCV або GStreamer), вимірювання реальної затримки та FPS, і передавання потоку в QGroundControl за RTSP/UDP через GStreamer з апаратним кодуванням. Лабораторна: кадри в OpenCV із вимірюванням FPS, RTSP-потік у QGC, виміряна затримка.

## theory
### Камери й інтерфейси
- **CSI** (Raspberry Pi Camera v2/v3, HQ; Jetson IMX219/IMX477): прямий інтерфейс до ISP, мінімальна затримка (1–2 кадри), висока частота (120 fps у низькій роздільній здатності), короткий шлейф (до ~30 см без підсилювача — на дроні це обмеження). Керування через libcamera (Pi) / Argus (Jetson).
- **USB (UVC)**: будь-яка вебкамера; затримка вища (буфери, USB-контролер), часто лише MJPEG на високих fps (декодування коштує CPU), зате кабель до 3–5 м і заміна камери без драйверів. Global shutter USB-камери (наприклад, на OV9281) — для швидкого руху та VIO.
- **IP-камери/HDMI-захоплення**: для важких платформ; затримка 100+ мс — для телеметрії операторові, не для контуру керування.
- **Затвор**: rolling (рядки в різний час — «желе» за вібрації та швидкого обертання; ламає VIO) проти global (увесь кадр одночасно). Для навігації — global.
- **Формати**: YUV420 — сирий, дешево для алгоритмів; MJPEG — стиснутий, кожен кадр незалежний, декодувати на CPU; H.264/H.265 — для передавання, кодувати апаратно (Pi 4: H.264 до 1080p30; Jetson: NVENC).

### Захоплення з мінімальною затримкою
Принципи: (1) не копіювати зайвий раз, (2) коротка черга буферів (1–2 кадри), (3) брати **останній** кадр, а не перший із черги, (4) роздільна здатність — за задачею (детектору вистачає 640×480), (5) фіксована експозиція/підсилення — інакше автоекспозиція дає ривки.

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

### Виміряти затримку
«Glass-to-glass»: на екрані телефона секундомір із мілісекундами (або блимальний LED із таймером), камера дивиться на нього, програма показує кадр поруч — фото обох: різниця = затримка захоплення+обробка+виведення. Для передавання в GCS — те саме з екраном GCS. Типово: CSI + OpenCV локально 30–60 мс; USB MJPEG 60–120 мс; RTSP H.264 до QGC через Wi-Fi 150–300 мс (буферизація плеєра — головний внесок; у QGC і GStreamer-приймачі зменшувати `latency`).

FPS — рахувати за часом між кадрами, а не за заявленим; пропуски кадрів — за різницею номерів кадрів/timestamp.

### Потік у GCS
GStreamer на борту (Pi 4, апаратний H.264 через `v4l2h264enc`; Jetson — `nvv4l2h264enc`):
```bash
# UDP/RTP to the GCS (QGC: Video Source = UDP h.264, port 5600)
gst-launch-1.0 libcamerasrc ! video/x-raw,width=1280,height=720,framerate=30/1 \
  ! videoconvert ! v4l2h264enc extra-controls="controls,repeat_sequence_header=1,video_bitrate=2000000" \
  ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=192.168.1.10 port=5600 sync=false
```
RTSP-сервер (QGC: RTSP URL): `gst-rtsp-server` (`test-launch` з examples) або `mediamtx` з тим самим пайплайном; RTSP зручний для кількох клієнтів і перепідключень, UDP — мінімальна затримка. Бітрейт — за бюджетом лінку (2–4 Мбіт/с для 720p30 на Wi-Fi/4G; для далеких лінків 0.5–1 Мбіт/с із 480p). Ключові кадри частіше (`iframe period` 1 с) — швидше відновлення після втрат.

### Камера й автопілот
Час кадру має зіставлятися з даними польоту: timestamp кадру (монотонний годинник) + MAVLink `SYSTEM_TIME`/`TIMESYNC` для синхронізації з FC; зміщення та орієнтація камери відносно IMU (`CAM_*`/extrinsics) — для будь-якої геометрії (VIO, стеження). Companion живиться від свого BEC (модуль про периферію), камера й шлейф — подалі від силових проводів.

{{diagram:glass-to-glass|Із чого складається затримка відеопотоку від світла на сенсорі до екрана (типові частки; вимірюй свій ланцюжок).}}

## practice
### Крок 1. Захоплення
USB або CSI: код вище, 640×480, фіксована експозиція; 30 с — середній FPS, пропуски кадрів. Порівняти BUFFERSIZE 1 і 4.

### Крок 2. Затримка glass-to-glass
Секундомір на телефоні → фото «екран vs вікно OpenCV» ×5 → середнє. Потім із вимкненим виведенням через `cv2.imshow` (лише захоплення + timestamp на кадрі) — оцінити внесок виведення.

Точніше й без фото — блимальний екран. Камера дивиться на вікно, яке програма перемикає між чорним і білим; затримка = момент, коли камера побачила зміну, мінус момент перемикання (той самий годинник, тому синхронізація не потрібна):
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
Камеру спрямувати так, щоб вікно займало майже весь кадр; до результату входить і затримка самого монітора (5–20 мс) — для порівняння варіантів (USB проти CSI, MJPEG проти YUYV, BUFFERSIZE 1 проти 4) це не заважає.

### Крок 3. Потік у QGC
GStreamer UDP H.264 у QGC; затримка glass-to-glass до екрана GCS; бітрейт проти якості/затримки (2 Мбіт vs 8 Мбіт).

Порядок величин для налаштування: 1280×720 за 30 кадр/с і 2 Мбіт/с — у середньому ~8 КБ на кадр; ключовий кадр (I-frame) у 5–10 разів більший, і на слабкому каналі саме він приходить із запізненням або губиться. Звідси налаштування для низької затримки: короткий інтервал ключових кадрів (0.5–1 с), `config-interval=1` у `rtph264pay` (параметри потоку повторюються — приймач, що підключився пізніше, одразу починає декодувати), без B-кадрів.

### Крок 4. RTSP
mediamtx або gst-rtsp-server; підключитися з QGC і VLC одночасно. Лабораторна: FPS виміряно, затримку виміряно блимальним екраном (медіана та p95) для двох варіантів захоплення, RTSP у QGC, бітрейт та інтервал ключових кадрів обґрунтовано.

## diagnostics
- **Симптом:** затримка зростає з часом
  - Можлива причина: алгоритм повільніший за FPS — черга буферів накопичується.
  - Що зробити: BUFFERSIZE 1, брати останній кадр, знизити роздільну здатність/FPS, пропускати кадри.
- **Симптом:** «желе»/вигини під час руху
  - Можлива причина: rolling shutter + вібрації.
  - Що зробити: демпфування камери, global shutter, коротша експозиція.
- **Симптом:** у QGC потік смикається
  - Можлива причина: бітрейт вищий за пропускну здатність, втрати пакетів без ключових кадрів.
  - Що зробити: нижчий бітрейт, частіше iframe, перевірити Wi-Fi/бюджет.
- **Симптом:** CSI-камера не визначається
  - Можлива причина: шлейф/роз'єм, довжина, не ввімкнено overlay.
  - Що зробити: `rpicam-hello --list-cameras` (до Raspberry Pi OS Bookworm — `libcamera-hello`), коротший шлейф, конфіг `dtoverlay`.
- **Симптом:** автоекспозиція «блимає» під час нахилів
  - Можлива причина: AE реагує на небо/землю.
  - Що зробити: фіксована експозиція/підсилення або обмеження діапазону.

## references
- Raspberry Pi — Camera software (libcamera, picamera2) | https://raspberrypi.com/documentation/computers/camera_software.html | primary | A
- GStreamer — Documentation | https://gstreamer.freedesktop.org/documentation/ | secondary | B
- QGroundControl — Video settings (UDP/RTSP sources) | https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/settings_view/video.html | primary | A

## checklist
- Знаю різницю CSI/USB, rolling/global shutter і форматів
- Захоплення з чергою в 1 кадр і фіксованою експозицією
- FPS і glass-to-glass затримку виміряно
- Потік H.264 у QGC за UDP і RTSP працює
- Розумію, де втрачається час у ланцюжку і як зменшити затримку
