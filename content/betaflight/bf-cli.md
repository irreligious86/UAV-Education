---
id: bf-cli
title: "CLI и ремаппинг ресурсов в Betaflight"
level: L3
readingTime: 45 мин
firmware: Betaflight 4.5+
status: published
tags:
  - CLI
  - resource
  - remapping
  - backup
  - Betaflight
references:
  - title: "Betaflight CLI Documentation"
    url: "https://www.betaflight.com/docs/development/Cli"
    tier: primary
    stack: betaflight
  - title: "Betaflight Resource Remapping Guide"
    url: "https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 CLI Command Reference"
    url: "https://betaflight-com.pages.dev/docs/wiki/guides/current/Betaflight-4.5-CLI-commands"
    tier: primary
    stack: betaflight
  - title: "Remapping Motors with Resource Command"
    url: "https://betaflight-com.pages.dev/docs/wiki/guides/current/Remapping-Motors-with-Resource-Command"
    tier: primary
    stack: betaflight
  - title: "How to Check Betaflight Build Options"
    url: "https://oscarliang.com/check-betaflight-build-options/"
    tier: secondary
    stack: betaflight
  - title: "Rotorflight Wiki: Backup and Restore (общие принципы)"
    url: "https://github.com/rotorflight/rotorflight-old-wiki/wiki/Back-up-and-restore"
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

### Специфика Betaflight 4.5

Между версиями меняются названия и логика части параметров:

- D-term naming: в 4.5+ `d_roll` — base D, `d_max_roll` — peak.
- GPS rescue: часть переменных переработана.
- Failsafe landing: появились отличия в naming/поведении.

Из-за этого старые бэкапы нельзя бездумно вставлять в новую прошивку.

### Проверка состава прошивки через BUILD KEY

В `status` у Betaflight 4.5+ отображается `BUILD KEY`. Подставив его в URL ниже, можно получить JSON со списком включённых опций (`Options`):

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

Это помогает диагностировать отсутствие функций (например, GPS/LED/VTX) без перепрошивки.

## practice

### Доступ к CLI

1. Подключите полётный контроллер по USB и откройте Betaflight Configurator.
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
set gyro_lpf2_hz = 300
set dterm_lpf2_hz = 150
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

## diagnostics

- Симптом: CLI не отвечает, команды не выполняются.
  - Возможная причина: неверный вход в CLI (не отправлен `#`), конфликт порта, некорректная скорость.
  - Что сделать: убедиться, что активна вкладка CLI, закрыть другие приложения с доступом к COM-порту, сверить `msp_baudrate` и скорость терминала.

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
  - Возможная причина: старая версия Betaflight (< 4.5), ключ скопирован не полностью, неверный URL.
  - Что сделать: убедиться, что версия 4.5+, повторно скопировать ключ, при необходимости проверить альтернативный endpoint `.../<BUILD_KEY>/log`.

## references

- Betaflight CLI Documentation | https://www.betaflight.com/docs/development/Cli | primary | A
- Betaflight Resource Remapping Guide | https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping | primary | A
- Betaflight 4.5 CLI Command Reference | https://betaflight-com.pages.dev/docs/wiki/guides/current/Betaflight-4.5-CLI-commands | primary | A
- Remapping Motors with Resource Command | https://betaflight-com.pages.dev/docs/wiki/guides/current/Remapping-Motors-with-Resource-Command | primary | A
- Betaflight 4.0 CLI Reference (для сравнения версий) | https://www.betaflight.com/docs/wiki/guides/archive/Betaflight-4.0-CLI-commands | primary | A
- How to Check Betaflight Build Options | https://oscarliang.com/check-betaflight-build-options/ | secondary | B
- Rotorflight Wiki: Backup and Restore (общие принципы) | https://github.com/rotorflight/rotorflight-old-wiki/wiki/Back-up-and-restore | secondary | B
- Joshua Bardwell: Betaflight CLI Tutorial | https://www.youtube.com/results?search_query=joshua+bardwell+betaflight+cli | secondary | B