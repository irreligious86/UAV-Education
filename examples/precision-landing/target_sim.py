"""Synthetic landing-target camera for SITL without Gazebo (project #5 starter).

Given the vehicle state (local NED position, attitude, height above ground) and a marker position on the
ground, produce what a downward camera + detector would output: pixel of the marker centre, its size in
pixels, LANDING_TARGET angles — with detection range limits, noise, dropouts and camera latency.
The camera model is examples/perception/camgeo.py.
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "perception"))
import camgeo as cg  # noqa: E402


@dataclass
class Camera:
    width: int = 640
    height: int = 480
    hfov_deg: float = 70.0
    latency_s: float = 0.06          # exposure -> detection result
    min_marker_px: float = 20.0      # smaller than this: detector does not find the marker

    @property
    def K(self):
        f = cg.fx_from_hfov(self.width, self.hfov_deg)
        return cg.K_matrix(f, f, self.width / 2, self.height / 2)


@dataclass
class Detection:
    t_exposure: float
    u: float
    v: float
    size_px: float
    angle_x: float
    angle_y: float
    distance: float


class TargetSim:
    def __init__(self, marker_ne=(0.0, 0.0), marker_size_m: float = 0.5, camera: Camera | None = None,
                 noise_px: float = 0.5, dropout: float = 0.0, seed: int = 0):
        self.marker_ne = marker_ne
        self.marker_size = marker_size_m
        self.cam = camera or Camera()
        self.noise_px = noise_px
        self.dropout = dropout
        self.rng = random.Random(seed)

    def detect(self, t: float, pos_ned, roll: float, pitch: float, yaw: float, hagl: float) -> Detection | None:
        """Detection for an exposure at time t, or None (out of frame, too small, dropout, too low)."""
        if hagl <= 0.05 or (self.dropout and self.rng.random() < self.dropout):
            return None
        n = self.marker_ne[0] - pos_ned[0]
        e = self.marker_ne[1] - pos_ned[1]
        K = self.cam.K
        try:
            u, v = cg.ground_to_pixel(n, e, K, roll, pitch, yaw, hagl)
        except ValueError:
            return None
        if not (0 <= u < self.cam.width and 0 <= v < self.cam.height):
            return None
        slant = math.sqrt(n * n + e * e + hagl * hagl)
        size_px = K[0, 0] * self.marker_size / slant
        if size_px < self.cam.min_marker_px:
            return None
        u += self.rng.gauss(0, self.noise_px)
        v += self.rng.gauss(0, self.noise_px)
        ax, ay = cg.landing_target_angles(u, v, K)
        return Detection(t, u, v, size_px, ax, ay, slant)

    def capture_range(self) -> float:
        """Max slant distance at which the marker is still >= min_marker_px."""
        return self.cam.K[0, 0] * self.marker_size / self.cam.min_marker_px
