---
id: bf-motor-balance
title: "Механика до PID: баланс моторов по логу"
level: L2
readingTime: 45 мин
firmware: Betaflight 4.5 (сверено с исходником 4.5.3 и 4.5.5); миксер Quad X и поля лога в 2025.12 те же
status: published
added: 2026-11-25
tags:
  - Betaflight
  - Blackbox
  - моторы
  - механика
  - диагностика
related:
  - bf-blackbox
  - bf-pid
  - bf-filters
  - f-motors-esc
  - f-frame-mech
  - bf-setup-scratch
  - ctl-allocation
  - des-thrust-stand
next:
  - bf-pid
---

## summary
Перед тюнингом PID стоит проверить механику. В ровном полёте разные выходы моторов показывают, что регулятор постоянно компенсирует физический перекос: смещённый центр тяжести (ЦТ), слабый мотор, повреждённый проп, наклонённый мотор или кривой луч. Модуль даёт метод. Выбираешь устойчивый участок лога на 10–20 с, берёшь медиану каждого `motor[0..3]` и переводишь её в проценты хода по заголовку `motorOutput`. Из медиан считаются три индекса перекоса: зад–перёд, лево–право и диагональ (рыскание). По их сочетанию находишь причину, а swap-тест подтверждает её. Лабораторная — скрипт на Python. Он сам находит устойчивый участок в CSV от `blackbox_decode`. Проверяешь скрипт на синтетических логах с заранее внесёнными дефектами: ЦТ сзади на 4 % и мотор 4 на +6 %. Потом то же самое делаешь на своём аппарате, со стендовой и полевой процедурой.

## theory
### Почему механика идёт до PID
В ровном висении угловые скорости по всем осям около нуля, и P- и D-члены почти ничего не делают. Постоянный паразитный момент держит I-член: он накапливает поправку, пока ошибка не обнулится, и потом её хранит. Поэтому механический перекос в логе выглядит одинаково: ненулевая медиана `axisI[0..2]` и постоянная разница между `motor[0..3]` при стиках в центре. Рост I по yaw здесь бесполезен: I быстрее наберёт ту же поправку, но сама поправка останется.

Платишь за это запасом управления (headroom):

- Поправку миксер добавляет к газу: `motor = motorOutputMin + motorOutputRange · (газ + Σ pidSum/1000 · коэффициент миксера)` (`flight/mixer.c`, `applyMixToMotors`, `PID_MIXER_SCALING` = 1000). Мотор, которому в висении уже нужно на 8 % больше, первым упрётся в 100 % на панче. Если разброс поправок `motorMixRange` больше 1, миксер `LEGACY` сжимает поправки по всем осям вместе (`applyMixerAdjustment`), и все оси одновременно теряют часть авторитета.
- `iterm_windup` = 85: когда `motorMixRange` превышает 0.85, I-член начинает накапливаться медленнее, а при 1.0 перестаёт совсем (`flight/pid.c`, `dynCi`). Часть этого окна уже потрачена на механический перекос.
- По рысканию запас меньше всего. Момент по yaw создаётся только реакцией пропов: плечо реактивного момента K_M = Q/T — 1–2 см против 15–25 см плеча по крену и тангажу (оценка ниже). Вдобавок `pidsum_limit_yaw` = 400 против 500 у крена и тангажа. Постоянный перекос по диагонали съедает именно этот запас, поэтому на резком развороте при полном газе курс «уплывает».

Мотор, которому всё время нужна команда выше, чем остальным, греется сильнее — частый ответ на вопрос «почему один мотор горячее». Слабый мотор или проп даёт и вибрации, которые фильтры не уберут (`bf-filters`). Отсюда порядок: механика и баланс, потом фильтры, потом PID.

### Quad X: номера, поля лога, вращение
В Betaflight 4.5 моторы Quad X пронумерованы так: **1 — задний правый (RR), 2 — передний правый (FR), 3 — задний левый (RL), 4 — передний левый (FL)**. В логе индексы начинаются с нуля: `motor[0]` = мотор 1, …, `motor[3]` = мотор 4. Таблица `mixerQuadX[]` (`flight/mixer_init.c`, столбцы throttle, roll, pitch, yaw) задаёт знаки так:

| Мотор | Поле лога | roll | pitch | yaw | Вращение, props-in |
|---|---|---|---|---|---|
| 1 RR | `motor[0]` | −1 | +1 | −1 | CW |
| 2 FR | `motor[1]` | −1 | −1 | +1 | CCW |
| 3 RL | `motor[2]` | +1 | +1 | +1 | CCW |
| 4 FL | `motor[3]` | +1 | −1 | −1 | CW |

Вращение по умолчанию — props-in: передние пропы у камеры крутятся внутрь. Страница Betaflight «Running with Reversed Motors» описывает обратное: у props-out передний левый крутится против часовой, передний правый по часовой. Для props-out ставят `yaw_motors_reversed = ON`. Параметр не меняет ни таблицу, ни номера, только инвертирует знак yaw-PID перед миксером (`if (!mixerConfig()->yaw_motors_reversed) scaledAxisPidYaw = -scaledAxisPidYaw;`). Сами моторы при этом не разворачиваются: направление меняется в конфигураторе ESC или перекидкой фаз. Пары для рыскания: моторы 1 и 4 крутятся в одну сторону, моторы 2 и 3 — в другую.

Ещё одна деталь: `motor_output_reordering` переставляет только физические выходы (в драйверах моторов: `dshot_bitbang.c`, `dshot_dpwm.c`, `pwm_output.c`), а лог пишет индексы миксера. Поэтому `motor[0]` всегда задний правый, на какую бы площадку ни был припаян этот мотор. Если порядок или направление перепутаны, баланс считать бессмысленно: сначала пройди вкладку Motors (`bf-setup-scratch`).

{{diagram:bf-quadx-motor-map|Номер мотора и поле лога различаются на единицу, у диагоналей 1+4 и 2+3 противоположное вращение. Три сравнения пар разделяют причины: ЦТ даёт только pitch и roll, наклон мотора — только yaw, один слабый мотор — все три индекса одной величины.}}

### Что лежит в `motor[0..3]` и как перевести в проценты
В лог пишется команда мотора после миксера и ограничений (`blackbox.c`: `blackboxCurrent->motor[i] = lrintf(motor[i])`). У DShot это значение протокола, а не проценты. Границы диапазона пишутся в заголовок лога строкой `motorOutput:low,high`, где берутся `getMotorOutputLow()` и `getMotorOutputHigh()`. Для DShot без 3D (`drivers/dshot.c`):

- low = 48 + `dshot_idle_value`/10000 · 1999. При умолчании 550 это 48 + 0.055 · 1999 = 157.9, в заголовке **158**;
- high = 2047 − 1999 · (1 − `motor_output_limit`/100). При 100 % это **2047**, при 80 % — 1647;
- при включённом dynamic idle (`dyn_idle_min_rpm` > 0, нужен bidirectional DShot) нижняя граница сбрасывается в 48 (`mixerInitProfile`), и в заголовке будет `48,2047`.

Процент хода: **p = (motor − low) / (high − low) · 100**. Значение 876 при `158,2047` даёт 38.01 %. Если по ошибке взять `48,2047`, выйдет 41.42 %. Для индексов перекоса это почти неважно, потому что они относительные. Для запаса до 100 % и для сравнения логов с разными настройками это важно. Строку диапазона проще всего достать из самого файла лога: `grep -a motorOutput LOG00001.BFL` (заголовок там текстовый) или на вкладке заголовка в Blackbox Explorer.

`blackbox_decode` пишет CSV с заголовком из имён полей лога: `motor[0]`…`motor[3]`, `rcCommand[3]` (газ, 1000–2000), `gyroADC[0..2]`, `axisI[0..2]`, `eRPM[0..3]` (eRPM/100, только с DShot-телеметрией). Единица добавляется в скобках, например `time (us)`. Гироскоп по умолчанию выводится в сырых единицах (`--unit-rotation raw`). В Betaflight 4.x сырые единицы — это °/с, в заголовке `gyro_scale` = 1.0, а при `blackbox_high_resolution = ON` значения умножаются на 10.

### Метод: участок, медианы, три индекса
1. **Участок.** Висение или ровный прямой пролёт на 10–20 с без переходов газа. Скрипт ниже режет лог на блоки по 0.5 с и берёт самый длинный ряд блоков, в которых размах газа `rcCommand[3]` за блок ≤ 20 единиц (≈ 40 /с), RMS гироскопа ≤ 20 °/с и газ выше 1150 (аппарат в воздухе). Ряд обрезается до 20 с по центру. Это ориентиры курса, не значения прошивки.
2. **Медианы.** Медиана каждого `motor[i]` на участке, переведённая в проценты: p₁…p₄, среднее p̄. Медиана, а не среднее: порыв ветра сдвигает среднее, а медиану почти не трогает.
3. **Индексы** в процентах от среднего, это разности средних по парам:
   - I_pitch = [(p₁ + p₃) − (p₂ + p₄)] / 2 / p̄ · 100 — задние минус передние;
   - I_roll = [(p₃ + p₄) − (p₁ + p₂)] / 2 / p̄ · 100 — левые минус правые;
   - I_yaw = [(p₁ + p₄) − (p₂ + p₃)] / 2 / p̄ · 100 — диагональ 1+4 минус 2+3.

Положительный I_yaw значит, что пара 1+4 работает сильнее. При props-in её пропы крутятся по часовой (вид сверху), их реакция поворачивает раму против часовой. Если узор чисто yaw (I_pitch ≈ I_roll ≈ 0), регулятор гасит паразитный момент, который тянет нос вправо; при props-out всё наоборот. Если все три индекса одной величины, это слабый мотор этой пары, и паразитного момента нет: тяги равны, значит, равны и реакции. Есть быстрая сверка с регулятором: при выключенной линеаризации (`thrust_linear` = 0), `motorMixRange` < 1 и включённом airmode (или газе ≥ 50 %) постоянный yaw-pidSum S даёт каждому мотору ±S/10 % хода. Без airmode на газе g < 0.5 миксер `LEGACY` умножает поправку на 0.5 + g (`applyMixerAdjustment`): на висении 30 % это ×0.8. Значит, с airmode медиана `axisI[2]` = 20 (P, D и F в висении около нуля) соответствует разнице диагоналей 4 процентных пункта; при p̄ = 38 % это I_yaw ≈ 10.5 %.

**Ориентир курса** (не значение прошивки): |I| ≤ 2 % — норма для собранного аппарата, 2–5 % — смотри, повторяется ли от полёта к полёту, больше 5 % стабильно в нескольких логах — ищи механическую причину до любого тюнинга.

### Сигнатуры причин
Четыре медианы связаны четырьмя величинами: общим газом и тремя индексами. Каждая причина оставляет свой узор.

- **Смещённый ЦТ** даёт I_pitch и/или I_roll при I_yaw ≈ 0. Моменты сил тяги вокруг ЦТ уравновешены, когда T_перед · (L/2 + x) = T_зад · (L/2 − x). Отсюда смещение ЦТ назад x = I_T · L/4, где L — расстояние между передней и задней осями моторов, а I_T — индекс по тяге. Тяга растёт как квадрат оборотов (`f-aero-props`), но обороты растут медленнее команды: по таблице T-Motor 15×5 из `des-thrust-stand` тяга ∝ команде^k с k ≈ 1.1–1.8 (2 — верхняя граница, если считать обороты пропорциональными команде). Поэтому I_T ≈ k · I_pitch и **x ≈ k · I_pitch · L/4**. При L = 300 мм и I_pitch = 4 % получается x ≈ 3–5 мм (6 мм при k = 2). Это оценка порядка величины, точный k своего мотора с пропом даёт стенд.
- **Один слабый мотор** (мотору k нужно на w больше команды при той же тяге) даёт три индекса одной величины ≈ w/2. Знаки показывают угол: для мотора 4 (FL) это перёд, лево и диагональ 1+4. Если причина только в ЦТ, в линейной модели p₁ + p₄ = p₂ + p₃. Значит, мотор k «должен» иметь p_k = (сумма соседей) − (противоположный мотор), и w = p_k / [(сумма соседей) − противоположный] − 1. Четыре медианы точно описывают четыре решения, по одному на мотор: «слабый» мотор на нагруженной диагонали (два угла, w > 0) или «сильный» на другой (два угла, w < 0 — например, проп с большим шагом). Скрипт выводит все четыре, а слабыми считает только w > 1 % (ориентир курса). Слабый мотор не отличить от мотора в противоположном углу той же диагонали: различает их только swap-тест.
- **Наклонённый мотор или кривой луч** даёт I_yaw при I_pitch ≈ I_roll ≈ 0. Мотор, наклонённый по касательной на угол δ, создаёт момент рыскания T · r · sin δ. Его гасит разница реакций пар: 2 · K_M · T · I_T, где K_M = Q/T — отношение реактивного момента пропа к тяге. Отсюда I_T = r · sin δ / (2K_M), а по команде в k раз меньше (k ≈ 1.1–1.8, не больше 2). По таблице T-Motor 15×5 из `des-thrust-stand` K_M = 0.15 Н·м / (0.805 · 9.81 Н) ≈ 0.019 м. Для 10" пропа с тем же отношением шага к диаметру K_M ≈ 0.013 м (масштаб по диаметру, оценка; у 10×5 шаг относительно больше, K_M выше, и индекс ниже). При r = 0.21 м наклон в 1° даёт I_T ≈ 14.5 %, то есть ≈ 7–13 % по команде, 0.5° — ≈ 4–7 %.
- **Разные пропы** (партии, шаг, ремонт) дают разную тягу и разный момент на тех же оборотах. В зависимости от того, куда попал «чужой» проп, выйдет узор одного мотора или чистый yaw.

{{diagram:bf-motor-balance-tree|Решение принимается по узору трёх индексов, а не по одному мотору: только pitch/roll — ЦТ, только yaw — наклон или пропы, три индекса одной величины — один угол, а мотор это или проп, решает swap-тест.}}

### Таблица диагностики

| Причина | Узор индексов | Что ещё в логе | Проверка |
|---|---|---|---|
| ЦТ смещён | I_pitch и/или I_roll, I_yaw ≈ 0 | `axisI[0]`/`axisI[1]` постоянны | сдвинь АКБ на 5–10 мм, повтори полёт: индекс меняется пропорционально |
| Слабый мотор (подшипник, обмотка) | три индекса ≈ w/2, знаки на угол | `eRPM` того мотора как у остальных при большей команде | swap моторов местами: перекос уходит вместе с мотором |
| Повреждённый или неравный проп | узор угла или yaw | `eRPM` того мотора выше при большей команде, проп даёт меньше тяги на оборот; растёт пик 1× RPM в спектре | swap пропов: перекос уходит с пропом |
| Наклон мотора, кривой луч | только I_yaw | постоянный `axisI[2]` | уровень или линейка по оси вала, осмотр луча; swap не переносит перекос |
| Разный тайминг или настройки ESC | узор одного угла | в полёте как у слабого мотора; на столе без пропов при одной команде `eRPM` ниже | сверить настройки всех ESC в конфигураторе ESC, одна прошивка и одни значения |
| Порядок или направление моторов | аппарат не взлетает или крутится | runaway, флаг `RUNAWAY` | вкладка Motors без пропов (`bf-setup-scratch`) |

Swap-тест не двигает массу, поэтому ЦТ после него не меняется. Верная гипотеза — та, у которой оценка ЦТ после перестановки осталась прежней, а «слабый» угол переехал вместе с переставленной деталью.

### Кейс: 10" с перекосом по рысканию
10-дюймовый квадрокоптер. На ровном полёте перекос по рысканию держался на 6–8 % от полёта к полёту. Усиление PID по yaw ничего не меняло. Так и должно быть: постоянный момент держит I-член, и разница диагоналей остаётся при любом PID. Медианы участков ровного полёта показали два вклада сразу: индекс тангажа (смещённый ЦТ) и диагональ с узором одного угла (слабый мотор). Если весь диагональный перекос даёт один мотор, ему по формуле нужно примерно вдвое больше индекса: w ≈ 2 · I_yaw, то есть 12–16 % лишней команды. Это уже неисправность, а не разброс партии. По оценке выше тот же порядок (7–13 %) дал бы и наклон мотора на 1° на 10" раме, поэтому одного yaw-индекса мало, решает весь узор. Исправили обе причины: переставили батарею и заменили мотор. После этого сняли новый лог по той же программе полёта. Именно повторный лог, а не ощущения, закрывает вопрос. Медианы реального лога здесь не приводятся: лабораторная ниже воспроизводит ту же структуру (ЦТ плюс слабый мотор) на синтетике с известными вкладами, чтобы метод можно было проверить числом.

### Порядок работ до тюнинга
1. Порядок и направление моторов, `yaw_motors_reversed` по факту пропов (вкладка Motors, без пропов).
2. Механика на столе: люфт моторов, свободное вращение, валы, луч и крепление мотора, одинаковые пропы одной партии, балансировка пропов (`f-frame-mech`).
3. ЦТ на геометрическом центре: подвесь аппарат за точки на осях моторов или поставь на два пальца под линиями 1–3 и 2–4.
4. Лог висения и ровного полёта 10–20 с, медианы, три индекса. Пока индексы больше 5 %, исправляй механику.
5. Только потом фильтры (`bf-filters`, `bf-rpm-filter`) и PID (`bf-pid`).

{{lesson:bf-pid|Когда индексы в норме, следующий шаг — тюнинг по метрикам: один параметр за полёт, медианы по манёврам.}}

### Справочная таблица (Betaflight 4.5)

| Параметр / поле | Умолчание | Диапазон | Роль в балансе |
|---|---|---|---|
| `yaw_motors_reversed` | OFF | OFF, ON | ON для props-out: знак yaw-PID инвертирован, номера те же |
| `motor_output_reordering` | 0,1,2,3… | индексы выходов | переставляет только физические выходы, лог остаётся по миксеру |
| `dshot_idle_value` (в 2025.12 `motor_idle`) | 550 | 0–2000 | нижняя граница `motorOutput`: 158 при 550 |
| `motor_output_limit` | 100 | 1–100 % | верхняя граница: 2047 при 100, 1647 при 80 |
| `dyn_idle_min_rpm` | 0 | 0–200 (×100 об/мин) | > 0 → нижняя граница в заголовке 48 |
| `thrust_linear` | 0 | 0–150 | ≠ 0 искажает связь pidSum ↔ команда |
| `mixer_type` | LEGACY | LEGACY, LINEAR, DYNAMIC, EZLANDING | как миксер сжимает поправки при насыщении |
| `iterm_windup` | 85 | 30–100 % | порог `motorMixRange`, выше которого I растёт медленнее (в 2025.12 другой смысл: 80, 20–100 % — потолок I в % от `pidsum_limit`) |
| `iterm_limit` (в 2025.12 удалён) | 400 | 0–500 | потолок I-члена |
| `pidsum_limit` / `pidsum_limit_yaw` | 500 / 400 | 100–1000 | потолок суммы P+I+D+F, у yaw ниже |
| `blackbox_disable_motors` | OFF | OFF, ON | никогда не включать: без `motor[]` баланса нет |
| `blackbox_high_resolution` | OFF | OFF, ON | ON → gyro, rcCommand, setpoint ×10 в логе |
| заголовок `motorOutput` | 158,2047 | — | low, high для перевода в проценты |

В 2025.12 `mixerQuadX[]`, знак `yaw_motors_reversed`, поля `motor[]` и строка `motorOutput` не изменились. Переименован `dshot_idle_value` → `motor_idle` (умолчание то же, 550), удалён `iterm_limit`, а `iterm_windup` стал потолком I-члена: 80 % от `pidsum_limit` (`flight/pid_init.c`), то есть 400 по крену и тангажу и 320 по рысканию.

### Место в системе
- **Получает:** лог с `motor[0..3]`, `axisI`, `rcCommand`, gyro и `eRPM` (`bf-blackbox`); правильные порядок и направление моторов (`bf-setup-scratch`); квадратичную связь тяги с оборотами и отношение момента к тяге (`f-aero-props`, `des-thrust-stand`).
- **Отдаёт:** механически выверенный аппарат с запасом управления — фильтрам (`bf-filters`) и тюнингу (`bf-pid`); вывод «мотор, проп или ESC» — обслуживанию моторов и ESC (`f-motors-esc`).
- **Если ошибиться здесь:** перекос оставлен, и PID держит его I-членом. На панче один мотор упирается в 100 %, курс уплывает на развороте, этот мотор греется. Пилот «лечит» это ростом I или D (`bf-pid`) и получает горячие моторы и шум, который принимает за проблему фильтров (`bf-filters`).

## practice
Основной путь не требует железа. Скрипт читает CSV от `blackbox_decode`, сам находит устойчивый участок, считает медианы, индексы и гипотезы «ЦТ + один мотор». Своего лога нет, поэтому скрипт генерирует три синтетических лога с известными дефектами и проверяет, что метод их находит. Нужен только Python 3, `numpy` по желанию: без него медианы считает `statistics` с тем же результатом.

### Шаг 1. Диапазон и проценты
Прежде чем считать, переведи значения в проценты хода. По умолчанию заголовок `motorOutput:158,2047`, тогда 876 → (876 − 158)/1889 · 100 = 38.01 %. С dynamic idle заголовок `48,2047`, и то же 876 даёт 41.42 %. Посчитай сам для `motor_output_limit = 80`: верхняя граница 1647, значение 876 даёт (876 − 158)/(1647 − 158) · 100 = 48.22 %. Запиши себе: диапазон берётся из заголовка конкретного лога, а не из памяти.

### Шаг 2. Скрипт
Сохрани как `motor_balance.py`. Функция `make_log` пишет CSV в формате `blackbox_decode`. Взлёт 0–3 с, висение 3–19 с, манёвры 19–22 с (газ ±400, gyro до 150 °/с), ровный полёт 22–34 с, посадка. На каждом выходе шум 2.5 % и медленная «поправка PID» ±1.5 % с частотой 1.3 Гц.

```python
#!/usr/bin/env python3
"""Motor balance from a blackbox_decode CSV (Betaflight 4.5, Quad X, motors 1 RR, 2 FR, 3 RL, 4 FL).

  python3 motor_balance.py LOG00001.01.csv --motor-range 158,2047   # own log; range = header "motorOutput"
  python3 motor_balance.py LOG00001.01.csv --hires                  # log header blackbox_high_resolution:1
  python3 motor_balance.py --demo                                   # synthetic logs A, B, C with known faults
Standard library only; numpy is used for the medians if it is installed.
"""
import argparse, csv, math, os, random, re, statistics, sys, tempfile

try:
    import numpy as np
    median = lambda xs: float(np.median(xs))
except ImportError:
    median = statistics.median

#        motor[0] 1 RR, motor[1] 2 FR, motor[2] 3 RL, motor[3] 4 FL
SIGN = {"pitch": (+1, -1, +1, -1),   # rear pair (1,3) minus front pair (2,4)
        "roll":  (-1, -1, +1, +1),   # left pair (3,4) minus right pair (1,2)
        "yaw":   (+1, -1, -1, +1)}   # diagonal 1+4 minus diagonal 2+3
NAME = ("1 RR", "2 FR", "3 RL", "4 FL")
NEIGH = {0: (1, 2, 3), 1: (0, 3, 2), 2: (0, 3, 1), 3: (1, 2, 0)}   # motor: (neighbour, neighbour, opposite)


def read_csv(path):
    with open(path, newline="") as f:
        rd = csv.reader(f)
        head = [re.sub(r"\s*\(.*\)$", "", h.strip()) for h in next(rd)]   # 'time (us)' -> 'time'
        need = ["time", "rcCommand[3]"] + [f"gyroADC[{a}]" for a in range(3)] + [f"motor[{i}]" for i in range(4)]
        miss = [n for n in need if n not in head]
        if miss:
            sys.exit(f"{path}: no columns {miss} (blackbox_decode CSV of a quad expected)")
        pos = {n: head.index(n) for n in need}
        cols = {n: [] for n in need}
        for row in rd:
            if len(row) >= len(head):
                for n in need:
                    cols[n].append(float(row[pos[n]]))
    return cols


def steady_segment(c, block_s=0.5, thr_span_max=20.0, gyro_rms_max=20.0, thr_min=1150, min_s=10, max_s=20, scale=1.0):
    """Longest run of 0.5 s blocks with throttle span <= 20 and gyro RMS <= 20 deg/s, trimmed to 20 s.
    All thresholds are course guidelines; scale = 10 for blackbox_high_resolution (rcCommand and gyro x10)."""
    t = c["time"]
    fs = (len(t) - 1) / ((t[-1] - t[0]) / 1e6)
    blk = max(1, int(round(fs * block_s)))
    good = []
    for b in range(len(t) // blk):
        sl = slice(b * blk, (b + 1) * blk)
        thr = c["rcCommand[3]"][sl]
        rms = math.sqrt(sum(v * v for a in range(3) for v in c[f"gyroADC[{a}]"][sl]) / (3 * blk))
        good.append(max(thr) - min(thr) <= thr_span_max * scale and rms <= gyro_rms_max * scale
                    and min(thr) >= thr_min * scale)
    best, start = (0, 0), None
    for i, ok in enumerate(good + [False]):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            best = max(best, (start, i), key=lambda r: r[1] - r[0])
            start = None
    n = best[1] - best[0]
    if n * block_s < min_s:
        return None
    keep = min(n, int(max_s / block_s))
    i0 = (best[0] + (n - keep) // 2) * blk
    return i0, i0 + keep * blk, fs


def analyse(path, lo, hi, props_out=False, scale=1.0):
    c = read_csv(path)
    seg = steady_segment(c, scale=scale)
    if seg is None:
        print(f"{os.path.basename(path)}: no steady segment >= 10 s - fly 10-20 s of level hover/cruise")
        return None
    i0, i1, fs = seg
    t0 = (c["time"][i0] - c["time"][0]) / 1e6
    pct = [median([(v - lo) / (hi - lo) * 100 for v in c[f"motor[{i}]"][i0:i1]]) for i in range(4)]
    mean = sum(pct) / 4
    ind = {k: sum(s * p for s, p in zip(sg, pct)) / 2 / mean * 100 for k, sg in SIGN.items()}
    print(f"{os.path.basename(path)}: steady {t0:.1f}-{t0 + (i1 - i0) / fs:.1f} s ({(i1 - i0) / fs:.0f} s, {fs:.0f} Hz)")
    print("  medians, % of motorOutput range: " + "  ".join(f"{NAME[i]} {pct[i]:.2f}" for i in range(4)) + f"  mean {mean:.2f}")
    for k, txt in (("pitch", "rear-front"), ("roll", "left-right"), ("yaw", "diag 1+4 - 2+3")):
        v = ind[k]
        verdict = "ok" if abs(v) <= 2 else ("watch" if abs(v) <= 5 else "find the hardware cause")   # course guideline
        print(f"  {k:5s} {txt:15s} {v:+6.2f} %  {verdict}")
    if abs(ind["yaw"]) > 2:
        pair = "1+4" if ind["yaw"] > 0 else "2+3"
        cw = (ind["yaw"] > 0) != props_out          # props-in: motors 1 and 4 spin CW
        print(f"  pair {pair} works harder: if the pattern is pure yaw, a parasitic torque turns the nose "
              f"{'right (CW)' if cw else 'left (CCW)'} seen from above; if all three indices match, one motor of it is weak")
    cands = []
    for k, (a, b, o) in NEIGH.items():
        base = pct[a] + pct[b] - pct[o]           # what motor k would need if only the CG were off
        w = (pct[k] / base - 1) * 100
        fixed = pct[:k] + [base] + pct[k + 1:]
        cg = {ax: sum(s * p for s, p in zip(SIGN[ax], fixed)) / 2 / (sum(fixed) / 4) * 100 for ax in ("pitch", "roll")}
        kind = "weak" if w > 1.0 else ("strong" if w < -1.0 else "")     # 1 %: course guideline
        if kind:
            print(f"  exact fit: motor {NAME[k]} {kind:6s} {w:+.1f} % + CG offset pitch {cg['pitch']:+.1f} % roll {cg['roll']:+.1f} %")
        if kind == "weak":
            cands.append((k, w, cg))
    if not cands:
        print("  hypothesis: no single weak motor; pitch/roll = CG offset, yaw = tilted motors / props")
    return {"pct": pct, "ind": ind, "cands": cands}


def make_log(path, cg_rear=0.0, cg_left=0.0, weak=None, seed=1, fs=1000, dur=40.0, lo=158, hi=2047, hover=38.0):
    """Synthetic blackbox_decode CSV: take-off, 16 s hover, manoeuvres, 12 s cruise, landing.
    cg_rear / cg_left: rear-front / left-right imbalance in % of the mean; weak = (motor index, extra %)."""
    rnd = random.Random(seed)
    base = []
    for i in range(4):
        m = 1 + SIGN["pitch"][i] * cg_rear / 200 + SIGN["roll"][i] * cg_left / 200
        if weak and weak[0] == i:
            m *= 1 + weak[1] / 100
        base.append(m)
    head = ["loopIteration", "time (us)", "rcCommand[3]"] + [f"gyroADC[{a}]" for a in range(3)] + [f"motor[{i}]" for i in range(4)]
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(head)
        for n in range(int(dur * fs)):
            t = n / fs
            if t < 3:   thr, k, g = 1000 + 150 * t, t / 3, 40.0                # take-off ramp
            elif t < 19: thr, k, g = 1450, 1.0, 6.0                              # hover
            elif t < 22: thr, k, g = 1450 + 400 * math.sin(2 * math.pi * t), 1 + 0.6 * math.sin(2 * math.pi * t), 150.0
            elif t < 34: thr, k, g = 1470, 1.03, 8.0                             # level cruise
            else:        thr, k, g = 1470 - 70 * (t - 34), 1 - (t - 34) / 7, 30.0   # landing
            wob = 1.5 * math.sin(2 * math.pi * 1.3 * t)                         # PID corrections around trim
            row = [n, int(t * 1e6), int(thr)] + [round(rnd.gauss(0, g)) for _ in range(3)]
            for i in range(4):
                p = hover * k * base[i] + SIGN["roll"][i] * wob + rnd.gauss(0, 2.5)
                row.append(int(round(lo + max(0.0, min(100.0, p)) / 100 * (hi - lo))))
            wr.writerow(row)


def demo():
    d = tempfile.mkdtemp(prefix="bfmb_")
    logs = [("A", "CG rear 4 %, motor 4 FL +6 %", dict(cg_rear=4.0, weak=(3, 6.0), seed=1)),
            ("B", "swap test: motors 1 and 4 swapped, CG unchanged", dict(cg_rear=4.0, weak=(0, 6.0), seed=2)),
            ("C", "battery moved forward, weak motor replaced", dict(seed=3))]
    res = {}
    for name, what, kw in logs:
        p = os.path.join(d, f"LOG_{name}.csv")
        make_log(p, **kw)
        print(f"== {name}: injected {what}")
        res[name] = analyse(p, 158, 2047)
    print("== A vs B: the swap moved no mass, so the true hypothesis keeps its CG and its motor moves 4 <-> 1")
    swap = {0: 3, 3: 0, 1: 1, 2: 2}
    for k, wa, cga in res["A"]["cands"]:
        hb = next((h for h in res["B"]["cands"] if h[0] == swap[k]), None)
        if hb is None:
            print(f"  motor {NAME[k]}: no matching hypothesis in B -> rejected")
            continue
        dcg = max(abs(cga[ax] - hb[2][ax]) for ax in ("pitch", "roll"))
        print(f"  motor {NAME[k]} (A) -> {NAME[hb[0]]} (B): CG change {dcg:.1f} % -> {'confirmed' if dcg < 1.0 else 'rejected'}")  # 1 %: course guideline


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="*")
    ap.add_argument("--motor-range", default="158,2047", help="header line motorOutput: low,high")
    ap.add_argument("--props-out", action="store_true", help="yaw_motors_reversed = ON")
    ap.add_argument("--hires", action="store_true", help="blackbox_high_resolution = ON: rcCommand, gyro x10")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo or not a.csv:
        demo()
    lo, hi = (float(x) for x in a.motor_range.split(","))
    for p in a.csv:
        analyse(p, lo, hi, a.props_out, 10.0 if a.hires else 1.0)
```

### Шаг 3. Прогон на синтетике
`python3 motor_balance.py --demo`. Генератор детерминирован (`random.Random(seed)`), вывод должен совпасть до сотых:

```text
== A: injected CG rear 4 %, motor 4 FL +6 %
LOG_A.csv: steady 3.0-19.0 s (16 s, 1000 Hz)
  medians, % of motorOutput range: 1 RR 38.75  2 FR 37.22  3 RL 38.80  4 FL 39.54  mean 38.58
  pitch rear-front       +1.03 %  ok
  roll  left-right       +3.09 %  watch
  yaw   diag 1+4 - 2+3   +2.95 %  watch
  pair 1+4 works harder: if the pattern is pure yaw, a parasitic torque turns the nose right (CW) seen from above; if all three indices match, one motor of it is weak
  exact fit: motor 1 RR weak   +6.2 % + CG offset pitch -1.9 % roll +6.1 %
  exact fit: motor 2 FR strong -5.8 % + CG offset pitch -1.9 % roll +0.1 %
  exact fit: motor 3 RL strong -5.5 % + CG offset pitch +3.9 % roll +5.9 %
  exact fit: motor 4 FL weak   +6.1 % + CG offset pitch +4.0 % roll +0.1 %
== B: injected swap test: motors 1 and 4 swapped, CG unchanged
LOG_B.csv: steady 3.0-19.0 s (16 s, 1000 Hz)
  medians, % of motorOutput range: 1 RR 41.08  2 FR 37.27  3 RL 38.75  4 FL 37.22  mean 38.58
  pitch rear-front       +6.93 %  find the hardware cause
  roll  left-right       -3.09 %  watch
  yaw   diag 1+4 - 2+3   +2.95 %  watch
  pair 1+4 works harder: if the pattern is pure yaw, a parasitic torque turns the nose right (CW) seen from above; if all three indices match, one motor of it is weak
  exact fit: motor 1 RR weak   +5.9 % + CG offset pitch +4.0 % roll -0.1 %
  exact fit: motor 2 FR strong -5.8 % + CG offset pitch +3.9 % roll -5.9 %
  exact fit: motor 3 RL strong -5.5 % + CG offset pitch +9.7 % roll -0.1 %
  exact fit: motor 4 FL weak   +6.5 % + CG offset pitch +10.0 % roll -6.1 %
== C: injected battery moved forward, weak motor replaced
LOG_C.csv: steady 3.0-19.0 s (16 s, 1000 Hz)
  medians, % of motorOutput range: 1 RR 38.01  2 FR 38.06  3 RL 38.01  4 FL 38.01  mean 38.02
  pitch rear-front       -0.07 %  ok
  roll  left-right       -0.07 %  ok
  yaw   diag 1+4 - 2+3   -0.07 %  ok
  hypothesis: no single weak motor; pitch/roll = CG offset, yaw = tilted motors / props
== A vs B: the swap moved no mass, so the true hypothesis keeps its CG and its motor moves 4 <-> 1
  motor 1 RR (A) -> 4 FL (B): CG change 12.3 % -> rejected
  motor 4 FL (A) -> 1 RR (B): CG change 0.3 % -> confirmed
```

Разбор. **Лог A** показывает главную ловушку: I_pitch = +1.03 %, «норма», хотя ЦТ внесён на 4 %. Слабый передний мотор 4 поднял перёд и замаскировал тяжёлый зад. Зато roll +3.09 % появился, хотя бокового смещения ЦТ нет. Индексы не равны причинам, это только узор. Решатель выдаёт четыре точных решения. Два «сильных» (моторы 2 и 3, w ≈ −5.5…−5.8 %) правдоподобны, только если на диагонали 2+3 стоят пропы другой партии или шага. Остаются два «слабых», и они одинаково точно описывают медианы: «мотор 4 +6.1 %, ЦТ назад 4.0 %» и «мотор 1 +6.2 %, ЦТ влево 6.1 % и вперёд 1.9 %». По одному логу выбрать нельзя. Обрати внимание, что w у обеих одинаковый (около 6 %): он зависит только от диагонального перекоса, а ЦТ на диагональ не влияет. **Лог B** — swap-тест: моторы 1 и 4 переставлены, масса не двигалась. Гипотеза «мотор 4» превращается в «мотор 1» с тем же ЦТ (+4.0 %), изменение 0.3 %, гипотеза подтверждена. Альтернатива дала бы прыжок ЦТ на 12.3 % без переноса массы, это невозможно, гипотеза отвергнута. **Лог C** — после переноса батареи и замены мотора все индексы −0.07 %. Это и есть проверка ремонта.

### Шаг 4. Свой лог
Расшифруй лог: `blackbox_decode LOG00001.BFL`. Без `--index` расшифруются все логи файла в `LOG00001.01.csv`, `.02.csv`…, с `--index N` — только N-й. Проверь `grep -a blackbox_high_resolution LOG00001.BFL`: при значении 1 газ и гироскоп в логе умножены на 10, запускай скрипт с `--hires`, иначе он не найдёт устойчивый участок. Достань диапазон: `grep -a motorOutput LOG00001.BFL`. Запусти: `python3 motor_balance.py LOG00001.01.csv --motor-range 158,2047`, для props-out добавь `--props-out`. Если скрипт пишет `no steady segment >= 10 s`, ровного участка в полёте не было: слетай 15–20 с висения. Для сверки открой в Blackbox Explorer `axisI[2]` на том же участке: медиана S должна дать разницу диагоналей около S/5 процентных пунктов (ориентир при `thrust_linear` = 0, airmode и без насыщения; без airmode умножь на 0.5 + газ).

### Переход на реальное железо
**Стол, пропы сняты.** Сохрани `diff all`.
1. Вкладка Motors: моторы по одному на 5–10 %, порядок 1 RR, 2 FR, 3 RL, 4 FL, направление props-in (или props-out с `yaw_motors_reversed = ON`).
2. АКБ отключена. Покрути каждый мотор рукой: без хруста, без касания колокола о статор, без осевого люфта. Вал не бьёт.
3. Наклон: приложи линейку или уровень к оси вала каждого мотора относительно плоскости рамы. Если на глаз есть перекос, луч или крепление правят до полёта: по оценке из теории 1° на 10" — уже около 7 % по рысканию.
4. ЦТ: аппарат с АКБ и всей нагрузкой на двух пальцах под линией моторов 1–3, потом 2–4. Наклоняется — двигай АКБ, запиши положение (метка на раме).

**Поле, пропы ставятся здесь.** Безветрие или ветер не больше 3–4 м/с (ориентир курса), высота 2–3 м, Blackbox ≥ 1 кГц, ANGLE или ACRO на выбор, один режим во всех полётах. Программа: 20 с висения, 15 с ровного пролёта по прямой, посадка. Повтори на второй АКБ. Если I_yaw или I_pitch больше 5 % в обоих логах — swap-тест. Сначала поменяй местами пропы подозреваемого угла и его пары по диагонали: у моторов 1 и 4 (и у 2 и 3) одно вращение, пропы взаимозаменяемы. Полёт, лог. Перекос не ушёл с пропом — поменяй местами моторы (ESC остаются на своих площадках). **Сразу после перестановки моторов проверь направление во вкладке Motors без пропов:** вращение задаётся настройкой ESC и порядком фаз на площадке, а не самим мотором, и переставленный мотор может крутиться обратно. Затем полёт, лог. Ушёл с мотором — мотор; остался на месте и после этого — ESC, луч или крепление.

**Прерви полёт и садись, если:** аппарат сносит или крутит, и стиком это не удержать; газ висения выше 60 % (ориентир курса: ошибка массы или пропов); слышен дребезг или новый звук; после посадки мотор не удержать пальцем 5 с; один мотор в логе на висении выше 80 % хода (числа — ориентиры курса). После swap-теста первый взлёт — короткий подлёт на 1 м: при перестановке легко перепутать направление пропа.

Самопроверка: лабораторная выполнена, когда:
- **Расчёт (основной путь):** 876 при `158,2047` = 38.01 %, при `48,2047` = 41.42 %, при `motor_output_limit = 80` = 48.22 % (±0.01).
- **Расчёт:** вывод `--demo` совпал с выводом выше: в логе A индексы +1.03/+3.09/+2.95 %, четыре точных решения (два «слабых» — моторы 1 и 4), в сравнении A–B подтверждён мотор 4 FL (изменение ЦТ 0.3 %), отвергнут мотор 1 RR (12.3 %), в логе C все три индекса −0.07 %.
- **Расчёт:** ты своими словами записал, почему в логе A I_pitch «норма» при ЦТ 4 %, и сверил с эталоном ниже.
- **Железо:** на двух логах ровного полёта по одной программе все три индекса ≤ 2 % (ориентир курса). Если нет — для каждого индекса больше 5 % записана причина, найденная swap-тестом или осмотром, и сохранён лог после исправления, где индекс ≤ 2 %.

**Эталон для самопроверки.** Правильное объяснение лога A: мотору 4 нужно на 6 % больше, и это поднимает средний выход передней пары на 3 %. Тяжёлый зад поднимает заднюю пару на 4 % относительно передней, разность даёт около +1 %. Тот же лишний выход мотора 4 добавляет +3 % в roll (он левый) и в yaw (он в паре 1+4). Типичные ошибки. «ЦТ в норме, раз I_pitch 1 %» — индексы складываются, по одному индексу причину не назначают. «Слабый мотор 1, раз гипотеза есть» — по одному логу гипотезы «мотор 1» и «мотор 4» неразличимы, решает swap-тест. Вывод в процентах выглядит как 40–45 вместо 38: в скрипт подан диапазон `48,2047` для лога, где в заголовке 158.

## diagnostics
- **Симптом:** аппарат плавно разворачивает по курсу в висении, рост P или I по yaw не помогает
  - Возможная причина: наклонённый мотор или кривой луч, разные пропы в паре.
  - Что видно в логе: I_yaw стабильно больше 5 %, I_pitch и I_roll около нуля, постоянный `axisI[2]`.
  - Что сделать: проверить ось вала каждого мотора относительно рамы, выпрямить или заменить луч, поставить пропы одной партии.
- **Симптом:** один мотор после полёта заметно горячее остальных
  - Возможная причина: он постоянно работает на повышенной команде (слабый мотор, повреждённый проп, ЦТ смещён к нему).
  - Что видно в логе: медиана этого `motor[i]` выше, узор индексов указывает на его угол.
  - Что сделать: swap пропов, затем swap моторов; при узоре только pitch/roll — перенести АКБ.
- **Симптом:** скрипт выдаёт `no steady segment >= 10 s`
  - Возможная причина: в полёте не было 10 с без изменений газа, или аппарат качает (gyro RMS > 20 °/с).
  - Что сделать: проверь `blackbox_high_resolution` в заголовке (при 1 — `--hires`); при ручном висении подними `thr_span_max` до 40–50; отдельный полёт с 20 с висения; если качает и в висении — сначала разобраться с колебаниями (`bf-pid`, `bf-filters`).
- **Симптом:** проценты моторов в висении выше ожидаемого на 3–4 пункта
  - Возможная причина: неверный `--motor-range`, например 48 вместо 158 при выключенном dynamic idle.
  - Что сделать: взять `motorOutput` из заголовка этого лога (`grep -a motorOutput`).
- **Симптом:** индексы скачут от полёта к полёту больше чем на 2 пункта
  - Возможная причина: ветер, разные участки (висение и пролёт), АКБ сдвигается в полёте.
  - Что сделать: одна программа, безветрие, ремешок и упор под АКБ, сравнивать участки одного типа.
- **Симптом:** после swap-теста аппарат при взлёте сразу закручивает
  - Возможная причина: проп поставлен не той стороной или на мотор другого вращения.
  - Что сделать: дизарм, сверить вращение по схеме Quad X, проп по направлению мотора.
- **Симптом:** на 2025.12 `get dshot_idle_value` пишет, что параметра нет
  - Возможная причина: в 2025.12 он переименован.
  - Что сделать: `get motor_idle`, умолчание то же, 550.

## checklist
- Порядок 1 RR, 2 FR, 3 RL, 4 FL и направление проверены во вкладке Motors без пропов
- `yaw_motors_reversed` соответствует пропам (props-out → ON)
- Моторы без люфта и хруста, валы прямые, оси моторов параллельны, пропы одной партии и отбалансированы
- ЦТ на центре: аппарат с АКБ не наклоняется на линиях 1–3 и 2–4, положение АКБ отмечено
- Диапазон `motorOutput` взят из заголовка конкретного лога
- Медианы на участке 10–20 с без переходов газа, три индекса посчитаны
- Индексы ≤ 2 % на двух логах (ориентир курса); всё больше 5 % объяснено swap-тестом или осмотром
- Только после этого — фильтры и PID

## references
- Betaflight `flight/mixer_init.c`, 4.5-maintenance (mixerQuadX, getMotorOutputLow/High, dynamic idle) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer_init.c | primary | A
- Betaflight `flight/mixer.c`, 4.5-maintenance (yaw_motors_reversed, applyMixToMotors, PID_MIXER_SCALING) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c | primary | A
- Betaflight `blackbox/blackbox.c`, 4.5-maintenance (поля motor, eRPM, заголовки motorOutput и gyro_scale) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/blackbox/blackbox.c | primary | A
- Betaflight `drivers/dshot.c`, 4.5-maintenance (dshotInitEndpoints) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/dshot.c | primary | A
- Betaflight `flight/pid.c`, 4.5-maintenance (iterm_windup, iterm_limit, pidsum_limit) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight `flight/mixer_init.c`, 2025.12-maintenance (та же таблица Quad X) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12-maintenance/src/main/flight/mixer_init.c | primary | A
- blackbox-tools `blackbox_decode.c` (имена столбцов CSV, единицы, файлы .NN.csv) | https://raw.githubusercontent.com/betaflight/blackbox-tools/master/src/blackbox_decode.c | primary | A
- Running with Reversed Motors — Betaflight Documentation | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Reversed-motor-direction.md | primary | A
- Motors Tab — Betaflight Documentation (props-in / props-out) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/app/motors-tab.md | primary | B

## notes
Пороги 2 % и 5 %, критерии устойчивого участка (размах газа 20 за 0.5 с, 20 °/с, 10–20 с), фильтр решений w > 1 % и допуск ЦТ 1 % в сравнении A–B — ориентиры курса, в прошивке их нет. Связь «индекс по тяге = k × индекс по команде» взята из таблицы 15×5 (тяга ∝ команде^k, k ≈ 1.1–1.8; 2 — верхняя граница при оборотах, пропорциональных команде). Для своего мотора с пропом k стоит снять на стенде. K_M для 10" пересчитан по диаметру из табличного 15×5 при том же P/D, это оценка. Медианы реального лога из кейса не приводятся, числа практики получены на синтетике.
