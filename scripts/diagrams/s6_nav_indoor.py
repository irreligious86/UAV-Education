"""Stage 6 diagrams for nav-indoor: external-nav sources into EKF3, and the lag sweep.

Numbers in the chart are the module's own SITL runs (ArduCopter 4.6.3, VISION_POSITION_ESTIMATE from
SITL truth, noise 2 cm, 30 Hz, square 4 m at 1.5 m/s): p95 / max horizontal error of XKF1 against truth
for each uncompensated lag (transport lag minus VISO_DELAY_MS).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

# (uncompensated lag ms, p95 error m, max error m) from runs lag/VISO_DELAY_MS 50/50, 150/50, 250/50, 300/50, 600/250 (analyze.py, XKF1 vs SIM)
RUNS = [(0, 0.029, 0.044), (100, 0.242, 0.280), (200, 0.514, 0.644), (250, 0.785, 0.915), (350, 3.113, 3.865)]
V = 1.5  # m/s, WPNAV_SPEED in the runs


def build(D: dict) -> None:
    xs = [r[0] for r in RUNS[:4]]
    D["chart-nav-indoor-lag"] = chart(
        "Ошибка позиции EKF3 от нескомпенсированной задержки внешней навигации (SITL, 1.5 м/с)",
        [dict(name="модель v·τ", xs=[0, 400], ys=[0, V * 0.4], cls="m", dash=True, label_at=400, label_dy=-6),
         dict(name="p95 ошибки", xs=xs, ys=[r[1] for r in RUNS[:4]], cls="a", label_at=250, label_dy=22, label_anchor="start"),
         dict(name="", xs=xs, ys=[r[1] for r in RUNS[:4]], cls="a", dots=True),
         dict(name="max", xs=xs, ys=[r[2] for r in RUNS[:4]], cls="w", label_at=250, label_dy=-10),
         dict(name="", xs=xs, ys=[r[2] for r in RUNS[:4]], cls="w", dots=True)],
        Axis("задержка − VISO_DELAY_MS, мс", 0, 400), Axis("ошибка XKF1 к истине, м", 0, 1.2),
        marks=[(350, "350 мс", "d", 240)],
        notes=[(80, 60, "350 мс (600 / 250): p95 3.1 м, max 3.9 м, колебания Loiter", "d"),
               (80, 74, "550 мс (600 / 50): XKF4.SP до 5.7, «EKF variance», failsafe LAND, до 46 м", "d"),
               (80, 100, "0 мс: задержка 50 / VISO_DELAY_MS 50 и 250 / 250 — одинаково, 3–5 см", "m")])

    D["nav-indoor-sources"] = flow(
        "Пути внешней навигации в EKF3 ArduPilot 4.6: сообщение → драйвер → EK3_SRC",
        [Box("mocap", ["Mocap / VIO", "OptiTrack, Vicon, T265"], 10, 20, 140, accent=True),
         Box("uwb", ["UWB-тег", "Pozyx, Nooploop"], 10, 110, 140, accent=True),
         Box("flow", ["Поток + дальномер", "PMW3901, TFmini"], 10, 200, 140, accent=True),
         Box("gpsin", ["Псевдо-GPS", "lat/lon из mocap"], 10, 290, 140),
         Box("vpe", ["VISION_POSITION_ESTIMATE", "ODOMETRY (FRD), /ap/tf"], 185, 20, 215),
         Box("ser13", ["SERIALx_PROTOCOL 13", "node_frame2, IndoorLoiter"], 185, 110, 215),
         Box("flowmsg", ["FLOW_TYPE 1/5/6/7", "RNGFND1_TYPE, ORIENT 25"], 185, 200, 215),
         Box("gpsmsg", ["GPS_INPUT", "GPS1_TYPE 14, yaw в cdeg"], 185, 290, 215),
         Box("viso", ["AP_VisualOdom", "VISO_TYPE 1, DELAY_MS"], 440, 20, 150),
         Box("bcn", ["AP_Beacon", "BCN_TYPE 1/2/3, ≤4 якоря"], 440, 110, 150),
         Box("of", ["AP_OpticalFlow", "FXSCALER, EK3_FLOW_*"], 440, 200, 150),
         Box("gps", ["AP_GPS", "GPS1_DELAY_MS"], 440, 290, 150),
         Box("ekf", ["EKF3 SRC", "POSXY 6/4/0/3", "VELXY 6/0/5/3", "YAW 6/1/1/2"], 625, 110, 90, 120, accent=True)],
        [("mocap", "vpe"), ("uwb", "ser13"), ("flow", "flowmsg"), ("gpsin", "gpsmsg"),
         ("vpe", "viso"), ("ser13", "bcn"), ("flowmsg", "of"), ("gpsmsg", "gps"),
         ("viso", "ekf", "", True), ("bcn", "ekf", "", True), ("of", "ekf", "", True), ("gps", "ekf", "", True)],
        720, 360)
