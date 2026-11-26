---
id: est-attitude
title: "Орієнтація: кути Ейлера, кватерніони, комплементарний фільтр"
level: L3
readingTime: 40 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-08
tags:
  - орієнтація
  - кватерніони
  - комплементарний фільтр
  - AHRS
related:
  - est-sensors
  - data-python
  - est-kalman
  - ap-ekf
next:
  - est-kalman
source: content/estimation/est-attitude.md
source_hash: bc09a4c0a4b6
---

## summary
«Де верх» — перше питання, на яке автопілот відповідає тисячу разів на секунду. Гіроскоп дає швидку, але дрейфуючу відповідь; акселерометр — повільну й шумну, але без дрейфу; компас — курс. Модуль пояснює, чому кути Ейлера ламаються (gimbal lock) і прошивки живуть на кватерніонах, як інтегрувати кутову швидкість, як працює комплементарний фільтр (на Python, ~40 рядків) і як він співвідноситься з DCM в ArduPilot і з Mahony/Madgwick у Betaflight/INAV. Лабораторна: власний фільтр на записі IMU проти `ATT` з логу.

## theory
### Представлення орієнтації
- **Кути Ейлера** (roll φ, pitch θ, yaw ψ) — зручні людині. Проблема: при θ = ±90° roll і yaw зливаються (**gimbal lock**), а рівняння для швидкостей зміни кутів містять ділення на cos θ. Для фристайлу з петлями — неприйнятно. Використовуються лише для виведення (`ATT.Roll/Pitch/Yaw`).
- **Матриця повороту (DCM)** — 3×3, стовпці — осі апарата в земній системі. Без особливих точок, але 9 чисел із 6 зв'язками; потрібна ортонормалізація після інтегрування.
- **Кватерніон** q = (w, x, y, z), |q| = 1 — 4 числа, один зв'язок, без особливих точок, дешеве множення. Стандарт у Betaflight (з 3.x), INAV, PX4 (`vehicle_attitude.q`), EKF3 (стани 0–3).

Перехід кватерніон → Ейлер (для виведення):
φ = atan2(2(wx + yz), 1 − 2(x² + y²)); θ = asin(2(wy − zx)); ψ = atan2(2(wz + xy), 1 − 2(y² + z²)).

{{widget:attitude-3d}}

### Інтегрування гіроскопа
Кутова швидкість ω (в осях апарата) змінює кватерніон: q̇ = ½ · q ⊗ (0, ω). Дискретно за крок Δt: q ← q ⊗ (cos(|ω|Δt/2), ω/|ω| · sin(|ω|Δt/2)), потім нормувати. Лише гіроскоп → дрейф зі швидкістю bias (0.05 °/с → 3°/хв) плюс накопичення шуму.

### Комплементарний фільтр
Ідея: гіроскопу віримо на високих частотах, акселерометру (гравітації) — на низьких. Алгоритм Mahony:
1. Передбачити «вниз» в осях апарата з поточного q: v = R(q)ᵀ · (0, 0, 1).
2. Виміряний «вниз» — нормований акселерометр зі знаком мінус: −a/|a| (акселерометр вимірює питому силу; у спокої у FRD він показує (0, 0, −g)).
3. Похибка — векторний добуток e = (−a/|a|) × v (малий при узгодженні, напрямок — вісь поправки).
4. Поправити кутову швидкість: ω' = ω + Kp·e + Ki·∫e (Ki — оцінка bias гіроскопа!).
5. Проінтегрувати ω' у q.

Kp задає сталу часу «довіри» акселерометру: τ ≈ 1/Kp; Kp = 0.5 → ~2 с. Під час маневрів |a| ≠ 1 g — акселерометр бреше; стандартний захист: зменшувати Kp, коли | |a| − g | велике (ArduPilot DCM: `AHRS_GPS_GAIN`, використання GPS для доцентрової поправки; Betaflight: `imu_dcm_kp`, вимкнення корекції при великих прискореннях). Компас додається тим самим способом для осі yaw: похибка між виміряним і очікуваним напрямком горизонтальної складової поля.

{{diagram:chart-attitude-kp-sweep|Ошибка оценки наклона имеет минимум по Kp: слева её делает дрейф гироскопа (ошибка b/Kp), справа — доверие ложному «низу» при разгоне; защита по модулю |a| сдвигает минимум с 0.1 к 0.25–0.5 и вдвое уменьшает ошибку.}}

### Що це в прошивках
- **Betaflight**: Mahony-подібний фільтр на кватерніонах, `imu_dcm_kp` (за замовчуванням 2500 → 0.25 після масштабу), `imu_dcm_ki`; без компаса yaw дрейфує — для Acro неважливо, для GPS Rescue використовується курс за GPS.
- **INAV**: той самий клас фільтра + компас і GPS-курс, поправки з урахуванням прискорення за GPS.
- **ArduPilot**: DCM (матриця, з поправкою за GPS-швидкістю) як резерв, основний — **EKF3**, де орієнтація — частина вектора стану разом зі швидкістю, позицією та bias датчиків. Комплементарний фільтр — це EKF зі сталими, не адаптивними коефіцієнтами.
- **PX4**: EKF2 (`ekf2`), орієнтація у `vehicle_attitude`.

### Чому yaw — особливий
Гравітація не містить інформації про курс: без компаса або GPS-курсу yaw дрейфує з bias гіроскопа Z. На зависанні це ~3°/хв, непомітно; за 10 хвилин — 30°, і Loiter поїде по спіралі («туалетна воронка» — класичний симптом). Джерела yaw: компас (завади), GPS-курс під час руху (не на зависанні), два GPS (moving baseline), EKF-GSF (оцінка за рухом, ArduPilot `EK3_SRC1_YAW = 8`), зовнішня навігація.

{{diagram:complementary-filter|Комплементарний фільтр: інтеграл гіроскопа точний на короткому інтервалі, кут за акселерометром — на довгому; ваги α і 1 − α їх змішують.}}

{{diagram:attitude-mahony-loop|Цикл Mahony в Betaflight: гироскоп интегрируется всегда, а поправка Kp·e от акселерометра включается только после фильтра 25 Гц и проверки 0.9–1.1 g; Ki в Betaflight по умолчанию 0.}}

## practice

Розрахункова лабораторна (без заліза): `att_lab.py` моделює 120 с IMU з bias гіроскопа, шумом, вібрацією, розгонами й координованим віражем і порівнює п'ять оцінювачів. Скрипт і його реальний вивід:

```python
# att_lab.py — attitude estimation lab: simulated IMU, five estimators, numbers.
# python3 att_lab.py   (pure Python 3, no packages)
import math, random

G, FS, T = 9.81, 250, 120.0           # gravity, IMU rate Hz, flight length s
DT = 1.0 / FS
BIAS = [math.radians(b) for b in (0.5, -0.3, 0.2)]   # gyro bias, deg/s -> rad/s
ARW = math.radians(0.005)             # gyro noise density, rad/s/sqrt(Hz)
VIB = 2.0                             # accel vibration amplitude, m/s^2 (motors on)

def truth(t):
    """True roll, pitch, yaw (rad) and earth-frame linear acceleration (NED, m/s^2)."""
    r = p = y = 0.0; acc = (0.0, 0.0, 0.0)
    if 20 <= t < 60:                                  # smooth tilts, little acceleration
        r = math.radians(20) * math.sin(2 * math.pi * 0.2 * (t - 20))
        p = math.radians(15) * math.sin(2 * math.pi * 0.13 * (t - 20))
    elif 60 <= t < 80:                                # sprints: 4 m/s^2 forward/back, 1 s pulses
        a = 4.0 if int(t) % 4 == 0 else (-4.0 if int(t) % 4 == 2 else 0.0)
        p = -math.atan2(a, G); acc = (a, 0.0, 0.0)  # nose down to accelerate forward
    elif 80 <= t < 100:                               # coordinated turn: bank 30 deg, V = 15 m/s
        r = math.radians(30); w = G * math.tan(r) / 15.0
        y = w * (t - 80)
        acc = (-G * math.tan(r) * math.sin(y), G * math.tan(r) * math.cos(y), 0.0)
    return r, p, y, acc

def euler_to_q(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r / 2), math.sin(r / 2), math.cos(p / 2),
                              math.sin(p / 2), math.cos(y / 2), math.sin(y / 2))
    return [cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy, cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy]

def qmul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return [w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2]

def qnorm(q):
    n = math.sqrt(sum(c * c for c in q)); return [c / n for c in q]

def down_body(q):                      # earth "down" (0,0,1) seen in body axes, q = body->earth
    w, x, y, z = q
    return [2*(x*z - w*y), 2*(w*x + y*z), w*w - x*x - y*y + z*z]

def rot_to_body(q, v):                 # earth vector -> body axes (R^T v)
    w, x, y, z = q
    R = [[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)],
         [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
         [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]]
    return [sum(R[i][k] * v[i] for i in range(3)) for k in range(3)]

def integrate(q, g):                   # exact rotation by g*DT, then renormalise
    n = math.sqrt(sum(c * c for c in g))
    if n < 1e-12: return q
    s = math.sin(n * DT / 2) / n
    return qnorm(qmul(q, [math.cos(n * DT / 2), g[0] * s, g[1] * s, g[2] * s]))

def cross(a, b):
    return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]

def make_imu(seed=1):
    rnd = random.Random(seed); out = []
    prev = euler_to_q(*truth(0)[:3])
    for i in range(int(T * FS)):
        t = i * DT
        r, p, y, acc = truth(t)
        q = euler_to_q(r, p, y)
        dq = qmul([prev[0], -prev[1], -prev[2], -prev[3]], q)   # body rate from q(t-dt) -> q(t)
        if dq[0] < 0: dq = [-c for c in dq]
        ang = 2 * math.acos(max(-1.0, min(1.0, dq[0])))
        s = math.sin(ang / 2)
        rate = [0.0, 0.0, 0.0] if s < 1e-12 else [dq[k + 1] / s * ang / DT for k in range(3)]
        prev = q
        gyro = [rate[k] + BIAS[k] + rnd.gauss(0, ARW * math.sqrt(FS)) for k in range(3)]
        f = rot_to_body(q, [acc[0], acc[1], acc[2] - G])        # specific force = a - g (NED)
        vib = VIB * math.sin(2 * math.pi * 117 * t) if t >= 5 else 0.0   # motors spin up at 5 s
        accel = [f[0] + 0.3 * vib + rnd.gauss(0, 0.05), f[1] + 0.3 * vib + rnd.gauss(0, 0.05),
                 f[2] + vib + rnd.gauss(0, 0.05)]
        out.append((t, q, gyro, accel))
    return out

def tilt_err(qt, qe):                  # angle between true and estimated "down", deg
    a, b = down_body(qt), down_body(qe)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))

def acc_tilt_q(a):                     # roll/pitch from accelerometer only (yaw = 0)
    r = math.atan2(-a[1], -a[2]); p = math.atan2(a[0], math.hypot(a[1], a[2]))
    return euler_to_q(r, p, 0.0)

def run(imu, kind, kp=0.25, ki=0.0, gate=(0.9, 1.1), beta=0.05, tau=2.0, lpf=25.0):
    q = [1.0, 0, 0, 0]; ib = [0.0, 0.0, 0.0]; rp = [0.0, 0.0]; errs = []; ib60 = None
    k = 1.0 if not lpf else DT / (DT + 1 / (2 * math.pi * lpf * 1.553774))  # PT2 = 2 x PT1
    s1 = list(imu[0][3]); s2 = list(imu[0][3])
    for t, qt, g, a in imu:
        s1 = [s1[i] + k * (a[i] - s1[i]) for i in range(3)]     # accel low-pass, as acc_lpf_hz
        s2 = [s2[i] + k * (s1[i] - s2[i]) for i in range(3)]
        a = s2
        an = math.sqrt(sum(c * c for c in a))
        if kind == "gyro":
            q = integrate(q, g)
        elif kind == "accel":
            q = acc_tilt_q(a)
        elif kind == "compl":          # first-order complementary filter on roll/pitch angles
            alpha = tau / (tau + DT)
            ar = math.atan2(-a[1], -a[2]); ap = math.atan2(a[0], math.hypot(a[1], a[2]))
            rp = [alpha * (rp[0] + g[0] * DT) + (1 - alpha) * ar,
                  alpha * (rp[1] + g[1] * DT) + (1 - alpha) * ap]
            q = euler_to_q(rp[0], rp[1], 0.0)
        elif kind == "mahony":
            use = gate is None or gate[0] * G < an < gate[1] * G
            if use and an > 1e-3:
                e = cross([-c / an for c in a], down_body(q))
                if math.sqrt(sum(c * c for c in g)) < math.radians(20):   # SPIN_RATE_LIMIT
                    ib = [ib[j] + ki * e[j] * DT for j in range(3)]
                g = [g[j] + kp * e[j] + ib[j] for j in range(3)]
            elif ki > 0:
                g = [g[j] + ib[j] for j in range(3)]
            q = integrate(q, g)
        elif kind == "madgwick":       # gradient step on f(q) = down_body(q) - measured down
            w, x, y, z = q
            qd = [0.5 * c for c in qmul(q, [0.0] + list(g))]
            if an > 1e-3:
                m = [-c / an for c in a]; d = down_body(q)
                f = [d[0] - m[0], d[1] - m[1], d[2] - m[2]]
                J = [[-2*y, 2*z, -2*w, 2*x], [2*x, 2*w, 2*z, 2*y], [2*w, -2*x, -2*y, 2*z]]
                s = [sum(J[i][j] * f[i] for i in range(3)) for j in range(4)]
                sn = math.sqrt(sum(c * c for c in s))
                if sn > 1e-12: qd = [qd[j] - beta * s[j] / sn for j in range(4)]
            q = qnorm([q[j] + qd[j] * DT for j in range(4)])
        errs.append((t, tilt_err(qt, q)))
        if ib60 is None and t >= 60: ib60 = list(ib)
    return errs, ib60

def stats(errs, t0, t1):
    e = [v for t, v in errs if t0 <= t < t1]
    return math.sqrt(sum(v * v for v in e) / len(e)), max(e)

SEG = [("hover 0-20", 0, 20), ("tilts 20-60", 20, 60), ("sprint 60-80", 60, 80),
       ("turn 80-100", 80, 100), ("hover 100-120", 100, 120)]

if __name__ == "__main__":
    imu = make_imu()
    print("gimbal lock: Euler-rate factor 1/cos(theta) =",
          ", ".join(f"{d} deg: {1 / math.cos(math.radians(d)):.1f}" for d in (60, 80, 85, 89)))
    print("bias 0.5 deg/s -> yaw/tilt drift", 0.5 * 60, "deg/min; noise only, 120 s:",
          f"{math.degrees(ARW) * math.sqrt(T):.3f} deg (N*sqrt(t))")
    cases = [("gyro only", dict(kind="gyro")),
             ("accel only", dict(kind="accel")),
             ("complementary tau=2s", dict(kind="compl")),
             ("Mahony BF kp=0.25 ki=0", dict(kind="mahony")),
             ("Mahony kp=0.25 ki=0.02", dict(kind="mahony", ki=0.02)),
             ("Mahony kp=0.25 no gate", dict(kind="mahony", gate=None)),
             ("Madgwick beta=0.05", dict(kind="madgwick"))]
    print(f"{'tilt error RMS / max, deg':26s}" + "".join(f"{s[0]:>15s}" for s in SEG))
    res = {}
    for name, kw in cases:
        errs, ib = run(imu, **kw); res[name] = (errs, ib)
        print(f"{name:26s}" + "".join("{:7.2f}/{:<7.2f}".format(*stats(errs, a, b)) for _, a, b in SEG))
    ib = res["Mahony kp=0.25 ki=0.02"][1]
    print("Mahony ki=0.02 bias estimate at t=60 s, deg/s:", [round(-math.degrees(c), 3) for c in ib],
          "true:", [0.5, -0.3, 0.2])
    print("kp sweep (Mahony, gate 0.9-1.1 g, ki=0): kp -> RMS whole flight / max, deg")
    for kp in (0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0):
        e1, _ = run(imu, "mahony", kp=kp)
        e2, _ = run(imu, "mahony", kp=kp, gate=None)
        print(f"  kp={kp:<5} gate: {stats(e1, 0, T)[0]:5.2f}/{stats(e1, 0, T)[1]:5.2f}"
              f"   no gate: {stats(e2, 0, T)[0]:5.2f}/{stats(e2, 0, T)[1]:5.2f}")
```


```text
gimbal lock: Euler-rate factor 1/cos(theta) = 60 deg: 2.0, 80 deg: 5.8, 85 deg: 11.5, 89 deg: 57.3
bias 0.5 deg/s -> yaw/tilt drift 30.0 deg/min; noise only, 120 s: 0.055 deg (N*sqrt(t))
tilt error RMS / max, deg      hover 0-20    tilts 20-60   sprint 60-80    turn 80-100  hover 100-120
gyro only                    6.72/11.66    24.06/34.54    40.27/45.81    45.92/47.36    53.17/58.83  
accel only                   0.37/0.95      0.52/1.38     15.70/32.70    30.01/30.76     0.42/0.93   
complementary tau=2s         1.07/1.18      1.20/1.53      4.58/7.95     32.40/35.31     5.44/24.87  
Mahony BF kp=0.25 ki=0       1.95/2.33      2.30/2.39      3.03/4.34      4.02/5.18      2.95/5.08   
Mahony kp=0.25 ki=0.02       1.26/1.64      0.29/0.70      2.16/4.47      2.25/2.79      0.93/2.67   
Mahony kp=0.25 no gate       1.95/2.33      2.30/2.39      3.16/4.69     15.54/18.78     4.75/15.27  
Madgwick beta=0.05           0.11/0.25      0.15/0.32      3.29/6.35     15.43/20.61     1.58/9.74   
Mahony ki=0.02 bias estimate at t=60 s, deg/s: [0.489, -0.296, 0.006] true: [0.5, -0.3, 0.2]
kp sweep (Mahony, gate 0.9-1.1 g, ki=0): kp -> RMS whole flight / max, deg
  kp=0.02  gate: 19.47/26.81   no gate: 17.39/23.34
  kp=0.05  gate: 10.51/13.78   no gate:  8.94/12.27
  kp=0.1   gate:  5.85/ 8.31   no gate:  5.59/11.92
  kp=0.25  gate:  2.84/ 5.18   no gate:  6.93/18.78
  kp=0.5   gate:  2.48/ 7.23   no gate:  9.69/24.44
  kp=1.0   gate:  3.30/12.58   no gate: 11.60/27.89
  kp=2.5   gate:  4.81/19.74   no gate: 12.94/29.57
  kp=5.0   gate:  5.65/21.95   no gate: 13.41/29.91
  kp=10.0  gate:  6.07/22.31   no gate: 13.62/30.05
```

### Крок 1. Запис IMU
ArduPilot: лог з `IMU` (gyro, accel) і `ATT`; `LOG_BITMASK` з IMU_RAW не потрібен — 50–400 Гц IMU достатньо. Betaflight: blackbox з `debug_mode = ATTITUDE` (пише кути) або використати gyro + accel зі звичайного логу. Політ 2–3 хвилини з нахилами й зависанням.

### Крок 2. Власний фільтр
```python
import numpy as np
def qmul(a, b):
    w1,x1,y1,z1 = a; w2,x2,y2,z2 = b
    return np.array([w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2,
                     w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2])
def down_body(q):          # gravity direction in body frame from quaternion (w,x,y,z)
    w,x,y,z = q
    return np.array([2*(x*z - w*y), 2*(w*x + y*z), w*w - x*x - y*y + z*z])
def mahony(gyro, acc, dt, kp=0.5, ki=0.01):
    q = np.array([1.0, 0, 0, 0]); ib = np.zeros(3); out = []
    for g, a in zip(gyro, acc):                 # g in rad/s, a in m/s^2 (body frame)
        an = np.linalg.norm(a)
        if an > 1e-3:
            a_u = -a / an; v = down_body(q)   # accel measures specific force (-g at rest, FRD)
            e = np.cross(a_u, v)
            trust = 1.0 if abs(an - 9.81) < 2.0 else 0.0   # ignore accel during hard manoeuvres
            ib += ki * e * dt * trust
            g = g + (kp * e * trust) + ib
        n = np.linalg.norm(g)
        if n > 1e-9:
            dq = np.concatenate([[np.cos(n*dt/2)], g/n*np.sin(n*dt/2)])
            q = qmul(q, dq); q /= np.linalg.norm(q)
        w,x,y,z = q
        out.append([np.degrees(np.arctan2(2*(w*x+y*z), 1-2*(x*x+y*y))),
                    np.degrees(np.arcsin(np.clip(2*(w*y-z*x), -1, 1)))])
    return np.array(out)
```
Прогнати на своєму записі; побудувати roll/pitch проти `ATT.Roll/Pitch` (ArduPilot) або кутів із debug-логу.

### Крок 3. Експерименти
- Ki = 0: спостерігати повільний відхід при сталому bias.
- Kp = 0: лише гіроскоп — дрейф.
- Kp = 5: акселерометр «тягне» в маневрах — похибки під час розгону.
- Порівняти RMS-похибку відносно ATT при трьох Kp.

### Крок 4. Yaw
Проінтегрувати gyro Z без корекції — записати дрейф за хвилину; порівняти з `ATT.Yaw`. Пояснити, звідки прошивка бере курс. Лабораторна: фільтр реалізовано, порівняння з ATT, дрейф yaw пояснено.

### Що має вийти і що записати
- **Порівняння з ATT.** На зависанні й плавних нахилах твій фільтр має йти поруч з `ATT.Roll` і `ATT.Pitch` автопілота: різниця — одиниці градусів, без систематичного відходу. Порахуй RMS різниці за креном і тангажем і запиши.
- **Різкі маневри.** Під час різких розгонів акселерометр показує не тільки гравітацію, тому фільтр перестає йому довіряти (`trust = 0`) і на цей час інтегрує лише гіроскоп. Знайди таку ділянку й подивися, як зростає похибка, поки довіру вимкнено.
- **kp і ki.** Збільш `kp` у 10 разів — оцінка почне смикатися разом із вібраціями акселерометра. Зменш у 10 разів — повільно відповзе дрейфом гіроскопа. Запиши обидва спостереження: це і є суть комплементарного фільтра.
- **Рискання без компаса.** Гравітація паралельна осі рискання, тому акселерометр нічого не каже про курс. Похибка курсу — інтеграл зміщення гіроскопа: при зміщенні 0.5 °/с це 30° за хвилину. Оціни зміщення свого гіроскопа на нерухомій ділянці логу й порахуй очікуваний дрейф за політ.

Лабораторну зараховано, коли фільтр реалізовано й прогнано на записі IMU, порівняння з `ATT` дало числа (RMS різниці за креном і тангажем), експерименти з `kp` описано, а дрейф рискання пояснено й оцінено за зміщенням гіроскопа.

## diagnostics
- **Симптом:** горизонт в OSD з'їжджає після різких маневрів і повільно повертається
  - Можлива причина: гіроскоп накопичив похибку, Kp малий — довге відновлення.
  - Що зробити: норма для Acro; для Angle — помірно підняти Kp, перевірити вібрації.
- **Симптом:** Loiter ходить по спіралі, курс в OSD не збігається з реальним
  - Можлива причина: дрейф yaw / поганий компас.
  - Що зробити: компас, GPS yaw, GSF; перевірити завади.
- **Симптом:** власний фільтр розходиться з ATT на 5–10° у маневрах
  - Можлива причина: немає компенсації доцентрового прискорення.
  - Що зробити: додати корекцію за GPS-швидкістю або знижувати довіру до accel при |a| ≠ g.
- **Симптом:** NaN у кватерніоні
  - Можлива причина: пропущено нормування або acc = 0.
  - Що зробити: перевіряти норми, захищати ділення.

## references
- ArduPilot — EKF (Extended Kalman Filter) overview | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- PX4 — Using the ECL EKF (attitude/state estimation) | https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf.html | primary | A
- Mahony et al., "Nonlinear Complementary Filters on the Special Orthogonal Group" (IEEE TAC 2008) — першоджерело алгоритму | https://hal.archives-ouvertes.fr/hal-00488376 | primary | A

## checklist
- Можу пояснити gimbal lock і чому прошивки на кватерніонах
- Розумію, як Kp/Ki комплементарного фільтра ділять довіру між гіроскопом і акселерометром
- Реалізував фільтр і порівняв з ATT з логу
- Знаю, звідки береться yaw і чому він дрейфує без компаса
- Розумію зв'язок комплементарного фільтра з EKF
