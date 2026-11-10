---
id: tools-overview
title: "Інструменти: Configurator, GCS, git"
level: L1
readingTime: 15 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-07
tags:
  - інструменти
  - git
  - GCS
related:
  - f-safety
  - bf-cli-automation
next:
  - bf-intro
source: content/tools/tools-overview.md
source_hash: 7528e2cae361
---

## summary
Інженерові БпЛА треба не один інструмент, а цілий набір: конфігуратор під прошивку, наземна станція, аналізатор логів, термінал і система контролю версій для конфігів. Модуль описує мінімальний стек на 2026 рік, що чим робити, і одне правило, яке береже найбільше нервів: конфіги й логи живуть у папках із датами та в git — як у доброго ґазди, кожна річ на своєму місці.

## theory
### Конфігуратори прошивок
- **Betaflight App** — налаштування Betaflight: порти, приймач, режими, PID, OSD, CLI, прошивка. Є версії під Windows/macOS/Linux і веб-версія.
- **INAV Configurator** — те саме для INAV, із планувальником місій.
- **Mission Planner** (Windows) і **QGroundControl** (кросплатформний) — наземні станції для ArduPilot і PX4: параметри, калібрування, місії, телеметрія, логи. Для ArduPilot на Linux файний і консольний **MAVProxy**.

### Прошивка і ESC
- **Betaflight App → Firmware Flasher** із Cloud Build.
- **ESC Configurator** (веб) або **Bluejay/AM32 Configurator** для прошивки ESC через passthrough.
- **ExpressLRS Configurator** — прошивка приймачів і модулів ELRS.
- Часом треба **Zadig** (Windows) для драйвера DFU під час прошивки.

### Логи
- **Blackbox Explorer** (Betaflight) і **PIDscope** (відкрите продовження PIDtoolbox на GNU Octave; сам PIDtoolbox з 2024 року платний) — логи Betaflight.
- **Mission Planner / MAVExplorer / UAV Log Viewer** — DataFlash ArduPilot.
- **Python** з `orangebox` (Betaflight) і `pymavlink.DFReader` (ArduPilot) — коли треба власні метрики.

### Термінал і Python
Linux-термінал або WSL на Windows: `picocom`/`minicom` для UART, `pyserial` для скриптів до CLI, `pymavlink` для MAVLink, `scipy`/`matplotlib` для спектрів. Віртуальне оточення на проєкт (`python -m venv`), щоб версії бібліотек не ся заважали одна одній.

### Git для конфігів
Конфігурація дрона — то код. `diff all` Betaflight і `.param` ArduPilot — текстові файли, їх можна тримати в git, порівнювати й відкочувати. Структура:

```
drones/
  viking2/
    configs/   2026-11-03_viking2_F405_diff.txt
    logs/      2026-11-03_daylight_profiles/
    notes/     session_notes.md, SUMMARY_2026-11-03.md
  viking10/
```

Ім'я файлу починається з дати `ГГГГ-ММ-ДД` — сортування за іменем дає хронологію. Перед будь-якою зміною — файл «до», після — файл «після», а різницю видно в `git diff`.

### SITL
Для ArduPilot — SITL, для PX4 — Gazebo/jMAVSim. Кожен сценарій, скрипт і параметр — спершу на симуляторі.

### Робоче місце інженера: мінімальний набір
| Задача | Інструмент | Чому саме він |
|---|---|---|
| Налаштування Betaflight/INAV | Betaflight App / INAV Configurator (десктоп, не веб — для прошивки й DFU) | повний доступ до CLI, прошивка, DFU |
| ArduPilot/PX4 | Mission Planner (Windows; найповніший для ArduPilot: Full Parameter List, MAVFtp, log review), QGroundControl (кросплатформний; для PX4 — основний) | параметри, калібрування, місії, логи |
| Консоль MAVLink | MAVProxy (`pip install MAVProxy`), `mavproxy.py --master=/dev/ttyACM0 --console --map` | GCS, яку можна скриптувати, `param`, `module load log` |
| Логи Betaflight | Blackbox Explorer, PIDscope (GNU Octave), `blackbox_decode` → CSV → Python | спектри, step response, власні метрики |
| Логи ArduPilot | Mission Planner Log Review, MAVExplorer (`mavexplorer.py log.bin`, графіки за виразами `ATT.Roll-ATT.DesRoll`), UAV Log Viewer (веб), `pymavlink` | шпаркий огляд / власні метрики |
| ESC | ESC Configurator (веб, Chrome), Bluejay/AM32 configurator; passthrough через FC | прошивка й налаштування ESC |
| Радіо | ExpressLRS Configurator, EdgeTX Companion + Buddy | прошивка модулів, моделі пульта |
| Залізо | мультиметр, ватметр XT60, smoke stopper, програматор ST-Link (відновлення FC), логічний аналізатор 24 МГц, осцилограф (з часом) | модулі «Вимірювання» |
| Термінал | Linux / WSL2: `picocom -b 115200 /dev/ttyACM0`, `pyserial`, `venv` | скрипти до CLI, MAVLink |
| Симуляція | ArduPilot SITL (`sim_vehicle.py`), PX4 SITL (`make px4_sitl gz_x500`), Betaflight SITL (`make TARGET=SITL`) | кожен сценарій — спершу тут |
| Версіонування | git + GitHub; `.gitattributes` з LFS для `.bin/.BFL` | конфіги й скрипти, модуль «CI» |

### Порядок встановлення (Linux / WSL2)
```bash
sudo apt install git python3-venv picocom build-essential
python3 -m venv ~/uav && . ~/uav/bin/activate
pip install pymavlink MAVProxy pandas numpy scipy matplotlib pyserial
sudo usermod -aG dialout $USER     # access to /dev/ttyACM*/ttyUSB*; re-login
git clone --depth 1 https://github.com/ArduPilot/ardupilot && cd ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y
```
Перевірка: `mavproxy.py --master=tcp:127.0.0.1:5760` ся підключає до `sim_vehicle.py -v ArduCopter`. У WSL2 USB-пристрої прокидаються через `usbipd` (Windows 11) — або бери Windows-застосунки для USB, а Linux — для скриптів і логів.

### Куди що логується (щоб потім знайти)
Betaflight: flash на FC → вивантаження через конфігуратор (вкладка Blackbox) у `.BFL`; ArduPilot: SD-карта `/APM/LOGS/*.BIN` або MAVFtp з Mission Planner; телеметрійні логи GCS (`.tlog`) — окремо, в них є вшитко, що йшло через MAVLink; PX4: `.ulg` на SD, перегляд через Flight Review (веб) або `pyulog`. Іменування: `ГГГГ-ММ-ДД_аппарат_цель.ext` у папці апарата.

{{diagram:toolbox-map|Мінімальний набір інструментів інженера за задачами.}}

## practice
### Мінімальне встановлення
1. Betaflight App, Mission Planner або QGroundControl.
2. Python 3 + `pip install pyserial pymavlink orangebox scipy matplotlib` у venv.
3. Git; репозиторій `drones/` за структурою вище.
4. Термінал послідовного порту.
5. Для ArduPilot — SITL за модулем «SITL: дрон без дрона».

### Перший коміт
1. Підключити дрон, `diff all` у CLI (або зберегти `.param`).
2. Зберегти в `drones/<имя>/configs/<дата>_<имя>_<плата>_diff.txt`.
3. `git add`, `git commit -m "<имя>: baseline <дата>"`.
4. Після будь-якої зміни — новий файл і коміт з описом, що й нащо.

### Що має вийти
Після двох комітів `git log --oneline drones/<имя>/configs/` показує два рядки зі зрозумілими описами, а `git diff` між файлами — рівно один змінений рядок:

```text
-set rpm_filter_min_hz = 100
+set rpm_filter_min_hz = 50
```

Як у різниці більше рядків, ніж ти міняв, то в диф трафилися неочікувані зміни: інша версія прошивки (нові або перейменовані налаштування), чиїсь правки, скидання до типових значень. То привід розібратися до польоту, а не після. Порівнюй дифи однієї версії прошивки. Після оновлення прошивки роби окремий базовий коміт «baseline після оновлення».

### Типові помилки
- Ім'я файлу без дати або без плати — за місяць не втямиш, що то і звідки.
- Тримати `dump` замість `diff all`: у дампі сотні рядків типових значень, і корисна зміна в ньому гет губиться.
- Коміт без опису «нащо». За пів року «змінив фільтр» ніц не скаже, а «rpm_filter_min_hz 100→50: мотори 10" нижче 100 Гц на зависанні» — скаже.

### Лабораторна
Зроби два дифи з різницею в один параметр і покажи `git diff` між ними. Во твоє перше «код-рев'ю» власного дрона.

Лабораторна зараховується, коли репозиторій `drones/` створено за структурою, конфіг збережено з датою та платою в імені й закомічено з описом, а `git diff` двох конфігів показує рівно одну зміну з поясненням у повідомленні коміту.

## diagnostics
- **Симптом:** конфігуратор не бачить плату
  - Можлива причина: драйвер (Windows), кабель лиш для заряджання, плата в DFU.
  - Що зробити: Zadig для DFU, інший кабель, перевірити COM-порт.
- **Симптом:** не пам'ятаю, що міняв, заки ся зламало
  - Можлива причина: нема дифів «до/після».
  - Що зробити: правило «файл до змін — завжди», git.
- **Симптом:** бібліотеки Python конфліктують між проєктами
  - Можлива причина: вшитко ставиться в системний Python.
  - Що зробити: venv на проєкт.

## references
- Betaflight App — Documentation | https://betaflight.com/docs/wiki/app | primary | A
- Mission Planner — Documentation | https://ardupilot.org/planner/ | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/Stable_V5.0/en/ | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A
- Pro Git — book | https://git-scm.com/book/en/v2 | primary | A

## checklist
- Встановлено конфігуратор і наземну станцію під мої прошивки
- Python у venv з pyserial/pymavlink
- Репозиторій `drones/` з папкою на кожен дрон
- Кожен конфіг — файл із датою в імені, у git
- Перед змінами завжди є файл «до»
