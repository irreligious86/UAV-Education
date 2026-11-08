"""Logger + offboard square for PX4 (expects MicroXRCEAgent and PX4 SITL running)."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="uav_ros2_labs", executable="telemetry_logger", parameters=[{"source": "px4", "out": "/tmp/px4_flight.csv"}]),
        Node(package="uav_ros2_labs", executable="px4_offboard_square", parameters=[{"alt": 5.0, "side": 10.0}], output="screen"),
    ])
