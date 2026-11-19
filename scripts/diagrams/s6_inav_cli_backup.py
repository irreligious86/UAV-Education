"""Stage 6 diagrams for module inav-cli-backup (INAV 9.1 CLI: diff/dump scopes, backup and restore).

inav-cli-diff-scopes  — which blocks each of `diff`, `diff all`, `diff <one profile>`, `dump`, `dump all`
                        prints (printConfig() in src/main/fc/cli.c, INAV 9.1.0), with the command-line
                        counts of the module's worked example (69 lines in `diff all`, 38 in `diff`).
inav-cli-restore-flow — restore / migration flow: backup with version, edit, flash with full chip erase,
                        paste, error branch, save, verify.
"""
from __future__ import annotations

from svg import ACCENT, DANGER, INK, MUTED, PANEL, WARN, Box, flow, svg, text

# rows: (label, example lines in `diff all`, [diff, diff all, diff <profile>, dump, dump all])
# 1 = printed, 0 = not printed, 2 = printed only for the selected scope
ROWS = [
    ("# version + batch start", 1, [1, 1, 0, 1, 1]),
    ("defaults noreboot", 1, [0, 1, 0, 0, 0]),
    ("feature, serial, aux, servo, osd_layout…", 6, [1, 1, 0, 1, 1]),
    ("# master (set …)", 6, [1, 1, 0, 1, 1]),
    ("control_profile — активный", 5, [1, 1, 2, 1, 1]),
    ("control_profile — остальные 2", 8, [0, 1, 0, 0, 1]),
    ("mixer_profile — активный (+mmix, smix)", 15, [1, 1, 2, 1, 1]),
    ("mixer_profile — второй", 14, [0, 1, 0, 0, 1]),
    ("battery_profile — активный", 3, [1, 1, 2, 1, 1]),
    ("battery_profile — остальные 2", 6, [0, 1, 0, 0, 1]),
    ("возврат выбора профилей (3 строки)", 3, [0, 1, 0, 0, 1]),
    ("save", 1, [1, 1, 0, 1, 1]),
    ("batch end (после save)", 0, [1, 0, 0, 1, 0]),
]
COLS = ["diff", "diff all", "diff X_profile", "dump", "dump all"]


def build(D: dict) -> None:
    x0, y0, lw, cw, rh = 10, 58, 300, 80, 22
    out = [text(x0, 20, "INAV 9.1.0: что печатают diff и dump (printConfig, cli.c)", "b", "start", 13),
           text(x0 + lw - 8, y0 - 10, "строк в примере", "m t", "end", 10)]
    for j, c in enumerate(COLS):
        out.append(text(x0 + lw + j * cw + cw / 2, y0 - 10, c, "b" if c == "diff all" else "", size=10.5))
    total_all = 0
    total_diff = 0
    for i, (label, n, cells) in enumerate(ROWS):
        y = y0 + i * rh
        if i % 2 == 0:
            out.append(f'<rect x="{x0}" y="{y}" width="{lw + cw * len(COLS)}" height="{rh}" fill="{PANEL}"/>')
        out.append(text(x0 + 6, y + 15, label, "t", "start", 10.5))
        out.append(text(x0 + lw - 8, y + 15, str(n) if n else "+1", "m t", "end", 10.5))
        total_all += n
        total_diff += n if cells[0] else 0
        for j, v in enumerate(cells):
            cx, cy = x0 + lw + j * cw + cw / 2, y + rh / 2
            if v == 1:
                colour = ACCENT if j == 1 else INK
                out.append(f'<rect x="{cx - 26}" y="{cy - 6}" width="52" height="12" rx="3" fill="{colour}"/>')
            elif v == 2:
                out.append(f'<rect x="{cx - 26}" y="{cy - 6}" width="52" height="12" rx="3" fill="none" '
                           f'stroke="{WARN}" stroke-width="1.6"/>')
            else:
                out.append(f'<path d="M{cx - 5} {cy} L{cx + 5} {cy}" stroke="{MUTED}" stroke-width="1.4"/>')
    total_diff += 1  # `batch end` is printed after `save` in the non-`all` output
    assert (total_all, total_diff) == (69, 38), (total_all, total_diff)
    yb = y0 + len(ROWS) * rh + 18
    out.append(text(x0, yb, f"Пример модуля: diff all — {total_all} командных строк, diff — {total_diff}. "
                            f"В diff нет {total_all - total_diff + 1} строк из diff all:", "t", "start"))
    out.append(text(x0, yb + 15, "23 строки с настройками неактивных профилей, 5 строк выбора профиля, 3 строки возврата, defaults noreboot.",
                    "w t", "start"))
    out.append(text(x0, yb + 30, "Рамка — печатается только блок, названный в команде (активный профиль), без version, batch и save.",
                    "m t", "start"))
    out.append(text(x0, yb + 45, "Счётчики профилей: control 3, mixer 2 (на F411 — 1), battery 3. Область rates из help не реализована.",
                    "m t", "start"))
    D["inav-cli-diff-scopes"] = svg(720, yb + 58, "INAV 9.1: области diff и dump", "".join(out))

    boxes = [
        Box("bk", ["Старая прошивка:", "diff all → файл"], 10, 40, 150, 44, accent=True),
        Box("ed", ["Копия файла:", "переименовать/убрать"], 200, 40, 160, 44),
        Box("fl", ["Прошивка 9.1 +", "Full chip erase"], 400, 40, 140, 44),
        Box("ps", ["CLI: вставить", "файл целиком"], 580, 40, 130, 44),
        Box("er", ["Есть строки", "### ERROR ?"], 580, 140, 130, 44, accent=True),
        Box("fx", ["Исправить файл,", "defaults, вставить"], 380, 140, 150, 44),
        Box("sv", ["save", "(перезагрузка)"], 580, 240, 130, 44),
        Box("ck", ["Снова diff all,", "сравнить с файлом"], 380, 240, 150, 44, accent=True),
        Box("st", ["status: флаги,", "калибровки, выходы"], 170, 240, 160, 44),
    ]
    links = [
        ("bk", "ed", "", False, "h"),
        ("ed", "fl", "", False, "h"),
        ("fl", "ps", "", False, "h"),
        ("ps", "er", "", False, "v"),
        ("er", "fx", "да", False, "h"),
        ("er", "sv", "нет", True, "v"),
        ("sv", "ck", "", True, "h"),
        ("ck", "st", "", True, "h"),
    ]
    # the "paste again" loop is drawn by hand: flow() would route it over the "да" link
    loop = ('<path class="ln" d="M455 140 L455 104 L562 104 L562 74 L580 74" marker-end="url(#ar)"/>'
            + text(508, 99, "заново", "m t", size=10))
    D["inav-cli-restore-flow"] = flow(
        "INAV: бэкап, перенос на 9.1 и восстановление",
        boxes, links, 720, 350,
        notes=[(10, 108, "Первая строка файла — версия", "m t"),
               (10, 122, "и target: # INAV/TARGET 8.0.1 …", "m t"),
               (10, 306, "batch start в файле: при любой ошибке save откажет и напечатает число ошибок — полусобранный", "a t"),
               (10, 321, "конфиг не сохранится командой save. Но команды выбора профиля пишут EEPROM сами, поэтому", "m t"),
               (10, 336, "после неудачной вставки — defaults, а не exit. Пропы сняты до проверки выходов.", "w t")]
    ).replace("</svg>", loop + "</svg>")
