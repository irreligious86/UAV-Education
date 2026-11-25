---
id: bf-rates-rc
title: "Рейты, RC smoothing и feedforward: от стика до setpoint"
level: L2
readingTime: 55 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5) и 4.5.3 (конвейер FF, оценка частоты RX); лабораторные сняты на исходниках 4.5.6 и 4.5.3
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
Модуль разбирает путь команды от стика до setpoint — желаемой угловой скорости, с которой PID сравнивает гироскоп. Это калибровка каналов (`rxrange`), формулы пяти типов рейтов из `fc/rc.c`, кривая газа, профили рейтов, RC smoothing с автоподбором частоты среза по скорости приёмника и feedforward с его фильтрами от дрожания. Лабораторная — Python-порт формул прошивки. Он переводит рейты между Actual, Betaflight и Quick с сохранением центра и максимума и моделирует PT3-сглаживание ступеньки стика на ELRS 50…1000 Гц; второй скрипт воспроизводит конвейер feedforward 4.5.3 (jitter, дубликаты, boost, лимит у максимального рейта) и учит читать `debug_mode = FEEDFORWARD`. Затем на железе: проверка `rxrange`, чтение `rc_smoothing_info` с реальным линком и слепое сравнение профилей рейтов с переключением в полёте.

## theory
### Цепочка от стика до PID
Порядок обработки (`rx/rx.c`, `fc/rc.c`, `flight/mixer.c`; одинаков в 4.5 и 2025.12):

1. Приёмник отдаёт канал в микросекундах. CRSF/ELRS: 172…1811 → **988…2012 мкс** (`rx/crsf.c`).
2. `rxrange` растягивает первые четыре канала (после `map`) из `min…max` в 1000…2000. AUX-каналы не масштабируются.
3. Проверка валидности: вне `rx_min_usec`…`rx_max_usec` (885…2115) канал считается плохим. Он 300 мс держит последнее значение, затем получает значение из `rxfail`, а для каналов 0–3 Betaflight объявляет потерю сигнала (failsafe).
4. Roll/pitch/yaw: `rcCommand = rcData − mid_rc` с вычетом `deadband` (`yaw_deadband`), ограничение ±500. Отклонение `x = rcCommand / (500 − deadband)` ∈ [−1; 1]. В модуле «полный ход» — от упора до упора, 1000 единиц `rcCommand`; «половина хода» — от центра до упора, 500 единиц, x = 1.
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
- В Actual три параметра независимы: centre sensitivity, max rate, expo. В Quick центр (rc_rate·2) и максимум (srate·10) задаются напрямую, а форму между ними задаёт expo вместе с отношением M/R. В Betaflight, KISS и RaceFlight каждое число меняет и центр, и максимум.
- В Betaflight expo не трогает максимум, но умножает наклон в центре на (1 − e). Super rate поднимает край кривой гиперболой 1/(1 − |x|·s).
- Дефолт — ACTUAL 7/67/0 (и в 4.5, и в 2025.12): центр 70 °/с, максимум 670 °/с. При expo = 0 кривая Actual не линейна: квадратичный член (M−C)·x·|x| даёт 150 из 185 °/с на половине хода.
- QUICK при `quickrates_rc_expo = ON` применяет expo к самому стику, а не только к super-фактору.
- Лимиты по типу (`validateAndFixRatesSettings`, `config/config.c`) обрезают значения при загрузке конфига. rc_rate/srate: BETAFLIGHT 255/100, ACTUAL 200/200, QUICK 255/200, KISS 255/99, RACEFLIGHT 200/255. Expo везде до 100. При смене `rates_type` в CLI числа не пересчитываются: тот же 7/67/0 в Betaflight даёт 14 °/с в центре.

### Actual по коду: центр, максимум, expo
Функция из `fc/rc.c` 4.5.3, строки 209–219 (в 2025.12 тело то же, добавлено только `static`):
```c
float applyActualRates(const int axis, float rcCommandf, const float rcCommandfAbs)
{
    float expof = currentControlRateProfile->rcExpo[axis] / 100.0f;
    expof = rcCommandfAbs * (power5(rcCommandf) * expof + rcCommandf * (1 - expof));
    const float centerSensitivity = currentControlRateProfile->rcRates[axis] * 10.0f;
    const float stickMovement = MAX(0, currentControlRateProfile->rates[axis] * 10.0f - centerSensitivity);
    const float angleRate = rcCommandf * centerSensitivity + stickMovement * expof;
    return angleRate;
}
```
Три числа работают так:
- `centerSensitivity` C = `rc_rate`·10 — наклон кривой в нуле (centre sensitivity). Второе слагаемое растёт как x², его производная в нуле равна 0, поэтому чувствительность у центра задаёт только C.
- `stickMovement` = max(0, `srate`·10 − C) — добавка, которая поднимает край до максимума M = `srate`·10 (max rate). Если `srate`·10 < C, добавка обнуляется: кривая — прямая C·x, а максимум равен C, `srate` игнорируется.
- `expof` = |x|·(x⁵·e + x·(1 − e)). При e = 0 это x·|x|, парабола. При e = 1 это x⁵·|x|: до половины хода почти ноль, у края резкий рост. Expo перераспределяет добавку по ходу, концы кривой (0 и M) не трогает.

Разбор на числах: дефолт 70/670/0 (`7/67/0`) и «фристайл» 200/850/0.20 (`20/85/20`), стик на половине хода (x = 0.5):
- 70/670/0: expof = 0.5·(0 + 0.5·1) = 0.25; setpoint = 0.5·70 + 600·0.25 = 35 + 150 = **185 °/с**.
- 200/850/0.20: expof = 0.5·(0.5⁵·0.2 + 0.5·0.8) = 0.5·(0.00625 + 0.4) = 0.203125; setpoint = 0.5·200 + 650·0.203125 = 100 + 132.0 = **232.0 °/с**.

Наклон у упора — производная при x = 1: C + (M − C)·(2 + 4e). Это 70 + 600·2 = 1270 и 200 + 650·2.8 = 2020 °/с на полный ход, то есть **12.7 и 20.2 °/с на 1 % хода**. В центре — 0.7 и 2.0 °/с на 1 %. На половине хода второй профиль быстрее всего на 47 °/с (25 %), у центра — почти втрое, у упора — на 180 °/с. Поэтому профили сравнивают в трёх точках (центр, середина, максимум), а не по одному максимуму.

{{diagram:chart-bf-actual-two-profiles|Пунктир — линейная часть C·x: у дефолта 70/670/0 почти весь setpoint на середине хода (150 из 185 °/с) даёт квадратичная добавка, а у 200/850/0.20 линейная часть больше (100 из 232 °/с). Поэтому второй профиль острее у центра, хотя на середине хода разница всего 47 °/с.}}

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

С ELRS/CRSF без калибровки стик доходит до 2012. `rcCommand` ограничен 500, поэтому полный рейт наступает уже на 2000 мкс, и последние 12 из 512 мкс от центра до упора (≈ 2.3 % половины хода) мертвы. То же с газом: `constrain(rcData, min_check, 2000)`. Внизу 988 < `min_check` 1050, так что арм не страдает. Решение — `rxrange 0 988 2012` для всех четырёх каналов. Тогда полный ход стика даёт ровно 1000…2000, а центр 1500 ± 1.

Входные пороги (вопрос FAQ «min_check vs min_command»): `min_check` 1050 и `max_check` 1900 — пороги газа и стиков для арма и стик-команд. Газ ниже `min_check` считается нулём. `mid_rc` 1500 — центр стиков. `rx_min_usec`/`rx_max_usec` 885/2115 — окно валидности сигнала. `min_command` и `motor_idle` (до 2025.12 — `dshot_idle_value`) — выходы на моторы, к RC не относятся. `deadband`/`yaw_deadband` (0…32/0…100) вырезают зону у центра. Они нужны только для изношенных гимбалов, потому что сужают ход стика.

### RC smoothing: PT3 по измеренной частоте приёмника
Без сглаживания setpoint меняется ступеньками раз в пакет: на 50 Гц — раз в 20 мс. D-член и feedforward превращают каждую ступеньку в пик на моторах. Отсюда «нотчи», нагрев и дрожь на частоте линка. Поэтому `rc_smoothing = ON` по умолчанию. Это PT3-фильтр на частоте PID-цикла для setpoint (roll/pitch/yaw) и для газа; feedforward в 2025.12 фильтруется тем же срезом, что setpoint (в 4.5 у FF был свой срез).

Автоматический режим действует для каждой частоты среза, если её `*_cutoff = 0` (так по умолчанию). В 2025.12 (`updateRcRefreshRate()`, `shouldUpdateSmoothing()`, `rcSmoothingSetFilterCutoffs()` в `fc/rc.c`):
- интервал пакетов ограничен окном 800…65 500 мкс; частота сглаживается фильтром первого порядка с k = 0.1;
- выброс — отсчёт, отличающийся от сглаженной частоты больше чем на 20 % (потерянный пакет, слот телеметрии): он в оценку не идёт. Три выброса подряд одного знака считаются сменой packet rate, и оценка сразу принимает новое значение;
- срезы пересчитываются на каждом 3-м принятом отсчёте: `cutoff = max(15, f_rx · 1.5 / (1 + auto_factor/10))` Гц, результат хранится целым (дробная часть отбрасывается). С `rc_smoothing_auto_factor = 30` это 0.375 · f_rx;
- при потере сигнала последняя оценка удерживается.

В 4.5 детали другие (окно 950…65 500 мкс, старт через 1 с, другой критерий выброса), формула среза та же — разбор ниже, в подразделе про 4.5.3.

Ручной срез (`rc_smoothing_setpoint_cutoff`, `rc_smoothing_throttle_cutoff`, Гц; в 4.5 был ещё `rc_smoothing_feedforward_cutoff`, в 2025.12 удалён) фиксирует частоту. Его ставят для нестабильных линков: Crossfire без lock, прыгающий между 50 и 150 Гц, по примечаниям 4.3 держат на 20–30 Гц. По тем же примечаниям 4.3: factor 30 — норма, 20 — для гонок на 250/500 Гц, 90–120 — для кинематографичной съёмки. `rc_smoothing` выключать не рекомендуют.

Чтение `rc_smoothing_info` (формат строк из `cliRcSmoothing()` 2025.12.5, значения для ELRS 500 Гц рассчитаны; в 4.5 строк пять — первая `# RC Smoothing Type: FILTER`, срезы setpoint и FF отдельными строками, единица пишется `hz`):
```
# Detected Rx frequency: 500Hz
# RC Smoothing: ON
# Active setpoint and FF cutoff: 187Hz (auto)
# Active throttle cutoff: 187Hz (auto)
```
`NO SIGNAL` означает, что интервал не измерен (нет линка или USB без приёмника). Частота сильно ниже packet rate говорит о потере пакетов или неверно выбранном режиме ELRS. `(manual)` значит, что срез задан вручную. Те же числа пишутся в заголовок Blackbox (`rc_smoothing_active_cutoffs_ff_sp_thr`; в 2025.12 значений два — setpoint и газ), а `debug_mode = RC_SMOOTHING_RATE` логирует интервал и оценку частоты.

### Как 4.5.3 измеряет частоту приёмника
1. **Метка времени кадра.** Драйвер протокола запоминает момент приёма каждого RC-кадра (`lastRcFrameTimeUs`, для CRSF — в `rx/crsf.c:395`). `rxGetFrameDelta()` (`rx/rx.c:1025`) отдаёт разницу между двумя кадрами. `updateRcRefreshRate()` (`fc/rc.c:264`) ограничивает её окном 950…65 500 мкс (`RX_INTERVAL_MIN_US`/`MAX_US`), а интервал за пределами окна помечает невалидным. Отсюда же `currentRxRateHz` = 10⁶/интервал, по которому считается скорость setpoint для FF.
2. **Защитное время.** Первые 1000 мс после включения отсчёты не берутся (`rc.c:412`), чтобы PID-цикл успел установиться.
3. **Отбор отсчётов.** Отсчёт принимается, если интервал изменился меньше чем на 7/8 предыдущего (`rc.c:418`). Один слот телеметрии ELRS удваивает интервал (2000 → 4000 мкс, изменение 2000 > 1750) — такой отсчёт отбрасывается. Возврат к норме (4000 → 2000, изменение 2000 < 3500) принимается.
4. **Сглаживание и пересчёт.** Принятая частота идёт в фильтр первого порядка с k = 0.1 (`rc.c:424`). Срезы считаются на первом принятом отсчёте и затем на каждом 4-м (счётчик 3 → 0, `rc.c:436`). Срезов три: setpoint и FF — по `rc_smoothing_auto_factor`, газ — по `_throttle`; формула та же max(15, ⌊f·1.5/(1 + factor/10)⌋).
5. **Потеря сигнала.** Сбрасывается только счётчик (`rc.c:444`), сама оценка частоты остаётся. Первый же хороший отсчёт после восстановления сразу пересчитывает срезы.

Лаба (шаг 4, раздел 6) прогоняет этот алгоритм со слотом телеметрии в каждом 8-м пакете. На 500 Гц срез выходит на 187 ± 1 Гц через 1.13 с после включения, на 50 Гц — на 18 ± 1 Гц только через ≈ 1.7 с (1.68 с). Первый отсчёт после защитного времени всегда отбрасывается: `previousRxIntervalUs` до этого равен 0. Первый срез на 50 Гц — 15 Гц: фильтр стартует с нуля, и первая оценка равна 0.1·50 = 5 Гц.

### ELRS 50 Гц против 500 Гц
Packet rate меняет и сглаживание, и FF. Числа — из лабораторных этого модуля (4.5.3, factor 30, стик движется со скоростью 1500 единиц `rcCommand` в секунду, то есть половина хода за 0.33 с):

| Величина | 50 Гц | 500 Гц |
|---|---|---|
| Период пакета | 20 мс | 2 мс |
| Авто-срез PT3 setpoint и FF | 18 Гц | 187 Гц |
| Время до 50 % ступеньки стика | 22 мс | 2.1 мс |
| Шаг `rcCommand` за пакет | 30 | 3 |
| jitter-множитель FF (`jitter_factor` 7, 4.5.3) | 1.00 | 0.67 |
| τ сглаживания FF, `smooth_factor` 25 (4.5.3) | 6.7 мс | 0.67 мс |
| τ сглаживания FF, `smooth_factor` 65 (2025.12) | 7.4 мс | 7.4 мс |

Выводы. На 50 Гц PT3 сам режет FF срезом 18 Гц, а jitter-множитель на обычном движении равен 1.00: по расчёту лабы jitter-фильтр и smooth здесь почти ничего не меняют. Tuning Notes 4.3 говорят о том же: на 50 Гц шаги большие и проблемы дрожания почти нет. На 500 Гц срез 187 Гц пропускает шум гимбала, а шаг за пакет мал: jitter-фильтр 4.5.3 гасит треть FF на обычном движении. Сглаживание 25 «на пакет» на 500 Гц даёт всего 0.67 мс. Tuning Notes 4.3 требуют для 500 Гц smooth 65–70 (шкала «на пакет», τ ≈ 3.7–4.7 мс) и 2_POINT. В 2025.12 дефолт стал 65 и 2_POINT, но smooth нормирован на 250 Гц (комментарий в `pid_init.c`): τ = 7.4 мс на любом линке, то есть на 500 Гц сглаживание вдвое сильнее, чем по совету 4.3. Связь совета 4.3 и нового дефолта — вывод автора, в коде её нет.

{{lesson:link-elrs|Packet rate, телеметрия и режимы D250/D500/F1000 — откуда берётся частота пакетов, которую меряет Betaflight.}}

### Feedforward: производная setpoint с защитой от дрожания (2025.12)
`calculateFeedforward()` выполняется на каждом новом RC-пакете. В 2025.12:
- скорость = Δsetpoint · f_rx (°/с²); при дубликате пакета первая итерация экстраполирует прошлую скорость, следующие обнуляют. Экстраполяция выключена для CRSF/ELRS по UART (`feedforwardInterpolate` ложно при `serialrx_provider = CRSF`);
- `feedforward_jitter_factor` 7 (0…20): множитель = min(1, ((Δ + Δпред)/2 + 1) / (1 + 7)), где Δ — изменение `rcCommand` за пакет. При шаге 7 единиц (0.7 % полного хода) и больше FF проходит целиком, при неподвижном стике остаётся 1/8;
- `feedforward_smooth_factor` 65 (0…95): PT1 по скорости setpoint с постоянной времени τ = 4 мс · s/(1 − s), s = 65/100, то есть 7.4 мс. Число нормировано на 250 Гц: на любом packet rate сглаживание по времени одинаковое (в 4.5 это был коэффициент «на пакет», дефолт 25);
- `feedforward_boost` 15 (0…50): добавка от ускорения setpoint (вторая производная, сглаженная тем же PT1), компенсирует раскрутку моторов; только roll и pitch;
- `feedforward_max_rate_limit` 90 (0…200): на roll/pitch FF того же знака, что setpoint, ограничен величиной (max_rate − |setpoint|)·90 и обнуляется у упора. Убирает перелёт в конце флипа, когда стик дошёл до упора;
- yaw: вместо boost и лимита — удержание `feedforward_yaw_hold_gain` 15 (0…100) · (setpoint − его PT1 с постоянной `feedforward_yaw_hold_time` 100 мс, 10…250; при time < 100 усиление автоматически растёт в 150/(time + 50) раз). В 4.5 этих переменных нет;
- `feedforward_transition` 0 (0…100): ослабляет FF линейно до нуля, пока |x| меньше transition/100;
- `feedforward_averaging` 2_POINT (OFF / 2_POINT / 3_POINT / 4_POINT): скользящее среднее по пакетам, последним шагом (дефолт 4.5 — OFF);
- итог проходит PT3 со срезом setpoint и умножается на `Kf = 0.013754 · f/100`, где `f_roll`/`f_pitch`/`f_yaw` = 120/125/120.

Packet rate ELRS и FF. Интервалы из `common.cpp` (ELRS 4.1.0, в 3.x те же): LoRa 2.4 ГГц 50/150/250/500 Гц — 20 000/6666/4000/2000 мкс, F500 — 2000, F1000 — 1000. D250/D500 шлют каждый пакет 4×/2× с интервалом 1000 мкс, то есть дают 250/500 Гц новых данных. Слот телеметрии (по умолчанию от 1:16 на 50 Гц до 1:128 на 500 Гц/F1000, настраивается до 1:2) периодически занимает место RC-пакета, и FC видит двойной интервал. Чем выше частота, тем меньше шаг `rcCommand` за пакет: jitter-фильтр сильнее гасит FF на медленных движениях (лаба, шаг 3), а шум гимбала сильнее проходит в FF. Tuning Notes 4.3 (числа smooth там даны в шкале «на пакет» 4.3–4.5; в 2025.12 шкала нормирована на 250 Гц): для 500 Гц `feedforward_smooth_factor` 65–70 и `feedforward_averaging = 2_POINT`, для 250 Гц — 2_POINT и smooth 35–40 (в другом месте документа 40–50), для Crossfire 150 — 3_POINT. Для F1000 официальной цифры нет; настройки 500 Гц как старт — экстраполяция, проверяй по Blackbox. При дёргании моторов с неподвижными стиками там же советуют jitter 10–12 и тестовый полёт с FF = 0.

### Feedforward 4.5.3: конвейер по шагам
`processRcCommand()` (`fc/rc.c:628`) на каждом новом пакете считает x = `rcCommand`/(500 − deadband), `applyRates`, ограничение `*_rate_limit` и для каждой из трёх осей вызывает `calculateFeedforward()` (`rc.c:499–626`). Коэффициенты готовит `pid_init.c:414–424`. Порядок шагов как в коде:

1. **Скорость setpoint** (`rc.c:522`, `551`): v = (sp − sp_пред)·f_rx, °/с². Здесь f_rx = 10⁶/интервал текущего пакета. Это и есть FF: «насколько быстро пилот двигает стик».
2. **Дубликаты** (`rc.c:545–571`). Если `rcCommand` не изменился, первый такой пакет получает прошлую скорость плюс прошлое ускорение (ускорение — только если |sp| < 0.95·max), второй и следующие — ноль. Пакет с движением после дубликата считает скорость за два интервала, ускорение в нём обнуляется. Лечит пилу от пакетов-повторов, когда пульт обновляет каналы реже, чем шлёт линк. Модель лабы: каналы меняются раз в 4 мс при 500 Гц, то есть каждый второй пакет — повтор. Так бывает, если микшер не синхронизирован с модулем: 4 мс — только дефолтный период микшера EdgeTX (`mixer_scheduler.h`). С ELRS/CRSF EdgeTX подстраивает период микшера под packet rate модуля (`crossfireSetupMixerScheduler`, `pulses/crossfire.cpp`), и повторов почти нет. В лабе без этой логики FF скачет +9000/−6300 °/с², с ней зигзаг 1.6 %. *2025.12: для `serialrx_provider = CRSF` экстраполяция выключена, порог 0.90·max.*
3. **`feedforward_smooth_factor`** 25 (0…95): PT1 по скорости, k = 1 − 25/100 = 0.75 на пакет (`pid_init.c:418`, `rc.c:573`). Постоянная времени τ = T·s/(1 − s) = T/3: 1.33 мс на 250 Гц, 0.67 мс на 500 Гц. Лечит ступеньки FF от неровной частоты пакетов и квантования канала. *2025.12: τ = 4 мс·s/(1 − s) на любом линке, дефолт 65.*
4. **`feedforward_boost`** 15 (0…50): ускорение = Δv·f_rx·0.01, сглаженное тем же k, × 0.1·boost × jitter-множитель (`rc.c:582`, `pid_init.c:422`). В сумме boost/1000·Δv·f_rx. Компенсирует задержку раскрутки моторов в начале резкого движения. В 4.5.3 работает на всех трёх осях. В лабе на взмахе стика за 40 мс boost даёт 11 000 из пиковых 29 400 °/с². *2025.12: только roll/pitch, на yaw вместо него `feedforward_yaw_hold_*`.*
5. **`feedforward_transition`** 0 (0…100): при |x| < tr/100 FF умножается на |x|·100/tr (`rc.c:597`). Transition 30 на x = 0.15 даёт ×0.5. Убирает резкость у центра для плавной съёмки. *2025.12: так же.*
6. **`feedforward_averaging`** OFF (OFF, 2_POINT, 3_POINT, 4_POINT): скользящее среднее FF по последним 2…4 пакетам (`rc.c:603`, `common/filter.c:327`). Гасит зигзаг от чередования пакетов ценой задержки ≈ (N − 1)/2 периода пакета при окне N. *2025.12: дефолт 2_POINT, выполняется последним.*
7. **`feedforward_jitter_factor`** 7 (0…20): множитель считается в начале (`rc.c:535`), применяется здесь (`rc.c:607`). Если шаг за пакет Δ = |Δ`rcCommand`| < j, множитель = 1 − m², где m = max(0, 1 − (Δ + Δпред)/(2j)); при Δ ≥ j множитель 1. Boost умножается на него дважды, на шаге 4 и здесь. Гасит FF от дрожи пальцев и шума гимбала у неподвижного стика: при Δ = 0 два пакета подряд FF = 0. В лабе на 1500 ед./с множитель равен 1.00 на 150 Гц, 0.67 на 500 Гц и 0.38 на 1000 Гц. *2025.12: линейный min(1, ((Δ + Δпред)/2 + 1)/(1 + j)), у неподвижного стика 1/8, а не 0.*
8. **`feedforward_max_rate_limit`** 90 (0…200), только roll/pitch: если FF направлен туда же, куда setpoint, |FF| ≤ (max_rate − |sp|)·90 (`rc.c:611`). Значение входит в формулу как есть, без деления на 100. Лечит перелёт в конце флипа: стик дошёл до упора, а FF продолжает толкать. В лабе без лимита на пакете, где setpoint дошёл до 670 °/с, FF = 40 500 °/с² (F ≈ 668, больше `pidsum_limit` 500), на следующем пакете ещё 29 250 (F ≈ 483); с лимитом 90 — ноль. *2025.12: та же формула, но до transition и averaging.*
9. **Сглаживание и усиление.** `feedforwardRaw` проходит PT3 со срезом FF в каждом PID-цикле (`rc.c:480`). Затем `pid.c:1014` берёт его как `pidSetpointDelta`, а `pid.c:1081` даёт F = Kf·FF, где Kf = 0.013754·F/100 (`pid_init.c:277`, `pid.h:50`). Дефолты F (`pid.h:62–64`): **`f_roll` 120, `f_pitch` 125, `f_yaw` 120** (0…1000, `F_GAIN_MAX`), Kf = 0.0165 для 120. В режиме слайдеров F пересчитывается из дефолта × master × `simplified_feedforward_gain`/100, для pitch ещё × `simplified_pitch_pi_gain`/100 (`config/simplified_tuning.c:60`). На осях под Angle и при launch control FF обнуляется (`pid.c:1000–1015`, `1080`). *2025.12: F по умолчанию те же 120/125/120.*

{{diagram:flow-bf-ff-pipeline|Каждый фильтр конвейера лечит свою проблему: экстраполяция и PT1 — ступеньки от пакетов, jitter — дрожь неподвижного стика (в любом положении), max_rate_limit — перелёт у максимального рейта. PT3 и умножение на Kf идут уже на частоте PID-цикла.}}

### Что было иначе в 4.5
- `rc_smoothing_feedforward_cutoff` существовал: у FF был собственный срез, `rc_smoothing_info` печатал «Active FF cutoff» отдельной строкой.
- Оценка частоты RX: выброс — изменение интервала больше 7/8 предыдущего, пересчёт срезов на каждом 4-м отсчёте, при потере сигнала сбрасывается только счётчик.
- Дефолты FF: `feedforward_averaging = OFF`, `feedforward_smooth_factor = 25` (коэффициент на пакет: 1 − 25/100 = 0.75); jitter-множитель считался как 1 − (1 − (Δ+Δпред)/(2·7))² и только при Δ < 7.
- Boost действовал и на yaw; экстраполяция дубликатов работала для всех протоколов, включая CRSF; порядок шагов: boost → transition → averaging → jitter → limit.
- `feedforward_yaw_hold_gain` и `feedforward_yaw_hold_time` отсутствовали.
- `thr_hover` отсутствовал: кривая газа — таблица `tmp = 10·i − mid`, выход = `10·mid + tmp·(100 − expo + expo·tmp²/y²)/10`; при `thr_expo = 0` получалась прямая, и `thr_mid` ни на что не влиял.
- Были `expresslrs_rate_index`/`expresslrs_switch_mode` (SPI ELRS), в 2025.12 удалены.
- Формулы рейтов, дефолт ACTUAL 7/67/0 и четыре профиля одинаковы в 4.5 и 2025.12.

### Справочная таблица (2025.12; отличия 4.5.3 — в ячейках)
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
| `rc_smoothing_feedforward_cutoff` | 0 | 0…255 Гц | только 4.5: срез PT3 для FF, 0 = авто по `rc_smoothing_auto_factor`; в 2025.12 удалён |
| `rc_smoothing_debug_axis` | ROLL | ROLL, PITCH, YAW, THROTTLE | пишется только в заголовок Blackbox; на поля `debug_mode = RC_SMOOTHING` в 4.5.3 и 2025.12 не влияет |
| `rc_smoothing_info` | — | — | CLI: частота RX и активные срезы |
| `feedforward_transition` | 0 | 0…100 | FF × \|x\|·100/tr при \|x\| < tr/100 |
| `feedforward_averaging` | 2_POINT | OFF, 2_POINT, 3_POINT, 4_POINT | усреднение FF (в 4.5 дефолт OFF) |
| `feedforward_smooth_factor` | 65 | 0…95 | сглаживание FF, PT1 с τ = 4 мс · s/(1 − s) (в 4.5 дефолт 25, коэффициент на пакет) |
| `feedforward_jitter_factor` | 7 | 0…20 | порог шага `rcCommand` за пакет; 4.5.3: 1 − (1 − ΣΔ/2j)² при Δ < j, 2025.12: линейный |
| `feedforward_boost` | 15 | 0…50 | вклад ускорения setpoint, boost/1000·Δv·f_rx; roll/pitch (4.5.3 — все оси) |
| `feedforward_max_rate_limit` | 90 | 0…200 | roll/pitch: \|FF\| ≤ (max_rate − \|sp\|)·значение |
| `feedforward_yaw_hold_gain` / `feedforward_yaw_hold_time` | 15 / 100 | 0…100 / 10…250 мс | удержание FF по yaw (с 2025.12) |
| `f_roll` / `f_pitch` / `f_yaw` | 120 / 125 / 120 | 0…1000 | усиление FF (профиль PID), Kf = 0.013754·F/100 |
| `simplified_feedforward_gain` | 100 | 0…200 | слайдер: F = дефолт × master × gain/100 |
| `angle_feedforward` / `angle_feedforward_smoothing_ms` | 50 / 80 | 0…200 / 10…250 мс | FF в режиме Angle (отдельный путь, PT3) |
| `debug_mode` | NONE | FEEDFORWARD, FEEDFORWARD_LIMIT, RC_SMOOTHING, RC_SMOOTHING_RATE, RX_TIMING, RC_INTERPOLATION … | что пишется в поля debug[] Blackbox |

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

### Шаг 4. Feedforward 4.5.3 в Python и `debug_mode = FEEDFORWARD`
Скрипт `ff_lab.py` (228 строк) переносит `applyActualRates` и `calculateFeedforward()` из `fc/rc.c` 4.5.3 строка в строку, коэффициенты — из `pid_init.c:414–424`. Упрощения: одна ось (roll); `rcCommand` — гладкая рампа (реальный CRSF квантован шагом ≈ 0.62 мкс); PT3 RC smoothing на выходе не моделируется. Скрипт печатает `feedforwardRaw` — ровно то, что пишет debug FEEDFORWARD[3] (×0.1). Ядро (сокращено: без строк debug и переключателя экстраполяции):

```python
def step(self, rc_command, setpoint, deflection_abs, interval_us):
    interval_us = min(max(interval_us, 950), 65500)        # RX_INTERVAL_MIN/MAX_US
    rx_interval, rx_rate = interval_us * 1e-6, 1e6 / interval_us
    dabs = abs(rc_command - self.prev_rc); self.prev_rc = rc_command
    speed = setpoint - self.prev_sp; self.prev_sp = setpoint
    zero_acc, jitter_att = 1.0, 1.0
    if self.jit and dabs < self.jit:                        # rc.c:535
        j = max(1.0 - (dabs + self.prev_dabs) / (2 * self.jit), 0.0)
        jitter_att = 1.0 - j * j
    self.prev_dabs = dabs
    if dabs:                                                # movement
        if self.prev_dup:
            rx_rate = 1.0 / (rx_interval + self.prev_interval); zero_acc = 0.0
        speed *= rx_rate; self.prev_dup = False
    else:                                                   # duplicate packet
        if not self.prev_dup:
            speed = self.prev_speed + (self.prev_acc if abs(setpoint) < 0.95 * self.max_rate else 0.0)
        else:
            speed = 0.0; self.prev_speed = 0.0
        zero_acc = 0.0; self.prev_dup = True
    self.prev_interval = rx_interval
    speed = self.prev_speed + self.k * (speed - self.prev_speed)          # k = 1 - smooth/100
    acc = (speed - self.prev_speed) * rx_rate * 0.01; self.prev_speed = speed
    acc = self.prev_acc + self.k * (acc - self.prev_acc); self.prev_acc = acc * zero_acc
    ff = speed + acc * self.boost * jitter_att * zero_acc                 # boost = 0.1 * feedforward_boost
    if self.tr and deflection_abs < self.tr: ff *= deflection_abs * self.tr_inv
    if self.win > 1: ff = self._avg(ff)                                   # feedforward_averaging
    ff *= jitter_att
    if self.mrl and ff * setpoint > 0.0:                                  # max rate limit, roll/pitch
        limit = (self.max_rate - abs(setpoint)) * self.mrl
        ff = max(-limit, min(limit, ff)) if limit > 0.0 else 0.0
    return ff
```

Вывод `python3 ff_lab.py`. Разделы 1 (таблица Actual) и 5 (τ сглаживания) опущены, их числа приведены в теории; в разделе 4 опущены строки 52–60 мс, где все FF равны 0:
```
== 2. jitter attenuator (4.5.3), stick ramp 1500 rcCommand/s, read at x = 0.5 ==
Kf = 0.013754 * f_roll/100 = 0.01650 (f_roll = 120)
 rate_Hz  delta/packet  jitter_att  speed_deg/s2  FF_raw  F_term
      50          30.0       1.000          1758    1920    31.7
     150          10.0       1.000          1950    2112    34.9
     250           6.0       0.980          1988    2103    34.7
     500           3.0       0.673          1985    1410    23.3
    1000           1.5       0.383          2005     791    13.1
jitter factor sweep at 500 Hz (delta 3.0/packet):
  feedforward_jitter_factor  0: jitter_att 1.000, FF_raw  2147
  feedforward_jitter_factor  5: jitter_att 0.840, FF_raw  1782
  feedforward_jitter_factor  7: jitter_att 0.673, FF_raw  1410
  feedforward_jitter_factor 10: jitter_att 0.510, FF_raw  1054
  feedforward_jitter_factor 12: jitter_att 0.438, FF_raw   899
  feedforward_jitter_factor 20: jitter_att 0.278, FF_raw   563

== 3. duplicates: ELRS 500 Hz, MODEL ASSUMPTION: channels change every 4 ms (mixer not synced), jitter 0 ==
  zigzag = mean |FF_i - (FF_i-1 + FF_i+1)/2| / mean FF, packets with stick 0.30...0.36
  4.5.3 interpolation, averaging OFF  : FF_raw  1254  1254  1297  1297  1340  1340 | zigzag 0.016
  4.5.3 interpolation, averaging 2_POINT: FF_raw  1232  1254  1276  1297  1319  1340 | zigzag 0.000
  no interpolation,   averaging OFF  : FF_raw  9025 -6286  9327 -6502  9629 -6718 | zigzag 11.257
  no interpolation,   averaging 2_POINT: FF_raw  1477  1369  1520  1412  1564  1456 | zigzag 0.085

== 4. fast flick 0 -> full stick in 40 ms, ELRS 250 Hz, Actual 70/670/0 ==
  max_rate_limit 90 vs 0, boost 15 vs 0; FF_raw in deg/s^2, debug = FEEDFORWARD[0..3], FEEDFORWARD_LIMIT[0..3]
  t_ms  setpoint  FF(lim90,b15)  FF(lim0)  FF(boost0)  boost_part  debug FEEDFORWARD       debug FF_LIMIT
     0         0              0         0           0           0  [0, 0, 0, 0]            [0, 670, 0, 0]
     4        13           1219      1219        1219           0  [130, 122, 122, 122]    [100, 670, 13, 1219]
     8        38          15605     15605        4992       10613  [380, 499, 1560, 1560]  [100, 670, 38, 15605]
    12        75          19820     19820        8186       11635  [750, 819, 1982, 1982]  [100, 670, 75, 19820]
    16       124          22716     22716       11234       11482  [1240, 1123, 2272, 2272]  [100, 670, 124, 22716]
    20       185          25588     25588       14246       11342  [1850, 1425, 2559, 2559]  [100, 670, 185, 25588]
    24       258          28530     28530       17249       11281  [2580, 1725, 2853, 2853]  [100, 670, 258, 28530]
    28       343          29430     31510       20250       11260  [3430, 2025, 3151, 2943]  [100, 670, 343, 29430]
    32       440          20700     34503       20700       11253  [4400, 2325, 3450, 2070]  [100, 670, 440, 20700]
    36       549          10890     37501       10890       11251  [5490, 2625, 3750, 1089]  [100, 670, 549, 10890]
    40       670              0     40500           0       11250  [6700, 2925, 4050, 0]   [100, 670, 670, 0]
    44       670              0     29250           0           0  [6700, 2925, 2925, 0]   [100, 670, 670, 0]
    48       670              0         0           0           0  [6700, 0, 0, 0]         [0, 670, 670, 0]
  lim90_b15: peak FF_raw  29430, FF at setpoint 670 =    0, F_term peak 485.7
  lim0_b15 : peak FF_raw  40500, FF at setpoint 670 = 29250, F_term peak 668.4
  lim90_b0 : peak FF_raw  20700, FF at setpoint 670 =    0, F_term peak 341.6

== 6. RX-rate estimator 4.5.3 (rc.c:370-452), telemetry slot every 8th packet ==
   50 Hz: first cutoff  15 Hz at   1040 ms, within 1 Hz of final 18 Hz at   1680 ms after power-up
  500 Hz: first cutoff  18 Hz at   1004 ms, within 1 Hz of final 187 Hz at   1132 ms after power-up
```
Разбор.
- **Jitter.** Одно и то же движение даёт на 50–250 Гц F-член ≈ 32–35, на 500 Гц — 23, на 1000 Гц — 13. Это не «слабый FF на ELRS», а дефолтный jitter 7 при шаге 3 и 1.5 единицы за пакет. Варианты для 500 Гц на 4.5.3 (выбор автора, проверяй по Blackbox): поднять `f_*` или снизить jitter до 5 (множитель 0.84). Tuning Notes 4.3 допускают 5 только для гонок на чистом линке. Обратная сторона: меньший jitter пропускает больше шума гимбала, поэтому при дёргании моторов на неподвижном стике (первая строка диагностики) идут в другую сторону — 10–12.
- **Дубликаты.** Без экстраполяции каждый второй пакет даёт нулевую скорость, а boost превращает это в ±9000 °/с². 2_POINT убирает зигзаг почти целиком (0.085), но не до нуля, как экстраполяция. Так 2025.12 и работает с CRSF: экстраполяции нет, есть averaging и PT1 с τ 7.4 мс.
- **Флип.** До 24 мс лимит не мешает. С 28 мс он режет FF: (670 − 343)·90 = 29 430, у упора FF = 0. Без лимита на пакете, где setpoint дошёл до 670, FF = 40 500 °/с² (F ≈ 668, больше `pidsum_limit` 500), и на следующем пакете ещё 29 250 (F ≈ 483). Это и есть перелёт в конце флипа.
- **Первый пакет после покоя.** На 4 мс FF = 1219, хотя 13 °/с за 4 мс — это 3250 °/с². Пакеты в покое были дубликатами, поэтому скорость считается за два интервала (×0.5) и ещё проходит PT1 (×0.75).

**Как читать то же в Blackbox Explorer (4.5.3).** В CLI: `set debug_mode = FEEDFORWARD`, `set blackbox_sample_rate = 1/1` (или 1/2 на 8 кГц), `save`. Каналы пишутся только для roll — ось в коде зашита (`axis == FD_ROLL`, `rc.c:527–624`). Значения обновляются раз в пакет, поэтому на графике это ступеньки с шагом периода линка:
- debug[0] — rawSetpoint × 10 (°/с·10), до RC smoothing;
- debug[1] — сглаженная скорость setpoint × 0.1 (°/с² / 10), без boost;
- debug[2] — скорость + boost × 0.1, до transition, averaging, jitter и лимита;
- debug[3] — итоговый FF до PT3 × 0.1.

Разница debug[2] − debug[1] — это boost. Отношение debug[3]/debug[2] — это transition, averaging, jitter-множитель и лимит. В лабе на 28 мс это 2943/3151: лимит срезал ≈ 7 % (6.6 %). `debug_mode = FEEDFORWARD_LIMIT` даёт [0] jitter-множитель в %, [1] максимальный рейт оси, [2] setpoint, [3] итоговый FF без масштаба. Страница Debug Modes описывает раскладку 4.3: там debug[3] — «RC Command delta»; подписи полей в Explorer могут следовать ей (не проверено). Для 4.5.3 верь числам и этому списку, а не подписям. *2025.12: восемь полей — [0] setpoint ×1, [1] скорость ×0.01, [2] boost ×0.01, [3] Δ`rcCommand` ×10, [4] jitter %, [5] флаг дубликата, [6–7] yaw; ось выбирает `gyro_filter_debug_axis`.*

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

**3. Три профиля на тумблере.** Профили 0–2 заполняются в случайном порядке, которого ты до посадки не знаешь. Помощник не нужен — порядок выбирает генератор случайных чисел, а соответствие лежит в файле, который ты открываешь только после полёта. Процедура на одного: (а) разложи три набора рейтов из примера ниже по трём файлам `x.txt`, `y.txt`, `z.txt` — в каждом только строки `set rates_type`, `set roll_*`, такие же `set pitch_*` и yaw, без `rateprofile N` и без имени; (б) перемешай порядок, не глядя на результат: `python -c "import random; o=['x.txt','y.txt','z.txt']; random.shuffle(o); open('order.txt','w').write('\n'.join(o))"`; (в) в скрипте с функцией `cli(port, cmds)` из `bf-cli-automation` собери команды по `order.txt` и залей их, не выводя на экран: `cmds = []`, затем для каждой пары `i, f` из `enumerate(open('order.txt').read().split())` — `cmds += [f'rateprofile {i}'] + open(f).read().splitlines() + [f'set rateprofile_name = P{i}']`, затем `out = cli(port, cmds + ['adjrange 0 0 2 900 2100 12 2 0 0', 'save'])`, `open('load.log','w').write(out)` и `print(out.count('###ERROR'))` — должно напечатать 0; (г) до посадки не открывай `order.txt` и `load.log` и не заходи на вкладку рейтов; (д) после полёта и своих записей открой `order.txt`: строка 1 — файл, попавший в профиль P0, строка 2 — в P1, строка 3 — в P2. Пример раскладки трёх наборов (здесь с именами A/B/C, в слепом варианте имена — P0/P1/P2):
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
Это пример раскладки, порядок блоков переставляется произвольно. `pitch_*` в каждом профиле — те же числа, что `roll_*`. `rates_type` действует на все оси, поэтому yaw выставь одинаковым по ощущению: 20/67/54 в A и C, 101/70/1 в B. Иначе yaw в B останется 7/67/0, а в модели Betaflight это RC rate 0.07, и yaw почти мёртв. AUX3 (индекс 2) — 3-позиционный тумблер. Проверка на столе: в Betaflight App (PID Tuning, раздел рейтов) максимум всех трёх профилей 670 ± 7 °/с, OSD показывает A/B/C. В слепом варианте на вкладку рейтов не заходи (цифры выдадут порядок): проверка на столе — счётчик `###ERROR` равен 0 и OSD показывает P0/P1/P2 при переключении тумблера, а максимум 670 °/с проверяется после полёта по Blackbox.

**4. Полёт (пропы ставятся здесь).** Поле с запасом 50 × 50 м, режим ACRO, высота от 5 м, Blackbox ≥ 1 кГц. В каждом профиле: 30 с плавных пролётов, по 5 бочек и флипов, серия быстрых стабов стиком. Переключай профиль только в ровном полёте при газе висения. Прерви полёт и вернись в позицию 1 тумблера, если аппарат не держит горизонт, если LQ меньше 70 % или если флип не выходит в ровный полёт. Пилот записывает, какие профили одинаковы. Критерии: пилот считает одинаковыми профили, где лежат 20/67/54 и 101/70/1, и отличает 7/67/0. В Blackbox `setpoint[0]` на полном стике 670 ± 1 % во всех трёх профилях. На половине хода стика setpoint отличается не больше чем на 10 °/с между «одинаковыми» и примерно на 27 °/с у третьего (158 против 185 °/с). Сохранить выбранный профиль: дизарм, затем stick-save или `save`.

**5. Debug FEEDFORWARD на столе (4.5.3, пропы сняты, можно до пункта 4).** `set debug_mode = FEEDFORWARD`, `set blackbox_mode = ALWAYS` (лог пишется без арма, моторы не крутятся), `set blackbox_sample_rate = 1/2`, `save`. Запиши 20 с: стик крена неподвижен 5 с, затем 5 медленных проходов от центра до упора (около 1 с каждый) и 5 резких взмахов. Верни `blackbox_mode = NORMAL` и `debug_mode = NONE`. В Explorer критерии: при неподвижном стике |debug[3]| ≤ 5 (≈ 50 °/с², порог автора для этой проверки) большую часть времени (jitter-фильтр гасит дрожь); на упоре debug[0] = max_rate × 10 ± 1 % (после `rxrange`); после остановки стика debug[1] падает в 0 за 1–2 пакета; на резком взмахе у упора debug[3] заметно меньше debug[2] (работает лимит).

Самопроверка: лабораторная выполнена, когда:
- **Расчёт (основной путь):** скрипт с функциями из `fc/rc.c` запущен, и его вывод совпадает с выводом в модуле: конвертер для двух профилей Actual (RMS 2.5 °/с и максимум 4 °/с для 200/670/0.54; RMS 95.4 и максимум 151 °/с для 7/67/0), таблица PT3-сглаживания для 50/150/250/500/1000 Гц (срезы 18/56/93/187/375 Гц) и расчёт jitter-фильтра (FF × 1.00 на 50 Гц, × 0.27 на 1000 Гц).
- **Расчёт (FF 4.5.3):** `ff_lab.py` запущен, вывод совпадает с модулем: Actual 185.0 и 232.0 °/с на x = 0.5; jitter-множитель 0.673 на 500 Гц и 0.383 на 1000 Гц при 1500 ед./с; зигзаг 0.016 / 11.257 с экстраполяцией дубликатов и без неё; пик FF на флипе 29 430 с лимитом и 40 500 без него, на первых двух пакетах у упора без лимита — 40 500 и 29 250 °/с², с лимитом — 0; срез 187 ± 1 Гц через 1.13 с (500 Гц) и 18 ± 1 Гц через 1.68 с (50 Гц).
- **Расчёт:** ты письменно, для себя, объяснил, почему Actual 7/67/0 не переводится в Betaflight с ошибкой меньше 20 °/с, и сверил текст с эталоном ниже.
- **Железо:** `rxrange` настроен, упоры 1000/2000 ± 2. Сохранены выводы `rc_smoothing_info` для двух packet rate: частота в пределах ±3 %, срез равен ⌊0.375·f⌋ ± 1 Гц.
- **Железо:** лог debug FEEDFORWARD снят на столе, все четыре критерия пункта 5 выполнены.
- **Железо:** слепое сравнение трёх профилей проведено; в папке полёта лежат Blackbox и твои записи, а после вскрытия порядка выполняются критерии пункта 4: `setpoint[0]` на полном стике 670 ± 1 % во всех трёх профилях, на половине хода «одинаковые» расходятся не больше чем на 10 °/с, третий — примерно на 27 °/с (158 против 185 °/с).

**Эталон для самопроверки.** Правильное объяснение: у Actual с малым expo кривая близка к параболе, а super rate даёт гиперболу, которая лежит низко и взлетает у края; конвертер совмещает только центр и максимум, поэтому в середине хода остаётся до 151 °/с (стик 0.71). Объяснение «плохо подобран expo» неверно: перебор 0…100 уже выбрал лучший (89), ошибка — свойство формы кривой. Если у тебя RMS для 7/67/0 вышел около 2.5 °/с — в конвертер подан профиль 200/670/0.54 (`rc_rate` 20), а не дефолт. Если срез PT3 не равен 0.375·f — в расчёте стоит не factor 30. Для FF 4.5.3: если jitter-множитель на 500 Гц вышел 0.500 вместо 0.673 — взята линейная формула 2025.12 ((3 + 3)/2 + 1)/(1 + 7); если 0.429 — забыт квадрат: 1 − (1 − 6/14). Правильно 1 − (1 − 6/14)² = 0.673. Если на флипе FF при sp = 670 не ноль при лимите 90 — лимит умножен на 0.9 вместо 90. Если на 4 мс у тебя 2437, а не 1219, — не учтено, что пакеты в покое были дубликатами и скорость считается за два интервала.

## diagnostics
- **Симптом:** моторы дёргаются и греются при неподвижных стиках, на Blackbox у FF шумная «трава»
  - Возможная причина: шум гимбала или линка 250–1000 Гц проходит в feedforward; на 2025.12 — слишком малый `feedforward_smooth_factor` или `averaging = OFF` в перенесённом конфиге; на 4.5 дефолт 25 задан «на пакет», поэтому на 500 Гц даёт всего 0.67 мс, а averaging выключен.
  - Что сделать: вернуть дефолты 2025.12 (65 и `2_POINT`; на 4.5 для 500 Гц выставить их вручную), `feedforward_jitter_factor` 10–12. Проверочный полёт с `f_roll`/`f_pitch` = 0: если стало чисто, проблема в FF.
  - Что видно в логе: `debug_mode = FEEDFORWARD_LIMIT`, поле debug[3] (FF ×0.01 до averaging, ось `gyro_filter_debug_axis`, по умолчанию roll; в 4.5 — `debug_mode = FEEDFORWARD`, debug[3], ×0.1) скачет при почти постоянном rcCommand.
- **Симптом:** в конце флипа или бочки аппарат проскакивает максимальный рейт и отскакивает
  - Возможная причина: `feedforward_max_rate_limit = 0` или завышенный `feedforward_boost`: FF продолжает толкать у упора (лаба: 40 500 и 29 250 °/с² на первых двух пакетах у упора, F ≈ 668 и 483).
  - Что сделать: вернуть лимит 90 (дефолт), boost — не выше дефолта 15 (10–15 — ориентир автора).
  - Что видно в логе: на 4.5.3 в `debug_mode = FEEDFORWARD` у упора debug[3] ≈ debug[2]; на 2025.12 в `FEEDFORWARD_LIMIT` debug[3] (FF ×0.01) не падает, когда debug[2] (setpoint) ≈ debug[1] (max rate); gyro выше setpoint.
- **Симптом:** на 4.5.3 с ELRS 500 Гц / F1000 плавные движения запаздывают, FF «слабый»
  - Возможная причина: jitter 7 при шаге 1.5–3 единицы за пакет режет FF до 0.38–0.67.
  - Что сделать: поднять `f_roll`/`f_pitch` или снизить `feedforward_jitter_factor` до 5 (Tuning Notes 4.3 допускают 5 только для гонок на чистом линке; меньший jitter пропускает больше шума гимбала — при дёргании моторов на неподвижном стике идут в обратную сторону, 10–12); проверить в `FEEDFORWARD_LIMIT` debug[0] на плавных движениях.
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
- Betaflight `fc/rc.c`, тег 4.5.3 (applyActualRates, calculateFeedforward, оценка частоты RX) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc.c | primary | A
- Betaflight `flight/pid_init.c`, тег 4.5.3 (коэффициенты FF, Kf) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/flight/pid_init.c | primary | A
- Betaflight `rx/rx.c`, тег 4.5.3 (rxGetFrameDelta) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/rx/rx.c | primary | A
- Betaflight `build/debug.c`, тег 4.5.3 (имена debug_mode) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/build/debug.c | primary | A
- Betaflight Debug Modes (раскладка FEEDFORWARD 4.3) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Debug-Modes.md | primary | B
- Betaflight `fc/rc.c`, тег 2025.12.5 (сглаживание, FF, кривая газа) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/rc.c | primary | A
- Betaflight `flight/pid_init.c`, тег 2025.12.5 (нормировка feedforward_smooth_factor, yaw hold) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/pid_init.c | primary | A
- Betaflight 4.3 Tuning Notes (PT3 RC smoothing, jitter reduction, ELRS 250/500 Гц) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/tuning/4-3-Tuning-Notes.md | primary | A
- Betaflight Rate Calculator (типы рейтов, конвертеры) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Rate-Calculator.md | primary | B
- EdgeTX `pulses/crossfire.cpp` (crossfireSetupMixerScheduler: период микшера по packet rate модуля) | https://raw.githubusercontent.com/EdgeTX/edgetx/main/radio/src/pulses/crossfire.cpp | primary | B
- ExpressLRS `common.cpp` (интервалы и повторы пакетов по режимам) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/master/src/src/common.cpp | primary | B

## notes
Вывод `rc_smoothing_info` в теории собран по формату `cliRcSmoothing()` (2025.12.5) и частотам из лабы, с платы он не снят. Советы по FF для 250/500 Гц, jitter 10–12 / 5, factor 20 и 90–120, ручной срез 20–30 Гц — из Tuning Notes 4.3 (сверено с текстом документа 2026-11-25); описанные там механизмы есть в `rc.c` 4.5. Дефолты 2025.12 (2_POINT, 65) совпадают с советом для 500 Гц только по числу: шкала smooth в 2025.12 другая. Для F1000 официальной рекомендации не найдено. Помеченные «вывод/ориентир автора» пороги и советы получены из расчётов модуля, а не из документации.
