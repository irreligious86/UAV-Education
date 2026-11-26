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
Бортовий зір ся починає з кадру, котрий дійшов до програми вчасно. Модуль — про шлях камера → пам'ять → алгоритм → GCS: CSI проти USB, формати (MJPEG/YUV/H.264), захоплення в Python із мінімальною затримкою (libcamera/V4L2 через OpenCV або GStreamer), вимірювання реальної затримки та FPS, і передавання потоку в QGroundControl по RTSP/UDP через GStreamer з апаратним кодуванням. Лабораторна: кадри в OpenCV із вимірюванням FPS, RTSP-потік у QGC, виміряна затримка.

## theory
### Камери й інтерфейси
- **CSI** (Raspberry Pi Camera v2/v3, HQ; Jetson IMX219/IMX477): прямий інтерфейс до ISP, мінімальна затримка (1–2 кадри), висока частота (120 fps у низькій роздільній здатності), короткий шлейф (до ~30 см без підсилювача — на дроні то обмеження). Керування через libcamera (Pi) / Argus (Jetson).
- **USB (UVC)**: будь-яка вебкамера; затримка вища (буфери, USB-контролер), часто лише MJPEG на високих fps (декодування коштує CPU), зате кабель до 3–5 м і заміна камери без драйверів. Global shutter USB-камери (наприклад, на OV9281) — для шпаркого руху та VIO.
- **IP-камери/HDMI-захоплення**: для важких платформ; затримка 100+ мс — то для телеметрії операторові, не для контуру керування.
- **Затвор**: rolling (рядки в різний час — «желе» за вібрацій та шпаркого обертання; ламає VIO) проти global (вшиткий кадр нараз). Для навігації — global.
- **Формати**: YUV420 — сирий, дешево для алгоритмів; MJPEG — стиснутий, кожен кадр незалежний, декодувати на CPU; H.264/H.265 — для передавання, кодувати апаратно (Pi 4: H.264 до 1080p30; Jetson: NVENC).

{{diagram:camera-choice-tree|Выбор камеры начинается с вопроса, идёт ли кадр в контур: картинке оператору хватает IP-камеры со 100+ мс, навигации нужен global shutter, а CSI против USB решает длина кабеля — около 30 см против 3–5 м.}}

### Захоплення з мінімальною затримкою
Принципи: (1) не копіювати зайвий раз, (2) коротка черга буферів (1–2 кадри), (3) брати **останній** кадр, а не перший із черги, (4) роздільна здатність — за задачею (детекторові вистачить 640×480), (5) фіксована експозиція/підсилення — бо інакше автоекспозиція дає ривки.

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
«Glass-to-glass»: на екрані телефона секундомір із мілісекундами (або блимальний LED із таймером), камера дивить ся на нього, програма показує кадр поруч — фото обох: різниця = затримка захоплення+обробка+виведення. Для передавання в GCS — те саме з екраном GCS. Типово: CSI + OpenCV локально 30–60 мс; USB MJPEG 60–120 мс; RTSP H.264 до QGC через Wi-Fi 150–300 мс (буферизація плеєра — головний внесок; у QGC і GStreamer-приймачі зменшувати `latency`).

FPS — рахувати за часом між кадрами, а не за тим, шо заявлено; пропуски кадрів — за різницею номерів кадрів/timestamp.

### Потік у GCS
GStreamer на борту (Pi 4, апаратний H.264 через `v4l2h264enc`; Jetson — `nvv4l2h264enc`):
```bash
# UDP/RTP to the GCS (QGC: Video Source = UDP h.264, port 5600)
gst-launch-1.0 libcamerasrc ! video/x-raw,width=1280,height=720,framerate=30/1 \
  ! videoconvert ! v4l2h264enc extra-controls="controls,repeat_sequence_header=1,video_bitrate=2000000" \
  ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=192.168.1.10 port=5600 sync=false
```
RTSP-сервер (QGC: RTSP URL): `gst-rtsp-server` (`test-launch` з examples) або `mediamtx` з тим самим пайплайном; RTSP файний для кількох клієнтів і перепідключень, UDP — мінімальна затримка. Бітрейт — за бюджетом лінку (2–4 Мбіт/с для 720p30 на Wi-Fi/4G; для далеких лінків 0.5–1 Мбіт/с із 480p). Ключові кадри частіше (`iframe period` 1 с) — шпаркіше відновлення після втрат.

### Камера й автопілот
Час кадру мусить ся зіставляти з даними польоту: timestamp кадру (монотонний годинник) + MAVLink `SYSTEM_TIME`/`TIMESYNC` для синхронізації з FC; зміщення та орієнтація камери відносно IMU (`CAM_*`/extrinsics) — для будь-якої геометрії (VIO, стеження). Companion живить ся від свого BEC (модуль про периферію), а камеру й шлейф пантруй подалі від силових дротів.

{{diagram:glass-to-glass|Із чого ся складає затримка відеопотоку від світла на сенсорі до екрана (типові частки; вимірюй свій ланцюжок).}}

{{diagram:camera-motion-blur|Смаз растёт линейно с экспозицией, но вращение 90°/с смазывает в восемь раз сильнее, чем полёт 10 м/с на высоте 50 м: при 1/500 с это 5.3 px против 0.7 px.}}

## practice
### Крок 1. Захоплення
USB або CSI: код вище, 640×480, фіксована експозиція; 30 с — середній FPS, пропуски кадрів. Порівняти BUFFERSIZE 1 і 4.

### Крок 2. Затримка glass-to-glass
Секундомір на телефоні → фото «екран vs вікно OpenCV» ×5 → середнє. Потім із вимкненим виведенням через `cv2.imshow` (лише захоплення + timestamp на кадрі) — оцінити внесок виведення.

Точніше й без фото — блимальний екран. Камера дивить ся на вікно, котре програма перемикає між чорним і білим; затримка = момент, коли камера побачила зміну, мінус момент перемикання (той самий годинник, тож синхронізація не треба):
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
Камеру наставити так, аби вікно займало майже цілий кадр; до результату входить і затримка самого монітора (5–20 мс) — для порівняння варіантів (USB проти CSI, MJPEG проти YUYV, BUFFERSIZE 1 проти 4) то не заважає.

### Крок 3. Потік у QGC
GStreamer UDP H.264 у QGC; затримка glass-to-glass до екрана GCS; бітрейт проти якості/затримки (2 Мбіт vs 8 Мбіт).

Порядок величин для налаштування: 1280×720 за 30 кадр/с і 2 Мбіт/с — у середньому ~8 КБ на кадр; ключовий кадр (I-frame) у 5–10 разів більший, і на слабкому каналі якраз він приходить із запізненням або губить ся. Звідси налаштування для низької затримки: короткий інтервал ключових кадрів (0.5–1 с), `config-interval=1` у `rtph264pay` (параметри потоку ся повторюють — приймач, шо підключив ся пізніше, зара починає декодувати), без B-кадрів.

### Крок 4. RTSP
mediamtx або gst-rtsp-server; підключити ся з QGC і VLC нараз. Лабораторна: FPS виміряно, затримку виміряно блимальним екраном (медіана та p95) для двох варіантів захоплення, RTSP у QGC, бітрейт та інтервал ключових кадрів обґрунтовано.

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

## diagnostics
- **Симптом:** затримка росте з часом
  - Можлива причина: алгоритм повільніший за FPS — черга буферів ся накопичує.
  - Що зробити: BUFFERSIZE 1, брати останній кадр, знизити роздільну здатність/FPS, пропускати кадри.
- **Симптом:** «желе»/вигини під час руху
  - Можлива причина: rolling shutter + вібрації.
  - Що зробити: демпфування камери, global shutter, коротша експозиція.
- **Симптом:** у QGC потік смикає ся
  - Можлива причина: бітрейт вищий за пропускну здатність, втрати пакетів без ключових кадрів.
  - Що зробити: нижчий бітрейт, частіше iframe, перевірити Wi-Fi/бюджет.
- **Симптом:** CSI-камера не визначає ся
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
- Потік H.264 у QGC по UDP і RTSP працює
- Розумію, де губить ся час у ланцюжку і як зменшити затримку
