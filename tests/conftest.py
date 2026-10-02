"""
Pytest configuration and shared fixtures
"""

import socket
import time

import pytest

from tests.mocks.gateway_server import MODE_CLASSIC, MODE_NFACTOR, MockGatewayServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        return s.getsockname()[1]


def _start_server(mode: str) -> MockGatewayServer:
    server = MockGatewayServer(port=_free_port(), mode=mode)
    server.start(threaded=True)
    time.sleep(1)
    return server


@pytest.fixture
def mock_classic_server():
    """Mock gateway with classic authentication policies"""
    server = _start_server(MODE_CLASSIC)
    yield server
    server.stop()


@pytest.fixture
def mock_nfactor_server():
    """Mock gateway with nFactor authentication (13.1+ firmware)"""
    server = _start_server(MODE_NFACTOR)
    yield server
    server.stop()
