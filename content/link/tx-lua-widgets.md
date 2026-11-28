---
id: tx-lua-widgets
title: "Lua-виджеты EdgeTX: свой экран телеметрии"
level: L2
readingTime: 45 мин
firmware: EdgeTX 2.12 (сверено с 2.12.5) · ExpressLRS 4.1 · Lua 5.3.6
status: published
added: 2026-11-25
tags:
  - EdgeTX
  - Lua
  - telemetry
  - CRSF
  - пульт
related:
  - link-edgetx
  - link-elrs
  - link-protocols
  - link-telemetry-radios
next:
  - ops-field
---

## summary
Стандартные виджеты цветного пульта показывают по одному числу. Свой Lua-виджет собирает на одном экране то, что нужно именно тебе в поле: качество связи с цветом, батарею с пересчётом на банку, режим полётника и последние значения после обрыва. Модуль разбирает по исходникам EdgeTX 2.12.5 пять типов Lua-скриптов и где каждый лежит на SD-карте, устройство виджета (`create`, `update`, `refresh`, `background`, `useLvgl`), когда пульт вызывает каждую функцию, опции, рисование на цветном экране, чтение сенсоров CRSF/ELRS, быстродействие и отладку. Лабораторная — виджет LinkBox целиком: код, проверка синтаксиса `luac` и тест-стенд на настольном Lua 5.3, который подменяет `lcd` и телеметрию подставными функциями (stubs) и прогоняет полёт с обрывом связи. Железо не нужно; установка на TX16S или TX15 — в конце, по желанию.

## theory
### Пять типов скриптов и где они лежат
В EdgeTX Lua — это язык расширений: прошивка даёт скрипту функции (`getValue`, `lcd.drawText`, `playFile`…) и вызывает его в своём цикле. Тип скрипта определяется папкой на SD-карте и тем, кто его запускает (пути — `radio/src/sdcard.h`, загрузка — `radio/src/lua/interface.cpp` и `widgets.cpp`):

| Тип | Папка | Кто запускает | Пульты | Ограничения (2.12.5) |
|---|---|---|---|---|
| Widget | `/WIDGETS/<имя>/main.lua` | экран: виджет ставят в зону | только цветные | имя папки до 13 символов; до 50 опций; ~20 000 инструкций на вызов |
| Telemetry | `/SCRIPTS/TELEMETRY/<имя>.lua` | экран телеметрии модели (Display) | только монохромные | имя файла до 6 символов, экранов до 4 |
| Function | `/SCRIPTS/FUNCTIONS/<имя>.lua` | Special function `Lua Script` по тумблеру | все | имя до 8 символов |
| Mix | `/SCRIPTS/MIXES/<имя>.lua` | Model → Mixer Scripts, выходы — источники миксов | все, где собрано с `LUA_MIXER` | имя до 6 символов; до 6 входов и 6 выходов |
| Tool | `/SCRIPTS/TOOLS/` (файл или папка с `main.lua`) | вручную из меню Tools / Apps | все | один за раз, на весь экран |

Пояснения к таблице. Telemetry-скрипты загружаются только в сборках `PCBTARANIS`, то есть на монохромных пультах (`interface.cpp:706–729`); на TX16S их экранов нет вообще — ту же задачу решают виджеты. Длины имён — из `dataconstants.h`: `LEN_SCRIPT_FILENAME 6` для mix и telemetry, `LEN_FUNCTION_NAME 8` для function (имя хранится в модели без `.lua`). Опция сборки `LUA_MIXER` в 2.12.5 включена по умолчанию (`radio/src/CMakeLists.txt:56`) и во всех целях оставлена `ON`; без неё пропадают только mix-скрипты. Есть и шестой, редкий тип — `/SCRIPTS/RGBLED` для пультов с RGB-подсветкой, его запускает Special function `RGB LED`. Постоянных скриптов одновременно может быть девять на цветном пульте (mix + function + RGB LED) и семь на монохромном (mix + function + telemetry) — `MAX_SCRIPTS`; следующий даёт «Too many Lua scripts». Виджеты в этот счёт не входят: у них своя Lua-среда. Папка виджета — не длиннее 13 символов: буфер пути `LEN_FILE_PATH_MAX + 6 + 5 + 1` (`widgets.cpp:46–48, 187, 203`), более длинную папку пульт молча пропускает.

{{diagram:edgetx-lua-script-types|Выбор типа решает задача: экран на цветном пульте — только виджет, на монохромном — telemetry-скрипт; действие по тумблеру — function, расчёт канала — mix.}}

Главное правило выбора: **mix-скрипт не для основных каналов.** Если он упал с ошибкой, все строки миксов с его выходами отключаются (`mixer.cpp:899–906`), и канал теряет этот источник прямо в полёте. Экран, озвучка и логика тревог — в виджете или function-скрипте, управление — в обычных миксах.

### Анатомия виджета
Виджет — файл `main.lua`, который при выполнении **возвращает таблицу**. При старте пульт перебирает папки в `/WIDGETS`, выполняет каждый `main.lua` и читает ключи таблицы (`widgets.cpp:101–153`):

| Ключ | Обязателен | Когда вызывается | Аргументы → что вернуть |
|---|---|---|---|
| `name` | да | — | строка в списке виджетов |
| `options` | да (хватит `{}`) | читается при старте | таблица опций, см. ниже |
| `create` | да | виджет поставлен в зону или загружена модель | `(zone, options, path)` → объект виджета (обычно таблица) |
| `update` | нет | изменены опции или размер зоны | `(widget, options)` |
| `refresh` | нет (без неё виджет пустой) | зона видна: каждый цикл меню | `(widget, event, touchState)` |
| `background` | нет | зона **не** видна: каждый цикл меню | `(widget)` |
| `translate` | нет | при старте | `(name, lang)` → подпись опции на языке пульта |
| `useLvgl` | нет | при старте | `true` — рисовать через `lvgl.*`, см. ниже |

Подвох в регистрации: фабрика виджета создаётся, только если есть `name` и `create` (`widgets.cpp:146–148`) **и** таблица `options` — без неё `parseOptionDefinitions` возвращает `NULL` (`lua_widget_factory.cpp:276–280`), и виджета просто нет в списке. Сообщения об ошибке при этом нет.

Таблица `zone` в 2.12 относительная: `x = 0`, `y = 0`, `w`, `h` — размер зоны, `xabs`, `yabs` — её положение на экране (`lua_widget_factory.cpp:81–86`). Рисовать надо от `zone.x, zone.y`, а размер не хардкодить: один и тот же виджет ставят и в полноэкранную зону, и в узкую ячейку верхней панели. Третий аргумент `create` — путь к папке виджета (`/WIDGETS/LinkBox/`), удобно для картинок рядом с кодом.

### Опции
Каждая опция — таблица `{ имя, тип, по умолчанию, мин, макс }`; у некоторых типов четвёртое и пятое поля значат другое: у `CHOICE` четвёртое — список строк, у `FILE` — папка. Значения опций хранятся в модели **по номеру**, а не по имени, поэтому вставка новой опции в середину списка сдвинет сохранённые значения у всех, кто уже поставил виджет. Новые опции добавляй в конец.

| Константа | Что выбирает пользователь | Поля 3–5 | Умолчания, если не задано |
|---|---|---|---|
| `VALUE` | целое число | умолчание, мин, макс | мин −100, макс 100 |
| `SOURCE` | источник (стик, сенсор, канал) | умолчание (имя или номер) | — |
| `BOOL` | вкл./выкл. | по умолчанию 0/1 | 0 |
| `STRING` | строка | умолчание | до 255 символов (`textedit.h:61`) |
| `COLOR` | цвет | умолчание (`WHITE`, `lcd.RGB(…)`) | — |
| `TIMER` | таймер 1–3 | по умолчанию 0–2 | 0…`MAX_TIMERS−1` |
| `SWITCH` | тумблер или LS | умолчание, мин, макс | весь диапазон |
| `TEXT_SIZE`, `ALIGNMENT` | размер шрифта, выравнивание | умолчание | — |
| `SLIDER` | ползунок | умолчание, мин, макс | 0…9 |
| `CHOICE` | один пункт списка | умолчание, список строк | — |
| `FILE` | файл | умолчание, папка для выбора | — |

Опций не больше 50 (`MAX_WIDGET_OPTIONS`, лишние отбрасываются). В OpenTX и ранних EdgeTX строковые опции были ограничены 8 символами, в 2.12 — 255; если пишешь виджет для старых пультов, держи строки короткими.

### Когда вызываются refresh и background
Цикл меню EdgeTX повторяется каждые 50 мс (`tasks.cpp:51`, `MENU_TASK_PERIOD`), то есть примерно 20 раз в секунду. На каждом шаге `WidgetsContainer::refreshWidgets` решает для каждой зоны: видна — перерисовать (через перерисовку вызывается `refresh`), не видна — вызвать `background` (`widgets_container.cpp:86–98`). Отсюда три следствия.

- **`background` не вызывается, пока виджет на экране.** Если тревога или подсчёт минимума живёт только в `background`, на видимом экране он молчит. Общую работу (опрос сенсоров) выносят в функцию и вызывают из обеих.
- **Рисовать можно только в `refresh`.** Буфер экрана передаётся Lua только на время `refresh` (`lua_widget.cpp:525–536`); `lcd.*` в `background` или `create` ничего не делают.
- **`event` — число только в полноэкранном режиме (0, если события нет); `touchState` — только при касании в полноэкранном режиме и только на сенсорных пультах** (`lua_widget.cpp:512–522`). В обычной зоне оба `nil`, нажатия забирает интерфейс пульта. Константы касаний (`EVT_TOUCH_*`) определены только на пультах с сенсорным экраном (`api_general.cpp:3387–3392`), на остальных они `nil` — сравнение `event == EVT_TOUCH_TAP` в обычной зоне даёт `nil == nil`, то есть истину; поэтому сначала проверяют `event`. В полноэкранном приходят `EVT_VIRTUAL_ENTER`, `EVT_VIRTUAL_EXIT`, касания `EVT_TOUCH_FIRST`, `EVT_TOUCH_BREAK`, `EVT_TOUCH_TAP`, `EVT_TOUCH_SLIDE`; `touchState` — таблица с `x`, `y`, `tapCount`, а при скольжении ещё `slideX`, `slideY`, `swipeLeft`…

**Бюджет времени.** Перед каждым вызовом виджета ставится счётчик: хук срабатывает каждые 200 инструкций виртуальной машины Lua, и на 101-м срабатывании (около 20 000 инструкций) вызывается `luaL_error("CPU limit")` (`widgets.cpp:37, 51–71`). В отладочных (DEBUG) сборках, в том числе в некоторых симуляторах, лимит только печатается в отладочный вывод и не останавливает виджет (`widgets.cpp:54–65`) — не считай отсутствие ошибки там доказательством. Любая ошибка в `create`, `update`, `refresh` или `background` выключает этот экземпляр виджета: в зоне появляется текст `ERROR in refresh(): …` мелким шрифтом цвета предупреждения (`lua_widget.cpp:455–501`), и его больше не вызывают, пока виджет не создадут заново (смена модели, правка экрана, перезагрузка).

{{diagram:edgetx-widget-lifecycle|Рисует только refresh, и только пока зона видна; background работает вместо него, update приходит при смене опций или зоны, а ошибка в любой функции или лимит инструкций выключают экземпляр виджета, пока его не создадут заново.}}

### useLvgl: другой способ рисовать
Интерфейс цветных пультов построен на графической библиотеке LVGL. С EdgeTX 2.11.0 виджет может объявить `useLvgl = true` и вместо рисования пикселей каждый кадр один раз создать объекты: `lvgl.label`, `lvgl.rectangle`, `lvgl.arc`, `lvgl.image`, кнопки и поля ввода, или всё сразу через `lvgl.build{…}`. Что меняется по коду (`lua_widget.cpp:259–264, 294–323`):

- `update` вызывается сразу после `create` — там и строят интерфейс;
- `refresh` вызывается с пустым буфером: `lcd.*` в нём молча ничего не рисуют, остаётся только логика;
- свойства объектов можно задать функциями (`text = function() return … end`), их пульт пересчитывает после каждого `refresh`;
- в полноэкранном режиме доступны настоящие кнопки и поля ввода с фокусом и прокруткой.

Для приборной панели из чисел, как LinkBox, хватает `lcd.*`: проще отлаживать и переносить на старые версии. LVGL нужен для интерактивного полноэкранного приложения с кнопками.

### Рисование на цветном экране
| Функция | Аргументы | Заметки |
|---|---|---|
| `lcd.drawText` | `x, y, text [, flags [, inversColor]]` | `RIGHT`, `CENTER`, `VCENTER`, `INVERS`, `BLINK`, `SHADOWED` |
| `lcd.drawNumber` | `x, y, value [, flags]` | `value` — **целое**; дробь — через `PREC1` / `PREC2` |
| `lcd.sizeText` | `text [, flags]` → `w, h` | для выравнивания своими руками |
| `lcd.drawFilledRectangle` | `x, y, w, h [, flags [, opacity]]` | прозрачность: 0 — непрозрачно, 15 — полностью прозрачно |
| `lcd.drawRectangle`, `lcd.drawLine`, `lcd.drawGauge` | — | рамки, линии, шкалы |
| `Bitmap.open` + `lcd.drawBitmap` | `bmp, x, y [, scale %]` | картинку открывать один раз в `create`, не в `refresh` |
| `lcd.RGB` | `r, g, b` или `0xRRGGBB` | возвращает флаг цвета |

Флаги складываются побитово (`DBLSIZE | RED`; в Lua 5.3 оператор `|` есть, у старых примеров встречается `+`). Размеры шрифта: `TINSIZE`, `SMLSIZE`, `STDSIZE` (по умолчанию), `MIDSIZE`, `DBLSIZE`, `XLSIZE`, `XXLSIZE`; `BOLD`. Цвета: константы `WHITE`, `BLACK`, `RED`, `GREEN`, `YELLOW`, `ORANGE`, `GREY`… и цвета темы `COLOR_THEME_PRIMARY1`, `COLOR_THEME_WARNING` — с ними виджет не потеряется на светлой теме (`api_colorlcd.cpp:1422–1455`).

Две ловушки чисел. EdgeTX собран с `LUA_32BITS` (`luaconf.h:64`): целые 32-битные, дроби одинарной точности. `lcd.drawNumber(x, y, 16.4)` и `string.format("%d", 16.4)` падают с «number has no integer representation» — напряжение выводи через `string.format("%.1f", v)` или как целое в десятых с `PREC1`. Шрифт цветного пульта выбирается при сборке по языку интерфейса (`gui/colorlcd/lv_conf.h:452–454`). В английском шрифте `lv_font_en_STD` кириллицы нет (только латиница и несколько символов), симулятор Companion всегда использует его (`lv_conf.h:472–475`); в русскую сборку попадают только буквы, встречающиеся в переводе, а `XLSIZE` и `XXLSIZE` даже там без кириллицы (`fonts/lvgl/make_fonts.sh:67–68, 323–335`). Надписи на экране пиши латиницей.

### Чтение телеметрии
| Функция | Возвращает | Без телеметрии |
|---|---|---|
| `getValue(name или id)` | число, строку (`FM`), таблицу (`GPS`) | **0** для всех сенсоров (`api_general.cpp:345`) |
| `getSourceValue(name или id)` | `value, isCurrent, isFresh` | последнее значение и `isCurrent = false`; `nil`, если сенсор ни разу не приходил |
| `getFieldInfo(name)` | `{ id, name, desc, unit }` | `nil`, пока сенсор не обнаружен |
| `getRSSI()` | для CRSF — сглаженный `RQly` (не больше 99), пороги тревог | 0 |
| `model.getInfo()` | `{ name, filename, labels, … }` | — |

Как EdgeTX решает, что связи нет. Для CRSF поток считается живым, пока `RQly` больше нуля, и ещё 1 с после последнего пакета (`TELEMETRY_TIMEOUT10ms = 100`, `telemetry.h:46`; `crossfire.cpp:302–313`). Как только поток пропал, все сенсоры помечаются устаревшими (`telemetry.cpp:405–413`): `getValue` начинает отдавать 0, а `getSourceValue` — последнее значение с `isCurrent = false`. На этом и строится «последнее известное»: напряжение и режим в момент обрыва — подсказка, где и почему аппарат упал.

Имя сенсора — до 4 символов (`TELEM_LABEL_LEN 4`), и это имя из списка телеметрии модели: если пользователь переименовал `RxBt` в `Batt`, `getValue("RxBt")` вернёт 0. Сенсоры CRSF/ELRS, которые появляются после `Discover new` (`telemetry/crossfire.cpp:44–80`, имена — `translations/untranslated.h:116–227`):

| Сенсор | Единица, точность | Что вернёт Lua | Откуда |
|---|---|---|---|
| `1RSS`, `2RSS` | дБм, целое | −63 | приёмник |
| `RQly` | %, целое | 0–100 | приёмник |
| `RSNR` | дБ, целое | 9 | приёмник |
| `ANT` | — | ELRS: 1 или 2 (к номеру прибавляется 1); TBS Crossfire: 0 или 1 | приёмник |
| `RFMD` | — | номер режима | приёмник |
| `TPWR` | мВт | 0, 10, 25, 50, 100, 250, 500, 1000, 2000 (у Crossfire бывает второй `TPWR` в дБм из кадров LINK_TX) | модуль пульта |
| `TRSS`, `TQly`, `TSNR` | дБм, %, дБ | обратный канал | модуль пульта |
| `RxBt` | В, 0.1 | 16.4 (дробь); Betaflight шлёт с шагом 0.1 В | полётник |
| `Curr` | А, 0.1 | 12.3 | полётник |
| `Capa`, `Bat%` | мА·ч, % | целые | полётник |
| `FM` | текст | Betaflight: `"ACRO"`, `"ANGL"`, `"!FS!"`; до арма с суффиксом `*` (готов), `!` (арм запрещён), `?` — например `"ANGL*"` | полётник |
| `GPS` | координаты | таблица `{lat, lon}` | полётник |
| `GSpd`, `Hdg`, `GAlt`, `Sats`, `Alt`, `VSpd` | км/ч, °, м, шт., м, м/с | числа | полётник |

Что значит каждый сенсор и какие пороги ставят — в разделе о телеметрии CRSF модуля `link-edgetx`; как часто приходят пакеты — в `link-elrs`.

{{lesson:link-edgetx|Таблица сенсоров CRSF с порогами, логические переключатели и голосовые тревоги — то, что виджет только показывает, а пульт озвучивает.}}

{{lesson:link-elrs|Packet rate и telemetry ratio задают, как часто приходят слоты телеметрии: при 250 Гц и 1:64 — раз в 256 мс; каждый отдельный сенсор обновляется не чаще.}}

### Быстродействие
- **Ищи сенсор по имени один раз.** `getValue("RQly")` каждый раз перебирает список сенсоров по строке; `getFieldInfo` даёт числовой `id`, по нему чтение быстрее (так сказано и в описании API). Но `getFieldInfo` вернёт `nil`, пока сенсоры не обнаружены, поэтому поиск повторяют раз в секунду, пока не найдутся.
- **Не создавай таблицы в `refresh`.** Каждая `{}` — работа сборщика мусора на пульте с сотнями килобайт памяти. Объект виджета, списки и картинки создаются в `create`.
- **Числа меняются реже, чем кадры.** При 250 Гц и 1:64 слот телеметрии — раз в 256 мс, `refresh` — раз в 50 мс: из пяти кадров четыре рисуют те же числа, а `RQly` и сенсоры полётника обновляются ещё реже — пакеты статистики линка (LINK) и данных (DATA) делят одни и те же слоты (`link-elrs`).
- **Меряй, а не угадывай.** Код LinkBox на тест-стенде тратит до 393 инструкций на вызов `refresh` — 2 % лимита. Стенд считает только инструкции `main.lua`: `lcd.*` и `getSourceValue` на пульте — функции на C, хук их не считает. Запас нужен: тот же код на пульте делит процессор с миксером и интерфейсом.

### Отладка
- **Симулятор EdgeTX Companion.** В окне симулятора есть `Telemetry Simulator` (F4): в списке `Internal Module` выбери `CRSF / ELRS` — появятся поля `RQly`, `1RSS`, `RSNR`, `TPWR`, `RxBt`, `Curr`, `Capa`, `Bat%`, `FM`, `GPS`; поток телеметрии включает флажок `Simulate` (кнопка `Run` там — запуск GPS-трека). `Debug Output` (F6) показывает вывод `print()`. `Reload Lua Scripts` (F7) перечитывает только mix-, function- и telemetry-скрипты; код виджетов читается при старте, поэтому после правки виджета симулятор закрывают и открывают снова (`simulatormainwindow.cpp:149, 306–331`, `widgets.cpp:223–257`, `telemetrysimu.ui`). SD-карту симулятора задают в настройках Companion — копируй туда `/WIDGETS`.
- **На пульте** ошибка видна прямо в зоне: `ERROR in refresh(): /WIDGETS/LinkBox/main.lua:57: attempt to compare nil with number` — файл, строка, причина. Номер строки есть при первом запуске после правки и в симуляторе; когда пульт грузит скомпилированный `.luac`, отладочная информация из него вырезана, и строка пропадает (`interface.cpp:567`) — для отладки удали `.luac` и перезагрузи. `print()` уходит в отладочный вывод (`TRACE`), который в обычной сборке не виден; на пульте отлаживай текстом на экране.
- **На компьютере** — `luac5.3 -p main.lua` (проверка синтаксиса) и тест-стенд с подставными функциями, как в практике. EdgeTX 2.12 использует Lua 5.3.6 (`thirdparty/Lua/src/lua.h:19–22`) — та же версия есть в любом дистрибутиве Linux, но в прошивке числа 32-битные (целые int32, дроби float, `luaconf.h:64, 76–85`), а на компьютере 64-битные; граничные случаи округления проверяй с запасом.
- Пульт сам компилирует `.lua` в `.luac` рядом с исходником (режим `bt` — что новее, `lua_api.h:36–42`; симулятор использует режим `T` и предпочитает `.lua`). Если поправил скрипт на компьютере, а пульт работает по-старому, проверь время файлов или удали `.luac` — и помни, что виджеты перечитываются только при старте пульта (или после выхода из режима USB Storage).

### Место в системе
- **Получает:** сенсоры телеметрии CRSF от приёмника и полётника через модуль пульта (`link-elrs`, `link-protocols`), имена и обнаружение сенсоров и логику тревог пульта (`link-edgetx`), частоту обновления — от packet rate и telemetry ratio ELRS.
- **Отдаёт:** пилоту — LQ с цветом, напряжение на банку, режим полётника и время с момента обрыва; процедуре поиска упавшего аппарата (`ops-field`) — последние значения на экране.
- **Если ошибиться здесь:** неверное число банок покажет 4.2 В/банку на пакете, который на самом деле на 3.5 В/банку, и пилот посадит батарею в ноль (`f-power`); пустой экран из-за `ERROR in refresh()` пилот заметит только в поле; mix-скрипт вместо виджета при падении отключит канал управления (`link-edgetx`, Mixer Scripts).

## practice
Лабораторная без железа: собрать виджет LinkBox, проверить синтаксис и прогнать его на тест-стенде. Нужен компьютер с Lua 5.3 (`apt install lua5.3` в Debian/Ubuntu; на Windows — WSL). Требования к виджету: LQ крупно с цветом по порогам (ориентир курса: от 80 — зелёный, 50–79 — жёлтый, ниже 50 — красный; пороги — опции), `RxBt` с напряжением на банку, `FM`, строка `1RSS` / `RSNR` / `TPWR`, после обрыва — последние значения серым и счётчик секунд, компактный вид для маленькой зоны (крупная разметка — от 180 × 100 пикселей, ориентир курса).

### Шаг 1. Сенсоры и опции
Список сенсоров — константа, опции — четыре: число банок (0 — авто), два порога LQ и цвет текста. Порядок опций закрепляется сразу: значения хранятся по номеру.

Для авто-оценки берётся ⌈V / 4.40⌉: 4.40 В — чуть выше полной LiHV-банки (4.35 В), запас на погрешность измерения. С делителем ровно 4.35 полный 6S LiHV (26.1 В) дал бы 26.1 / 4.35 = 6.0000…01 и после округления вверх — 7S. Оценка верна, пока напряжение на банку выше 4.40·(n−1)/n: для 4S — 3.30 В, для 6S — 3.67 В, для 8S — 3.85 В. Поэтому разряженный пакет (а для 8S и выше — уже и хранящийся) авто-оценка может посчитать неверно: 21.0 В — это и полный 5S, и пустой 6S. Оценка фиксируется в `sample` при первом значении после каждого подключения — даже если виджет в этот момент не на экране — и не сбрасывается в `update`, который пульт вызывает при каждой смене опций и размера зоны; сбрасывает её только новое подключение (новая батарея) или смена опции `Cells`. Для полётов число банок задают опцией.

Значение `RxBt` ≤ 4.5 В (порог — ориентир курса) виджет считает уже пересчитанным на банку: так шлёт Betaflight с `report_cell_voltage = ON` (с шагом 0.1 В), или это 1S.

### Шаг 2. Полный код
Файл `tools/lua/LinkBox/main.lua` в репозитории курса; на пульте — `/WIDGETS/LinkBox/main.lua`.

```lua
-- LinkBox: ELRS/CRSF link and battery widget for EdgeTX colour radios.
-- Checked against the EdgeTX 2.12.5 Lua API (widgets.cpp, lua_widget.cpp, api_general.cpp).
-- Install: /WIDGETS/LinkBox/main.lua on the SD card, then add the widget to a screen zone.
-- Screen strings are ASCII on purpose: the English-build font has no Cyrillic glyphs.

local SENSORS = { "RQly", "RxBt", "FM", "1RSS", "RSNR", "TPWR" }
local LOOKUP_PERIOD = 100   -- 10 ms ticks: retry sensor lookup once per second
local CELL_MAX_V = 4.40     -- just above LiHV full charge (4.35 V): auto cell count only
local PER_CELL_MAX = 4.5    -- RxBt at or below this is already per cell (course choice)

local options = {
  { "Cells",  VALUE, 0, 0, 14 },    -- 0 = auto (latched at the first reading after each connect)
  { "LQwarn", VALUE, 80, 1, 100 },  -- course reference thresholds, not a standard
  { "LQcrit", VALUE, 50, 1, 100 },
  { "Text",   COLOR, WHITE },
}

-- getSourceValue (EdgeTX 2.12) returns value, isCurrent, isFresh and keeps
-- the last value after the link is lost. Fallback for radios without it:
-- getValue returns 0 when telemetry is not streaming.
local function readSource(id)
  if getSourceValue then
    return getSourceValue(id)
  end
  local v = getValue(id)
  if v == 0 then return nil, false end
  return v, true
end

local function resolveIds(w)
  local now = getTime()
  if now - w.lastLookup < LOOKUP_PERIOD then return end
  w.lastLookup = now
  for i = 1, #SENSORS do
    local name = SENSORS[i]
    if not w.ids[name] then
      local info = getFieldInfo(name)   -- nil until the sensor is discovered
      if info then w.ids[name] = info.id end
    end
  end
end

local function sample(w)
  resolveIds(w)
  local up = false
  for i = 1, #SENSORS do
    local name = SENSORS[i]
    local id = w.ids[name]
    if id then
      local v, current = readSource(id)
      if v ~= nil and current then
        if name ~= "RQly" then
          w.last[name] = v
        elseif v > 0 then                 -- RQly 0 = link just dropped: keep last good
          w.last[name] = v
          up = true
        end
      end
    end
  end
  if up then
    if not w.up then w.cells = nil end   -- new connection: maybe a new pack
    local v = w.last.RxBt
    if w.cells == nil and v and v > PER_CELL_MAX then
      w.cells = math.ceil(v / CELL_MAX_V) -- latched here, visible or not
    end
    w.lastGood = getTime()
    local lq = w.last.RQly
    if w.lqMin == nil or lq < w.lqMin then w.lqMin = lq end
  end
  w.up = up
end

local function cellCount(w, v)
  if v <= PER_CELL_MAX then return 1 end -- 1S, or FC already sends the average per cell
  if w.options.Cells > 0 then return w.options.Cells end
  return w.cells or math.ceil(v / CELL_MAX_V)
end

local function lqColor(w, lq)
  if lq >= w.options.LQwarn then return GREEN end
  if lq >= w.options.LQcrit then return YELLOW end
  return RED
end

local function create(zone, opts)
  local w = { zone = zone, options = opts, ids = {}, last = {},
              lastLookup = -LOOKUP_PERIOD, lastGood = nil, up = false,
              cells = nil, lqMin = nil }
  return w
end

local function update(w, opts)
  -- called on every option change and zone resize: keep the latched count
  if opts.Cells ~= w.options.Cells then w.cells = nil end
  w.options = opts
end

local function background(w)
  sample(w)          -- called only while the widget is not on screen
end

local function drawBig(w, x, y, txt)
  local L = w.last
  if not L.RQly and not L.RxBt then
    lcd.drawText(x + 4, y + 2, "NO TLM", SMLSIZE | RED | BLINK)
    return
  end
  local dim = w.up and txt or GREY
  local lq = L.RQly
  if lq then
    lcd.drawText(x + 4, y + 2, "LQ", SMLSIZE | dim)
    lcd.drawNumber(x + 4, y + 14, lq, DBLSIZE | (w.up and lqColor(w, lq) or GREY))
    if w.lqMin then
      lcd.drawText(x + 4, y + 52, string.format("min %d", w.lqMin), SMLSIZE | dim)
    end
  end
  local v = L.RxBt
  if v then
    local n = cellCount(w, v)
    if n == 1 then
      lcd.drawText(x + 90, y + 2, string.format("%.2fV", v), MIDSIZE | dim)
      lcd.drawText(x + 90, y + 30, "per cell", SMLSIZE | dim)
    else
      lcd.drawText(x + 90, y + 2, string.format("%.1fV", v), MIDSIZE | dim)
      lcd.drawText(x + 90, y + 30, string.format("%.2fV/c %dS", v / n, n), SMLSIZE | dim)
    end
  end
  if L.FM then
    lcd.drawText(x + 90, y + 52, tostring(L.FM), SMLSIZE | BOLD | dim)
  end
  local row = y + 74
  lcd.drawText(x + 4, row, string.format("1RSS %s", L["1RSS"] or "--"), SMLSIZE | dim)
  lcd.drawText(x + 4, row + 16, string.format("RSNR %s  TPWR %s", L.RSNR or "--", L.TPWR or "--"), SMLSIZE | dim)
  if not w.up then
    local msg = "NO TLM"
    if w.lastGood then
      msg = string.format("NO LINK %ds", (getTime() - w.lastGood) // 100)
    end
    lcd.drawText(x + w.zone.w - 4, y + 2, msg, SMLSIZE | RIGHT | RED | BLINK)
  end
end

local function drawSmall(w, x, y, txt)
  local L = w.last
  if not L.RQly then
    lcd.drawText(x + 2, y + 2, "NO TLM", SMLSIZE | RED)
    return
  end
  local col = w.up and lqColor(w, L.RQly) or GREY
  lcd.drawText(x + 2, y + 2, string.format("LQ %d", L.RQly), SMLSIZE | col)
  if L.RxBt then
    lcd.drawText(x + 2, y + 18, string.format("%.1fV", L.RxBt), SMLSIZE | (w.up and txt or GREY))
  end
end

local function refresh(w, event, touchState)
  sample(w)
  -- event is nil unless the widget is in full-screen mode;
  -- EVT_TOUCH_TAP is nil on radios without a touch screen
  if event and (event == EVT_VIRTUAL_ENTER or event == EVT_TOUCH_TAP) then
    w.lqMin = nil                         -- reset the flight minimum
  end
  local z = w.zone
  local txt = w.options.Text
  if z.w >= 180 and z.h >= 100 then    -- big layout size: course choice
    drawBig(w, z.x, z.y, txt)
  else
    drawSmall(w, z.x, z.y, txt)
  end
end

return { name = "LinkBox", options = options, create = create,
         update = update, refresh = refresh, background = background }
```

Что в коде сделано из теории. Опрос сенсоров (`sample`) вызывается и из `refresh`, и из `background` — минимум LQ, число банок и время обрыва считаются, даже когда открыт другой экран. Идентификаторы ищутся раз в секунду, пока не найдутся. `RQly = 0` не записывается как «последнее хорошее»: в момент обрыва модуль успевает прислать ноль. LQ выводится через `drawNumber` (целое), напряжение — через `string.format("%.1f")` (дробь). Минимум LQ считается с момента создания виджета; в полноэкранном режиме нажатие Enter или касание его сбрасывает. Перед сравнением с `EVT_TOUCH_TAP` проверяется, что `event` не `nil`: на пульте без сенсорного экрана эта константа `nil`, и без проверки минимум сбрасывался бы каждый кадр.

### Шаг 3. Проверка синтаксиса
```
$ luac5.3 -p tools/lua/LinkBox/main.lua && echo "luac5.3 -p: OK"
luac5.3 -p: OK
```
`luac -p` ловит только синтаксис: незакрытый `end`, лишнюю запятую. Ошибки вроде сравнения `nil` с числом проявятся лишь при выполнении — для этого следующий шаг.

### Шаг 4. Тест-стенд
Файл `tools/lua/harness.lua` в репозитории курса подменяет глобальные функции EdgeTX подставными: `lcd.drawText` и `lcd.drawNumber` печатают координаты, флаги и текст, а `drawNumber`, как настоящий `luaL_checkinteger`, проверяет, что у значения нет дробной части; `getFieldInfo` возвращает `nil`, пока сенсор «не обнаружен»; `getSourceValue` отдаёт значение и флаг `isCurrent`; `getTime` — управляемые часы в тиках по 10 мс. Стенд загружает `main.lua` через `loadfile`, проверяет таблицу виджета, вызывает `create` с зоной 225 × 122 и прогоняет 14 кадров: сенсоров нет → связь с 6S → LQ 62 → LQ 38 → виджет скрыт, работает только `background` → обрыв → новая батарея 4S → Enter в полноэкранном режиме → `update` под нагрузкой → замена батареи → ловушка авто-оценки → опция `Cells = 6` → напряжение на банку от полётника → зона верхней панели 70 × 36. Число инструкций считает `debug.sethook` со счётчиком 1 — тот же механизм, которым EdgeTX ограничивает виджеты; стенд считает только инструкции из `main.lua`, потому что его подставные функции написаны на Lua, а на пульте это функции на C, которые хук не считает.

```
$ lua5.3 tools/lua/harness.lua tools/lua/LinkBox/main.lua
widget 'LinkBox': 4 options, keys create/update/refresh/background = true/true/true/true
t=  0.0 s  1. sensors not discovered yet  [147 VM instructions]
  text   (  4,  2) SML|BLINK|RED NO TLM
t=  1.5 s  2. link up, 6S pack at 24.6 V  [393 VM instructions]
  text   (  4,  2) SML|WHITE LQ
  number (  4, 14) DBL|GREEN 100
  text   (  4, 52) SML|WHITE min 100
  text   ( 90,  2) MID|WHITE 24.6V
  text   ( 90, 30) SML|WHITE 4.10V/c 6S
  text   ( 90, 52) SML|BOLD|WHITE ACRO
  text   (  4, 74) SML|WHITE 1RSS -63
  text   (  4, 90) SML|WHITE RSNR 9  TPWR 250
t=  4.0 s  3. LQ 62 (between LQcrit 50 and LQwarn 80)  [346 VM instructions]
  …
  number (  4, 14) DBL|YELLOW 62
  …
t=  4.5 s  4. LQ 38 (below LQcrit)  [309 VM instructions]
  …
  number (  4, 14) DBL|RED 38
  …
t=  4.6 s  5. widget hidden: background() samples, 0 draw calls  [154 VM instructions]
t=  9.7 s  6. link lost 5 s ago: last good values (from background), grey  [322 VM instructions]
  text   (  4,  2) SML|GREY LQ
  number (  4, 14) DBL|GREY 41
  text   (  4, 52) SML|GREY min 38
  text   ( 90,  2) MID|GREY 21.9V
  text   ( 90, 30) SML|GREY 3.65V/c 6S
  text   ( 90, 52) SML|BOLD|GREY ANGL
  text   (  4, 74) SML|GREY 1RSS -104
  text   (  4, 90) SML|GREY RSNR -4  TPWR 1000
  text   (221,  2) SML|RIGHT|BLINK|RED NO LINK 5s
t= 15.0 s  7. reconnect with a fresh 4S pack (cell count re-detected)  [352 VM instructions]
  …
  text   (  4, 52) SML|WHITE min 38
  text   ( 90,  2) MID|WHITE 16.4V
  text   ( 90, 30) SML|WHITE 4.10V/c 4S
  text   ( 90, 52) SML|BOLD|WHITE ACRO*
  …
t= 15.1 s  8. full screen, ENTER pressed: LQ minimum reset  [296 VM instructions]
  …
  number (  4, 14) DBL|GREEN 100
  text   ( 90,  2) MID|WHITE 16.4V
  …
t= 15.2 s  9. update() (zone or option change) under load keeps the latched 4S  [304 VM instructions]
  …
  text   ( 90,  2) MID|WHITE 12.9V
  text   ( 90, 30) SML|WHITE 3.23V/c 4S
  …
t= 15.3 s  10. pack swapped: link lost  [285 VM instructions]
  …
  text   (221,  2) SML|RIGHT|BLINK|RED NO LINK 0s
t= 16.0 s  11. auto count trap: 6S at 3.50 V/cell reads as 5S  [336 VM instructions]
  …
  text   ( 90,  2) MID|WHITE 21.0V
  text   ( 90, 30) SML|WHITE 4.20V/c 5S
  …
t= 16.1 s  12. Cells option = 6: correct per-cell value  [298 VM instructions]
  …
  text   ( 90, 30) SML|WHITE 3.50V/c 6S
  …
t= 16.2 s  13. FC sends average per cell, 0.1 V steps (report_cell_voltage = ON)  [281 VM instructions]
  …
  text   ( 90,  2) MID|WHITE 3.90V
  text   ( 90, 30) SML|WHITE per cell
  …
t= 16.2 s  14. topbar-size zone 70x36
  text   (  2,  2) SML|GREEN LQ 100
  text   (  2, 18) SML|WHITE 3.9V
max main.lua VM instructions per refresh: 393 of the ~20000 widget budget (2.0 %)
```

Вывод сокращён: «…» — пропущенные строки тех же кадров; полный лог получишь, запустив стенд у себя. Стенд окупился дважды. В первой версии проверка «≤ 4.5 В — это уже на банку» стояла после опции `Cells`, и в кадре 13 виджет делил 3.9 В на 6 и показывал `0.65V/c 6S`. А число банок сбрасывалось в `update`: в кадре 9 после смены зоны оно пересчиталось бы по просевшим 12.9 В — ⌈12.9 / 4.40⌉ = 3, то есть `4.30V/c 3S` на пакете, который на самом деле на 3.23 В/банку. На пульте это выглядело бы как «батарея полная» в конце полёта; здесь — одна строка лога и правка двух функций.

### Шаг 5. Симулятор Companion (по желанию)
Скопируй папку `LinkBox` в `/WIDGETS` на SD-карте симулятора и открой симулятор для цветного пульта (TX16S). В `Telemetry Simulator` (F4) выбери `Internal Module` = `CRSF / ELRS`, задай `RQly = 100`, `RxBt = 24.6`, `FM = ACRO`, включи флажок `Simulate`, выполни `Discover new` и поставь LinkBox в зону. Сними `Simulate` — через секунду цифры станут серыми и пойдёт счётчик `NO LINK`. После правки кода закрой и снова открой симулятор: F7 (`Reload Lua Scripts`) виджеты не перечитывает.

### Переход на реальное железо
Пульт: цветной EdgeTX 2.11 или новее (TX16S, TX16S MK3, TX15, Jumper T15/T16/T18 и подобные); аппарат с ELRS и включённой телеметрией в полётнике (`link-protocols`). Пропеллеры сняты: проверка идёт на столе.

1. **Бэкап.** Пульт в режиме `USB Storage (SD)`, скопируй всю SD-карту на компьютер. Критерий отмены: если копия не прочиталась целиком, дальше не идти.
2. Скопируй `LinkBox` в `/WIDGETS/` и перезагрузи пульт (или выйди из режима USB Storage — виджеты перечитываются при этом). На главном экране — настройка экрана, выбери зону не меньше 180 × 100 пикселей (например, раскладка с одной большой зоной), виджет `LinkBox`. В опциях поставь `Cells` = числу банок своей батареи.
3. Включи аппарат, `Telemetry → Discover new`. Не позже чем через секунду после появления сенсоров виджет показывает LQ, напряжение и режим.
4. Сверь с экраном телеметрии: `RQly`, `RxBt`, `FM`, `1RSS`, `RSNR`, `TPWR` совпадают с числами виджета; напряжение на банку = `RxBt` / `Cells` с точностью 0.01 В.
5. Отойди с аппаратом или накрой антенну приёмника рукой: цвет LQ меняется на жёлтый ниже 80 и красный ниже 50. Отключи батарею аппарата: через 1 с цифры серые, `NO LINK` считает секунды. Включи снова — цифры вернули цвет, `min` показывает худший LQ.
6. Критерии отмены: на экране `ERROR in …` или пульт стал медленно реагировать на кнопки — удали папку `LinkBox` с SD-карты и верни бэкап; виджет не влияет на каналы, но проверку повторяют на компьютере.

Критерии приёмки на железе: шесть значений совпадают с экраном телеметрии; переход «связь есть → нет → есть» отрабатывает как в кадрах 2, 6 и 7 стенда; в зоне верхней панели — компактный вид в две строки.

Самопроверка: лабораторная выполнена, когда:
- (1) `luac5.3 -p` по твоему `main.lua` печатает `OK`;
- (2) тест-стенд проходит все 14 кадров без ошибки Lua, и числа совпадают с эталоном: кадр 2 — `100`, зелёный, `24.6V`, `4.10V/c 6S`; кадр 3 — `62` жёлтый; кадр 4 — `38` красный; кадр 6 — все значения серые, `41` и `21.9V` из `background`, `NO LINK 5s`; кадр 7 — `4.10V/c 4S`, `min 38`, `ACRO*`; кадр 9 — `3.23V/c 4S`; кадр 11 — `5S`; кадр 12 — `3.50V/c 6S`; кадр 13 — `3.90V`, `per cell`;
- (3) максимум инструкций `main.lua` на вызов не больше 2000 (10 % лимита, ориентир курса) — у эталона 393;
- (4) для пути на железе — выполнены критерии приёмки из раздела «Переход на реальное железо».

Пункты 1–3 — путь на компьютере, пункт 4 — только при наличии пульта и аппарата.

**Эталон для самопроверки.** Верный виджет даёт вывод из шага 4 (полностью — при запуске стенда); координаты могут отличаться, если ты менял разметку, но цвета, тексты и порядок кадров — нет. Четыре типичные ошибки. Кадр 6 показывает `0` вместо `41` и `21.9V` — чтение через `getValue` без проверки `isCurrent`: после обрыва он отдаёт ноль; если там `38` и `22.1V`, опрос не вызывается из `background`. Кадр 9 показывает `3S` — число банок сбрасывается в `update`. Кадр 13 показывает `0.65V/c 6S` — проверка «≤ 4.5 В» стоит после опции `Cells`. Стенд падает с «number has no integer representation» — в `drawNumber` или `%d` попало напряжение-дробь.

## diagnostics
- **Симптом:** виджета нет в списке, ошибки тоже нет.
  Возможная причина: файл лежит не как `/WIDGETS/<имя>/main.lua`; имя папки длиннее 13 символов; в таблице нет `name`, `create` или `options`; файл не возвращает таблицу (`return` в конце забыт).
  Что сделать: проверить путь и последнюю строку файла; добавить `options = {}`; перезагрузить пульт — список виджетов читается при старте.
- **Симптом:** в зоне `ERROR in refresh(): …: attempt to compare nil with number`.
  Возможная причина: сенсор ещё не обнаружен или переименован, `getValue` / `getSourceValue` вернул `nil` или 0, а код сравнивает без проверки.
  Что сделать: проверять значение на `nil` перед сравнением; брать имя сенсора из списка телеметрии модели; после правки — перезапуск симулятора или пульта (на пульте хватает и выхода из режима USB Storage); F7 в симуляторе виджеты не перечитывает.
- **Симптом:** `ERROR in refresh(): … number has no integer representation`.
  Возможная причина: `lcd.drawNumber` или `string.format("%d")` получил дробь (`RxBt`, `Curr`, `VSpd` — с точностью 0.1–0.01).
  Что сделать: `string.format("%.1f", v)` или `lcd.drawNumber(x, y, math.floor(v * 10 + 0.5), PREC1)`.
- **Симптом:** `ERROR in refresh(): CPU limit`.
  Возможная причина: больше ~20 000 инструкций за вызов — цикл по всем сенсорам с поиском по имени каждый кадр, построение строк в цикле, большие таблицы.
  Что сделать: кэшировать `id`, выносить подготовку в `create` и `update`, измерить инструкции на стенде с `debug.sethook`. В DEBUG-сборке симулятора лимит не срабатывает — проверяй на стенде или на пульте.
- **Симптом:** после обрыва связи виджет показывает нули вместо последних значений.
  Возможная причина: чтение через `getValue` — без потока телеметрии он возвращает 0.
  Что сделать: `getSourceValue` и флаг `isCurrent`; для старых прошивок — не перезаписывать сохранённое значение нулём.
- **Симптом:** напряжение на банку завышено на 0.7–0.8 В (например, `4.20V/c 5S` на 6S) или занижено (`7S` на полном 6S LiHV с делителем 4.35).
  Возможная причина: авто-оценка числа банок по разряженному пакету (ниже 4.40·(n−1)/n В на банку) или делитель ровно на границе полного заряда; либо оценка пересчитывается в `update` по просевшему напряжению.
  Что сделать: задать `Cells` явно; делитель 4.40; фиксировать оценку при подключении, а не в `update`.
- **Симптом:** напряжение на банку около 0.6–0.7 В (например, 3.9 / 6 = `0.65V/c`).
  Возможная причина: в Betaflight включён `report_cell_voltage`, `RxBt` уже на банку, а виджет делит его ещё раз.
  Что сделать: проверка «≤ 4.5 В — уже на банку» раньше деления, как в LinkBox, или выключить `report_cell_voltage`.
- **Симптом:** тревога или минимум LQ считаются, только когда открыт экран с виджетом (или наоборот).
  Возможная причина: логика только в `refresh` или только в `background`; они не вызываются одновременно.
  Что сделать: общая функция опроса, вызываемая из обеих.
- **Симптом:** после настройки опций в новой версии виджета пороги «переехали» в чужие поля.
  Возможная причина: новая опция вставлена в середину списка; значения хранятся по номеру.
  Что сделать: новые опции — только в конец; после изменения порядка — заново выставить опции в каждой модели.
- **Симптом:** поправил скрипт на компьютере, а пульт или симулятор работает по-старому.
  Возможная причина: на пульте — рядом лежит более новый `main.luac`, пульт загрузил его; в симуляторе (режим `T`, `.lua` в приоритете) — виджет просто не перезапущен.
  Что сделать: на пульте — удалить `.luac` или скопировать `.lua` с текущим временем и перезагрузить; симулятор закрыть и открыть заново (F7 виджеты не перечитывает).

## checklist
- Перед любой правкой на пульте — копия всей SD-карты.
- Виджет лежит в `/WIDGETS/<имя>/main.lua` (имя папки до 13 символов), таблица содержит `name`, `options`, `create`.
- После правки виджета — перезапуск пульта или симулятора.
- Рисование — только в `refresh`; опрос и логика — в общей функции, вызываемой из `refresh` и `background`.
- Сенсоры ищутся через `getFieldInfo` и кэшируются по `id`; поиск повторяется, пока они не обнаружены.
- Последние значения — через `getSourceValue` и `isCurrent`, не через `getValue`.
- Дроби — через `string.format("%.1f")` или `PREC1`, не через `drawNumber` напрямую.
- Число банок задано опцией; авто-оценка (⌈V / 4.40⌉) фиксируется при подключении и верна только для заряженного пакета.
- Новые опции добавляются в конец списка.
- Надписи на экране — латиницей.
- `luac5.3 -p` и тест-стенд проходят; инструкций `main.lua` на вызов меньше 10 % лимита (ориентир курса).
- На пульте значения виджета совпадают с экраном телеметрии, обрыв связи отрабатывает.

## references
- EdgeTX, исходный код, тег v2.12.5: radio/src/lua (widgets.cpp, lua_widget.cpp, lua_widget_factory.cpp, interface.cpp, api_general.cpp, api_colorlcd.cpp, api_colorlcd_lvgl.cpp) | https://github.com/EdgeTX/edgetx/tree/v2.12.5/radio/src/lua | primary | A
- EdgeTX v2.12.5: telemetry/crossfire.cpp и translations/untranslated.h — сенсоры CRSF | https://github.com/EdgeTX/edgetx/blob/v2.12.5/radio/src/telemetry/crossfire.cpp | primary | A
- EdgeTX v2.12.5: dataconstants.h и sdcard.h — длины имён и папки SD-карты | https://github.com/EdgeTX/edgetx/blob/v2.12.5/radio/src/dataconstants.h | primary | A
- EdgeTX Lua Reference Guide (репозиторий документации Lua API) | https://github.com/EdgeTX/lua-reference-guide | primary | A
- Lua 5.3 Reference Manual | https://www.lua.org/manual/5.3/ | primary | A
- EdgeTX Companion: симулятор, Telemetry Simulator и Debug Output (companion/src/simulation) | https://github.com/EdgeTX/edgetx/tree/v2.12.5/companion/src/simulation | primary | A

## notes
Сверено с исходным кодом EdgeTX v2.12.5 (коммит 0ebe2e9): типы скриптов, ключи таблицы виджета, аргументы `create` и `refresh`, условие вызова `background`, лимит инструкций, типы и число опций, функции `lcd.*` и константы, поведение `getValue` / `getSourceValue` / `getRSSI` при потере телеметрии, имена и единицы сенсоров CRSF, окна симулятора Companion. Код LinkBox проверен `luac5.3 -p` и тест-стендом на Lua 5.3.6 (та же версия, что в прошивке, но с 64-битными числами вместо 32-битных); на пульте автором не запускался — разметка в пикселях подобрана под зону 225 × 122 и может потребовать подгонки шрифтов. Не проверено: с какой версии EdgeTX есть `getSourceValue` (в 2.12.5 есть; для старых прошивок в коде оставлен запасной путь через `getValue`). Кириллицы в шрифте `lv_font_en_STD` нет — проверено по диапазонам символов в самом файле шрифта.
