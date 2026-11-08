"""PX4 Offboard square via uXRCE-DDS: the OffboardFSM wrapped in a ROS 2 node.

  ros2 run uav_ros2_labs px4_offboard_square --ros-args -p alt:=5.0 -p side:=10.0

Topics follow PX4 message versioning: a versioned message gets the suffix _v<N> (see
get_message_name_version), so the same code works with px4_msgs before and after versioning.
"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand, VehicleLocalPosition, VehicleStatus

from .offboard_fsm import Obs, OffboardFSM, S


def topic(base: str, msg_cls) -> str:
    v = getattr(msg_cls, "MESSAGE_VERSION", 0)
    return base if v == 0 else f"{base}_v{v}"


PX4_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     history=HistoryPolicy.KEEP_LAST, depth=1)


class Px4OffboardSquare(Node):
    def __init__(self):
        super().__init__("px4_offboard_square")
        self.declare_parameter("alt", 5.0)
        self.declare_parameter("side", 10.0)
        self.fsm = OffboardFSM(alt=float(self.get_parameter("alt").value), side=float(self.get_parameter("side").value))
        self.status: VehicleStatus | None = None
        self.lpos: VehicleLocalPosition | None = None
        self.t_status = None

        self.pub_mode = self.create_publisher(OffboardControlMode, topic("/fmu/in/offboard_control_mode", OffboardControlMode), PX4_QOS)
        self.pub_sp = self.create_publisher(TrajectorySetpoint, topic("/fmu/in/trajectory_setpoint", TrajectorySetpoint), PX4_QOS)
        self.pub_cmd = self.create_publisher(VehicleCommand, topic("/fmu/in/vehicle_command", VehicleCommand), PX4_QOS)
        self.create_subscription(VehicleStatus, topic("/fmu/out/vehicle_status", VehicleStatus), self.on_status, PX4_QOS)
        self.create_subscription(VehicleLocalPosition, topic("/fmu/out/vehicle_local_position", VehicleLocalPosition), self.on_lpos, PX4_QOS)
        self.timer = self.create_timer(0.05, self.tick)        # 20 Hz: well above PX4's 2 Hz proof-of-life
        self._last_req = 0.0

    def now_s(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def us(self) -> int:
        return self.get_clock().now().nanoseconds // 1000

    def on_status(self, m):
        self.status, self.t_status = m, self.now_s()

    def on_lpos(self, m):
        self.lpos = m

    def command(self, cmd: int, p1: float = 0.0, p2: float = 0.0):
        m = VehicleCommand()
        m.command, m.param1, m.param2 = cmd, float(p1), float(p2)
        m.target_system, m.target_component, m.source_system, m.source_component = 1, 1, 1, 1
        m.from_external, m.timestamp = True, self.us()
        self.pub_cmd.publish(m)

    def tick(self):
        t = self.now_s()
        st, lp = self.status, self.lpos
        obs = Obs(t=t, status_age=(t - self.t_status) if self.t_status else 1e9,
                  pos_valid=bool(lp and lp.xy_valid and lp.z_valid),
                  armed=bool(st and st.arming_state == VehicleStatus.ARMING_STATE_ARMED),
                  offboard=bool(st and st.nav_state == VehicleStatus.NAVIGATION_STATE_OFFBOARD),
                  pos=(lp.x, lp.y, lp.z) if lp else (0.0, 0.0, 0.0),
                  landed=bool(st and st.arming_state != VehicleStatus.ARMING_STATE_ARMED and self.fsm.state in (S.LAND, S.ABORT)))
        prev = self.fsm.state
        a = self.fsm.step(obs)
        if self.fsm.state != prev:
            self.get_logger().info(f"{prev.name} -> {self.fsm.state.name}: {self.fsm.log[-1][3]}")

        if a.setpoint is not None:
            mode = OffboardControlMode(position=True, timestamp=self.us())
            self.pub_mode.publish(mode)
            sp = TrajectorySetpoint()
            sp.position = [float(v) for v in a.setpoint]
            sp.velocity = [float("nan")] * 3
            sp.acceleration = [float("nan")] * 3
            sp.yaw = float("nan")
            sp.timestamp = self.us()
            self.pub_sp.publish(sp)
        if t - self._last_req > 0.5:                            # rate-limit requests; the FSM repeats them until state changes
            if a.request_arm:
                self.command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0); self._last_req = t
            if a.request_offboard:
                self.command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0); self._last_req = t   # custom mode, main mode 6 = Offboard
            if a.request_land:
                self.command(VehicleCommand.VEHICLE_CMD_NAV_LAND); self._last_req = t
        if self.fsm.state == S.DONE:
            self.get_logger().info("done")
            self.timer.cancel()


def main():
    rclpy.init()
    node = Px4OffboardSquare()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()
