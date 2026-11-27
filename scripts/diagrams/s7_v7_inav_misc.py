"""Visual pass (stage 7), batch v7_inav_misc: one new diagram per INAV / link / estimation / payload module.

inav-upgrade-8-to-9        inav-intro — the module's 7-step upgrade 8.0 -> 9.1 as a flow: diff all to a file, Full chip
                           erase, then steps 3–4 either by hand (paste, fix «### ERROR: Invalid name», defaults, paste in
                           two parts with several profiles) or by Configurator 9.1 (restore backup + migration window 8 -> 9,
                           compare with your diff all); what is not carried over (new 9.x defaults), Outputs check with
                           props off, revert nav_mc_pos_z_p / nav_mc_vel_z_p raised above the defaults 50 / 100.
inav-gps-loss-modes        inav-gps — the navigation.c 9.1.0 rule from «Потеря GPS в полёте»: position estimate gone
                           (no dead reckoning left) -> RTH / WP wait nav_position_timeout (default 5 s, 1–10) and go to
                           emergency landing; 0 -> wait forever, but a failsafe RTH started without position lands at once;
                           CRUISE / COURSE HOLD switch off; emergency landing descends at nav_emerg_landing_speed
                           (default 500 cm/s) while the altitude estimate lives, otherwise fixed failsafe_throttle.
inav-autotune-tree         inav-wing — what fixed-wing AUTOTUNE changes (pid_autotune.c 9.1.0 as the module states it):
                           gate fw_autotune_min_stick (default 50 %, first change after 5 s = 250 × 20 ms); MANUAL — not
                           active; ANGLE — fw_ff_* only, rates never; ACRO / HORIZON — fw_autotune_rate_adjustment
                           AUTO (default) up and down, LIMIT only down, FIXED none (rate found at
                           fw_autotune_max_rate_deflection, default 90 %); P and I never; save after disarm.
inav-wp-user-action-chain  inav-missions — the module's worked user-action example as a chain: p3 = 2 on waypoint 2 ->
                           logic 0 (mission operand 6) -> logic 1 (operation 38, channel 12 = 2000 us) -> aux USER1 on
                           channel 12, 1700–2100 -> pinio_box1 = 47 -> PINIO1; below, which leg is lit: operand 6 (from
                           point 2) -> leg 2 -> 3, operand 10 (to point 2) -> leg 1 -> 2.
inav-logic-line-fields     inav-ipf — the practice step-2 pair of `logic` lines field by field (format, operation 2 =
                           GREATER_THAN, flight operand 1 = home distance m, operation 25 = SET_VTX_POWER_LEVEL), the
                           activator of rule 1 pointing at rule 0, and the module's 3-step build procedure above.
esc-pwm-class-map          f-esc-firmware — the start PWM frequency per class from «Стартовое значение по классу» on the
                           Bluejay steps 24 / 48 / 96 kHz, with the DJI O3/O4 + Gyroflow constraint (>= 48 kHz) shown as a
                           zone that moves the four 24-kHz classes up; below, step 2 of the procedure with the module's
                           7" check N = 10·24000/50000 = 4.8 (computed here).
vtx-power-index-map        link-vtx — vtx_power is a level index: the same `set vtx_power = 3` gives 400 mW with the module's
                           vtxtable (14/20/26 dBm), 500 mW with the exercise table (14/23/27/29 dBm), 200 mW on the INAV
                           Tramp 600 mW VTX (25/100/200/400/600); level 4 does not exist in the first table; with
                           vtx_low_power_disarm = ON level 1 on the ground, not in failsafe. dBm -> mW checked here.
goggles-vtx-links          link-digital-video — the goggles compatibility table drawn as links goggles -> video systems
                           (native / via module or external receiver / after update or on compatible firmware / not checked):
                           the DJI cluster is closed; HDZero and Walksnail reach analog (natively only HDZero Goggle 2 /
                           BoxPro, the rest via module or receiver), each other only via an external receiver.
dronecan-dna-flow          el-dronecan — dynamic node allocation as a flow: a new node asks with its unique ID; known ID ->
                           the same number, new -> a free number <= 125 (126, 127 reserved), remembered; the failure path
                           (moved / copied node, two nodes with one number -> «Duplicate Node» pre-arm) and the fix
                           (CAN_D1_UC_OPTION bit 0 -> «UC DNA database reset», or a fixed ID); PX4 serves DNA only with
                           UAVCAN_ENABLE 2/3 (default 0).
inav-surface-limits        est-alt-sources — INAV SURFACE (id 33): appears only on a multirotor with baro and rangefinder;
                           throttle maps 0…100 % to 0…nav_max_terrain_follow_alt (navigation_multicopter.c); readings above
                           inav_max_surface_altitude (default 200 cm) are rejected -> AGL unreliable -> descent; the module's
                           pair 100 at 200 (default) and 250 at 200 (wrong) on a linear 0–300 cm scale; the top
                           (250 − 200)/250 = 20 % of throttle travel lands above the limit (computed here).
gps-loss-ladder            nav-resilience — what each firmware does as navigation degrades, from «Что делает прошивка сама»:
                           ArduPilot (EK3_GLITCH_RAD 25 m reset, EKF failsafe FS_EKF_ACTION 0–3), PX4 1.18 (COM_POS_LOW_ACT
                           in Mission/Hold, Position -> Altitude -> Stabilized), INAV (nav_position_timeout 5 s ->
                           emergency landing 5 m/s -> failsafe_throttle); bottom — the module's choice by place.
gimbal-control-paths       payload-gimbal — the command path per firmware: ArduPilot clients -> mount manager
                           (MNT1_DEFLT_MODE default 3 RC, MNT1_RC_RATE) -> MNT1_TYPE -> servo outputs / UART / MAVLink 154 /
                           DroneCAN; PX4 clients (MNT_MAN_* and RC_MAP_AUXn both) -> gimbal module (MNT_MODE_IN default −1 =
                           not running) -> MNT_MODE_OUT 0 AUX 420/421/422 or 2 Gimbal v2 («compid not found» without
                           GIMBAL_DEVICE_INFORMATION).
"""
from __future__ import annotations

import math

from svg import ACCENT, DANGER, INK, MUTED, WARN, svg, text


# ---------------------------------------------------------------- helpers (same as s7_v6_ros_px4.py)
def _rect(x, y, w, h, cls="box", rx=6, extra=""):
    return f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"{extra}/>'


def _arrow(d, acc=False, extra=""):
    return f'<path class="{"lna" if acc else "ln"}" d="{d}" marker-end="url(#{"ara" if acc else "ar"})"{extra}/>'


def _path(d, cls="ln", extra=""):
    return f'<path class="{cls}" d="{d}"{extra}/>'


def _lines(cx, y, lines, size=10.5, lh=13, cls_first="", cls_rest="", anchor="middle"):
    return "".join(text(cx, y + i * lh, s, cls_first if i == 0 else cls_rest, anchor, size) for i, s in enumerate(lines))


def _box(x, y, w, h, lines, cls="box", rx=6, size=10.5, lh=13, bold_first=False, anchor="middle"):
    """A box with lines of text, centred (or left-aligned with anchor='start')."""
    y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + 4
    first = "b" if bold_first or cls == "boxa" else ""
    tx = x + w / 2 if anchor == "middle" else x + 10
    return _rect(x, y, w, h, cls, rx) + _lines(tx, y0, lines, size, lh, first, "", anchor)


class _T:
    """A hand-placed tree node: centre x, top y, width, height."""

    def __init__(self, cx, y, w, h, lines, leaf=False, cls="box"):
        self.cx, self.y, self.w, self.h, self.lines, self.leaf, self.cls = cx, y, w, h, lines, leaf, cls

    def draw(self):
        return _box(self.cx - self.w / 2, self.y, self.w, self.h, self.lines, self.cls, 16 if self.leaf else 6)


def _edge(p: _T, c: _T, label: str, acc=False) -> str:
    """Orthogonal edge parent -> child; the label sits beside the child's vertical drop, never on a line."""
    y1 = p.y + p.h
    mid = (y1 + c.y) / 2
    if abs(p.cx - c.cx) < 1:
        d = f"M{p.cx:.1f} {y1} L{c.cx:.1f} {c.y}"
    else:
        d = f"M{p.cx:.1f} {y1} L{p.cx:.1f} {mid} L{c.cx:.1f} {mid} L{c.cx:.1f} {c.y}"
    ly = (mid + c.y) / 2 + 4
    lab = text(c.cx + 6, ly, label, "a t b", "start", 10.5) if label else ""
    return _arrow(d, acc) + lab


def _close(out: list[str], W: int, H: int, title: str) -> str:
    return svg(W, H, title, "".join(out))


# ---------------------------------------------------------------- inav-intro
def upgrade_flow() -> str:
    W = 720
    out = [text(16, 18, "Обновление INAV 8.0 → 9.1 по шагам release notes 9.0.0 и 9.1.0", "m t", "start")]
    out.append(_box(150, 30, 420, 40, ["1. Configurator 9.1; на прошивке 8.0 — diff all в файл",
                                        "в имени файла — версия и дата"]))
    out.append(_arrow("M360 70 L360 88"))
    out.append(_box(150, 88, 420, 40, ["2. Прошить 9.1 с Full chip erase",
                                        "обязательно при переходе между мажорными версиями"], "boxa"))
    # split: by hand (left) or Configurator 9.1 (right)
    out.append(_path("M360 128 L360 142 L180 142"))
    out.append(_arrow("M180 142 L180 166"))
    out.append(_arrow("M360 142 L545 142 L545 166"))
    out.append(text(186, 160, "вручную", "a t b", "start", 10.5))
    out.append(text(551, 160, "или сам Configurator", "a t b", "start", 10.5))
    out.append(_box(14, 166, 332, 56, ["3. Вставить старый diff в CLI;",
                                        "красные «### ERROR: Invalid name» выписать",
                                        "и исправить в копии по таблице переименований"]))
    out.append(_arrow("M180 222 L180 236"))
    out.append(_box(14, 236, 332, 70, ["4. defaults → после перезагрузки вставить",
                                        "исправленный diff → save; профилей несколько —",
                                        "сначала до конца # master и save,",
                                        "потом с # control_profile 1"]))
    out.append(_box(380, 166, 330, 140, ["Шаги 3–4 в Configurator 9.1:",
                                          "после прошивки с Full chip erase",
                                          "он предлагает восстановить бэкап",
                                          "и показывает окно миграции 8 → 9",
                                          "(переименования и предупреждения);",
                                          "результат всё равно сравнить",
                                          "своим diff all"]))
    # merge
    out.append(_path("M545 306 L545 322 L360 322"))
    out.append(_arrow("M180 306 L180 322 L360 322 L360 336"))
    out.append(_box(70, 336, 580, 40, ["5. Само не переносится: что не трогал — получает умолчания 9.x:",
                                        "созвездия и частота GPS, inav_w_z_*, nav_fw_pos_z_ff; новый шрифт OSD"]))
    out.append(_arrow("M360 376 L360 390"))
    out.append(_box(70, 390, 580, 40, ["6. Пропы сняты: выходы моторов и серв на вкладке Outputs,",
                                        "затем наземная проверка оценщика (шаг 3б)"]))
    out.append(_arrow("M360 430 L360 444"))
    out.append(_box(70, 444, 580, 40, ["7. nav_mc_pos_z_p / nav_mc_vel_z_p подняты выше умолчаний 50 / 100?",
                                        "вернуть или настроить заново — иначе газ колеблется в RTH, WP, CRUISE"], "boxa"))
    return _close(out, W, 494, "Обновление INAV 8.0 → 9.1")


# ---------------------------------------------------------------- inav-gps
def gps_loss_modes() -> str:
    y0, y1, y2, y3, y4 = 32, 108, 190, 282, 364
    root = _T(360, y0, 400, 42, ["Оценки позиции нет совсем (счисления", "inav_allow_dead_reckoning не осталось): какой режим?"],
              cls="boxa")
    q1 = _T(240, y1, 300, 42, ["RTH или миссия WP:", "nav_position_timeout?"])
    cr = _T(560, y1, 200, 42, ["режим выключается,", "управление — пилоту"], leaf=True)
    la = _T(120, y2, 210, 54, ["нет позиции дольше", "N с → аварийная посадка", "(emergency landing)"])
    lb = _T(370, y2, 260, 54, ["ждать без конца; RTH по", "failsafe, начатый без позиции,", "— посадка сразу на месте"])
    q2 = _T(240, y3, 300, 42, ["Аварийная посадка:", "оценка высоты есть?"], cls="boxa")
    l1 = _T(150, y4, 270, 54, ["снижение со скоростью", "nav_emerg_landing_speed (умолч.", "500 см/с) до детектора посадки"],
            leaf=True)
    l2 = _T(470, y4, 240, 54, ["снижения по скорости нет:", "фиксированный газ", "failsafe_throttle"], leaf=True)
    out = [text(16, 18, "INAV 9.1.0 (navigation.c): что делает аппарат, когда оценка позиции пропала", "m t", "start")]
    out += [_edge(root, q1, "RTH, WP"), _edge(root, cr, "CRUISE, COURSE HOLD"),
            _edge(q1, la, "N = 1–10 с (умолч. 5)"), _edge(q1, lb, "0"),
            _edge(q2, l1, "да"), _edge(q2, l2, "нет")]
    # both leaf-like boxes of row 2 feed the emergency landing
    out.append(_arrow(f"M120 {y2 + 54} L120 {y2 + 76} L230 {y2 + 76} L230 {y3}", True))
    out.append(_arrow(f"M370 {y2 + 54} L370 {y2 + 76} L250 {y2 + 76} L250 {y3}", True))
    out.append(text(376, y2 + 70, "failsafe-RTH", "a t b", "start", 10.5))
    out += [n.draw() for n in (root, q1, cr, la, lb, q2, l1, l2)]
    return _close(out, 720, y4 + 64, "Потеря позиции в INAV: реакция по режимам")


# ---------------------------------------------------------------- inav-wing
def autotune_tree() -> str:
    W = 720
    out = [text(16, 18, "Autotune крыла в INAV 9.1.0: что он меняет, зависит от режима под ним", "m t", "start")]
    out.append(_box(40, 30, 640, 40, ["Отклик пишется, только пока стик отклонён больше fw_autotune_min_stick (умолч. 50 %);",
                                       "первые изменения по оси — после 5 с таких движений (250 отсчётов по 20 мс)"]))
    y1, y2, y3 = 96, 178, 268
    root = _T(360, y1, 260, 40, ["AUTOTUNE включён поверх", "какого режима?"], cls="boxa")
    man = _T(85, y2, 150, 42, ["не работает"], leaf=True)
    ang = _T(250, y2, 160, 54, ["только fw_ff_roll,", "fw_ff_pitch, fw_ff_yaw;", "рейты — никогда"], leaf=True)
    rat = _T(530, y2, 320, 54, ["fw_autotune_rate_adjustment?", "рейт подбирается на доле хода",
                                "fw_autotune_max_rate_deflection (умолч. 90 %)"])
    auto = _T(410, y3, 120, 54, ["FF + рейты", "вверх и вниз"], leaf=True, cls="boxa")
    lim = _T(545, y3, 120, 54, ["FF + рейты", "только вниз"], leaf=True)
    fix = _T(660, y3, 90, 54, ["только FF"], leaf=True)
    out.append(_arrow(f"M360 70 L360 {y1}"))
    out += [_edge(root, man, "MANUAL"), _edge(root, ang, "ANGLE"), _edge(root, rat, "ACRO, HORIZON"),
            _edge(rat, auto, "AUTO (умолч.)"), _edge(rat, lim, "LIMIT"), _edge(rat, fix, "FIXED")]
    # every working branch ends in the same save step
    yb = y3 + 54 + 16
    out.append(_path(f"M250 {y2 + 54} L250 {yb}"))
    for cx in (410, 545, 660):
        out.append(_path(f"M{cx} {y3 + 54} L{cx} {yb}"))
    out.append(_path(f"M250 {yb} L660 {yb}"))
    out.append(_arrow(f"M360 {yb} L360 {yb + 16}"))
    out.append(_box(110, yb + 16, 500, 40, ["P и I autotune не трогает (их — вручную); результат сам не сохраняется:",
                                             "после посадки дизарм и стик-команда сохранения или save"]))
    out += [n.draw() for n in (root, man, ang, rat, auto, lim, fix)]
    return _close(out, W, yb + 66, "Autotune крыла INAV: что меняется в каждом режиме")


# ---------------------------------------------------------------- inav-missions
def user_action_chain() -> str:
    W = 720
    out = [text(16, 18, "User action в миссии INAV 9.1.0: бит p3 сам ничего не включает (пример модуля)", "m t", "start")]
    r1, bh = 34, 64
    out.append(_box(10, r1, 190, bh, ["1. Точка 2: p3 = 2", "бит 1 → user action 1", "на участке этой точки"], "boxa"))
    out.append(_arrow(f"M200 {r1 + bh / 2} L222 {r1 + bh / 2}"))
    out.append(_box(222, r1, 238, bh, ["2. logic 0 1 -1 1 7 6 0 1 0", "тип 7 (миссия), операнд 6:", "«действие 1 активно» = 1"]))
    out.append(_arrow(f"M460 {r1 + bh / 2} L482 {r1 + bh / 2}"))
    out.append(_box(482, r1, 228, bh, ["3. logic 1 1 0 38 0 12 0 2000 0", "операция 38 (Override RC):",
                                        "пока правило 0 true —", "канал 12 = 2000 мкс"]))
    r2 = r1 + bh + 28
    out.append(_arrow(f"M596 {r1 + bh} L596 {r2}"))
    out.append(_box(482, r2, 228, bh, ["4. aux: режим USER1", "на канале 12,", "диапазон 1700–2100"]))
    out.append(_arrow(f"M482 {r2 + bh / 2} L460 {r2 + bh / 2}"))
    out.append(_box(222, r2, 238, bh, ["5. pinio_box1 = 47 (USER1)", "режим USER1 включает", "свой выход PINIO1"]))
    out.append(_arrow(f"M222 {r2 + bh / 2} L200 {r2 + bh / 2}", True))
    out.append(_box(10, r2, 190, bh, ["PINIO1 включён:", "затвор, свет, сброс", "(inav-led-pinio-beeper)"], "boxa"))
    # which leg is lit: operand 6 (from-point) vs 10 (to-point)
    y = r2 + bh + 40
    out.append(text(16, y - 14, "Какой участок «помечен», решает номер операнда (logic_condition.c):", "m t", "start"))
    xs = {1: 150, 2: 380, 3: 610}
    ly6, ly10 = y + 26, y + 76
    for k in (1, 2):
        out.append(_path(f"M{xs[k]} {ly6} L{xs[k + 1]} {ly6}", "lnm"))
        out.append(_path(f"M{xs[k]} {ly10} L{xs[k + 1]} {ly10}", "lnm"))
    out.append(f'<path d="M{xs[2]} {ly6} L{xs[3]} {ly6}" stroke="{ACCENT}" stroke-width="5" fill="none"/>')
    out.append(f'<path d="M{xs[1]} {ly10} L{xs[2]} {ly10}" stroke="{ACCENT}" stroke-width="5" fill="none"/>')
    for k, x in xs.items():
        for yy in (ly6, ly10):
            out.append(f'<circle cx="{x}" cy="{yy}" r="6" fill="{ACCENT if k == 2 else INK}"/>')
        out.append(text(x, y + 6, f"точка {k}" + (" (p3 = 2)" if k == 2 else ""), "a t b" if k == 2 else "t", "middle", 10.5))
    out.append(text(16, ly6 + 4, "операнд 6", "b", "start", 10.5))
    out.append(text(16, ly10 + 4, "операнд 10", "b", "start", 10.5))
    out.append(text((xs[2] + xs[3]) / 2, ly6 + 20, "PINIO1 вкл: летит ОТ точки 2", "a t", "middle", 10.5))
    out.append(text((xs[1] + xs[2]) / 2, ly10 + 20, "PINIO1 вкл: летит К точке 2", "a t", "middle", 10.5))
    return _close(out, W, ly10 + 32, "User action миссии INAV → логика → PINIO")


# ---------------------------------------------------------------- inav-ipf
def logic_line_fields() -> str:
    W = 720
    out = [text(16, 18, "Строка logic по полям: пример «дальше 100 м — мощность VTX 3» (шаг 2 практики, 9.1.0)", "m t", "start")]
    # the three-step procedure of the module
    st = [("1. Вход", ["фраза: «если <величина>", "<сравнение> <порог>, то …»"]),
          ("2. Решение", ["тип и № операнда, порог", "в его единицах, № операции"]),
          ("3. Проверка", ["logic печатает правило обратно,", "Programming — живое значение"])]
    bx, bw = [10, 248, 486], 224
    for i, (h, ls) in enumerate(st):
        out.append(_box(bx[i], 30, bw, 52, [h] + ls, "boxa" if i == 1 else "box", bold_first=True))
        if i < 2:
            out.append(_arrow(f"M{bx[i] + bw} 56 L{bx[i + 1]} 56"))
    fields = ["правило", "вкл", "активатор", "операция", "тип A", "знач. A", "тип B", "знач. B", "флаги"]
    rows = [(["0", "1", "-1", "2", "2", "1", "0", "100", "0"],
             [["№ 0"], ["1 — да"], ["−1 —", "всегда"], ["2 — «>»", "GREATER"], ["2 —", "параметр", "полёта"],
              ["1 — до", "дома, м"], ["0 —", "число"], ["100 м"], ["0 —", "обычное"]]),
            (["1", "1", "0", "25", "0", "3", "0", "0", "0"],
             [["№ 1"], ["1 — да"], ["0 — пока", "правило 0", "true"], ["25 —", "мощность", "VTX"], ["0 —", "число"],
              ["3 —", "уровень"], ["0 —", "число"], ["0 — не", "нужно"], ["0 —", "обычное"]])]
    x0, cw = 16, (W - 32) / 9
    yh = 112
    out.append(_arrow("M360 82 L360 100"))
    for k, f in enumerate(fields):
        out.append(text(x0 + k * cw + cw / 2, yh, f, "m t", "middle", 10.5))
    ys = [122, 240]
    for r, (vals, means) in enumerate(rows):
        y = ys[r]
        for k in range(9):
            acc = (r == 1 and k == 2) or (r == 0 and k == 0)
            out.append(_rect(x0 + k * cw + 2, y, cw - 4, 30, "boxa" if acc else "box", 4))
            out.append(text(x0 + k * cw + cw / 2, y + 20, vals[k], "a b" if acc else "b", "middle", 13))
            out.append(_lines(x0 + k * cw + cw / 2, y + 46, means[k], 10.5, 13, "m t", "m t"))
    # rule 1's activator points at rule 0
    ax0, ax1 = x0 + cw / 2, x0 + 2 * cw + cw / 2
    out.append(_arrow(f"M{ax0 - 26:.1f} 152 L{ax0 - 26:.1f} 212 L{ax1:.1f} 212 L{ax1:.1f} 240", True))
    out.append(text(ax1 + 18, 208, "активатор правила 1 = номер правила 0:", "a t", "start", 10.5))
    out.append(text(ax1 + 18, 222, "мощность ставится, пока правило 0 true", "a t", "start", 10.5))
    out.append(text(16, 344, "logic 0 1 -1 2 2 1 0 100 0  ·  logic 1 1 0 25 0 3 0 0 0  ·  save", "b", "start", 11.5))
    return _close(out, W, 356, "Строка logic в INAV по полям")


# ---------------------------------------------------------------- f-esc-firmware
def esc_pwm_class_map() -> str:
    W = 720
    out = [text(16, 18, "Стартовая частота ШИМ по классу аппарата (ступени Bluejay 24 / 48 / 96 кГц)", "m t", "start")]
    cx = {24: 395, 48: 525, 96: 655}
    top, rh = 64, 40
    rows = [("Вуп 65–75 мм, 1S, 0603–0802", "96 — только при dead time в layout < 30", [48], [96], None),
            ("2–3.5\", 2–4S", "toothpick, cinewhoop", [48], [], None),
            ("5\" фристайл, 4–6S", "плавность, чистый гироскоп", [48], [], None),
            ("5\" гонка, 4–6S", "AM32 — 24 с переменной (до 2·f)", [24], [], (24, 48)),
            ("7\" long range, 6S", "или переменная 24–48; Bluejay — 48", [24], [48], (24, 48)),
            ("10\" и больше, низкий KV", "фиксированная; оценка, источника нет", [24], [], None),
            ("Самолёт, 1–2 мотора", "оценка", [24], [], None)]
    n = len(rows)
    y_end = top + n * rh
    # Gyroflow constraint zone: below 48 kHz
    out.append(f'<rect x="{cx[24] - 52}" y="{top - 6}" width="104" height="{n * rh + 6}" fill="{DANGER}" opacity="0.10"/>')
    out.append(text(cx[24], top - 24, "DJI O3/O4 + Gyroflow:", "d t b", "middle", 10.5))
    out.append(text(cx[24], top - 11, "не ниже 48 кГц", "d t b", "middle", 10.5))
    for f, x in cx.items():
        out.append(f'<line class="lnm" x1="{x}" y1="{top - 4}" x2="{x}" y2="{y_end}"/>')
        out.append(text(x, y_end + 16, f"{f} кГц", "b", "middle", 11.5))
    for i, (cls_, sub, start, alt, var) in enumerate(rows):
        y = top + i * rh + rh / 2
        out.append(text(16, y - 3, cls_, "b", "start", 11))
        out.append(text(16, y + 11, sub, "m t", "start", 10.5))
        out.append(f'<line class="lnm" x1="{cx[24] - 52}" y1="{y + rh / 2}" x2="{cx[96] + 40}" y2="{y + rh / 2}" style="opacity:0.4"/>')
        if var:
            out.append(f'<path d="M{cx[var[0]]} {y} L{cx[var[1]]} {y}" stroke="{ACCENT}" stroke-width="6" opacity="0.45" fill="none"/>')
        for f in start:
            out.append(f'<circle cx="{cx[f]}" cy="{y}" r="7" fill="{ACCENT}"/>')
            if f == 24:     # the Gyroflow constraint moves this class up
                out.append(_path(f"M{cx[24] + 10} {y - 9} Q{(cx[24] + cx[48]) / 2} {y - 20} {cx[48] - 10} {y - 9}", "ln",
                                 f' style="stroke:{DANGER};stroke-dasharray:4 3"'))
                out.append(f'<path d="M{cx[48] - 10} {y - 9} l-7 -1 l3 6 z" fill="{DANGER}"/>')
        for f in alt:
            out.append(f'<circle cx="{cx[f]}" cy="{y}" r="6" fill="none" stroke="{ACCENT}" stroke-width="2"/>')
    out.append(text(16, top - 11, "класс", "m t", "start", 10.5))
    # legend for marks (a key, not a note)
    ky = y_end + 36
    out.append(f'<circle cx="22" cy="{ky - 4}" r="6" fill="{ACCENT}"/>')
    out.append(text(34, ky, "старт", "t", "start", 10.5))
    out.append(f'<circle cx="92" cy="{ky - 4}" r="5" fill="none" stroke="{ACCENT}" stroke-width="2"/>')
    out.append(text(104, ky, "допустимо", "t", "start", 10.5))
    out.append(f'<path d="M190 {ky - 4} L226 {ky - 4}" stroke="{ACCENT}" stroke-width="6" opacity="0.45"/>')
    out.append(text(232, ky, "переменная частота", "t", "start", 10.5))
    out.append(_path(f"M380 {ky - 4} L414 {ky - 4}", "ln", f' style="stroke:{DANGER};stroke-dasharray:4 3"'))
    out.append(text(420, ky, "сдвиг при DJI O3/O4 + Gyroflow", "d t", "start", 10.5))
    # step 2 of the procedure with the module's 7" number
    f_hz, erpm = 24000, 50000
    N = 10 * f_hz / erpm
    assert abs(N - 4.8) < 1e-9
    by = ky + 16
    out.append(_box(16, by, 688, 56, ["Затем для любого класса: N = 10·f/eRPM на висении (периодов ШИМ на шаг коммутации)",
                                       f"7\": висение ≈ 50 000 eRPM, 24 кГц → N = 10·24 000/50 000 = {N:.1f} — запас есть",
                                       "N < 3 — ступень вверх; N > 10 при горячем ESC — вниз; дальше — по симптомам в полёте"],
                    anchor="start"))
    return _close(out, W, by + 66, "Частота ШИМ ESC по классу аппарата")


# ---------------------------------------------------------------- link-vtx
def vtx_power_index_map() -> str:
    W = 720
    mw = lambda dbm: 10 ** (dbm / 10)
    t_a = [(14, 25), (20, 100), (26, 400)]                       # module «Синтаксис» vtxtable
    t_b = [(14, 25), (23, 200), (27, 500), (29, 800)]            # exercise table, built by hand
    for dbm, lab in t_a + t_b:
        assert abs(mw(dbm) - lab) / lab < 0.05, (dbm, lab)
    t_c = [25, 100, 200, 400, 600]                               # INAV Tramp 600 mW VTX (io/vtx_tramp.c)
    out = [text(16, 18, "vtx_power — номер уровня, а не милливатты: одна строка, три передатчика", "m t", "start")]
    out.append(_box(300, 30, 220, 34, ["set vtx_power = 3"], "boxa", size=12))
    cols = [(205, "Betaflight, vtxtable модуля", "powervalues 14 20 26", [(f"{l} мВт", f"{d} дБм") for d, l in t_a], 4),
            (430, "Тот же diff, другой VTX", "powervalues 14 23 27 29", [(f"{l} мВт", f"{d} дБм") for d, l in t_b], 0),
            (625, "INAV, Tramp 600 мВт", "уровни io/vtx_tramp.c", [(f"{l} мВт", "") for l in t_c], 0)]
    top, rh = 124, 34
    cws = [176, 176, 160]
    out.append(text(16, top - 12, "уровень", "m t", "start", 10.5))
    for k in range(5):
        out.append(text(44, top + k * rh + 21, str(k + 1), "b", "middle", 13))
    y3 = top + 2 * rh
    out.append(f'<rect x="20" y="{y3 + 1}" width="{W - 30}" height="{rh - 2}" rx="4" fill="{ACCENT}" opacity="0.10"/>')
    out.append(_arrow(f"M410 64 L410 80 L94 80 L94 {y3 + 4}", True))
    for (cx, head, sub, cells, missing), cw in zip(cols, cws):
        out.append(text(cx, top - 26, head, "b", "middle", 11))
        out.append(text(cx, top - 12, sub, "m t", "middle", 10.5))
        for k, (a, b) in enumerate(cells):
            y = top + k * rh
            acc = k == 2
            out.append(_rect(cx - cw / 2, y + 3, cw, rh - 6, "boxa" if acc else "box", 4))
            out.append(text(cx - (22 if b else 0), y + 21, a, "a b" if acc else "b", "middle", 11.5))
            if b:
                out.append(text(cx + 48, y + 21, b, "m t", "middle", 10.5))
        if missing:
            y = top + (missing - 1) * rh
            out.append(_rect(cx - cw / 2, y + 3, cw, rh - 6, "box", 4, ' style="stroke-dasharray:4 3;opacity:0.7"'))
            out.append(text(cx, y + 21, "нет: FC не отправит", "d t", "middle", 10.5))
    yb = top + 5 * rh + 12
    out.append(_box(16, yb, 688, 40, ["vtx_low_power_disarm = ON: в дизарме — уровень 1 (25 мВт во всех трёх);",
                                       "UNTIL_FIRST_ARM — только до первого арма; в failsafe мощность не снижается"],
                    anchor="start"))
    return _close(out, W, yb + 50, "vtx_power: уровень и милливатты")


# ---------------------------------------------------------------- link-digital-video
def goggles_vtx_links() -> str:
    W = 720
    out = [text(16, 18, "Какие очки что принимают (ноябрь 2026): связи, которые прячет таблица", "m t", "start")]
    styles = {"n": (INK, "", 1.6), "m": (INK, "6 4", 1.4), "u": (ACCENT, "6 4", 1.8), "x": (MUTED, "2 3", 1.4)}
    keys = [("n", "сами", 16, 40), ("m", "через модуль или внешний приёмник", 130, 40),
            ("u", "после обновления / на совместимой прошивке", 16, 58), ("x", "не проверено", 470, 58)]
    for k, lab, kx, ky in keys:
        col, dash, sw = styles[k]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<path d="M{kx} {ky - 4} L{kx + 30} {ky - 4}" stroke="{col}" stroke-width="{sw}"{d}/>')
        out.append(text(kx + 36, ky, lab, "t", "start", 10.5))
    gog = ["DJI Goggles 2 / Integra", "DJI Goggles 3", "DJI Goggles N3", "Walksnail Goggles L", "Walksnail Goggles X",
           "HDZero Goggle 2, BoxPro", "HDZero Goggle (первые)", "Аналоговые очки"]
    sysn = ["Vista, DJI FPV Air Unit", "DJI O3", "DJI O4, O4 Pro", "Walksnail", "HDZero", "Аналог 5.8 ГГц"]
    top, gh, gw, gx = 92, 38, 214, 14
    sw_, sx = 214, 492
    gy = [top + i * gh + (18 if i >= 3 else 0) for i in range(len(gog))]
    sy = [gy[0], gy[1], gy[2], (gy[3] + gy[4]) / 2, (gy[5] + gy[6]) / 2, gy[7]]
    edges = [(0, 0, "u"), (0, 1, "n"), (0, 2, "n"), (1, 1, "u"), (1, 2, "n"), (2, 2, "n"), (3, 3, "n"), (4, 3, "n"),
             (4, 4, "m"), (4, 5, "m"), (5, 4, "n"), (5, 5, "n"), (5, 3, "m"), (6, 4, "n"), (6, 5, "m"), (7, 5, "n"),
             (7, 4, "x"), (7, 3, "x")]
    # DJI cluster frame
    out.append(f'<rect x="6" y="{top - 7}" width="708" height="{gy[2] + 28 + 14 - top}" rx="10" fill="none" stroke="{MUTED}" '
               f'stroke-dasharray="5 4"/>')
    out.append(text(360, gy[2] + 28 + 3, "DJI — только с DJI, по поколениям", "m t", "middle", 10.5))
    groups = {}
    for g, s, k in edges:
        groups.setdefault(k, []).append(
            f"M{gx + gw} {gy[g] + 14:.1f} C{gx + gw + 110} {gy[g] + 14:.1f} {sx - 110} {sy[s] + 14:.1f} {sx} {sy[s] + 14:.1f}")
    for k, ds in groups.items():
        col, dash, sw = styles[k]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<g fill="none" stroke="{col}" stroke-width="{sw}"{d}>' + "".join(f'<path d="{p}"/>' for p in ds) + "</g>")
    for i, name in enumerate(gog):
        out.append(_box(gx, gy[i], gw, 28, [name], "box", 5, 10.5))
    for i, name in enumerate(sysn):
        out.append(_box(sx, sy[i], sw_, 28, [name], "boxa" if i >= 3 else "box", 5, 10.5))
    return _close(out, W, gy[7] + 38, "Совместимость очков и видеосистем")


# ---------------------------------------------------------------- el-dronecan
def dna_flow() -> str:
    W = 720
    out = [text(16, 18, "DNA: номер узла выдаёт полётник и запоминает его за уникальным ID узла", "m t", "start")]
    out.append(_box(10, 32, 200, 46, ["Новый узел без номера", "(GPS, компас, датчик тока)"]))
    out.append(_arrow("M210 55 L240 55"))
    out.append(_box(240, 32, 200, 46, ["Просит номер у сервера,", "шлёт свой уникальный ID"]))
    out.append(_arrow("M440 55 L470 55"))
    out.append(_box(470, 26, 240, 58, ["DNA-сервер — полётник:", "этот уникальный ID", "уже есть в таблице?"], "boxa"))
    # who the server is: a side box linked to the server box
    out.append(_path("M484 84 L484 92 L145 92 L145 112", "lnm"))
    out.append(text(151, 106, "кто сервер", "m t", "start", 10.5))
    out.append(_box(10, 112, 270, 128, ["ArduPilot — полётник, его номер", "CAN_D1_UC_NODE = 10 (умолч.);",
                                         "не совпадать с жёстким номером", "ни одного узла;",
                                         "PX4 — только при UAVCAN_ENABLE", "2 или 3 (умолч. 0 — шина выключена;",
                                         "1 — номера узлов вручную)"], anchor="start"))
    # branches
    out.append(_path("M590 84 L590 98 L470 98"))
    out.append(_arrow("M470 98 L470 112"))
    out.append(_arrow("M590 98 L650 98 L650 112"))
    out.append(text(656, 108, "да", "a t b", "start", 10.5))
    out.append(text(476, 108, "нет", "a t b", "start", 10.5))
    out.append(_box(300, 112, 300, 58, ["свободный номер 1…125 (126, 127 —", "для сервисных инструментов),",
                                         "записать «ID → номер»"]))
    out.append(_box(610, 112, 100, 58, ["прежний", "номер"]))
    out.append(_path("M450 170 L450 186 L660 186 L660 170"))
    out.append(_arrow("M555 186 L555 200"))
    out.append(_box(400, 200, 310, 40, ["узел работает: NodeStatus", "(здоровье, режим, время работы)"]))
    # failure path
    y = 274
    out.append(text(16, y - 12, "Где ломается", "d t b", "start", 10.5))
    out.append(_box(10, y, 220, 72, ["узлы переставили между", "аппаратами или скопировали", "настройки: два узла",
                                      "с одним номером"]))
    out.append(_arrow(f"M230 {y + 36} L252 {y + 36}"))
    out.append(_box(252, y, 210, 72, ["ArduPilot: PreArm", "«Duplicate Node», арм", "запрещён; датчик не виден"]))
    out.append(_arrow(f"M462 {y + 36} L484 {y + 36}", True))
    out.append(_box(484, y, 226, 72, ["CAN_D1_UC_OPTION бит 0 (1):", "очистить таблицу при загрузке —",
                                       "«UC DNA database reset»,", "бит сбросится сам; или", "жёсткий номер на узле"], "boxa"))
    return _close(out, W, y + 82, "DroneCAN DNA: как узел получает номер")


# ---------------------------------------------------------------- est-alt-sources
def surface_limits() -> str:
    W = 720
    out = [text(16, 18, "INAV 9.1.0: высота над поверхностью — режим SURFACE, а не источник, как EK3_SRC1_POSZ = 2",
                "m t", "start")]
    out.append(_box(30, 30, 660, 54, ["SURFACE (id 33) есть на вкладке Modes, только если мультиротор + барометр + дальномер;",
                                       "работает поверх ALTHOLD или POSHOLD, газ задаёт высоту над землёй;",
                                       "inav_max_surface_altitude = 200 см (умолч.): выше отсчёт дальномера не принимается"],
                    "boxa"))
    y0, y1 = 316, 112                        # 0 cm at y0, 300 cm at y1 — linear scale
    Y = lambda cm: y0 - (y0 - y1) * cm / 300
    LIM = 200                                # inav_max_surface_altitude, default
    panels = [(40, 100, "Норма: nav_max_terrain_follow_alt = 100 (умолч.)"),
              (400, 250, "Ошибка: nav_max_terrain_follow_alt = 250")]
    out.append(_arrow("M360 84 L360 100"))
    for x, tf, head in panels:
        w = 300
        out.append(f'<rect x="{x + 40}" y="{Y(LIM):.1f}" width="{w - 40}" height="{Y(0) - Y(LIM):.1f}" fill="{ACCENT}" opacity="0.08"/>')
        out.append(f'<rect x="{x + 40}" y="{Y(300):.1f}" width="{w - 40}" height="{Y(LIM) - Y(300):.1f}" fill="{DANGER}" opacity="0.10"/>')
        out.append(f'<g stroke="{MUTED}" stroke-width="1">' + "".join(
            f'<line x1="{x + 36}" y1="{Y(cm):.1f}" x2="{x + 40}" y2="{Y(cm):.1f}"/>' for cm in range(0, 301, 50)) + "</g>")
        for cm in range(0, 301, 50):
            out.append(text(x + 32, Y(cm) + 4, f"{cm}", "m t", "end", 10.5))
        out.append(f'<line x1="{x + 40}" y1="{Y(0)}" x2="{x + 40}" y2="{Y(300)}" stroke="{INK}" stroke-width="1"/>')
        out.append(f'<line x1="{x + 40}" y1="{Y(LIM):.1f}" x2="{x + w}" y2="{Y(LIM):.1f}" stroke="{DANGER}" stroke-width="1.4" stroke-dasharray="5 3"/>')
        out.append(text(x + w - 4, Y(LIM) + 15, "предел 200 см", "d t", "end", 10.5))
        out.append(text(x + w - 4, Y(LIM) + 30, "дальномер учитывается", "a t", "end", 10.5))
        out.append(text(x + w - 4, Y(285), "отсчёт не принимается →", "d t", "end", 10.5))
        out.append(text(x + w - 4, Y(285) + 13, "AGL недостоверна → снижение", "d t", "end", 10.5))
        # throttle -> target AGL bar (linear: 0…100 % -> 0…tf)
        bx = x + 70
        top_ok = min(tf, LIM)
        out.append(f'<path d="M{bx} {Y(0):.1f} L{bx} {Y(top_ok):.1f}" stroke="{ACCENT}" stroke-width="10" fill="none"/>')
        if tf > LIM:
            out.append(f'<path d="M{bx} {Y(LIM):.1f} L{bx} {Y(tf):.1f}" stroke="{DANGER}" stroke-width="10" fill="none"/>')
        out.append(f'<line x1="{bx - 12}" y1="{Y(tf):.1f}" x2="{bx + 12}" y2="{Y(tf):.1f}" stroke="{INK}" stroke-width="2"/>')
        out.append(text(bx + 14, Y(tf) + 4, f"полный газ = {tf} см", "b", "start", 10.5))
        out.append(text(bx + 14, Y(0) - 6, "газ 0 % = 0 см", "t", "start", 10.5))
        out.append(text(x + w / 2 + 20, Y(0) + 20, head, "b", "middle", 10.5))
    out.append(text(16, Y(150), "см", "m t", "start", 10.5))
    tf_bad = panels[1][1]
    share = round(100 * (tf_bad - LIM) / tf_bad)          # linear map: throttle above LIM/tf_bad of travel
    assert share == 20
    out.append(text(400 + 84, Y(225) + 4, f"верхние {share} % газа — без дальномера", "d t", "start", 10.5))
    return _close(out, W, Y(0) + 32, "Режим SURFACE в INAV: два предела")


# ---------------------------------------------------------------- nav-resilience
def gps_loss_ladder() -> str:
    W = 720
    out = [text(16, 18, "Что делает прошивка сама, когда навигация деградирует (по ступеням)", "m t", "start")]
    cols = [(104, "ArduPilot 4.7"), (308, "PX4 1.18"), (512, "INAV 9.1")]
    cw = 200
    rungs = [("позиция", "врёт / хуже"), ("позиции", "нет"), ("нет и", "высоты")]
    for cx, h in cols:
        out.append(text(cx + cw / 2, 40, h, "b", "middle", 12))
    cells = {
        (0, 0): ["GPS glitch: расхождение", "> EK3_GLITCH_RAD (25 м,", "умолч.) — сброс позиции", "и скорости к GPS"],
        (1, 0): ["Mission / Hold: точность", "хуже COM_POS_LOW_EPH (умолч.", "выкл.) → COM_POS_LOW_ACT", "(умолч. Return)"],
        (2, 0): ["короткие пропадания:", "счисление на секунды", "(inav_allow_dead_reckoning)"],
        (0, 1): ["EKF failsafe: порог", "FS_EKF_THRESH; FS_EKF_ACTION", "1 Land, 2 AltHold — если", "режим требует позицию;",
                 "3 Land всегда; 0 сообщение"],
        (1, 1): ["Position → Altitude", "(с 1.17 сам; до 1.17 —", "COM_POSCTL_NAVL)"],
        (2, 1): ["RTH / WP: нет позиции", "> nav_position_timeout (5 с)", "→ аварийная посадка 5 м/с", "(оба — умолч.) до детектора"],
        (1, 2): ["Altitude → Stabilized"],
        (2, 2): ["снижения по скорости нет:", "газ failsafe_throttle"],
    }
    tops = [52, 138, 236]
    hs = [68, 78, 44]
    for r, (a, b) in enumerate(rungs):
        out.append(text(14, tops[r] + hs[r] / 2 - 2, a, "b", "start", 11))
        out.append(text(14, tops[r] + hs[r] / 2 + 12, b, "b", "start", 11))
    for (c, r), ls in cells.items():
        out.append(_box(cols[c][0], tops[r], cw, hs[r], ls, "boxa" if r == 1 else "box", 6, 10.5, 13))
    for (c, r) in cells:
        if (c, r + 1) in cells and (c, r) != (1, 0):     # PX4: Mission/Hold and Position are different modes
            cx = cols[c][0] + cw / 2
            out.append(_arrow(f"M{cx} {tops[r] + hs[r]} L{cx} {tops[r + 1]}"))
    yb = tops[2] + hs[2] + 22
    out.append(_box(14, yb, 698, 54, ["Всегда: Stabilize / AltHold на тумблере, и пилот умеет ими летать.",
                                       "Действие при потере позиции — по месту: поле — AltHold и ручная посадка;",
                                       "люди — Land; вода — AltHold и ручной возврат к берегу (на инерциалку не рассчитывать)"],
                    "box", anchor="start"))
    return _close(out, W, yb + 64, "Деградация навигации: реакция ArduPilot, PX4, INAV")


# ---------------------------------------------------------------- payload-gimbal
def gimbal_control_paths() -> str:
    W = 720
    out = [text(16, 18, "Путь команды подвесу: где включается и где молча обрывается (ArduPilot 4.7.2, PX4 1.18)",
                "m t", "start")]
    # ArduPilot lane
    y = 46
    out.append(text(16, y - 6, "ArduPilot", "b", "start", 12))
    out.append(_box(10, y, 206, 96, ["Клиенты", "пульт: RCx_OPTION 212–214", "(163 — Mount Yaw Lock);",
                                      "GCS / companion:", "DO_GIMBAL_MANAGER_PITCHYAW;", "миссия: DO_SET_ROI_LOCATION"],
                    bold_first=True))
    out.append(_arrow(f"M216 {y + 48} L238 {y + 48}"))
    out.append(_box(238, y, 206, 96, ["Менеджер в автопилоте", "MNT1_DEFLT_MODE:", "умолч. 3 — слушает пульт;",
                                       "MNT1_RC_RATE: 0 — угол,", "> 0 — скорость °/с"], "boxa"))
    outs = [["1 Servo, 7 BrushlessPWM:", "SERVOn_FUNCTION 6 / 7 / 8"],
            ["5, 8, 11–14 — UART:", "SERIALn_PROTOCOL = 8 (Gimbal);", "3 Alexmos — протокол 7"],
            ["4, 6 — порт MAVLink 2:", "подвес — компонент 154"],
            ["10 Xacti — DroneCAN"]]
    hs = [32, 44, 32, 22]
    ox, ow = 488, 222
    yy = y - 14
    bus = 470
    out.append(_path(f"M444 {y + 48} L{bus} {y + 48}"))
    ys = []
    for ls, h in zip(outs, hs):
        out.append(_box(ox, yy, ow, h, ls, "box", 5, 10.5, 12))
        ys.append(yy + h / 2)
        yy += h + 6
    out.append(_path(f"M{bus} {ys[0]:.1f} L{bus} {ys[-1]:.1f}"))
    for yc in ys:
        out.append(_arrow(f"M{bus} {yc:.1f} L{ox} {yc:.1f}"))
    out.append(text(bus - 4, y + 118, "MNT1_TYPE", "a t b", "end", 10.5))
    # PX4 lane
    y = 214
    out.append(text(16, y - 6, "PX4", "b", "start", 12))
    out.append(_box(10, y, 206, 96, ["Клиенты", "пульт: MNT_MAN_PITCH = AUX n", "и RC_MAP_AUXn — нужны оба,",
                                      "иначе по оси ноль;", "GCS / миссия / companion —", "Gimbal v2"], bold_first=True))
    out.append(_arrow(f"M216 {y + 48} L238 {y + 48}"))
    out.append(_box(238, y, 206, 96, ["Модуль gimbal", "MNT_MODE_IN: умолч. −1 —", "не стартует («not running»);",
                                       "0 пульт + v2, 1 пульт,", "4 только v2 (2, 3 — v1,", "не выбирать); перезагрузка"],
                    "boxa"))
    out.append(_path(f"M444 {y + 48} L{bus} {y + 48}"))
    o1 = (y + 2, 40, ["MNT_MODE_OUT = 0 — AUX:", "функции 420 / 421 / 422, 50 Гц"])
    o2 = (y + 48, 52, ["MNT_MODE_OUT = 2 — Gimbal v2:", "MAV_n_MODE = 10; без", "GIMBAL_DEVICE_INFORMATION —",
                       "«compid not found»"])
    for (yt, h, ls) in (o1, o2):
        out.append(_box(ox, yt, ow, h, ls, "box", 5, 10.5, 12))
    c1, c2 = o1[0] + o1[1] / 2, o2[0] + o2[1] / 2
    out.append(_path(f"M{bus} {c1:.1f} L{bus} {c2:.1f}"))
    out.append(_arrow(f"M{bus} {c1:.1f} L{ox} {c1:.1f}"))
    out.append(_arrow(f"M{bus} {c2:.1f} L{ox} {c2:.1f}"))
    out.append(_box(10, 330, 700, 40, ["Проверка: ArduPilot — нет «PreArm: Mount: …», стик RCx_OPTION = 213 двигает наклон в режиме 3;",
                                        "PX4 — gimbal status, затем gimbal test pitch -45 (руки и кабели из зоны хода)"],
                    anchor="start"))
    return _close(out, W, 380, "Подвес: путь команды в ArduPilot и PX4")


def build(D: dict) -> None:
    D["inav-upgrade-8-to-9"] = upgrade_flow()
    D["inav-gps-loss-modes"] = gps_loss_modes()
    D["inav-autotune-tree"] = autotune_tree()
    D["inav-wp-user-action-chain"] = user_action_chain()
    D["inav-logic-line-fields"] = logic_line_fields()
    D["esc-pwm-class-map"] = esc_pwm_class_map()
    D["vtx-power-index-map"] = vtx_power_index_map()
    D["goggles-vtx-links"] = goggles_vtx_links()
    D["dronecan-dna-flow"] = dna_flow()
    D["inav-surface-limits"] = surface_limits()
    D["gps-loss-ladder"] = gps_loss_ladder()
    D["gimbal-control-paths"] = gimbal_control_paths()
