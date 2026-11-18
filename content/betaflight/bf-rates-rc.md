---
id: bf-rates-rc
title: "Рейты, RC smoothing и feedforward: от стика до setpoint"
level: L2
readingTime: 40 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5); лабораторная снята на исходнике 4.5.6
status: published
added: 2026-11-14
tags:
  - Betaflight
  - рейты
  - RC smoothing
  - feedforward
  - ELRS
related:
  - bf-intro
  - bf-pid-reg-in-bf
  - bf-pid
  - bf-blackbox
  - bf-modes-osd
  - link-elrs
  - link-protocols
  - bf-cli
next:
  - bf-pid
---

## summary
Модуль разбирает путь команды от стика до setpoint — желаемой угловой скорости, с которой PID сравнивает гироскоп. Это калибровка каналов (`rxrange`), формулы пяти типов рейтов из `fc/rc.c`, кривая газа, профили рейтов, RC smoothing с автоподбором частоты среза по скорости приёмника и feedforward с его фильтрами от дрожания. Лабораторная — Python-порт формул прошивки. Он переводит рейты между Actual, Betaflight и Quick с сохранением центра и максимума и моделирует PT3-сглаживание ступеньки стика на ELRS 50…1000 Гц. Затем на железе: проверка `rxrange`, чтение `rc_smoothing_info` с реальным линком и слепое сравнение профилей рейтов с переключением в полёте.

## theory
### Цепочка от стика до PID
Порядок обработки (`rx/rx.c`, `fc/rc.c`, `flight/mixer.c`; одинаков в 4.5 и 2025.12):

1. Приёмник отдаёт канал в микросекундах. CRSF/ELRS: 172…1811 → **988…2012 мкс** (`rx/crsf.c`).
2. `rxrange` растягивает первые четыре канала (после `map`) из `min…max` в 1000…2000. AUX-каналы не масштабируются.
3. Проверка валидности: вне `rx_min_usec`…`rx_max_usec` (885…2115) канал считается плохим. Он 300 мс держит последнее значение, затем получает значение из `rxfail`, а для каналов 0–3 Betaflight объявляет потерю сигнала (failsafe).
4. Roll/pitch/yaw: `rcCommand = rcData − mid_rc` с вычетом `deadband` (`yaw_deadband`), ограничение ±500. Отклонение `x = rcCommand / (500 − deadband)` ∈ [−1; 1].
5. `applyRates(x)` даёт °/с, затем ограничение `*_rate_limit` (по умолчанию 1998). Результат — rawSetpoint.
6. Feedforward считается из rawSetpoint на каждом новом RC-пакете.
7. RC smoothing (PT3) сглаживает setpoint и feedforward на частоте PID-цикла. Дальше их берёт PID.
8. Газ: `(rcData − min_check)·1000/(2000 − min_check)` → кривая `thr_mid`/`thr_hover`/`thr_expo` → PT3 газа → `throttle_limit_*` в миксере.

{{diagram:chart-bf-rates-curves|Центр и максимум ещё не задают ощущение стика. Actual 20/67/54 и Betaflight 1.01/0.70/0.01 совпадают до 4 °/с. Дефолтный Actual 7/67/0 (70 → 670 °/с) с тем же центром и максимумом в Betaflight расходится до 151 °/с в середине хода.}}

### Пять типов рейтов (`rates_type`, по умолчанию ACTUAL)
Значения хранятся целыми: `rc_rate`, `srate`, `expo` по осям `roll_`/`pitch_`/`yaw_`. Ниже `x` — отклонение стика, `e = expo/100`. Формулы взяты из функций `apply*Rates()`.

| Тип | Формула, °/с | Центр (наклон при x→0) | Максимум (x = 1) |
|---|---|---|---|
| BETAFLIGHT | x' = x·\|x\|³·e + x·(1−e); 200·r·x' / (1 − \|x\|·s), r = rc_rate/100 (при r > 2: r += 14.54·(r−2)), s = srate/100 | 200·r·(1−e) | 200·r / (1−s) |
| ACTUAL | C·x + (M−C)·\|x\|·(x⁵·e + x·(1−e)), C = rc_rate·10, M = srate·10 | C | M |
| QUICK | R·x / (1 − c·k), R = rc_rate·2, k = (M/R − 1)/(M/R), c = \|x\|³·e + \|x\|·(1−e) | R | M = srate·10 |
| KISS | 2000·(rc_rate/1000)·(x³·e + x·(1−e)) / (1 − \|x\|·srate/100) | 2·rc_rate·(1−e) | 2·rc_rate / (1 − srate/100) |
| RACEFLIGHT | 10·rc_rate·x·(1 + e·(x²−1))·(1 + \|x\|·srate/100) | 10·rc_rate·(1−e) | 10·rc_rate·(1 + srate/100) |

Выводы из формул:
- В Actual три параметра независимы: centre sensitivity, max rate, expo. В Quick независим центр, а expo и rate вместе формируют кривую. В Betaflight, KISS и RaceFlight каждое число меняет и центр, и максимум.
- В Betaflight expo не трогает максимум, но снижает центр в (1−e) раз. Super rate поднимает край кривой гиперболой 1/(1 − |x|·s).
- Дефолт — ACTUAL 7/67/0 (и в 4.5, и в 2025.12): центр 70 °/с, максимум 670 °/с. При expo = 0 кривая Actual не линейна: квадратичный член (M−C)·x·|x| даёт 185 °/с на половине хода.
- QUICK при `quickrates_rc_expo = ON` применяет expo к самому стику, а не только к super-фактору.
- Лимиты по типу (`validateAndFixRatesSettings`, `config/config.c`) обрезают значения при загрузке конфига. rc_rate/srate: BETAFLIGHT 255/100, ACTUAL 200/200, QUICK 255/200, KISS 255/99, RACEFLIGHT 200/255. Expo везде до 100. При смене `rates_type` в CLI числа не пересчитываются: тот же 7/67/0 в Betaflight даёт 14 °/с в центре.

### Газ: `thr_mid`, `thr_hover`, `thr_expo`, `throttle_limit_*`
Кривая газа — таблица из 12 точек. В 2025.12 (`initRcProcessing()`) она строится из двух квадратичных кривых Безье, которые сходятся в точке (`thr_mid`, `thr_hover`): положение стика `thr_mid` даёт выход `thr_hover` (оба в процентах, дефолты 50 и 50). При `thr_expo = 0` получаются два прямых отрезка: (0, 0) → (`thr_mid`, `thr_hover`) → (100, 100); при равных `thr_mid` и `thr_hover` это одна прямая. С expo оба отрезка выгибаются так, что кривая уплощается вокруг точки висения: при `thr_expo = 100` касательная в ней горизонтальна. Так получают более мягкий газ около висения, а точку ставят туда, где аппарат реально висит. В 4.5 переменной `thr_hover` нет, кривая считалась по другой формуле (`tmp = 10·i − mid`, выход = `10·mid + tmp·(100 − expo + expo·tmp²/y²)/10`), и при `thr_expo = 0` **`thr_mid` ни на что не влиял**.

`throttle_limit_type` (OFF/SCALE/CLIP) с `throttle_limit_percent` (25…100) работает в миксере. SCALE умножает газ на процент. CLIP обрезает газ сверху. Это ограничитель для учебного аппарата и полётов в помещении, по профилю рейтов.

### Профили рейтов и переключение
Профилей рейтов **четыре** (и в 4.5, и в 2025.12) (`CONTROL_RATE_PROFILE_COUNT 4`, индексы 0–3). В профиль входит всё из таблицы ниже с пометкой «профиль»: тип, рейты, `thr_*`, `throttle_limit_*`, `*_rate_limit`, имя. Способы переключения:
- CLI `rateprofile` (без аргумента печатает текущий) и `rateprofile 2`. Переменные из `set`/`get` относятся к **текущему** профилю. `diff rates` выводит только текущий профиль, `diff all` — все четыре.
- Adjustments, функция **12** RATE_PROFILE: `adjrange <i> 0 <aux> 900 2100 12 <aux> 0 0`. Диапазон 900…2100 делится на три позиции по 400 мкс (0, 1, 2), смена профиля сопровождается position+1 бипами. С `rate_6pos_switch = ON` позиций шесть, но позиции 5–6 указывают на несуществующие индексы 4–5, и профиль не меняется. Работает в полёте.
- Команды стиками только в дизарме и в ACRO: газ вверх + тангаж вверх / тангаж вниз / крен вправо / крен влево → профили 1/2/3/4. В ANGLE/HORIZON те же сочетания подстраивают акселерометр.
- OSD-элемент `osd_rate_profile_name_pos`, имя задаётся в `rateprofile_name` (до 8 символов).
Профиль PID таким способом не переключается: у Adjustments нет функции PID-профиля.

### Концы каналов: `rxrange` и почему 988–2012
Синтаксис: `rxrange <0..3> <min> <max>`, где каналы 0–3 — roll, pitch, yaw, throttle после `map`, а min и max лежат в пределах 750…2250. Без аргументов команда печатает текущие значения, `rxrange reset` ставит дефолт 1000 2000. Масштабирование: `1000 + (raw − min)·1000/(max − min)`.

С ELRS/CRSF без калибровки стик доходит до 2012. `rcCommand` ограничен 500, поэтому полный рейт наступает уже на 2000 мкс, и последние 12 из 512 мкс (≈ 2.3 % хода) мертвы. То же с газом: `constrain(rcData, min_check, 2000)`. Внизу 988 < `min_check` 1050, так что арм не страдает. Решение — `rxrange 0 988 2012` для всех четырёх каналов. Тогда полный ход стика даёт ровно 1000…2000, а центр 1500 ± 1.

Входные пороги (вопрос FAQ «min_check vs min_command»): `min_check` 1050 и `max_check` 1900 — пороги газа и стиков для арма и стик-команд. Газ ниже `min_check` считается нулём. `mid_rc` 1500 — центр стиков. `rx_min_usec`/`rx_max_usec` 885/2115 — окно валидности сигнала. `min_command` и `motor_idle` (до 2025.12 — `dshot_idle_value`) — выходы на моторы, к RC не относятся. `deadband`/`yaw_deadband` (0…32/0…100) вырезают зону у центра. Они нужны только для изношенных гимбалов, потому что сужают ход стика.

### RC smoothing: PT3 по измеренной частоте приёмника
Без сглаживания setpoint меняется ступеньками раз в пакет: на 50 Гц — раз в 20 мс. D-член и feedforward превращают каждую ступеньку в пик на моторах. Отсюда «нотчи», нагрев и дрожь на частоте линка. Поэтому `rc_smoothing = ON` по умолчанию. Это PT3-фильтр на частоте PID-цикла для setpoint (roll/pitch/yaw) и для газа; feedforward в 2025.12 фильтруется тем же срезом, что setpoint (в 4.5 у FF был свой срез).

Автоматический режим действует для каждой частоты среза, если её `*_cutoff = 0` (так по умолчанию). В 2025.12 (`updateRcRefreshRate()`, `shouldUpdateSmoothing()`, `rcSmoothingSetFilterCutoffs()` в `fc/rc.c`):
- интервал пакетов ограничен окном 800…65 500 мкс; частота сглаживается фильтром первого порядка с k = 0.1;
- выброс — отсчёт, отличающийся от сглаженной частоты больше чем на 20 % (потерянный пакет, слот телеметрии): он в оценку не идёт. Три выброса подряд одного знака считаются сменой packet rate, и оценка сразу принимает новое значение;
- срезы пересчитываются на каждом 3-м принятом отсчёте: `cutoff = max(15, f_rx · 1.5 / (1 + auto_factor/10))` Гц, результат хранится целым (дробная часть отбрасывается). С `rc_smoothing_auto_factor = 30` это 0.375 · f_rx;
- при потере сигнала последняя оценка удерживается.

В 4.5 то же делалось иначе в деталях: окно 950…65 500 мкс, старт измерения через 1 с после включения, выброс — изменение интервала больше чем на 7/8 предыдущего, пересчёт на каждом 4-м отсчёте, сброс оценки при потере сигнала. Формула среза та же.

Ручной срез (`rc_smoothing_setpoint_cutoff`, `rc_smoothing_throttle_cutoff`, Гц; в 4.5 был ещё `rc_smoothing_feedforward_cutoff`, в 2025.12 удалён) фиксирует частоту. Его ставят для нестабильных линков: Crossfire без lock, прыгающий между 50 и 150 Гц, по примечаниям 4.3 держат на 20–30 Гц. По тем же примечаниям 4.3: factor 30 — норма, 20 — для гонок на 250/500 Гц, 90–120 — для кинематографичной съёмки. `rc_smoothing` выключать не рекомендуют.

Чтение `rc_smoothing_info` (формат строк из `cliRcSmoothing()` 2025.12.5, значения для ELRS 500 Гц рассчитаны; в 4.5 строк пять — первая `# RC Smoothing Type: FILTER`, срезы setpoint и FF отдельными строками, единица пишется `hz`):
```
# Detected Rx frequency: 500Hz
# RC Smoothing: ON
# Active setpoint and FF cutoff: 187Hz (auto)
# Active throttle cutoff: 187Hz (auto)
```
`NO SIGNAL` означает, что интервал не измерен (нет линка или USB без приёмника). Частота сильно ниже packet rate говорит о потере пакетов или неверно выбранном режиме ELRS. `(manual)` значит, что срез задан вручную. Те же числа пишутся в заголовок Blackbox (`rc_smoothing_active_cutoffs_ff_sp_thr`; в 2025.12 значений два — setpoint и газ), а `debug_mode = RC_SMOOTHING_RATE` логирует интервал и оценку частоты.

### Feedforward: производная setpoint с защитой от дрожания
`calculateFeedforward()` выполняется на каждом новом RC-пакете. В 2025.12:
- скорость = Δsetpoint · f_rx (°/с²); при дубликате пакета первая итерация экстраполирует прошлую скорость, следующие обнуляют. Экстраполяция выключена для CRSF/ELRS по UART (`feedforwardInterpolate` ложно при `serialrx_provider = CRSF`);
- `feedforward_jitter_factor` 7 (0…20): множитель = min(1, ((Δ + Δпред)/2 + 1) / (1 + 7)), где Δ — изменение `rcCommand` за пакет. При шаге 7 единиц (0.7 % хода) и больше FF проходит целиком, при неподвижном стике остаётся 1/8;
- `feedforward_smooth_factor` 65 (0…95): PT1 по скорости setpoint с постоянной времени τ = 4 мс · s/(1 − s), s = 65/100, то есть 7.4 мс. Число нормировано на 250 Гц: на любом packet rate сглаживание по времени одинаковое (в 4.5 это был коэффициент «на пакет», дефолт 25);
- `feedforward_boost` 15 (0…50): добавка от ускорения setpoint (вторая производная, сглаженная тем же PT1), компенсирует раскрутку моторов; только roll и pitch;
- `feedforward_max_rate_limit` 90 (0…200): на roll/pitch FF в сторону движения ограничен величиной (max_rate − |setpoint|)·90 и обнуляется у упора. Убирает перелёт в начале флипа;
- yaw: вместо boost и лимита — удержание `feedforward_yaw_hold_gain` 15 (0…100) · (setpoint − его PT1 с постоянной `feedforward_yaw_hold_time` 100 мс, 10…250). В 4.5 этих переменных нет;
- `feedforward_transition` 0 (0…100): ослабляет FF линейно до нуля, пока |x| меньше transition/100;
- `feedforward_averaging` 2_POINT (OFF / 2_POINT / 3_POINT / 4_POINT): скользящее среднее по пакетам, последним шагом (дефолт 4.5 — OFF);
- итог проходит PT3 со срезом setpoint и умножается на `Kf = 0.013754 · f/100`, где `f_roll`/`f_pitch`/`f_yaw` = 120/125/120.

Packet rate ELRS и FF. Интервалы из `common.cpp` (ELRS 4.1.0, в 3.x те же): LoRa 2.4 ГГц 50/150/250/500 Гц — 20 000/6666/4000/2000 мкс, F500 — 2000, F1000 — 1000. D250/D500 шлют каждый пакет 4×/2× с интервалом 1000 мкс, то есть дают 250/500 Гц новых данных. Слот телеметрии (1:16…1:128) периодически занимает место RC-пакета, и FC видит двойной интервал. Чем выше частота, тем меньше шаг `rcCommand` за пакет: jitter-фильтр сильнее гасит FF на медленных движениях (лаба, шаг 3), а шум гимбала сильнее проходит в FF. Примечания 4.3 (числа smooth там даны в шкале «на пакет» 4.3–4.5; в 2025.12 шкала нормирована на 250 Гц, а дефолты 2_POINT и 65 уже рассчитаны на быстрые линки): для 500 Гц `feedforward_smooth_factor` 65–70 и `feedforward_averaging = 2_POINT`, для 250 Гц — 2_POINT и smooth 35–40 (в другом месте документа 40–50), для Crossfire 150 — 3_POINT. Для F1000 официальной цифры нет; настройки 500 Гц как старт — экстраполяция, проверяй по Blackbox. При дёргании моторов с неподвижными стиками там же советуют jitter 10–12 и тестовый полёт с FF = 0.

### Что было иначе в 4.5
- `rc_smoothing_feedforward_cutoff` существовал: у FF был собственный срез, `rc_smoothing_info` печатал «Active FF cutoff» отдельной строкой.
- Оценка частоты RX: выброс — изменение интервала больше 7/8 предыдущего, пересчёт срезов на каждом 4-м отсчёте.
- Дефолты FF: `feedforward_averaging = OFF`, `feedforward_smooth_factor = 25` (коэффициент на пакет: 1 − 25/100 = 0.75); jitter-множитель считался как 1 − (1 − (Δ+Δпред)/(2·7))².
- `feedforward_yaw_hold_gain` и `feedforward_yaw_hold_time` отсутствовали.
- `thr_hover` отсутствовал: кривая газа — таблица `tmp = 10·i − mid`, выход = `10·mid + tmp·(100 − expo + expo·tmp²/y²)/10`; при `thr_expo = 0` получалась прямая, и `thr_mid` ни на что не влиял.
- Были `expresslrs_rate_index`/`expresslrs_switch_mode` (SPI ELRS), в 2025.12 удалены.
- Формулы рейтов, дефолт ACTUAL 7/67/0 и четыре профиля одинаковы в 4.5 и 2025.12.

### Справочная таблица (2025.12)
| Переменная / команда | По умолчанию | Диапазон | Смысл |
|---|---|---|---|
| `rates_type` | ACTUAL | BETAFLIGHT, RACEFLIGHT, KISS, ACTUAL, QUICK | модель кривой (профиль) |
| `roll_rc_rate`, `pitch_rc_rate`, `yaw_rc_rate` | 7 | 1…255 (лимит типа) | Actual: центр ×10 °/с; Betaflight: RC rate ×0.01; Quick: центр ×2 °/с |
| `roll_srate`, `pitch_srate`, `yaw_srate` | 67 | 0…255 (лимит типа) | Actual/Quick: максимум ×10 °/с; Betaflight: super rate ×0.01 |
| `roll_expo`, `pitch_expo`, `yaw_expo` | 0 | 0…100 | expo ×0.01 |
| `quickrates_rc_expo` | OFF | OFF/ON | Quick: expo на стик |
| `roll_rate_limit`, `pitch_rate_limit`, `yaw_rate_limit` | 1998 | 200…1998 | потолок setpoint, °/с |
| `thr_mid` / `thr_hover` / `thr_expo` | 50 / 50 / 0 | 0…100 | кривая газа через точку (mid, hover); `thr_hover` — с 2025.12, в 4.5 mid без expo не действует |
| `throttle_limit_type` / `throttle_limit_percent` | OFF / 100 | OFF, SCALE, CLIP / 25…100 | ограничение газа |
| `rateprofile_name` | пусто | 1…8 символов | имя для OSD |
| `rateprofile` | 0 | 0…3 | CLI: выбрать профиль рейтов |
| `rate_6pos_switch` | OFF | OFF/ON | 6 позиций у функции 12 |
| `rxrange <ch> <min> <max>` | 1000 2000 | 750…2250, ch 0…3 | CLI: калибровка концов каналов |
| `mid_rc` | 1500 | 1200…1700 | центр стиков |
| `min_check` / `max_check` | 1050 / 1900 | 750…2250 | пороги для арма и стик-команд |
| `rx_min_usec` / `rx_max_usec` | 885 / 2115 | 750…2250 | окно валидности канала |
| `deadband` / `yaw_deadband` | 0 / 0 | 0…32 / 0…100 | мёртвая зона у центра, мкс |
| `airmode_start_throttle_percent` | 25 | 0…100 | air mode включается после этого газа |
| `rc_smoothing` | ON | OFF/ON | PT3-сглаживание RC |
| `rc_smoothing_auto_factor` / `_auto_factor_throttle` | 30 / 30 | 0…250 | больше → ниже срез, плавнее, медленнее |
| `rc_smoothing_setpoint_cutoff` / `_throttle_cutoff` | 0 / 0 | 0…255 Гц | 0 = авто; срез setpoint действует и на FF (в 4.5 был отдельный `rc_smoothing_feedforward_cutoff`) |
| `rc_smoothing_info` | — | — | CLI: частота RX и активные срезы |
| `feedforward_transition` | 0 | 0…100 | ослабление FF у центра |
| `feedforward_averaging` | 2_POINT | OFF, 2_POINT, 3_POINT, 4_POINT | усреднение FF (в 4.5 дефолт OFF) |
| `feedforward_smooth_factor` | 65 | 0…95 | сглаживание FF, PT1 с τ = 4 мс · s/(1 − s) (в 4.5 дефолт 25, коэффициент на пакет) |
| `feedforward_jitter_factor` | 7 | 0…20 | порог подавления дрожания, ×0.1 % хода |
| `feedforward_boost` | 15 | 0…50 | вклад ускорения setpoint |
| `feedforward_max_rate_limit` | 90 | 0…200 | срез FF у максимального рейта |
| `feedforward_yaw_hold_gain` / `feedforward_yaw_hold_time` | 15 / 100 | 0…100 / 10…250 мс | удержание FF по yaw (с 2025.12) |
| `f_roll` / `f_pitch` / `f_yaw` | 120 / 125 / 120 | 0…1000 | усиление FF (профиль PID) |

### Место в системе

- **Получает:** каналы в микросекундах и частоту пакетов от приёмника (`link-elrs`, `link-protocols`); окно валидности канала, общее с failsafe (`bf-failsafe`); номер рейт-профиля от Adjustments (`bf-adjustments`).
- **Отдаёт:** setpoint — желаемую угловую скорость — и feedforward регулятору (`bf-pid-reg-in-bf`); форму кривой — режиму Angle (`bf-features-tour`); максимальную скорость рыскания — порогу yaw spin recovery в режиме AUTO (`bf-arming-safety`).
- **Если ошибиться здесь:** выключил `rc_smoothing` → ступеньки setpoint проходят в D и feedforward, на моторах пики на частоте линка и нагрев; в спектре это похоже на шум, который пытаются лечить фильтрами (`bf-filters`, `bf-blackbox`). Сменил `rates_type` без пересчёта чисел → 7/67/0 в типе Betaflight даёт 14 °/с в центре: аппарат вялый, как при низком P из `bf-pid`.

## practice
### Шаг 1. Порт формул и конвертер рейтов
Функции рейтов перенесены из `fc/rc.c` 4.5 строка в строку; формула не изменилась в 2025.12 (diff функций `apply*Rates()` между 4.5.3 и 2025.12.5 пуст). Конвертер держит центр (наклон в нуле) и максимум целевого профиля Actual. Оставшийся параметр формы (expo у Betaflight и Quick) он подбирает перебором 0…100, минимизируя RMS-разницу на 101 точке стика. Значения округляются до целых, как их хранит прошивка. Полный скрипт — 189 строк, ниже ядро:

```python
def bf_rates(x, rc_rate, srate, expo):            # applyBetaflightRates
    a = abs(x)
    if expo:
        e = expo / 100
        x = x * a**3 * e + x * (1 - e)
    r = rc_rate / 100
    if r > 2.0:
        r += 14.54 * (r - 2.0)                    # RC_RATE_INCREMENTAL
    rate = 200.0 * r * x
    if srate:
        rate *= 1.0 / min(max(1.0 - a * srate / 100, 0.01), 1.0)
    return rate

def actual_rates(x, rc_rate, srate, expo):        # applyActualRates
    a = abs(x)
    e = expo / 100
    ex = a * (x**5 * e + x * (1 - e))
    centre = rc_rate * 10.0
    stick = max(0.0, srate * 10.0 - centre)
    return x * centre + stick * ex

def quick_rates(x, rc_rate, srate, expo, rc_expo=False):   # applyQuickRates
    a = abs(x)
    rcr = rc_rate * 2
    max_dps = max(srate * 10, rcr)
    e = expo / 100
    sfc = (max_dps / rcr - 1) / (max_dps / rcr)
    if rc_expo:
        curve = x**3 * e + x * (1 - e)
        sf = 1 / min(max(1 - a * sfc, 0.01), 1)
        return max(-1998, min(1998, curve * rcr * sf))
    curve = a**3 * e + a * (1 - e)
    sf = 1 / min(max(1 - curve * sfc, 0.01), 1)
    return max(-1998, min(1998, x * rcr * sf))
```

Вывод `python3 rates_lab.py`:
```
== default 4.5 profile: ACTUAL 7/67/0 ==
centre 71 deg/s, max 670 deg/s, 50% stick 185 deg/s

== converter, target ACTUAL rc_rate=20 srate=67 expo=54 (centre 200, max 670 deg/s) ==
BETAFLIGHT rc_rate=101 srate= 70 expo=  1  RMS   2.5 deg/s
QUICK      rc_rate=100 srate= 67 expo=  0  RMS   2.5 deg/s
stick  ACTUAL  BETAFL   QUICK
 0.10      22      22      22
 0.25      64      61      61
 0.50     158     154     154
 0.75     317     317     317
 0.90     490     490     488
 1.00     670     673     670
centre   200     200     200
max |BF-Actual| = 4 deg/s at stick 0.42
max |Quick-Actual| = 4 deg/s at stick 0.42

== converter, target ACTUAL rc_rate=7 srate=67 expo=0 (centre 70, max 670 deg/s) ==
BETAFLIGHT rc_rate=208 srate=  3 expo= 89  RMS  95.4 deg/s
QUICK      rc_rate= 35 srate= 67 expo=  0  RMS 143.7 deg/s
stick  ACTUAL  BETAFL   QUICK
 0.10      13       7       8
 0.25      55      20      23
 0.50     185      73      63
 0.75     390     242     160
 0.90     549     455     325
 1.00     670     669     670
centre    71      71      70
max |BF-Actual| = 151 deg/s at stick 0.71
max |Quick-Actual| = 245 deg/s at stick 0.83
```
Разбор. Actual 200/670/0.54 переводится в Betaflight 1.01/0.70/0.01 и Quick 100/67/0 с расхождением до 4 °/с — пилот его не почувствует. Дефолт 70/670/0 так не переводится: у Actual с малым expo кривая близка к параболе, а super rate даёт гиперболу, которая лежит низко и взлетает у края. Совпадения центра и максимума мало, поэтому конвертер печатает RMS и максимальную ошибку. Наклон в центре совпал с формулой из таблицы: 200·1.01·0.99 = 200.

### Шаг 2. PT3-сглаживание ступеньки стика
Расчёт сделан по коду 4.5; формула среза и `pt3FilterGain` в 2025.12 не изменились, поэтому числа шага действительны и для 2025.12.

Стик резко идёт из центра в упор (setpoint 0 → 670 °/с) в момент t = 0. Первый пакет с новым значением приходит через T/2, где T — период пакетов. PID-цикл 8 кГц, PT3 с `pt3FilterGain` (срез × 1.961459177, как в `common/filter.c`), автоматический срез при factor 30. «Ripple» — максимум d(setpoint)/dt при плавном движении стика в упор за 100 мс, делённый на идеальный наклон. Это мера ступенчатости, которую увидят D и FF.

```
== RC smoothing (rc_smoothing_auto_factor = 30), step 0 -> 670 deg/s, PID loop 8 kHz ==
link        rx_Hz  cutoff_Hz  t50_ms  t90_ms  | OFF: t50  ripple ON  ripple OFF
CRSF 50        50        18    22.0    34.1  |     10.0      1.36      161.0
ELRS 150      150        56     7.2    11.2  |      3.4      1.37       54.0
ELRS 250      250        93     4.2     6.8  |      2.0      1.36       33.0
ELRS 500      500       187     2.1     3.5  |      1.0      1.33       17.0
ELRS F1000   1000       375     1.0     1.8  |      0.5      1.29        9.0

auto_factor sweep at ELRS 250 Hz:
factor   0: cutoff 375 Hz, t50   2.5 ms, t90   3.3 ms, ripple 4.13
factor  10: cutoff 187 Hz, t50   3.1 ms, t90   4.5 ms, ripple 2.28
factor  30: cutoff  93 Hz, t50   4.2 ms, t90   6.8 ms, ripple 1.36
factor  60: cutoff  53 Hz, t50   6.1 ms, t90  10.2 ms, ripple 1.10
factor  90: cutoff  37 Hz, t50   7.9 ms, t90  13.9 ms, ripple 1.04
factor 120: cutoff  28 Hz, t50   9.8 ms, t90  17.6 ms, ripple 1.02
```
Авто-режим держит ступенчатость постоянной (≈ 1.3–1.4 при factor 30), а задержку делает пропорциональной периоду пакета: переход с 50 на 500 Гц сокращает время до 50 % с 22 до 2.1 мс. Без сглаживания задержка вдвое меньше, но производная setpoint в 9–161 раз больше нормы — импульсы в D и FF. Factor 120 на 250 Гц даёт 9.8 мс: такова цена «кинематографичной» плавности.

{{diagram:chart-bf-rc-smoothing-step|Авто-сглаживание с factor 30 (срез 0.375·f_rx) оставляет задержку пропорциональной периоду пакета: до 50 % ступеньки за 22 мс на 50 Гц, 7.2 мс на 150 Гц, 2.1 мс на 500 Гц и 1.0 мс на F1000. Ступенька без сглаживания на 50 Гц приходит раньше, но целиком.}}

### Шаг 3. Jitter-фильтр, газ и throttle limit
Вывод снят на формулах 4.5; в 2025.12 jitter-множитель линейный (min(1, ((Δ+Δпред)/2 + 1)/(1 + jitter))), а кривая газа строится через точку (`thr_mid`, `thr_hover`) — числа этого шага для 2025.12 будут другими.

```
== feedforward_jitter_factor = 7: same slow stick move (half travel in 0.5 s) ==
   50 Hz: rcCommand delta  20.0/packet -> FF x 1.00
  150 Hz: rcCommand delta   6.7/packet -> FF x 1.00
  250 Hz: rcCommand delta   4.0/packet -> FF x 0.82
  500 Hz: rcCommand delta   2.0/packet -> FF x 0.49
 1000 Hz: rcCommand delta   1.0/packet -> FF x 0.27

== throttle curve: rcCommand[THROTTLE] (us) vs stick % ==
stick   mid50/expo0  mid50/expo50  mid40/expo50
  10%         1100          1172          1166
  30%         1300          1384          1347
  40%         1400          1448          1400
  50%         1500          1500          1451
  60%         1600          1552          1510
  90%         1900          1828          1820

throttle_limit_percent = 80:  stick 50% / 90% / 100%
OFF  : 50% / 90% / 100%
SCALE: 40% / 72% / 80%
CLIP : 50% / 80% / 80%
```
Одно и то же медленное движение (полхода за 0.5 с) на F1000 оставляет 27 % FF, на 50 Гц — 100 %. Высокая частота с дефолтным jitter 7 делает плавные движения «мягче», и это не ошибка настройки. Кривая газа подтверждает теорию для 4.5: `thr_mid` 40 без expo дал бы прямую, а с expo 50 точка 40 % стала неподвижной (1400), газ вокруг неё уплощился.

### Переход на реальное железо
Пропы сняты до пункта 4. Перед изменениями сохрани `diff all` в файл.

**1. `rxrange` с пультом (стол, АКБ можно не подключать).** На вкладке Receiver или через `rxrange` без аргументов запиши крайние значения каждого из четырёх каналов на полном ходе стиков (триммеры в нуле, EdgeTX limits ±100 %). Для ELRS ожидай 988/1500/2012 ± 1. Затем:
```
rxrange 0 988 2012
rxrange 1 988 2012
rxrange 2 988 2012
rxrange 3 988 2012
save
```
После перезагрузки упоры должны показывать 1000 и 2000 ± 2, центр — 1500 ± 2, газ внизу — ниже 1050. Если упор после `rxrange` выходит за 885…2115 (расширенные limits в пульте), канал считается невалидным, а через 300 мс наступает failsafe: верни limits к 100 %.

**2. `rc_smoothing_info` с реальным линком.** АКБ подключена, пропы сняты, связь установлена больше 2 с. Выполни `rc_smoothing_info` на каждом packet rate, который используешь: 150, 250, 500 Гц, F1000 (ELRS Lua, telemetry ratio запиши). Норма — `Detected Rx frequency` в пределах ±3 % от packet rate (для D250/D500 — 250/500), срез «setpoint and FF» = ⌊0.375·f⌋ ± 1 Гц, обе строки срезов `(auto)` (в 4.5 строк срезов три). Если частота ниже на 10 % и больше, это потерянные пакеты: проверь антенны и LQ.

**3. Три профиля на тумблере.** Помощник заполняет профили 0–2 в случайном порядке. Он один знает, где что лежит:
```
rateprofile 0
set rates_type = ACTUAL
set roll_rc_rate = 20
set roll_srate = 67
set roll_expo = 54
set rateprofile_name = A
rateprofile 1
set rates_type = BETAFLIGHT
set roll_rc_rate = 101
set roll_srate = 70
set roll_expo = 1
set rateprofile_name = B
rateprofile 2
set rates_type = ACTUAL
set roll_rc_rate = 7
set roll_srate = 67
set roll_expo = 0
set rateprofile_name = C
adjrange 0 0 2 900 2100 12 2 0 0
save
```
Это пример раскладки, помощник переставляет её как хочет. `pitch_*` в каждом профиле — те же числа, что `roll_*`. `rates_type` действует на все оси, поэтому yaw выставь одинаковым по ощущению: 20/67/54 в A и C, 101/70/1 в B. Иначе yaw в B останется 7/67/0, а в модели Betaflight это RC rate 0.07, и yaw почти мёртв. AUX3 (индекс 2) — 3-позиционный тумблер. Проверка на столе: в Betaflight App (PID Tuning, раздел рейтов) максимум всех трёх профилей 670 ± 7 °/с, OSD показывает A/B/C.

**4. Полёт (пропы ставятся здесь).** Поле с запасом 50 × 50 м, режим ACRO, высота от 5 м, Blackbox ≥ 1 кГц. В каждом профиле: 30 с плавных пролётов, по 5 бочек и флипов, серия быстрых стабов стиком. Переключай профиль только в ровном полёте при газе висения. Прерви полёт и вернись в позицию 1 тумблера, если аппарат не держит горизонт, если LQ меньше 70 % или если флип не выходит в ровный полёт. Пилот записывает, какие профили одинаковы. Критерии: пилот считает одинаковыми профили, где лежат 20/67/54 и 101/70/1, и отличает 7/67/0. В Blackbox `setpoint[0]` на полном стике 670 ± 1 % во всех трёх профилях. На половине хода стика setpoint отличается не больше чем на 10 °/с между «одинаковыми» и примерно на 27 °/с у третьего (158 против 185 °/с). Сохранить выбранный профиль: дизарм, затем stick-save или `save`.

Самопроверка: лабораторная выполнена, когда:
- **Расчёт (основной путь):** скрипт с функциями из `fc/rc.c` запущен, сдан вывод конвертера для двух профилей Actual с RMS и максимальной ошибкой, таблица PT3-сглаживания для 50/150/250/500/1000 Гц и расчёт jitter-фильтра.
- **Расчёт:** письменно объяснено, почему Actual 7/67/0 не переводится в Betaflight с ошибкой меньше 20 °/с.
- **Железо:** `rxrange` настроен, упоры 1000/2000 ± 2. Сданы выводы `rc_smoothing_info` для двух packet rate, частота в пределах ±3 %.
- **Железо:** слепое сравнение трёх профилей проведено, сдан Blackbox с `setpoint[0]` по каждому профилю и записи пилота.

## diagnostics
- **Симптом:** моторы дёргаются и греются при неподвижных стиках, на Blackbox у FF шумная «трава»
  - Возможная причина: шум гимбала или линка 250–1000 Гц проходит в feedforward; на 2025.12 — слишком малый `feedforward_smooth_factor` или `averaging = OFF` в перенесённом конфиге; на 4.5 дефолтные 25 и OFF рассчитаны на медленные линки.
  - Что сделать: вернуть дефолты 2025.12 (65 и `2_POINT`; на 4.5 для 500 Гц выставить их вручную), `feedforward_jitter_factor` 10–12. Проверочный полёт с `f_roll`/`f_pitch` = 0: если стало чисто, проблема в FF.
  - Что видно в логе: `debug_mode = FEEDFORWARD_LIMIT`, поле debug[3] (итоговый несглаженный FF по roll; в 4.5 — `debug_mode = FEEDFORWARD`, debug[3]) скачет при почти постоянном rcCommand.
- **Симптом:** стик «ватный», аппарат отстаёт на быстрых движениях
  - Возможная причина: низкий packet rate (50 Гц, срез 18 Гц), завышенный `rc_smoothing_auto_factor` или ручной срез.
  - Что сделать: `rc_smoothing_info`; поднять packet rate, вернуть factor 30 и `*_cutoff = 0`.
- **Симптом:** на 50 Гц или при `rc_smoothing = OFF` аппарат мелко трясётся, моторы шумят
  - Возможная причина: ступеньки setpoint раз в 20 мс, D и FF усиливают каждую.
  - Что сделать: `rc_smoothing = ON`, для нестабильного Crossfire — ручной срез 20–30 Гц.
- **Симптом:** `rc_smoothing_info` показывает `NO SIGNAL` или частоту намного ниже packet rate
  - Возможная причина: нет линка, плохой LQ, ELRS в другом режиме, частые выбросы интервала.
  - Что сделать: проверить связь и LQ на вкладке Receiver, повторить через 2 с после восстановления.
- **Симптом:** последние миллиметры хода стика ничего не меняют, полный рейт «раньше упора»
  - Возможная причина: CRSF отдаёт 988–2012, `rcCommand` ограничен ±500.
  - Что сделать: `rxrange <ch> 988 2012` для каналов 0–3.
- **Симптом:** после смены `rates_type` аппарат стал неуправляемо медленным или быстрым
  - Возможная причина: числа не пересчитаны: Actual 7/67 в Betaflight — это RC rate 0.07.
  - Что сделать: перевести профиль конвертером, затем проверить максимум на вкладке Rates.
- **Симптом:** тумблер профиля рейтов в позициях 5–6 ничего не меняет
  - Возможная причина: `rate_6pos_switch = ON`, а профилей только четыре.
  - Что сделать: 3-позиционный тумблер или диапазоны под индексы 0–3.
- **Симптом:** `thr_mid` изменён, а газ ведёт себя так же
  - Возможная причина: прошивка 4.5 и `thr_expo = 0` — там кривая без expo прямая. В 2025.12 `thr_mid` действует и без expo, если он не равен `thr_hover`.
  - Что сделать: на 4.5 задать `thr_expo` 20–50; на 2025.12 проверить пару `thr_mid`/`thr_hover` и точку висения на вкладке Rates.
- **Симптом:** `diff` после настройки не содержит рейтов других профилей
  - Возможная причина: `diff`/`diff rates` выводят только текущий профиль.
  - Что сделать: бэкап только через `diff all`.

## checklist
- `diff all` сохранён до изменений
- `rxrange` настроен для каналов 0–3, упоры 1000/2000, центр 1500
- Тип рейтов и числа проверены на вкладке Rates: центр, максимум, середина хода
- При смене `rates_type` профиль переведён с проверкой RMS-ошибки
- `rc_smoothing = ON`, `rc_smoothing_info` показывает реальную частоту линка и `(auto)`
- FF-параметры соответствуют packet rate (smooth, averaging, jitter)
- Профили рейтов названы (`rateprofile_name`), переключение проверено на столе
- После полёта выбранный профиль сохранён, `diff all` с датой в файле

## references
- Betaflight `fc/rc.c` (рейты, RC smoothing, feedforward), 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc.c | primary | A
- Betaflight `fc/controlrate_profile.c` (дефолты и лимиты рейтов) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/controlrate_profile.c | primary | A
- Betaflight `pg/rx.c` (rc_smoothing, mid_rc, min_check, rx_min_usec) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/pg/rx.c | primary | A
- Betaflight `cli/cli.c` (rxrange, rateprofile, rc_smoothing_info) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- Betaflight `flight/pid.c` (дефолты feedforward_*, f_*) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight `rx/crsf.c` (172…1811 → 988…2012 мкс) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/rx/crsf.c | primary | A
- Betaflight `fc/rc.c`, тег 2025.12.5 (сглаживание, FF, кривая газа) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/rc.c | primary | A
- Betaflight `flight/pid_init.c`, тег 2025.12.5 (нормировка feedforward_smooth_factor, yaw hold) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/pid_init.c | primary | A
- Betaflight 4.3 Tuning Notes (PT3 RC smoothing, jitter reduction, ELRS 250/500 Гц) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/tuning/4-3-Tuning-Notes.md | primary | A
- Betaflight Rate Calculator (типы рейтов, конвертеры) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Rate-Calculator.md | primary | B
- ExpressLRS `common.cpp` (интервалы и повторы пакетов по режимам) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/master/src/src/common.cpp | primary | B

## notes
Вывод `rc_smoothing_info` в теории собран по формату `cliRcSmoothing()` (2025.12.5) и частотам из лабы, с платы он не снят. Советы по FF для 250/500 Гц — из примечаний 4.3; описанные там механизмы есть в `rc.c` 4.5, а дефолты 2025.12 (2_POINT, 65) совпадают с советом для 500 Гц. Для F1000 официальной рекомендации не найдено.
