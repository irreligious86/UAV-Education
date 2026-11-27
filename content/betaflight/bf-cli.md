---
id: bf-cli
title: "CLI и ремаппинг ресурсов в Betaflight"
level: L3
readingTime: 45 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5)
status: published
tags:
  - CLI
  - resource
  - remapping
  - backup
  - Betaflight
references:
  - title: "Betaflight CLI Documentation"
    url: "https://betaflight.com/docs/wiki/guides/current/Cli"
    tier: primary
    stack: betaflight
  - title: "Betaflight Resource Remapping Guide"
    url: "https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 CLI Command Reference"
    url: "https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands"
    tier: primary
    stack: betaflight
  - title: "How to Check Betaflight Build Options"
    url: "https://oscarliang.com/check-betaflight-build-options/"
    tier: secondary
    stack: betaflight
related:
  - bf-custom
  - bf-ports
next:
  - bf-custom
---

## summary

Командная строка (CLI) Betaflight — это текстовый интерфейс, открывающий доступ к конфигурации полётного контроллера на уровне, недоступном в графическом интерфейсе. Из CLI можно изменять любые параметры, включая не вынесенные во вкладки конфигуратора, проверять аппаратное состояние, управлять ресурсами (выводами микроконтроллера) и создавать резервные копии.

Ключевая практическая задача статьи — дать навык уверенной работы с `resource` и ремаппингом выводов без перепрошивки, а также научить диагностировать состав прошивки и восстанавливать конфигурацию после сбоев.

## theory

### Архитектура CLI

CLI работает поверх последовательного порта (UART), используя тот же канал, что и конфигуратор (`MSP`, `MultiWii Serial Protocol`). Для входа в CLI через терминал (например, PuTTY/screen) необходимо отправить символ `#` — он переключает контроллер в командный режим.

### Ключевые команды и их назначение

- Управление сессией: `save`, `exit`, `batch start`, `batch end`
- Просмотр конфигурации: `get`, `diff`, `dump`, `status`, `version`
- Изменение параметров: `set`, `feature`, `profile`, `rateprofile`
- Ремаппинг ресурсов: `resource`, `timer`
- Диагностика и отладка: `tasks`, `flash_info`, `dma`

### Diff vs Dump: что и когда использовать

`diff all` выводит только изменённые параметры. Это основной формат для резервных копий и безопасного переноса в пределах одной версии прошивки.

`dump all` выводит полный снимок конфигурации, включая значения по умолчанию. Подходит для глубокой диагностики, но опасен для переноса между разными версиями.

Рекомендуется сохранять отдельно:
- `diff all`
- `resource show`
- `status` (версия/сборка)

### Области `diff`/`dump` и флаги
Синтаксис (одинаков в 4.5 и 2025.12): `diff [master|profile|rates|hardware|all] {defaults|bare}`, у `dump` те же слова (`printConfig()` в `cli/cli.c`). Что попадает в вывод:

| Команда | Что выводит | Обёртка |
|---|---|---|
| `diff` = `diff master` | общие настройки (resource, timer, dma, feature, serial, mixer, beeper, map, led, aux, adjrange, rxrange, vtxtable, vtx, rxfail, все `set` уровня master) **плюс только текущий** PID-профиль и **только текущий** рейт-профиль | `batch start` … `batch end`, без `defaults nosave` и без `save` |
| `diff profile` | только текущий PID-профиль | без обёртки |
| `diff rates` | только текущий рейт-профиль | без обёртки |
| `diff hardware` | resource, timer, dma, feature, serial и «железные» `set` (`blackbox_device`, шины датчиков…), без профилей | `batch` |
| `diff all` | всё из `master`, `mcu_id` и `signature`, **все 4 PID-профиля и все 4 рейт-профиля**, в конце — возврат к активным профилям (`profile N`, `rateprofile N`) | `batch start`, `defaults nosave`, …, `save` (без `batch end`: он печатается только у `diff`/`dump` без `all`) |
| флаг `defaults` | к каждой изменённой строке добавляет закомментированную строку со значением по умолчанию | — |
| флаг `bare` | убирает `batch`/`defaults nosave`/`save`, `mcu_id`, `signature` и восстановление выбора профилей | — |

Ловушка: `diff` без `all` теряет три профиля из четырёх. Бэкап «с профилем 2 под Li-Ion» через `diff` при активном профиле 1 вставится без профиля 2. Для бэкапа — только `diff all`; для сравнения версий — `diff all defaults` (видно, какое умолчание было у изменённого параметра). Флаги `defaults` и `bare` вместе не работают: обрабатывается только первый.

{{diagram:bf-diff-scopes|Простой diff пишет только активные PID- и рейт-профиль; все 4 + 4 профиля, mcu_id и обёртку с save содержит только diff all.}}

### Все команды CLI
Команды с приоритетом A/B (`cmdTable[]` в `cli/cli.c`, всего 59 — набор одинаков в 4.5 и 2025.12; изменился только порядок аргументов `flash_read`: в 2025.12 `<address> <length>`, в 4.5 `<length> <address>`; команды за `#ifdef` есть не в каждой сборке):

| Команда | Что делает |
|---|---|
| `adjrange` | слоты подстроек в полёте (bf-adjustments) |
| `aux` | режимы на AUX-каналах (bf-modes-osd) |
| `batch start` / `batch end` | применить вставленный блок одним пакетом |
| `beacon` | условия DShot-маячка (моторы пищат): `beacon list`, `beacon RX_LOST`, `beacon -RX_LOST` (bf-led-buzzer) |
| `beeper` | условия пищалки: `beeper list`, `beeper -BAT_LOW` (bf-led-buzzer) |
| `bind_rx` | перевести приёмник SPI, SRXL2 или CRSF (ELRS) в режим привязки; без поддержки — `Not supported.` |
| `bl` | перезагрузка в загрузчик (`bl rom`; на платах с внешней flash — `bl flash`) |
| `color`, `led`, `mode_color` | палитра, раскладка и цвета режимов LED-ленты (bf-led-buzzer) |
| `defaults` | сброс к умолчаниям и перезагрузка; `defaults nosave` — без записи |
| `diff`, `dump` | конфиг: изменения / полностью (таблица выше) |
| `dma` | DMA-потоки: `dma show`, `dma <устройство> <индекс> list` |
| `dshot_telemetry_info` | eRPM и ошибки DShot-телеметрии по моторам |
| `dshotprog` | сырые DShot-команды ESC: `dshotprog <индекс\|255> <команда>…` |
| `exit` | выход из CLI с перезагрузкой; `exit noreboot` (с 4.5.4) |
| `feature` | список и переключение функций: `feature`, `feature list`, `feature GPS`, `feature -GPS` |
| `flash_erase`, `flash_info` | стереть / показать встроенную flash для Blackbox (bf-blackbox) |
| `get`, `set` | прочитать (поиск по подстроке: `get gps_rescue`) / изменить параметр |
| `gpspassthrough` | мост USB ↔ UART GPS для u-center; выход — переподключение USB/питания (bf-gps-setup) |
| `help` | список команд, `help <строка>` — поиск |
| `map` | порядок каналов (`map AETR1234`) |
| `mixer`, `mmix` | тип рамы (`mixer list`, `mixer QUADX`) / свой микс моторов |
| `motor` | значение мотора на дизарме, как ползунок вкладки Motors: `motor 0 1100` (индекс с 0, 255 — все, 1000–2000), **без пропов** |
| `msc` | перезагрузка в режим USB-накопителя (выгрузка логов с flash/SD) |
| `profile`, `rateprofile` | выбрать PID-профиль 0–3 / рейт-профиль 0–3 (bf-rates-rc) |
| `rc_smoothing_info` | текущие частоты RC smoothing: найденная частота RX, срезы setpoint/FF/газа (bf-rates-rc) |
| `resource` | пины: `resource`, `resource show all`, `resource MOTOR 1 B00`, `… none` |
| `rxfail`, `rxrange` | значения каналов в Stage 1 failsafe (bf-failsafe) / масштаб каналов |
| `save` | сохранить и перезагрузить; `save noreboot` (с 4.5.4) |
| `sd_info` | состояние SD-карты (`Not configured` / `None inserted` / `Startup failed` / параметры карты) |
| `serial` | функции и скорости портов (bf-ports) |
| `serialpassthrough` | мост USB ↔ любой UART: прошивка приёмника ELRS, настройка GPS/VTX (ниже) |
| `servo`, `smix` | концы хода и микшер серв (bf-servos-pwm) |
| `simplified_tuning` | `apply` / `disable` — пересчитать PID и фильтры по слайдерам |
| `status`, `tasks`, `version` | состояние и BUILD KEY / нагрузка по задачам / версия |
| `timer` | таймеры пинов: `timer show`, `timer <pin> list` |
| `vtx`, `vtx_info`, `vtxtable` | VTX на тумблере / что сообщил VTX / таблица частот и мощностей (link-vtx, bf-adjustments) |

Список функций для `feature` — массив `featureNames[]` в `cli/cli.c`; `feature list` печатает список имён. Вывод снят на 4.5; в 2025.12 `feature` и `feature list` печатают три строки — `Enabled:`, `Available:` и `Unavailable:` (функции, которых нет в сборке), имени `RX_MSP` в списке нет, добавлено `OPTICALFLOW`:

```text
Available: RX_PPM INFLIGHT_ACC_CAL RX_SERIAL MOTOR_STOP SERVO_TILT SOFTSERIAL GPS RANGEFINDER TELEMETRY 3D RX_PARALLEL_PWM RX_MSP RSSI_ADC LED_STRIP DISPLAY OSD CHANNEL_FORWARDING TRANSPONDER AIRMODE RX_SPI ESC_SENSOR ANTI_GRAVITY
```

В 2025.12 отсутствующие в сборке функции (LED_STRIP, SERVO_TILT, GPS зависят от опций Cloud Build) попадают в строку `Unavailable:`, а попытка включить такую функцию отвечает `Unavailable <имя>`. В 4.5 список `Available:` печатался из таблицы имён целиком, и наличие имени не значило, что функция есть в сборке (проверка по BUILD KEY ниже).

### Ремаппинг ресурсов: концепция и ограничения

Команда `resource` управляет привязкой «функция -> физический пин»:

```text
resource <ФУНКЦИЯ> <ИНДЕКС> <ПИН> 
resource MOTOR 1 B00 
resource MOTOR 5 NONE
```

- ADC-ресурсы (`ADC_BATT`, `ADC_CURR`, `ADC_RSSI`) назначаются только на ADC-пины.
- UART ограничен аппаратными блоками контроллера — не любой пин можно использовать как сериал.
- Для DShot критичны таймеры и DMA: неверный пин/канал приводит к неработающим моторам.

### Специфика Betaflight 2025.12 (что изменилось после 4.5)

Между версиями меняются названия и логика части параметров:

- D-term naming: в 2025.12 `d_roll` — базовый D, `d_max_roll` — пиковый (в 4.5 наоборот: `d_roll` — пиковый, `d_min_roll` — базовый; `d_min_*` удалены).
- GPS rescue: газ и контур высоты переехали в общие `ap_*` (`ap_hover_throttle` — до 2025.12 `gps_rescue_throttle_hover`).
- Failsafe landing: `failsafe_landing_time` в секундах (до 2025.12 — `failsafe_off_delay` в десятых долях секунды).
- `serial`: `diff` пишет имена портов (`serial UART3 64 …`); номера из 4.5 (`serial 2 64 …`) принимаются.

Из-за этого старые бэкапы нельзя бездумно вставлять в новую прошивку. Полная таблица — в модуле «Введение в Betaflight», раздел «Переход 4.5.3 → 2025.12: что переименовано и изменилось».

### Проверка состава прошивки через BUILD KEY

В `status` (4.5 и 2025.12) отображается `BUILD KEY`. Подставив его в URL ниже, можно получить JSON со списком включённых опций (`Options`):

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

Это помогает диагностировать отсутствие функций (например, GPS/LED/VTX) без перепрошивки.

### Рецепты, которые нужны чаще всего (команды из `cli/cli.c`)
| Задача | Команда |
|---|---|
| Узнать версию, target / BUILD KEY | `version` / `status` |
| Загрузка CPU, флаги арма, частота гироскопа | `status`, `tasks` |
| Переназначить мотор на другой пад | `resource MOTOR 3 B01` → `save` (`resource show all` — занятость) |
| Поменять порядок моторов без перепайки | `resource` своп пар или в Motors tab «Motor direction/remap» |
| Реверс направления одного мотора (DShot-команды) | `dshotprog 0 8` (7 — `SPIN_DIRECTION_1`, 8 — `SPIN_DIRECTION_2`: постоянное направление в ESC), затем `dshotprog 0 12` (save settings); команды 20/21 — временный разворот для turtle, их шлёт сама прошивка; моторы без пропов, индекс с 0 (255 — все моторы) |
| Проверить DShot-телеметрию | `dshot_telemetry_info` |
| Таймеры/DMA (конфликты моторов, LED, serial) | `timer`, `dma show` |
| Сброс к умолчаниям без сохранения / с | `defaults nosave`, `defaults` |
| Войти в загрузчик DFU | `bl` (или `bl rom`) |
| Flash как USB-диск (выгрузка логов) | `msc` |
| Прошить ESC/настроить | `serialpassthrough`/`escprog` через конфигуратор ESC |
| Покрутить один мотор из CLI (без пропов!) | `motor 0 1100` … `motor 0 1000`; `motor 255 1000` — все моторы |
| Привязать ELRS/CRSF-приёмник без кнопки | `bind_rx` (если сборка с `USE_RX_BIND`; иначе — binding phrase или 3 перезапуска питания приёмника) |
| Настроить GPS в u-center через FC | `gpspassthrough` → закрыть Configurator → u-center на тот же COM-порт; выход — переподключить USB |
| Прошить приёмник ELRS через FC | `serialpassthrough <id UART> <baud>`: id как в `serial` (UART1 = 0; в 2025.12 можно и именем — `UART1`); обычно это делает сам ELRS Configurator методом прошивки через Betaflight passthrough — Configurator Betaflight при этом закрыт |
| Стереть flash Blackbox / проверить SD | `flash_erase` (ждать конца точек) / `sd_info` |
| Какую частоту RX увидел RC smoothing | `rc_smoothing_info` (на подключённом и работающем приёмнике) |
| Пакетная загрузка diff без промежуточных перезагрузок | `batch start` … `batch end` → `save` |
| Диапазоны каналов, карта стиков | `rxrange`, `map AETR1234` |
| Профили | `profile 1`, `rateprofile 2` (команды `battery_profile` в Betaflight нет) |
| Тест пищалки/звука, сенсоры | `beeper`, `play_sound`, `gyroregisters` (найденные датчики — в выводе `status`) |
| Подпись и идентификация платы | `board_name`, `manufacturer_id`, `mcu_id`, `signature` |

### Разобранный пример: сгорел пад мотора 2
Плата F405, пад M2 отвалился. `resource show all` — свободные таймерные пады: `LED_STRIP 1 A08`. Проверка `timer A08 list` — есть таймер с DMA; `resource LED_STRIP 1 NONE`, `resource MOTOR 2 A08`, `timer A08 AF1` (если нужен), `dma pin A08 0`, `save`; Motors tab — мотор 2 крутится на правильной позиции без пропов; `diff all` в репозиторий с комментарием. Если таймер пада конфликтует с DShot других моторов (одна DMA-группа) — `dma show` покажет, и bitbang DShot (`dshot_bitbang = ON`) обходит часть конфликтов.

{{diagram:bf-resource-remap|Перенос мотора на другой пад: проверить таймер и DMA, освободить старый ресурс, назначить новый, сохранить и проверить на вкладке Motors.}}

### Место в системе

- **Получает:** тот же последовательный канал, что и конфигуратор (`bf-intro`); состав сборки — функции, которых нет в прошивке, CLI не включит (`bf-custom`); карту таймеров и DMA конкретной платы.
- **Отдаёт:** `diff all` как бэкап и материал для скриптов (`bf-cli-automation`); назначение пинов через `resource` моторам, сервам и ленте (`bf-servos-pwm`, `bf-led-buzzer`); `status` с флагами арма (`bf-arming-safety`).
- **Если ошибиться здесь:** бэкап снят командой `diff` без `all` → три PID-профиля и три рейт-профиля из четырёх потеряны, и профиль, под который шёл тюнинг, после восстановления не вернётся (`bf-pid`, `bf-rates-rc`). Мотор перенесён на пад, чей таймер или DMA конфликтует с DShot остальных → моторы не работают либо висит флаг `DSHOT_BBANG` (`bf-arming-safety`).

## practice

### Доступ к CLI

1. Подключите полётный контроллер по USB и откройте Betaflight App (для 4.5 — Configurator 10.10).
2. Перейдите на вкладку CLI.
3. Нажмите `Connect`, если соединение не поднялось автоматически.

Альтернатива через терминал:
- подключитесь к порту (`/dev/ttyACM0` в Linux или `COMx` в Windows);
- установите скорость `115200`;
- отправьте символ `#`.

### Создание полной резервной копии

Перед любыми изменениями сохраните состояние:

```text
status
version
diff all
resource show
timer show
```

Сохраните вывод в файл — это даст:
- версию и сборку;
- список изменённых параметров;
- назначения ресурсов;
- конфигурацию таймеров.

### Просмотр и изменение параметров

Просмотр:

```text
get gyro_
get acc
set dyn_notch_min_hz = 150
```

Изменение:

```text
set dyn_notch_min_hz = 150
set dyn_notch_q = 250
save
```

Для пакетного редактирования (меньше перезагрузок):

```text
batch start
set gyro_lpf1_static_hz = 0
set gyro_lpf2_static_hz = 300
set dterm_lpf2_static_hz = 150
batch end
save
```

### Ремаппинг моторов: полный пример

Сценарий: поворот FC на 90° по часовой стрелке без изменения ориентации в прошивке.

Шаг 1. Проверить текущие назначения:

```text
resource show
```

Пример вывода:

```text
A06: MOTOR 1
A07: MOTOR 2
A11: MOTOR 3
A12: MOTOR 4
```

Шаг 2. Текущая схема:

```text
         FRONT
4 (A12)        2 (A07)

3 (A11)        1 (A06)
         BACK
```

Шаг 3. После поворота FC целевая схема:

```text
         FRONT
3 (A11)        4 (A12)

1 (A06)        2 (A07)
         BACK
```

Шаг 4. Назначить новые соответствия:

```text
resource MOTOR 1 none
resource MOTOR 2 none
resource MOTOR 3 none
resource MOTOR 4 none
resource MOTOR 1 A07
resource MOTOR 2 A12
resource MOTOR 3 A06
resource MOTOR 4 A11
save
```

После `save` контроллер перезагрузится с новой схемой.

**Упражнение без железа: тот же аппарат, другие повороты.** Исходные назначения те же: `A06` — MOTOR 1, `A07` — MOTOR 2, `A11` — MOTOR 3, `A12` — MOTOR 4. Номер мотора привязан к месту на раме (схема шага 2): 1 — задний правый, 2 — передний правый, 3 — задний левый, 4 — передний левый. На бумаге составьте блок `resource` для двух других установок платы: (а) FC повёрнут на 90° **против** часовой стрелки; (б) FC повёрнут на 180°. Приём тот же, что в шагах 2–4: нарисовать, на какое место рамы уехал каждый пад, и назначить паду номер мотора этого места.

Затем найдите четыре ошибки в последовательности из таблицы. Её автор решал ту же задачу, что и шаги 1–4 (поворот на 90° по часовой стрелке), и закончил бэкапом (учебный пример, собран вручную):

| № | Что введено в CLI |
|---|---|
| 1 | `resource MOTOR 1 A07` |
| 2 | `resource MOTOR 2 A12` |
| 3 | `resource MOTOR 3 A06` |
| 4 | `resource MOTOR 4 A12` |
| 5 | `diff` — вывод сохранён в файл как бэкап |

И последнее: по таблице «Области `diff`/`dump` и флаги» запишите, сколько PID-профилей и сколько рейт-профилей попадёт в файл после `diff`, `diff all`, `diff profile` и `diff hardware`.

### Проверка build-опций через BUILD KEY

```text
status
```

Далее откройте:

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

Пример секции опций:

```json
"Options": [
  "CLOUD_BUILD",
  "USE_DSHOT",
  "USE_GPS",
  "USE_OSD",
  "USE_SERIALRX",
  "USE_SERIALRX_CRSF",
  "USE_TELEMETRY",
  "USE_VTX"
]
```

### Восстановление конфигурации из бэкапа

1. Выполните сброс:

```text
defaults
```

2. После перезагрузки снова войдите в CLI.
3. Вставьте команды из бэкапа частями (не одним огромным блоком).
4. Проверьте критичные параметры для вашей версии прошивки.
5. Выполните `save`.

Самопроверка: лабораторная выполнена, когда:
- блок для поворота на 90° против часовой стрелки даёт `MOTOR 1 A11`, `MOTOR 2 A06`, `MOTOR 3 A12`, `MOTOR 4 A07`;
- блок для 180° даёт `MOTOR 1 A12`, `MOTOR 2 A11`, `MOTOR 3 A07`, `MOTOR 4 A06`;
- в каждом блоке 9 строк, как в шаге 4: четыре `resource MOTOR N none`, четыре назначения, `save`; каждый из четырёх падов встречается в назначениях ровно один раз;
- в последовательности из таблицы найдены ровно четыре ошибки, и для каждой записано следствие (эталон ниже);
- по профилям получилось: `diff` — 1 PID и 1 рейт; `diff all` — 4 и 4; `diff profile` — 1 и 0; `diff hardware` — 0 и 0.

**Эталон для самопроверки.** Проверка поворотов без подсказки: после 180° каждый мотор получает пад диагонального соседа (1 ↔ 4, 2 ↔ 3), а поворот на 90° против часовой, применённый к собственному результату ещё раз, обязан дать блок для 180°. Четыре ошибки таблицы: нет строк `resource MOTOR N none` перед назначениями — при вводе появятся сообщения `also used by MOTOR`; в строке 4 пад `A12` назначен второй раз, а `A11` не назначен никому (должно быть `resource MOTOR 4 A11`); нет `save` — после перезагрузки схема останется старой; бэкап снят `diff` без `all` — в файле один PID-профиль и один рейт-профиль из четырёх. Частые неверные ответы: в задании (а) получился блок шага 4 (`A07`, `A12`, `A06`, `A11`) — плата повёрнута по часовой стрелке, а не против; в задании (б) получилось `A07`, `A06`, `A12`, `A11` — это зеркало «перед ↔ зад», а не поворот: левый и правый борт остались на месте; в ответе про `diff hardware` записаны профили — эта область содержит только resource, timer, dma, feature, serial и «железные» `set`.

## diagnostics

- Симптом: CLI не отвечает, команды не выполняются.
  - Возможная причина: неверный вход в CLI (не отправлен `#`), конфликт порта, некорректная скорость.
  - Что сделать: убедиться, что активна вкладка CLI, закрыть другие приложения с доступом к COM-порту, сверить скорость MSP на порту (`serial`/вкладка Ports) и скорость терминала (для USB VCP она не важна).

- Симптом: после вставки бэкапа дрон работает некорректно.
  - Возможная причина: версионное несоответствие прошивки.
  - Что сделать: сверить `version` из бэкапа и текущую версию, восстанавливать через `diff all`, а не через `dump all`, вручную проверить критические параметры.

- Симптом: при ремаппинге появляются ошибки `also used by MOTOR`.
  - Возможная причина: временное перекрытие ресурсов при последовательном назначении.
  - Что сделать: сначала очистить назначения (`resource MOTOR N none`), затем назначить новые, сохранить через `save`.

- Симптом: после ремаппинга моторы не работают или работают неверно.
  - Возможная причина: неверный пин, конфликт таймера/DMA, отсутствует поддержка DShot на выбранном пине.
  - Что сделать: выполнить `resource show` и `timer show`, сверить распиновку платы и поддерживаемые функции пинов.

- Симптом: команда `save` зависает или контроллер не перезагружается.
  - Возможная причина: нестабильное USB-подключение, питание, повреждённая конфигурация.
  - Что сделать: переподключить питание и USB, проверить кабель, при повторении выполнить `defaults` и восстановление по шагам.

- Симптом: не удаётся получить BUILD KEY или URL возвращает ошибку.
  - Возможная причина: старая версия Betaflight (< 4.4, до Cloud Build), ключ скопирован не полностью, неверный URL.
  - Что сделать: убедиться, что версия не ниже 4.4, повторно скопировать ключ, при необходимости проверить альтернативный endpoint `.../<BUILD_KEY>/log`.

## references

- Betaflight CLI Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Resource Remapping Guide | https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping | primary | A
- Betaflight 4.5 CLI Command Reference | https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands | primary | A
- How to Check Betaflight Build Options | https://oscarliang.com/check-betaflight-build-options/ | secondary | B
