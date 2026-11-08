#!/usr/bin/env python3
"""Tracking controller skeleton: pixel error in the image -> body-frame velocity setpoint.
Transport-agnostic; the adapter publishes to PX4 (uXRCE-DDS) or MAVROS.

Protections (do not remove):
  - velocity and acceleration limits
  - 0.5 s detection watchdog -> zero velocity (hover)
  - 3 s target-loss timeout -> hover and release control
"""
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point  # detection: x, y normalised to [-1, 1], z = confidence


class Tracker(Node):
    def __init__(self, adapter):
        super().__init__("uav_tracker")
        self.adapter = adapter
        self.kp = self.declare_parameter("kp", 1.5).value          # m/s per unit error
        self.v_max = self.declare_parameter("v_max", 2.0).value
        self.a_max = self.declare_parameter("a_max", 2.0).value
        self.watchdog_s = 0.5
        self.loss_timeout_s = 3.0
        self.last_det = 0.0
        self.err = (0.0, 0.0)
        self.v = [0.0, 0.0]
        self.create_subscription(Point, "/detections/target", self.on_det, 10)
        self.create_timer(0.05, self.step)                          # 20 Hz control loop
        self.get_logger().info("tracker ready")

    def on_det(self, msg: Point):
        if msg.z < 0.5:                                             # low confidence: ignore
            return
        self.err = (msg.x, msg.y); self.last_det = time.time()

    def step(self):
        dt = 0.05
        age = time.time() - self.last_det
        if age > self.loss_timeout_s:
            self.adapter.send_velocity(0.0, 0.0, 0.0); self.adapter.release(); return
        if age > self.watchdog_s:
            target = (0.0, 0.0)                                     # watchdog: hover
        else:
            ex, ey = self.err
            # image x -> body right (vy), image y -> body forward (vx); sign depends on camera mount
            target = (-self.kp * ey, self.kp * ex)
        for i in range(2):                                          # accel + speed limits
            dv = max(-self.a_max * dt, min(self.a_max * dt, target[i] - self.v[i]))
            self.v[i] = max(-self.v_max, min(self.v_max, self.v[i] + dv))
        self.adapter.send_velocity(self.v[0], self.v[1], 0.0)


def main():
    rclpy.init()
    from .adapters import load_adapter                              # px4 or mavros, by parameter
    node = Tracker(adapter=None)
    node.adapter = load_adapter(node)
    rclpy.spin(node)


if __name__ == "__main__":
    main()
