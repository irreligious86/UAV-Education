"""ArduPilot GUIDED square via AP_DDS (native DDS, no MAVROS).

  ros2 run uav_ros2_labs ap_dds_square

Uses /ap/mode_switch and /ap/arm_motors services, /ap/experimental/takeoff, and velocity commands on
/ap/cmd_vel (TwistStamped, frame_id "map" = ENU). The vehicle state comes from /ap/pose/filtered and
/ap/status. Same OffboardFSM as for PX4; positions are converted ENU -> NED for it.
"""
from __future__ import annotations

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geometry_msgs.msg import PoseStamped, TwistStamped
from ardupilot_msgs.msg import Status
from ardupilot_msgs.srv import ArmMotors, ModeSwitch, Takeoff

from .frames import enu_to_ned, ned_to_enu
from .offboard_fsm import Obs, OffboardFSM, S

COPTER_GUIDED, COPTER_LAND = 4, 9
KP, VMAX = 0.8, 3.0


class ApDdsSquare(Node):
    def __init__(self):
        super().__init__("ap_dds_square")
        self.fsm = OffboardFSM(alt=5.0, side=10.0, prestream_s=0.0)
        self.pose: PoseStamped | None = None
        self.status: Status | None = None
        self.t_status = None
        self.create_subscription(PoseStamped, "/ap/pose/filtered", self.on_pose, qos_profile_sensor_data)
        self.create_subscription(Status, "/ap/status", self.on_status, qos_profile_sensor_data)
        self.pub_vel = self.create_publisher(TwistStamped, "/ap/cmd_vel", 1)
        self.cli_mode = self.create_client(ModeSwitch, "/ap/mode_switch")
        self.cli_arm = self.create_client(ArmMotors, "/ap/arm_motors")
        self.cli_takeoff = self.create_client(Takeoff, "/ap/experimental/takeoff")
        self.timer = self.create_timer(0.1, self.tick)
        self._pending = None
        self._took_off = False

    def now_s(self):
        return self.get_clock().now().nanoseconds / 1e9

    def on_pose(self, m):
        self.pose = m

    def on_status(self, m):
        self.status, self.t_status = m, self.now_s()

    def call(self, cli, req):
        if self._pending is not None and not self._pending.done():
            return                                    # one request in flight at a time
        if cli.service_is_ready():
            self._pending = cli.call_async(req)

    def send_velocity_towards(self, target_ned, pos_ned):
        d = [t - p for t, p in zip(target_ned, pos_ned)]
        v = [max(-VMAX, min(VMAX, KP * x)) for x in d]
        e, n, u = ned_to_enu(v)
        m = TwistStamped()
        m.header.stamp = self.get_clock().now().to_msg()
        m.header.frame_id = "map"                     # ENU world frame; AP_DDS converts to NED
        m.twist.linear.x, m.twist.linear.y, m.twist.linear.z = float(e), float(n), float(u)
        self.pub_vel.publish(m)

    def tick(self):
        t = self.now_s()
        st, ps = self.status, self.pose
        pos = enu_to_ned((ps.pose.position.x, ps.pose.position.y, ps.pose.position.z)) if ps else (0.0, 0.0, 0.0)
        armed = bool(st and st.armed)
        guided = bool(st and st.mode == COPTER_GUIDED)
        obs = Obs(t=t, status_age=(t - self.t_status) if self.t_status else 1e9, pos_valid=ps is not None,
                  armed=armed, offboard=guided, pos=pos, landed=bool(st and not st.armed and self.fsm.state in (S.LAND, S.ABORT)))
        prev = self.fsm.state
        a = self.fsm.step(obs)
        if self.fsm.state != prev:
            self.get_logger().info(f"{prev.name} -> {self.fsm.state.name}: {self.fsm.log[-1][3]}")
        # ArduPilot arms only in a mode that allows it: switch to GUIDED first, then arm, then take off
        if a.request_arm:
            if not guided:
                self.call(self.cli_mode, ModeSwitch.Request(mode=COPTER_GUIDED))
            else:
                self.call(self.cli_arm, ArmMotors.Request(arm=True))
        elif a.request_offboard and not guided:
            self.call(self.cli_mode, ModeSwitch.Request(mode=COPTER_GUIDED))
        elif self.fsm.state == S.TAKEOFF and not self._took_off:
            self.call(self.cli_takeoff, Takeoff.Request(alt=float(self.fsm.alt)))
            self._took_off = True
        elif a.request_land:
            self.call(self.cli_mode, ModeSwitch.Request(mode=COPTER_LAND))
        elif a.setpoint is not None and guided and self.fsm.state == S.SQUARE:
            self.send_velocity_towards(a.setpoint, pos)
        if self.fsm.state == S.DONE:
            self.get_logger().info("done")
            self.timer.cancel()


def main():
    rclpy.init()
    node = ApDdsSquare()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()
