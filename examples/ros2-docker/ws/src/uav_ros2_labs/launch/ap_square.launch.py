"""Logger + GUIDED square for ArduPilot over AP_DDS (expects micro_ros_agent and SITL with DDS)."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="uav_ros2_labs", executable="telemetry_logger", parameters=[{"source": "ardupilot", "out": "/tmp/ap_flight.csv"}]),
        Node(package="uav_ros2_labs", executable="ap_dds_square", output="screen"),
    ])
