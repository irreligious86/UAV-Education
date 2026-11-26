"""Thin-module pass diagram for module ros2-from-ros1.

ros2-distro-timeline — support windows of ROS 1 Noetic and ROS 2 distros (release -> EOL) on one time axis with the
                       course date (Nov 2026). Dates: ROS 2 docs «Distributions» table (rolling branch, Nov 2026) and the
                       Noetic EOL announcement (31 May 2025). Kilted EOL: docs say December 2026, REP 2000 November 2026.
"""
from __future__ import annotations

from svg import ACCENT, DANGER, INK, MUTED, svg, text

Y0, Y1 = 2020.0, 2031.6
ROWS = [  # name, start, end, label, supported in Nov 2026, Ubuntu
    ("Noetic (ROS 1)", 2020.38, 2025.41, "EOL 31.05.2025", False, "20.04"),
    ("Foxy", 2020.43, 2023.47, "EOL 06.2023", False, "20.04"),
    ("Humble LTS", 2022.39, 2027.42, "до 05.2027", True, "22.04"),
    ("Iron", 2023.39, 2024.93, "EOL 12.2024", False, "22.04"),
    ("Jazzy LTS", 2024.39, 2029.42, "до 05.2029", True, "24.04"),
    ("Kilted", 2025.39, 2027.0, "до 12.2026", True, "24.04"),
    ("Lyrical LTS", 2026.39, 2031.42, "до 05.2031", True, "26.04"),
]
NOW = 2026.9


def distro_timeline() -> str:
    W, L, R, top, lane = 720, 150, 20, 46, 30
    X = lambda y: L + (W - L - R) * (y - Y0) / (Y1 - Y0)
    out = [text(16, 18, "Поддержка дистрибутивов ROS: что ещё живо в ноябре 2026", "m t", "start")]
    h = top + len(ROWS) * lane + 40
    for yr in range(2020, 2032):
        out.append(f'<line class="lnm" x1="{X(yr):.1f}" y1="{top - 6}" x2="{X(yr):.1f}" y2="{h - 26}"/>')
        out.append(text(X(yr), h - 12, f"{yr}", "m t", size=10))
    for i, (name, a, b, lab, alive, ub) in enumerate(ROWS):
        y = top + i * lane
        out.append(text(L - 8, y + 18, name, "b" if alive else "m", "end", size=11))
        cls = "boxa" if alive else "box"
        op = "" if alive else ' opacity="0.55"'
        out.append(f'<rect class="{cls}" x="{X(a):.1f}" y="{y + 4}" width="{X(b) - X(a):.1f}" height="{lane - 10}" rx="3"{op}/>')
        inside = X(b) - X(a) > 150
        out.append(text((X(a) + X(b)) / 2 if inside else X(b) + 4, y + 18, f"{lab} · Ubuntu {ub}",
                        "" if inside else "m t", "middle" if inside else "start", size=10))
    out.append(f'<line x1="{X(NOW):.1f}" y1="{top - 10}" x2="{X(NOW):.1f}" y2="{h - 26}" stroke="{DANGER}" stroke-width="1.6"/>')
    out.append(text(X(NOW) + 4, top - 14, "ноябрь 2026", "d t", "start", size=10))
    return svg(W, h, "Окна поддержки ROS 1 Noetic и ROS 2 по годам", "".join(out))


def build(D: dict) -> None:
    D["ros2-distro-timeline"] = distro_timeline()
