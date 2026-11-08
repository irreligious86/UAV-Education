"""mav-component lab: the virtual rangefinder is seen by the vehicle as DISTANCE_SENSOR from its own compid."""
import time

from pymavlink import mavutil

from virtual_rangefinder import VirtualRangefinder

M = mavutil.mavlink


def test_rangefinder_reaches_vehicle(vehicle_factory):
    v, port = vehicle_factory()
    rf = VirtualRangefinder(f"udpout:127.0.0.1:{port}")
    rf.heartbeat()
    rf.alt_m = 5.0
    for _ in range(20):
        rf.send(rf.measurement_cm(rf.alt_m, time.time()))
        time.sleep(0.02)
    time.sleep(0.2)
    assert len(v.distance_sensor) >= 10
    msg = v.distance_sensor[-1]
    assert msg.get_srcComponent() == M.MAV_COMP_ID_PERIPHERAL
    assert msg.orientation == M.MAV_SENSOR_ROTATION_PITCH_270
    assert 430 <= msg.current_distance <= 540        # 5 m minus fake terrain ±0.3 m, ±noise


def test_rangefinder_clamps_to_limits():
    rf = VirtualRangefinder.__new__(VirtualRangefinder)
    rf.noise_cm = 0
    assert rf.measurement_cm(-1.0, 0.0) == VirtualRangefinder.MIN_CM
    assert rf.measurement_cm(100.0, 0.0) == VirtualRangefinder.MAX_CM
