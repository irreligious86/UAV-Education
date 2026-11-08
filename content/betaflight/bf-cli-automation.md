---
id: bf-cli-automation
title: "Автоматизация CLI по serial: грабли"
level: L3
readingTime: 25 мин
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
---

## summary
Когда дронов больше одного, настраивать их кликами в Configurator — путь к ошибкам. CLI Betaflight доступен через обычный serial-порт, значит его можно скриптовать. Модуль показывает рабочий шаблон на Python (`pyserial`) и собирает грабли, на которые мы реально наступили при массовой настройке нескольких квадрокоптеров: плавающие COM-порты, «тихие» исправления параметров, перезагрузки и несовместимость diff между версиями.

## theory
### Как устроен вход в CLI
Полётный контроллер по USB — это виртуальный COM-порт (USB CDC). Скорость в настройках порта для USB CDC роли не играет, принято ставить 115200. Символ `#` переводит контроллер в CLI, `exit` выходит с перезагрузкой. Пока FC в CLI, на моторы не идёт сигнал — ESC могут пищать, это нормально.

### Грабли 1: COM-порт не постоянный
Если к компьютеру подключено несколько одинаковых плат, у них один USB VID/PID, и номер COM-порта меняется после каждой перезагрузки. Привязываться к `COM8` нельзя. Надёжный идентификатор — `craft_name` внутри конфига: открыть каждый порт, войти в CLI, выполнить `get craft_name` и выбрать нужный. Отсюда правило: у всех дронов разные `craft_name` ещё до начала работы.

### Грабли 2: exit noreboot перезагружает
В Betaflight 4.5.x команда `exit noreboot` всё равно перезагружает контроллер (флаг `noreboot` заработал только в более новых версиях). Значит после любого `exit` скрипт должен заново искать порт по `craft_name`. Для «просто подсмотреть значение» не выходи из CLI командой — просто закрой порт.

### Грабли 3: тихие исправления
`set` + `save` не гарантирует, что значение осталось таким, каким ты его записал. Betaflight при загрузке корректирует несовместимые комбинации: протокол DShot, bidirectional DShot, схема таймеров на конкретной плате. В нашей практике на F405-плате после включения bidir протокол DShot оказался не тем, что записывали. Правило: после каждого `save` и перезагрузки — перечитать через `get` каждое изменённое значение и сравнить с ожидаемым.

### Грабли 4: diff не переносится между версиями
Имена и смысл параметров меняются между версиями прошивки: переименовываются `debug_mode`, меняется синтаксис команды `serial`, меняется смысл PID-параметров D-term. Вставлять `diff all` от 2025.12 в 4.5 (и наоборот) построчно нельзя. Переносить настройки между версиями — только осмысленно, по разделам, с перечитыванием.

### Почему диф, а не дамп
`diff all` содержит только отличия от дефолтов — его можно читать глазами и хранить в git. `dump` — всё подряд, при обновлении прошивки он тащит старые дефолты как явные значения.

### Минимальный скрипт выгрузки `diff all` (pyserial)
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
Нормализация перед коммитом: убрать строки с датой/временем из `version` и `# ` эхо, отсортировать блоки — иначе `git diff` шумит (модуль «CI»).

### Что автоматизировать стоит, а что нет
Стоит: бэкап `diff all` перед каждым полётным днём; проверка инвариантов (failsafe, poles, bidir) по выгрузке; массовая смена `craft_name`/VTX-таблицы на парке; выгрузка логов через `msc`. Не стоит: массовая «накатка PID» на разные аппараты (разная механика), любые изменения без перечитывания `get` после `save`.

## practice
### Шаг 1. Минимальный клиент CLI на Python
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

### Шаг 2. Применение изменений с проверкой
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

### Шаг 3. Хранить конфиги как код
1. Папка на каждый дрон, внутри `configs/` и `logs/`.
2. Имя файла: `<дрон>_<плата>_<ГГГГ-ММ-ДД>_diff.txt` — сортировка по имени = сортировка по дате.
3. Перед изменениями — бэкап, после — новый diff; сравнивать их обычным `git diff`.

## diagnostics
- **Симптом:** скрипт «потерял» дрон после save
  - Возможная причина: после перезагрузки COM-порт получил другой номер.
  - Что сделать: искать порт заново по `craft_name`, а не по номеру.
- **Симптом:** записанное значение после перезагрузки другое
  - Возможная причина: Betaflight скорректировал несовместимую комбинацию.
  - Что сделать: перечитать связанные параметры, сверить с документацией платы и прошивки.
- **Симптом:** после вставки diff часть строк дала ошибки `Invalid name`
  - Возможная причина: diff от другой версии прошивки.
  - Что сделать: переносить настройки по разделам, проверяя имена параметров в `help` текущей версии.
- **Симптом:** два дрона откликаются на один `craft_name`
  - Возможная причина: одинаковые имена (клон конфига).
  - Что сделать: сразу переименовать, `set craft_name = ...` + `save`.

## references
- Betaflight CLI — Documentation | https://betaflight.com/docs/development/Cli | primary | A
- pySerial — Documentation | https://pyserial.readthedocs.io/en/latest/ | primary | A
- Betaflight — source code (GitHub) | https://github.com/betaflight/betaflight | primary | A

## checklist
- У каждого дрона уникальный `craft_name`
- Скрипт ищет порт по `craft_name`, а не по номеру COM
- Перед изменениями сохраняется `diff all` с датой в имени
- После `save` скрипт заново находит порт и перечитывает значения
- diff между разными версиями прошивки не вставляется построчно
