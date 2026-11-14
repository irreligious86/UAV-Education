"""Stage 6 diagrams for per-vision-pipeline: the latency budget of the on-board vision chain and the
geo-referencing error caused by a time offset between the frame and ATTITUDE.

Numbers come from the module's lab: pipeline.py on the synthetic 640x480 @ 30 fps flight (HSV detector,
Kalman tracker, --undistort frame) measured on a 2-core x86 box, the fine-tuned yolo11n run of step 3, and
score.py with --undistort point --att-offset-ms 0 / 50 / 100 (mean and p95 of the ground error on
true-positive frames). The exposure/readout and the
FC link segments are the typical values stated in the module, not measured on this machine.
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import timeline

# measured p50 / p95 per stage, ms (module step 2)
P50 = dict(cap=0.25, und=0.91, det=0.73, trk=0.04, geo=0.07, cmd=0.00)
P95 = dict(cap=0.79, und=1.31, det=1.01, trk=0.08, geo=0.12, cmd=0.00)
EXPOSURE, LINK = 25.0, 8.0          # typical: CSI exposure+readout; MAVLink serial + autopilot update
YOLO_P95 = 29.3                     # yolo11n fine-tuned, imgsz 320, CPU, same machine (p50 25.2)

# time-offset experiment (module step 3): offset ms -> (mean, p95) ground error, m
OFFSET = {0: (0.13, 0.20), 50: (0.34, 0.50), 100: (0.58, 0.85)}
AGL, W_MAX = 15.0, math.hypot(8 * 2 * math.pi * 0.5, 5 * 2 * math.pi * 0.35)   # deg/s, peak attitude rate of the synthetic flight


def build(D: dict) -> None:
    cu = P95["cap"] + P95["und"]                       # capture + undistort
    rest = P95["trk"] + P95["geo"] + P95["cmd"]
    t_end = EXPOSURE + cu + P95["det"] + rest
    D["vision-pipeline-budget"] = timeline(
        "Бюджет задержки glass-to-command, мс (стадии companion — p95 из лабораторной, 2 ядра x86)",
        [("сенсор", [(0, EXPOSURE, "экспозиция + readout, типично 10–30")]),
         ("companion", [(EXPOSURE, t_end, f"захват+undistort {cu:.1f} · HSV {P95['det']:.1f} · трекер+гео {rest:.1f} = {t_end - EXPOSURE:.1f}", True)]),
         ("линк + FC", [(t_end, t_end + LINK, f"MAVLink → FC, типично {LINK:.0f}")])],
        45, marks=[(t_end + LINK, f"команда: {t_end + LINK:.0f} мс (YOLO CPU: {t_end + LINK - P95['det'] + YOLO_P95:.0f})")])

    xs = [0, 25, 50, 75, 100, 125]
    bound = [OFFSET[0][0] + AGL * math.tan(math.radians(W_MAX * x / 1000)) for x in xs]   # baseline + worst-case rate
    D["chart-vision-timesync"] = chart(
        "Ошибка точки на земле от сдвига времени кадр → ATTITUDE (надир, AGL 15 м, вращение до 27 °/с)",
        [dict(name="0.13 + h·tan(ω_max·Δt)", xs=xs, ys=bound, cls="m", dash=True),
         dict(name="p95 измерено", xs=list(OFFSET), ys=[v[1] for v in OFFSET.values()], cls="d"),
         dict(name="", xs=list(OFFSET), ys=[v[1] for v in OFFSET.values()], cls="d", dots=True),
         dict(name="среднее измерено", xs=list(OFFSET), ys=[v[0] for v in OFFSET.values()], cls="a"),
         dict(name="", xs=list(OFFSET), ys=[v[0] for v in OFFSET.values()], cls="a", dots=True)],
        Axis("сдвиг времени, мс", 0, 125), Axis("ошибка на земле, м", 0, 1.2),
        hmarks=[(0.13, "0 мс: 0.13 м — пиксель, AGL 10 Гц, интерполяция ATTITUDE", "m")],
        notes=[(80, 60, "100 мс сдвига = 0.58 м в среднем, 0.85 м p95;", "m"),
               (80, 76, "пиксель на 15 м — 4 см. Время важнее камеры.", "m")])
