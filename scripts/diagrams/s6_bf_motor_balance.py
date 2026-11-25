"""Stage 6 diagrams for module bf-motor-balance (mechanics before PID: motor balance from the log).

bf-quadx-motor-map     — Betaflight Quad X seen from above: motor numbers 1 RR, 2 FR, 3 RL, 4 FL, log index
                         motor[0..3], spin directions with props-in (yaw_motors_reversed = OFF), and the three
                         pair comparisons the module computes (rear-front, left-right, diagonal 1+4 vs 2+3);
                         signs from mixerQuadX[] in flight/mixer_init.c (4.5.3), spin directions from the
                         betaflight.com page "Running with Reversed Motors".
bf-motor-balance-tree  — the module's diagnosis rule: which index pattern points to which hardware cause, with the
                         course guideline 2 % (not a firmware value) and the prop/motor swap test (svg.tree).
"""
from __future__ import annotations

import math

from svg import Node, svg, text, tree

# (number, position, log index, x, y, spins CW with props-in)
_MOTORS = [(1, "RR", 0, 270, 238, True), (2, "FR", 1, 270, 92, False),
           (3, "RL", 2, 110, 238, False), (4, "FL", 3, 110, 92, True)]


def _spin(cx, cy, r, cw, cls="lna"):
    """Arc of ~110 deg on the outside of a motor circle with an arrow head in the spin direction."""
    a0, a1 = (-150, -40) if cw else (-40, -150)
    p0 = (cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    p1 = (cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1)))
    sweep = 1 if cw else 0
    return (f'<path class="{cls}" d="M{p0[0]:.1f} {p0[1]:.1f} A{r} {r} 0 0 {sweep} {p1[0]:.1f} {p1[1]:.1f}" '
            f'marker-end="url(#ara)"/>')


def _mini(x0, y0, hi: set, title, lines):
    """A 70 px quad sketch: the motors of the 'higher' group filled with the accent colour."""
    out = []
    pos = {1: (x0 + 58, y0 + 58), 2: (x0 + 58, y0 + 12), 3: (x0 + 12, y0 + 58), 4: (x0 + 12, y0 + 12)}
    out.append(f'<path class="lnm" d="M{x0 + 12} {y0 + 12} L{x0 + 58} {y0 + 58} M{x0 + 58} {y0 + 12} L{x0 + 12} {y0 + 58}"/>')
    for n, (x, y) in pos.items():
        fill = "var(--gc-accent-hud, #5ef1d2)" if n in hi else "none"
        out.append(f'<circle cx="{x}" cy="{y}" r="10" fill="{fill}" fill-opacity="0.35" '
                   f'stroke="currentColor" stroke-width="1.2"/>')
        out.append(text(x, y + 4, str(n), "b", size=11))
    out.append(text(x0 + 35, y0 - 10, title, "b t"))
    for i, ln in enumerate(lines):
        out.append(text(x0 + 35, y0 + 88 + i * 14, ln, "m t"))
    return "".join(out)


def build(D: dict) -> None:
    b = []
    b.append(text(16, 18, "Betaflight Quad X сверху: номер, поле лога, вращение (props-in)", "m t", "start"))
    # frame arms and body
    arms = []
    for _, _, _, x, y, _ in _MOTORS:                 # arm from the FC box edge to the motor circle edge
        dx, dy = x - 190, y - 165
        L = math.hypot(dx, dy)
        arms.append(f"M{190 + dx * 34 / L:.1f} {165 + dy * 34 / L:.1f} L{190 + dx * (L - 34) / L:.1f} {165 + dy * (L - 34) / L:.1f}")
    b.append(f'<path class="ln" d="{" ".join(arms)}" style="stroke-width:5;opacity:0.35"/>')
    b.append('<rect class="box" x="166" y="141" width="48" height="48" rx="6"/>')
    b.append(text(190, 169, "FC", "m t"))
    b.append('<path class="lna" d="M190 136 L190 56" marker-end="url(#ara)"/>')
    b.append(text(190, 46, "нос, камера", "a t"))
    for n, pos, li, x, y, cw in _MOTORS:
        b.append(f'<circle class="box" cx="{x}" cy="{y}" r="34"/>')
        b.append(text(x, y - 4, f"{n} {pos}", "b", size=14))
        b.append(text(x, y + 14, f"motor[{li}]", "a t"))
        b.append(_spin(x, y, 44, cw))
        lx = x + (58 if x > 190 else -58)
        b.append(text(lx, y + 4, "CW" if cw else "CCW", "b t", "start" if x > 190 else "end"))
    b.append(text(190, 306, "yaw_motors_reversed = ON (props-out):", "m t"))
    b.append(text(190, 320, "все стрелки наоборот, номера те же", "m t"))
    # right panel: three pair comparisons
    b.append(text(400, 46, "Три сравнения пар по медианам (в % хода)", "m t", "start"))
    b.append(_mini(410, 82, {1, 3}, "pitch", ["зад − перед", "(1+3) − (2+4)"]))
    b.append(_mini(520, 82, {3, 4}, "roll", ["лево − право", "(3+4) − (1+2)"]))
    b.append(_mini(630, 82, {1, 4}, "yaw", ["диагонали", "(1+4) − (2+3)"]))
    b.append(text(400, 236, "mixerQuadX: roll −1 у 1, 2; +1 у 3, 4;", "m t", "start"))
    b.append(text(400, 252, "pitch +1 у 1, 3; yaw −1 у 1, 4; +1 у 2, 3", "m t", "start"))
    b.append(text(400, 274, "Один слабый мотор даёт три перекоса одной", "a t", "start"))
    b.append(text(400, 290, "величины; ЦТ — только pitch и roll;", "a t", "start"))
    b.append(text(400, 306, "наклон мотора — только yaw.", "a t", "start"))
    D["bf-quadx-motor-map"] = svg(720, 332, "Betaflight Quad X: номера моторов, поля лога и вращение", "".join(b))

    leaf = lambda i, lines: Node(i, lines, leaf=True)
    D["bf-motor-balance-tree"] = tree(
        "Медианы участка 10–20 с → индексы → причина (2 % и 5 % — ориентиры курса)",
        Node("r", ["индексы pitch,", "roll, yaw"], [
            ("все ≤ 2 %", leaf("ok", ["механика в норме:", "фильтры, PID"])),
            ("pitch/roll", Node("cg", ["yaw ≈ 0:", "смещён ЦТ"], [
                ("", leaf("cg1", ["сдвинь АКБ,", "новый лог"]))])),
            ("|p|≈|r|≈|y|", Node("one", ["один мотор", "в углу: swap", "пропов"], [
                ("с пропом", leaf("prop", ["проп: замена,", "балансировка"])),
                ("остался", leaf("mot", ["swap моторов:", "мотор или", "ESC/луч"]))], accent=True)),
            ("только yaw", Node("yaw", ["pitch/roll ≈ 0:", "момент"], [
                ("", leaf("tilt", ["наклон мотора,", "луч, разные", "пропы"]))])),
        ], accent=True),
        width=720, box_w=132, box_h=52, gap_y=92)
