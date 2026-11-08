"""Camera geometry for UAV perception labs (numpy only).

Frames (all right-handed):
  NED   world: x North, y East, z Down
  FRD   body:  x Forward, y Right, z Down          (ArduPilot/PX4 convention)
  CAM   camera optical frame: x right in image, y down in image, z along the optical axis (OpenCV)

Chain for a pixel: pixel --K^-1, undistort--> ray in CAM --R_bc--> ray in FRD --R_nb(roll,pitch,yaw)--> ray in NED
--intersect with ground plane z = +altitude below the camera--> ground point in NED relative to the vehicle.
"""
from __future__ import annotations

import math

import numpy as np


# ---------------------------------------------------------------- rotations
def rot_x(a): c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def rot_y(a): c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def rot_z(a): c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def R_nb(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Body (FRD) -> NED for aerospace ZYX Euler angles in radians."""
    return rot_z(yaw) @ rot_y(pitch) @ rot_x(roll)


def R_bc_for_mount(tilt_deg: float) -> np.ndarray:
    """Camera optical frame -> body FRD for a camera on the nose, pitched DOWN by tilt_deg.
    tilt 0: looks forward (optical z = body x); tilt 90: looks straight down (optical z = body z).
    At tilt 0, image-right = body right (y), image-down = body down (z)."""
    base = np.array([[0, 0, 1],      # body x  <- cam z
                     [1, 0, 0],      # body y  <- cam x
                     [0, 1, 0]])     # body z  <- cam y
    return rot_y(-math.radians(tilt_deg)) @ base


# ---------------------------------------------------------------- intrinsics and distortion
def K_matrix(fx: float, fy: float, cx: float, cy: float) -> np.ndarray:
    return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])


def fx_from_hfov(width_px: int, hfov_deg: float) -> float:
    """Focal length in pixels from horizontal field of view: fx = (W/2) / tan(HFOV/2)."""
    return (width_px / 2) / math.tan(math.radians(hfov_deg) / 2)


def distort(xn: np.ndarray, yn: np.ndarray, k1: float = 0.0, k2: float = 0.0):
    """Radial (Brown) distortion of normalised image coordinates."""
    r2 = xn * xn + yn * yn
    f = 1 + k1 * r2 + k2 * r2 * r2
    return xn * f, yn * f


def undistort(xd: float, yd: float, k1: float = 0.0, k2: float = 0.0, iters: int = 20):
    """Invert radial distortion by fixed-point iteration (what cv2.undistortPoints does for this model)."""
    x, y = xd, yd
    for _ in range(iters):
        r2 = x * x + y * y
        f = 1 + k1 * r2 + k2 * r2 * r2
        x, y = xd / f, yd / f
    return x, y


def project(p_cam: np.ndarray, K: np.ndarray, k1: float = 0.0, k2: float = 0.0) -> tuple[float, float]:
    """3D point in the camera frame -> pixel (u, v). Point must be in front of the camera (z > 0)."""
    if p_cam[2] <= 0:
        raise ValueError("point is behind the camera")
    xn, yn = p_cam[0] / p_cam[2], p_cam[1] / p_cam[2]
    xd, yd = distort(np.float64(xn), np.float64(yn), k1, k2)
    return float(K[0, 0] * xd + K[0, 2]), float(K[1, 1] * yd + K[1, 2])


def pixel_ray_cam(u: float, v: float, K: np.ndarray, k1: float = 0.0, k2: float = 0.0) -> np.ndarray:
    """Pixel -> unit ray in the camera frame."""
    xd = (u - K[0, 2]) / K[0, 0]
    yd = (v - K[1, 2]) / K[1, 1]
    x, y = undistort(xd, yd, k1, k2)
    r = np.array([x, y, 1.0])
    return r / np.linalg.norm(r)


# ---------------------------------------------------------------- pixel -> ground
def pixel_to_ground(u: float, v: float, K: np.ndarray, roll: float, pitch: float, yaw: float, alt: float,
                    R_bc: np.ndarray | None = None, k1: float = 0.0, k2: float = 0.0) -> np.ndarray | None:
    """Ground point (N, E) in metres relative to the point under the camera, flat ground `alt` metres below.
    Returns None when the ray does not hit the ground (points at or above the horizon)."""
    R_bc = R_bc if R_bc is not None else R_bc_for_mount(90.0)
    ray_ned = R_nb(roll, pitch, yaw) @ R_bc @ pixel_ray_cam(u, v, K, k1, k2)
    if ray_ned[2] <= 1e-9:
        return None
    t = alt / ray_ned[2]
    return (ray_ned * t)[:2]


def ground_to_pixel(n: float, e: float, K: np.ndarray, roll: float, pitch: float, yaw: float, alt: float,
                    R_bc: np.ndarray | None = None, k1: float = 0.0, k2: float = 0.0) -> tuple[float, float]:
    """Inverse of pixel_to_ground: ground point (N, E, ground at +alt) -> pixel. Used for synthetic checks."""
    R_bc = R_bc if R_bc is not None else R_bc_for_mount(90.0)
    p_ned = np.array([n, e, alt])
    p_cam = (R_nb(roll, pitch, yaw) @ R_bc).T @ p_ned
    return project(p_cam, K, k1, k2)


# ---------------------------------------------------------------- survey helpers
def gsd_cm(alt_m: float, sensor_width_mm: float, focal_mm: float, image_width_px: int) -> float:
    """Ground sample distance at nadir, cm/pixel."""
    return alt_m * sensor_width_mm / (focal_mm * image_width_px) * 100.0


def footprint_m(alt_m: float, hfov_deg: float, vfov_deg: float) -> tuple[float, float]:
    """Ground footprint (across, along) at nadir over flat ground."""
    return (2 * alt_m * math.tan(math.radians(hfov_deg) / 2), 2 * alt_m * math.tan(math.radians(vfov_deg) / 2))


def survey_spacing(alt_m: float, hfov_deg: float, vfov_deg: float, side_overlap: float, front_overlap: float):
    """Line spacing and trigger distance for the requested overlaps (fractions 0..1)."""
    across, along = footprint_m(alt_m, hfov_deg, vfov_deg)
    return across * (1 - side_overlap), along * (1 - front_overlap)


# ---------------------------------------------------------------- landing target
def landing_target_angles(u: float, v: float, K: np.ndarray, k1: float = 0.0, k2: float = 0.0) -> tuple[float, float]:
    """LANDING_TARGET angle_x / angle_y (rad) for a downward camera: angular offset of the target from the
    optical axis along the image x and y axes (MAVLink defines them in the sensor frame)."""
    r = pixel_ray_cam(u, v, K, k1, k2)
    return math.atan2(r[0], r[2]), math.atan2(r[1], r[2])
