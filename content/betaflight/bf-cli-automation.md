---
id: bf-cli-automation
title: "Автоматизация CLI по serial: грабли"
level: L3
readingTime: 45 мин
firmware: "Betaflight 4.5.3 и 2025.12.5 (исходники и SITL обеих версий); pyserial 3.5"
status: published
added: 2026-11-07
tags:
  - CLI
  - MSP
  - automation
  - Python
related:
  - bf-cli
  - bf-rpm-filter
  - eng-ci-configs
next: []
---

## summary
Когда дронов больше одного, настраивать их кликами в Configurator — путь к ошибкам. CLI Betaflight доступен через обычный serial-порт, значит его можно скриптовать, а опознать плату можно вообще без CLI — по протоколу MSP. Модуль разбирает, как прошивка переключает порт между MSP и CLI, в каком формате отвечает CLI и как отличить ответ от приглашения, и собирает грабли массовой настройки: плавающие COM-порты, `save` и `exit`, которые перезагружают (в 4.5.3 — даже с `noreboot`), «тихие» исправления значений при сохранении и загрузке, поиск по подстроке в `get`, пакетный режим и несовместимость `diff all` между 4.5 и 2025.12. Лабораторная идёт без железа: на собранных из исходников SITL Betaflight 4.5.3 и 2025.12.5 скрипт на Python делает всё то же, что делал бы с платой по USB, и ловит реальные исправления значений прошивкой.

## theory
### Как устроен вход в CLI
Полётный контроллер по USB — это виртуальный COM-порт (USB CDC). Скорость в настройках порта для USB CDC роли не играет, принято ставить 115200. Символ `#` переводит контроллер в CLI, `exit` выходит с перезагрузкой.

Механизм — из исходников (`msp/msp_serial.c`, `cli/cli.c`, 4.5.3 и 2025.12.5 одинаково, если не оговорено). Порт по умолчанию слушает MSP. Каждый байт, который не является частью MSP-кадра, прошивка рассматривает как «не-MSP данные»: байт `#` ставит запрос на вход в CLI, байт `reboot_character` (по умолчанию `R`, код 82, диапазон 48–126) — запрос на перезагрузку в загрузчик. Запрос выполняется, только когда порт молчал 100 мс, и версии ведут себя по-разному: в 4.5.3 любой байт, пришедший до истечения этих 100 мс в следующем проходе задачи, отменяет вход (`msp_serial.c:519–522`: «abort pending request») — `#` и следом команда дают «CLI не открылся»; в 2025.12 запрос сбрасывает только `$` (`msp_serial.c:535–539`), но байты, пришедшие до входа, теряются. Порядок для обеих: `#`, дождаться приглашения, потом команды. Пока аппарат заармлен, не-MSP байты игнорируются (`fc/tasks.c`: `ARMING_FLAG(ARMED) ? MSP_SKIP_NON_MSP_DATA`): на армленом дроне `#` ничего не сделает, и это защита, а не баг. Отсюда же грабля: скрипт, который шлёт в порт произвольный текст до входа в CLI, может случайно отправить `R` и уронить плату в DFU.

После входа прошивка печатает `Entering CLI Mode, type 'exit' to return, or 'help'` (в 2025.12 — `... to reboot ...`), ставит флаг запрета арма `CLI` и выводит приглашение — ровно 4 байта `\r\n# `. Каждый принятый символ CLI возвращает эхом, поэтому ответ на команду — это эхо, перевод строки, вывод и снова `\r\n# `. Строка длиннее 256 символов (`CLI_IN_BUFFER_SIZE`) молча обрезается, всё после `#` в строке считается комментарием (поэтому, если плата уже в CLI с прошлого сеанса, одиночный `#` начинает комментарий и съедает следующую команду: в проверке короткого скрипта ниже так пропала команда `version`; безопасный вход — `#\n`, отправленный одной записью в порт: тогда оба байта приходят в одном проходе, и он работает в обоих состояниях), ошибки печатаются в формате `###ERROR IN <команда>: <текст>###`. В CLI все байты порта идут в CLI: MSP на этом порту не отвечает (в 4.5.3 — ни на одном порту: `fc/tasks.c` выходит до `mspSerialProcess`; в 2025.12 состояние CLI хранится у порта, и другие MSP-порты работают), Blackbox не пишет (`fc/core.c`: `if (!cliMode && blackboxConfig()->device)`), задача телеметрии не работает (`fc/tasks.c`: `if (!cliMode && featureIsEnabled(FEATURE_TELEMETRY))`). Configurator в это время показывает «нет связи» — это нормально.

### MSP: опознать плату, не входя в CLI
MSP v1 — двоичный протокол Configurator: запрос `$M<`, байт длины, байт команды, данные и контрольная сумма — XOR длины, команды и данных; ответ начинается с `$M>`, неподдерживаемая команда — `$M!`. Для поиска нужной платы хватает пяти команд, и ни одна не требует CLI, не перезагружает и не ставит запрет арма:

| Команда (номер) | Ответ | 4.5.3 (SITL) | 2025.12.5 (SITL) |
|---|---|---|---|
| `MSP_API_VERSION` (1) | протокол, major, minor | 1.46 | 1.47 |
| `MSP_FC_VARIANT` (2) | 4 символа | `BTFL` | `BTFL` |
| `MSP_FC_VERSION` (3) | 3 байта версии (в 2025.12 — ещё строка Pascal) | 4.5.3 | 25.12.5 (год − 2000, месяц, патч) + `2025.12.5`, всего 13 байт |
| `MSP_NAME` (10) | `craft_name` | строка | строка |
| `MSP_UID` (160) | 3 × uint32, уникальный ID MCU | 12 байт | 12 байт |

Грабля в третьей строке: с переходом на календарные версии `MSP_FC_VERSION` в 2025.12 отдаёт `25, 12, 5` (`msp.c`: `FC_VERSION_YEAR - FC_CALVER_BASE_YEAR`). Скрипт с проверкой «major ≥ 4 — значит новая» примет 2025.12 за 25-ю версию, а скрипт с «major == 4» — за неизвестную прошивку. Версию сравнивай по `MSP_API_VERSION`, по полной строке из `version` или по строке, которую 2025.12 добавляет в ответ `MSP_FC_VERSION` после трёх байт (`sbufWritePString(FC_VERSION_STRING)`, `msp.c:646`). `MSP_UID` на реальной плате — заводской номер микроконтроллера, он не меняется при перепрошивке и `defaults`; в SITL он фиксированный (`000000000100000002000000` в обеих версиях), поэтому в лабораторной опознание идёт по имени.

### Грабли 1: COM-порт не постоянный
Если к компьютеру подключено несколько одинаковых плат, у них один USB VID/PID, и номер COM-порта меняется после каждой перезагрузки. Привязываться к `COM8` нельзя. Надёжный идентификатор — `craft_name` внутри конфига, и читать его надо по MSP (`MSP_NAME`), а не входом в CLI на каждом порту: вход в CLI ставит запрет арма до перезагрузки, а на 4.5.3 из CLI нельзя выйти без перезагрузки. Отсюда правило: у всех дронов разные `craft_name` ещё до начала работы; для парка из одинаковых плат храни рядом с именем ещё и `MSP_UID` — он ловит клон конфига, когда два аппарата получили одно имя.

### Грабли 2: exit noreboot перезагружает на 4.5.3
Команда `exit` по умолчанию перезагружает контроллер и печатает `leaving CLI mode, unsaved changes lost` — всё, что не сохранено `save`, теряется. В 2025.12 (и в 4.5.5, проверено по исходникам; по истории изменений — с 4.5.4) есть `exit noreboot` и `save noreboot`; в 4.5.0–4.5.3 аргумента нет, и `exit` перезагружает всегда. Хуже того: в 4.5.3 `cliSave` и `cliExit` аргумент просто не читают (`UNUSED(cmdline)`), поэтому `save noreboot`, отправленный на 4.5.3, сохранит и перезагрузит плату без ошибки. Скрипт, который должен работать на любой из этих версий, после любого `exit` и `save` должен заново искать порт по `craft_name`. Для «просто подсмотреть значение» не выходи из CLI командой — просто закрой порт. И ещё одна деталь 2025.12: после `exit noreboot` флаг запрета арма `CLI` остаётся до перезагрузки — в исходниках он только ставится (`setArmingDisabled(ARMING_DISABLED_CLI)` в `cliEnter`, комментарий «arming flag not released if exiting cli with no reboot for safety»).

### Неинтерактивный режим 4.5.5 и 2025.12: STX … ETX
В 4.5.5 и 2025.12 есть режим для программ (в 4.5.3 его нет; `msp_serial.c:547` в 4.5.5): байт `0x02` (STX) вместо `#` входит в CLI без эха, без приглашения и без запрета арма; прошивка отвечает `0x02`, выполняет присланные строки и печатает только их вывод (неизвестная команда — `ERR_CMD_NA: <строка>`), а байт `0x03` (ETX) или первый байт, пришедший позже чем через 2 с после входа, завершают сеанс — прошивка отвечает `0x03` и остаётся работать без перезагрузки (`cli.c`, `cliProcess`). Двухсекундный предел проверяется только при приходе байта: если после ответа ничего не прислать, порт так и остаётся в CLI (MSP на нём молчит, Blackbox и телеметрия стоят), поэтому сеанс всегда заканчивают байтом `0x03`. В лабораторной `\x02get failsafe_delay\n\x03` вернул `\x02failsafe_delay = 10\r\nAllowed range: 1 - 200\r\nDefault value: 15\r\n\x03`. Для чтения значений на 4.5.5 и 2025.12 это самый безопасный путь; в 4.5.3 байт `0x02` — просто мусор для MSP.

### Грабли 3: тихие исправления
`set` + `save` не гарантирует, что значение осталось таким, каким ты его записал. Betaflight корректирует несовместимые комбинации функцией `validateAndFixConfig()` (`config/config.c`) — и делает это дважды: внутри `save` перед записью в EEPROM и при каждой загрузке. Ответ `x set to 20` означает только «записано в RAM». Примеры, проверенные по исходникам и в SITL:

- 2025.12: если `d_max_<ось>` меньше `d_<ось>`, `d_max` обнуляется (`config.c:268`); в 4.5.3 зеркально — `d_min` больше `D` обнуляется (`config.c:281`).
- Обе версии, полётная плата с GPS-сборкой: `failsafe_procedure = GPS-RESCUE` при выключенной `feature GPS` (или 3D, или самолётном миксере) сбрасывается в `DROP` (`config.c:370` в 4.5.3, `:357` в 2025.12; вывод из кода, в SITL не проверено).
- 4.5.5 и 2025.12: любое значение `failsafe_procedure` вне перечня процедур этой сборки сбрасывается в `DROP` (`config.c:373` в 4.5.5, `:360–361` в 2025.12); в 4.5.3 такой проверки нет. Именно это сработало в лабораторной: в SITL обеих версий GPS-спасение не собрано (`target/common_pre.h:72`: GPS-драйверы только при `!defined(SITL)`), строка `GPS-RESCUE` принимается таблицей значений, но такой процедуры в прошивке нет. 2025.12.5 на `save noreboot` сбросил её в `DROP`, 4.5.3 оставил как есть.
- Обе версии: двунаправленный DShot (`dshot_bidir`) выключается, если протокол моторов не DShot, или bitbang выключен и при этом включён burst DShot либо мотор висит на N-канале таймера (`config.c:556` в 4.5.3, `:472` в 2025.12). Наблюдение из практики без сохранённого лога: на F405-плате после включения bidir связка «протокол + bidir» после перезагрузки оказалась не той, что записывали.

Правило: после каждого `save` и перезагрузки — перечитать через `get` каждое изменённое значение и сравнить с ожидаемым.

{{diagram:bf-cli-silent-fix|validateAndFixConfig работает дважды — в save и при загрузке, поэтому подтверждение «set to» ничего не гарантирует: проверка только чтением get после перезагрузки.}}

### Грабли 4: get ищет по подстроке
`get d_roll` печатает все параметры, в имени которых есть `d_roll`, — в 4.5.3 это `align_board_roll = 0` и только потом `d_roll = 30` (реальный вывод SITL в лабораторной: `align_boar[d_roll]` совпал). Проверка `if "d_roll = " in out` в таком выводе случайно сработает на чужой строке, а наивный разбор «первая строка с ` = `» вернёт 0 вместо 30 — так в первой версии лабораторного скрипта появился ложный `FAIL`. Разбирай ответ регулярным выражением с якорем начала строки: `^d_roll = (.*)$` в многострочном режиме. Заодно `get` печатает строку профиля (`profile 0`) и `Default value:` для изменённых значений — эти строки тоже не значение.

### Грабли 5: пакетный режим
`batch start` … `batch end` — режим вставки: команды выполняются по одной, но если хотя бы одна дала ошибку, `batch end` печатает `###ERROR IN batch: ERRORS WERE DETECTED - PLEASE REVIEW BEFORE CONTINUING###`, а `save` внутри такого пакета отказывается: `###ERROR IN save: PLEASE FIX ERRORS THEN 'SAVE'###`. Это защита от наполовину применённого конфига, но одноразовая: и `batch end`, и отказавший `save` закрывают пакет (`resetCommandBatch()`), так что следующий `save` молча сохранит всё, что успело примениться в RAM. Скрипт должен собирать ошибки `###ERROR…###` после каждой команды и при любой ошибке не слать `save`, а перезагрузить плату без сохранения. Нюанс: `defaults nosave` внутри пакета сбрасывает флаг ошибки, но не сам пакет (`cli.c:4296` в 4.5.3, `:4374` в 2025.12). Вывод `diff all` сам начинается с `batch start` и `defaults nosave` — вставка `diff all` сначала сбрасывает всё к умолчаниям.

### Грабли 6: diff не переносится между версиями
Имена и смысл параметров меняются между версиями прошивки: переименовываются `debug_mode`, меняется синтаксис команды `serial`, меняется смысл PID-параметров D-term. Вставлять `diff all` от 4.5 в 2025.12 (и наоборот) построчно нельзя: таблица отличий — в модуле «Введение в Betaflight», раздел «Переход 4.5.3 → 2025.12». Переносить настройки между версиями — только осмысленно, по разделам, с перечитыванием.

Что происходит на деле — из лабораторной. `diff all` 4.5.3 с `d_roll = 30` и `d_min_roll = 20`, вставленный в 2025.12.5 как есть, дал одну ошибку `INVALID NAME: d_min_roll = 20`, и пакет не сохранился — это хороший исход. Плохой — «починить» переименованием: `d_max_roll = 20` при `d_roll = 30` прошивка обнулила при сохранении, а `d_roll = 30`, принятый без ошибок, в 2025.12 означает базовый D, а не пиковый (умолчания: 4.5.3 — D 40 и `d_min` 30; 2025.12 — D 30 и `d_max` 40; `flight/pid.h`). Строка «без ошибок» — не значит «тот же тюн».

{{lesson:bf-intro|Полная таблица переименований и смены смысла параметров 4.5.3 → 2025.12 — там.}}

### Почему диф, а не дамп
`diff all` содержит только отличия от дефолтов — его можно читать глазами и хранить в git. `dump` — всё подряд, при обновлении прошивки он тащит старые дефолты как явные значения.

Формат вывода (`cli.c`, `printConfig`): строка `# version` и строка версии с датой сборки, `batch start`, `defaults nosave`, `mcu_id`, `signature` (для `diff all`), `# name: …`, блоки `# feature`, `# master` с `set …`, затем `profile 0…3` и `rateprofile 0…3` со своими `set`, возврат к активным профилям и в конце `save`. После `save` строки `batch end` нет: прошивка снимает флаг пакета, раз сохранение уже в выводе (в лабораторном выводе это видно). Ловушка для скрипта, который читает вывод: строки-комментарии `\r\n# version`, `\r\n# master` начинаются ровно как приглашение. Если кусок данных случайно закончился на `\r\n# `, наивный «читать до приглашения» оборвёт бэкап на середине. Надёжный признак конца — приглашение в конце буфера и после него 0.3 с тишины (ориентир курса; на USB и TCP хватает с запасом).

| Команда | 4.5.3 | 2025.12.5 | Что вернёт / сделает |
|---|---|---|---|
| `#` (байт) | вход в CLI | вход в CLI | после 100 мс тишины; не на армленом аппарате |
| `0x02` … `0x03` | нет (в 4.5.5 есть) | один сеанс без эха и перезагрузки | вывод команд, окно 2 с; заканчивать `0x03` |
| `get <подстрока>` | есть | есть | все совпадения по подстроке + диапазон/умолчание |
| `set <имя> = <v>` | есть | есть | `<имя> set to <v>` или `###ERROR IN set: INVALID NAME/VALUE###` |
| `batch start` / `batch end` | есть | есть | при ошибке в пакете `save` отказывает |
| `diff all` | есть | есть | `batch start`, `defaults nosave`, …, `save` |
| `save` | сохранить + перезагрузка | сохранить + перезагрузка | `# saving`; перед записью — `validateAndFixConfig` |
| `save noreboot` | аргумент игнорируется: перезагрузка | без перезагрузки | в 4.5.5 тоже есть |
| `exit` | перезагрузка | перезагрузка | `unsaved changes lost` |
| `exit noreboot` | аргумент игнорируется: перезагрузка | без перезагрузки | запрет арма `CLI` остаётся до перезагрузки |

### Минимальный скрипт выгрузки `diff all` (pyserial)
```python
import serial, time, sys, glob, re

def cli(port, cmds, timeout=3.0):
    """Open CLI, run commands, return full text. Do not send 'exit' (reboots on 4.5.3)."""
    with serial.Serial(port, 115200, timeout=0.2) as s:
        s.write(b"#\n"); time.sleep(0.5); s.read(4096)   # "#\n": safe if the FC is already in CLI
        out = ""
        for c in cmds:
            s.write((c + "\n").encode()); t0 = time.time(); buf = ""
            while time.time() - t0 < timeout:
                chunk = s.read(4096).decode(errors="replace")
                if chunk: buf += chunk; t0 = time.time()
                elif buf.endswith("\r\n# "): break   # prompt AND a quiet read: end of output
            out += buf
        return out

ports = glob.glob("/dev/ttyACM*")                              # Linux; Windows: COM*
for p in ports:
    name = cli(p, ["get craft_name"])
    if re.search(r"^craft_name = viking7\r?$", name, re.M):   # anchored: not viking70
        text = cli(p, ["version", "diff all"])
        open("viking7/betaflight/diff-all.txt", "w").write(text)
        break
else:
    sys.exit("craft not found")
```
Нормализация перед коммитом: убрать строки с датой/временем из `version` и `# ` эхо, отсортировать блоки — иначе `git diff` шумит (модуль «CI»). Этот короткий вариант входит в CLI на каждом порту ради имени — для разового бэкапа терпимо (порт закрывается без `exit`, плата остаётся в CLI с запретом арма до переподключения питания); для парка ищи плату по `MSP_NAME`, как в практике.

### Что автоматизировать стоит, а что нет
Стоит: бэкап `diff all` перед каждым полётным днём; проверка инвариантов (failsafe, poles, bidir) по выгрузке; массовая смена `craft_name`/VTX-таблицы на парке; выгрузка логов через `msc`. Не стоит: массовая «накатка PID» на разные аппараты (разная механика), любые изменения без перечитывания `get` после `save`.

{{diagram:bf-cli-session|Сессия CLI по serial: ждать приглашение, перечитывать значения после set, после save искать порт заново.}}

### Место в системе

- **Получает:** текстовый CLI по USB и команды `diff all`, `get`, `set`, `save` (`bf-cli`); MSP для опознания платы; таблицу переименований между 4.5 и 2025.12 (`bf-intro`); уникальный `craft_name` каждого аппарата.
- **Отдаёт:** `diff all` перед полётным днём — в git и на проверку инвариантов в CI (`eng-ci-configs`); фактические значения после перезагрузки для failsafe, числа полюсов и bidir (`bf-failsafe`, `bf-rpm-filter`).
- **Если ошибиться здесь:** не перечитал `get` после `save` → прошивка тихо обнулила `d_max` или вернула failsafe в `DROP` → на аппарате не то, что в твоей записи; вскроется в полёте как другой тюн (`bf-pid`) или как падение вместо возврата (`bf-failsafe`). Вставил `diff all` от 4.5 в 2025.12 построчно и «починил» имена → `d_roll` принят, но означает уже базовый D, а не пиковый → тюн другой; таблица — в `bf-intro`.

## practice
Главный путь — без платы: Betaflight 4.5.3 и 2025.12.5 собираются под Linux как SITL (программа, в которой работает настоящий код прошивки), и её UART1 доступен как TCP-порт 5761. pyserial открывает его той же функцией, что и USB-порт (`serial.serial_for_url("socket://127.0.0.1:5761")`), поэтому скрипт отличается от «железного» одной строкой. `save` в SITL вызывает `systemReset()`, а она — `exit(0)` (`target/SITL/sitl.c`): перезагрузка выглядит как завершение процесса, и скрипт перезапускает его в той же папке, где лежит `eeprom.bin`, — ровно как плата загружается со своей flash.

### Шаг 1. Собрать SITL двух версий
Исходники — теги `4.5.3` и `2025.12.5` репозитория betaflight/betaflight. Makefile требует `arm-none-eabi-gcc` даже для SITL (`mk/tools.mk:266`); официальный путь — `make arm_sdk_install`. Для SITL кросс-компилятор на деле не используется, поэтому хватает подставить системный gcc под ожидаемыми именами; 2025.12 ещё требует папку `src/config` (её заполняет `make configs` клоном betaflight/config; для SITL достаточно пустой `src/config/configs` — вывод из `mk/config.mk`). Сборка заняла 12 с и 8 с.

```bash
mkdir -p fakesdk/bin && for t in gcc g++ gdb objcopy objdump readelf size; do
  ln -sf /usr/bin/$t fakesdk/bin/arm-none-eabi-$t; done
(cd bf453 && make TARGET=SITL ARM_SDK_DIR=$PWD/../fakesdk -j8)      # -> obj/main/betaflight_SITL.elf
(cd bf2025 && mkdir -p src/config/configs && make SITL ARM_SDK_DIR=$PWD/../fakesdk -j8)
                                                                     # -> obj/betaflight_2025.12.5_SITL
```

### Шаг 2. Лабораторный скрипт
Скрипт делает шесть шагов: (1) опознание по MSP; (2) пакет `set` и `save` на 4.5.3; (3) поиск по `MSP_NAME` после «перезагрузки», перечитывание каждого ключа и выгрузка `diff all`; (4) вставка этого `diff all` в 2025.12.5 как есть; (5) «перенос» переименованием `d_min_roll → d_max_roll`, `save noreboot`, перечитывание, неинтерактивный запрос STX/ETX; (6) сравнение двух `diff all` по ключам. Запуск: `python3 -I bf_cli_lab.py <SITL 4.5.3> <SITL 2025.12.5> work`; порт 5761 должен быть свободен — скрипт проверяет это сам, иначе ответил бы чужой SITL (так и случилось при первом прогоне: оставшийся процесс 2025.12 отвечал вместо свежего 4.5.3).

```python
"""Betaflight CLI + MSP automation lab on SITL (4.5.3 and 2025.12.5).

The same functions work on a real FC over USB: replace open_port() with
serial.Serial("/dev/ttyACM0", 115200, timeout=0.2) (Windows: "COM8").
Usage: python3 bf_cli_lab.py <sitl-4.5.3> <sitl-2025.12.5> <workdir>
"""
import os, re, socket, subprocess, sys, time
import serial  # pyserial 3.5

PROMPT = b"\r\n# "
ERR = re.compile(r"###ERROR IN (\w+): (.*?)###")


def open_port(url="socket://127.0.0.1:5761", tries=50):
    for _ in range(tries):               # SITL needs ~0.5 s to bind its TCP "UART1"
        try:
            return serial.serial_for_url(url, timeout=0.2)
        except (serial.SerialException, OSError):
            time.sleep(0.1)
    raise RuntimeError("port did not open")


def msp(port, cmd, payload=b""):
    """MSP v1: '$M<' size cmd payload xor; reply '$M>' (or '$M!' = unsupported)."""
    body = bytes([len(payload), cmd]) + payload
    ck = 0
    for b in body:
        ck ^= b
    port.reset_input_buffer()
    port.write(b"$M<" + body + bytes([ck]))
    buf, t_end = b"", time.time() + 1.0
    while time.time() < t_end:
        buf += port.read(256)
        i = buf.find(b"$M")
        if i >= 0 and len(buf) >= i + 6 and len(buf) >= i + 6 + buf[i + 3]:
            n = buf[i + 3]
            if buf[i + 2:i + 3] != b">":
                raise IOError(f"MSP {cmd}: error reply")
            ck = 0
            for b in buf[i + 3:i + 5 + n]:
                ck ^= b
            if ck != buf[i + 5 + n]:
                raise IOError(f"MSP {cmd}: bad checksum")
            return buf[i + 5:i + 5 + n]
    raise TimeoutError(f"MSP {cmd}: no reply")


def identify(port):
    api = msp(port, 1)            # MSP_API_VERSION: protocol, major, minor
    variant = msp(port, 2)        # MSP_FC_VARIANT: 'BTFL'
    ver = msp(port, 3)            # MSP_FC_VERSION: 4.5.3 or 25.12.5 (calver: year-2000)
    name = msp(port, 10)          # MSP_NAME: craft_name
    uid = msp(port, 160)          # MSP_UID: 3 x uint32 MCU unique id
    return {"api": f"{api[1]}.{api[2]}", "variant": variant.decode(),
            "version": ".".join(str(x) for x in ver[:3]),
            "name": name.decode(errors="replace"), "uid": uid.hex()}


def read_prompt(port, timeout=8.0, quiet=0.3):
    """Read until the CLI prompt AND then `quiet` s of silence: comment lines of
    `diff` ('\\r\\n# version') look exactly like the prompt at a chunk boundary."""
    buf, t_end = b"", time.time() + timeout
    while time.time() < t_end:
        chunk = port.read(4096)
        buf += chunk
        if buf.endswith(PROMPT) and not chunk:
            t_quiet = time.time() + quiet
            while time.time() < t_quiet and not (chunk := port.read(4096)):
                pass
            if not chunk:
                return buf.decode(errors="replace")
            buf += chunk
    raise TimeoutError(f"no prompt after {len(buf)} bytes")


def cli_enter(port):
    port.write(b"#")              # non-MSP '#', handled after 100 ms idle; ignored while ARMED
    return read_prompt(port)


def cli(port, cmd, timeout=8.0):
    port.write(cmd.encode() + b"\n")
    out = read_prompt(port, timeout)
    lines = out.replace("\r", "").split("\n")[1:-1]  # drop echo and prompt
    return "\n".join(lines).strip("\n"), ERR.findall(out)


def get(port, key):
    """`get` is a substring search: `get d_roll` also prints align_board_roll."""
    out, _ = cli(port, f"get {key}")
    return re.search(rf"^{re.escape(key)} = (.*)$", out, re.M)[1].strip()


def start_sitl(binary, workdir):
    with socket.socket() as s:            # a leftover SITL would answer instead of ours
        if s.connect_ex(("127.0.0.1", 5761)) == 0:
            sys.exit("port 5761 busy: another SITL is running")
    os.makedirs(workdir, exist_ok=True)
    PROCS.append(subprocess.Popen([binary], cwd=workdir, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL))
    return PROCS[-1]


def wait_reboot(port, proc):
    """On SITL `save` = systemReset() = exit(0); on a real FC the USB device re-enumerates."""
    try:
        while port.read(4096):
            pass
    except (serial.SerialException, OSError):
        pass
    port.close()
    return proc.wait(timeout=5)


def parse_diff(text):
    """`diff all` -> {(context, key): value}; context = master / profile N / rateprofile N."""
    ctx, out = "master", {}
    for line in text.replace("\r", "").split("\n"):
        line = line.strip()
        if m := re.match(r"(profile|rateprofile) (\d)$", line):
            ctx = f"{m[1]} {m[2]}"
        elif m := re.match(r"set (\S+) = (.*)$", line):
            out[(ctx, m[1])] = m[2]
        elif line and not line.startswith("#") and line.split()[0] in (
                "feature", "serial", "aux", "resource", "beacon", "map", "led", "vtxtable"):
            out[(ctx, line)] = "line"
    return out


CHANGES = {"craft_name": "viking2", "failsafe_delay": "10",
           "failsafe_procedure": "GPS-RESCUE", "d_roll": "30", "d_min_roll": "20"}

PROCS = []


def run(bin453, bin2025, work):
    w453 = os.path.join(work, "fc453")
    print("== 1. MSP identify (no CLI, no reboot)")
    proc = start_sitl(bin453, w453)
    p = open_port()
    print("  ", identify(p))

    print("== 2. CLI: batch of set, then save")
    cli_enter(p)
    print("  ", cli(p, "batch start")[0])
    for k, v in CHANGES.items():
        print("  ", cli(p, f"set {k} = {v}")[0].splitlines()[0])
    print("  ", cli(p, "batch end")[0])
    p.write(b"save\n")
    print("   save -> FC reboots, SITL exit code", wait_reboot(p, proc))

    print("== 3. after reboot: find by MSP_NAME, re-read every key with get")
    proc = start_sitl(bin453, w453)
    p = open_port()
    print("   MSP_NAME =", identify(p)["name"])
    cli_enter(p)
    print("   raw `get d_roll`:", cli(p, "get d_roll")[0].replace("\n", " | "))
    for k, v in CHANGES.items():
        got = get(p, k)
        print(f"   {'OK  ' if got == v else 'FAIL'} {k:20s} wrote {v:10s} read {got}")
    diff453, _ = cli(p, "diff all", timeout=15)
    open(os.path.join(work, "viking2_4.5.3_diff.txt"), "w").write(diff453 + "\n")
    print(f"   diff all: {len(diff453.splitlines())} lines saved")
    p.close(); proc.terminate(); proc.wait()

    print("== 4. paste the 4.5.3 diff into 2025.12.5 as is")
    proc = start_sitl(bin2025, os.path.join(work, "fc2025"))
    p = open_port()
    print("  ", identify(p))
    cli_enter(p)
    errors = []
    for line in diff453.splitlines():
        if line.strip() and not line.startswith("#") and line.strip() != "save":
            errors += cli(p, line)[1]
    for e in errors:
        print("   ERROR", e)
    print("  ", cli(p, "save noreboot")[0].replace("\n", " | "))

    print("== 5. 'port' by renaming d_min_roll -> d_max_roll, save noreboot")
    cli(p, "defaults nosave")
    ported = {("d_max_roll" if k == "d_min_roll" else k): v for k, v in CHANGES.items()}
    for k, v in ported.items():
        cli(p, f"set {k} = {v}")
    print("  ", cli(p, "save noreboot")[0])
    for k, v in ported.items():
        got = get(p, k)
        print(f"   {'OK  ' if got == v else 'FAIL'} {k:20s} wrote {v:10s} read {got}")
    diff2025, _ = cli(p, "diff all", timeout=15)
    open(os.path.join(work, "viking2_2025.12.5_diff.txt"), "w").write(diff2025 + "\n")
    p.write(b"exit noreboot\n"); time.sleep(1.0)
    print("  ", p.read(4096).decode().strip().replace("\r\n", " | "),
          "| SITL alive:", proc.poll() is None, "| MSP_NAME:", identify(p)["name"])
    p.write(b"\x02get failsafe_delay\n\x03"); time.sleep(0.5)  # 2025.12: one-shot CLI, STX..ETX
    print("   STX/ETX:", p.read(4096))
    p.close(); proc.terminate(); proc.wait()

    print("== 6. semantic diff 4.5.3 -> 2025.12.5 (by key, not by text line)")
    a, b = parse_diff(diff453), parse_diff(diff2025)
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key):
            print(f"   {key[0]:10s} {key[1]:20s} {a.get(key, '-'):>10s} -> {b.get(key, '-')}")


if __name__ == "__main__":
    try:
        run(*sys.argv[1:4])
    finally:
        for pr in PROCS:
            if pr.poll() is None:
                pr.terminate()
```

```text
== 1. MSP identify (no CLI, no reboot)
   {'api': '1.46', 'variant': 'BTFL', 'version': '4.5.3', 'name': '', 'uid': '000000000100000002000000'}
== 2. CLI: batch of set, then save
   Command batch started
   craft_name set to viking2
   failsafe_delay set to 10
   failsafe_procedure set to GPS-RESCUE
   d_roll set to 30
   d_min_roll set to 20
   Command batch ended
   save -> FC reboots, SITL exit code 0
== 3. after reboot: find by MSP_NAME, re-read every key with get
   MSP_NAME = viking2
   raw `get d_roll`: align_board_roll = 0 | Allowed range: -180 - 360 |  | d_roll = 30 | profile 0 | Allowed range: 0 - 250 | Default value: 40
   OK   craft_name           wrote viking2    read viking2
   OK   failsafe_delay       wrote 10         read 10
   OK   failsafe_procedure   wrote GPS-RESCUE read GPS-RESCUE
   OK   d_roll               wrote 30         read 30
   OK   d_min_roll           wrote 20         read 20
   diff all: 51 lines saved
== 4. paste the 4.5.3 diff into 2025.12.5 as is
   {'api': '1.47', 'variant': 'BTFL', 'version': '25.12.5', 'name': '', 'uid': '000000000100000002000000'}
   ERROR ('set', 'INVALID NAME: d_min_roll = 20')
   ###ERROR IN save: ERRORS WERE DETECTED - PLEASE REVIEW BEFORE CONTINUING### | ###ERROR IN save: PLEASE FIX ERRORS THEN 'SAVE'###
== 5. 'port' by renaming d_min_roll -> d_max_roll, save noreboot
   # saving
   OK   craft_name           wrote viking2    read viking2
   OK   failsafe_delay       wrote 10         read 10
   FAIL failsafe_procedure   wrote GPS-RESCUE read DROP
   OK   d_roll               wrote 30         read 30
   FAIL d_max_roll           wrote 20         read 0
   exit noreboot |  | # leaving CLI mode, no reboot | SITL alive: True | MSP_NAME: viking2
   STX/ETX: b'\x02failsafe_delay = 10\r\nAllowed range: 1 - 200\r\nDefault value: 15\r\n\x03'
== 6. semantic diff 4.5.3 -> 2025.12.5 (by key, not by text line)
   master     failsafe_procedure   GPS-RESCUE -> -
   profile 0  d_max_roll                    - -> 0
   profile 0  d_min_roll                   20 -> -
   profile 0  d_roll                       30 -> -
```

### Шаг 3. Что доказывает каждая строка вывода
- Шаг 1 вывода: опознание прошло по MSP, плата не входила в CLI. Версия 4.5.3 пришла как `4.5.3`, 2025.12.5 — как `25.12.5`: проверка версии по первому байту сломалась бы.
- Шаг 2–3: все пять значений на 4.5.3 пережили `save` и загрузку — `OK`. Строка `raw get d_roll` показывает, почему разбирать ответ надо с якорем: первой пришла `align_board_roll = 0`.
- Шаг 4: единственная ошибка — `d_min_roll`, и из-за неё пакет не сохранился вовсе; это правильное поведение, а не сбой.
- Шаг 5: после «переноса» переименованием два `FAIL`: `failsafe_procedure` стал `DROP` (GPS-спасения в SITL нет, значение вне перечня — проверка 2025.12), `d_max_roll` стал 0 (меньше `d_roll`). Ни одна команда не напечатала ошибку — это и есть тихие исправления. `exit noreboot` оставил SITL живым, MSP снова отвечает.
- Шаг 6: построчный `git diff` двух файлов показал бы и смену строки версии с датой сборки; сравнение по ключам показывает четыре настоящих изменения смысла, в том числе исчезновение `d_roll = 30` из diff 2025.12 — там 30 уже умолчание.

{{diagram:bf-cli-apply-verify|Скрипт правки: бэкап, set и save, поиск порта заново после перезагрузки, get по каждому ключу и второй бэкап — git diff должен показать ровно строки CHANGES.}}

### Шаг 4. Хранить конфиги как код
1. Папка на каждый дрон, внутри `configs/` и `logs/`.
2. Имя файла: `<дрон>_<плата>_<ГГГГ-ММ-ДД>_diff.txt` — сортировка по имени = сортировка по дате.
3. Перед изменениями — бэкап, после — новый `diff all` (`viking2_after_diff.txt`, той же командой, что и бэкап); сравнивать их обычным `git diff`. Именно `diff all`, а не просто `diff`: простой `diff` сохраняет только текущий PID- и рейт-профиль, остальные три пары профилей в бэкап не попадут.
4. Строку `# Betaflight / … <дата сборки>` перед коммитом оставь, но сравнивай файлы по ключам (`parse_diff` из скрипта): дата сборки меняется при каждой перепрошивке и в построчном diff выглядит как изменение конфига.

### Переход на реальное железо
Пропеллеры сняты на всё время работы; батарея не нужна — USB питает FC, и ESC без силового питания не крутят моторы. Подключи по USB две платы, закрой Configurator (он держит порт и засыпает его MSP-трафиком). Порты на реальной машине — `/dev/ttyACM*` или `COM*`; поиск по `MSP_NAME` — тот же `identify()` из лабораторного скрипта, только по списку портов `list_ports.comports()`. Проверено на SITL с одним мёртвым и одним живым портом:

```python
"""Find an FC by craft_name over MSP: no CLI, no reboot, no arming lock. Usage: find_craft.py NAME [port ...]"""
import sys
import serial
from serial.tools import list_ports
from bf_cli_lab import identify   # msp() + MSP_API_VERSION/FC_VARIANT/FC_VERSION/NAME/UID from the lab


def find_craft(name, ports=None):
    ports = ports or [p.device for p in list_ports.comports()]   # /dev/ttyACM*, COM*
    for dev in ports:
        try:
            with serial.serial_for_url(dev, baudrate=115200, timeout=0.2) as p:
                info = identify(p)
        except (serial.SerialException, OSError, TimeoutError) as e:
            print(f"  {dev}: no MSP ({type(e).__name__})")
            continue
        print(f"  {dev}: {info['variant']} {info['version']} name={info['name']!r} uid={info['uid']}")
        if info["name"] == name:
            return dev, info
    raise RuntimeError(f"FC {name!r} not found")


if __name__ == "__main__":
    print(find_craft(sys.argv[1], sys.argv[2:] or None))
# python3 find_craft.py viking2 socket://127.0.0.1:5768 socket://127.0.0.1:5761   (SITL 2025.12.5 running)
#   socket://127.0.0.1:5768: no MSP (SerialException)
#   socket://127.0.0.1:5761: BTFL 25.12.5 name='viking2' uid=000000000100000002000000
# ('socket://127.0.0.1:5761', {'api': '1.47', 'variant': 'BTFL', 'version': '25.12.5', 'name': 'viking2', 'uid': '000000000100000002000000'})
```

Затем на каждой плате: бэкап `diff all`, пакет `set` из `CHANGES`, `save`, поиск порта заново (на Windows номер COM может смениться; жди до 10 с в цикле — ориентир курса), перечитывание каждого ключа. Прервать: плата не нашлась за 10 с после `save` — не повторять запись, переподключить USB и начать с бэкапа; любая строка `###ERROR` в пакете — не слать `save`. Критерии на железе: обе платы найдены по имени без входа в CLI; после `save` каждый ключ из `CHANGES` перечитан со статусом `OK` или объяснённым `FAIL` (исправление прошивкой, которое ты можешь назвать по таблице выше); `diff all` до и после различается ровно строками из `CHANGES` и ничем больше; прогон на второй плате идёт без правки кода — меняется только `craft_name` в аргументах.

Самопроверка: лабораторная выполнена, когда (SITL) обе версии собраны и отвечают по MSP: 4.5.3 — API 1.46 и версия `4.5.3`, 2025.12.5 — API 1.47 и версия `25.12.5`; после `save` на 4.5.3 процесс завершается с кодом 0, а после перезапуска все пять ключей — `OK`; вставка `diff all` 4.5.3 в 2025.12.5 даёт ровно одну ошибку `INVALID NAME: d_min_roll = 20` и отказ `save`; после переименования ровно два `FAIL` — `failsafe_procedure → DROP` и `d_max_roll → 0`; запрос STX/ETX возвращает `failsafe_delay = 10`, обрамлённый байтами `\x02` и `\x03`; сравнение по ключам выводит 4 строки. На железе — критерии из раздела «Переход на реальное железо».

**Эталон для самопроверки.** Верный вывод совпадает с приведённым выше, кроме даты сборки в строке версии и хэша коммита. Типичные неверные: (1) на шаге 3 `FAIL d_roll … read 0` — ответ `get` разобран без якоря, совпала строка `align_board_roll`; (2) шаг 1 сразу показывает `25.12.5` и `name: viking2` — на порту 5761 ответил оставшийся с прошлого запуска SITL 2025.12, а свой не смог занять порт; (3) скрипт виснет после `exit noreboot` — после выхода из CLI приглашения нет, читать надо по таймауту, а не до `# `; (4) на 4.5.3 нет ни одного `FAIL`, а ты ждал исправления failsafe — в 4.5.3 нет проверки «значение вне перечня → DROP», а правило «GPS-RESCUE без feature GPS» в SITL не собрано (GPS в SITL нет); на полётной плате с GPS-сборкой оно сработает.

## diagnostics
- **Симптом:** скрипт «потерял» дрон после save
  - Возможная причина: после перезагрузки COM-порт получил другой номер.
  - Что сделать: искать порт заново по `craft_name` через `MSP_NAME`, а не по номеру.
- **Симптом:** записанное значение после перезагрузки другое
  - Возможная причина: Betaflight скорректировал несовместимую комбинацию в `validateAndFixConfig` (`d_max` < D, GPS-RESCUE без GPS, bidir без DShot).
  - Что сделать: перечитать связанные параметры, сверить с таблицей исправлений выше и с документацией платы и прошивки.
- **Симптом:** после вставки diff часть строк дала ошибки `Invalid name`
  - Возможная причина: diff от другой версии прошивки.
  - Что сделать: переносить настройки по разделам, проверяя имена параметров в `help` текущей версии.
  - Последствия: если пакет был открыт `batch start`, первый `save` откажет и ничего не сохранится (в RAM изменения остаются до перезагрузки; повторный `save` их сохранит); без пакета применится всё, кроме ошибочных строк.
- **Симптом:** два дрона откликаются на один `craft_name`
  - Возможная причина: одинаковые имена (клон конфига).
  - Что сделать: сразу переименовать, `set craft_name = ...` + `save`; хранить рядом с именем `MSP_UID`.
- **Симптом:** `save noreboot` перезагрузил плату
  - Возможная причина: прошивка 4.5.3 или старше: аргумент не читается.
  - Что сделать: определить версию по MSP до записи и на 4.5.3 всегда ждать перезагрузки.
- **Симптом:** после `exit noreboot` аппарат не армится
  - Возможная причина: 2025.12 оставляет флаг запрета арма `CLI` до перезагрузки.
  - Что видно в логе: `status` → `Arming disable flags: CLI`.
  - Что сделать: перезагрузить плату перед полётом; для чтения значений использовать MSP или STX/ETX.
- **Симптом:** бэкап `diff all` обрывается на середине
  - Возможная причина: чтение «до `# `» сработало на строке-комментарии `# master` на границе куска данных; или фиксированный таймаут меньше времени вывода на большом конфиге F7/H7.
  - Что сделать: конец вывода — приглашение и 0.3 с тишины; проверять, что файл заканчивается строкой `save`.

## references
- Betaflight — source code: src/main/cli/cli.c, msp/msp_serial.c, msp/msp.c, config/config.c (теги 4.5.3, 2025.12.5) | https://github.com/betaflight/betaflight | primary | A
- Betaflight CLI — Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- pySerial — Documentation (serial_for_url, socket://) | https://pyserial.readthedocs.io/en/latest/ | primary | A

## checklist
- У каждого дрона уникальный `craft_name`, рядом записан `MSP_UID`
- Скрипт ищет порт по `MSP_NAME`, а не по номеру COM и не входом в CLI
- Перед изменениями сохраняется `diff all` с датой в имени
- После `save` скрипт заново находит порт и перечитывает значения `get` с якорем `^имя = `
- `save noreboot` на 4.5.3 считается перезагрузкой
- Ошибки `###ERROR` в пакете останавливают `save`
- diff между разными версиями прошивки не вставляется построчно
