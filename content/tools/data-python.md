---
id: data-python
title: "Python для анализа полётных данных"
level: L2
readingTime: 55 мин
firmware: "Betaflight 4.5.3 / 2025.12.5 · ArduPilot 4.7.2 · Python 3.13: pandas 3.1.1, numpy 2.5.5, scipy 1.18.1, pymavlink 2.4.50"
status: published
added: 2026-11-08
tags:
  - Python
  - pandas
  - логи
  - спектр
related:
  - tools-overview
  - bf-blackbox
  - ap-logs
next:
  - ctl-signals
---

## summary
Blackbox Explorer и MAVExplorer показывают графики; инженеру нужны числа, которые можно сравнить до/после и записать в журнал настройки. Модуль — минимальный стек: Python + pandas + numpy + scipy + matplotlib; как прочитать лог Betaflight (через `blackbox_decode` в CSV) и ArduPilot (`.bin` через pymavlink), как определить настоящую частоту записи, как построить спектр гироскопа методом Уэлча и не обмануться разрешением и алиасингом, и как написать переиспользуемые функции метрик: overshoot, время нарастания и установления, задержка, bounce-back, джиттер цикла. Лабораторная идёт на настоящем логе ArduCopter 4.7.2 SITL с известной «вибрацией» 165 Гц и ступеньками по крену: каждое число в ней можно получить у себя и сравнить с эталоном.

## theory
### Стек и установка
```bash
python3 -m venv ~/uav-venv && source ~/uav-venv/bin/activate
pip install pandas numpy scipy matplotlib pymavlink
```
`blackbox_decode` — из репозитория betaflight/blackbox-tools (собирается `make`), превращает `.BFL` в CSV с одной строкой на записанный кадр.

Версии на ноябрь 2026 (проверены `pip index versions`; pandas, numpy, scipy и pymavlink ещё и установкой в чистый venv под Python 3.13, matplotlib — только по индексу): pandas 3.1.1, numpy 2.5.5, scipy 1.18.1, matplotlib 3.11.2, pymavlink 2.4.50. Ставь всё в отдельное виртуальное окружение (virtual environment, venv) и записывай версии в `requirements.txt` (`pip freeze > requirements.txt`): скрипт анализа — такой же инструмент измерения, как стенд, и через полгода он должен давать те же числа на том же логе.

Главное, что изменилось для старых скриптов, — pandas 3.0. Первое: Copy-on-Write включён всегда. Цепочка `df["gyroADC[0]"][маска] = 99` больше ничего не меняет в исходной таблице (pandas выдаёт `ChainedAssignmentError` как предупреждение), правильно — одним шагом через `df.loc[маска, "gyroADC[0]"] = 99`. Второе: текстовые колонки по умолчанию получают тип `str` (StringDtype), а не `object`. Для числовых полей лога это незаметно, но код, который проверял `dtype == object`, чтобы найти текст, ломается. Оба эффекта показаны в шаге 4 практики на реальном выводе pandas 3.1.1.

| Что | Где / как | Версия, проверено | Ловушка |
|---|---|---|---|
| `pd.read_csv(path, skipinitialspace=True)` | CSV из `blackbox_decode` | pandas 3.1.1 | разделитель `", "`: без `skipinitialspace` имена колонок начинаются с пробела |
| `df.loc[mask, col] = v` | любая правка таблицы | pandas ≥ 3.0 | цепочка `df[col][mask] = v` не работает (Copy-on-Write) |
| `pd.merge_asof(a, b, on="t", direction="nearest", tolerance=…)` | склейка сообщений с разной частотой | pandas 3.1.1 | обе таблицы отсортированы по `t`; без `tolerance` склеит и через дыру в логе |
| `mavutil.mavlink_connection("x.bin")` + `recv_match(type=[...])` | чтение DataFlash | pymavlink 2.4.50 | читать все нужные типы за один проход, а не по проходу на тип |
| `msg.to_dict()` | сообщение → строка таблицы | pymavlink 2.4.50 | поля-массивы `ISBD.x/y/z` приходят как `array('h')` |
| `scipy.signal.welch(x, fs, nperseg, noverlap, window)` | спектральная плотность | scipy 1.18.1 | Δf = fs / nperseg; при двух логах — одинаковые fs и nperseg |
| `scipy.signal.spectrogram` | спектр во времени | scipy 1.18.1 | окно короче — время точнее, частота грубее |
| `blackbox_decode --unit-rotation deg/s` | единицы гироскопа | blackbox-tools, коммит 49e18ca (23.11.2026) | меняет имя колонки на `gyroADC[0] (deg/s)` |
| `blackbox_high_resolution` | Betaflight 4.5.3, 2025.12.5 | по умолчанию OFF | при ON `gyroADC`, `gyroUnfilt`, `rcCommand[0–3]`, `setpoint[0–2]` ×10 (не `setpoint[3]` — газ ×1000) |
| `LOG_BITMASK` биты 0, 1, 7, 12, 18 | ArduCopter 4.7.2 | `ArduCopter/defines.h`, `Copter.cpp` | без бита 0 `RATE` — 10 Гц при бите 1, без битов 0 и 1 не пишется; без бита 18 `IMU` — 25 Гц при бите 7; `PIDx` — только с битом 12 |
| `INS_LOG_BAT_MASK`, `INS_LOG_BAT_CNT` | батч-сэмплер `ISBH/ISBD` | ArduPilot 4.7.2, по умолчанию 0 и 1024 | `ISBD.x / ISBH.mul` = рад/с; аксели и гироскоп чередуются (`ISBH.type` 0/1) |

### Чтение логов
**Betaflight CSV**: колонки `time (us)`, `gyroADC[0..2]` (град/с, после фильтров — `gyroADC`, до — `gyroUnfilt` (отдельное поле blackbox, включается выбором полей; в 4.5 нефильтрованный гироскоп можно было писать и в `debug[]` через `debug_mode = GYRO_SCALED`, в 2025.12 этого режима нет)), `setpoint[0..3]`, `motor[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[...]`, `eRPM[...]` при ESC-телеметрии.

```python
import pandas as pd, numpy as np
df = pd.read_csv("log.01.csv", skipinitialspace=True)
df.columns = [c.strip() for c in df.columns]
t = df["time (us)"].to_numpy() / 1e6
fs = 1 / np.median(np.diff(t))          # частота логирования, Гц (8000/4000/2000)
gyro_roll = df["gyroADC[0]"].to_numpy()
```

Как `blackbox_decode` называет колонки и в каких они единицах — вывод из его исходников (`src/blackbox_decode.c`, коммит 49e18ca). Время по умолчанию в микросекундах, поэтому колонка называется `time (us)`. Гироскоп по умолчанию выводится «как записан» (`--unit-rotation raw`), и тогда имя колонки — просто `gyroADC[0]`. Betaflight пишет в заголовок лога `gyro_scale = 1.0` и кладёт в поле `gyroADC` округлённые градусы в секунду (`blackbox.c`, строка `lrintf(gyro.gyroADCf[i] * blackboxHighResolutionScale)`), так что «raw» здесь уже и есть °/с. Если передать `--unit-rotation deg/s`, значения останутся теми же (печатаются с двумя знаками после точки), а имя колонки станет `gyroADC[0] (deg/s)` — и код с `df["gyroADC[0]"]` упадёт с `KeyError`. Вторая ловушка — `blackbox_high_resolution = ON` (по умолчанию OFF в 4.5.3 и 2025.12.5): прошивка умножает на 10 `gyroADC`, `gyroUnfilt`, `rcCommand[0–3]` и `setpoint[0–2]` (`setpoint[3]` — газ ×1000, он не масштабируется; `blackbox.c` 4.5.3, строки 1137–1155), а в исходниках `blackbox_decode` эта настройка не учитывается. Проверка — строка заголовка `H blackbox_high_resolution:1` в самом `.BFL` (это текст, его видно `grep`); если она есть, дели эти колонки (кроме `setpoint[3]`) на 10 сам.

Частота строк в CSV равна частоте цикла PID, делённой на `blackbox_sample_rate` (1/1, 1/2, 1/4, 1/8, 1/16; по умолчанию 1/4 — `blackbox.c`, `.sample_rate = BLACKBOX_RATE_QUARTER`): при 8 кГц цикла это 2 кГц. Но в анализе бери `fs` из временных меток, а не из настроек. Ошибка в `fs` сдвигает все частоты спектра в то же число раз: на синтетике в шаге 1 синус 210 Гц при `fs`, заниженной вдвое, «переезжает» на 105 Гц.

**ArduPilot .bin**:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("flight.bin")
rows = {"ATT": [], "RATE": []}
while (msg := m.recv_match(type=list(rows))) is not None:   # one pass for all types
    rows[msg.get_type()].append(msg.to_dict())
att = pd.DataFrame(rows["ATT"]); att["t"] = att["TimeUS"] / 1e6
```
Каждый тип сообщения — своя таблица со своей частотой, и частоту задаёт `LOG_BITMASK`, а не автопилот «вообще». В ArduCopter 4.7.2 (`Copter.cpp`, `loop_rate_logging` и `twentyfive_hz_logging`) `RATE` и `ANG` пишутся с частотой цикла только при бите 0 (ATTITUDE_FAST); без него — 10 Гц, если включён бит 1 (ATTITUDE_MED, он есть в умолчании), а без битов 0 и 1 не пишутся вовсе; `PIDx` дополнительно требуют бит 12 (PID). `IMU` пишется на частоте цикла только при бите 18 (IMU_FAST), а с одним битом 7 (IMU, тоже в умолчании) — 25 Гц. В лабораторном логе (`SCHED_LOOP_RATE = 400`, биты 0 и 18 включены) по меткам времени вышло: `IMU` и `RATE` — 400.2 Гц, `ATT` — 10.0 Гц. Значит, `ATT` не годится ни для спектра, ни для времени нарастания: за 100 мс между его строками ступенька успевает закончиться.

Единицы — из описания формата в самом логе (`FMTU`) и из исходников: `RATE.RDes/R` — °/с, `IMU.GyrX` — рад/с, `ATT.Roll` — градусы. Если IMU несколько, `IMU` идёт одной таблицей с колонкой `I` (номер датчика), и её надо отфильтровать: у двух датчиков одинаковые метки времени, половина интервалов dt равна нулю, и `rate_stats` по медиане выдаст `inf` (по среднему — вдвое больше, 800 Гц). Для спектров выше половины частоты цикла есть батч-сэмплер: `INS_LOG_BAT_MASK = 1` (первый IMU) пишет пачки по `INS_LOG_BAT_CNT` = 1024 отсчёта с той частотой, на которой драйвер отдаёт отсчёты (в лабораторной 1000 Гц; полную частоту датчика даёт бит 0 `INS_LOG_BAT_OPT`, по умолчанию `INS_LOG_BAT_OPT = 0`) — заголовок `ISBH` (номер пачки `N`, `type` 0 — акселерометр, 1 — гироскоп, множитель `mul`, частота `smp_rate`) и 32 сообщения `ISBD` по 32 отсчёта на ось. Значение в рад/с = `ISBD.x / ISBH.mul`; пачки акселерометра и гироскопа чередуются, а между пачками — разрыв, поэтому Уэлч считают по каждой пачке отдельно и усредняют, или по склеенным пачкам с окном, равным длине пачки (или её делителю), без перекрытия — иначе часть окон ложится на шов. Функция `spectrum` в лабораторной для простоты берёт перекрытие 50 % по склейке; пики от этого сдвинулись не больше чем на бин, но для точных измерений используй схему без перекрытия.

Склеить таблицы разной частоты помогает `pd.merge_asof`: к каждой строке `ATT` (10 Гц) подбирается ближайшая строка `RATE` (400 Гц) не дальше `tolerance`. На лабораторном логе все 674 строки `ATT` нашли пару в пределах 5 мс; если бы `RATE` отфильтровали по режиму, а `ATT` нет, пустых строк были бы сотни — и это видно сразу, если печатать число `NaN` после склейки. Скорость чтения: лог 16.9 МБ из лабораторной (шесть типов сообщений, один проход) читается за 1.2 с. Для логов в сотни МБ сужай `type=[...]` до нужных сообщений или один раз выгружай CSV через `mavlogdump.py --types RATE --format csv`.

{{lesson:ap-logs|Что включает каждый бит LOG_BITMASK и сколько это стоит по объёму SD — разобрано там.}}

### Спектр: почему Уэлч, а не один FFT
FFT всего лога — шумный и зависит от длины. Метод Уэлча режет сигнал на перекрывающиеся окна, берёт FFT каждого и усредняет: оценка спектральной плотности с контролируемым разрешением (Δf = fs / nperseg).

```python
from scipy.signal import welch
f, pxx = welch(gyro_roll, fs=fs, nperseg=1024, noverlap=512, window="hann")
pxx_db = 10 * np.log10(pxx + 1e-12)
```
При fs = 8000 и nperseg = 1024 разрешение 7.8 Гц; пик мотора на 250 Гц виден как бугор шириной 2–3 бина. Сравнивать логи — только при одинаковых fs и nperseg. Сегмент для спектра — висение или ровный полёт 10–20 с, без газа в пол (иначе пики размазываются по частотам).

Выбор `nperseg` — обмен разрешения на шум оценки. Длинное окно даёт узкие бины, но окон в записи меньше и усреднять нечего; короткое — гладкая кривая, но два близких пика сливаются. На батч-логе лабораторной (1000 Гц, 33 пачки гироскопа) `nperseg = 256` дал Δf = 3.91 Гц и пик 164.1 Гц, `nperseg = 1024` — Δf = 0.98 Гц и пик 166.0 Гц; введённая частота 165 Гц, оба ответа верны в пределах одного-двух бинов. Ориентир курса: Δf не грубее 5 Гц для поиска пиков моторов и не меньше 8–10 окон на оценку.

Вторая граница — частота Найквиста fs/2: всё, что выше, не исчезает, а отражается. Составляющая f при дискретизации fs видна на частоте |f − k·fs| для ближайшего целого k. Лог `IMU` на 400 Гц честно показал 166.1 Гц, потому что 165 < 200. Пик мотора 250 Гц в таком логе появился бы на |250 − 400| = 150 Гц — фантом, по которому notch ставят мимо. Поэтому шум моторов ищут в батч-сэмплере на частоте датчика или в `gyroUnfilt` Betaflight на 2 кГц, а не в 400-герцевом `IMU` и тем более не в 10-герцевом `ATT`.

### Спектрограмма
```python
from scipy.signal import spectrogram
f, tt, S = spectrogram(gyro_roll, fs=fs, nperseg=512, noverlap=256)
# imshow(10*log10(S), aspect="auto", origin="lower", extent=[tt[0], tt[-1], f[0], f[-1]])
```
Показывает, как пики едут с оборотами (моторы) или стоят (резонанс) — модуль «Сигналы и спектры».

### Метрики переходного процесса
По паре setpoint → gyro на одной оси:

- **Ошибка** e(t) = setpoint − gyro.
- **Overshoot** — насколько gyro перелетает setpoint после ступеньки, в % от величины ступеньки.
- **Время нарастания** — от 10 % до 90 % ступеньки; характеризует быстроту, не путай с задержкой.
- **Время установления** — через сколько мс gyro остаётся в ±5% (или ±2%) от setpoint.
- **Bounce-back** — после резкой остановки стика (setpoint → 0) gyro уходит в противоположную сторону: амплитуда отскока в % от пикового значения перед остановкой.
- **Задержка** — лаг между setpoint и gyro по максимуму кросс-корреляции или, проще, по моменту, когда оба проходят 50 % ступеньки.

Удобная реализация — не искать ступеньки вручную, а строить **step response** деконволюцией (как PID Toolbox): считать импульсную характеристику системы setpoint→gyro по окнам и интегрировать. Проще для начала — отобрать участки, где setpoint быстро меняет уровень, и мерить на них.

Как находить ступеньки — по уровню, а не по производной. В Betaflight setpoint следует за стиком почти мгновенно, и порог по |d setpoint/dt| работает. В ArduPilot цель по скорости ограничена ускорением `ATC_ACC_R_MAX` (в 4.7 — °/с², 1100 в лабораторной; до 4.7 — `ATC_ACCEL_R_MAX` в сантиградусах/с²): за номинальный отсчёт 2.5 мс она растёт не больше чем на 1100 × 0.0025 ≈ 2.75 °/с (в логе максимум около 4 °/с: интервал между отсчётами доходит до 3.3 мс), а до 112 °/с — примерно за 0.1 с. Порог по производной на таком логе не находит ни одной ступеньки — это и случилось с первой версией функции. Надёжнее: событие — момент, когда |setpoint| пересёк порог (60 °/с), начало окна — последняя точка перед ним, где |setpoint| был меньше 2 % порога, цель — медиана setpoint на плато.

```python
def step_metrics(t, sp, gy, thr_dps=60.0, win_s=0.45):
    """Steps of the rate setpoint (|sp| rises from <2 % to >thr): overshoot %, rise 10-90 %,
    settle into +-5 % (ms), lag at 50 %. Detects by level, not by d(sp)/dt."""
    res, hi = [], np.abs(sp) > thr_dps
    for k in np.where(hi[1:] & ~hi[:-1])[0] + 1:
        i = k - np.argmax(np.abs(sp[k::-1]) < 0.02 * thr_dps)      # back to the quiet start
        j = np.searchsorted(t, t[i] + win_s)
        base, target = sp[i], np.median(sp[k:j])
        step = target - base
        r, q = (gy[i:j] - base) / step, (sp[i:j] - base) / step
        tt = (t[i:j] - t[i]) * 1000
        out = np.abs(r - 1) > 0.05
        last_out = np.where(out)[0][-1] if out.any() else -1
        res.append({"t_s": round(t[i], 2), "step_dps": round(step),
                    "overshoot_pct": max(0.0, r.max() - 1) * 100,
                    "rise_ms": tt[np.argmax(r >= 0.9)] - tt[np.argmax(r >= 0.1)],
                    "settle_ms": tt[last_out + 1] if last_out + 1 < len(tt) else np.nan,
                    "lag_ms": tt[np.argmax(r >= 0.5)] - tt[np.argmax(q >= 0.5)]})
    return pd.DataFrame(res)
```

**Bounce-back**:
```python
def bounce_back(t, sp, gy, thr_dps=60.0, win_s=0.3):
    """After |sp| drops from >thr to ~0: reversal of gyro against the old direction, % of peak.
    The window ends where the next manoeuvre starts, or the next stick input counts as bounce."""
    out, hi, quiet = [], np.abs(sp) > thr_dps, np.abs(sp) < 0.1 * thr_dps
    for k in np.where(~hi[1:] & hi[:-1])[0] + 1:
        peak = np.median(sp[max(0, k - 40):k])
        q0 = k + np.argmax(quiet[k:])                       # setpoint back near zero
        nxt = q0 + np.argmax(~quiet[q0:]) if (~quiet[q0:]).any() else len(sp)
        j = min(np.searchsorted(t, t[k] + win_s), nxt)
        out.append(100 * max(0.0, (-np.sign(peak) * gy[k:j]).max()) / abs(peak))
    return np.array(out)
```
Ориентиры курса для 5" (Betaflight): overshoot 5–15% — хорошо; bounce-back < 10% — хорошо, > 25% — много D или плохая механика.

Окно bounce-back обязано заканчиваться там, где начинается следующий манёвр. В лабораторной после правой ступеньки стик стоит в центре 0.3 с, потом идёт левая. С фиксированным окном 0.3 с первая версия функции насчитала отскок 15–20 % после каждой правой ступеньки и 2 % после левой — это был не отскок, а начало следующей команды. С обрезкой окна по следующему уходу setpoint от нуля все 12 значений легли в 1.8–2.2 %. Правило одно для всех метрик: смотри, что попало в окно, прежде чем верить числу, и записывай медиану по 10–20 событиям, а не лучшее.

{{diagram:step-metrics-anatomy|Что считают функции: overshoot — перелёт над нормированной ступенькой, время установления — вход в ±5 % навсегда, bounce-back — отскок после отпущенного стика в процентах от пика (форма отклика условная).}}

Как читать результат на реальном логе. Ступенька крена ArduCopter в SITL (первая из шести правых в лабораторной): цель растёт до 112 °/с примерно за 100 мс, `R` проходит 50 % на 30 мс позже цели, от 10 до 90 % — за 120 мс, в коридор ±5 % входит на 202 мс и остаётся в нём; перелёта нет. У левых ступенек время установления — `NaN`: установившаяся ошибка около 5 % лежит на самой границе коридора. Это не сбой функции, а сигнал выбрать коридор осознанно и записать его рядом с числом.

{{diagram:chart-dpy-sitl-roll-step|Реальная ступенька крена из лабораторного лога ArduCopter 4.7.2 SITL: цель (RDes) ограничена по ускорению и растёт около 100 мс, отклик (R) отстаёт на 30 мс на уровне 50 % и входит в коридор ±5 % через 202 мс без перелёта.}}

### Джиттер цикла
```python
dt = np.diff(t) * 1e6   # мкс
print(dt.mean(), dt.std(), np.percentile(dt, 99.9))
```
Для 8 кГц среднее 125 мкс, std единицы мкс; std > 10 — перегруженный процессор, пропуски — обрыв записи (ориентир курса для Betaflight на F7/H7). Лабораторный лог ArduCopter SITL при 400 Гц: среднее 2500.0 мкс, std 28.7 мкс, 99.9-й перцентиль 3332 мкс, разрывов длиннее двух периодов нет. Разрыв (`dt` больше двух медианных периодов) режет спектр: Уэлч по куску с дырой даёт ложную энергию на низких частотах, поэтому сегменты для спектра выбирают между разрывами.

{{diagram:log-analysis-pipeline|Конвейер анализа лога на Python: CSV → DataFrame → общая ось времени → спектры и метрики → отчёт.}}

### Место в системе

- **Получает:** логи: CSV из `blackbox_decode` (`bf-blackbox`), DataFlash `.bin` (`ap-logs`), ULog через `pyulog` (`px4-intro`); состав и частоту записи (`blackbox_sample_rate`, `LOG_BITMASK`, `INS_LOG_BAT_MASK`); смысл спектра и спектрограммы (`ctl-signals`).
- **Отдаёт:** числа «до/после» — overshoot, время нарастания и установления, задержку, bounce-back, спектры — тюнингу (`bf-pid`, `ap-tuning`); оценки по спектрам — идентификации (`ctl-sysid`); функции, которые CI прогоняет на логах контрольных полётов (`eng-ci-configs`).
- **Если ошибиться здесь:** сравнил спектры с разными fs и `nperseg` → «улучшение» оказалось артефактом → фильтры меняют зря (`bf-filters`). Искал шум моторов в 400-герцевом `IMU` → пик 250 Гц отразился на 150 Гц → notch ставят мимо (`ctl-signals`, `ap-tuning`). Не заметил `blackbox_high_resolution` → все скорости в 10 раз больше → «перелёт» и рейты в отчёте неверны (`bf-blackbox`).

## practice
Главный путь — без железа: синтетика с известным ответом, затем настоящий лог ArduCopter 4.7.2 SITL, который ты генерируешь сам. В логе заранее известны два «ответа»: вибрация гироскопа на 165 Гц (`SIM_VIB_FREQ_X/Y/Z = 165`, амплитуда задаётся `SIM_GYR1_RND = 20` °/с × газ) и двенадцать ступенек по крену в ACRO (стик ±0.4 хода, пары «вправо 0.5 с — пауза 0.3 с — влево 0.5 с — пауза 1.5 с»). Всё ниже запущено в Python 3.13 с версиями из таблицы теории; вывод вставлен без правок.

### Шаг 1. Проверка спектра на синтетике
Прежде чем верить спектру своего лога, проверь функцию на сигнале с известным ответом: синус 210 Гц плюс шум должен дать пик ровно там. Вторая строка — та же запись с неверной `fs`: пик съезжает вдвое.

```python
import numpy as np
from scipy.signal import welch

fs = 2000.0                                     # 8 kHz loop, blackbox 1/4
t = np.arange(0, 10, 1 / fs)
x = 5 * np.sin(2 * np.pi * 210 * t) + np.random.default_rng(0).normal(0, 1, t.size)
f, p = welch(x, fs=fs, nperseg=int(fs))        # 1 s windows -> 1 Hz resolution
print(f"peak at {f[np.argmax(p)]:.0f} Hz")      # expect 210
f, p = welch(x, fs=fs / 2, nperseg=int(fs))    # wrong fs: 1000 instead of 2000
print(f"wrong fs: peak at {f[np.argmax(p)]:.0f} Hz")
# output:
# peak at 210 Hz
# wrong fs: peak at 105 Hz
```

### Шаг 2. Сгенерировать лог в SITL
Скрипт запускает `arducopter` 4.7.2 (собранный SITL, `build/sitl/bin/arducopter`) с умолчаниями `Tools/autotest/default_params/copter.parm` и своими параметрами, взлетает в GUIDED на 30 м, переходит в ACRO, делает шесть пар ступенек через RC override и садится в LAND. `FS_THR_ENABLE = 0` здесь только потому, что RC приходит из MAVLink override, а не из пульта; для поля такой конфиг не годится — это поймает CI в модуле «CI и версионирование конфигов». Instance 23 (TCP 5990) выбран, чтобы не столкнуться с другим SITL на машине. Запуск: `python3 -I make_log.py <arducopter> <copter.parm> run`, около 1.5 мин.

```python
"""Fly ArduCopter 4.7.2 SITL: GUIDED takeoff 30 m, ACRO roll steps, LAND. Leaves logs/00000001.BIN.
Usage: python3 -I make_log.py <arducopter> <copter.parm> <workdir>
"""
import os, subprocess, sys, time
from pymavlink import mavutil

ardu, parm, work = sys.argv[1:4]
os.makedirs(work, exist_ok=True)
extra = os.path.join(work, "lab.parm")
open(extra, "w").write("""LOG_BITMASK 267741
LOG_DISARMED 0
INS_LOG_BAT_MASK 1
INS_LOG_BAT_OPT 0
SIM_GYR1_RND 20
SIM_VIB_FREQ_X 165
SIM_VIB_FREQ_Y 165
SIM_VIB_FREQ_Z 165
ACRO_TRAINER 0
FS_THR_ENABLE 0
""")
I = 23                                    # instance 23: TCP 5990, away from other SITLs
sitl = subprocess.Popen([ardu, "-S", "--model", "+", "--speedup", "1", "-I", str(I), "-w",
                         "--defaults", f"{parm},{extra}", "--home", "50.45,30.52,100,0"],
                        cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(2)
    m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{5760 + 10 * I}")
    m.wait_heartbeat(timeout=30)

    def rc(roll=1500, thr=1500):
        m.mav.rc_channels_override_send(m.target_system, m.target_component,
                                        roll, 1500, thr, 1500, 0, 0, 0, 0)

    def wait_text(txt, timeout=120):
        t_end = time.time() + timeout
        while time.time() < t_end:
            msg = m.recv_match(type="STATUSTEXT", blocking=True, timeout=1)
            if msg and txt in msg.text:
                return msg.text
        raise TimeoutError(txt)

    m.mav.request_data_stream_send(m.target_system, m.target_component,
                                   mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    wait_text("using GPS", 180)           # "EKF3 IMU0 is using GPS"
    m.set_mode("GUIDED")
    for _ in range(60):                   # pre-arm checks may need a few more seconds
        m.arducopter_arm()
        time.sleep(1)
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if m.motors_armed():
            break
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 30)
    t_end = time.time() + 40
    while time.time() < t_end:
        pos = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if pos and pos.relative_alt > 29000:
            break
    rc()                                  # sticks centred before ACRO
    time.sleep(1)
    m.set_mode("ACRO")
    time.sleep(2)
    for k in range(6):                    # 6 pairs: +step, short pause, -step back to level
        for pwm, dur in ((1700, 0.5), (1500, 0.3), (1300, 0.5), (1500, 1.5)):
            t_end = time.time() + dur
            while time.time() < t_end:
                rc(roll=pwm)
                time.sleep(0.02)
    m.set_mode("LAND")
    m.motors_disarmed_wait()
    print("landed and disarmed")
finally:
    sitl.terminate()
    sitl.wait()
logs = sorted(os.listdir(os.path.join(work, "logs")))
bins = [f for f in logs if f.endswith(".BIN")]
print("log:", bins[-1], os.path.getsize(os.path.join(work, "logs", bins[-1])), "bytes")
# output:
# landed and disarmed
# log: 00000001.BIN 16875520 bytes
```

Первая версия сценария держала крен 55° по 1.5 с между правой и левой ступенькой — аппарат в ACRO с газом «в середине» терял высоту и четыре раза ударился о землю (`SIM Hit ground` в сообщениях `MSG`). Поэтому пауза между ступеньками в паре короткая, а высота взлёта 30 м: сценарий манёвра — часть измерения, и его тоже проверяют по логу.

### Шаг 3. Прочитать лог и посчитать метрики
`uavlog.py` — модуль из функций теории плюс `read_ap`, `rate_stats`, `batch_gyro` и `spectrum`. Запуск: `python3 -I uavlog.py run/logs/00000001.BIN`. Окно анализа ступенек — между входом в ACRO (`MODE.Mode = 1`) и LAND (`Mode = 9`).

```python
"""uavlog.py - read an ArduPilot DataFlash .bin into pandas and compute the module's metrics.
Tested: Python 3.13, pandas 3.1.1, numpy 2.5.5, scipy 1.18.1, pymavlink 2.4.50, ArduCopter 4.7.2 SITL.
Paste step_metrics() and bounce_back() from the theory section into this file unchanged.
"""
import sys
import numpy as np
import pandas as pd
from pymavlink import mavutil
from scipy.signal import welch


def read_ap(path, types):
    """One pass over the log -> {type: DataFrame}, time column t in seconds."""
    rows = {t: [] for t in types}
    log = mavutil.mavlink_connection(path)
    while (msg := log.recv_match(type=types)) is not None:
        rows[msg.get_type()].append(msg.to_dict())
    out = {}
    for t, r in rows.items():
        df = pd.DataFrame(r).drop(columns="mavpackettype", errors="ignore")
        if "TimeUS" in df:
            df["t"] = df["TimeUS"] / 1e6
        out[t] = df
    return out


def rate_stats(t):
    """Logging rate from timestamps, not from settings: median dt, jitter, gaps."""
    dt = np.diff(t) * 1e6
    return {"fs_hz": float(1e6 / np.median(dt)), "dt_mean_us": float(dt.mean()),
            "dt_std_us": float(dt.std()), "dt_p999_us": float(np.percentile(dt, 99.9)),
            "gaps": int((dt > 2 * np.median(dt)).sum())}


def batch_gyro(isbh, isbd, axis="x"):
    """ISBH/ISBD batch sampler -> list of (sample_rate, ndarray rad/s) gyro batches."""
    out = []
    for _, h in isbh[isbh["type"] == 1].iterrows():           # type 1 = gyro, 0 = accel
        d = isbd[isbd["N"] == h["N"]].sort_values("seqno")
        x = np.concatenate([np.asarray(v, float) for v in d[axis]]) / h["mul"]
        if len(x) == h["smp_cnt"]:
            out.append((h["smp_rate"], x))
    return out


def spectrum(x, fs, nperseg):
    f, p = welch(x - x.mean(), fs=fs, nperseg=nperseg, noverlap=nperseg // 2, window="hann")
    return f, 10 * np.log10(p + 1e-12)


# paste def step_metrics(...) and def bounce_back(...) from the theory section here


if __name__ == "__main__":
    d = read_ap(sys.argv[1], ["RATE", "IMU", "ISBH", "ISBD", "MODE", "ATT"])
    print("pandas", pd.__version__, "| numpy", np.__version__, "| rows:",
          {k: len(v) for k, v in d.items()})
    imu = d["IMU"][d["IMU"]["I"] == 0]
    for name, t in (("IMU", imu["t"].to_numpy()), ("RATE", d["RATE"]["t"].to_numpy()),
                    ("ATT", d["ATT"]["t"].to_numpy())):
        print(f"{name:5s}", {k: round(v, 1) for k, v in rate_stats(t).items()})

    acro = d["MODE"].loc[d["MODE"]["Mode"] == 1, "t"].iloc[0]            # 1 = ACRO
    land = d["MODE"].loc[d["MODE"]["Mode"] == 9, "t"].iloc[0]            # 9 = LAND
    r = d["RATE"][(d["RATE"]["t"] > acro) & (d["RATE"]["t"] < land)]
    m = step_metrics(r["t"].to_numpy(), r["RDes"].to_numpy(), r["R"].to_numpy())
    print(m.round(1).to_string(index=False))
    print("median:", m[["overshoot_pct", "rise_ms", "settle_ms", "lag_ms"]].median().round(1).to_dict())
    bb = bounce_back(r["t"].to_numpy(), r["RDes"].to_numpy(), r["R"].to_numpy())
    print("bounce-back %:", bb.round(1), "median", round(float(np.median(bb)), 1))

    att = pd.merge_asof(d["ATT"][["t", "Roll"]], d["RATE"][["t", "RDes", "R"]], on="t",
                        direction="nearest", tolerance=0.005)
    print("merge_asof ATT(10 Hz) + RATE(400 Hz):", len(att), "rows,",
          int(att["R"].isna().sum()), "without a RATE sample within 5 ms")

    batches = batch_gyro(d["ISBH"], d["ISBD"])
    fs_b = batches[0][0]
    x = np.concatenate([b for _, b in batches])
    for nps in (256, 1024):
        f, p = spectrum(x, fs_b, nps)
        k = np.argmax(p[f > 20]) + np.argmax(f > 20)
        print(f"batch gyro X: {len(batches)} batches, fs={fs_b:.0f} Hz, nperseg={nps}: "
              f"df={fs_b / nps:.2f} Hz, peak {f[k]:.1f} Hz, {p[k]:.1f} dB")
    f, p = spectrum(imu["GyrX"].to_numpy(), rate_stats(imu["t"].to_numpy())["fs_hz"], 1024)
    k = np.argmax(p[f > 20]) + np.argmax(f > 20)
    print(f"IMU GyrX at 400 Hz: peak {f[k]:.1f} Hz (165 Hz injected; Nyquist 200 Hz)")
```

```text
pandas 3.1.1 | numpy 2.5.5 | rows: {'RATE': 26994, 'IMU': 53988, 'ISBH': 67, 'ISBD': 2119, 'MODE': 4, 'ATT': 674}
IMU   {'fs_hz': 400.2, 'dt_mean_us': 2500.0, 'dt_std_us': 28.7, 'dt_p999_us': 3332.0, 'gaps': 0}
RATE  {'fs_hz': 400.2, 'dt_mean_us': 2500.0, 'dt_std_us': 28.7, 'dt_p999_us': 3332.0, 'gaps': 0}
ATT   {'fs_hz': 10.0, 'dt_mean_us': 99999.6, 'dt_std_us': 177.3, 'dt_p999_us': 100793.0, 'gaps': 0}
 t_s  step_dps  overshoot_pct  rise_ms  settle_ms  lag_ms
62.1       112            0.0    120.0      202.4    30.0
62.7      -115            0.0    137.4        NaN    35.0
64.9       112            0.0    117.5      203.3    32.5
65.5      -116            0.0    144.9        NaN    35.0
67.7       112            0.0    120.0      207.4    30.0
68.4      -115            0.0    144.9        NaN    35.0
70.5       112            0.0    120.0      204.9    30.0
71.2      -115            0.0    142.4        NaN    35.0
73.4       111            0.0    117.5      202.4    30.0
74.0      -116            0.0    144.9        NaN    35.0
76.2       112            0.0    120.0      207.4    30.0
76.8      -115            0.0    139.9        NaN    35.0
median: {'overshoot_pct': 0.0, 'rise_ms': 128.7, 'settle_ms': 204.1, 'lag_ms': 33.7}
bounce-back %: [2.1 2.2 1.9 2.1 1.8 2.2 1.8 2.2 1.8 2.2 1.9 2.2] median 2.1
merge_asof ATT(10 Hz) + RATE(400 Hz): 674 rows, 0 without a RATE sample within 5 ms
batch gyro X: 33 batches, fs=1000 Hz, nperseg=256: df=3.91 Hz, peak 164.1 Hz, -26.9 dB
batch gyro X: 33 batches, fs=1000 Hz, nperseg=1024: df=0.98 Hz, peak 166.0 Hz, -22.6 dB
IMU GyrX at 400 Hz: peak 166.1 Hz (165 Hz injected; Nyquist 200 Hz)
```

Что здесь проверяется. Частоты сообщений получены из меток времени и совпали с тем, что следует из `LOG_BITMASK`: 400 Гц для `IMU` и `RATE`, 10 Гц для `ATT`. Двенадцать ступенек найдены все, по шесть в каждую сторону; медиана считается по всем двенадцати, `NaN` в медиану не входят. Спектр батч-сэмплера нашёл введённые 165 Гц при обоих `nperseg`, и разница положения пика (164.1 и 166.0 Гц) — в пределах двух бинов. Bounce-back около 2 % — мягкий контроллер SITL без отскока, а не «идеальный тюн»: модель в SITL не повторяет механику твоего аппарата.

### Шаг 4. pandas 3: Copy-on-Write и тип str
Старые рецепты из интернета часто правят таблицу цепочкой индексов. В pandas 3 это ничего не меняет — только предупреждение `ChainedAssignmentError`.

```python
import io
import pandas as pd

csv = "time (us), gyroADC[0], setpoint[0]\n0, 1, 0\n125, 2, 0\n250, 3, 300\n"
df = pd.read_csv(io.StringIO(csv), skipinitialspace=True)
print(pd.__version__, list(df.columns))
df["gyroADC[0]"][df["setpoint[0]"] > 0] = 99           # chained assignment: no effect in pandas 3
print(df["gyroADC[0]"].tolist())
df.loc[df["setpoint[0]"] > 0, "gyroADC[0]"] = 99       # one-step .loc: works
print(df["gyroADC[0]"].tolist())
# output (python3 -W ignore; without it pandas also prints ChainedAssignmentError):
# 3.1.1 ['time (us)', 'gyroADC[0]', 'setpoint[0]']
# [1, 2, 3]
# [1, 2, 99]
```

### Шаг 5. Свой пакет
Сложи функции в `uavlog.py` (`read_bf`, `read_ap`, `rate_stats`, `spectrum`, `step_metrics`, `bounce_back`) с docstring и `requirements.txt`; второй лог прогоняется тремя строками: `read_*`, `spectrum`, `step_metrics`. Если для второго лога что-то пришлось править руками, функция ещё не готова. Для Betaflight `read_bf` — это `pd.read_csv` из теории плюс проверка заголовка `.BFL` на `blackbox_high_resolution` и имени колонки гироскопа с единицами и без.

### Переход на реальное железо
Betaflight: запиши 20–30 с висения и серию резких «стик в упор — отпустить» по крену с полем `gyroUnfilt`, `blackbox_sample_rate = 1/2` или 1/4; пропеллеры снимаются для любой работы на столе, ставятся только перед полётом на поле. Расшифруй `blackbox_decode LOG00001.BFL` (без `--unit-rotation`, чтобы имена колонок совпали с кодом) и проверь `H blackbox_high_resolution` в заголовке. ArduPilot: на время тюнинга `LOG_BITMASK` с битом 0, для фильтров — `INS_LOG_BAT_MASK = 1`; после настройки верни, иначе лог растёт в разы. Прервать сессию: любая вибрация или звук мотора, которых не было до изменения, — посадка и разбор лога до следующего вылета. Критерии на железе: `fs` из меток равна частоте цикла, делённой на делитель записи, с точностью 1 %; между двумя висениями с одной настройкой положение главного пика моторов в спектре различается не больше чем на 2 бина; медианы метрик по 10–20 ступенькам двух полётов с одной настройкой расходятся не больше чем на 10 % — иначе разброс полёта больше эффекта, который ты собрался измерять.

Самопроверка: лабораторная выполнена, когда (SITL-путь) синтетика даёт пик 210 Гц, а с вдвое заниженной `fs` — 105 Гц; `rate_stats` по твоему логу даёт 400 ± 1 Гц для `IMU` и `RATE` и 10 ± 0.1 Гц для `ATT`; `step_metrics` находит 12 ступенек (6 по ~112 °/с и 6 по ~−115 °/с) с медианами overshoot 0 %, нарастание 129 ± 10 мс, установление 204 ± 15 мс, задержка 34 ± 5 мс; bounce-back по всем 12 событиям 1.5–2.5 %; пик батч-спектра лежит в 165 ± 2 Гц при `nperseg` 256 и 1024, а Δf равна 3.91 и 0.98 Гц; цепочка присваивания в pandas 3 оставляет `[1, 2, 3]`, а `.loc` даёт `[1, 2, 99]`. На железе — три критерия из раздела «Переход на реальное железо».

**Эталон для самопроверки.** Верный результат — таблица из 12 строк, как в выводе шага 3, с отличиями в последнем знаке (тайминг RC override на другой машине плавает на 1–2 отсчёта). Типичные неверные: (1) таблица ступенек пустая — ступеньки искали по порогу на d setpoint/dt, а цель в ArduPilot растёт всего на 3–4 °/с за отсчёт; (2) bounce-back 15–20 % через раз — окно залезло на следующую ступеньку пары; (3) все пики спектра сдвинуты в одно и то же число раз — `fs` взята из настроек, а не из меток времени, или не отфильтрован `IMU.I` — `fs_hz` выходит `inf` (медиана dt = 0); (4) пик «вибрации» на неожиданной частоте в 400-герцевом логе — алиасинг составляющей выше 200 Гц, смотри батч-сэмплер.

## diagnostics
- **Симптом:** спектры двух логов нельзя сравнить
  - Возможная причина: разные fs или nperseg, разные режимы полёта.
  - Что сделать: одинаковые параметры, один и тот же режим (висение).
- **Симптом:** step_metrics пустой
  - Возможная причина: в логе нет резких движений стиков; или порог стоит на производной setpoint, а цель ограничена по ускорению (`ATC_ACC_R_MAX` в ArduPilot).
  - Что сделать: искать события по уровню |setpoint|, как в теории; полёт с резкими остановками стика; порог подобрать по гистограмме |setpoint|.
- **Симптом:** пики спектра размазаны
  - Возможная причина: обороты менялись внутри окна.
  - Что сделать: ровный участок, спектрограмма вместо Welch.
- **Симптом:** pymavlink читает очень долго
  - Возможная причина: лог в сотни МБ, чтение в Python по сообщению; или отдельный проход по файлу на каждый тип.
  - Что сделать: один проход с `type=[...]`, `mavlogdump.py --format csv` для разовой выгрузки.
- **Симптом:** скорости в CSV Betaflight в 10 раз больше ожидаемых
  - Возможная причина: в логе `blackbox_high_resolution = ON`, а `blackbox_decode` этого не учитывает.
  - Что видно в логе: строка `H blackbox_high_resolution:1` в заголовке `.BFL`.
  - Что сделать: делить `gyroADC`, `gyroUnfilt`, `rcCommand[0–3]`, `setpoint[0–2]` на 10 (`setpoint[3]` — нет).
- **Симптом:** `KeyError: 'gyroADC[0]'` на CSV, который вчера читался
  - Возможная причина: расшифрован с `--unit-rotation deg/s`, колонка называется `gyroADC[0] (deg/s)`.
  - Что сделать: искать колонку по префиксу (`[c for c in df if c.startswith("gyroADC[0]")]`) или расшифровывать всегда одной командой из скрипта.
- **Симптом:** правка `df[...][...] = …` ничего не меняет, в консоли `ChainedAssignmentError`
  - Возможная причина: pandas 3, Copy-on-Write.
  - Что сделать: одна операция `df.loc[маска, колонка] = значение`.
- **Симптом:** в 400-герцевом `IMU` пик на частоте, которой нет в механике
  - Возможная причина: алиасинг: составляющая f > 200 Гц видна на |f − 400|.
  - Что сделать: батч-сэмплер (`INS_LOG_BAT_MASK = 1`) на частоте датчика.

## references
- Betaflight blackbox-tools (blackbox_decode), Readme и src/blackbox_decode.c | https://github.com/betaflight/blackbox-tools | primary | A
- Betaflight — source code (src/main/blackbox/blackbox.c, 4.5.3 и 2025.12.5) | https://github.com/betaflight/betaflight | primary | A
- pymavlink — DataFlash log reading (mavutil) | https://github.com/ArduPilot/pymavlink | primary | A
- ArduPilot — source code (ArduCopter/Copter.cpp, defines.h; libraries/AP_InertialSensor/BatchSampler.cpp), 4.7.2 | https://github.com/ArduPilot/ardupilot | primary | A
- SciPy — scipy.signal.welch | https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html | primary | A
- pandas — Copy-on-Write и миграция на 3.0 | https://pandas.pydata.org/docs/dev/user_guide/migration.html | primary | A

## checklist
- Лог прочитан в DataFrame, fs определена по меткам времени
- Спектр Уэлча построен с подписанными пиками, Δf записана рядом
- Шум моторов ищется в записи, частота дискретизации которой больше удвоенной частоты пика (батч-сэмплер / gyroUnfilt)
- Overshoot, нарастание, установление, задержка и bounce-back посчитаны функциями, записана медиана
- Окно метрики не залезает на следующий манёвр
- Функции собраны в модуль с requirements.txt и работают на втором логе
- Понимаю, почему Уэлч, а не один FFT
