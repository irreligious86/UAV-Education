import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uav_ros2_labs.offboard_fsm import S, Obs, OffboardFSM  # noqa: E402


class Sim:
    """Toy vehicle: arms on request, enters offboard on request (only if setpoints were streaming),
    moves toward the setpoint at 2 m/s, lands on request."""

    def __init__(self):
        self.t = 0.0; self.pos = [0.0, 0.0, 0.0]; self.armed = False; self.offboard = False
        self.landing = False; self.stream_since = None; self.status_age = 0.0; self.pos_valid = True

    def obs(self):
        return Obs(self.t, self.status_age, self.pos_valid, self.armed, self.offboard, tuple(self.pos),
                   landed=self.armed is False or (self.landing and self.pos[2] >= -0.05))

    def apply(self, a, dt):
        if a.setpoint is not None:
            self.stream_since = self.stream_since if self.stream_since is not None else self.t
            if self.offboard and not self.landing:
                for i in range(3):
                    d = a.setpoint[i] - self.pos[i]
                    self.pos[i] += max(-2 * dt, min(2 * dt, d))
        else:
            self.stream_since = None
        if a.request_arm:
            self.armed = True
        if a.request_offboard and self.stream_since is not None and self.t - self.stream_since >= 0.5:
            self.offboard = True
        if a.request_land:
            self.landing = True; self.offboard = False
        if self.landing:
            self.pos[2] = min(0.0, self.pos[2] + 1.0 * dt)
            if self.pos[2] >= 0.0:
                self.armed = False
        self.t += dt


def run(fsm, sim, until=200.0, dt=0.05, hook=None):
    while sim.t < until and fsm.state != S.DONE:
        if hook:
            hook(sim)
        sim.apply(fsm.step(sim.obs()), dt)
    return fsm


def test_full_mission_happy_path():
    fsm = run(OffboardFSM(alt=5, side=10), Sim())
    states = [s for (_, _, s, _) in fsm.log]
    assert states[:6] == ["STREAM_SETPOINTS", "ARMING", "OFFBOARD", "TAKEOFF", "SQUARE", "LAND"]
    assert fsm.state == S.DONE and "ABORT" not in states


def test_setpoints_stream_before_offboard_request():
    fsm, sim = OffboardFSM(), Sim()
    first_offboard_request = None
    first_setpoint = None
    while sim.t < 10:
        a = fsm.step(sim.obs())
        if a.setpoint is not None and first_setpoint is None:
            first_setpoint = sim.t
        if a.request_offboard and first_offboard_request is None:
            first_offboard_request = sim.t
        sim.apply(a, 0.05)
    assert first_setpoint is not None and first_offboard_request - first_setpoint >= fsm.prestream_s - 1e-9


def test_abort_on_lost_position():
    def hook(sim):
        if sim.t > 8:
            sim.pos_valid = False
    fsm = run(OffboardFSM(), Sim(), hook=hook)
    assert any(s == "ABORT" and "position" in why for (_, _, s, why) in fsm.log)
    assert fsm.state == S.DONE


def test_abort_on_stale_status():
    def hook(sim):
        if 6 < sim.t:
            sim.status_age = 2.0
    fsm = run(OffboardFSM(), Sim(), hook=hook)
    assert any(s == "ABORT" and "stale" in why for (_, _, s, why) in fsm.log)


def test_operator_takeover_releases_control():
    def hook(sim):
        if sim.t > 9 and sim.offboard:
            sim.offboard = False            # pilot switched mode on the transmitter
    fsm = run(OffboardFSM(), Sim(), hook=hook)
    assert fsm.state == S.DONE
    assert any("operator" in why for (_, _, _, why) in fsm.log)
