"""ros2-basics lab: subscribe to vehicle pose (PX4 or ArduPilot) and write a CSV at a fixed rate.

  ros2 run uav_ros2_labs telemetry_logger --ros-args -p source:=px4 -p out:=flight.csv
  ros2 run uav_ros2_labs telemetry_logger --ros-args -p source:=ardupilot

Demonstrates: parameters, QoS for sensor data, a timer decoupled from message rate, and why the
stored frame (ENU for ROS) must be written into the file header.
"""
from __future__ import annotations

import csv

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data

from .frames import ned_to_enu


class TelemetryLogger(Node):
    def __init__(self):
        super().__init__("telemetry_logger")
        self.declare_parameter("source", "px4")
        self.declare_parameter("out", "telemetry.csv")
        self.declare_parameter("rate_hz", 10.0)
        src = self.get_parameter("source").value
        self.last = None
        self.f = open(self.get_parameter("out").value, "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(["t_ros_s", "x_east_m", "y_north_m", "z_up_m", "msg_age_s"])
        if src == "px4":
            from px4_msgs.msg import VehicleLocalPosition
            v = getattr(VehicleLocalPosition, "MESSAGE_VERSION", 0)
            qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             history=HistoryPolicy.KEEP_LAST, depth=1)
            name = "/fmu/out/vehicle_local_position" + (f"_v{v}" if v else "")
            self.create_subscription(VehicleLocalPosition, name, self.on_px4, qos)
        else:
            from geometry_msgs.msg import PoseStamped
            self.create_subscription(PoseStamped, "/ap/pose/filtered", self.on_ap, qos_profile_sensor_data)
        self.create_timer(1.0 / float(self.get_parameter("rate_hz").value), self.write)

    def now_s(self):
        return self.get_clock().now().nanoseconds / 1e9

    def on_px4(self, m):
        self.last = (ned_to_enu((m.x, m.y, m.z)), self.now_s())

    def on_ap(self, m):
        p = m.pose.position
        self.last = ((p.x, p.y, p.z), self.now_s())        # AP_DDS already publishes ENU

    def write(self):
        if self.last is None:
            return
        (e, n, u), t_rx = self.last
        t = self.now_s()
        self.w.writerow([f"{t:.3f}", f"{e:.3f}", f"{n:.3f}", f"{u:.3f}", f"{t - t_rx:.3f}"])

    def destroy_node(self):
        self.f.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = TelemetryLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()
