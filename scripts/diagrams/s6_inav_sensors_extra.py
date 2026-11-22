"""Stage 6 diagrams for module inav-sensors-extra (INAV 9.1.0: rangefinder, optical flow, pitot, temperature).

inav-sensors-extra-flow     — which sensor feeds which state of the INAV position estimator and which
                              consumer, with the gates the code applies (sensors/rangefinder.c,
                              navigation_pos_estimator*.c, sensors/opflow.c, sensors/pitotmeter.c).
chart-inav-airspeed-dp      — indicated airspeed against differential pressure,
                              v = pitot_scale * sqrt(2 * |dP| / 1.225) (sensors/pitotmeter.c, SSL_AIR_DENSITY),
                              for pitot_scale 1.0 and 1.08 — the module's worked example (245 Pa -> 20.0 / 21.6 m/s).
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Box, flow

RHO = 1.225          # SSL_AIR_DENSITY, kg/m^3 (common/maths.h)
DP_EXAMPLE = 245.0   # Pa, practice step 2
SCALE_NEW = 1.08     # pitot_scale after the two-way GPS run of step 2


def airspeed(dp: float, scale: float = 1.0) -> float:
    return scale * math.sqrt(2.0 * abs(dp) / RHO)


def build(D: dict) -> None:
    boxes = [
        Box("rf", ["Дальномер", "см, −1 вне диапазона"], 10, 40, 150, 44, accent=True),
        Box("of", ["Оптический поток", "счёт за Δt, качество"], 10, 120, 150, 44, accent=True),
        Box("ba", ["Барометр"], 10, 200, 150, 36),
        Box("gp", ["GPS", "позиция, скорость"], 10, 256, 150, 44),
        Box("pt", ["Пито / VIRTUAL", "ΔP, Па"], 10, 336, 150, 44, accent=True),
        Box("agl", ["AGL: высота и V_z", "над поверхностью"], 270, 40, 170, 44, accent=True),
        Box("xy", ["XY: скорость", "и позиция"], 270, 120, 170, 44),
        Box("z", ["Z: высота и V_z", "от точки взлёта"], 270, 216, 170, 44),
        Box("ias", ["Воздушная скорость", "IAS, см/с"], 270, 336, 170, 44, accent=True),
        Box("c1", ["SURFACE, детектор", "посадки, flare крыла"], 540, 40, 170, 44),
        Box("c2", ["POSHOLD без GPS", "(dead reckoning)"], 540, 120, 170, 44),
        Box("c3", ["ALTHOLD, RTH,", "миссии"], 540, 216, 170, 44),
        Box("c4", ["APA, координация", "разворота, OSD"], 540, 336, 170, 44),
    ]
    links = [
        ("rf", "agl", "× cos наклона", True, "h"),
        ("of", "xy", "(поток − гиро) × h", True, "h"),
        ("ba", "z", "", False, "h"),
        ("gp", "z", "", False, "h"),
        ("pt", "ias", "√(2ΔP / 1.225)", True, "h"),
        ("agl", "c1", "", True, "h"),
        ("xy", "c2", "", False, "h"),
        ("z", "c3", "", False, "h"),
        ("ias", "c4", "", True, "h"),
    ]
    extra = (
        # rangefinder height is the lever arm of the flow measurement
        '<path class="lna" d="M85 84 L85 120" marker-end="url(#ara)"/>'
        # baro validity gates the AGL estimate; Z feeds the AGL offset
        '<path class="lnm" d="M425 216 L425 84" marker-end="url(#ar)"/>'
        # GPS position and velocity into XY
        '<path class="ln" d="M160 290 L240 290 L240 150 L270 150" marker-end="url(#ar)"/>'
    )
    D["inav-sensors-extra-flow"] = flow(
        "INAV 9.1.0: какой датчик питает какое состояние оценщика",
        boxes, links, 720, 470,
        notes=[
            (95, 106, "h", "a t"),
            (446, 194, "Z и баро", "m t"), (446, 207, "нужны AGL", "m t"),
            (10, 406, "Ворота дальномера: наклон не больше половины конуса датчика; 0 ≤ высота ≤ inav_max_surface_altitude;", "a t"),
            (10, 421, "надёжность ≥ 0.75 для AGL и ≥ 0.33 для потока; без исправного барометра AGL не считается вовсе.", "a t"),
            (10, 436, "Поток работает только пока GPS по XY недостоверен; позиция по потоку — только при inav_allow_dead_reckoning = ON.", "m t"),
            (10, 451, "Воздушная скорость в оценщик позиции не входит: она нужна PID (apa_pow), развороту, оценке позиции без GPS и OSD.", "m t"),
            (10, 466, "Высота AGL не подмешивается в Z: это отдельная оценка, её читают SURFACE и посадка.", "w t"),
        ],
    ).replace("</svg>", extra + "</svg>")

    xs = [i * 5.0 for i in range(0, 161)]            # 0…800 Pa
    v1 = [airspeed(p) for p in xs]
    v2 = [airspeed(p, SCALE_NEW) for p in xs]
    v_ex = airspeed(DP_EXAMPLE)                      # 20.0 m/s
    v_ex2 = airspeed(DP_EXAMPLE, SCALE_NEW)          # 21.6 m/s
    assert abs(v_ex - 20.0) < 1e-9 and abs(v_ex2 - 21.6) < 1e-9
    dp_10, dp_30 = RHO * 10 ** 2 / 2, RHO * 30 ** 2 / 2   # 61.25 and 551.25 Pa
    D["chart-inav-airspeed-dp"] = chart(
        "Воздушная скорость по перепаду давления: v = pitot_scale × √(2ΔP / 1.225)",
        [
            dict(xs=xs, ys=v1, cls="a"),
            dict(xs=xs, ys=v2, cls="w", dash=True),
            dict(xs=[dp_10, DP_EXAMPLE, dp_30], ys=[10.0, v_ex, 30.0], cls="ink", dots=True),
            dict(xs=[DP_EXAMPLE], ys=[v_ex2], cls="w", dots=True),
        ],
        Axis("перепад давления ΔP = |P − P₀|, Па", 0, 800), Axis("воздушная скорость, м/с", 0, 40),
        marks=[(DP_EXAMPLE, "245 Па", "ink", 14)],
        hmarks=[(v_ex, "", "a")],
        legend=[("pitot_scale = 1.0", "a", False), (f"pitot_scale = {SCALE_NEW}", "w", True)],
        legend_at=(470, 236),
        notes=[
            (266, 192, f"245 Па → {v_ex:.1f} м/с; со шкалой {SCALE_NEW} → {v_ex2:.1f} м/с", ""),
            (124, 260, f"10 м/с — всего {dp_10:.1f} Па", "m"),
            (506, 126, f"30 м/с — {dp_30:.0f} Па", "m"),
            (270, 286, "Скорость ×2 — давление ×4: на малых скоростях", "m"),
            (270, 300, "сигнал тонет в шуме и в ошибке нуля P₀.", "m"),
        ])
