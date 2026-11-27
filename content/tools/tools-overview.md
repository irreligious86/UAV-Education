---
id: tools-overview
title: "Инструменты: Configurator, GCS, git"
level: L1
readingTime: 35 мин
firmware: Betaflight 2025.12 · INAV 9.1 · ArduPilot 4.7 (сверено с 4.7.3; лабораторная снята на SITL 4.7.2) · PX4 1.18
status: published
added: 2026-11-07
tags:
  - инструменты
  - git
  - GCS
related:
  - f-safety
  - bf-cli-automation
next:
  - bf-intro
---

## summary
Инженеру БПЛА нужен не один инструмент, а набор: конфигуратор под прошивку, наземная станция, анализатор логов, терминал и система контроля версий для конфигов. Модуль описывает минимальный стек на ноябрь 2026 года с проверенными версиями, как версия инструмента связана с версией прошивки и почему несовпадение ломает работу молча, таблицу «задача → инструмент» со ссылками на модули, где каждый инструмент разобран, и одно правило, которое экономит больше всего нервов: конфиги и логи живут в папках с датами и в git. Лабораторная (выполнена на ArduCopter 4.7.2 SITL): поставить Python-стек в venv, сохранить параметры в `.param`, закоммитить, изменить один параметр и получить `git diff` ровно в одну строку — и увидеть, что параметр со старым именем прошивка молча игнорирует.

## theory
### Конфигураторы прошивок
- **Betaflight App** — настройка Betaflight: порты, приёмник, режимы, PID, OSD, CLI, прошивка. Есть версии под Windows/macOS/Linux и веб-версия.
- **INAV Configurator** — то же для INAV, с планировщиком миссий.
- **Mission Planner** (Windows) и **QGroundControl** (кроссплатформенный) — наземные станции для ArduPilot и PX4: параметры, калибровки, миссии, телеметрия, логи. Для ArduPilot на Linux удобен и консольный **MAVProxy**.

### Прошивка и ESC
- **Betaflight App → Firmware Flasher** с Cloud Build.
- **ESC Configurator** (веб) или **Bluejay/AM32 Configurator** для прошивки ESC через passthrough.
- **ExpressLRS Configurator** — прошивка приёмников и модулей ELRS.
- Иногда нужен **Zadig** (Windows) для драйвера DFU при прошивке.

### Логи
- **Blackbox Explorer** (Betaflight) и **PIDscope** (открытое продолжение PIDtoolbox на GNU Octave; сам PIDtoolbox с 2024 года платный) — логи Betaflight.
- **Mission Planner / MAVExplorer / UAV Log Viewer** — DataFlash ArduPilot.
- **Flight Review** (веб) и **PlotJuggler** — логи PX4 `.ulg`; PlotJuggler открывает и `.ulg`, и CSV, и ROS 2 bag.
- **Python** с `orangebox` (Betaflight), `pymavlink.DFReader` (ArduPilot) и `pyulog` (PX4) — когда нужны свои метрики.

### Терминал и Python
Linux-терминал или WSL на Windows: `picocom`/`minicom` для UART, `pyserial` для скриптов к CLI, `pymavlink` для MAVLink, `scipy`/`matplotlib` для спектров. Виртуальное окружение на проект (`python -m venv`), чтобы версии библиотек не мешали друг другу. Зачем это нужно на практике: `pymavlink`, `MAVProxy` и `mavsdk` выходят по несколько раз в год, а скрипт разбора логов, написанный под одну версию, через год может упасть на другой. Поэтому рядом с кодом лежит `requirements.txt` с точными версиями: `pip freeze > requirements.txt` после того, как всё заработало, и `pip install -r requirements.txt` в новом venv на другой машине. Тот же принцип, что с конфигом дрона: зафиксированное состояние, к которому можно вернуться. Системный Python Ubuntu 24.04 и новее вообще не даёт ставить пакеты через `pip` вне venv (ошибка «externally-managed-environment», PEP 668) — это не поломка, а подсказка создать окружение.

Порт и права. На Linux полётник появляется как `/dev/ttyACM0` (USB VCP) или `/dev/ttyUSB0` (через USB-UART), и доступ к нему есть только у группы `dialout`: без `usermod -aG dialout` и повторного входа конфигуратор и `picocom` получают «Permission denied». На Windows порт — `COMn`, а для DFU-режима нужен драйвер WinUSB (Zadig) — без него Betaflight App видит плату в DFU, но прошить не может. Один порт — один владелец: открытый в `picocom` порт конфигуратор не откроет, и наоборот; это самая частая причина «конфигуратор не видит плату» после драйвера и кабеля.

Как читать версии у себя. Прошивка Betaflight и INAV — команда `version` в CLI (первая строка `diff all` тоже содержит версию и плату); ArduPilot — сообщение при подключении в GCS или параметр-метка в логе (`VER` в DataFlash); PX4 — `ver all` в консоли. Конфигуратор пишет свою версию в заголовке окна, Python-пакеты — `pip list` или `importlib.metadata.version()` (так делает скрипт лабораторной). Эти четыре строки (прошивка, конфигуратор или GCS, Python-стек, дата) — первое, что записывается в журнал аппарата перед изменением настроек.

### Git для конфигов
Конфигурация дрона — это код. `diff all` Betaflight и `.param` ArduPilot — текстовые файлы, их можно хранить в git, сравнивать и откатывать. Структура:

```
drones/
  viking2/
    configs/   2026-11-03_viking2_F405_diff.txt
    logs/      2026-11-03_daylight_profiles/
    notes/     session_notes.md, SUMMARY_2026-11-03.md
  viking10/
```

Имя файла начинается с даты `ГГГГ-ММ-ДД` — сортировка по имени даёт хронологию. Перед любым изменением — файл «до», после — файл «после», разница видна `git diff`.

{{diagram:config-change-flow|Правило «до/после»: файл до изменения, коммит, одно изменение — и git diff должен показать ровно одну строку; лишние строки разбирают до полёта.}}

### SITL
Для ArduPilot — SITL, для PX4 — Gazebo/jMAVSim. Любой сценарий, скрипт и параметр сначала на симуляторе.

### Рабочее место инженера: минимальный набор
| Задача | Инструмент | Зачем именно он |
|---|---|---|
| Настройка Betaflight/INAV | Betaflight App / INAV Configurator (десктоп, не веб — для прошивки и DFU) | полный доступ к CLI, прошивка, DFU |
| ArduPilot/PX4 | Mission Planner (Windows; самый полный для ArduPilot: Full Parameter List, MAVFtp, log review), QGroundControl (кроссплатформенный; PX4 — основной) | параметры, калибровки, миссии, логи |
| Консоль MAVLink | MAVProxy (`pip install MAVProxy`), `mavproxy.py --master=/dev/ttyACM0 --console --map` | скриптуемая GCS, `param`, `module load log` |
| Логи Betaflight | Blackbox Explorer, PIDscope (GNU Octave), `blackbox_decode` → CSV → Python | спектры, step response, свои метрики |
| Логи ArduPilot | Mission Planner Log Review, MAVExplorer (`mavexplorer.py log.bin`, графики по выражениям `ATT.Roll-ATT.DesRoll`), UAV Log Viewer (веб), `pymavlink` | быстрый обзор / свои метрики |
| ESC | ESC Configurator (веб, Chrome), Bluejay/AM32 configurator; passthrough через FC | прошивка и настройки ESC |
| Радио | ExpressLRS Configurator, EdgeTX Companion + Buddy | прошивка модулей, модели пульта |
| Железо | мультиметр, ваттметр XT60, smoke stopper, программатор ST-Link (восстановление FC), логический анализатор 24 МГц, осциллограф (по мере роста) | модули «Измерения» |
| Терминал | Linux / WSL2: `picocom -b 115200 /dev/ttyACM0`, `pyserial`, `venv` | скрипты к CLI, MAVLink |
| Симуляция | ArduPilot SITL (`sim_vehicle.py`), PX4 SITL (`make px4_sitl gz_x500`), Betaflight SITL (`make TARGET=SITL`) | любой сценарий — сначала здесь |
| Версионирование | git + GitHub; `.gitattributes` с LFS для `.bin/.BFL` | конфиги и скрипты, модуль «CI» |

### Версии на ноябрь 2026
Версии сверены по тегам релизов на GitHub и по PyPI 25–26 ноября 2026 года. Курс опирается на прошивки ArduPilot 4.7.3 (Copter и Plane, тег от 14.11.2026; отличия от 4.7.2 — в `ap-intro`), PX4 1.18.0 (тег от 23.11.2026; отличия от 1.17.0 — в `px4-intro`), Betaflight 2025.12.5, INAV 9.1.0, ExpressLRS 4.1.0; новее уже вышел Betaflight 2026.6.2 (17.09.2026) — его отличия в курсе разобраны только там, где о них спотыкаются (заметки «в 2026.6 …» в `bf-intro`).

| Инструмент | Версия (дата тега) | Для чего | Совместимость, что проверено |
|---|---|---|---|
| Betaflight App (бывший Configurator) | 2026.6.2 (17.09.2026) | Betaflight: настройка, CLI, прошивка, Blackbox | принимает прошивку с MSP API ≥ 1.44 (`API_VERSION_ACCEPTED` в `data_storage.js`); 4.5 отдаёт 1.46, 2025.12 — 1.47 (`msp_protocol.h`); со старой прошивкой открывает только CLI |
| Blackbox Explorer | 2025.12.1 (14.02.2026) | логи Betaflight `.BFL` | читает логи 4.x и 2025.12 |
| INAV Configurator | 9.1.1 (12.07.2026) | INAV: настройка, миссии | принимает прошивку от 9.0.0 до < 10.0.0 (`data_storage.js`): мажорная версия обязана совпасть |
| Mission Planner | 1.3.83 (тег 10.09.2025; в master на 25.11.2026 та же 1.3.83) | ArduPilot, Windows | обновляет описания параметров из сети; параметр со старым именем в 4.7 просто не найдёт |
| QGroundControl | 5.1.5 (30.09.2026) | PX4 и ArduPilot, Windows/macOS/Linux/Android | основной GCS для PX4 |
| MAVProxy / pymavlink | 1.8.75 / 2.4.50 (PyPI, 24.09.2026) | консольная GCS, MAVLink из Python, MAVExplorer | `pip install` в venv |
| pyulog | 1.3.0 (PyPI, 20.10.2026) | логи PX4 из Python | — |
| MAVSDK-Python | 4.2.1 (PyPI, 17.11.2026) | управление аппаратом из Python | разбор — `mav-sdk` |
| orangebox | 0.5.0 (PyPI, 16.05.2026) | логи Betaflight из Python | ставить отдельной последней командой: `pip install orangebox` печатает ERROR про точку входа `bb2csv` и выходит с кодом 1, библиотека при этом ставится и `from orangebox import Parser` работает; в одной команде с другими пакетами эта ошибка обрывает установку остальных (проверено) |
| PlotJuggler | 4.2.0 (дата тега не сверялась) | графики `.ulg`, CSV, ROS 2 bag | — |
| ExpressLRS Configurator | 1.8.5 (14.11.2026) | сборка и прошивка ELRS | обе стороны линка — одной мажорной версии ELRS (`link-elrs`) |
| EdgeTX / Companion | 2.12.5 (17.10.2026) | прошивка пульта, модели | Companion той же версии, что пульт |
| ArduPilot SITL | Copter 4.7.3 (курс; лабораторная ниже снята на 4.7.2) | симуляция ArduPilot | `sim_vehicle.py` или бинарник `arducopter` |
| PX4 SITL | 1.18.0 (курс; сборка `px4_sitl_default` и запуск `sihsim_quadx` проверены на v1.18.0), Gazebo Harmonic | симуляция PX4 | `Tools/setup/ubuntu.sh` ставит `gz-harmonic` на Ubuntu 22.04 и 24.04 |

Даты — это даты коммита под тегом; «стабильная» у каждого проекта своя: Mission Planner обновляется внутри 1.3.83, а у Betaflight App и Betaflight-прошивки номера версий совпадают с годом и месяцем выпуска.

### Почему версия инструмента — не мелочь
Инструмент и прошивка разговаривают по протоколу, и у каждого протокола свой способ ломаться при несовпадении версий. Знать механизм полезнее, чем помнить версии: он подсказывает, что проверить первым.

- **MSP (Betaflight, INAV).** Конфигуратор спрашивает у полётника версию API и решает, что умеет показать. У Betaflight App есть нижняя граница: прошивку старше MSP API 1.44 он не настраивает, а предлагает обновиться и пускает только в CLI (вывод из кода `serial_backend.js` 2026.6.2). У INAV граница жёстче — окно по мажорной версии прошивки: Configurator 9.1.1 работает с 9.x, а с 8.x или 10.x пишет, что версия не поддерживается, и открывает только CLI (`serial_backend.js`). Отсюда правило: сначала обновить конфигуратор под прошивку, потом подключаться.
- **MAVLink (ArduPilot, PX4).** Протокол обратно совместим: GCS любой версии видит heartbeat и параметры. Ломаются не сообщения, а имена параметров. В ArduPilot 4.7 часть параметров переименована с переходом на метры (`RTL_ALT` в сантиметрах стал `RTL_ALT_M` в метрах; `ARMING_CHECK` — маска включённых проверок — заменён `ARMING_SKIPCHK` — маской пропускаемых: значение не переносят, а пересчитывают). Запись старого имени не даёт ошибки: прошивка просто не отвечает, и `.param`-файл со старыми именами «загружается» частично. Это видно в лабораторной: `RTL_ALT` — «нет ответа», `RTL_ALT_M` — подтверждено.
- **Сборщики прошивки (ExpressLRS Configurator, Betaflight Cloud Build).** Инструмент собирает ту версию, которую ты выбрал; несовпадение проявляется уже в работе — приёмник 3.x не свяжется с передатчиком 4.x (`link-elrs`).
- **Файлы моделей пульта.** EdgeTX хранит модели в YAML; Companion должен быть той же версии, что прошивка пульта, иначе модель, сохранённая новой версией, на старой читается не полностью (ориентир курса: держать Companion и пульт на одной версии).

Практическое правило курса: версии прошивки, конфигуратора и GCS записываются в журнал аппарата рядом с каждым `diff all` или `.param`, а сравнивают только дифы одной версии прошивки.

### Задача → инструмент
| Задача | Betaflight | INAV | ArduPilot | PX4 |
|---|---|---|---|---|
| Настроить с нуля | Betaflight App (`bf-setup-scratch`) | INAV Configurator (`inav-setup-scratch`) | Mission Planner или QGC (`ap-setup-scratch`) | QGroundControl (`px4-setup-scratch`) |
| Сохранить конфиг как текст | `diff all` в CLI (`bf-cli`) | `diff all` в CLI | `.param` из GCS или MAVProxy `param save` | `.params` из QGC, `param save` в консоли |
| Разобрать лог | Blackbox Explorer, PIDscope (`bf-blackbox`) | Blackbox Explorer (форк INAV) | Mission Planner, MAVExplorer, UAV Log Viewer, WebTools (`ap-logs`) | Flight Review, PlotJuggler |
| Свои метрики по логу | `orangebox` | `orangebox` | `pymavlink.DFReader` (`data-python`) | `pyulog` (`data-python`) |
| Симуляция | Betaflight SITL | INAV SITL | ArduPilot SITL (`ap-sitl`) | PX4 SITL + Gazebo (`tools-gazebo`) |
| Управлять из программы | MSP по `pyserial` (`bf-cli-automation`) | MSP | `pymavlink`, MAVSDK, MAVProxy | MAVSDK, uXRCE-DDS (ROS 2) |
| Прошить ESC | ESC Configurator, Bluejay/AM32 (`f-esc-firmware`) | то же | то же или DShot/BLHeli passthrough | то же |

Как выбирать, если инструментов несколько. Первым — тот, что ведёт проект прошивки (Betaflight App, INAV Configurator, QGC для PX4): он первым поддерживает новые параметры. Mission Planner для ArduPilot полнее QGC по экранам настройки (Full Parameter List, MAVFtp, разбор логов), но только под Windows; на Linux его функции закрывают QGC плюс MAVProxy. Новые открытые GCS для ArduPilot (например, ArduDeck и ADOS Mission Control, которые обсуждают на форуме ArduPilot discuss.ardupilot.org) на ноябрь 2026 ещё развиваются, поэтому настройку курса по ним не строим. Веб-версии (Betaflight App в браузере, ESC Configurator) удобны для быстрого взгляда, но для прошивки в DFU надёжнее десктопная версия.

{{diagram:tools-firmware-tree|Сначала прошивка, потом инструмент: у каждой прошивки свой конфигуратор и свой формат логов, а совпадение версий конфигуратора и прошивки проверяют до подключения.}}

{{lesson:ap-sitl|SITL ArduPilot с нуля: запуск, MAVProxy, подстановка отказов — среда для любой проверки до аппарата.}}

{{lesson:data-python|Разбор логов DataFlash и ULog в Python: метрики, спектры и переходные процессы своими скриптами.}}

### Порядок установки (Linux / WSL2)
```bash
sudo apt install git python3-venv picocom build-essential
python3 -m venv ~/uav && . ~/uav/bin/activate
pip install pymavlink MAVProxy pandas numpy scipy matplotlib pyserial
sudo usermod -aG dialout $USER     # access to /dev/ttyACM*/ttyUSB*; re-login
git clone --depth 1 https://github.com/ArduPilot/ardupilot && cd ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y
```
Проверка: `mavproxy.py --master=tcp:127.0.0.1:5760` подключается к `sim_vehicle.py -v ArduCopter`. В WSL2 USB-устройства пробрасываются через `usbipd` (Windows 11) — или использовать Windows-приложения для USB, Linux — для скриптов и логов.

### Куда что логируется (чтобы потом найти)
Betaflight: flash на FC → выгрузка через конфигуратор (Blackbox tab) в `.BFL`; ArduPilot: SD-карта `/APM/LOGS/*.BIN` или MAVFtp из Mission Planner; телеметрийные логи GCS (`.tlog`) — отдельно, содержат всё, что шло по MAVLink; PX4: `.ulg` на SD, просмотр через Flight Review (веб) или `pyulog`. Именование: `ГГГГ-ММ-ДД_аппарат_цель.ext` в папке аппарата.

{{diagram:toolbox-map|Минимальный набор инструментов инженера по задачам.}}

### Место в системе

- **Получает:** от аппарата — конфиги (`diff all` из `bf-cli`, `.param`) и логи (`.BFL`, `.BIN`, `.ulg`); от задачи — что именно нужно сделать: настроить, прошить, разобрать лог, смоделировать.
- **Отдаёт:** инструмент под задачу всем трекам: Python-стек — в `data-python`, симулятор — в `ap-sitl`, структуру папок и git для конфигов — в `eng-ci-configs`.
- **Если ошибиться здесь:** не сохранил файл «до» → после неудачной правки не с чем сравнить и некуда откатиться → причину ищут по дереву диагностики вслепую (`diag-troubleshooting`). Проверил скрипт или параметр сразу на аппарате, минуя симулятор → ошибка проявляется уже в поле (`ap-sitl`).

## practice
### Минимальная установка
1. Betaflight App, Mission Planner или QGroundControl.
2. Python 3 + `pip install pyserial pymavlink scipy matplotlib` в venv, затем отдельно `pip install orangebox` (выйдет с ERROR про `bb2csv`, но библиотека встанет).
3. Git; репозиторий `drones/` по структуре выше.
4. Терминал последовательного порта.
5. Для ArduPilot — SITL по модулю «SITL: дрон без дрона».

### Первый коммит
1. Подключить дрон, `diff all` в CLI (или сохранить `.param`).
2. Сохранить в `drones/<имя>/configs/<дата>_<имя>_<плата>_diff.txt`.
3. `git add`, `git commit -m "<имя>: baseline <дата>"`.
4. После любого изменения — новый файл и коммит с описанием, что и зачем.

### Лабораторная на SITL (выполнено): стек, `.param`, git
Аппарат не нужен: тот же цикл «сохранить → закоммитить → изменить одно → сравнить» прогоняется на ArduCopter 4.7.2 SITL. Подготовка: `python3 -m venv ~/uav && . ~/uav/bin/activate && pip install pymavlink MAVProxy pyulog mavsdk pyserial numpy scipy matplotlib`, затем отдельной последней командой `pip install orangebox`. Он завершится с ERROR про `bb2csv` и кодом 1, но библиотека поставится (`from orangebox import Parser` работает). В одной команде с другими пакетами эта ошибка обрывает установку остальных, и скрипт упадёт уже на первой строке с версиями. Запуск SITL: `arducopter -S --model + -I 6 -w --defaults Tools/autotest/default_params/copter.parm --home -35.363261,149.165230,584,353`, затем `python3 tools_lab.py tcp:127.0.0.1:5820 ~/lab-repo`. Скрипт печатает версии стека, ждёт 60 с, сохраняет все параметры в `drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param`, коммитит, пробует записать `RTL_ALT` (имя до 4.7) и `RTL_ALT_M` (имя 4.7), через 20 с снова сохраняет и показывает `git diff`.

```python
"""tools-overview lab: versions of the Python stack, then config-as-code with ArduCopter SITL:
save .param (Mission Planner format NAME,VALUE) -> git commit -> change one parameter -> save -> git diff."""
import subprocess, sys, time
from importlib.metadata import version
from pathlib import Path
from pymavlink import mavutil
for p in ("pymavlink", "MAVProxy", "pyulog", "mavsdk", "orangebox", "pyserial", "numpy", "scipy", "matplotlib"):
    print(f"{p:11s} {version(p)}")
repo = Path(sys.argv[2]); cfg = repo / "drones/sitl-copter/configs"; cfg.mkdir(parents=True, exist_ok=True)
def git(*a): return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()
m = mavutil.mavlink_connection(sys.argv[1]); m.wait_heartbeat()
def fetch():
    m.param_fetch_all(); got = {}; total = None
    while total is None or len(got) < total:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=10)
        if p is None: break
        got[p.param_id] = p.param_value; total = p.param_count
    return got
def save(name, params):
    (cfg / name).write_text("".join(f"{k},{v:g}\n" for k, v in sorted(params.items())))
    return len(params)
time.sleep(60)     # baseline only after boot calibrations (gyro offsets, baro ground pressure) are done
def setp(name, val):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), val, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    ack = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3,
                       condition=f"PARAM_VALUE.param_id=='{name}'")
    print(f"set {name}={val}: " + (f"ack {ack.param_value:g}" if ack else "no answer - no such parameter"))
git("init", "-q"); git("config", "user.email", "me@example.invalid"); git("config", "user.name", "me")
n = save("2026-11-26_sitl-copter_SITL.param", fetch()); print(f"saved {n} params")
git("add", "-A"); git("commit", "-q", "-m", "sitl-copter: baseline 2026-11-26 (ArduCopter 4.7.2 SITL)")
setp("RTL_ALT", 3000)     # the 4.6 name, centimetres
setp("RTL_ALT_M", 30)     # the 4.7 name, metres
time.sleep(20)            # let the vehicle run a while, like a real bench session
save("2026-11-26_sitl-copter_SITL.param", fetch())
git("commit", "-q", "-am", "sitl-copter: RTL_ALT_M 15->30: return above 25 m trees")
print(git("log", "--oneline"))
print(git("diff", "-U0", "HEAD~1", "--", "drones"))
```

Вывод прогона в окружении автора (ArduCopter 4.7.2 SITL, Python 3.13):

```text
pymavlink   2.4.50
MAVProxy    1.8.75
pyulog      1.3.0
mavsdk      4.2.1
orangebox   0.5.0
pyserial    3.5
numpy       2.5.5
scipy       1.18.1
matplotlib  3.11.2
saved 1370 params
set RTL_ALT=3000: no answer - no such parameter
set RTL_ALT_M=30: ack 30
89ad5f7 sitl-copter: RTL_ALT_M 15->30: return above 25 m trees
7487194 sitl-copter: baseline 2026-11-26 (ArduCopter 4.7.2 SITL)
diff --git a/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param b/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param
index 4a5d4f5..2c809a9 100644
--- a/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param
+++ b/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param
@@ -824 +824 @@ RTL_ALT_FINAL_M,0
-RTL_ALT_M,15
+RTL_ALT_M,30
```

Что здесь видно. Из двух записей подтверждена только `RTL_ALT_M`; `RTL_ALT` в 4.7.2 не существует, и прошивка просто промолчала — `.param` со старыми именами загрузился бы «успешно», но без этого параметра. В диффе ровно одна строка, потому что базовый файл снят после того, как прошли калибровки загрузки. В первом прогоне автора базовый файл был снят сразу после старта, и `git diff` показал 17 параметров, которые изменились сами: `BARO1_GND_PRESS` и `BARO2_GND_PRESS` (давление на земле), `INS_GYROFFS_*` и `INS_GYR2OFFS_*` (смещения гироскопов), `INS_GYR1_CALTEMP`, идентификаторы датчиков `INS_*_ID`, `COMPASS_DEC`, `MIS_TOTAL`. Такие параметры в диффе — не твоя правка, а состояние аппарата; их узнают по имени и не путают с изменением настройки.

### Что должно получиться
После двух коммитов `git log --oneline drones/<имя>/configs/` показывает две строки с понятными описаниями, а `git diff` между файлами — ровно одну изменённую строку:

```text
-set rpm_filter_min_hz = 100
+set rpm_filter_min_hz = 50
```

Если в разнице больше строк, чем ты менял, значит, в диф попали неожиданные изменения: другая версия прошивки (новые или переименованные настройки), чьи-то правки, сброс к умолчаниям. Это повод разобраться до полёта, а не после. Сравнивай дифы одной версии прошивки. После обновления прошивки делай отдельный базовый коммит «baseline после обновления».

### Типичные ошибки
- Имя файла без даты или без платы — через месяц не понять, что это и откуда.
- Сохранять `dump` вместо `diff all`: в дампе сотни строк значений по умолчанию, и полезное изменение в нём теряется.
- Коммит без описания «зачем». Через полгода «изменил фильтр» ничего не скажет, а «rpm_filter_min_hz 100→50: моторы 10" ниже 100 Гц на висении» — скажет.

### Лабораторная
Сделай два дифа с разницей в один параметр и посмотри `git diff` между ними. Это твой первый «код-ревью» собственного дрона.

Самопроверка: лабораторная выполнена, когда **(SITL)** скрипт напечатал версии стека (pymavlink 2.4.x, MAVProxy 1.8.x — или новее, тогда запиши свои), сохранено 1370 ± 50 параметров ArduCopter 4.7.x, `RTL_ALT` дал «no answer», `RTL_ALT_M` — «ack 30», а `git diff` — ровно две строки `-RTL_ALT_M,15` / `+RTL_ALT_M,30`; **(свой аппарат)** репозиторий `drones/` создан по структуре, конфиг сохранён с датой и платой в имени и закоммичен с описанием, `git log --oneline drones/<имя>/configs/` показывает две строки с понятными описаниями, а `git diff` двух конфигов показывает ровно одну изменённую строку — ту, что ты менял, с объяснением «зачем» в сообщении коммита.

**Эталон для самопроверки.** Верный результат: одна изменённая строка и сообщение вида «rpm_filter_min_hz 100→50: моторы 10" ниже 100 Гц на висении». Типичные неверные: (1) в разнице больше строк, чем ты менял, — в диф попала другая версия прошивки или сброс к умолчаниям: разберись до полёта; (2) в разнице сотни строк — сохранён `dump` вместо `diff all`; (3) в SITL-диффе строки `INS_GYROFFS_*`, `BARO*_GND_PRESS`, `INS_*_ID` — базовый файл снят до окончания калибровок загрузки, подожди 60 с и сними заново; (4) в диффе нет строки RTL — записан `RTL_ALT` вместо `RTL_ALT_M`, имя из версии до 4.7.

## diagnostics
- **Симптом:** конфигуратор не видит плату
  - Возможная причина: драйвер (Windows), кабель только для зарядки, плата в DFU.
  - Что сделать: Zadig для DFU, другой кабель, проверить COM-порт.
- **Симптом:** не помню, что менял перед тем, как сломалось
  - Возможная причина: нет дифов «до/после».
  - Что сделать: правило «файл до изменений — всегда», git.
- **Симптом:** загрузил `.param` в ArduPilot 4.7, ошибок нет, а часть настроек не применилась
  - Возможная причина: в файле имена параметров до 4.7 (`RTL_ALT`, `ARMING_CHECK`); запись неизвестного имени прошивка молча игнорирует.
  - Что сделать: сравнить файл с полным списком параметров после загрузки (`git diff`), переименовать по примечаниям к выпуску (`ap-setup-scratch`); `ARMING_CHECK` не переименовывают, а пересчитывают в `ARMING_SKIPCHK` (маска пропускаемых проверок, смысл обратный).
- **Симптом:** INAV Configurator пишет, что версия прошивки не поддерживается, и открывает только вкладку CLI
  - Возможная причина: мажорные версии не совпадают (Configurator 9.x принимает только прошивку 9.x).
  - Что сделать: поставить Configurator той же мажорной версии, что прошивка, или обновить прошивку.
- **Симптом:** `pip install` в системный Python отвечает «externally-managed-environment»
  - Возможная причина: Ubuntu 24.04+ запрещает ставить пакеты в системный Python (PEP 668).
  - Что сделать: `python3 -m venv` на проект; `requirements.txt` с точными версиями.
- **Симптом:** библиотеки Python конфликтуют между проектами
  - Возможная причина: всё ставится в системный Python.
  - Что сделать: venv на проект.

## references
- Betaflight App — Documentation | https://betaflight.com/docs/wiki/app | primary | A
- Mission Planner — Documentation | https://ardupilot.org/planner/ | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/Stable_V5.0/en/ | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A
- Pro Git — book | https://git-scm.com/book/en/v2 | primary | A
- Betaflight App 2026.6.2 source — src/js/data_storage.js (API_VERSION_ACCEPTED 1.44, MAX_SUPPORTED 1.48), src/js/serial_backend.js | https://github.com/betaflight/betaflight-configurator/blob/2026.6.2/src/js/data_storage.js | primary | A
- INAV Configurator 9.1.1 source — js/data_storage.js (minfirmwareVersionAccepted 9.0.0, maxFirmwareVersionAccepted 10.0.0) | https://github.com/iNavFlight/inav-configurator/blob/9.1.1/js/data_storage.js | primary | A
- PX4 1.18.0 — Tools/setup/ubuntu.sh (Gazebo Harmonic на Ubuntu 22.04+) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/Tools/setup/ubuntu.sh | primary | A
- PyPI — pymavlink, MAVProxy, pyulog, mavsdk, orangebox (версии и даты на 2026-11-25) | https://pypi.org/project/pymavlink/ | primary | A

## checklist
- Установлены конфигуратор и наземная станция под мои прошивки
- Python в venv с pyserial/pymavlink, `requirements.txt` с версиями
- Версии прошивки, конфигуратора/GCS и Python-стека записаны в журнал аппарата
- Конфигуратор той же мажорной версии, что прошивка (INAV) или в окне MSP API (Betaflight)
- Репозиторий `drones/` с папкой на каждый дрон
- Каждый конфиг — файл с датой в имени, в git
- Перед изменениями всегда есть файл «до»
