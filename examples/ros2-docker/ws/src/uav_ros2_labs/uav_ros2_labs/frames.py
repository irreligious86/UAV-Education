"""Frame conversions between the autopilot world (NED / FRD) and ROS (ENU / FLU, REP-103).

No ROS imports: tested with plain pytest. Quaternions are (w, x, y, z) here; ROS messages
store (x, y, z, w) — convert at the message boundary, not inside the math.
"""
from __future__ import annotations

import math

SQRT1_2 = math.sqrt(0.5)


def ned_to_enu(v):
    """Position/velocity vector NED -> ENU."""
    n, e, d = v
    return (e, n, -d)


def enu_to_ned(v):
    e, n, u = v
    return (n, e, -u)


def frd_to_flu(v):
    """Body vector FRD -> FLU."""
    x, y, z = v
    return (x, -y, -z)


flu_to_frd = frd_to_flu          # the map is its own inverse


def yaw_ned_to_enu(yaw_ned: float) -> float:
    """Heading from north clockwise (NED) -> angle from east counter-clockwise (ENU), wrapped to (-pi, pi]."""
    return wrap_pi(math.pi / 2 - yaw_ned)


yaw_enu_to_ned = yaw_ned_to_enu  # also an involution


def wrap_pi(a: float) -> float:
    a = math.fmod(a + math.pi, 2 * math.pi)
    if a <= 0:
        a += 2 * math.pi
    return a - math.pi


def q_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


# Fixed rotations: NED->ENU world frame swap and FRD->FLU body frame flip
Q_NED_TO_ENU = (0.0, SQRT1_2, SQRT1_2, 0.0)      # 180 deg about the (1,1,0)/sqrt2 axis
Q_FRD_TO_FLU = (0.0, 1.0, 0.0, 0.0)              # 180 deg about x


def q_ned_frd_to_enu_flu(q):
    """Attitude of body FRD in world NED -> attitude of body FLU in world ENU (as px4_ros_com does)."""
    return q_mul(q_mul(Q_NED_TO_ENU, q), Q_FRD_TO_FLU)


def q_to_euler(q):
    """ZYX Euler (roll, pitch, yaw) from (w, x, y, z)."""
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


def euler_to_q(roll, pitch, yaw):
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy)


def ros_xyzw(q):
    """(w, x, y, z) -> ROS geometry_msgs order (x, y, z, w)."""
    return (q[1], q[2], q[3], q[0])
