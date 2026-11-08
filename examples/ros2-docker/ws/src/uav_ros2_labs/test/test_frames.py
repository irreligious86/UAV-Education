import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uav_ros2_labs import frames as F  # noqa: E402


def close(a, b, eps=1e-9):
    return all(abs(x - y) < eps for x, y in zip(a, b))


def test_vector_maps_are_involutions():
    for _ in range(100):
        v = tuple(random.uniform(-10, 10) for _ in range(3))
        assert close(F.enu_to_ned(F.ned_to_enu(v)), v)
        assert close(F.flu_to_frd(F.frd_to_flu(v)), v)


def test_altitude_sign():
    # 10 m above origin: NED z = -10, ENU z = +10
    assert F.ned_to_enu((0, 0, -10))[2] == 10


def test_yaw_mapping():
    assert abs(F.yaw_ned_to_enu(0.0) - math.pi / 2) < 1e-12           # facing north
    assert abs(F.yaw_ned_to_enu(math.pi / 2) - 0.0) < 1e-12           # facing east
    for _ in range(100):
        y = random.uniform(-math.pi, math.pi)
        assert abs(F.wrap_pi(F.yaw_enu_to_ned(F.yaw_ned_to_enu(y)) - y)) < 1e-9


def test_attitude_conversion_matches_yaw_and_level():
    for _ in range(200):
        yaw = random.uniform(-math.pi, math.pi)
        q_ned = F.euler_to_q(0.0, 0.0, yaw)
        r, p, y = F.q_to_euler(F.q_ned_frd_to_enu_flu(q_ned))
        assert abs(r) < 1e-9 and abs(p) < 1e-9
        assert abs(F.wrap_pi(y - F.yaw_ned_to_enu(yaw))) < 1e-9


def test_attitude_conversion_roll_sign():
    # right wing down in FRD/NED (roll +0.3) is right wing down in FLU/ENU as well: roll about forward axis
    # FLU's y points left, so right-wing-down is a positive rotation about x in FLU too, same sign.
    r, p, y = F.q_to_euler(F.q_ned_frd_to_enu_flu(F.euler_to_q(0.3, 0.0, 0.0)))
    assert abs(r - 0.3) < 1e-9
    # nose up in FRD is pitch +0.2; in FLU nose up is a negative rotation about y (y points left)
    r, p, y = F.q_to_euler(F.q_ned_frd_to_enu_flu(F.euler_to_q(0.0, 0.2, 0.0)))
    assert abs(p + 0.2) < 1e-9


def test_ros_order():
    assert F.ros_xyzw((1, 2, 3, 4)) == (2, 3, 4, 1)
