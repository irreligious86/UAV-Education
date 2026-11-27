---
id: inav-cli-backup
title: "CLI INAV: все команды, diff/dump и профили, бэкап, восстановление и переезд 7 → 8 → 9"
level: L2
readingTime: 50 мин
firmware: INAV 9.1 (сверено с 9.1.0)
status: published
added: 2026-11-18
tags:
  - INAV
  - CLI
  - diff
  - бэкап
  - миграция
related:
  - inav-intro
  - inav-setup-scratch
  - inav-mixer-vtol
  - inav-osd-hd
  - inav-ipf
  - bf-cli
  - bf-cli-automation
next:
  - inav-mixer-vtol
---

## summary
CLI INAV — единственное место, где конфигурация аппарата видна целиком и текстом: 62 команды в 9.1.0, 677 настроек, три вида профилей. Модуль разбирает команды с их аргументами и опасностями, показывает, что именно печатают `diff`, `diff all` и `dump` и чем они отличаются, что в бэкап не попадает, в каком порядке конфиг восстанавливают и что означают красные строки `### ERROR`. Отдельно — `status` с 24 флагами блокировки арма, `tasks`, `feature`, авто-бэкап и миграция в Configurator 9.1 и таблица переезда 7 → 8 → 9. Лабораторная без железа и без симулятора: по фрагменту `diff all` аппарата на 8.0.1 ты размечаешь каждую строку для 9.1, считаешь, что потерял бы обычный `diff`, собираешь порядок восстановления и расшифровываешь строку флагов из `status`.

## theory
### Вход в CLI и что он делает с аппаратом
CLI открывается символом `#` на порту MSP (вкладка CLI в Configurator делает это сама). Пока CLI открыт, стоит флаг блокировки арма `CLI`, логические условия (`inav-ipf`) не выполняются, OSD по MSP не обновляется. Выйти можно тремя способами, и все три перезагружают полётник: `save` (записать и перезагрузить), `exit` (перезагрузить без записи), `defaults` (сбросить и перезагрузить). Аргумента `noreboot` у `save` и `exit` в INAV нет — в отличие от Betaflight 2025.12 (`bf-cli`).

Всё после `#` в строке CLI отбрасывает, поэтому файл бэкапа с комментариями вставляется как есть. Ошибка всегда начинается с `### ERROR: ` (в Betaflight — `###ERROR IN`): клиент из `bf-cli-automation` переносится на INAV заменой этой строки и логики выхода.

### Все команды INAV 9.1.0
В `cmdTable[]` 9.1.0 — 62 команды (в 8.0.1 — 61, добавлена `bind_msp_rx`; убранных нет). Часть собирается не во все прошивки: условие стоит в скобках. `help` печатает список; на платах с флешем ≤ 512 КБ (F411, F722) — только имена, без описаний и аргументов.

| Команда | Аргументы | Что делает | Когда опасна |
|---|---|---|---|
| `help` | — | список команд | — |
| `version` | — | `# INAV/<target> <версия> <дата> / <время> (<git>)` и версия GCC | — |
| `status` | — | версия, uptime, напряжение, датчики, нагрузка, флаги арма, OSD, VTX, GPS | — |
| `tasks` | — | частота, время и нагрузка каждой задачи планировщика | — |
| `get` | `[часть имени]` | значения всех настроек, в имени которых есть подстрока, с диапазоном | — |
| `set` | `<имя> = <значение>`; пусто или `*` — весь список | меняет настройку в ОЗУ до `save` | значение вне диапазона отвергается, но осмысленность не проверяется |
| `save` | — | запись в EEPROM и перезагрузка | в пакете с ошибками первая `save` откажет |
| `exit` | — | выход с перезагрузкой, без записи | останавливает моторы, запущенные `motor` |
| `defaults` | `[noreboot]` | сброс всей конфигурации и запись; без аргумента — перезагрузка | стирает всё сразу, `save` не нужен |
| `batch` | `start` · `end` | пакетный режим: считает ошибки, `save` при ошибках отказывает [USE_CLI_BATCH] | — |
| `diff` | `master` · `control_profile` · `mixer_profile` · `battery_profile` · `all`, затем `[showdefaults]`; всё необязательно | отличия от умолчаний | без `all` — неполный бэкап |
| `dump` | те же | вся конфигурация, включая умолчания | при переносе между версиями тащит старые умолчания |
| `control_profile` | `[1…3]` | показать или выбрать control-профиль (PID, рейты, EZ Tune — их числа разобраны в `inav-mc-tuning`) | при смене индекса сразу пишет EEPROM |
| `mixer_profile` | `[1…2]` | профиль миксера (на F411 он один) | то же; меняет платформу и выходы |
| `battery_profile` | `[1…3]` | батарейный профиль | то же |
| `feature` | `list` · `<имя>` · `-<имя>` | включённые функции; включить; выключить | имя сравнивается по началу строки |
| `beeper`, `blackbox` | `list` · `<имя>` · `-<имя>` | условия пищалки; группы полей Blackbox | — |
| `map` | `[AETR…]` | порядок каналов | неверная карта — газ на другом стике |
| `rxrange` | `<канал> <min> <max>` | диапазон канала приёмника | — |
| `aux` | `<№> <id режима> <AUX> <от> <до>` | диапазоны режимов | ARM без проверки тумблера |
| `adjrange` | `<№> <слот> <AUX> <от> <до> <функция> <AUX подстройки>` | подстройки в полёте (формат и функции — `inav-adjustments`) | — |
| `serial` | `<id> <маска> <msp> <gps> <телем.> <периф.>`; `<id> +n` · `<id> -n` | функции и скорости UART | снять MSP с порта, через который подключён, — потерять связь с Configurator |
| `mmix`, `smix` | строки миксера; `reset` | миксер моторов и серв активного профиля (`inav-mixer-vtol`) | `reset` стирает правила профиля |
| `servo` | `<№> <min> <max> <mid> <rate>` | концы, центр и расход сервы | — |
| `timer_output_mode` | `[таймер [режим]]`, режим `AUTO` · `MOTORS` · `SERVOS` · `LED` | назначение таймера | мотор на выходе сервы и наоборот |
| `motor` | `<№> [1000…2000]` | значение на выходе мотора без арма | **мотор крутится — только без пропов** |
| `resource` | — | только просмотр: какой вывод чем занят | переназначить вывод нельзя |
| `safehome`, `fwapproach`, `geozone`, `wp` | свои строки; `reset`; у `wp` ещё `load`, `save` | safehome, заход на посадку, геозоны [флеш > 512 КБ], миссия | `reset` стирает список |
| `logic`, `gvar`, `pid` | свои строки; `reset` | программный фреймворк (`inav-ipf`) | логика может менять газ и режимы |
| `osd_layout`, `osd_custom_elements` | свои строки | раскладки и свои элементы OSD (`inav-osd-hd`) | — |
| `led`, `color`, `mode_color`, `ledpinpwm` | свои строки | лента и вывод LED [USE_LED_STRIP] | — |
| `temp_sensor` | свои строки | датчики температуры | — |
| `gpspassthrough`, `serialpassthrough` | —; `<id> [baud] [mode] [options]` | мост USB ↔ UART (u-center, прошивка приёмника) | выход только отключением питания |
| `gpssats` | — | таблица спутников u-blox | — |
| `bind_rx`, `bind_msp_rx`, `eleres_bind` | —; `<порт>`; — | привязка SRXL2; MSP-приёмника mLRS (с 9.1); EleRes | — |
| `flash_info`, `flash_erase`, `sd_info` | — | флеш логов и SD-карта | `flash_erase` стирает все логи Blackbox |
| `flash_read`, `flash_write` | `<длина> <адрес>`; `<адрес> <текст>` | сырой доступ к флешу [USE_FLASH_TOOLS] | портит логи |
| `msc` | — | перезагрузка в режим USB-накопителя | только если есть флеш или SD |
| `dfu` | — | перезагрузка в загрузчик DFU | полётник «пропадает» до прошивки или переподключения |
| `bootlog`, `assert` [отладочные сборки: USE_BOOTLOG, USE_ASSERT]; `memory`, `showdebug` (в любой сборке) | — | журнал загрузки, память, отладка | — |
| `cli_delay` | `<мс>`; пусто — выключить | пауза между строками CLI | — |
| `play_sound` | `[№]` | проиграть сигнал пищалки | — |

Три ловушки для пришедших с Betaflight. `resource` только показывает выводы: функции переносят через `timer_output_mode` или свой target. `bind_rx` не привязывает CRSF/ELRS. `feature gp` включит `GPS`: имя сравнивается по первым введённым буквам, поэтому пиши имена целиком. Имён 23, список — `feature list`; в бэкапе они выглядят как `feature GPS` и `feature -AIRMODE`.

### `diff`, `diff all`, `dump`: что печатает каждая
Настройка в `settings.yaml` принадлежит одному из разделов: основной (`master`, 511 настроек в 9.1.0), control-профиль (91 PID и навигационных + 25 рейтов и TPA + 10 EZ Tune = 126), профиль миксера (12 и правила `mmix`/`smix`), батарейный профиль (28). Профилей — 3, 2 и 3; на F411 профиль миксера один.

{{diagram:inav-cli-diff-scopes|Обычный diff печатает основной раздел и по одному активному профилю каждого вида; все восемь блоков профилей и строку defaults noreboot даёт только diff all. В примере модуля это 38 строк против 69.}}

| Команда | Что в выводе |
|---|---|
| `diff` или `diff master` | версия, `batch start`, команды и `set` основного раздела, **активные** control-, mixer- и battery-профиль, `save`, `batch end` |
| `diff all` | то же, плюс `defaults noreboot` в начале, все 3 + 2 + 3 профиля и три строки возврата выбора профилей; `batch end` не печатается |
| `diff control_profile` (`mixer_profile`, `battery_profile`) | только блок активного профиля этого вида, без версии, `batch` и `save` |
| `dump`, `dump all` | те же области, но со всеми настройками, включая равные умолчанию; `defaults noreboot` нет |

Проверено по `printConfig()`: с маской `DUMP_MASTER` выполняется ветка «dump just the current profiles». Отсюда ловушка: **`diff` выглядит как полный бэкап — в нём есть PID, миксер и батарея, — но только активных профилей.** Остальные профили он не печатает совсем. У VTOL с двумя профилями миксера это половина аппарата. В `diff` нет и `defaults noreboot`, поэтому вставка поверх чужого конфига даст смесь. Бэкап — только `diff all`.

Ещё три детали из исходников. Область `rates` есть в `help`, но не реализована: `diff rates` печатает то же, что `diff`. Флага `hex` нет. `showdefaults` должен добавлять умолчание комментарием `#…` перед изменённой строкой; для команд (`aux`, `serial`, `feature`) так и есть, а для строк `set` код 9.1.0 печатает в комментарии то же текущее значение (`cli.c`, `dumpPgValue`), так что умолчание настройки смотри командой `get`.

### Как устроен `diff all`
Порядок блоков фиксирован: строка версии, `batch start`, `defaults noreboot`, затем команды (`timer_output_mode`, `servo`, `safehome`, `fwapproach`, `geozone`, `feature`, `beeper`, `blackbox`, `map`, `serial`, `led`, `aux`, `adjrange`, `rxrange`, `temp_sensor`, `wp`, `osd_layout`, `logic`, `gvar`, `pid`, `osd_custom_elements`), затем `# master` со строками `set`. Дальше идут профили: перед каждым блоком стоит команда выбора с номером от 1 — `control_profile 1`, `2`, `3`; `mixer_profile 1`, `2`; `battery_profile 1`, `2`, `3`. Блок печатается, даже если в нём ничего не изменено: остаётся одна строка выбора. В блоке миксера после `set` идут `mmix reset`, строки `mmix`, `smix reset`, строки `smix`. В конце — три строки, возвращающие исходный выбор профилей, и `save`. Итого команд выбора профиля в файле 8 + 3 = 11.

Команда выбора профиля при смене номера сама записывает EEPROM (`setConfigProfileAndWriteEEPROM`). Поэтому вставленный `diff all` частично сохраняется ещё до `save`, и `exit` его не отменяет — отменяет только `defaults`.

### Что бэкап не содержит и что содержит неожиданно
Не содержит: прошивку и её target (только имя в строке версии); логи Blackbox на флеше или SD; шрифт аналогового OSD (он в чипе MAX7456) и шрифты очков (`inav-osd-hd`); настройки ESC, приёмника, GPS-модуля, VTX-таблицу воздушного модуля. Отдельно про миссию: строки `wp` в diff — это точки, которые сейчас лежат в памяти полётника; при вставке они тоже попадают только в память. Чтобы миссия пережила перезагрузку, перед `save` нужна `wp save` (`inav-missions`). Давай её только когда во вставке нет красных строк: `wp save` записывает в EEPROM всё несохранённое и обходит защиту, из-за которой `save` отказывает при ошибках в batch.

Содержит калибровки, потому что это обычные настройки основного раздела: `acczero_x/y/z` и `accgain_x/y/z` (акселерометр), `magzero_*` и `maggain_*` (компас), `gyro_zero_*`, а также `vbat_scale`, `current_meter_scale`, `current_meter_offset`. На ту же плату они возвращаются вместе с конфигом. На другую плату переносить их нельзя: аппарат будет считать себя откалиброванным с чужими нулями — убери эти строки и откалибруй заново (`inav-setup-scratch`). Счётчики `stats_total_*` тоже в diff.

### Восстановление и красные строки
{{diagram:inav-cli-restore-flow|Восстановление — это цикл «вставил, прочитал ошибки, исправил файл, сбросил, вставил снова»; save выполняется только после вставки без единой строки ERROR, а заканчивается всё повторным diff all и сравнением.}}

Порядок: (1) снять `diff all`, первая строка файла — версия и target; (2) править копию; (3) прошить с Full chip erase (при смене мажорной версии обязательно) либо на той же прошивке выполнить `defaults`; (4) вставить файл целиком; (5) прочитать вывод; (6) `save`; (7) снова `diff all` и сравнить с файлом; (8) `status`, выходы на вкладке Outputs без пропов.

`batch start` включает счётчик ошибок. При активном пакете `save` с ошибками не записывает, а печатает `### ERROR: N ERRORS WERE DETECTED - Please review and fix before continuing!` и `PLEASE FIX ERRORS THEN 'SAVE'`, после чего пакет сбрасывается — вторая `save` уже запишет то, что есть. Не делай так: каждая отвергнутая строка — это настройка, оставшаяся на умолчании.

| Строка | Причина | Что делать |
|---|---|---|
| `### ERROR: Invalid name` | настройки или имени функции нет в этой прошивке: переименована или убрана | найти в таблице переезда; переименовать или удалить строку |
| `### ERROR: Invalid value. Allowed range: …` / `Allowed values: …` | значение вне нового диапазона или убрано из списка | выбрать новое значение осознанно |
| `### ERROR: Unknown command, try 'help'` | команда переименована (`profile`) или не собрана в этот target | заменить; для вырезанной функции — удалить блок |
| `### ERROR: Parse error`, `… must be between …` | изменился формат или предел команды | сверить формат через `help` |

После исправления файла — `defaults`, и вставка заново с начала: так в конфиге не остаётся следов неудачной попытки. Release notes 9.0 советуют при нескольких профилях вставлять `diff all` двумя частями — до конца `# master` с `save`, затем профили (`inav-intro`).

### `status`, `tasks`
`status` печатает: строку версии; uptime; время; напряжение с числом банок и состоянием батареи; частоту ядра и найденные датчики; `Sensor status` по восьми датчикам; состояние SD; стек и размер конфигурации (`config size` / `max available config`); ошибки I2C; каналы АЦП; `System load`, `cycle time`, `PID rate`, `RX rate`; затем `Arming disabled flags:` с именами; строки `OSD:` (тип и сетка), `VTX:`, блок `GPS:` для u-blox и, при ошибке таймеров, `PWM output init error`. Имена идут в порядке битов. Шестнадцатеричную маску стандартная сборка не печатает (только сборка с `CLI_MINIMAL_VERBOSITY`); маска целиком приходит по MSP в `MSP2_INAV_STATUS` как 32-битное `armingFlags`.

Флагов 24, биты 6–30 без бита 17 (в таблице имён на его месте `PLACEHOLDER`). В 8.0.1 набор тот же.

| Бит | Имя в `status` | Что блокирует | Что сделать |
|---|---|---|---|
| 6 | `GEOZONE` | включена `feature GEOZONE`, и геозона запрещает взлёт | выйти из запретной зоны, проверить зоны |
| 7 | `FS` | аппарат сел или дизармлен по failsafe, связь ещё не признана устойчивой | вернуть связь, выждать, тумблер арма выключить |
| 8 | `ANGLE` | наклон больше `small_angle` (25°) | выровнять аппарат; проверить ориентацию платы и калибровку |
| 9 | `CAL` | идёт калибровка датчиков | подождать неподвижно |
| 10 | `OVRLD` | перегрузка процессора | снизить нагрузку: см. `tasks` |
| 11 | `NAV` | нет фикса при настроенных навигационных режимах, активен режим навигации, первая точка миссии слишком далеко или ошибка JUMP; ниже строка-пояснение | дождаться фикса, выключить режим, исправить миссию |
| 12 | `COMPASS` | компас есть, но не откалиброван | откалибровать |
| 13 | `ACC` | акселерометр нужен, но не откалиброван | 6-позиционная калибровка |
| 14 | `ARMSW` | тумблер арма включён при наличии другой блокировки | выключить тумблер, убрать причину |
| 15 | `HWFAIL` | датчик выбран, но не найден или даёт мусор | `Sensor status`, проводка, `*_hardware` |
| 16 | `BOXFS` | включён режим FAILSAFE тумблером | выключить |
| 18 | `RX` | нет данных приёмника | включить пульт, проверить порт и протокол |
| 19 | `THR` | газ не в минимуме | опустить стик, проверить `rxrange` и `min_check` |
| 20 | `CLI` | открыт CLI | `exit` или `save` |
| 21 | `CMS` | открыто меню CMS | выйти из меню |
| 22 | `OSD` | открыто меню OSD | выйти из меню |
| 23 | `ROLL/PITCH` | включён автозапуск крыла, а стики крена/тангажа отклонены | отпустить стики |
| 24 | `AUTOTRIM` | активен режим AUTOTRIM серв | выключить режим |
| 25 | `OOM` | кончилась динамическая память | упростить конфигурацию, `memory` |
| 26 | `SETTINGFAIL` | настройка вне допустимого диапазона; ниже `### ERROR: Invalid setting: <имя>` | исправить названную настройку |
| 27 | `PWMOUT` | ошибка назначения выходов | `timer_output_mode`, `inav-mixer-vtol` |
| 28 | `NOPREARM` | режим PREARM назначен, но не включён или истёк | включить PREARM перед ARM |
| 29 | `DSHOTBEEPER` | только что пищали моторы по DShot | подождать |
| 30 | `LANDED` | засчитана посадка | выключить тумблер арма |

`tasks` печатает для каждой задачи частоту, максимальное и среднее время выполнения в микросекундах и нагрузку. Нагрузка считается как (время × частота + 5000) / 1000 в десятых долях процента: 120 мкс при 2000 Гц дают 24.5 %. Строка `Total (excluding SERIAL)` — сумма без задачи SERIAL.

### Configurator 9.1: авто-бэкап и миграция
По исходникам Configurator 9.1.0 (`js/backup_restore.js`, `js/migration/`, `tabs/firmware_flasher*.js`):

- Перед прошивкой через serial Configurator входит в CLI, выполняет `diff all` и сохраняет файл `UPDATE_inav_backup_<версия>_<target>_<дата>_<время>.txt`; хранятся 10 последних авто-бэкапов. Если плата уже в DFU или включено «No reboot sequence», бэкапа не будет — CLI недоступен.
- Папка — `inav-backups` в каталоге данных приложения (`app.getPath('userData')`); её открывает кнопка Open Backups на вкладке Firmware Flasher (в документации — Open Backups Folder). Документ `Backup and Restore.md` называет подпапку `backups` — верь кнопке.
- Файл начинается с шапки: у авто-бэкапа перед прошивкой — `# INAV Auto-Backup (pre-flash)`, у бэкапа кнопкой Backup Config — `# INAV Backup`; дальше одинаково: `# Version: 8.0.1`, `# Board:`, `# Date:`, `# Craft:`. **Версию для миграции Configurator берёт только из строки `# Version:`.** У `diff all`, сохранённого руками из CLI, такой строки нет — миграция к нему не применится, пока не допишешь её сам.
- Восстановление предлагается после прошивки с Full chip erase: при той же мажорной версии — сразу, при смене мажорной — после окна предпросмотра миграции. Без Full chip erase, при прошивке из локального файла и при понижении мажорной версии файл сохраняется, но восстановление не предлагается.
- Восстановление шлёт строки по одной, комментарии, `save` и `exit` пропускает, ошибкой считает ответ с `### ERROR:`, `Invalid` или `Unknown command`. Без ошибок — `save`. С ошибками — диалог «сохранить всё равно / прервать»; что бы ты ни выбрал, сними `diff all` и сравни.

Что именно делает `8_to_9.json`: заменяет слово `controlrate_profile` на `use_control_profile`, переименовывает `mixer_pid_profile_linking` → `mixer_control_profile_linking` и `osd_pan_servo_pwm2centideg` → `osd_pan_servo_range_decadegrees`, показывает два предупреждения (умолчания весов оценщика высоты; `ahrs_acc_ignore_rate`). Список удаляемых настроек в нём пуст: `reboot_character`, убранная в 9.0, останется красной строкой. Второе предупреждение по исходникам не подтверждается: `ahrs_acc_ignore_rate` равна 15 и в 8.0.1, и в 9.1.0.

### Переезд 7 → 8 → 9: строки для CLI
Полная таблица 8.0 → 9.1 с умолчаниями — в `inav-intro`; здесь то, что ломает вставку файла. Столбец 7 → 8 взят из release notes 8.0.0 и `7_to_8.json` Configurator 9.1.0: дерева 7.x под рукой не было, по исходникам 8.0.1 проверено только отсутствие старых имён и наличие новых.

| Было | Стало | Переход | Действие со строкой |
|---|---|---|---|
| команда `profile` | `control_profile` | 7 → 8 | переименовать |
| `gps_provider = UBLOX7` | `UBLOX` | 7 → 8 | заменить значение |
| `nav_auto_climb_rate`, `nav_manual_climb_rate` | `nav_mc_auto_climb_rate` и `nav_fw_auto_climb_rate`; `nav_mc_manual_climb_rate` и `nav_fw_manual_climb_rate` | 7 → 8 | записать значение в настройку своей платформы |
| `nav_fw_wp_tracking_accuracy` | то же имя, теперь расстояние до линии пути в метрах | 7 → 8 | пересчитать вручную |
| типы `osd_custom_elements` 4, 5, 6, 7 | 9, 16, 7, 10 | 7 → 8 | перенумеровать |
| `max_throttle`, `pidsum_limit`, `pidsum_limit_yaw`, `control_deadband`, `cpu_underclock`, `disarm_kill_switch`, `dji_workarounds`, `fw_iterm_limit_stick_position`, `gyro_anti_aliasing_lpf_type`, `gyro_hardware_lpf`, `gyro_main_lpf_type`, `gyro_use_dyn_lpf`, `inav_use_gps_no_baro`, `inav_use_gps_velned`, `ledstrip_visual_beeper`, `osd_stats_min_voltage_unit` | — | 7 → 8 | удалить |
| `dynamic_gyro_notch_mode = 3D_*` | значения убраны | 7 → 8 | выбрать из оставшихся |
| `controlrate_profile` | `use_control_profile` | 8 → 9 | переименовать |
| `mixer_pid_profile_linking` | `mixer_control_profile_linking` | 8 → 9 | переименовать |
| `osd_pan_servo_pwm2centideg` | `osd_pan_servo_range_decadegrees` | 8 → 9 | переименовать, число то же |
| `reboot_character` | — | 8 → 9 | удалить |
| `inav_w_z_baro_v`, `inav_w_z_gps_p`, `inav_w_z_gps_v` со своими значениями | имена те же, умолчания 0.35 | 8 → 9 | пересмотреть: оценщик перенастроен |
| `osd_snr_alarm` > 30 | предел 30 | 8 → 9 | уменьшить |

Команда CLI называется `control_profile` и в 8.0.1, и в 9.1.0; `profile` даст `Unknown command`. Пример в `docs/Cli.md` 9.1.0 пишет `control_profile 0` — номера идут с 1, ноль молча игнорируется. Release notes 8.0 и 9.0 упоминают сторонний онлайн-конвертер diff (mrd-rc.com); его работу я не проверял.

И главное, чего нет ни в одном файле: diff хранит только отличия от **старых** умолчаний. Всё, что ты не менял, после переезда получит новые умолчания (`gps_ublox_nav_hz` 10 → 8, `nav_fw_pos_z_ff` 10 → 30 и другие — `inav-intro`).

### Место в системе
- **Получает:** готовую конфигурацию аппарата — порты, режимы, failsafe и калибровки из `inav-setup-scratch`, профили миксера из `inav-mixer-vtol`, раскладки OSD из `inav-osd-hd`, правила `logic` из `inav-ipf`; список переименований из `inav-intro`.
- **Отдаёт:** проверенный файл `diff all` с версией — основу восстановления, переноса на новую прошивку и хранения в git (`eng-ci-configs`); расшифровку флагов арма — предполётной проверке; приёмы скриптования — клиенту из `bf-cli-automation`.
- **Если ошибиться здесь:** бэкап из `diff` вместо `diff all` — после восстановления у VTOL нет второго профиля миксера (`inav-mixer-vtol`); пропущенная красная строка — связка профилей выключена, PID не следуют за режимом; чужие `acczero_*` — горизонт и навигация врут (`inav-gps`).

## practice
Железо и симулятор не нужны: всё решается по таблицам модуля. Фрагмент ниже — **учебный пример, собран вручную** по формату `printConfig()` и `settings.yaml` 8.0.1 (все имена настроек проверены скриптом по дереву 8.0.1 и лежат в своих разделах); это не вывод реального аппарата. Аппарат — VTOL «4+1» из `inav-mixer-vtol`: три control-профиля, два профиля миксера, активны профили 1/1/1.

### Шаг 1. Разметь 69 строк для 9.1
В файле 91 строка: 69 командных и 22 комментария. Для каждой командной строки реши: вставить как есть, переименовать (во что), удалить или пересмотреть.

```text
# version
# INAV/MATEKH743 8.0.1 <дата и время сборки> (<ревизия git>)
# start the command batch
batch start
# reset configuration to default settings
defaults noreboot
# features
feature GPS
feature PWM_OUTPUT_ENABLE
# Ports
serial 1 2 115200 115200 0 115200
# Modes [aux]
aux 0 0 0 1700 2100
aux 1 62 2 1700 2100
aux 2 63 2 1300 1700
# master
set gps_ublox_use_galileo = ON
set reboot_character = 114
set inav_w_z_baro_v = 0.200
set osd_pan_servo_pwm2centideg = 18
set failsafe_procedure = RTH
set nav_rth_altitude = 5000
# control_profile
control_profile 1
set fw_p_pitch = 12
set fw_i_pitch = 9
set fw_ff_pitch = 70
set roll_rate = 30
# control_profile
control_profile 2
set mc_p_pitch = 44
set mc_i_pitch = 85
set mc_d_pitch = 28
set tpa_rate = 20
# control_profile
control_profile 3
set mc_p_pitch = 36
set rc_expo = 60
# mixer_profile
mixer_profile 1
set platform_type = AIRPLANE
set mixer_pid_profile_linking = ON
set mixer_automated_switch = ON
# Mixer: motor mixer
mmix reset
mmix 0 -1.000 0.000 0.000 0.000
mmix 1 -1.000 0.000 0.000 0.000
mmix 2 -1.000 0.000 0.000 0.000
mmix 3 -1.000 0.000 0.000 0.000
mmix 4 1.000 0.000 0.000 0.000
# Mixer: servo mixer
smix reset
smix 0 1 1 100 0 -1
smix 1 2 0 100 0 -1
smix 2 3 0 100 0 -1
smix 3 4 2 100 0 -1
# mixer_profile
mixer_profile 2
set mixer_pid_profile_linking = ON
set mixer_automated_switch = ON
set mixer_switch_trans_timer = 40
# Mixer: motor mixer
mmix reset
mmix 0 1.000 -1.000 1.000 -1.000
mmix 1 1.000 -1.000 -1.000 1.000
mmix 2 1.000 1.000 1.000 1.000
mmix 3 1.000 1.000 -1.000 -1.000
mmix 4 -1.300 0.000 0.000 0.000
# Mixer: servo mixer
smix reset
smix 0 1 1 50 0 -1
smix 1 2 0 50 0 -1
smix 2 3 0 50 0 -1
# battery_profile
battery_profile 1
set bat_cells = 4
set battery_capacity = 5000
# battery_profile
battery_profile 2
set bat_cells = 6
set battery_capacity = 8000
set controlrate_profile = 3
set nav_mc_hover_thr = 1420
# battery_profile
battery_profile 3
# restore original profile selection
control_profile 1
mixer_profile 1
battery_profile 1
# save configuration
save
```

Свою разметку сверь с конвертером. Его правила — три переименования из `8_to_9.json`, одно удаление и три настройки «пересмотреть» из таблицы переезда. Я запускал его на этом файле:

```python
#!/usr/bin/env python3
"""INAV diff all 8.0.x -> 9.1: rename / drop / flag. Usage: convert_8_to_9.py old.txt > new.txt"""
import sys

RENAME = {  # settings.yaml 8.0.1 vs 9.1.0; the same three as Configurator js/migration/8_to_9.json
    "controlrate_profile": "use_control_profile",
    "mixer_pid_profile_linking": "mixer_control_profile_linking",
    "osd_pan_servo_pwm2centideg": "osd_pan_servo_range_decadegrees",
}
DROP = {"reboot_character"}                       # removed in 9.0, not in 8_to_9.json
REVIEW = {"inav_w_z_baro_v", "inav_w_z_gps_p", "inav_w_z_gps_v"}  # defaults changed, estimator retuned

out, log = [], []
for n, raw in enumerate(open(sys.argv[1], encoding="utf-8"), 1):
    line = raw.rstrip("\n")
    p = line.split()
    if len(p) >= 4 and p[0] == "set" and p[2] == "=":
        if p[1] in DROP:
            log.append(f"{n}: DROP   {line}")
            continue
        if p[1] in RENAME:
            log.append(f"{n}: RENAME {p[1]} -> {RENAME[p[1]]}")
            p[1] = RENAME[p[1]]
            line = " ".join(p)
        elif p[1] in REVIEW:
            log.append(f"{n}: REVIEW {line}")
    out.append(line)
print("\n".join(out))
cmds = [l for l in out if l.strip() and not l.startswith("#")]
print("\n".join(log), file=sys.stderr)
print(f"command lines out: {len(cmds)}, renamed: {sum('RENAME' in l for l in log)}, "
      f"dropped: {sum('DROP' in l for l in log)}, review: {sum('REVIEW' in l for l in log)}", file=sys.stderr)
```

Вывод в stderr (номера — строки файла вместе с комментариями):

```text
18: DROP   set reboot_character = 114
19: REVIEW set inav_w_z_baro_v = 0.200
20: RENAME osd_pan_servo_pwm2centideg -> osd_pan_servo_range_decadegrees
42: RENAME mixer_pid_profile_linking -> mixer_control_profile_linking
59: RENAME mixer_pid_profile_linking -> mixer_control_profile_linking
82: RENAME controlrate_profile -> use_control_profile
command lines out: 68, renamed: 4, dropped: 1, review: 1
```

Итог: 63 строки как есть, 4 переименовать, 1 удалить, 1 пересмотреть. Все имена итогового файла проверены тем же скриптом по `settings.yaml` 9.1.0. Конвертер не знает переезда 7 → 8 и не заменяет чтение вывода CLI: он правит только строки `set`.

Допиши к разметке то, чего в файле нет. `set gps_ublox_use_galileo = ON` в 9.1 совпадает с умолчанием — строка безвредна, но лишняя. Строк `gps_ublox_nav_hz`, `gps_ublox_use_beidou`, `nav_fw_pos_z_ff` в файле нет: в 8.0.1 они стояли на умолчаниях 10, OFF и 10, а в 9.1 станут 8, ON и 30. Если прежнее поведение нужно — добавь строки сам.

### Шаг 2. Что потерял бы `diff`
Посчитай по тому же файлу, сколько командных строк напечатал бы `diff` без `all` при активных профилях 1/1/1 и каких строк из `diff all` в нём нет. Считай блоками: шапка и команды, `# master`, каждый профиль, возврат выбора, `save`.

Разбор: шапка и команды — 8 строк (`batch start`, `defaults noreboot`, 2 × `feature`, `serial`, 3 × `aux`), `master` — 6, control-профили — 5, 5 и 3, профили миксера — 15 и 14, батарейные — 3, 5 и 1, возврат — 3, `save` — 1; сумма 69. `diff` печатает всё, кроме `defaults noreboot`, неактивных профилей и возврата: 7 + 6 + 5 + 15 + 3 + 1 = 37, плюс `batch end` после `save` — 38. Потеряно 32 строки: 23 строки с настройками (4 + 2 + 13 + 4), 5 команд выбора профиля, 3 строки возврата и `defaults noreboot`. По смыслу — оба мультироторных набора PID, весь миксер висения и батарейный профиль 6S: после такого «восстановления» VTOL не может висеть.

### Шаг 3. Порядок восстановления и три ошибки
Расставь шаги по порядку:

- А. `save`.
- Б. Вставить файл целиком в CLI.
- В. Прошить 9.1 с Full chip erase, пропы сняты.
- Г. Снять `diff all` на 8.0.1, проверить строку версии, сохранить файл.
- Д. Снова снять `diff all` и сравнить с файлом; затем `status` и выходы.
- Е. В копии файла переименовать и удалить строки по таблице.
- Ж. Прочитать вывод: ни одной строки `### ERROR`; иначе — исправить файл, `defaults`, вставить заново.

Затем найди три ошибки в такой процедуре: «(1) На 8.0.1 выполнил `diff`, сохранил вывод. (2) Прошил 9.1 без Full chip erase, чтобы настройки остались. (3) Вставил файл, увидел две строки `### ERROR: Invalid name`, набрал `save` дважды — со второго раза сохранилось. (4) Снял `diff all` и сохранил как новый бэкап».

### Шаг 4. Строка флагов
Ниже — строки, составленные по формату `cliStatus()` (не вывод аппарата). Назови каждую причину блокировки, биты, десятичную и шестнадцатеричную маску `armingFlags` и скажи, какие флаги уйдут сами, а какие требуют работы.

```text
Arming disabled flags: ANGLE NAV COMPASS ACC RX CLI
  WAITING FOR GPS FIX
```

### Переход на реальное железо
Пропы сняты на всё время. На своей плате: `version`, затем `diff all` → файл; посчитай блоки профилей (должно быть 3 + 2 + 3, на F411 — 3 + 1 + 3). Проверь бэкап делом: `defaults`, вставь файл, `save`, снова `diff all` — файлы должны совпасть построчно, кроме `stats_*`. При переезде на 9.1 прогони конвертер или миграцию Configurator, вставь, добейся вывода без `### ERROR`, сравни `diff all`, проверь выходы на вкладке Outputs и флаги в `status`. Критерий на железе: в `status` после выхода из CLI нет флагов, кроме ожидаемых на столе (`NAV` без фикса в помещении, `RX` при выключенном пульте).

Самопроверка: лабораторная выполнена, когда:
- шаг 1: получено 63 / 4 / 1 / 1 (как есть / переименовать / удалить / пересмотреть), названы все четыре новых имени, в итоговом файле 68 командных строк, перечислены три «молчаливых» умолчания (8, ON, 30);
- шаг 2: `diff all` — 69 строк, `diff` — 38, потеряно 32, из них 23 с настройками;
- шаг 3: порядок Г → Е → В → Б → Ж → А → Д, найдены ошибки в пунктах (1), (2) и (3);
- шаг 4: шесть флагов, биты 8, 11, 12, 13, 18, 20, маска 1325312 = 0x143900.

**Эталон для самопроверки.** Шаг 1: переименования — `osd_pan_servo_range_decadegrees`, дважды `mixer_control_profile_linking`, `use_control_profile`; удалить `reboot_character`; пересмотреть `inav_w_z_baro_v`. Шаг 3: ошибки — `diff` вместо `diff all`; нет Full chip erase при смене мажорной версии; сохранение поверх ошибок (две настройки остались на умолчании). Шаг 4: `CLI` уйдёт после `exit`, `RX` — когда включишь пульт; `ANGLE` — выровнять аппарат (если он ровно стоит, причина в ориентации платы или калибровке); `ACC` и `COMPASS` — калибровки, типичны после переноса на другую плату без строк `acczero_*` и `magzero_*`; `NAV` с пояснением `WAITING FOR GPS FIX` — ждать фикса под открытым небом. Типичные неверные результаты: (1) в шаге 2 вышло «потеряны все профили, `diff` = 14 строк» — ты считал, что `diff` печатает только `master`; активные профили он печатает. (2) Потеряно 31, а не 32 — забыта `defaults noreboot`, либо `diff` вышел 37 — забыта `batch end`. (3) В шаге 1 переименований три, а не четыре — пропущен второй профиль миксера: настройка профильная и повторяется в каждом блоке. (4) Маска 0x142900 или иная — перепутан бит: `ACC` — 13, `COMPASS` — 12, бита 17 нет, `RX` — 18.

## diagnostics
- **Симптом:** после восстановления у VTOL нет режима висения, второй профиль миксера пуст
  - Возможная причина: бэкап снят командой `diff`, а не `diff all` — в нём только активные профили.
  - Что сделать: искать старый `diff all` или авто-бэкап Configurator (Firmware Flasher → Open Backups); иначе собирать профиль заново по `inav-mixer-vtol`.
- **Симптом:** при вставке красные строки `### ERROR: Invalid name`
  - Возможная причина: настройка переименована или убрана в новой версии; файл от другой мажорной версии.
  - Что сделать: выписать строки, исправить копию файла по таблице переезда, `defaults`, вставить заново. Да, при переходе 8 → 9 нужен Full chip erase; красные строки не «лечатся» повторным `save`.
- **Симптом:** `save` отвечает `N ERRORS WERE DETECTED` и не перезагружает
  - Возможная причина: файл начинается с `batch start`, и при вставке были ошибки.
  - Что сделать: пролистать вывод до первых `### ERROR`, исправить файл; не набирать `save` второй раз.
- **Симптом:** `### ERROR: Unknown command, try 'help'` на строке `profile 1`
  - Возможная причина: файл от INAV 7 или инструкция старая: с 8.0 команда называется `control_profile`.
  - Что сделать: заменить `profile` на `control_profile` (номера с 1).
- **Симптом:** Configurator 9.1 восстановил файл без окна миграции, в CLI остались ошибки
  - Возможная причина: в файле нет строки `# Version: X.Y.Z` (файл сохранён вручную из CLI), версия не распознана.
  - Что сделать: добавить строку `# Version: 8.0.1` в начало файла или исправить имена по таблице.
- **Симптом:** после переноса конфига на другую плату горизонт завален, компас врёт, флагов `ACC` и `COMPASS` нет
  - Возможная причина: вместе с diff перенесены чужие `acczero_*`, `accgain_*`, `magzero_*`, `maggain_*`.
  - Что сделать: откалибровать акселерометр и компас заново; в файле для другой платы эти строки удалять.
- **Симптом:** вставил файл, передумал, набрал `exit` — а часть настроек изменилась
  - Возможная причина: команды `control_profile`, `mixer_profile`, `battery_profile` при смене номера сами пишут EEPROM.
  - Что сделать: `defaults` и восстановление из своего бэкапа.
- **Симптом:** после обновления 8 → 9 аппарат ведёт себя иначе, хотя ошибок при вставке не было
  - Возможная причина: настройки, которых не было в diff, получили новые умолчания (GPS, оценщик высоты, `nav_fw_pos_z_ff`).
  - Что сделать: сверить с таблицей в `inav-intro`, нужные значения добавить в файл явно.
- **Симптом:** не армится, причина непонятна
  - Возможная причина: один из 24 флагов; `ARMSW` появляется поверх любой другой причины.
  - Что сделать: `status`, читать флаги слева направо по таблице, сначала убирать причину, потом щёлкать тумблером; помнить, что `CLI` в выводе есть всегда.

## checklist
- Бэкап снят `diff all`, не `diff`; в файле 3 + 2 + 3 блока профилей
- Первая строка файла — версия и target; файл назван с версией и датой
- Бэкап проверен восстановлением и повторным `diff all`
- Перед сменой мажорной версии файл исправлен по таблице переезда
- Прошивка с Full chip erase, пропы сняты
- Вставка без единой строки `### ERROR`, только потом `save`
- Для другой платы удалены строки калибровок
- После восстановления: `status`, выходы на Outputs, калибровки, новые умолчания

## references
- INAV 9.1.0 cli.c (таблица команд, printConfig, batch, save, status, tasks, feature) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/cli.c | primary | A
- INAV 9.1.0 settings.yaml (разделы настроек, имена, умолчания) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 runtime_config.h (флаги блокировки арма) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/runtime_config.h | primary | A
- INAV 9.1.0 fc_core.c (условия установки флагов) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/fc_core.c | primary | A
- INAV 9.1.0 config.c (запись EEPROM при смене профиля) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/config.c | primary | A
- INAV 9.1.0 docs/Cli.md | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Cli.md | primary | A
- INAV 9.1.0 docs/Backup and Restore.md | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Backup%20and%20Restore.md | primary | A
- INAV 8.0.1 cli.c (команды и области diff для сравнения) | https://github.com/iNavFlight/inav/blob/8.0.1/src/main/fc/cli.c | primary | A
- INAV Configurator 9.1.0 backup_restore.js (авто-бэкап, восстановление) | https://github.com/iNavFlight/inav-configurator/blob/9.1.0/js/backup_restore.js | primary | A
- INAV Configurator 9.1.0 migration/8_to_9.json | https://github.com/iNavFlight/inav-configurator/blob/9.1.0/js/migration/8_to_9.json | primary | A
- INAV Configurator 9.1.0 migration/7_to_8.json | https://github.com/iNavFlight/inav-configurator/blob/9.1.0/js/migration/7_to_8.json | primary | A
- INAV 9.0.0 release notes (порядок обновления с 8.0, Full chip erase) | https://github.com/iNavFlight/inav/releases/tag/9.0.0 | primary | A
- INAV 8.0.0 release notes (переименования и удаления 7 → 8) | https://github.com/iNavFlight/inav/releases/tag/8.0.0 | primary | A

## notes
Аудит курса (`docs/reviews/inav-coverage-audit.md`) утверждал, что `diff` без аргументов печатает только раздел `master`. По `printConfig()` в 8.0.1 и 9.1.0 это не так: печатаются ещё и активные профили. Модуль следует исходникам. Вывод CLI в модуле собран по строкам формата из исходников; на плате и в SITL я его не снимал.
