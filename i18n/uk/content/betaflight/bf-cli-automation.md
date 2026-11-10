---
id: bf-cli-automation
title: "Автоматизація CLI через serial: граблі"
level: L3
readingTime: 25 хв
firmware: Betaflight 4.5+
status: published
added: 2026-11-07
tags:
  - CLI
  - automation
  - Python
related:
  - bf-cli
  - bf-rpm-filter
next: []
source: content/betaflight/bf-cli-automation.md
source_hash: 915000400e1d
---

## summary
Коли дронів більше ніж один, налаштовувати їх кліками в Configurator — шлях до помилок. CLI Betaflight доступний через звичайний serial-порт, отже, його можна скриптувати. Модуль показує робочий шаблон на Python (`pyserial`) і збирає граблі, на які ми реально наступили під час масового налаштування кількох квадрокоптерів: плаваючі COM-порти, «тихі» виправлення параметрів, перезавантаження і несумісність diff між версіями.

## theory
### Як влаштований вхід у CLI
Польотний контролер через USB — це віртуальний COM-порт (USB CDC). Швидкість у налаштуваннях порту для USB CDC ролі не відіграє, прийнято ставити 115200. Символ `#` переводить контролер у CLI, `exit` виходить із перезавантаженням. Поки FC у CLI, на мотори не йде сигнал — ESC можуть пищати, це нормально.

### Граблі 1: COM-порт не постійний
Якщо до комп'ютера підключено кілька однакових плат, у них один USB VID/PID, і номер COM-порту змінюється після кожного перезавантаження. Прив'язуватися до `COM8` не можна. Надійний ідентифікатор — `craft_name` усередині конфігу: відкрити кожен порт, увійти в CLI, виконати `get craft_name` і вибрати потрібний. Звідси правило: у всіх дронів різні `craft_name` ще до початку роботи.

### Граблі 2: exit noreboot перезавантажує
У Betaflight 4.5.0–4.5.3 команда `exit` завжди перезавантажує контролер (аргумент `noreboot` з'явився в 4.5.4 і 2025.12.x). Отже, після будь-якого `exit` скрипт має заново шукати порт за `craft_name`. Для «просто підглянути значення» не виходь із CLI командою — просто закрий порт.

### Граблі 3: тихі виправлення
`set` + `save` не гарантує, що значення залишилося таким, яким ти його записав. Betaflight під час завантаження коригує несумісні комбінації: протокол DShot, bidirectional DShot, схему таймерів на конкретній платі. У нашій практиці на F405-платі після ввімкнення bidir протокол DShot виявився не тим, що записували. Правило: після кожного `save` і перезавантаження — перечитати через `get` кожне змінене значення і порівняти з очікуваним.

### Граблі 4: diff не переноситься між версіями
Імена та зміст параметрів змінюються між версіями прошивки: перейменовуються `debug_mode`, змінюється синтаксис команди `serial`, змінюється зміст PID-параметрів D-term. Вставляти `diff all` від 2025.12 у 4.5 (і навпаки) порядково не можна. Переносити налаштування між версіями — лише осмислено, за розділами, з перечитуванням.

### Чому диф, а не дамп
`diff all` містить лише відмінності від стандартних значень — його можна читати очима і зберігати в git. `dump` — усе підряд, під час оновлення прошивки він тягне старі стандартні значення як явні.

### Мінімальний скрипт вивантаження `diff all` (pyserial)
```python
import serial, time, sys, glob

def cli(port, cmds, timeout=3.0):
    """Open CLI, run commands, return full text. Do not send 'exit' (reboots on 4.5)."""
    with serial.Serial(port, 115200, timeout=0.2) as s:
        s.write(b"#\n"); time.sleep(0.5); s.read(s.in_waiting or 1)
        out = ""
        for c in cmds:
            s.write((c + "\n").encode()); t0 = time.time(); buf = ""
            while time.time() - t0 < timeout:
                chunk = s.read(4096).decode(errors="replace")
                if chunk: buf += chunk; t0 = time.time()
                if buf.rstrip().endswith("# "): break        # prompt returned
            out += buf
        return out

ports = glob.glob("/dev/ttyACM*")                              # Linux; Windows: COM*
for p in ports:
    name = cli(p, ["get craft_name"])
    if "viking7" in name:
        text = cli(p, ["version", "diff all"])
        open("viking7/betaflight/diff-all.txt", "w").write(text)
        break
else:
    sys.exit("craft not found")
```
Нормалізація перед комітом: прибрати рядки з датою/часом із `version` і `# ` ехо, відсортувати блоки — інакше `git diff` шумить (модуль «CI»).

### Що автоматизувати варто, а що ні
Варто: бекап `diff all` перед кожним польотним днем; перевірка інваріантів (failsafe, poles, bidir) за вивантаженням; масова зміна `craft_name`/VTX-таблиці на парку; вивантаження логів через `msc`. Не варто: масове «накочування PID» на різні апарати (різна механіка), будь-які зміни без перечитування `get` після `save`.

{{diagram:bf-cli-session|Сесія CLI через serial: чекати на запрошення, перечитувати значення після set, після save шукати порт заново.}}

## practice
### Крок 1. Мінімальний клієнт CLI на Python
```python
import time
import serial
from serial.tools import list_ports


def cli_cmd(port: serial.Serial, cmd: str, wait: float = 0.6) -> str:
    port.write((cmd + "\n").encode())
    time.sleep(wait)
    return port.read_all().decode(errors="replace")


def enter_cli(port: serial.Serial) -> None:
    port.write(b"\n")
    time.sleep(0.3)
    port.read_all()
    port.write(b"#")
    time.sleep(1.2)
    port.read_all()


def find_craft(craft_name: str) -> str:
    """Return the COM port of the FC whose craft_name matches. Never trust COM numbers."""
    for info in list_ports.comports():
        try:
            with serial.Serial(info.device, 115200, timeout=1) as p:
                enter_cli(p)
                out = cli_cmd(p, "get craft_name")
                # do NOT send exit here: on 4.5.x it reboots the FC
                if f"craft_name = {craft_name}" in out:
                    return info.device
        except serial.SerialException:
            continue
    raise RuntimeError(f"FC '{craft_name}' not found")
```

### Крок 2. Застосування змін із перевіркою
```python
CHANGES = {"rpm_filter_min_hz": "50", "failsafe_delay": "15"}

port_name = find_craft("viking2")
with serial.Serial(port_name, 115200, timeout=1) as p:
    enter_cli(p)
    backup = cli_cmd(p, "diff all", wait=3.0)
    open("viking2_before_diff.txt", "w", encoding="utf-8").write(backup)
    for key, val in CHANGES.items():
        cli_cmd(p, f"set {key} = {val}")
    cli_cmd(p, "save", wait=1.0)  # FC reboots, COM port may change

time.sleep(6)
port_name = find_craft("viking2")  # find it again after reboot
with serial.Serial(port_name, 115200, timeout=1) as p:
    enter_cli(p)
    for key, val in CHANGES.items():
        out = cli_cmd(p, f"get {key}")
        ok = f"{key} = {val}" in out
        print(("OK  " if ok else "FAIL"), key, "expected", val)
```

### Крок 3. Зберігати конфіги як код
1. Тека на кожен дрон, усередині `configs/` і `logs/`.
2. Ім'я файлу: `<дрон>_<плата>_<ГГГГ-ММ-ДД>_diff.txt` (дрон, плата, дата) — сортування за іменем = сортування за датою.
3. Перед змінами — бекап, після — новий diff; порівнювати їх звичайним `git diff`.

### Крок 4. Другий дрон і порівняння
Запусти той самий скрипт для другого дрона, змінивши лише `craft_name` в аргументах — не код. Порівняй бекапи до і після через `git diff --no-index viking2_before_diff.txt viking2_after_diff.txt`: у різниці мають бути рівно рядки з `CHANGES`, і нічого більше. Зайвий рядок означає, що хтось змінював налаштування руками між бекапами, і це привід розібратися до польоту.

### Що має вийти і типові збої
- `find_craft` друкує список опитаних портів і знаходить потрібний за `craft_name`. Якщо дрон не знайдено, перевір, що `craft_name` задано (`get craft_name`) і що Configurator закрито: він тримає порт і засипає його MSP-трафіком.
- `diff all` на F7/H7 з великим конфігом не встигає за 3 с, і бекап обривається на середині. Надійніше читати до запрошення CLI `# ` наприкінці виведення, ніж чекати фіксований час.
- Після `save` плата перезавантажується, а на Windows COM-порт може змінитися — тому `find_craft` викликається заново. 6 с очікування вистачає більшості плат. Якщо не вистачає, шукай порт у циклі з тайм-аутом.
- Підсумок перевірки — рядки `OK` за кожним ключем. Будь-який `FAIL` означає, що значення не збереглося або в цій версії ключ називається інакше (Betaflight 2025.12 перейменував частину налаштувань — модуль «CLI»).

Лабораторну зараховано, коли скрипт знаходить дрон за `craft_name`, зберігає `diff all` з датою до змін, після `save` знаходить порт заново і перечитує значення з усіма `OK`, а прогін на двох дронах проходить без правки коду.

## diagnostics
- **Симптом:** скрипт «загубив» дрон після save
  - Можлива причина: після перезавантаження COM-порт отримав інший номер.
  - Що зробити: шукати порт заново за `craft_name`, а не за номером.
- **Симптом:** записане значення після перезавантаження інше
  - Можлива причина: Betaflight скоригував несумісну комбінацію.
  - Що зробити: перечитати пов'язані параметри, звірити з документацією плати та прошивки.
- **Симптом:** після вставлення diff частина рядків дала помилки `Invalid name`
  - Можлива причина: diff від іншої версії прошивки.
  - Що зробити: переносити налаштування за розділами, перевіряючи імена параметрів у `help` поточної версії.
- **Симптом:** два дрони відгукуються на один `craft_name`
  - Можлива причина: однакові імена (клон конфігу).
  - Що зробити: одразу перейменувати, `set craft_name = ...` + `save`.

## references
- Betaflight CLI — Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- pySerial — Documentation | https://pyserial.readthedocs.io/en/latest/ | primary | A
- Betaflight — source code (GitHub) | https://github.com/betaflight/betaflight | primary | A

## checklist
- У кожного дрона унікальний `craft_name`
- Скрипт шукає порт за `craft_name`, а не за номером COM
- Перед змінами зберігається `diff all` з датою в імені
- Після `save` скрипт заново знаходить порт і перечитує значення
- diff між різними версіями прошивки не вставляється порядково
