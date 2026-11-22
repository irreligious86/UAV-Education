"""Stage 6 (theory-first) diagrams for module eng-career.

career-role-map            — matrix: twelve industry roles (rows) against the course tracks (columns) as the module's
                             role table states them: filled = core track for the role, ring = supporting track.
career-first-contribution  — the first open-source contribution path the module describes for ArduPilot / PX4 /
                             Betaflight / INAV: reproduce in SITL -> issue -> small PR with test evidence -> review.
"""
from __future__ import annotations

from svg import ACCENT, INK, MUTED, Box, esc, flow, svg, text

TRACKS = ["Фундамент", "Оператор", "Электроника", "Конструктор", "Интегратор", "Оценка", "Автономия", "Инженер",
          "Восприятие", "ROS 2"]
#            Ф  О  Э  К  И  Н  А  Инж В  R
ROLES = [
    ("Пилот / инструктор",        [2, 2, 0, 0, 1, 0, 0, 0, 0, 0]),
    ("Оператор БАС (работы)",     [2, 2, 0, 0, 0, 0, 2, 0, 1, 0]),
    ("Лётные испытания",          [0, 1, 0, 1, 2, 1, 2, 0, 0, 0]),
    ("Управление / GNC",          [0, 0, 0, 2, 2, 2, 1, 0, 0, 0]),
    ("Embedded / прошивка",       [0, 0, 1, 0, 1, 0, 1, 2, 0, 0]),
    ("Электроника / железо",      [1, 0, 2, 1, 0, 0, 0, 0, 0, 0]),
    ("Радиолиния / RF",           [0, 2, 2, 0, 0, 0, 0, 0, 0, 0]),
    ("Восприятие / CV / ML",      [0, 0, 0, 0, 0, 1, 0, 1, 2, 1]),
    ("Робототехника ROS 2",       [0, 0, 0, 0, 0, 0, 1, 1, 1, 2]),
    ("Системы и безопасность",    [2, 0, 1, 0, 0, 0, 1, 2, 0, 0]),
    ("Техник / обслуживание",     [2, 2, 1, 0, 1, 0, 0, 0, 0, 0]),
    ("Продукт / FAE",             [1, 1, 0, 2, 0, 0, 1, 1, 0, 0]),
]


def role_map() -> str:
    W, left, top, col, row = 720, 190, 112, 52, 26
    out = [text(16, 16, "Роли отрасли и треки курса: ● основной трек, ○ поддерживающий", "m t", "start")]
    for j, name in enumerate(TRACKS):
        x = left + j * col + col / 2
        out.append(f'<text x="{x:.0f}" y="{top - 10}" transform="rotate(-40 {x:.0f} {top - 10})" '
                   f'text-anchor="start" class="t">{esc(name)}</text>')
    for i, (role, marks) in enumerate(ROLES):
        y = top + i * row
        if i % 2 == 0:
            out.append(f'<rect x="10" y="{y}" width="{left + len(TRACKS) * col - 10}" height="{row}" '
                       f'fill="{MUTED}" fill-opacity="0.08"/>')
        out.append(text(left - 10, y + 17, role, "", "end", size=11))
        for j, m in enumerate(marks):
            cx, cy = left + j * col + col / 2, y + row / 2
            if m == 2:
                out.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="7" fill="{ACCENT}" stroke="{ACCENT}"/>')
            elif m == 1:
                out.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="6" fill="none" stroke="{INK}" stroke-width="1.3"/>')
    for j in range(len(TRACKS) + 1):
        x = left + j * col
        out.append(f'<line class="lnm" x1="{x}" y1="{top}" x2="{x}" y2="{top + len(ROLES) * row}"/>')
    h = top + len(ROLES) * row + 34
    out.append(text(16, h - 12, "Ни одна роль не закрывается одним треком: от двух (RF) до пяти (испытания, продукт)",
                    "m t", "start"))
    return svg(W, h, "Карта ролей: роли и треки курса", "".join(out))


def first_contribution() -> str:
    return flow("Первый вклад в открытый автопилот", [
        Box("read", ["1. CONTRIBUTING", "и правила проекта"], 10, 40, 150, 48),
        Box("pick", ["2. Задача: issue", "или правка docs"], 195, 40, 160, 48),
        Box("repro", ["3. Воспроизвести", "в SITL, записать лог"], 390, 40, 150, 48, accent=True),
        Box("pr", ["4. Маленький PR:", "одно изменение"], 565, 40, 150, 48),
        Box("evid", ["тест / лог до-после,", "Fixes/Resolves #N"], 470, 130, 160, 44, accent=True),
        Box("rev", ["5. Ревью: правки", "по правилам проекта"], 250, 130, 170, 44),
        Box("port", ["6. Ссылка на PR", "в портфолио"], 40, 130, 160, 44, accent=True),
    ], [("read", "pick"), ("pick", "repro"), ("repro", "pr", "", True), ("pr", "evid", "", False, "v"),
        ("evid", "rev"), ("rev", "port", "", True)],
        720, 210, notes=[(10, 198, "Начинать проще с docs-правки или воспроизведённого бага с логом, чем с новой функции",
                          "m t")])


def build(D: dict) -> None:
    D["career-role-map"] = role_map()
    D["career-first-contribution"] = first_contribution()
