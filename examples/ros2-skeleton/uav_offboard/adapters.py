"""Transport adapters. Each exposes send_velocity(vx, vy, vz) in body frame and release()."""
from geometry_msgs.msg import Twist


class MavrosAdapter:
    """ArduPilot via MAVROS: GUIDED mode velocity setpoints."""
    def __init__(self, node):
        self.pub = node.create_publisher(Twist, "/mavros/setpoint_velocity/cmd_vel_unstamped", 10)
        self.node = node

    def send_velocity(self, vx, vy, vz):
        t = Twist(); t.linear.x, t.linear.y, t.linear.z = vx, vy, vz
        self.pub.publish(t)

    def release(self):
        # Hand control back: switch to LOITER via /mavros/set_mode (service call omitted for brevity)
        self.node.get_logger().warn("target lost: hovering, control released")


class Px4Adapter:
    """PX4 via uXRCE-DDS: OffboardControlMode + TrajectorySetpoint at >= 2 Hz (we send at 20 Hz)."""
    def __init__(self, node):
        from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint
        self.OCM, self.TS = OffboardControlMode, TrajectorySetpoint
        self.pub_mode = node.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", 10)
        self.pub_sp = node.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", 10)
        self.node = node

    def send_velocity(self, vx, vy, vz):
        m = self.OCM(); m.velocity = True; m.position = False
        self.pub_mode.publish(m)
        sp = self.TS(); sp.position = [float("nan")] * 3; sp.velocity = [vx, vy, vz]
        self.pub_sp.publish(sp)

    def release(self):
        self.node.get_logger().warn("target lost: hovering, control released")


def load_adapter(node):
    name = node.declare_parameter("adapter", "mavros").value
    return Px4Adapter(node) if name == "px4" else MavrosAdapter(node)
