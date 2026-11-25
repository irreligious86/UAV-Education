"""Stage 6 diagrams for module bf-led-buzzer (Betaflight 4.5 LED strip, io/ledstrip.c).

bf-led-grid-layout  — the module's lab layout (10 LEDs, `led 0 1,1:NW:FW:0` ... `led 9 8,8::LW:0`) on the 16x16
                      grid, coloured exactly as the lab computed for STATUS / disarmed / battery 100 %
                      (NW, NE -> WHITE; "SE" -> E bit first -> DARK_VIOLET; SW -> RED; L -> green), with the data
                      chain in strip order and the quadrant split from updateDimensions() (x <= 7 west, y <= 7 north).
chart-bf-led-current — lab step 3b: strip current vs ledstrip_brightness for 10 and 32 LEDs at full white and for the
                      STATUS layout (380 mA at 100 %), model 20 mA per channel at 255; line = 1.1 A left on a 2 A FC BEC
                      after 0.9 A of other 5 V loads (the module's example budget).
bf-buzzer-find-tree  — theory "Найти упавший аппарат": what can still beep after a crash (2025.12, 4.5 difference in
                      the leaf), from flight/failsafe.c (RX_LOST: no RC data and no USB; 4.5: armed or WAS_EVER_ARMED),
                      io/beeper.c (DShot beacon gate: 1.2 s after disarm, RX_SET beacon only with a live link in
                      2025.12), drivers/usb_io.c (USB = detect pin OR VCP connected) and the Bluejay beacon-delay
                      row of f-esc-firmware (own leaf: needs only battery + DShot frames); lab2 section 4 reproduces the leaves.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Node, svg, text, tree

# lab output (bf-led-buzzer.led_lab.py, step 1 and step 3): (x, y, functions, rgb)
LEDS = [
    (1, 1, "FW", (255, 255, 255)), (2, 2, "FW", (255, 255, 255)),
    (13, 2, "FW", (255, 255, 255)), (14, 1, "FW", (255, 255, 255)),
    (14, 14, "FW", (127, 0, 255)), (13, 13, "FW", (127, 0, 255)),
    (2, 13, "FW", (255, 0, 0)), (1, 14, "FW", (255, 0, 0)),
    (7, 8, "LW", (0, 255, 0)), (8, 8, "LW", (0, 255, 0)),
]


OFFS = [(-10, -9), (10, 16), (-10, 16), (-10, -9), (-10, 17), (-10, -9), (10, -9), (-10, 17), (-12, -10), (12, -10)]


def _grid() -> str:
    cell, ox, oy = 17, 70, 46
    out = [text(10, 22, "LED-раскладка лабораторной: сетка 16×16, порядок по проводу, цвета STATUS", "b", "start", 13)]
    for i in range(16):
        out.append(text(ox + i * cell + cell / 2, oy - 6, str(i), "m t"))
        out.append(text(ox + 16 * cell + 4, oy + i * cell + cell / 2 + 4, str(i), "m t", "start"))
        for j in range(16):
            out.append(f'<rect x="{ox + i * cell}" y="{oy + j * cell}" width="{cell}" height="{cell}" fill="none" '
                       f'stroke="currentColor" stroke-width="0.25" opacity="0.5"/>')
    out.append(text(ox + 8 * cell, oy + 16 * cell + 16, "x →  (y ↓, север сверху)", "m t"))
    mid = ox + 8 * cell
    out.append(f'<line x1="{mid}" y1="{oy}" x2="{mid}" y2="{oy + 16 * cell}" class="lnm"/>')
    out.append(f'<line x1="{ox}" y1="{oy + 8 * cell}" x2="{ox + 16 * cell}" y2="{oy + 8 * cell}" class="lnm"/>')
    pts = [(ox + x * cell + cell / 2, oy + y * cell + cell / 2) for x, y, _, _ in LEDS]
    path = " ".join(f"{'M' if k == 0 else 'L'}{px:.1f} {py:.1f}" for k, (px, py) in enumerate(pts))
    out.append(f'<path d="M{ox - 62} {pts[0][1] + 40:.1f} L{ox - 62} {pts[0][1]:.1f} L{pts[0][0] - 9:.1f} {pts[0][1]:.1f}" '
               f'class="ln" marker-end="url(#ar)"/>')
    out.append(text(ox - 60, pts[0][1] + 54, "DIN от FC", "t", "start"))
    out.append(f'<path d="{path}" class="lna" opacity="0.7"/>')
    for k, ((x, y, fn, (r, g, b)), (px, py)) in enumerate(zip(LEDS, pts)):
        out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="rgb({r},{g},{b})" stroke="currentColor" stroke-width="1"/>')
        dx, dy = OFFS[k]
        out.append(text(px + dx, py + dy, f"{k}:{fn}", "t", "end" if dx < 0 else "start"))
    tx = ox + 16 * cell + 30
    notes = [
        ("a b", "Что видно"),
        ("t", "0–3 смотрят NW/NE → цвет N = WHITE"),
        ("t", "6–7: SW → цвет S = RED"),
        ("w t", "4–5: набрано «SE», а прошивка берёт"),
        ("w t", "первый бит в порядке N,E,S,W,U,D →"),
        ("w t", "E = DARK_VIOLET (`led` печатает ES)"),
        ("t", "8–9: L = заряд, 100 % → зелёный"),
        ("t", "W на всех: мигание предупреждений"),
        ("m t", "Пунктир: деление на стороны из"),
        ("m t", "updateDimensions(): x ≤ 7 — запад,"),
        ("m t", "y ≤ 7 — север (для I и стрелок)"),
        ("t", "Ток (модель): 380 мА при яркости 100 %"),
        ("t", "led 10 0,0::C:0 = 0 → конец ленты"),
    ]
    for i, (cls, s) in enumerate(notes):
        out.append(text(tx, oy + 10 + i * 19, s, cls, "start"))
    return svg(720, oy + 16 * cell + 30, "LED-раскладка лабораторной bf-led-buzzer", "".join(out))


def _find_tree() -> str:
    usb = Node("usb", ["FC видит USB?", "(VCP или", "пин detect)"], [
        ("да", Node("mute", ["RX_LOST молчит", "(2025.12)"], leaf=True)),
        ("нет", Node("lost", ["RX_LOST 0.5/0.5 с", "через failsafe_", "delay (4.5 — после", "арма); моторы", "≥ 1.2 с после", "дизарма"], leaf=True, accent=True)),
    ])
    link = Node("link", ["FC жив, пульт", "на связи?"], [
        ("да", Node("set", ["Тумблер BEEPER:", "RX_SET 0.1/0.1 с,", "лента 4 Гц,", "моторы при", "beacon RX_SET"], leaf=True)),
        ("нет", usb),
    ])
    root = Node("root", ["Аппарат упал:", "что ещё пищит?"], [
        ("батарея отлетела", Node("self", ["Только", "автономная", "пищалка со", "своей ячейкой"], leaf=True, accent=True)),
        ("на месте", link),
        ("+ DShot", Node("blj", ["Маяк Bluejay", "(батарея + DShot", "от FC): через", "beacon delay;", "от пульта и USB", "не зависит"], leaf=True)),
    ])
    return tree("Поиск упавшего аппарата, Betaflight 2025.12", root, width=720, box_w=134, box_h=86, gap_y=118)


def build(D: dict) -> None:
    D["bf-led-grid-layout"] = _grid()
    D["bf-buzzer-find-tree"] = _find_tree()

    br = list(range(5, 101, 5))

    def white(n, b):          # ws2811UpdateStrip: v = 255 * b / 100 (integer), 3 channels x 20 mA at 255
        v = 255 * b // 100
        return n * 3 * v / 255 * 20

    def status(b):            # lab layout: 4 white + 2 violet (382/255) + 2 red + 2 green channel sums
        v = 255 * b // 100
        return (4 * 3 * v + 2 * (v * 30 // 60 + v) + 4 * v) / 255 * 20   # violet hue 270: r = v*30/60, b = v

    D["chart-bf-led-current"] = chart(
        "Ток ленты по модели лабораторной: 20 мА на канал при 255",
        [dict(name="32 LED, белый", xs=br, ys=[white(32, b) for b in br], cls="d", label_at=60, label_dy=-8),
         dict(name="10 LED, белый", xs=br, ys=[white(10, b) for b in br], cls="w", label_at=85, label_dy=-8),
         dict(name="раскладка STATUS", xs=br, ys=[status(b) for b in br], cls="a", label_at=95, label_dy=16)],
        Axis("ledstrip_brightness, %", 0, 100), Axis("ток, мА", 0, 2000, ticks=[0, 400, 800, 1100, 1600, 2000]),
        hmarks=[(1100, "запас BEC 2 А − 0.9 А прочих = 1.1 А", "m")],
        marks=[(30, "30 %: 32 LED = 572 мА", "a", 100)],
        notes=[(72, 58, "Ток ∝ яркости: прошивка умножает V на brightness/100, драйвер светодиода — ШИМ.", "m"),
               (72, 74, "32 белых на 100 % (1.92 А) не помещаются в BEC платы — нужен свой 5 В.", "d")])
