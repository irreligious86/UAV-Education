"""Visual pass (stage 7), batch v6_ros_px4: one new diagram per ROS 2 / PX4 module (two for px4-intro).

px4-tune-order-flow         px4-control — the tuning order of the module as a flow: filters by the spectrum first
                            (IMU_GYRO_CUTOFF 40 Hz, IMU_DGYRO_CUTOFF 20 Hz, notch; autotune does not tune them), then
                            either autotune (most frames; MC_AT_EN = 1 + reboot, QGC → PID Tuning; writes rate P/I/D,
                            K = 1 and MC_ROLL_P / PITCH_P / YAW_P — saveGainsToParams() of mc_autotune_attitude_control)
                            or manual rate K → D → I and attitude P with the step-response rules; step response check
                            (overshoot ≤ 10 %, D without noise; else K/D ±10–20 %), velocity (MPC_XY_VEL_P_ACC 1.8,
                            MPC_Z_VEL_P_ACC 4.0 — first when Position wobbles), position (MPC_XY_P 0.95, MPC_Z_P 1.0).
px4-roll-osc-tree           px4-architecture — the worked example «vehicle wobbles in roll» as a decision tree, one
                            question per node: vehicle_angular_velocity rate ≈ IMU_GYRO_RATEMAX (800 Hz)? -> CPU
                            overload; oscillation also in vehicle_rates_setpoint? -> uorb top -1 (sensor with gaps ->
                            EKF2 innovations, else attitude P / position); only in the measurement -> spectrum peak in
                            band? (IMU_GYRO_CUTOFF / notch, else rate P / D).
px4-mode-ladder             px4-intro — the manual multicopter modes as a ladder of estimates (mode_requirements.cpp of
                            v1.17.0): Acro needs angular velocity, Stabilized + attitude, Altitude + local altitude,
                            Position + local position; what the autopilot holds and what is left to the pilot (practice
                            step 2); the 1.17 fallback Position -> Altitude on position loss, -> Stabilized without
                            altitude (checkModeFallback() in failsafe/failsafe.cpp; COM_POSCTL_NAVL removed).
px4-upgrade-param-tree      px4-intro — what happens to a saved parameter after the update to 1.17, from the module's
                            update rules: name gone -> translated by param_translation.cpp (SDLOG_MODE −1 ->
                            SDLOG_BACKEND 0) or lost (MPC_HOLD_DZ -> MAN_DEADZONE by hand); name kept -> a non-default
                            value is kept (meaning checked: COM_ARM_WO_GPS), a value equal to the old default silently
                            takes the 1.17 default (MC_ROLL_P 6.5 -> 4.0, IMU_DGYRO_CUTOFF 30 -> 20).
px4-dds-topic-naming        px4-ros2 — how a uORB topic gets its ROS 2 name, both directions: .msg MESSAGE_VERSION
                            (VehicleLocalPosition 1, TrajectorySetpoint 0) -> the dds_topics.yaml line (no line = no
                            topic) -> uxrce_dds_client adds _vN for version > 0 (generate_topic_name() in
                            utilities.hpp) -> MicroXRCEAgent (udp4 8888 / serial 921600) -> /fmu/out/..._v1 and
                            /fmu/in/trajectory_setpoint; px4_msgs of the same version as the firmware.
jetson-latency-budget       px4-companion-jetson — the module's latency budget as stacked bars: CSI frame ≤ 16 ms +
                            TensorRT YOLO-nano 12 ms + tracker 2 ms + DDS over UART 921600 2 ms = 32 ms (~35 ms); USB MJPEG
                            camera +40–80 ms -> 72–112 ms; plus a Wi-Fi bridge +20–50 ms -> 92–162 ms (3–5 times more).
ap-dds-guided-seq           ros2-ardupilot — the order of the module for AP_DDS as a message sequence: /ap/status and
                            /ap/pose/filtered (ENU), /ap/mode_switch {mode: 4} GUIDED (reply status, curr_mode),
                            /ap/arm_motors after pre-arm, /ap/experimental/takeoff (alt; without it ground setpoints are
                            ignored), /ap/cmd_vel stream in frame map, stream lost -> GUID_TIMEOUT = 3 s -> stop, mode 9
                            LAND. Service names: AP_DDS_Service_Table.h of Copter 4.7.2, GUID_TIMEOUT: Parameters.cpp.
chart-nav-brake-speed       ros2-nav — v_max = −a·t_r + √((a·t_r)² + 2·a·d) for a = 3 m/s² and t_r = 0 / 0.3 s against
                            the usable range d; the practice step 2 answer at d = 8 − 2 = 6 m: 5.2 m/s, and the two wrong
                            answers of the module: 6.0 m/s (reaction delay forgotten) and 6.9 m/s (margin not subtracted).
ros2-sync-call-deadlock     ros2-from-ros1 — why a synchronous service call inside a callback blocks the node: with
                            cli.call() the only executor thread waits inside tick() for a reply that it would itself have
                            to deliver, the 0.05 s timer ticks are not served and setpoints stop; with call_async() tick()
                            returns at once, the ticks keep the 50 ms period and the reply runs as its own callback.
"""
from __future__ import annotations

import math

from plot import Axis, _Scale, chart
from svg import ACCENT, DANGER, INK, MUTED, WARN, sequence, svg, text


# ---------------------------------------------------------------- helpers
def _rect(x, y, w, h, cls="box", rx=6, extra=""):
    return f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"{extra}/>'


def _arrow(d, acc=False, extra=""):
    return f'<path class="{"lna" if acc else "ln"}" d="{d}" marker-end="url(#{"ara" if acc else "ar"})"{extra}/>'


def _path(d, cls="ln"):
    return f'<path class="{cls}" d="{d}"/>'


def _lines(cx, y, lines, size=10.5, lh=13, cls_first="", cls_rest="", anchor="middle"):
    return "".join(text(cx, y + i * lh, s, cls_first if i == 0 else cls_rest, anchor, size) for i, s in enumerate(lines))


def _box(x, y, w, h, lines, cls="box", rx=6, size=10.5, lh=13, bold_first=False):
    """A box with centred lines of text."""
    y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + 4
    first = "b" if bold_first or cls == "boxa" else ""
    return _rect(x, y, w, h, cls, rx) + _lines(x + w / 2, y0, lines, size, lh, first, "")


class _T:
    """A hand-placed tree node: centre x, top y, width, height."""

    def __init__(self, cx, y, w, h, lines, leaf=False, cls="box"):
        self.cx, self.y, self.w, self.h, self.lines, self.leaf, self.cls = cx, y, w, h, lines, leaf, cls

    def draw(self):
        return _box(self.cx - self.w / 2, self.y, self.w, self.h, self.lines, self.cls, 16 if self.leaf else 6)


def _edge(p: _T, c: _T, label: str) -> str:
    """Orthogonal edge parent -> child; the label sits beside the child's vertical drop, never on a line."""
    y1 = p.y + p.h
    mid = (y1 + c.y) / 2
    if abs(p.cx - c.cx) < 1:
        d = f"M{p.cx:.1f} {y1} L{c.cx:.1f} {c.y}"
        ly = (mid + c.y) / 2 + 4
    else:
        d = f"M{p.cx:.1f} {y1} L{p.cx:.1f} {mid} L{c.cx:.1f} {mid} L{c.cx:.1f} {c.y}"
        ly = (mid + c.y) / 2 + 4
    lab = text(c.cx + 6, ly, label, "a t b", "start", 10.5) if label else ""
    return _arrow(d) + lab


def _tree_svg(title, header, nodes, edges, H, W=720):
    out = [text(16, 18, header, "m t", "start")]
    out += [_edge(p, c, lab) for p, c, lab in edges]
    out += [n.draw() for n in nodes]
    return svg(W, H, title, "".join(out))


# ---------------------------------------------------------------- px4-control
def tune_order_flow() -> str:
    W, H = 720, 430
    out = [text(16, 18, "Порядок тюнинга PX4: фильтры — до всего; autotune заменяет ручной rate и attitude P", "m t", "start")]
    out.append(_box(130, 32, 460, 46, ["1. Фильтры по спектру (Flight Review)",
                                       "умолч.: IMU_GYRO_CUTOFF 40 Гц · IMU_DGYRO_CUTOFF 20 Гц · notch"], "boxa"))
    # split to the two paths
    out.append(_path("M360 78 L360 100 L170 100"))
    out.append(_arrow("M170 100 L170 122"))
    out.append(_arrow("M360 100 L550 100 L550 122"))
    out.append(_box(20, 122, 300, 86, ["2а. Autotune — большинство рам", "MC_AT_EN = 1 + перезагрузка,",
                                       "QGC → PID Tuning → Autotune;", "пишет MC_*RATE_P/I/D, K = 1",
                                       "и MC_ROLL_P / PITCH_P / YAW_P"], "boxa"))
    out.append(_box(400, 122, 300, 86, ["2б. Вручную — нестандартная рама,", "большой аппарат, autotune не справился:",
                                        "rate K → D → I, затем attitude P;", "перелёт → K↓ или D↑, медленно → K↑,",
                                        "дрейф → I↑"]))
    # merge into the check
    out.append(_path("M550 208 L550 226 L360 226"))
    out.append(_arrow("M170 208 L170 226 L360 226 L360 244"))
    out.append(_box(160, 244, 400, 44, ["3. Проверка step response (Flight Review)", "перелёт ≤ 10 %, D без шума"]))
    # step 4 of the practice: manual K/D correction goes back to the manual box
    out.append(_arrow("M560 266 L670 266 L670 208", extra=' style="stroke-dasharray:5 4"'))
    out.append(text(568, 244, "если нужно:", "m t", "start", 10))
    out.append(text(568, 258, "K/D ±10–20 %", "m t", "start", 10))
    out.append(_arrow("M360 288 L360 310"))
    out.append(_box(110, 310, 500, 44, ["4. Скорость (умолч.): MPC_XY_VEL_P_ACC 1.8 · MPC_Z_VEL_P_ACC 4.0",
                                        "качает в Position — сначала здесь, а не MPC_XY_P"]))
    out.append(_arrow("M360 354 L360 376"))
    out.append(_box(110, 376, 500, 40, ["5. Позиция (умолч.): MPC_XY_P 0.95 · MPC_Z_P 1.0 (1/с)"]))
    return svg(W, H, "Порядок тюнинга PX4: autotune или вручную", "".join(out))


# ---------------------------------------------------------------- px4-architecture
def roll_osc_tree() -> str:
    y0, y1, y2, y3 = 32, 116, 200, 284
    root = _T(360, y0, 330, 42, ["vehicle_angular_velocity идёт с частотой",
                                 "≈ IMU_GYRO_RATEMAX (800 Гц у мультиротора)?"], cls="boxa")
    cpu = _T(625, y1, 160, 42, ["перегрузка CPU:", "top / listener cpuload"], leaf=True)
    q2 = _T(360, y1, 250, 42, ["Колебания видны и в", "vehicle_rates_setpoint?"])
    q3 = _T(182, y2, 230, 42, ["Пик моторов в спектре", "Flight Review — в полосе?"])
    q4 = _T(537, y2, 230, 42, ["uorb top -1: датчик", "публикует с пропусками?"])
    l1 = _T(95, y3, 170, 54, ["IMU_GYRO_CUTOFF /", "IMU_GYRO_NF0_FRQ /", "IMU_GYRO_DNF_EN"], leaf=True)
    l2 = _T(272, y3, 160, 54, ["rate P / D", "(px4-control)"], leaf=True)
    l3 = _T(450, y3, 160, 54, ["инновации EKF2", "по этому датчику"], leaf=True)
    l4 = _T(625, y3, 160, 54, ["attitude P /", "контур позиции"], leaf=True)
    edges = [(root, q2, "да"), (root, cpu, "нет"), (q2, q3, "нет, только в факте"), (q2, q4, "да"),
             (q3, l1, "да"), (q3, l2, "нет"), (q4, l3, "да"), (q4, l4, "нет")]
    return _tree_svg("Разбор «качает по roll»: топик → модуль → параметр",
                     "Разбор «качает по roll»: на каждом шаге — один вопрос к топику, ответ ведёт к модулю и параметру",
                     [root, cpu, q2, q3, q4, l1, l2, l3, l4], edges, y3 + 64)


# ---------------------------------------------------------------- px4-intro (1)
def mode_ladder() -> str:
    W = 720
    est = ["гироскоп", "ориентация", "высота", "позиция"]
    rows = [("Position", "", 4, ["держит точку и высоту", "пилот: стик — скорость"]),
            ("Altitude", "", 3, ["держит высоту", "пилот: горизонталь, снос"]),
            ("Stabilized", "", 2, ["держит угол", "пилот: газ и высота"]),
            ("Acro", "", 1, ["держит угл. скорость", "пилот: угол и высота"])]
    cx0, cw, top, rh, gap = 136, 78, 52, 48, 16
    out = [text(16, 18, "Режимы с пилотом: каждый следующий требует ещё одну оценку (commander, mode_requirements.cpp)",
                "m t", "start")]
    for k, e in enumerate(est):
        out.append(text(cx0 + k * cw + cw / 2, top - 10, e, "m t", "middle", 10.5))
    out.append(text(462, top - 10, "держит автопилот / пилот", "m t", "start", 10.5))
    for i, (name, sub, n, hold) in enumerate(rows):
        y = top + i * (rh + gap)
        out.append(_rect(14, y, 606, rh, "box", 6))
        out.append(text(24, y + (20 if sub else 29), name, "b", "start", 12))
        if sub:
            out.append(text(24, y + 36, sub, "m t", "start", 10.5))
        for k in range(4):
            on = k < n
            st = "" if on else ' style="opacity:0.35"'
            out.append(_rect(cx0 + k * cw + 3, y + 9, cw - 6, rh - 18, "boxa" if on else "box", 4, st))
            out.append(text(cx0 + k * cw + cw / 2, y + rh / 2 + 4, "нужна" if on else "—", "a t b" if on else "m t",
                            "middle", 10.5))
        out.append(text(462, y + 20, hold[0], "", "start", 10.5))
        out.append(text(462, y + 36, hold[1], "m t", "start", 10.5))
    # 1.17 fallback: Position -> Altitude -> Stabilized
    for i, lab in ((0, ["нет", "позиции"]), (1, ["нет", "высоты"])):
        ya = top + i * (rh + gap) + rh / 2
        yb = ya + rh + gap
        out.append(_arrow(f"M620 {ya:.1f} L640 {ya:.1f} L640 {yb:.1f} L622 {yb:.1f}", True))
        out.append(text(647, (ya + yb) / 2 - 2, lab[0], "a t", "start", 10.5))
        out.append(text(647, (ya + yb) / 2 + 12, lab[1], "a t", "start", 10.5))
    out.append(text(632, top - 10, "откат с 1.17", "a t", "start", 10.5))
    H = top + 4 * (rh + gap) - gap + 10
    return svg(W, H, "Режимы мультиротора PX4 и нужные им оценки", "".join(out))


# ---------------------------------------------------------------- px4-intro (2)
def upgrade_param_tree() -> str:
    y0, y1, y2 = 32, 116, 200
    root = _T(360, y0, 300, 42, ["Параметр на полётнике (1.15 / 1.16):", "имя есть в 1.17?"], cls="boxa")
    qa = _T(185, y1, 240, 40, ["Имя есть в", "param_translation.cpp?"])
    qb = _T(535, y1, 240, 40, ["Значение отличалось", "от умолчания?"])
    la = _T(97, y2, 165, 54, ["переведён сам:", "SDLOG_MODE −1 →", "SDLOG_BACKEND 0"], leaf=True)
    lb = _T(272, y2, 165, 54, ["потерян — руками:", "MPC_HOLD_DZ →", "MAN_DEADZONE"], leaf=True)
    lc = _T(447, y2, 165, 54, ["сохранён; смысл", "значения сверить:", "COM_ARM_WO_GPS"], leaf=True)
    ld = _T(622, y2, 165, 54, ["молча умолчание 1.17:", "MC_ROLL_P 6.5 → 4.0", "IMU_DGYRO_CUTOFF 30→20"],
            leaf=True, cls="boxa")
    edges = [(root, qa, "нет"), (root, qb, "да"), (qa, la, "да"), (qa, lb, "нет"), (qb, lc, "да"), (qb, ld, "нет")]
    return _tree_svg("Что станет с параметром после обновления до PX4 1.17",
                     "Обновление до 1.17: хранятся только значения, отличные от умолчания, а переводится лишь пара имён",
                     [root, qa, qb, la, lb, lc, ld], edges, y2 + 66)


# ---------------------------------------------------------------- px4-ros2
def dds_topic_naming() -> str:
    W = 720
    lx, lw, rx, rw = 170, 260, 446, 260
    top, bh, step = 58, 40, 60
    stages = [(["файл .msg"], ["msg/versioned/VehicleLocalPosition.msg", "MESSAGE_VERSION = 1"],
               ["msg/versioned/TrajectorySetpoint.msg", "MESSAGE_VERSION = 0"]),
              (["dds_topics.yaml", "нет строки — нет топика"], ["/fmu/out/vehicle_local_position"],
               ["/fmu/in/trajectory_setpoint"]),
              (["uxrce_dds_client", "(на полётнике)"], ["версия 1 > 0 → суффикс _v1"], ["версия 0 → без суффикса"]),
              (["MicroXRCEAgent", "(companion / ПК)"], None, None),
              (["имя в ROS 2"], ["/fmu/out/vehicle_local_position_v1"], ["/fmu/in/trajectory_setpoint"]),
              (["ваш узел", "px4_msgs = версия PX4"], ["подписка на имя с _v1", "(до 1.17 — без суффикса)"],
               ["публикует TrajectorySetpoint"])]
    out = [text(16, 18, "Имя топика в ROS 2 = строка из dds_topics.yaml + _vN, если MESSAGE_VERSION = N > 0", "m t", "start")]
    out.append(text(lx + lw / 2, 44, "из PX4 в ROS 2 ↓", "a t b", "middle", 11))
    out.append(text(rx + rw / 2, 44, "из ROS 2 в PX4 ↑", "a t b", "middle", 11))
    for i, (lab, left, right) in enumerate(stages):
        y = top + i * step
        out.append(text(16, y + (17 if len(lab) > 1 else 24), lab[0], "b", "start", 11))
        if len(lab) > 1:
            out.append(text(16, y + 32, lab[1], "m t", "start", 10))
        if left is None:
            out.append(_box(lx, y, rx + rw - lx, bh, ["udp4 -p 8888 (SITL, Wi-Fi) или serial -b 921600 (TELEM2)"]))
        else:
            acc = "boxa" if i == 4 else "box"
            out.append(_box(lx, y, lw, bh, left, acc))
            out.append(_box(rx, y, rw, bh, right, acc))
        if i < len(stages) - 1:
            out.append(_arrow(f"M{lx + lw / 2} {y + bh} L{lx + lw / 2} {y + step}", True))
            out.append(_arrow(f"M{rx + rw / 2} {y + step} L{rx + rw / 2} {y + bh}", True))
    H = top + (len(stages) - 1) * step + bh + 14
    return svg(W, H, "Как топик uORB получает имя в ROS 2", "".join(out))


# ---------------------------------------------------------------- px4-companion-jetson
def jetson_latency_budget() -> str:
    W = 720
    cam, yolo, trk, dds = 16, 12, 2, 2
    base = cam + yolo + trk + dds
    assert base == 32
    usb, wifi = (40, 80), (20, 50)
    r_usb = (base + usb[0], base + usb[1])
    r_all = (base + usb[0] + wifi[0], base + usb[1] + wifi[1])
    assert r_usb == (72, 112) and r_all == (92, 162)
    assert 2.8 < r_all[0] / base < 3 and 5 < r_all[1] / base < 5.1        # «в 3–5 раз»
    out = [text(16, 18, f"Бюджет задержки «камера → команда»: {base} мс на проводе против до {r_all[1]} мс с USB и Wi-Fi",
                "m t", "start")]
    # panel 1: breakdown of the wired chain, its own scale 0–32 ms
    x0, x1 = 170, 700
    k1 = (x1 - x0) / base
    y = 52
    out.append(text(16, y - 10, f"Разбор {base} мс (масштаб 0–{base} мс)", "m t", "start", 10.5))
    segs = [(cam, ["камера CSI 60 к/с", f"≤ {cam} мс до кадра"]), (yolo, ["TensorRT YOLO-nano", f"FP16 ~{yolo} мс"]),
            (trk, None), (dds, None)]
    x = x0
    for v, lab in segs:
        w = v * k1
        out.append(_rect(x, y, w, 38, "boxa" if lab else "box", 3))
        if lab:
            out.append(_lines(x + w / 2, y + 16, lab, 10.5, 13, "b", ""))
        x += w
    xt, xd = x0 + (cam + yolo + trk / 2) * k1, x0 + (cam + yolo + trk + dds / 2) * k1
    out.append(f'<line class="lnm" x1="{xt:.1f}" y1="{y + 38}" x2="{xt:.1f}" y2="{y + 50}"/>')
    out.append(f'<line class="lnm" x1="{xd:.1f}" y1="{y + 38}" x2="{xd:.1f}" y2="{y + 66}"/>')
    out.append(text(xt + 4, y + 58, f"трекер {trk} мс", "m t", "end", 10.5))
    out.append(text(xd + 4, y + 76, f"DDS по UART 921600 {dds} мс", "m t", "end", 10.5))
    out.append(text(16, y + 24, "CSI + UART", "b", "start", 11))
    # panel 2: the three paths on 0–200 ms
    top2 = 168
    tmax = 200
    k2 = (x1 - x0) / tmax
    X = lambda t: x0 + t * k2
    out.append(text(16, top2 - 10, "Три пути (масштаб 0–200 мс; пунктир — разброс по модулю)", "m t", "start", 10.5))
    rows = [("CSI + провод", [(0, base, "boxa", f"{base}")], None, f"= {base} мс (~35)"),
            ("USB-камера MJPEG", [(0, base, "boxa", f"{base}"), (base, base + usb[0], "box", "USB +40…80")],
             (r_usb[0], r_usb[1]), f"{r_usb[0]}–{r_usb[1]} мс"),
            ("USB + Wi-Fi-мост", [(0, base, "boxa", f"{base}"), (base, base + usb[0], "box", "USB"),
                                  (base + usb[0], r_all[0], "box", "Wi-Fi")], (r_all[0], r_all[1]),
             f"{r_all[0]}–{r_all[1]} мс")]
    rh, rs = 30, 44
    for i, (name, parts, rng, total) in enumerate(rows):
        yy = top2 + i * rs
        out.append(text(16, yy + 19, name, "b" if i == 0 else "", "start", 11))
        for t0, t1, cls, lab in parts:
            out.append(_rect(X(t0), yy, X(t1) - X(t0), rh, cls, 3))
            if lab:
                out.append(text((X(t0) + X(t1)) / 2, yy + 19, lab, "b" if cls == "boxa" else "t", "middle", 10.5))
        end = base
        if rng:
            out.append(f'<rect x="{X(rng[0]):.1f}" y="{yy}" width="{X(rng[1]) - X(rng[0]):.1f}" height="{rh}" rx="3" '
                       f'fill="{WARN}" fill-opacity="0.18" stroke="{WARN}" stroke-dasharray="4 3"/>')
            end = rng[1]
        out.append(text(X(end) + 6, yy + 19, total, "w b" if rng else "a b", "start", 11))
    ya = top2 + 2 * rs + rh + 12
    out.append(f'<line x1="{x0}" y1="{ya}" x2="{x1}" y2="{ya}" stroke="{MUTED}" stroke-width="1"/>')
    for t in range(0, tmax + 1, 50):
        out.append(f'<line x1="{X(t):.1f}" y1="{ya}" x2="{X(t):.1f}" y2="{ya + 5}" stroke="{MUTED}" stroke-width="1"/>')
        out.append(text(X(t), ya + 18, f"{t} мс", "m t", "middle", 10.5))
    return svg(W, ya + 28, "Бюджет задержки Jetson → PX4", "".join(out))


# ---------------------------------------------------------------- ros2-ardupilot
def ap_dds_guided_seq() -> str:
    steps = [(1, 0, "/ap/status, /ap/pose/filtered (ENU)", False, True),
             (0, 1, "/ap/mode_switch {mode: 4} → GUIDED"),
             (1, 0, "ответ: status, curr_mode = 4", False, True),
             (0, 1, "/ap/arm_motors {arm: true}"),
             (0, 1, "/ap/experimental/takeoff {alt}"),
             (0, 1, "/ap/cmd_vel поток, frame_id map (ENU)", True),
             (0, 0, "поток cmd_vel прервался"),
             (1, 1, "GUID_TIMEOUT = 3 с → остановка"),
             (0, 1, "/ap/mode_switch {mode: 9} → LAND")]
    notes = [(0, "BEST_EFFORT; status — RELIABLE"), (3, "только после pre-arm проверок"),
             (4, "иначе на земле уставки игнорируются"), (5, "base_link — оси корпуса, не мира"),
             (7, "тот же принцип, что Offboard у PX4")]
    return sequence("AP_DDS: порядок GUIDED → arm → takeoff → cmd_vel → LAND (ArduCopter 4.7)",
                    ["ROS 2 узел", "AP_DDS (Copter)"], steps, notes=notes, step_h=32)


# ---------------------------------------------------------------- ros2-nav
def nav_brake_speed() -> str:
    a, tr, rng, margin = 3.0, 0.3, 8.0, 2.0
    vmax = lambda d, t: -a * t + math.sqrt((a * t) ** 2 + 2 * a * d)
    d_ok = rng - margin
    v_ok, v_not, v_nomargin = vmax(d_ok, tr), vmax(d_ok, 0), vmax(rng, 0)
    assert round(v_ok, 1) == 5.2 and round(v_not, 1) == 6.0 and round(v_nomargin, 1) == 6.9
    assert abs(v_ok * tr + v_ok ** 2 / (2 * a) - d_ok) < 1e-9
    ds = [0.05 * k for k in range(201)]
    xa = Axis("надёжная дальность минус запас d, м", 0, 10, ticks=list(range(0, 11)))
    ya = Axis("предельная скорость v, м/с", 0, 8, ticks=list(range(0, 9)))
    px = lambda x, y: (_Scale(xa, 64, 696)(x), _Scale(ya, 312, 36)(y))
    p_ok, p_not, p_nm = px(d_ok, v_ok), px(d_ok, v_not), px(rng, v_nomargin)
    return chart(
        "Тормозной путь: v·t_r + v²/(2a) ≤ d, a = 3 м/с²",
        [dict(name="t_r = 0: v = √(2·a·d)", xs=ds, ys=[vmax(d, 0) for d in ds], cls="w", dash=True, label_at=4.0,
              label_dy=-8),
         dict(name="t_r = 0.3 с", xs=ds, ys=[vmax(d, tr) for d in ds], cls="a", label_at=10, label_dy=24),
         dict(name="", xs=[d_ok], ys=[v_ok], cls="a", dots=True, w=0),
         dict(name="", xs=[d_ok, rng], ys=[v_not, v_nomargin], cls="d", dots=True, w=0)],
        xa, ya,
        marks=[(d_ok, "d = 8 − 2 = 6 м", "ink", 250), (rng, "8 м — без запаса", "m", 250)],
        notes=[(p_ok[0] + 8, p_ok[1] + 16, f"{v_ok:.1f} м/с — верно", "a"),
               (p_not[0] - 6 - 25 * 6.6, p_not[1] - 8, f"{v_not:.1f} м/с — забыта задержка", "d"),
               (p_nm[0] - 6 - 16 * 6.6, p_nm[1] - 10, f"{v_nomargin:.1f} — без запаса", "d")])


# ---------------------------------------------------------------- ros2-from-ros1
def sync_call_deadlock() -> str:
    W = 720
    x0, x1, tmax = 180, 700, 220
    X = lambda t: x0 + (x1 - x0) * t / tmax
    ticks = [0, 50, 100, 150, 200]                      # create_timer(0.05, tick)
    out = []

    def lanes(y, title_, cls):
        out.append(text(16, y, title_, cls, "start", 11.5))
        out.append(text(16, y + 34, "executor", "b", "start", 11))
        out.append(text(16, y + 48, "(один поток)", "m t", "start", 10.5))
        out.append(text(16, y + 96, "узел-сервер /s", "", "start", 11))
        for yy in (y + 50, y + 104):
            out.append(f'<line class="lnm" x1="{x0}" y1="{yy}" x2="{x1}" y2="{yy}"/>')

    # panel A: synchronous call inside the timer callback
    ya = 30
    lanes(ya, "cli.call(req) внутри колбэка таймера: синхронный вызов", "d b")
    ey, sy = ya + 22, ya + 76                            # lane tops: executor, server
    out.append(f'<rect class="box" x="{X(0):.1f}" y="{ey}" width="{X(tmax) - X(0):.1f}" height="26" rx="3" '
               f'style="stroke:{DANGER}"/>')
    out.append(text(X(62), ey + 17, "tick(): cli.call(req) ждёт ответ — и не возвращается", "d", "start", 10.5))
    out.append(_arrow(f"M{X(6):.1f} {ey + 26} L{X(16):.1f} {sy}"))
    out.append(text(X(11) - 6, (ey + 26 + sy) / 2 + 4, "запрос", "m t", "end", 10.5))
    out.append(_rect(X(16), sy, X(48) - X(16), 26, "box", 3))
    out.append(text(X(32), sy + 17, "обработка", "", "middle", 10.5))
    out.append(_arrow(f"M{X(48):.1f} {sy} L{X(56):.1f} {ey + 26}", extra=f' style="stroke:{DANGER}"'))
    out.append(text(X(60), sy + 17, "ответ ждёт в очереди: доставить его должен тот же executor", "m t", "start", 10.5))
    for t in ticks[1:]:
        cx = X(t)
        out.append(text(cx, ey - 4, "×", "d b", "middle", 12))
    out.append(text(X(0), ey - 4, "тик 0", "m t", "start", 10.5))
    out.append(text(X(54), ey - 4, "тик пропущен", "d t", "start", 10.5))
    # panel B: call_async
    yb = 172
    lanes(yb, "rclpy: cli.call_async(req) — колбэк возвращается сразу", "a b")
    ey, sy = yb + 22, yb + 76
    for t in ticks:
        out.append(_rect(X(t), ey, X(t + 9) - X(t), 26, "boxa", 3))
    out.append(text(X(10) + 4, ey - 4, "tick() каждые 50 мс: уставки идут", "a t", "start", 10.5))
    out.append(_arrow(f"M{X(6):.1f} {ey + 26} L{X(16):.1f} {sy}"))
    out.append(text(X(11) - 6, (ey + 26 + sy) / 2 + 4, "запрос", "m t", "end", 10.5))
    out.append(_rect(X(16), sy, X(58) - X(16), 26, "box", 3))
    out.append(text(X(37), sy + 17, "обработка", "", "middle", 10.5))
    out.append(_arrow(f"M{X(58):.1f} {sy} L{X(66):.1f} {ey + 26}", True))
    out.append(_rect(X(66), ey, X(80) - X(66), 26, "box", 3))
    out.append(text(X(82), ey + 44, "done-колбэк future: ответ обработан между тиками", "a t", "start", 10.5))
    # time axis
    yax = yb + 122
    out.append(f'<line x1="{x0}" y1="{yax}" x2="{x1}" y2="{yax}" stroke="{MUTED}" stroke-width="1"/>')
    for t in ticks:
        out.append(f'<line x1="{X(t):.1f}" y1="{yax}" x2="{X(t):.1f}" y2="{yax + 5}" stroke="{MUTED}" stroke-width="1"/>')
        out.append(text(X(t), yax + 18, f"{t} мс", "m t", "middle", 10.5))
    out.append(text(16, yax + 18, "таймер 0.05 с", "m t", "start", 10.5))
    return svg(W, yax + 28, "Синхронный вызов сервиса в колбэке блокирует узел", "".join(out))


def build(D: dict) -> None:
    D["px4-tune-order-flow"] = tune_order_flow()
    D["px4-roll-osc-tree"] = roll_osc_tree()
    D["px4-mode-ladder"] = mode_ladder()
    D["px4-upgrade-param-tree"] = upgrade_param_tree()
    D["px4-dds-topic-naming"] = dds_topic_naming()
    D["jetson-latency-budget"] = jetson_latency_budget()
    D["ap-dds-guided-seq"] = ap_dds_guided_seq()
    D["chart-nav-brake-speed"] = nav_brake_speed()
    D["ros2-sync-call-deadlock"] = sync_call_deadlock()
