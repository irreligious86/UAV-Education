"""Visual pass (stage 7), batch v4_per_tools: one new diagram per perception / tools module.

camera-choice-tree        per-camera — the interface and shutter rule of «Камеры и интерфейсы»: frame not used in the
                          control loop -> IP camera / HDMI capture (100+ ms, operator picture); navigation (VIO) or fast
                          motion -> global shutter (USB OV9281); camera within ~30 cm of the companion -> CSI (1–2 frames,
                          120 fps at low resolution); otherwise USB UVC (3–5 m cable, MJPEG 60–120 ms, CPU decoding).
chart-cv-threshold        per-cv — the worked counters: threshold 0.5 -> precision 210/230 = 0.91, recall 210/250 = 0.84;
                          thresholds 0.3 (0.80 / 0.93) and 0.7 (0.96 / 0.70) from the module; person search picks the lower
                          threshold, an automatic action on a target the higher one plus confirmation over several frames.
vio-failure-tree          per-visual-nav — «Отказ источника»: what the companion sends after VIO lost tracking and what EKF3
                          does: nothing (health by arrival, 300 ms) -> inertial, failsafe; a jump -> EK3_POS_I_GATE 500
                          (5 sigma) rejects, accepted again after 7 s (10 s with velocity) with a reset; a frozen pose at the
                          old rate -> gates do not catch it, the aircraft drifts; ODOMETRY quality < VISO_QUAL_MIN -> dropped.
chart-tracking-kp-limit   per-tracking — the gain limit of the delayed P loop against T_d: pi/(2·T_d) without autopilot
                          dynamics, zero phase margin of Kp·e^(-s·T_d)/(s·(0.4 s + 1)), and the module's 1-D simulation with
                          v/a limits (run()/critical_kp() copied from practice step 2); 100 ms -> 15.7 / 10.4 / 7.8,
                          300 ms -> 5.2 / 3.7 / 2.8 1/s; the working gain 3–5x below the limit shaded for the limited curve.
precland-lost-target      per-landing — ArduPilot PLND: what happens when the target is lost, by rangefinder altitude: above
                          PLND_ALT_MAX not yet a problem, below PLND_ALT_MIN the landing continues, in between PLND_STRICT
                          (4.7.2 AC_PrecLand_StateMachine): 0 lands vertically at once; 1 (default) descends PLND_TIMEOUT s,
                          retries, then hovers 7 s and lands; 2 the same retry, then hovers; retries per mode <= PLND_RET_MAX.
chart-avoid-stop-distance per-depth-avoid — d_stop = v·L + v²/(2a) + d_margin for a = 3 m/s², margin 2 m, L = 0.3 s (the
                          worked example) and 0.5 s (top of the module's 0.2–0.5 s), plus braking only (L = 0); crossings
                          with the reliable stereo range 6 m: 4.9, 4.1 (example), 3.6 m/s from the v_max formula.
edge-budget-verdict       per-edge-ml — the budget verdict as the module states it: p99 of the whole pipeline after warm-up
                          and with the parallel load <= budget (example 80 ms), 20–30 min in the enclosure without p99
                          doubling, quantised model not worse on any slice -> release with version and rollback.
config-change-flow        tools-overview — the «до/после» rule for configs: diff all / .param, dated file name with board,
                          baseline commit, one change -> new file, git diff shows exactly one line -> commit with «зачем»;
                          more lines -> other firmware / reset / someone's edits, hundreds of lines -> dump.
step-metrics-anatomy      data-python — what step_metrics() and bounce_back() measure on a setpoint -> gyro pair: overshoot
                          over the normalised step, settle time into ±5 %, the 0.25 s window, the bounce-back after the stick
                          stop (0.2 s window, % of |setpoint| before the stop); the 5" guide values. The response shape is
                          illustrative (second order, zeta 0.6), no time scale and no metric values are printed on it.
chart-sysid-phase-margin  ctl-sysid — phase margin of L = Kp·G for the step 1 model G = K·e^(-s·tau)/(T·s + 1), T = 20 ms,
                          tau = 9 ms, against the crossover frequency (Kp = sqrt(1 + (2·pi·f·T)²)/K), alone and with a
                          first-order low-pass 80 and 40 Hz; at 20 Hz the filters cost 14° and 27° (arctan(f/f_c)).
sim-stand-choice-tree     tools-gazebo — which stand for which check: logic without a world -> SITL alone; a world without
                          cameras and CI -> Gazebo server without graphics; vision, landing, gimbal -> Gazebo with a camera
                          (--headless-rendering without a screen); the flight controller itself -> HITL.
"""
from __future__ import annotations

import math
import re

from plot import Axis, chart
from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, Node, flow, svg, text, tree


# ---------------------------------------------------------------- helpers
def _add_footer(svg_str: str, lines: list[str], lh: int = 16) -> str:
    """Grow a helper-built SVG downwards and add muted footnote lines under it."""
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg_str)
    w, h = float(m.group(1)), float(m.group(2))
    nh = h + lh * len(lines) + 6
    body = "".join(text(16, h + 4 + lh * (i + 1) - 4, s, "m t", "start") for i, s in enumerate(lines))
    svg_str = svg_str.replace(m.group(0), f'viewBox="0 0 {w:g} {nh:g}"', 1)
    i = svg_str.rfind("</svg>")
    return svg_str[:i] + body + svg_str[i:]


def _inject(svg_str: str, body: str) -> str:
    i = svg_str.rfind("</svg>")
    return svg_str[:i] + body + svg_str[i:]


# ---------------------------------------------------------------- per-camera
def camera_choice_tree() -> str:
    t = tree("Какую камеру и интерфейс брать: по тому, куда идёт кадр", Node("loop", ["Кадр идёт в контур", "управления?"], [
        ("нет", Node("ip", ["IP-камера / HDMI-", "захват: 100+ мс —", "картинка оператору"], leaf=True)),
        ("да", Node("nav", ["Навигация (VIO) или", "быстрое движение?"], [
            ("да", Node("gs", ["Global shutter", "(например, USB", "на OV9281)"], leaf=True, accent=True)),
            ("нет", Node("cab", ["Камера в пределах", "~30 см от companion?"], [
                ("да", Node("csi", ["CSI: 1–2 кадра,", "120 fps в низком", "разрешении"], leaf=True, accent=True)),
                ("нет", Node("usb", ["USB UVC: кабель", "3–5 м, MJPEG", "60–120 мс, CPU"], leaf=True)),
            ])),
        ])),
    ]), width=720, box_w=166, box_h=46, gap_y=74)
    return _add_footer(t, ["Rolling shutter при вибрации даёт «желе» и ломает VIO — поэтому для навигации только global"])


# ---------------------------------------------------------------- per-cv
def cv_threshold() -> str:
    tp, fp, fn = 210, 20, 40
    p05, r05 = tp / (tp + fp), tp / (tp + fn)
    assert round(p05, 2) == 0.91 and round(r05, 2) == 0.84
    thr = [0.3, 0.5, 0.7]
    prec = [0.80, p05, 0.96]
    rec = [0.93, r05, 0.70]
    s = [dict(name="", xs=thr, ys=prec, cls="a"), dict(name="", xs=thr, ys=prec, cls="a", dots=True),
         dict(name="", xs=thr, ys=rec, cls="w", dash=True), dict(name="", xs=thr, ys=rec, cls="w", dots=True)]
    out = chart("Порог уверенности двигает precision и recall в разные стороны",
                s, Axis("порог уверенности детектора", 0.2, 0.8, ticks=[0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]),
                Axis("доля", 0.6, 1.0, ticks=[0.6, 0.7, 0.8, 0.9, 1.0], fmt="{:.1f}"),
                marks=[(0.3, "", "m"), (0.5, "", "ink"), (0.7, "", "m")])
    # hand-placed labels (px from the chart scale: L 64 .. 696 for 0.2 .. 0.8, T 36 .. 312 for 1.0 .. 0.6)
    sx = lambda v: 64 + (v - 0.2) / 0.6 * 632
    sy = lambda v: 312 - (v - 0.6) / 0.4 * 276
    body = [
        text(sx(0.7) + 8, sy(0.96) + 4, "precision", "a t b", "start"),
        text(sx(0.7) + 8, sy(0.70) + 4, "recall", "w t b", "start"),
        text(sx(0.3) + 6, sy(0.80) + 16, "0.80", "a t", "start"), text(sx(0.3) + 6, sy(0.93) - 8, "0.93", "w t", "start"),
        text(sx(0.5) + 6, sy(p05) - 8, f"{p05:.2f}", "a t", "start"), text(sx(0.5) + 6, sy(r05) - 8, f"{r05:.2f}", "w t", "start"),
        text(sx(0.7) - 6, sy(0.96) - 8, "0.96", "a t", "end"), text(sx(0.7) - 6, sy(0.70) + 16, "0.70", "w t", "end"),
        text(sx(0.3) + 6, sy(0.66), "поиск человека:", "t", "start"),
        text(sx(0.3) + 6, sy(0.66) + 14, "пропуск дороже", "m t", "start"),
        text(sx(0.5) + 6, sy(0.66), f"пример: {tp}/{tp + fp} и {tp}/{tp + fn}", "t", "start"),
        text(sx(0.5) + 6, sy(0.66) + 14, f"TP {tp}, FP {fp}, FN {fn}", "m t", "start"),
        text(sx(0.7) + 6, sy(0.86), "действие по цели:", "t", "start"),
        text(sx(0.7) + 6, sy(0.86) + 14, "+ N кадров", "m t", "start"),
    ]
    return _inject(out, "".join(body))


# ---------------------------------------------------------------- per-visual-nav
def vio_failure_tree() -> str:
    t = tree("VIO потерял трекинг: что companion шлёт в EKF3 и что EKF с этим делает",
             Node("r", ["VIO потерял трекинг.", "Что приходит в EKF?"], [
                 ("", Node("none", ["Ничего: companion", "перестал слать"], [
                     ("", Node("n2", ["Через 300 мс источник", "«нездоров»: инерциалка", "→ failsafe", "(FS_EKF_ACTION)"], leaf=True, accent=True))])),
                 ("", Node("jump", ["Скачок позы"], [
                     ("", Node("j2", ["Ворота EK3_POS_I_GATE", "500 (5σ) отбрасывают;", "через 7 с (10 с со", "скоростью) — сброс"], leaf=True))])),
                 ("", Node("frz", ["Замёрзшая поза", "с прежней частотой"], [
                     ("", Node("f2", ["Ворота не ловят:", "инновация мала, EKF", "«стоит», а аппарат", "уплывает"], leaf=True))])),
                 ("", Node("q", ["ODOMETRY, quality", "< VISO_QUAL_MIN"], [
                     ("", Node("q2", ["Измерение в EKF", "не передаётся"], leaf=True))])),
             ]), width=720, box_w=166, box_h=58, gap_y=86)
    # the dangerous leaf (frozen pose) gets a red outline: it is the case the module warns about
    m = re.findall(r'<rect class="box" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="58" rx="18"/>', t)
    x, y, w = m[1]                                      # leaves in order: n2 (accent, not matched), j2, f2, q2
    t = _inject(t, f'<rect x="{x}" y="{y}" width="{w}" height="58" rx="18" fill="none" stroke="{DANGER}" stroke-width="1.8"/>')
    return _add_footer(t, ["Защита — первая ветка: companion по статусу трекинга перестаёт слать; резерв EK3_SRC2 на GPS",
                           "и пилот с AltHold на тумблере"])


# ---------------------------------------------------------------- per-tracking
def _run(kp, delay, tau_v=0.4, v_max=3.0, a_max=3.0, dt=0.01, T=30.0):
    """The module's practice step 2 model, unchanged: peak |error| over the last 10 s."""
    n_d = int(round(delay / dt))
    seen = [5.0] * (n_d + 1)
    x, v, tail = 5.0, 0.0, 0.0
    for k in range(int(T / dt)):
        cmd = max(-v_max, min(v_max, -kp * seen[0]))
        dv = max(-a_max * dt, min(a_max * dt, (cmd - v) / tau_v * dt))
        v += dv
        x += v * dt
        seen = seen[1:] + [x]
        if k * dt > T - 10:
            tail = max(tail, abs(x))
    return tail


def _critical_kp(delay):
    lo, hi = 0.05, 30.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _run(mid, delay) < 0.05 else (lo, mid)
    return lo


def _analytic_kp(delay, tau_v=0.4):
    lo, hi = 0.01, 100.0
    for _ in range(100):
        w = (lo + hi) / 2
        lo, hi = (w, hi) if math.atan(w * tau_v) + w * delay < math.pi / 2 else (lo, w)
    return w * math.hypot(1, w * tau_v)


def tracking_kp_limit() -> str:
    fine = [0.09 + 0.005 * i for i in range(63)]                      # 90 … 400 ms
    ds = [0.09 + 0.02 * i for i in range(16)] + [0.10, 0.30, 0.40]     # simulation points (bisection is slow)
    ds = sorted(set(round(d, 3) for d in ds))
    ideal = [math.pi / (2 * d) for d in fine]
    ana = [_analytic_kp(d) for d in fine]
    sim = [_critical_kp(d) for d in ds]
    i1, i3 = ds.index(0.10), ds.index(0.30)
    k1 = (math.pi / 0.2, _analytic_kp(0.1), sim[i1])
    k3 = (math.pi / 0.6, _analytic_kp(0.3), sim[i3])
    assert [round(v, 1) for v in k1] == [15.7, 10.4, 7.8] and [round(v, 1) for v in k3] == [5.2, 3.7, 2.8]
    ms_f, ms = [1000 * d for d in fine], [1000 * d for d in ds]
    work_lo, work_hi = [k / 5 for k in sim], [k / 3 for k in sim]
    return chart(
        "Предел K_p контура слежения падает с задержкой T_d",
        [dict(name="π/(2·T_d) — без динамики", xs=ms_f, ys=ideal, cls="m", dash=True, label_at=165, label_dy=-8, label_anchor="start"),
         dict(name="τ = 0.4 с", xs=ms_f, ys=ana, cls="w", label_at=128, label_dy=-7, label_anchor="start"),
         dict(name="лимиты v, a (симуляция)", xs=ms, ys=sim, cls="a", label_at=250, label_dy=13, label_anchor="end"),
         dict(name="", xs=ms, ys=work_hi, cls="a", w=0, band=(work_lo, work_hi))],
        Axis("чистая задержка цепочки T_d, мс", 90, 400, ticks=[100, 150, 200, 250, 300, 350, 400]),
        Axis("предельное K_p, 1/с (м/с на метр ошибки)", 0, 18, ticks=[0, 3, 6, 9, 12, 15, 18]),
        marks=[(100, "100 мс: " + " / ".join(f"{v:.1f}" for v in k1), "ink", 16),
               (300, "300 мс: " + " / ".join(f"{v:.1f}" for v in k3), "ink", 16)],
        notes=[(504, 291, "рабочий K_p: предел/5…/3", "a")])


# ---------------------------------------------------------------- per-landing
def precland_lost_target() -> str:
    # semantics checked against ArduPilot 4.7.2 AC_PrecLand_StateMachine: STRICT 0 lands vertically at once;
    # 1 and 2 descend PLND_TIMEOUT s, then retry; the failsafe after a failed retry is hover 7 s + land (1)
    # or hover (2). Above ALT_MAX / below ALT_MIN the target is "out of range" and the vehicle just descends.
    W = 720
    boxes = [
        Box("r", ["Цель пропала", "при посадке.", "Высота по", "дальномеру?"], 10, 130, 124, 74, accent=True),
        Box("hi", ["выше", "PLND_ALT_MAX"], 156, 36, 140, 44),
        Box("mid", ["между ALT_MIN", "и ALT_MAX"], 156, 145, 140, 44),
        Box("lo", ["ниже", "PLND_ALT_MIN"], 156, 276, 140, 44),
        Box("hio", ["отсутствие цели ещё не считается проблемой"], 318, 36, 392, 44),
        Box("st", ["PLND_STRICT?"], 318, 145, 104, 44, accent=True),
        Box("s0", ["0: сразу садится вертикально"], 440, 92, 270, 36),
        Box("s1", ["1 (по умолчанию): снижение ещё", "PLND_TIMEOUT с → повторный заход;", "цели нет — висит 7 с и садится"], 440, 138, 270, 58, accent=True),
        Box("s2", ["2: тот же повторный заход;", "цели нет — висит, не садится"], 440, 206, 270, 44),
        Box("loo", ["посадка продолжается без цели: у земли", "камера не видит маркер целиком"], 318, 276, 392, 44),
    ]
    links = [("r", "hi"), ("r", "mid"), ("r", "lo"), ("hi", "hio"), ("mid", "st", "", True), ("lo", "loo"),
             ("st", "s0"), ("st", "s1", "", True), ("st", "s2")]
    notes = [(10, 20, "ArduPilot PLND: что делает аппарат без цели — решает высота (дальномер обязателен)", "m t"),
             (10, 342, "Повторных заходов за режим — не больше PLND_RET_MAX", "m t"),
             (10, 358, "PX4 — та же логика у земли: ниже PLD_FAPPR_ALT снижение продолжается и при потере цели", "m t")]
    return flow("Точная посадка: потеря цели на разной высоте", boxes, links, W, 368, notes=notes)


# ---------------------------------------------------------------- per-depth-avoid
def avoid_stop_distance() -> str:
    a, margin, R = 3.0, 2.0, 6.0
    vmax = lambda L: -a * L + math.sqrt((a * L) ** 2 + 2 * a * (R - margin))
    v0, v3, v5 = vmax(0.0), vmax(0.3), vmax(0.5)
    assert round(v3, 1) == 4.1 and round(v0, 1) == 4.9 and round(v5, 1) == 3.6
    vs = [0.1 * i for i in range(71)]
    d = lambda v, L: v * L + v * v / (2 * a) + margin
    return chart(
        "Дистанция остановки: задержка добавляет v·L к торможению",
        [dict(name="L = 0", xs=vs, ys=[d(v, 0) for v in vs], cls="m", dash=True, label_at=7, label_dy=4, label_anchor="start"),
         dict(name="L = 0.3 с", xs=vs, ys=[d(v, 0.3) for v in vs], cls="a", label_at=7, label_dy=4, label_anchor="start"),
         dict(name="L = 0.5 с", xs=vs, ys=[d(v, 0.5) for v in vs], cls="w", label_at=7, label_dy=4, label_anchor="start")],
        Axis("скорость сближения v, м/с", 0, 8.5, ticks=[0, 1, 2, 3, 4, 5, 6, 7, 8]),
        Axis("d_stop = v·L + v²/(2a) + запас, м", 0, 14, ticks=[0, 2, 4, 6, 8, 10, 12, 14]),
        hmarks=[(R, "надёжная дальность стерео 6 м", "d"), (margin, "запас 2 м", "m")],
        marks=[(v5, f"{v5:.1f}", "w", 22), (v3, f"v_max {v3:.1f} м/с (пример)", "a", 40), (v0, f"{v0:.1f}", "m", 22)],
        notes=[(72, 60, "a = 3 м/с²; v_max — где кривая", "m"), (72, 76, "пересекает дальность датчика;", "m"),
               (72, 92, "L = 0 — только торможение и запас", "m")])


# ---------------------------------------------------------------- per-edge-ml
def edge_budget_verdict() -> str:
    t = tree("Вердикт по бюджету: модель влезает в задачу или нет", Node("p99", ["p99 всего конвейера", "(после прогрева, с видео,", "MAVLink) ≤ бюджета?"], [
        ("нет", Node("fix", ["FP16 на GPU — первый", "шаг; INT8 на NPU/TPU;", "слой не уехал на CPU?"], leaf=True)),
        ("да", Node("heat", ["20–30 мин в корпусе:", "p99 вдвое хуже, чем", "в первую минуту?"], [
            ("да", Node("thr", ["Троттлинг: обдув,", "радиатор, режим", "мощности"], leaf=True)),
            ("нет", Node("sl", ["По срезам (дистанция,", "свет, фон) после", "квантования не хуже?"], [
                ("нет", Node("cal", ["Калибровка PTQ", "по всем условиям,", "QAT или FP16"], leaf=True)),
                ("да", Node("ok", ["Бюджет выполнен:", "выкатка с версией", "и откатом"], leaf=True, accent=True)),
            ])),
        ])),
    ]), width=720, box_w=166, box_h=48, gap_y=76)
    return _add_footer(t, ["Бюджет — от задачи: пример ТЗ «p99 камера → bbox ≤ 80 мс при 35 °C, без троттлинга 30 минут»"])


# ---------------------------------------------------------------- tools-overview
def config_change_flow() -> str:
    boxes = [
        Box("b1", ["Файл «до»:", "diff all или .param"], 10, 34, 160, 48),
        Box("b2", ["configs/ГГГГ-ММ-ДД_", "имя_плата_diff.txt"], 190, 34, 160, 48),
        Box("b3", ["git commit", "«имя: baseline дата»"], 370, 34, 160, 48),
        Box("b4", ["Одно изменение →", "новый файл «после»"], 550, 34, 160, 48),
        Box("dec", ["git diff: ровно", "одна строка — та,", "что менял?"], 550, 126, 160, 56, accent=True),
        Box("ok", ["git commit с «зачем»:", "«rpm_filter_min_hz 100→50:", "моторы 10\" ниже 100 Гц»"], 190, 126, 300, 56, accent=True,
            note="следующее изменение — снова с файла «после»"),
        Box("bad", ["Строк больше: другая версия прошивки, сброс к умолчаниям,",
                    "чужие правки — разобраться до полёта; сотни строк — dump,",
                    "а не diff all; после обновления прошивки — новый baseline"], 190, 230, 520, 60),
    ]
    links = [("b1", "b2"), ("b2", "b3"), ("b3", "b4"), ("b4", "dec", "", False, "v"), ("dec", "ok", "да", True, "h"),
             ("dec", "bad", "нет", False, "v")]
    notes = [(10, 20, "Правило инструментов: конфиг «до» и «после» — в git, разница видна одной строкой", "m t")]
    return flow("Изменение конфига через git: до, после, одна строка", boxes, links, 720, 300, notes=notes)


# ---------------------------------------------------------------- data-python
def step_metrics_anatomy() -> str:
    W, H = 720, 380
    L, R, T, B = 64, 24, 40, 300                       # plot area
    t0, t1, t_end = 0.05, 0.35, 0.60                   # step up, stick release, end (s; shape only)
    zeta, wn = 0.6, 50.0                               # illustrative second-order response
    wd = wn * math.sqrt(1 - zeta ** 2)
    phi = math.acos(zeta)

    def unit(tt):                                      # unit step response, 0 before the step
        if tt <= 0:
            return 0.0
        return 1 - math.exp(-zeta * wn * tt) / math.sqrt(1 - zeta ** 2) * math.sin(wd * tt + phi)

    ts = [i * 0.001 for i in range(int(t_end / 0.001) + 1)]
    sp = [0.0 if t < t0 else (1.0 if t < t1 else 0.0) for t in ts]
    gy = [unit(t - t0) - unit(t - t1) for t in ts]
    sx = lambda t: L + t / t_end * (W - R - L)
    lo_y, hi_y = -0.3, 1.3
    sy = lambda v: B - (v - lo_y) / (hi_y - lo_y) * (B - T)
    # metrics exactly as step_metrics() / bounce_back() define them
    seg = [(t, g) for t, g in zip(ts, gy) if t0 <= t < min(t0 + 0.25, t1)]
    peak_t, peak = max(seg, key=lambda p: p[1])
    overshoot = (peak - 1) * 100
    inside = [abs(g - 1) < 0.05 for _, g in seg]
    k_set = next(k for k in range(len(inside)) if all(inside[k:]))
    t_set = seg[k_set][0]
    rev_t, rev = min(((t, g) for t, g in zip(ts, gy) if t1 <= t < t1 + 0.2), key=lambda p: p[1])
    bounce = -rev * 100
    assert 5 <= overshoot <= 15 and bounce < 25
    path = lambda ys: "M" + " L".join(f"{sx(t):.1f} {sy(v):.1f}" for t, v in zip(ts, ys))
    o = [text(16, 20, "Что меряют step_metrics() и bounce_back(): ступенька и отпущенный стик", "b", "start", 13)]
    # ±5 % band
    o.append(f'<rect x="{sx(t0):.1f}" y="{sy(1.05):.1f}" width="{sx(t1) - sx(t0):.1f}" height="{sy(0.95) - sy(1.05):.1f}" fill="{ACCENT}" opacity="0.12"/>')
    # axes (no grid)
    o.append(f'<line x1="{L}" y1="{sy(0):.1f}" x2="{W - R}" y2="{sy(0):.1f}" stroke="{MUTED}" stroke-width="0.8"/>')
    o.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{B}" stroke="{INK}" stroke-width="1"/>')
    for v, lab in ((0, "0"), (1, "1")):
        o.append(text(L - 6, sy(v) + 4, lab, "m t", "end"))
    o.append(f'<text transform="translate(18 {(T + B) / 2}) rotate(-90)" text-anchor="middle" class="m t">(gyro − база) / ступенька</text>')
    o.append(text((L + W - R) / 2, B + 18, "время (масштаб условный: окна 0.25 с и 0.2 с — из кода)", "m t"))
    # curves
    o.append(f'<path d="{path(sp)}" fill="none" stroke="{MUTED}" stroke-width="1.6" stroke-dasharray="6 4"/>')
    o.append(f'<path d="{path(gy)}" fill="none" stroke="{ACCENT}" stroke-width="2"/>')
    o.append(text(sx(0.50), sy(0.0) - 8, "gyro", "a t b", "start"))
    o.append(text(sx(t0) - 6, sy(0.6), "setpoint", "m t b", "end"))
    # overshoot
    o.append(f'<path class="ln" d="M{sx(peak_t):.1f} {sy(1.0):.1f} L{sx(peak_t):.1f} {sy(peak) + 2:.1f}" marker-end="url(#ar)"/>')
    o.append(text(sx(peak_t) - 6, sy(1.22), "overshoot = перелёт / ступенька (5–15 % — хорошо)", "t", "start"))
    # settle time bracket under the band
    yb = sy(0.86)
    o.append(f'<path class="ln" d="M{sx(t0):.1f} {yb:.1f} L{sx(t_set):.1f} {yb:.1f}" marker-end="url(#ar)"/>')
    o.append(f'<line x1="{sx(t_set):.1f}" y1="{yb - 6:.1f}" x2="{sx(t_set):.1f}" y2="{sy(0.95):.1f}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="3 3"/>')
    o.append(text(sx(t_set) + 6, yb + 4, "время установления: дальше", "t", "start"))
    o.append(text(sx(t_set) + 6, yb + 18, "только внутри ±5 %", "t", "start"))
    o.append(text(sx(t1) - 6, sy(1.05) - 6, "±5 %", "a t", "end"))
    # step window 0.25 s
    yw = sy(-0.18)
    o.append(f'<path class="lnm" d="M{sx(t0):.1f} {yw:.1f} L{sx(t0 + 0.25):.1f} {yw:.1f}"/>')
    for tx in (t0, t0 + 0.25):
        o.append(f'<line x1="{sx(tx):.1f}" y1="{yw - 5:.1f}" x2="{sx(tx):.1f}" y2="{yw + 5:.1f}" stroke="{MUTED}" stroke-width="1"/>')
    o.append(text((sx(t0) + sx(t0 + 0.25)) / 2, yw + 16, "окно step_metrics: 0.25 с", "m t"))
    # bounce-back
    o.append(f'<path class="ln" d="M{sx(rev_t):.1f} {sy(0):.1f} L{sx(rev_t):.1f} {sy(rev) - 2:.1f}" marker-end="url(#ar)"/>')
    yw2 = sy(-0.27)
    o.append(f'<path class="lnm" d="M{sx(t1):.1f} {yw2:.1f} L{sx(t1 + 0.2):.1f} {yw2:.1f}"/>')
    for tx in (t1, t1 + 0.2):
        o.append(f'<line x1="{sx(tx):.1f}" y1="{yw2 - 5:.1f}" x2="{sx(tx):.1f}" y2="{yw2 + 5:.1f}" stroke="{MUTED}" stroke-width="1"/>')
    o.append(text((sx(t1) + sx(t1 + 0.2)) / 2, yw2 - 8, "окно bounce_back: 0.2 с", "m t"))
    o.append(text(sx(t1) - 8, sy(0.62), "стик отпущен:", "t", "end"))
    o.append(text(sx(t1) - 8, sy(0.62) + 14, "|setpoint| < 200 °/с", "m t", "end"))
    o.append(text(sx(0.40), sy(0.34), "bounce-back = отскок / |setpoint|", "t", "start"))
    o.append(text(sx(0.40), sy(0.34) + 14, "перед остановкой; < 10 % хорошо,", "m t", "start"))
    o.append(text(sx(0.40), sy(0.34) + 28, "> 25 % — много D или механика", "m t", "start"))
    foot = H - 30
    o.append(text(16, foot, "Ориентиры для 5\" (Betaflight); медиана по 10–20 шагам, а не лучший шаг.", "m t", "start"))
    o.append(text(16, foot + 16, "Форма отклика условная (второй порядок, без масштаба) — она показывает, что меряют, а не значения.", "m t", "start"))
    return svg(W, H, "Метрики переходного процесса: overshoot, установление, bounce-back", "".join(o))


# ---------------------------------------------------------------- ctl-sysid
def sysid_phase_margin() -> str:
    K, T, tau = 1.0, 0.020, 0.009                      # model identified in practice step 1
    fs = [1 + 0.25 * i for i in range(157)]            # 1 … 40 Hz
    pm = lambda f, fc=None: (180 - math.degrees(math.atan(2 * math.pi * f * T)) - 360 * f * tau
                             - (math.degrees(math.atan(f / fc)) if fc else 0))
    kp = lambda f: math.hypot(1, 2 * math.pi * f * T) / K
    c80, c40 = pm(20) - pm(20, 80), pm(20) - pm(20, 40)
    assert round(c80) == 14 and round(c40) == 27
    f_kp = lambda k: math.sqrt(k * k * K * K - 1) / (2 * math.pi * T)
    f2, f4 = f_kp(2), f_kp(4)
    dots = lambda fc: dict(name="", xs=[20], ys=[pm(20, fc)], cls={None: "a", 80: "w", 40: "d"}[fc], dots=True)
    return chart(
        "Запас по фазе по модели: выше K_p — выше частота среза, меньше запас",
        [dict(name="без фильтра", xs=fs, ys=[pm(f) for f in fs], cls="a", label_at=40, label_dy=4, label_anchor="start"),
         dict(name="+ ФНЧ 80 Гц", xs=fs, ys=[pm(f, 80) for f in fs], cls="w", label_at=40, label_dy=4, label_anchor="start"),
         dict(name="+ ФНЧ 40 Гц", xs=fs, ys=[pm(f, 40) for f in fs], cls="d", dash=True, label_at=40, label_dy=4, label_anchor="start"),
         dots(None), dots(80), dots(40)],
        Axis("частота среза f_ср, Гц  (без фильтра K_p = √(1 + (2π·f·T)²) / K)", 0, 48, ticks=[0, 5, 10, 15, 20, 25, 30, 35, 40]),
        Axis("запас по фазе, °", -80, 180, ticks=[-60, -30, 0, 30, 60, 90, 120, 150, 180]),
        hmarks=[(0, "0° — граница устойчивости", "d")],
        marks=[(20, f"20 Гц: запас {pm(20):.0f}°; ФНЧ 80 Гц → −{c80:.0f}°, 40 Гц → −{c40:.0f}°", "ink", 18)],
        notes=[(72, 268, f"без фильтра: K_p = 2 → f_ср {f2:.1f} Гц,", "m"),
               (72, 284, f"K_p = 4 → {f4:.1f} Гц", "m"),
               (72, 300, "шаг 1: K = 1, T = 20 мс, τ = 9 мс", "m")])


# ---------------------------------------------------------------- tools-gazebo
def sim_stand_tree() -> str:
    t = tree("Какой стенд для какой проверки", Node("r", ["Что проверяешь?"], [
        ("логику без мира", Node("sitl", ["SITL без Gazebo:", "встроенная модель,", "мира нет"], leaf=True)),
        ("мир без камер", Node("srv", ["Gazebo без графики:", "gz sim -s -r мир.sdf,", "pytest → pass/fail"], leaf=True, accent=True)),
        ("зрение, посадку", Node("cam", ["Gazebo с камерой;", "без экрана —", "--headless-rendering"], leaf=True, accent=True)),
        ("сам полётник", Node("hitl", ["HITL: настоящий FC,", "датчики от симулятора,", "моторы не крутятся"], leaf=True)),
    ]), width=720, box_w=166, box_h=48, gap_y=80)
    return _add_footer(t, ["Камера без шума и размытия обманывает: проверять с шумом (параметры датчика в SDF),",
                           "сменой освещения и размытием движения. С камерами RTF падает ниже 1: lockstep",
                           "сохраняет корректность, тест идёт дольше"])


def build(D: dict) -> None:
    D["camera-choice-tree"] = camera_choice_tree()
    D["chart-cv-threshold"] = cv_threshold()
    D["vio-failure-tree"] = vio_failure_tree()
    D["chart-tracking-kp-limit"] = tracking_kp_limit()
    D["precland-lost-target"] = precland_lost_target()
    D["chart-avoid-stop-distance"] = avoid_stop_distance()
    D["edge-budget-verdict"] = edge_budget_verdict()
    D["config-change-flow"] = config_change_flow()
    D["step-metrics-anatomy"] = step_metrics_anatomy()
    D["chart-sysid-phase-margin"] = sysid_phase_margin()
    D["sim-stand-choice-tree"] = sim_stand_tree()
