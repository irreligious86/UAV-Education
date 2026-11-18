---
id: comp-jetson-nano
title: "Jetson Nano как компаньон: что он может, чего нет и как выжать максимум"
level: L2
readingTime: 50 мин
firmware: ArduPilot 4.7 (сверено с 4.7.2; лабораторная снята на 4.6.3) · PX4 1.17 (сверено с v1.17.0) · JetPack 4.6.6 / 6.2
status: published
added: 2026-11-14
tags:
  - Jetson Nano
  - Jetson Orin Nano
  - TensorRT
  - GStreamer
  - tegrastats
  - companion
related:
  - comp-intro
  - comp-raspberry
  - px4-companion-jetson
  - per-camera
  - per-edge-ml
  - ap-companion
  - mav-routing
next:
  - per-edge-ml
---

## summary
«Jetson Nano» в магазине — это две разные платы: оригинальный Nano 2019 года (Maxwell, 4 ГБ, JetPack 4, снят с поддержки) и Jetson Orin Nano (Ampere, 8 ГБ, JetPack 6, режим Super). Модуль честно разбирает обе: что каждая считает и чего не считает, сколько реально ест и почему 5 В — главная ловушка, как греется и троттлит, какие камеры и видеоконвейер брать, чем отличается стек инференса, как подключить UART к полётнику и поднять всё как сервис. Jetson в курсе нет, поэтому все цифры по железу — из документации NVIDIA и опубликованных бенчмарков со ссылками, а не из наших замеров. Лабораторная без железа: парсер строки `tegrastats` и мост «здоровье companion → MAVLink», который в SITL пишет температуру и загрузку в лог полётника как `NAMED_VALUE_FLOAT`. Потом — порядок переноса на настоящую плату.

## theory
### Две платы под одним именем
Граница ответственности та же, что в модуле «Companion: зачем и где граница»: полётник летит и возвращается сам, Jetson только смотрит и советует.

| | Jetson Nano (2019) | Jetson Orin Nano 8 ГБ (Super) |
|---|---|---|
| CPU | 4 × Cortex-A57, 1.43 ГГц | 6 × Cortex-A78AE, 1.7 ГГц |
| GPU | Maxwell, 128 ядер, 472 GFLOPS, без тензорных ядер | Ampere, 1024 ядра, 32 тензорных, 67 TOPS |
| Память | 4 ГБ LPDDR4, общая для CPU и GPU | 8 ГБ LPDDR5, общая |
| Режимы мощности | 10 Вт (MAXN), 5 Вт | 15 Вт, 25 Вт, MAXN_SUPER (без Super-конфигурации: 15 и 7 Вт) |
| Аппаратный кодер | есть: 4Kp30 или 4 × 1080p30, H.264/H.265 | **нет NVENC**: 1080p30 программно, ≈ 2 ядра CPU |
| Система | JetPack 4.6.6, L4T 32.7.6, Ubuntu 18.04, ядро 4.9 | JetPack 6.2, L4T 36.4.3, Ubuntu 22.04 |
| CUDA / TensorRT | 10.2 / 8.2.1 | 12.6 / 10.3 |
| Питание devkit | 5 В: micro-USB 2 А или гнездо 4 А | гнездо 9–20 В (в комплекте 19 В) |
| Модуль | 69.6 × 45 мм, SO-DIMM 260 | тот же форм-фактор |
| Статус | модуль выпускается до января 2027; devkit снят | модуль до января 2032 |

Что значит «снят с поддержки» на практике. JetPack 4.6.6 (22 ноября 2024) — последний в серии: критических обновлений больше не будет, JetPack 5/6 на Nano не существует. Ubuntu 18.04 — это Python 3.6, а современный `ultralytics` требует более нового Python, поэтому на Nano его запускают в готовом контейнере `ultralytics/ultralytics:latest-jetson-jetpack4`. Для TensorRT 8.x Q-engineering экспортирует ONNX с `opset=11`; DeepStream — 6.0.1, не новее. Итог: Nano годится, если он уже лежит в ящике и задача — один небольшой детектор; покупать его под новый проект незачем. Про Orin на PX4 — отдельный модуль «PX4 + Jetson Orin».

### Режимы мощности: nvpmodel и jetson_clocks
`nvpmodel` задаёт потолок: сколько ядер включено и максимальные частоты CPU/GPU. `sudo nvpmodel -q` — текущий режим, `sudo nvpmodel -m <ID>` — переключить.

| Плата | Режим | ID | Ядер CPU | CPU max, МГц | GPU max, МГц |
|---|---|---|---|---|---|
| Nano | MAXN (10 Вт) | 0 | 4 | 1479 | 921.6 |
| Nano | 5 Вт | 1 | 2 | 918 | 640 |
| Orin Nano 8 ГБ Super | 15 Вт | 0 | 6 | 1497.6 | 612 |
| Orin Nano 8 ГБ Super | 25 Вт (по умолчанию) | 1 | 6 | 1344 | 918 |
| Orin Nano 8 ГБ Super | MAXN_SUPER | 2 | 6 | 1728 | 1020 |

«10 Вт» у Nano — бюджет только шин CPU и GPU, а не всей платы. `jetson_clocks` прижимает частоты CPU, GPU и памяти к максимуму текущего режима: задержка стабильнее, расход выше; вентилятор он с релиза 32.4 сам не включает (`jetson_clocks --fan`). На Orin смена режима, меняющая маску TPC GPU, требует перезагрузки — `nvpmodel` сам предложит её. В режиме 5 Вт Nano теряет два ядра и треть частоты GPU — детектор, mavlink-router и кодер начинают делить два ядра.

### Питание: сколько ест на самом деле и ловушки 5 В
Реальные строки `tegrastats` с форума NVIDIA (Jetson Nano, поле `POM_5V_IN` — вход 5 В, мВт): с работающей CSI-камерой без нагрузки — 2.9 Вт; под TensorRT — пик 7.7 Вт при среднем 4.5 Вт. Плата devkit добавляет 0.5–1.25 Вт, USB-периферия — свои ватты. Бюджет для BEC: 10 Вт модуль + 1.25 Вт плата + камера и USB Wi-Fi/LTE ≈ 15 Вт → 3 А; BEC берём на 5 А. Orin Nano в простое — около 4 Вт (ответ сотрудника NVIDIA на форуме; у автора темы devkit в режиме 25 Вт по умолчанию брал 6.1 Вт), потолок — выбранный режим.

Ловушки Nano:
- Модулю нужно **4.75–5.25 В** на входе, и devkit ждёт именно 5 В: «5.3 В» с регулируемого BEC или просадка до 4.6 В — оба за пределами.
- micro-USB рассчитан на 2 А. Гнездо 5.5 × 2.1 мм — на 4 А, но работает только с перемычкой **J48**; без неё плата питается от micro-USB.
- Пины 2 и 4 гребёнки J41 принимают по 2.5 А (итого 5 А) — удобно для борта, но это прямой вход 5 В.
- Падение на проводе: U = U_BEC − I·(2·L·r + R_разъёма). Метровый micro-USB 28 AWG (0.213 Ом/м, разъём принят 0.10 Ом): R = 0.53 Ом — при 1.54 А (7.7 Вт) на плате 4.19 В, порог 4.75 В пройден уже на 0.48 А. Короткий 0.3 м 24 AWG: 4.77 В при 1.54 А и 4.55 В при 3 А. Гнездо, 0.3 м 20 AWG (разъём 0.03 Ом): 4.85 В при 3 А.

{{diagram:chart-jetson-brownout|При 5.0 В на BEC метровый micro-USB роняет вход Jetson Nano ниже 4.75 В уже на 0.5 А; короткая пара 20 AWG в гнездо держит 4.8 В до 4 А.}}

Orin Nano devkit принимает 9–20 В: 4S (до 16.8 В) формально в диапазоне, 3S под нагрузкой проседает к 9–10 В и ниже — ставь стабилизированные 12 В. Питание любой платы — от отдельного BEC с общей землёй с полётником, как в модуле «Raspberry Pi + ArduPilot».

Цена в полёте. Квадрокоптер 2.0 кг висит на 300 Вт, батарея 4S 5 А·ч, полезные 80 % = 59.2 Вт·ч → 11.84 мин. Добавляем только 10 Вт: 59.2 / 310 → 11.46 мин (−3.2 %). Добавляем ещё и 200 г (плата devkit 77 г + модуль с радиатором 61 г + BEC, камера, крепёж; мощность висения ∝ m^1.5 → 346 Вт): 9.97 мин (−15.8 %). Масса стоит впятеро дороже ватт — поэтому на борт ставят модуль на компактной несущей плате, а не devkit.

### Тепло и троттлинг
| Плата | Программный троттлинг | Аппаратный троттлинг | Выключение |
|---|---|---|---|
| Nano, CPU | 97.0 °C | 100.5 °C | 102.0 °C (программное), 102.5 °C (аппаратное) |
| Nano, GPU | 97.5 °C | 101.0 °C | 102.5 / 103.0 °C |
| Orin Nano, CPU/GPU/SoC | 99.0 °C | 103.0 °C | 104.5 / 105.0 °C |

На Nano вентилятор включается при 51 °C (средневзвешенная зона CPU+GPU). Троттлинг не пишет ошибок: падает частота GPU в поле `GR3D_FREQ`, растёт время инференса, контур слежения получает устаревшие координаты (модуль «ML на борту»). Перегрев до 102 °C — это выключение companion в воздухе. Отсюда правило: температура и частота GPU идут в телеметрию и в лог полётника, предупреждение — с запасом (в лабораторной 85 °C).

### Несущие платы и масса
Devkit Nano: модуль 15 г, модуль с радиатором 61 г (ответ сотрудника NVIDIA на форуме), плата 77 г — пересчёт пользователя форума по elinux (138 − 61); итого 138 г без проводов, не из спецификации. Orin Nano devkit по Carrier Board Specification: несущая плата 100 × 79 мм, devkit в сборе 103 × 90.5 × 34.8 мм и 175 г; всё равно взвесь свой. В списке companion-плат ArduPilot есть несущие под модули Jetson: ARK Jetson PAB Carrier, Holybro Pixhawk Jetson Baseboard, Aerium Lumen. Разъём у Nano и Orin Nano одинаковый, но совместимость конкретной платы с конкретным модулем проверяй по её документации.

### Камеры и видео
- **CSI**: IMX219 (Raspberry Pi Camera v2, 8 Мп) работает на Nano из коробки; IMX477 (HQ, 12.3 Мп) — с JetPack 4.6 через Jetson-IO (`sudo /opt/nvidia/jetson-io/jetson-io.py`). На Orin Nano разъёмы 22-контактные: для 15-контактного шлейфа нужен переходной кабель.
- **USB**: `v4l2src`; MJPEG приходится декодировать, это лишние десятки миллисекунд (модуль «Камеры и видеопоток на companion»).
- **Захват**: `nvarguscamerasrc` отдаёт кадры в памяти GPU (`memory:NVMM`), без копирования в CPU.
- **Кодирование на Nano** — аппаратное, `nvv4l2h264enc` (старый `omxh264enc` из gst-omx объявлен устаревшим). Для малой задержки: постоянный битрейт, без B-кадров, частый ключевой кадр, SPS/PPS перед каждым IDR:

```bash
gst-launch-1.0 nvarguscamerasrc sensor-id=0 \
  ! 'video/x-raw(memory:NVMM),width=1280,height=720,framerate=60/1,format=NV12' \
  ! nvv4l2h264enc bitrate=4000000 control-rate=1 iframeinterval=30 insert-sps-pps=true \
      maxperf-enable=true preset-level=1 \
  ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=192.168.1.10 port=5600 sync=false
```

- **На Orin Nano** кодера нет: вместо `nvv4l2h264enc` ставят `nvvidconv ! 'video/x-raw,format=I420' ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=4000`. В документации NVIDIA `ultrafast` на потоке с камеры 30 к/с даёт 30.66 к/с при 38 % загрузки на ядро (все шесть ядер) — эти ядра уже не достанутся постобработке детектора.

Конвейеры на плате не запускались (Jetson нет): свойства кодера сверены с руководством Accelerated GStreamer, свойство `sensor-id` (оно же `sensor_id`) — по примерам JetsonHacks CSI-Camera; имя сенсора и режимы проверь по `gst-inspect-1.0 nvarguscamerasrc` и выводу камеры.

### Стек инференса и бенчмарки
Путь один: PyTorch → ONNX → **TensorRT engine**, собранный на той же плате (engine привязан к GPU и версии TensorRT — с ноутбука и с Orin на Nano он не переносится). В `ultralytics` — `model.export(format="engine", quantize=16)` для FP16 и `quantize=8, data=...` для INT8 с калибровкой на своих кадрах; старые флаги `half=True` и `int8=True` ещё принимаются. В тесте Q-engineering INT8 скорости не добавил, а mAP ухудшил (у Maxwell нет тензорных ядер); на Orin Nano Super INT8 сокращает время кадра на 17–39 % относительно FP16, но mAP у YOLO26n падает с 0.480 до 0.449. DeepStream — готовый конвейер «декодер → TensorRT → трекер → кодер» на GStreamer: 6.0.1 для JetPack 4.6.x, 7.1 для JetPack 6.1.

| Плата | Модель | Формат | мс/кадр | к/с | Источник |
|---|---|---|---|---|---|
| Raspberry Pi 5 | YOLO26n | PyTorch, CPU | 299.09 | 3.3 | Ultralytics, 8.4.108 |
| Raspberry Pi 5 | YOLO26n | NCNN, CPU | 67.03 | 14.9 | Ultralytics |
| Raspberry Pi 5 | YOLO26s | NCNN, CPU | 172.88 | 5.8 | Ultralytics |
| Jetson Nano | YOLOv8n | TensorRT FP16 | — | 19 | Q-engineering, C++ |
| Jetson Nano | YOLOv8s | TensorRT FP16 | — | 9.25 | Q-engineering |
| Jetson Nano | YOLOv8m и крупнее | TensorRT FP16 | — | нет данных | Q-engineering |
| Orin Nano Super | YOLO26n | PyTorch, GPU | 15.60 | 64 | Ultralytics, 8.4.33 |
| Orin Nano Super | YOLO26n | TensorRT FP16 | 4.57 | 219 | Ultralytics |
| Orin Nano Super | YOLO26n | TensorRT INT8 | 3.80 | 263 | Ultralytics |
| Orin Nano Super | YOLO26s | TensorRT FP16 | 7.17 | 139 | Ultralytics |

Читать таблицу осторожно: это чужие замеры, мы ничего из этого не запускали. Строки Ultralytics — только время инференса без захвата, предобработки и NMS, вход 640 px; Orin Nano Super у них на JetPack 6.1. Строки Q-engineering — к/с их C++-демо: что входит в замер и размер входа там не указаны. Модели разных поколений (YOLOv8 и YOLO26), режим `nvpmodel` ни в одном источнике не указан — сравнивать строки можно только по порядку величины. Вывод всё равно устойчив: Nano с TensorRT даёт на nano-модели 19 к/с — на уровне Pi 5 на одном CPU (14.9 к/с); Orin Nano быстрее на порядок. Собственный бенчмарк NVIDIA 2019 года для Nano (TensorRT FP16): SSD MobileNet-V2 300 × 300 — 39 к/с, Tiny YOLO v3 416 × 416 — 25 к/с.

### Что Nano тянет одновременно
Память общая: в форумной строке под TensorRT занято 3100 из 3957 МБ и ещё 535 МБ в swap — с рабочим столом. Первое действие — headless: `sudo systemctl set-default multi-user.target` (по руководству Ultralytics для Jetson это до ~865 МБ).

- **Реалистично** (оценка по таблице и памяти, не замер): один детектор n/s в FP16 на 10–20 к/с + захват CSI + аппаратный H.264 720p–1080p + mavlink-router + скрипт на pymavlink.
- **Не тянет** (тоже оценка): два детектора или детектор плюс VIO/SLAM; модели m и крупнее в реальном времени (s уже 9 к/с); ROS 2 с визуализацией на борту; всё, чему нужен свежий Python, PyTorch или Isaac ROS без контейнера.

На Orin Nano предел другой — нет кодера (видео на землю ест CPU) и 8 ГБ на всё.

### UART, MAVLink, ROS 2
- Гребёнка J41 Nano: пин 8 — TX, пин 10 — RX, пин 6 — GND; устройство `/dev/ttyTHS1`. Уровни **3.3 В, 5 В плата не терпит**; провод 5 В с TELEM-порта не подключать.
- На этом UART по умолчанию висит консоль: `sudo systemctl stop nvgetty && sudo systemctl disable nvgetty`, пользователя — в группу `dialout`.
- ArduPilot: `SERIAL2_PROTOCOL = 2` (MAVLink 2), `SERIAL2_BAUD = 921` (в SITL по умолчанию 57). PX4: `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard`, `SER_TEL2_BAUD = 921600`.
- Один UART — несколько потребителей: `mavlink-routerd -e 192.168.1.10:14550 /dev/ttyTHS1:921600`, локальные скрипты — к TCP 5760 (модуль «Маршрутизация и транспорт MAVLink»); на стенде хватит `mavproxy.py --master=/dev/ttyTHS1 --baudrate 921600`. Управление из кода — модуль «Companion + ArduPilot».
- ROS 2: для Ubuntu 18.04 нет бинарных пакетов актуальных дистрибутивов; рабочий путь на Nano — контейнеры `dustynv/ros:humble-ros-base-l4t-r32.7.1` (jetson-containers, нужен JetPack 4.6.1+). На Orin Nano с JetPack 6 Humble ставится из apt.

### Диск, headless, автозапуск, выключение
- Nano devkit грузится с microSD (минимум 32 ГБ UHS-1), слота под NVMe нет (M.2 только Key E, под Wi-Fi); с JetPack 4.5 ядро и корневую ФС можно грузить с USB-накопителя (release notes JetPack 4.5), но вставленная microSD имеет приоритет — у нас не проверено. У Orin Nano devkit два слота M.2 Key M под NVMe — логи и видео пиши туда.
- Первая настройка без монитора: питание в гнездо, micro-USB в ноутбук, `sudo screen /dev/ttyACM0 115200`.
- Автозапуск — `systemd`-юнит с `Type=notify`, `WatchdogSec` и `Restart=always` (шаг 4), как на Raspberry Pi.
- Выключение: до снятия батареи — `sudo shutdown -h now`; обрыв питания во время записи портит файловую систему. В MAVLink для этого есть `MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN` с `param2 = 2` (выключить бортовой компьютер) — в лабораторном скрипте не реализовано.

### Что выбрать
{{diagram:jetson-sizing-tree|Выбор от задачи: MAVLink и логика — Pi 5; один небольшой детектор на уже купленном Nano; детектор с трекером — Orin Nano; SLAM и несколько сетей — Orin NX и выше.}}

Pi 5 — 5 В 5 А, свежая система, детектор на CPU до ~15 к/с, аппаратного H.264-кодера тоже нет. Nano выигрывает у него только кодером и CSI-конвейером на GPU. Orin Nano — когда нужно больше 20 к/с, трекер или модель s/m.

### Место в системе

- **Получает:** питание от отдельного BEC с общей землёй (`el-power-design`); MAVLink с TELEM-порта на 921600 (`mav-routing`); кадры CSI- или USB-камеры (`per-camera`).
- **Отдаёт:** уставки и результаты зрения автопилоту (`ap-companion`); видео H.264 на землю; температуру и загрузку в лог полётника как `NAMED_VALUE_FLOAT`; свои ватты и граммы — в бюджет аппарата (`des-sizing`).
- **Если ошибиться здесь:** длинный тонкий провод 5 В → под нагрузкой вход Nano ниже 4.75 В, companion пропадает в воздухе; со стороны автопилота это таймаут уставок GUIDED (`ap-companion`). Перегрев → троттлинг без ошибок, инференс медленнее, контур слежения получает устаревшие координаты (`per-tracking`); ловится профилированием в `per-edge-ml`.

## practice
Основной путь — без Jetson: настоящие строки `tegrastats`, SITL ArduCopter 4.6.3 (`-I 5`), pymavlink 2.4.50. Всё ниже запускалось, вывод настоящий.

### Шаг 1. Образец tegrastats
`tegrastats_sample.txt`: строки 1–2 — реальные с форума NVIDIA (камера без нагрузки; TensorRT), строка 3 — **синтетика**: вторая строка, руками доведённая до программного троттлинга (97.5 °C, частоты срезаны). Замером она не является.

```
RAM 1698/3965MB (lfb 99x4MB) CPU [16%@921,10%@921,10%@921,11%@921] EMC_FREQ 0% GR3D_FREQ 0% PLL@32.5C CPU@36C PMIC@100C GPU@33.5C AO@42.5C thermal@34.75C POM_5V_IN 2915/2915 POM_5V_GPU 40/40 POM_5V_CPU 319/319
RAM 3100/3957MB (lfb 18x1MB) SWAP 535/4096MB (cached 22MB) IRAM 0/252kB(lfb 252kB) CPU [79%@1428,100%@1428,81%@1428,83%@1428] EMC_FREQ 22%@1600 GR3D_FREQ 99%@844 APE 25 PLL@44.5C CPU@48.5C PMIC@100C GPU@43.5C AO@51C thermal@46C POM_5V_IN 7700/4490 POM_5V_GPU 2408/523 POM_5V_CPU 1224/613
RAM 3100/3957MB (lfb 18x1MB) SWAP 535/4096MB (cached 22MB) CPU [95%@918,100%@918,97%@918,98%@918] EMC_FREQ 22%@1600 GR3D_FREQ 99%@537 PLL@93.5C CPU@97.5C PMIC@100C GPU@98C AO@99C thermal@97.75C POM_5V_IN 5200/4900 POM_5V_GPU 1600/900 POM_5V_CPU 700/650
```

Формат: `CPU [загрузка%@МГц]` по ядрам (`off` — ядро выключено), `GR3D_FREQ` — загрузка и частота GPU, `X@YC` — температуры зон, `POM_5V_IN a/b` — мгновенная и средняя мощность в мВт.

### Шаг 2. Парсер
`cc_health.py`, первая половина:

```python
#!/usr/bin/env python3
"""Companion health: tegrastats -> dict -> MAVLink HEARTBEAT + NAMED_VALUE_FLOAT + STATUSTEXT.
Jetson:  cc_health.py --link /dev/ttyTHS1 --baud 921600
No Jetson: cc_health.py --link tcp:127.0.0.1:5813 --replay tegrastats_sample.txt   (or --parse FILE)"""
import argparse, os, re, socket, subprocess, time

RE_RAM = re.compile(r"RAM (\d+)/(\d+)MB")
RE_CPU = re.compile(r"CPU \[([^\]]*)\]")
RE_CORE = re.compile(r"(\d+)%@(\d+)|off")
RE_GR3D = re.compile(r"GR3D_FREQ (\d+)%(?:@(\d+))?")
RE_TEMP = re.compile(r"([A-Za-z0-9_]+)@([\d.]+)C")
RE_PWR = re.compile(r"((?:POM_5V|VDD)_[A-Z_0-9]+) (\d+)(?:mW)?/(\d+)")


def parse_tegrastats(line):
    """One tegrastats line -> flat dict; a field missing on this board is simply absent."""
    d = {}
    if m := RE_RAM.search(line):
        d["ram_pct"] = round(100.0 * int(m[1]) / int(m[2]), 1)
    if m := RE_CPU.search(line):
        cores = [(int(a), int(b)) for a, b in RE_CORE.findall(m[1]) if a]      # 'off' cores skipped
        d["cpu_pct"] = round(sum(c[0] for c in cores) / max(1, len(cores)), 1)
        d["cpu_mhz"] = max((c[1] for c in cores), default=0)
        d["cores"] = len(cores)
    if m := RE_GR3D.search(line):
        d["gpu_pct"] = int(m[1])
        if m[2]:
            d["gpu_mhz"] = int(m[2])
    temps = {k: float(v) for k, v in RE_TEMP.findall(line)}
    temps.pop("PMIC", None)                    # PMIC@100C on Nano is a constant, not a reading
    hot = [temps[k] for k in ("CPU", "GPU", "cpu", "gpu", "tj") if k in temps]  # Nano: CPU@ GPU@; Orin: cpu@ gpu@ tj@
    d["t_max"] = max(hot or temps.values(), default=float("nan"))
    pwr = {k: int(a) for k, a, _ in RE_PWR.findall(line)}
    if (mw := pwr.get("POM_5V_IN") or pwr.get("VDD_IN")):                       # Nano / Orin total input, mW
        d["p_in_w"] = mw / 1000.0
    return d


def lines_replay(path, period, loop=True):
    while True:
        for line in open(path):
            if line.strip() and not line.startswith("#"):
                yield line.rstrip()
                time.sleep(period)
        if not loop:
            return


def lines_tegrastats(period):
    p = subprocess.Popen(["tegrastats", "--interval", str(int(period * 1000))], stdout=subprocess.PIPE, text=True)
    yield from (line.rstrip() for line in p.stdout)
```

`python3 cc_health.py --parse tegrastats_sample.txt`:

```
{'ram_pct': 42.8, 'cpu_pct': 11.8, 'cpu_mhz': 921, 'cores': 4, 'gpu_pct': 0, 't_max': 36.0, 'p_in_w': 2.915}
{'ram_pct': 78.3, 'cpu_pct': 85.8, 'cpu_mhz': 1428, 'cores': 4, 'gpu_pct': 99, 'gpu_mhz': 844, 't_max': 48.5, 'p_in_w': 7.7}
{'ram_pct': 78.3, 'cpu_pct': 97.5, 'cpu_mhz': 918, 'cores': 4, 'gpu_pct': 99, 'gpu_mhz': 537, 't_max': 98.0, 'p_in_w': 5.2}
```

Проверь руками: 1698 / 3965 = 42.8 %; среднее (79 + 100 + 81 + 83) / 4 = 85.8 %; `PMIC@100C` отброшен — на Nano это константа, без этой строки `t_max` был бы 100 °C всегда. В первой строке у `GR3D_FREQ` нет частоты — поле `gpu_mhz` просто отсутствует, и мост его не шлёт. Признак троттлинга в третьей строке — не температура сама по себе, а 537 МГц при 99 % загрузки GPU против 844 МГц во второй. Формат Orin (зоны `cpu@`, `gpu@`, `tj@` строчными, `VDD_IN 5171mW/5171mW`) в выражениях учтён, но проверен только на строке, составленной по сообщениям форума, не на плате.

### Шаг 3. Мост в MAVLink и SITL
Вторая половина `cc_health.py`. Мост представляется отдельным компонентом той же системы: sysid полётника, compid 191 (`MAV_COMP_ID_ONBOARD_COMPUTER`), свой `HEARTBEAT` раз в секунду. Имя в `NAMED_VALUE_FLOAT` — не длиннее 10 символов.

```python
def sd_notify(msg):
    """READY=1 / WATCHDOG=1 for systemd Type=notify; no-op when started by hand."""
    if addr := os.environ.get("NOTIFY_SOCKET"):
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect("\0" + addr[1:] if addr[0] == "@" else addr)
            s.sendall(msg.encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--link", default="tcp:127.0.0.1:5813")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--replay")
    ap.add_argument("--parse")
    ap.add_argument("--period", type=float, default=1.0)
    ap.add_argument("--t-warn", type=float, default=85.0)
    ap.add_argument("--count", type=int, default=0)
    a = ap.parse_args()
    if a.parse:
        for line in lines_replay(a.parse, 0, loop=False):
            print(parse_tegrastats(line))
        return

    from pymavlink import mavutil
    mav = mavutil.mavlink
    m = mavutil.mavlink_connection(a.link, baud=a.baud, source_system=1,           # the vehicle's sysid,
                                   source_component=mav.MAV_COMP_ID_ONBOARD_COMPUTER)  # compid 191
    hb = m.wait_heartbeat(timeout=30)
    print(f"FC heartbeat: sysid={hb.get_srcSystem()} compid={hb.get_srcComponent()} autopilot={hb.autopilot}")
    sd_notify("READY=1")
    t0, n, warned = time.monotonic(), 0, False
    for line in lines_replay(a.replay, a.period) if a.replay else lines_tegrastats(a.period):
        d = parse_tegrastats(line)
        ms = int((time.monotonic() - t0) * 1000)
        m.mav.heartbeat_send(mav.MAV_TYPE_ONBOARD_CONTROLLER, mav.MAV_AUTOPILOT_INVALID, 0, 0, mav.MAV_STATE_ACTIVE)
        for name, key in (("CC_TEMP", "t_max"), ("CC_CPU", "cpu_pct"), ("CC_GPU", "gpu_pct"),
                          ("CC_RAM", "ram_pct"), ("CC_PWR_W", "p_in_w"), ("CC_GPU_MHZ", "gpu_mhz")):
            if key in d and d[key] == d[key]:                                      # skip absent and NaN
                m.mav.named_value_float_send(ms, name.encode(), float(d[key]))     # name: at most 10 chars
        hot = d["t_max"] >= a.t_warn
        if hot and not warned:                                                     # once per overheat episode
            m.mav.statustext_send(mav.MAV_SEVERITY_WARNING, f"CC hot {d['t_max']:.1f}C gpu {d.get('gpu_mhz', 0)}MHz".encode())
        warned = hot
        sd_notify("WATCHDOG=1")
        n += 1
        print(f"[{n}] T={d['t_max']}C cpu={d.get('cpu_pct')}% gpu={d.get('gpu_pct')}%@{d.get('gpu_mhz')} "
              f"ram={d.get('ram_pct')}% P={d.get('p_in_w')}W")
        if a.count and n >= a.count:
            break


if __name__ == "__main__":
    main()
```

SITL: SERIAL0 (TCP 5810) — «наземка», SERIAL2 (TCP 5813) — «TELEM2», куда на борту приходит UART Jetson; `SERIAL2_PROTOCOL` в SITL уже 2. Вспомогательный `sitl_tools.py`: `logon` ставит `LOG_DISARMED = 1` (лог без арминга), `gcs` считает на порту наземки сообщения от compid 191, `nval` читает DataFlash.

```python
"""SITL helpers: sitl_tools.py logon | gcs SECONDS | nval LOGFILE"""
import sys, time
from pymavlink import mavutil

if sys.argv[1] == "nval":                       # NVAL rows and companion STATUSTEXT from the DataFlash log
    log, n = mavutil.mavlink_connection(sys.argv[2]), 0
    while (msg := log.recv_match(type=["NVAL", "MSG"])) is not None:
        if msg.get_type() == "MSG":
            if "CC hot" in msg.Message:
                print(f"MSG  TimeUS={msg.TimeUS} {msg.Message}")
            continue
        n += 1
        if n <= 6 or msg.Name == "CC_GPU_MHZ":
            print(f"NVAL TimeUS={msg.TimeUS} TimeBootMS={msg.TimeBootMS} Name={msg.Name:<10} "
                  f"Value={msg.Value:.2f} SSys={msg.SSys} SCom={msg.SCom}")
    print("NVAL rows:", n)
    sys.exit()

m = mavutil.mavlink_connection("tcp:127.0.0.1:5810", source_system=255)      # SERIAL0 of SITL -I 5
m.wait_heartbeat()
m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
if sys.argv[1] == "logon":                      # log while disarmed
    m.mav.param_set_send(1, 1, b"LOG_DISARMED", 1, mavutil.mavlink.MAV_PARAM_TYPE_INT8)
    while (p := m.recv_match(type="PARAM_VALUE", blocking=True, timeout=5)) and p.param_id != "LOG_DISARMED":
        pass
    print(p.param_id, p.param_value)
else:                                           # gcs: count what arrives from the companion, compid 191
    t_end, seen = time.time() + float(sys.argv[2]), {}
    while time.time() < t_end:
        msg = m.recv_match(blocking=True, timeout=0.5)
        if msg is None or msg.get_srcComponent() != 191:
            continue
        t = msg.get_type()
        seen[t] = seen.get(t, 0) + 1
        if t == "NAMED_VALUE_FLOAT" and seen[t] <= 3:
            print(f"{t}: name={msg.name} value={msg.value:.2f} time_boot_ms={msg.time_boot_ms}")
        if t == "STATUSTEXT":
            print(f"{t}: severity={msg.severity} text={msg.text}")
    print("from compid 191:", seen)
```

```bash
mkdir sitl5 && cd sitl5
/tmp/ardupilot/build/sitl/bin/arducopter -w -S -I 5 --model + --speedup 1 \
  --home -35.363261,149.165230,584,353 --defaults /tmp/ardupilot/Tools/autotest/default_params/copter.parm &
cd ../lab
python3 sitl_tools.py logon                    # -> LOG_DISARMED 1.0
python3 sitl_tools.py gcs 10 > gcs_out.txt &
python3 cc_health.py --link tcp:127.0.0.1:5813 --replay tegrastats_sample.txt --count 6
python3 sitl_tools.py nval ../sitl5/logs/00000001.BIN      # after stopping SITL
```

Вывод моста:

```
FC heartbeat: sysid=1 compid=1 autopilot=3
[1] T=36.0C cpu=11.8% gpu=0%@None ram=42.8% P=2.915W
[2] T=48.5C cpu=85.8% gpu=99%@844 ram=78.3% P=7.7W
[3] T=98.0C cpu=97.5% gpu=99%@537 ram=78.3% P=5.2W
[4] T=36.0C cpu=11.8% gpu=0%@None ram=42.8% P=2.915W
[5] T=48.5C cpu=85.8% gpu=99%@844 ram=78.3% P=7.7W
[6] T=98.0C cpu=97.5% gpu=99%@537 ram=78.3% P=5.2W
```

Сторона наземки (`gcs_out.txt`):

```
NAMED_VALUE_FLOAT: name=CC_TEMP value=36.00 time_boot_ms=0
NAMED_VALUE_FLOAT: name=CC_CPU value=11.80 time_boot_ms=0
NAMED_VALUE_FLOAT: name=CC_GPU value=0.00 time_boot_ms=0
STATUSTEXT: severity=4 text=CC hot 98.0C gpu 537MHz
STATUSTEXT: severity=4 text=CC hot 98.0C gpu 537MHz
from compid 191: {'HEARTBEAT': 6, 'NAMED_VALUE_FLOAT': 34, 'STATUSTEXT': 2}
```

34 = 6 циклов × 6 полей − 2 (в строках без частоты GPU поле `CC_GPU_MHZ` не отправлялось). Полётник переслал сообщения companion на SERIAL0 сам — это штатная маршрутизация ArduPilot. И главное — DataFlash (`sitl_tools.py nval`, сообщения `NVAL` и `MSG`):

```
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_TEMP    Value=36.00 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_CPU     Value=11.80 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_GPU     Value=0.00 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_RAM     Value=42.80 SSys=1 SCom=191
NVAL TimeUS=5229574 TimeBootMS=0 Name=CC_PWR_W   Value=2.91 SSys=1 SCom=191
NVAL TimeUS=6234172 TimeBootMS=1000 Name=CC_TEMP    Value=48.50 SSys=1 SCom=191
NVAL TimeUS=6234172 TimeBootMS=1000 Name=CC_GPU_MHZ Value=844.00 SSys=1 SCom=191
NVAL TimeUS=7234605 TimeBootMS=2001 Name=CC_GPU_MHZ Value=537.00 SSys=1 SCom=191
MSG  TimeUS=7234605 SRC=1/191:CC hot 98.0C gpu 537MHz
NVAL TimeUS=9237137 TimeBootMS=4002 Name=CC_GPU_MHZ Value=844.00 SSys=1 SCom=191
NVAL TimeUS=10236737 TimeBootMS=5002 Name=CC_GPU_MHZ Value=537.00 SSys=1 SCom=191
MSG  TimeUS=10236737 SRC=1/191:CC hot 98.0C gpu 537MHz
NVAL rows: 34
```

Что это даёт: температура и частота GPU companion лежат в одном логе с `ATT` и `CTUN` на общей оси `TimeUS` — после полёта видно, совпал ли срыв слежения с троттлингом. `TimeBootMS` — время скрипта, а не полётника; для привязки бери `TimeUS`. В PX4 то же сообщение попадает в uORB-топик `debug_key_value`; в ULog он пишется при включённом бите 5 (Debug) в `SDLOG_PROFILE`, а до наземки доходит при `MAV_1_FORWARD = 1` (на PX4 SITL не проверялось).

### Шаг 4. Юнит со сторожевым таймером
`/etc/systemd/system/cc-health.service` (синтаксис проверен `systemd-analyze verify`; на плате не запускался):

```ini
[Unit]
Description=Companion health to MAVLink (tegrastats)
After=mavlink-router.service
Wants=mavlink-router.service

[Service]
Type=notify
NotifyAccess=main
ExecStart=/usr/bin/python3 /opt/uav/cc_health.py --link tcp:127.0.0.1:5760
WatchdogSec=10
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

`READY=1` уходит после первого heartbeat полётника, `WATCHDOG=1` — на каждой строке `tegrastats`: зависнет `tegrastats` или порт — через 10 с systemd перезапустит сервис. Запиши в отчёт таблицу трёх строк из шага 2 и число `NVAL` из своего лога.

### Переход на реальное железо
Пропеллеры сняты до последнего пункта; полётник на столе, питание Jetson — от лабораторного блока или того BEC, что пойдёт на борт.

1. **Прошивка.** Nano: образ JetPack 4.6.x на microSD ≥ 32 ГБ, первая настройка по micro-USB (`/dev/ttyACM0`), питание в гнездо с перемычкой J48. Orin Nano: JetPack 6.2 по руководству devkit, затем `sudo nvpmodel -q`. Сразу — `sudo systemctl set-default multi-user.target`, запиши свободную память до и после (`free -m`).
2. **Питание и тепло по режимам.** Для каждого режима `nvpmodel` (Nano: 0 и 1; Orin: 0, 1, 2): `sudo nvpmodel -m N`, `tegrastats --interval 1000 --logfile mode_N.log`, 20 минут детектора (контейнер Ultralytics, `yolo predict` на видеофайле с engine FP16) в том корпусе, в котором плата полетит. Мультиметром — напряжение на пинах 2/6 гребёнки под нагрузкой. В таблицу: к/с в первую и на двадцатой минуте, средняя и пиковая мощность на входе, максимум температуры, минимум частоты GPU, минимум напряжения.
3. **UART-петля.** Полётник не подключён, перемычка между пинами 8 и 10, `nvgetty` выключен: отправленная на `/dev/ttyTHS1` строка на 921600 бод должна вернуться (скрипт петли — в модуле «PX4 + Jetson Orin», шаг 2).
4. **MAVLink к полётнику.** TX→RX, RX→TX, GND; 5 В с TELEM не подключать. `SERIAL2_PROTOCOL = 2`, `SERIAL2_BAUD = 921`, перезагрузка полётника. `python3 cc_health.py --link /dev/ttyTHS1 --baud 921600 --count 60` — уже с настоящим `tegrastats`; затем mavlink-router и юнит из шага 4.
5. **Отказы.** Заморозь сервис (`sudo kill -STOP <PID>`) — через 10 с перезапуск. Выдерни питание Jetson: полётник продолжает работать, наземка видит пропажу heartbeat компонента 191. Десять холодных стартов подряд — сервис поднимается сам.
6. **С пропеллерами** — только висение на привязи или в сетке, 5 минут, с детектором под нагрузкой; после — `NVAL` в логе.

Критерии железа: напряжение на плате ≥ 4.75 В в пике (Nano); максимум температуры за 20 минут минимум на 10 °C ниже программного троттлинга (≤ 87 °C Nano, ≤ 89 °C Orin Nano); к/с на двадцатой минуте не ниже 90 % от первой; частота GPU при загрузке ≥ 90 % на двадцатой минуте не ниже, чем на первой; UART-петля 100 из 100 строк; `NVAL` с `SCom = 191` в логе полётника идут с частотой 1 Гц без пропусков дольше 3 с.

Лабораторная засчитывается, когда: (SITL) парсер даёт на трёх строках образца те же значения, что выше, и ты можешь пересчитать `ram_pct` и `cpu_pct` руками; мост в SITL даёт `NVAL` с `SCom = 191` в DataFlash, `HEARTBEAT` компонента 191 и `STATUSTEXT` на стороне наземки, число `NVAL` объяснено; посчитан бюджет питания своей сборки и напряжение на плате по формуле для своего провода; (железо, если плата есть) заполнена таблица режимов `nvpmodel` и выполнены критерии железа выше.

## diagnostics
- **Симптом:** Nano выключается или перезагружается при старте инференса, в простое работает
  - Возможная причина: питание через micro-USB или длинный тонкий провод; на входе меньше 4.75 В под током 1.5–3 А.
  - Что сделать: гнездо или пины 2/4 с перемычкой J48 по назначению, пара 20 AWG до 30 см, BEC 5.0–5.25 В на 5 А; измерить напряжение на гребёнке под нагрузкой.
  - Что видно в логе: `NVAL CC_PWR_W` обрывается на пике, heartbeat компонента 191 пропадает.
- **Симптом:** гнездо питания подключено, плата не стартует
  - Возможная причина: нет перемычки J48 — вход переключён на micro-USB.
  - Что сделать: поставить перемычку; проверить полярность штекера (плюс в центре).
- **Симптом:** к/с детектора падает через 5–10 минут, ошибок нет
  - Возможная причина: программный троттлинг около 97 °C (Nano) или 99 °C (Orin Nano), закрытый корпус, вентилятор не включён.
  - Что сделать: радиатор с обдувом, `jetson_clocks --fan` на стенде, ниже режим `nvpmodel`, меньше модель или разрешение.
  - Что видно в логе: `CC_GPU_MHZ` падает при `CC_GPU` около 99 %, `CC_TEMP` у порога.
- **Симптом:** `Killed` при сборке engine или при запуске второго процесса с моделью
  - Возможная причина: кончились 4 ГБ общей памяти, рабочий стол занимает сотни мегабайт.
  - Что сделать: headless-режим, swap на время сборки engine, одна модель, размер n/s.
- **Симптом:** на `/dev/ttyTHS1` мусор или «Permission denied»
  - Возможная причина: консоль `nvgetty` держит порт; пользователь не в `dialout`; скорость не совпадает с `SERIAL2_BAUD`.
  - Что сделать: выключить `nvgetty`, добавить группу, сверить скорость; проверить петлёй 8–10.
- **Симптом:** heartbeat полётника есть, а `NVAL` в логе нет
  - Возможная причина: лог не пишется без арминга (`LOG_DISARMED = 0`); мост шлёт с чужим sysid; на порту не MAVLink 2.
  - Что сделать: `LOG_DISARMED = 1` на время стенда, `source_system` равен sysid аппарата, `SERIAL2_PROTOCOL = 2`.
- **Симптом:** `nvv4l2h264enc` не находится или не открывает устройство на Orin Nano
  - Возможная причина: у Orin Nano нет NVENC.
  - Что сделать: `x264enc tune=zerolatency speed-preset=ultrafast` и учесть около двух ядер CPU в бюджете.
- **Симптом:** `pip install ultralytics` на Nano не ставится или тянет несовместимый PyTorch
  - Возможная причина: Ubuntu 18.04 с Python 3.6 и CUDA 10.2 — колёс под них нет.
  - Что сделать: контейнер `ultralytics/ultralytics:latest-jetson-jetpack4`; engine собирать на самой плате.
- **Симптом:** engine, собранный на другом Jetson или ПК, не загружается
  - Возможная причина: engine привязан к GPU и версии TensorRT.
  - Что сделать: переносить ONNX, собирать engine на целевой плате.
- **Симптом:** сервис перезапускается каждые 10 с
  - Возможная причина: `tegrastats` не запущен или не найден — нет строк, нет `WATCHDOG=1`.
  - Что сделать: `journalctl -u cc-health`, запустить скрипт руками, проверить путь к `tegrastats`.
  - Последствия: дыры в `NVAL` каждые 10 с — по ним это видно и после полёта.
- **Симптом:** после жёсткого отключения плата не грузится
  - Возможная причина: повреждена файловая система microSD.
  - Что сделать: выключать командой до снятия батареи, логи — на отдельный раздел или накопитель, журнал systemd в RAM (модуль «Raspberry Pi + ArduPilot»).

## checklist
- Понятно, какая плата на руках: Nano (JetPack 4.6.x, EOL) или Orin Nano (JetPack 6.x)
- Питание: отдельный BEC, 4.75–5.25 В на входе Nano под пиковым током, перемычка J48 по назначению
- Режим `nvpmodel` выбран и записан; headless-загрузка включена
- 20 минут под детектором в полётном корпусе: без троттлинга, запас ≥ 10 °C
- Камера и видеоконвейер проверены; на Orin Nano учтён программный кодер
- Engine собран на целевой плате, FP16; INT8 — только после проверки mAP на своих данных
- UART: `nvgetty` выключен, 3.3 В, петля проходит, `SERIAL2_PROTOCOL = 2`, скорости совпадают
- Мост здоровья работает как сервис со сторожевым таймером, `NVAL` есть в логе полётника
- Отказ и выключение Jetson на стенде не влияют на полётник

## references
- Jetson Nano Developer Kit User Guide (питание J25/J28/J48/J41, 4.75 В, IMX219) | https://developer.download.nvidia.com/embedded/L4T/r32-3-1_Release_v1.0/Jetson_Nano_Developer_Kit_User_Guide.pdf | primary | A
- Jetson Nano Data Sheet DS-09366-001 v1.1 (копия у дистрибьютора) | https://openzeka.com/en/wp-content/uploads/2022/08/JetsonNano_DataSheet_DS09366001v1.1-1.pdf | primary | A
- Jetson Linux 32.7.6 Developer Guide — Power Management for Jetson Nano (nvpmodel, jetson_clocks, тепловые пороги) | https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3276/Tegra%20Linux%20Driver%20Package%20Development%20Guide/power_management_nano.html | primary | A
- Jetson Linux 32.7.6 Developer Guide — tegrastats Utility | https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3276/Tegra%20Linux%20Driver%20Package%20Development%20Guide/AppendixTegraStats.html | primary | A
- Jetson Linux 36.4.3 Developer Guide — Orin Nano: режимы nvpmodel, тепловые пороги | https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html | primary | A
- Jetson Linux Developer Guide — Software Encode in Orin Nano | https://docs.nvidia.com/jetson/archives/r36.5.2/DeveloperGuide/SD/Multimedia/SoftwareEncodeInOrinNano.html | primary | A
- Jetson Linux Developer Guide — Accelerated GStreamer | https://docs.nvidia.com/jetson/l4t/Tegra%20Linux%20Driver%20Package%20Development%20Guide/accelerated_gstreamer.html | primary | A
- Jetson Product Lifecycle | https://www.developer.nvidia.com/embedded/lifecycle | primary | A
- Announcing End of Life for NVIDIA JetPack 4 with the release of JetPack 4.6.6 | https://forums.developer.nvidia.com/t/announcing-end-of-life-for-nvidia-jetpack-4-with-the-release-of-jetpack-4-6-6/314409 | primary | A
- JetPack 4.6.6 (версии компонентов) | https://developer.nvidia.com/jetpack-sdk-466 | primary | A
- JetPack 4.6 Release Notes (IMX477 через Jetson-IO) | https://docs.nvidia.com/jetson/archives/jetpack-archived/jetpack-46/release-notes/index.html | primary | A
- JetPack 6.2 Release Notes (Super mode) | https://docs.nvidia.com/jetson/jetpack/6.2/release-notes/index.html | primary | A
- NVIDIA Jetson Orin — технические характеристики | https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/ | primary | A
- Jetson Orin Nano Developer Kit Carrier Board Specification (копия) | https://uelectronics.com/wp-content/uploads/2023/05/Jetson-Orin-Nano-DevKit-Carrier-Board-Specification.pdf | primary | B
- Jetson Orin Nano Developer Kit User Guide — Hardware Layout | https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html | primary | A
- Getting Started with Jetson Nano Developer Kit (microSD, headless) | https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-devkit | primary | A
- Jetson Nano Brings AI Computing to Everyone (бенчмарки NVIDIA, кодер) | https://developer.nvidia.com/blog/jetson-nano-ai-computing/ | primary | B
- ArduPilot 4.6.3 — GCS_Common.cpp, handle_named_value → NVAL | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/GCS_MAVLink/GCS_Common.cpp | primary | A
- PX4 1.17 — mavlink_receiver.cpp, NAMED_VALUE_FLOAT → debug_key_value | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/mavlink/mavlink_receiver.cpp | primary | A
- MAVLink common.xml (NAMED_VALUE_FLOAT, MAV_COMP_ID_ONBOARD_COMPUTER, MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A
- ArduPilot Dev — Companion Computers | https://ardupilot.org/dev/docs/companion-computers.html | primary | A
- mavlink-router — исходники и README | https://github.com/mavlink-router/mavlink-router | primary | A
- Raspberry Pi — H.264 encoding performance on Raspberry Pi 5 | https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-010033-WP-1-H.264%20encoding%20performance%20on%20Raspberry%20Pi%205_series%20computers.pdf | primary | A
- Power supply considerations for Jetson Nano Developer Kit (форум NVIDIA) | https://forums.developer.nvidia.com/t/power-supply-considerations-for-jetson-nano-developer-kit/71637 | primary | B
- Ultralytics — NVIDIA Jetson guide (бенчмарки YOLO26, контейнеры, память) | https://docs.ultralytics.com/guides/nvidia-jetson/ | secondary | B
- Ultralytics — Raspberry Pi guide (бенчмарки YOLO26 на Pi 5) | https://docs.ultralytics.com/guides/raspberry-pi/ | secondary | B
- Ultralytics — TensorRT export (quantize, калибровка INT8) | https://github.com/ultralytics/ultralytics/blob/main/docs/en/integrations/tensorrt.md | secondary | B
- Q-engineering — YoloV8 TensorRT Jetson (Orin) Nano, таблица FPS | https://github.com/Qengineering/YoloV8-TensorRT-Jetson_Nano | secondary | B
- jetson-containers — образы ROS 2 для L4T r32.7.1 | https://github.com/dusty-nv/jetson-containers/blob/master/packages/physicalAI/ros/README.md | secondary | B
- JetsonHacks — Jetson Nano UART (ttyTHS1, nvgetty) | https://jetsonhacks.com/2019/10/10/jetson-nano-uart/ | secondary | B
- NVIDIA forum — Power consumption monitoring (строки tegrastats образца) | https://forums.developer.nvidia.com/t/power-consumption-monitoring/73608 | secondary | B
- JetPack 4.5 Release Notes (загрузка с USB/NVMe для Nano, приоритет microSD) | https://docs.nvidia.com/jetson/archives/jetpack-archived/jetpack-45/release-notes/index.html | primary | A
- JetsonHacks — CSI-Camera (nvarguscamerasrc sensor-id) | https://github.com/JetsonHacksNano/CSI-Camera | secondary | B
- NVIDIA forum — Weight of boards (масса модуля и devkit) | https://forums.developer.nvidia.com/t/weight-of-boards/175292 | secondary | C
- NVIDIA forum — Jetson Orin Nano 8GB: lowest operating power consumption (простой около 4 Вт) | https://forums.developer.nvidia.com/t/jetson-orin-nano-8gb-lowest-theoretical-operating-power-consumption/348662 | secondary | C
