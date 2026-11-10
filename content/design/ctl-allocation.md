---
id: ctl-allocation
title: "Миксер и распределение управления: матрица, насыщение, PX4 Control Allocation, наклонные моторы"
level: L3
readingTime: 45 мин
firmware: PX4 1.15–1.17 · ArduCopter 4.6 · Betaflight 4.5
status: published
tags:
  - миксер
  - control allocation
  - матрица эффективности
  - airmode
  - отказ мотора
related:
  - px4-control
  - px4-architecture
  - ap-heavy
  - math-linalg-rot
  - ctl-theory
  - f-frame-mech
next:
  - ctl-sysid
---

## summary
Регулятор выдаёт три момента и тягу, а моторов 4, 6 или 8, и стоят они где угодно. Перевод делает миксер (в PX4 — control allocation). Ты соберёшь его на Python так же, как PX4: матрица эффективности, псевдообратная, нормировка, последовательная десатурация. Затем прогонишь неудобные случаи: dead cat с ЦТ не по центру, манёвр на упоре, гексу без мотора, наклонные моторы, и перенесёшь результат в Betaflight (`mmix`), ArduPilot (`FRAME_CLASS` 15 + Lua) и PX4 (`CA_*`, вкладка Actuators). Лабораторная: свой фрейм в Python и PX4 SITL, отказ мотора в SIH, на железе — тест моторов без пропов и лог висения.

## theory
### Матрица эффективности B
Каждый мотор i с нормированной командой uᵢ ∈ [0, 1] создаёт силу и момент. PX4 считает их по формуле из `ActuatorEffectivenessRotors.cpp` (одинаково в 1.15, 1.16 и 1.17):

- тяга: **Fᵢ = CT · aᵢ**, где aᵢ — единичная ось ротора (`CA_ROTORn_AX/AY/AZ`, по умолчанию (0, 0, −1), то есть вверх в осях FRD);
- момент: **Mᵢ = CT · (pᵢ × aᵢ) − CT · KM · aᵢ**, где pᵢ — положение ротора относительно ЦТ в метрах (`CA_ROTORn_PX/PY/PZ`), `KM` — отношение реактивного момента к тяге: положительное у CCW-ротора, отрицательное у CW (умолчания `CT` = 6.5, `KM` = 0.05).

Столбцы [Mx My Mz Fx Fy Fz]ᵀ образуют матрицу B размером 6×N; нужно найти u, при котором B·u равно запрошенным моментам и тяге. У коптера с вертикальными моторами строки Fx и Fy нулевые, независимых осей четыре.

### Псевдообратная и нормировка
При N > 4 решений бесконечно много. PX4 берёт псевдообратную M = pinv(B), то есть решение с минимальной нормой u, и нормирует столбцы (`ControlAllocationPseudoInverse.cpp`): крен и тангаж приводит к общему масштабу, рыскание к максимуму 1, тягу к среднему по моторам. Так `MC_*RATE_K` значат одно и то же на любой раме, но если геометрия меняет физическую эффективность оси, меняется и усиление контура (шаг 5).

Betaflight и ArduPilot получают готовые коэффициенты roll/pitch/yaw/throttle на мотор (ArduPilot приводит их к ±0.5 в `normalise_rpy_factors`). Знаки различаются — главная ошибка при переносе:

| Прошивка | Где матрица | Знак pitch у заднего мотора | Рыскание у CW |
|---|---|---|---|
| PX4 | считается из `CA_ROTORn_*` | отрицательный (нос вверх = +My) | `KM` < 0 |
| ArduPilot | `add_motor_raw(n, roll, pitch, yaw, order)` | отрицательный (как PX4) | −1 |
| Betaflight | `mmix n THR ROLL PITCH YAW` | **положительный** (`mixerQuadX`) | −1 (документация: 1 = CCW) |

### Насыщение: кто уступает первым
Когда команда выходит за [0, 1], кто-то уступает:

- **PX4** (`CA_METHOD` = 1 или 2 = Auto, которое для мультиротора выбирает последовательную десатурацию, `ControlAllocationSequentialDesaturation.cpp`). При `MC_AIRMODE` = 0 тягу разрешено только уменьшать, затем ужимаются крен и тангаж, рыскание добавляется последним и режется первым; для него верхнюю границу временно поднимают на 15 % (`MINIMUM_YAW_MARGIN`). При `MC_AIRMODE` = 1 тягу можно и поднять ради крена/тангажа, при 2 — ещё и ради рыскания. `CA_METHOD` = 0 просто обрезает выходы, и оси начинают влиять друг на друга.
- **ArduPilot** (`AP_MotorsMatrix::output_armed_stabilizing`). Сначала ограничивается рыскание до того, что влезает при «лучшем» газе, но не меньше `MOT_YAW_HEADROOM`/1000 (умолчание 200 → 0.2). Если roll+pitch+yaw всё равно шире диапазона, они масштабируются вместе, а газ сдвигается; ставятся флаги `limit.*`. Air-mode в Acro включается через `ACRO_OPTIONS` бит 0 или RC-опцию 84.
- **Betaflight** (`mixer.c`, `mixer_type` = LEGACY по умолчанию). Если размах roll+pitch+yaw больше 1, все три оси делятся на размах одинаково, после чего газ сдвигается так, чтобы всё уместилось. Без airmode при газе ниже 50 % размах дополнительно ужимается до 0.5…1. Приоритет крена над рысканием получается раньше, на PID: `pidsum_limit` = 500 против `pidsum_limit_yaw` = 400.

### Отказ мотора на гексе
На гексе X с чередованием вращения (PNPNPN) после потери одного мотора псевдообратная сама загоняет противоположный мотор в 0, и висение держат четыре оставшихся. Каждый тянет W/4 вместо W/6 — в 1.5 раза больше. Мотор на нуле упирается в границу, и в части направлений запаса по моменту нет (шаг 4). Раскладка PPNNPN (пример `MotorMatrix_fault_tolerant_hex.lua` в ArduPilot) часть отказов переживает с запасом по всем осям.

Как реагируют прошивки:
- **PX4.** `CA_FAILURE_MODE` = 1 убирает отказавший мотор из матрицы (в 1.15–1.17 это единственный режим, кроме 0 = Ignore). Об отказе узнают от детектора по току ESC: `FD_ACT_EN`, `FD_ACT_MOT_THR` = 0.2, `FD_ACT_MOT_C2T` = 2.0 А/%, `FD_ACT_MOT_TOUT` = 100 мс (1.15–1.17); действие задаётся в `COM_ACT_FAIL_ACT`. В ветке main режимы расширены: 1 и 2 вдобавок останавливают или реверсируют противоположный мотор гексы.
- **ArduPilot.** Детектор `thrust_loss_check` включает thrust boost, если 1 с аппарат снижается при газе ≥ 90 % (или упоре по газу) и целевом наклоне < 15°. В GCS приходит сообщение «Potential Thrust Loss (N)». Мотор с наибольшим фильтрованным выходом считается потерянным и исключается из расчёта насыщения; детектор дисбаланса тяги работает только при ≥ 6 моторах.
- **Betaflight.** Отдельной обработки отказа мотора нет.

### Наклонные моторы
Если ось мотора наклонить по касательной к окружности на угол θ в ту же сторону, куда действует его реактивный момент, плечо r тоже начинает работать на рыскание:

**Mz = CT · (r · sinθ + |KM| · cosθ)**, а вертикальная тяга падает как **cosθ**.

При r = 0.246 м и KM = 0.05 наклон 10° даёт ×1.84 по рысканию ценой 1.5 % тяги; боковые силы пар взаимно гасятся. В PX4 наклон — это ось `CA_ROTORn_AX/AY/AZ`. В матрицах ArduPilot и Betaflight оси ротора нет, а одинаковое увеличение yaw у всех моторов съест нормировка.

{{diagram:alloc-pipeline|PX4 строит B по CA_ROTORn_*, обращает её один раз при смене параметров, а в каждом цикле только умножает и десатурирует; отказ мотора — это удаление столбца, а не новый регулятор.}}

## practice
Основной путь — Python 3 + numpy/scipy (numpy 2.5.3, scipy 1.18.1) и PX4 SITL. PX4 в контейнере автора не собирался (2 ядра, неполное дерево исходников), поэтому команды SITL взяты из документации PX4 1.17 и помечены как цитаты. Python-код запускался, вывод вставлен без правок.

### Шаг 1. Аллокатор как в PX4
Файл `alloc.py` — это прямой перенос трёх функций PX4: `computeEffectivenessMatrix`, `updateControlAllocationMatrixScale` и `ControlAllocationSequentialDesaturation`.

```python
# alloc.py - control allocation as PX4 control_allocator does it (v1.15-1.17)
import numpy as np

def effectiveness(rotors):
    """rotors: list of dict(p=(px,py,pz), a=(ax,ay,az), ct, km) -> B 6xN (Mx,My,Mz,Fx,Fy,Fz)."""
    B = np.zeros((6, len(rotors)))
    for i, r in enumerate(rotors):
        a = np.array(r.get("a", (0, 0, -1)), float); a /= np.linalg.norm(a)
        p = np.array(r["p"], float); ct = r.get("ct", 6.5); km = r["km"]
        B[:3, i] = ct * np.cross(p, a) - ct * km * a   # ActuatorEffectivenessRotors.cpp
        B[3:, i] = ct * a
    return B

def mix_matrix(B):
    """Pseudo-inverse + normalisation (ControlAllocationPseudoInverse.cpp)."""
    M = np.linalg.pinv(B)                                # N x 6
    nz = lambda c: max(np.sum(np.abs(c) > 1e-3), 1)
    rs = np.sqrt(np.sum(M[:, 0]**2) / (nz(M[:, 0]) / 2))
    ps = np.sqrt(np.sum(M[:, 1]**2) / (nz(M[:, 1]) / 2))
    s = np.ones(6); s[0] = s[1] = max(rs, ps); s[2] = M[:, 2].max()
    for ax in (5, 4, 3):                                 # thrust z first, x/y fall back to z
        c = np.abs(M[:, ax]); n = np.sum(c > 1e-7)
        s[ax] = c.sum() / n if n else s[5]
    M = M / s; M[np.abs(M) < 1e-3] = 0
    return M

def desat(u, v, increase_only=False, lo=0.0, hi=1.0):
    """desaturateActuators(): shift u along v to get back into [lo, hi]."""
    def gain(u):
        kmin = kmax = 0.0
        for ui, vi in zip(u, v):
            if abs(vi) < 0.2: continue
            if ui < lo: k = (lo - ui) / vi; kmin = min(kmin, k); kmax = max(kmax, k)
            if ui > hi: k = (hi - ui) / vi; kmin = min(kmin, k); kmax = max(kmax, k)
        return kmin + kmax
    g = gain(u)
    if increase_only and g < 0: return u
    u = u + g * v
    return u + 0.5 * gain(u) * v

def allocate(M, sp, method="seq", airmode=0):
    """sp = [roll, pitch, yaw, Fx, Fy, Fz] (normalised, hover Fz < 0)."""
    if method == "clip":                                 # CA_METHOD = 0
        return np.clip(M @ sp, 0, 1)
    R, P, Y, T = M[:, 0], M[:, 1], M[:, 2], M[:, 5]
    no_yaw = sp.copy(); no_yaw[2] = 0
    u = M @ no_yaw
    if airmode == 2:                                     # MC_AIRMODE = 2
        u = desat(u + Y * sp[2], T); return desat(u, Y)
    if airmode == 1: u = desat(u, T)                     # MC_AIRMODE = 1
    else: u = desat(desat(desat(u, T, True), R), P)      # MC_AIRMODE = 0
    u = u + Y * sp[2]                                    # mixYaw()
    u = desat(u, Y, hi=1.15)                             # MINIMUM_YAW_MARGIN = 0.15
    return desat(u, T, True)
```

### Шаг 2. Свой фрейм: dead cat 7"
Передние лучи у такой рамы шире и короче, ЦТ смещён назад. Блоки шагов 2–5 — это один файл `demo.py`, его запуск: `python3 demo.py`.

```python
import numpy as np
from scipy.optimize import linprog
from alloc import effectiveness, mix_matrix, allocate
np.set_printoptions(precision=3, suppress=True)

# --- 1. custom frame: "dead cat" 7", CG behind the geometric centre (metres, FRD)
cat = [dict(p=( 0.13,  0.17, 0), km= 0.05),   # 0 front right, CCW
       dict(p=(-0.15, -0.11, 0), km= 0.05),   # 1 rear left,   CCW
       dict(p=( 0.13, -0.17, 0), km=-0.05),   # 2 front left,  CW
       dict(p=(-0.15,  0.11, 0), km=-0.05)]   # 3 rear right,  CW
B = effectiveness(cat); M = mix_matrix(B)
print("mix [roll pitch yaw thrust]:\n", M[:, [0, 1, 2, 5]])
u = M @ [0, 0, 0, 0, 0, -0.5]
print("hover u:", u, "front/rear:", round(u[0] / u[1], 3))
```

```text
mix [roll pitch yaw thrust]:
 [[-0.707  0.707  0.647 -1.071]
 [ 0.707 -0.707  1.    -0.929]
 [ 0.707  0.707 -0.647 -1.071]
 [-0.707 -0.707 -1.    -0.929]]
hover u: [0.536 0.464 0.536 0.464] front/rear: 1.154
```

Передние моторы на висении нагружены на 15.4 % сильнее задних, и это ровно 0.15/0.13 — отношение плеч до ЦТ. Крен делают диагональные пары (все коэффициенты 0.707), рыскание сильнее грузит задние моторы (1.0 против 0.647).

### Шаг 3. Насыщение
```python
def run(name, sp, **kw):
    sp = np.array(sp, float); want = B @ (M @ sp); got = B @ allocate(M, sp, **kw)
    print(f"{name:20s} roll {got[0]/want[0]:.2f}  yaw " +
          (f"{got[2]/want[2]:.2f}" if abs(want[2]) > 1e-6 else " -  ") + f"  thrust {got[5]/want[5]:.2f}")
hard = [0.6, 0, 0.5, 0, 0, -0.6]
print("ideal u:", M @ hard)
run("CA_METHOD=0 clip", hard, method="clip")
run("seq, MC_AIRMODE=0", hard, airmode=0)
low = [0.4, 0, 0, 0, 0, -0.05]
run("low thr, AIRMODE=0", low, airmode=0)
run("low thr, AIRMODE=1", low, airmode=1)
```

```text
ideal u: [ 0.542  1.481  0.744 -0.367]
CA_METHOD=0 clip     roll 0.61  yaw 0.48  thrust 0.95
seq, MC_AIRMODE=0    roll 1.00  yaw 0.15  thrust 0.90
low thr, AIRMODE=0   roll 0.16  yaw  -    thrust 1.00
low thr, AIRMODE=1   roll 1.00  yaw  -    thrust 6.09
```

Обрезка даёт 61 % крена и паразитный тангаж. Десатурация даёт 100 % крена, а рыскание падает до 15 %, тяга до 90 %. При газе 5 % без airmode от крена остаётся 16 % — так аппарат кувыркается на снижении. С `MC_AIRMODE` = 1 крен полный, но тяга растёт в 6 раз: аппарат подпрыгивает. Поэтому PX4 велит выключать airmode на время тюнинга.

### Шаг 4. Гекса без мотора
Геометрия, нумерация и направления вращения взяты из `10044_sihsim_hex` (плечо 1 м); CT = 1 — нормировка расчёта, в самом airframe остаётся умолчание 6.5. Аппарат с T/W = 3 висит на 2 единицах тяги из 6.

```python
ang = [30, 90, 150, -150, -90, -30]
hexa = lambda s: [dict(p=(np.cos(np.radians(a)), np.sin(np.radians(a)), 0), ct=1, km=0.05 * k)
                  for a, k in zip(ang, s)]
PNPNPN, PPNNPN = [1, -1, 1, -1, 1, -1], [-1, -1, 1, -1, 1, 1]
def margins(rot, lost, W=2.0):            # max |torque| per axis while the other two stay 0
    Bh = effectiveness(rot)[[0, 1, 2, 5]]; bnd = [(0, 0) if i == lost else (0, 1) for i in range(6)]
    out = []
    for ax in range(3):
        for sg in (1, -1):
            r = linprog(-sg * Bh[ax], A_eq=np.delete(Bh, ax, 0), b_eq=[0, 0, -W], bounds=bnd)
            out.append(max(sg * Bh[ax] @ r.x, 0) if r.success else 0)
    return np.round(out, 2)               # +R -R +P -P +Y -Y
Bh = effectiveness(hexa(PNPNPN))[[0, 1, 2, 5]]; Bh[:, 0] = 0          # CA_FAILURE_MODE=1
print("PNPNPN, M0 lost, pinv hover u:", np.linalg.pinv(Bh) @ [0, 0, 0, -3.0])
for k in range(6):
    print(f"lost M{k}: PNPNPN {margins(hexa(PNPNPN), k)}  PPNNPN {margins(hexa(PPNNPN), k)}")
```

```text
PNPNPN, M0 lost, pinv hover u: [-0.    0.75  0.75 -0.    0.75  0.75]
lost M0: PNPNPN [1.5  0.   0.   1.73 0.   0.1 ]  PPNNPN [1.   1.   0.58 1.73 0.1  0.03]
lost M1: PNPNPN [1.5  0.   1.73 1.73 0.1  0.  ]  PPNNPN [1.   1.   1.73 1.73 0.1  0.1 ]
lost M2: PNPNPN [1.5  0.   1.73 0.   0.   0.1 ]  PPNNPN [1.   0.   1.73 0.   0.   0.1 ]
lost M3: PNPNPN [0.   1.5  1.73 0.   0.1  0.  ]  PPNNPN [0.   1.   1.73 0.   0.1  0.  ]
lost M4: PNPNPN [0.   1.5  1.73 1.73 0.   0.1 ]  PPNNPN [1.   1.   1.73 1.73 0.1  0.1 ]
lost M5: PNPNPN [0.   1.5  0.   1.73 0.1  0.  ]  PPNNPN [1.   1.   0.58 1.73 0.03 0.1 ]
```

У PNPNPN псевдообратная (при T/W = 2, W = 3) ставит противоположный мотор M3 в 0, а остальные четыре работают на 75 %. При любом отказе остаётся минимум два нуля, всегда в одну сторону по крену и в одну по рысканию. Аппарат висит, но порыв с «нулевой» стороны отработать уже нечем. PPNNPN переживает отказы M0, M1, M4 и M5 с запасом по всем шести направлениям, а при отказе M2 или M3 тоже остаётся с нулями. Вывод для проекта: гекса сама по себе от отказа мотора не страхует. Нужны раскладка вращения, проверенная таким расчётом, и запас тяги: у PNPNPN четыре мотора несут весь вес, то есть каждый в 1.5 раза больше нормы.

### Шаг 5. Наклон моторов
```python
P, KM = [(0.174, 0.174), (-0.174, -0.174), (0.174, -0.174), (-0.174, 0.174)], [0.05, 0.05, -0.05, -0.05]
def tilted(deg):
    s, c = np.sin(np.radians(deg)), np.cos(np.radians(deg))
    return [dict(p=(x, y, 0), km=k, a=(-y / np.hypot(x, y) * np.sign(k) * s,
                                       x / np.hypot(x, y) * np.sign(k) * s, -c)) for (x, y), k in zip(P, KM)]
B0 = effectiveness(tilted(0))
for d in (0, 5, 10, 15):
    Bt = effectiveness(tilted(d))
    print(f"tilt {d:2d} deg: yaw x{Bt[2,0]/B0[2,0]:.2f}  Fz x{Bt[5,0]/B0[5,0]:.3f}")
print("CA_ROTOR0_AX/AY/AZ @10 deg:", np.round(tilted(10)[0]["a"], 3))
```

```text
tilt  0 deg: yaw x1.00  Fz x1.000
tilt  5 deg: yaw x1.43  Fz x0.996
tilt 10 deg: yaw x1.84  Fz x0.985
tilt 15 deg: yaw x2.24  Fz x0.966
CA_ROTOR0_AX/AY/AZ @10 deg: [-0.123  0.123 -0.985]
```

{{diagram:chart-alloc-tilt|Наклон моторов на 10° по касательной даёт ×1.84 к моменту рыскания ценой 1.5 % вертикальной тяги. Из-за нормировки PX4 физическое усиление контура рыскания растёт во столько же раз, так что yaw-тюнинг надо проверить заново.}}

В нормированной матрице PX4 столбец рыскания остаётся [1 1 −1 −1], поэтому момент на единицу команды вырастает с 1.30 до 2.39 (×1.84). Тот же `MC_YAWRATE_K` теперь даёт в 1.84 раза более жёсткий контур.

### Шаг 6. Перенос в прошивки и PX4 SITL
PX4: `CA_AIRFRAME` = 0 (Multirotor), `CA_ROTOR_COUNT` = 4, `CA_ROTORn_PX/PY` из шага 2, `CA_ROTORn_KM` = ±0.05; в Actuators → Geometry сверь схему и Direction CCW. Документация (Actuators): «The X, Y, Z positions are in FRD coordinate frame, relative to the centre of gravity». Отказ гексы в SITL (PX4 1.17, цитаты из документации SIH и Failure Injection): сборка `make px4_sitl sihsim_hex`, затем `SYS_FAILURE_EN` = 1, `CA_FAILURE_MODE` = 1, взлёт, в pxh `failure motor off -i 1`, возврат `failure motor ok -i 1`. По исходнику 1.17 инъекция только останавливает мотор (`motor_stop_mask`, в консоли «Stopping motors»). Из матрицы его убирает детектор отказа, и тогда в консоли появляется «Removing motor from allocation». В логе (Flight Review / pyulog) смотри `control_allocator_status.motor_stop_mask`, `handled_motor_failure_mask`, `unallocated_torque`, `actuator_motors.control[0..5]`. Если мотор убран, ожидание по шагу 4 такое: противоположный около 0, остальные около 75 % при T/W 2.

Betaflight (конфигурация, в контейнере не выполнялась; столбец pitch взят с обратным знаком, roll и pitch приведены к ±1):

```text
mixer CUSTOM
mmix reset
mmix 0 0.929 -1.000  1.000 -1.000
mmix 1 1.071 -1.000 -1.000  0.647
mmix 2 0.929  1.000  1.000  1.000
mmix 3 1.071  1.000 -1.000 -0.647
save
```

Порядок моторов как у QUADX: 0 — RR, 1 — FR, 2 — RL, 3 — FL. ArduPilot (`FRAME_CLASS` = 15, `SCR_ENABLE` = 1, скрипт в `APM/scripts/`, в контейнере не выполнялся):

```lua
MotorsMatrix:add_motor_raw(0, -0.707,  0.707,  0.647, 1)  -- front right, CCW
MotorsMatrix:add_motor_raw(1,  0.707, -0.707,  1.0,   3)  -- rear left, CCW
MotorsMatrix:add_motor_raw(2,  0.707,  0.707, -0.647, 4)  -- front left, CW
MotorsMatrix:add_motor_raw(3, -0.707, -0.707, -1.0,   2)  -- rear right, CW
MotorsMatrix:set_throttle_factor(0, 1.071)
MotorsMatrix:set_throttle_factor(1, 0.929)
MotorsMatrix:set_throttle_factor(2, 1.071)
MotorsMatrix:set_throttle_factor(3, 0.929)
assert(MotorsMatrix:init(4), "Failed to init MotorsMatrix")
motors:set_frame_string("deadcat 7")
```

`set_throttle_factor` работает только до `init()` и только в классе 15. Коэффициенты здесь в долях тяги: линеаризацию в газ делают `THR_MDL_FAC` / `MOT_THST_EXPO`.

### Переход на реальное железо
1. **Пропы сняты**, АКБ через smoke stopper. PX4: Actuators → Enable sliders (или Identify & Assign Motors для PWM); ArduPilot: Motor Test, порядок A-B-C-D = testing order; Betaflight: вкладка Motors. Документация PX4 прямо пишет: «Remove the propellers from motors before assigning outputs or any testing».
2. По каждому мотору: место на раме совпадает со схемой, направление вращения совпадает с `KM` / yaw-знаком (лента на колоколе), на disarmed мотор не крутится, на minimum крутится уверенно.
3. Знаки без пропов: армить в Stabilize/Acro, наклонить раму рукой вправо — правые моторы должны раскрутиться; повернуть по рысканию — должна вырасти пара, компенсирующая поворот. Иначе ошибка в знаке столбца.
4. **Пропы ставятся только сейчас.** Висение 30–60 с на высоте 1–2 м, в открытом месте, люди на расстоянии ≥ 10 м. Критерий прерывания: аппарат уводит при нейтральных стиках, или любой мотор выше 90 % → посадка.
5. Лог висения: PX4 — `actuator_motors`, ArduPilot — `RCOU.C1…C4`, Betaflight — `motor[0..3]`. На dead cat отношение средних передних выходов к задним должно совпасть с шагом 2 в пределах ±5 %: в `actuator_motors` PX4 это тяга (1.15, `THR_MDL_FAC` применяется позже, в драйвере выхода), в командах ArduPilot и Betaflight — около √1.15 ≈ 1.07, если тяга растёт как квадрат команды. Средние выходы CW-пары и CCW-пары различаются не больше чем на 5 %, иначе перекошен мотор или неверен `KM`.

Лабораторная засчитывается, когда: (SITL/расчёт) столбцы mix своего фрейма и отношение нагрузок посчитаны в Python и объяснены геометрией; таблица насыщения из шага 3 повторена для своего фрейма с выводом, какая ось уступает первой; в SIH-гексе после `failure motor off -i 1` в логе есть ненулевой `motor_stop_mask`, записано, сработало ли удаление из матрицы (`handled_motor_failure_mask`), а выходы моторов сравнены с прогнозом шага 4; (железо) тест моторов без пропов совпал со схемой по месту и направлению всех моторов, а лог висения показывает отношение выходов в пределах ±5 % от расчёта и ни один мотор не выше 90 %.

## diagnostics
- **Симптом:** при отрыве аппарат резко переворачивается
  - Возможная причина: неверный порядок или направление мотора, либо перепутан знак столбца (в Betaflight знак pitch противоположен PX4/ArduPilot).
  - Что сделать: снять пропы, тест моторов по одному, проверка знаков наклоном рамы рукой (шаг 3 перехода на железо).
- **Симптом:** на резких креновых манёврах рыскание «отпускает» и аппарат доворачивает
  - Возможная причина: штатная десатурация — рыскание режется первым (PX4 `MINIMUM_YAW_MARGIN`, ArduPilot `MOT_YAW_HEADROOM`, Betaflight `pidsum_limit_yaw`).
  - Что сделать: поднять T/W или запас по газу; на ArduPilot поднять `MOT_YAW_HEADROOM`; на PX4 проверить `control_allocator_status.unallocated_torque[2]`.
  - Что видно в логе: рыскание в насыщении на пиках крена, `actuator_saturation` ≠ 0.
- **Симптом:** кувырок или «проваливание» при нулевом газе на снижении
  - Возможная причина: airmode выключен, на малом газе крен ужимается (в шаге 3 — до 16 %).
  - Что сделать: `MC_AIRMODE` = 1 после тюнинга (PX4), `ACRO_OPTIONS` бит 0 (ArduPilot), AIRMODE (Betaflight); для PX4 airmode по рысканию требует тумблер арма.
- **Симптом:** после замены рамы или наклона моторов рыскание осциллирует
  - Возможная причина: нормировка PX4 сохраняет команду, а физическое усиление выросло (×1.84 при 10°).
  - Что сделать: снизить `MC_YAWRATE_K`/P пропорционально росту эффективности и пере-тюнить.
- **Симптом:** гекса после отказа мотора крутится по рысканию и сносится
  - Возможная причина: PNPNPN без запаса в части направлений; `CA_FAILURE_MODE` = 0 или детектор не сработал (нет телеметрии тока ESC для `FD_ACT_*`).
  - Что сделать: T/W ≥ 3, проверить раскладку (PPNNPN), включить `CA_FAILURE_MODE` = 1 и проверить детектор в SITL.
  - Последствия: без обработки отказа PX4 продолжает распределять момент на мёртвый мотор, и ошибка растёт до потери управления.
- **Симптом:** ArduPilot со скриптовой матрицей не армится
  - Возможная причина: `SCR_ENABLE` = 0, скрипт не в `APM/scripts/`, `init()` раньше `add_motor_raw`, `FRAME_CLASS` ≠ 15.
  - Что сделать: сообщения скрипта в GCS, порядок вызовов, перезагрузка после смены `FRAME_CLASS`.

## checklist
- Могу записать столбец B для мотора по положению, оси, CT и KM
- Понимаю, зачем PX4 нормирует матрицу и как это меняет усиление после смены геометрии
- Знаю, кто уступает первым при насыщении в PX4, ArduPilot и Betaflight
- Посчитал нагрузку моторов своего фрейма на висении
- Понимаю, почему гекса PNPNPN после отказа не имеет запаса в части направлений
- Перенёс матрицу в mmix / Lua / CA_* с правильными знаками
- Проверил моторы без пропов и сверил лог висения с расчётом

## references
- PX4 Guide: Control Allocation (Mixing) | https://docs.px4.io/main/en/concept/control_allocation.html | primary | A
- PX4 Guide: Actuator Configuration and Testing | https://docs.px4.io/main/en/config/actuators.html | primary | A
- PX4 Guide: System Failure Injection | https://docs.px4.io/main/en/debug/failure_injection.html | primary | A
- PX4 source: ActuatorEffectivenessRotors.cpp (v1.17.0) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessRotors.cpp | primary | A
- PX4 source: ControlAllocationSequentialDesaturation.cpp (v1.17.0) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/lib/control_allocation/control_allocation/ControlAllocationSequentialDesaturation.cpp | primary | A
- PX4 source: control_allocator module.yaml (CA_* parameters, v1.17.0) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/control_allocator/module.yaml | primary | A
- ArduPilot source: AP_MotorsMatrix.cpp (Copter-4.6.3) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_Motors/AP_MotorsMatrix.cpp | primary | A
- ArduPilot example: MotorMatrix_fault_tolerant_hex.lua | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_Scripting/examples/MotorMatrix_fault_tolerant_hex.lua | primary | A
- Betaflight: Mixer (mmix, mixer_type) | https://betaflight.com/docs/wiki/guides/current/Mixer | primary | A
- Betaflight source: mixer.c (4.5-maintenance) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c | primary | A
