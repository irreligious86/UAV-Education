import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def vehicle_factory():
    from fake_vehicle import FakeVehicle
    made = []

    def make(loss: float = 0.0):
        port = free_port()
        v = FakeVehicle(f"udpin:127.0.0.1:{port}", loss=loss).start()
        made.append(v)
        return v, port

    yield make
    for v in made:
        v.close()
