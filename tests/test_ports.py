"""Tests for obsiforge.utils.ports module."""

import socket
from unittest.mock import patch

from obsiforge.utils.ports import (
    allocate_ports,
    find_available_port,
    is_port_available,
)


def test_is_port_available_unused():
    """An unbound port should be available."""
    # Bind to port 0 to get an ephemeral port, then release it
    # and verify it becomes available again
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        assert not is_port_available(port)
    # After closing, the port should be available
    assert is_port_available(port)


def test_is_port_available_in_use():
    """A port with an active listener should not be available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        assert not is_port_available(port)


def test_find_available_port_returns_int():
    """find_available_port should return an integer port number."""
    port = find_available_port(50000)
    assert isinstance(port, int)
    assert port >= 50000


def test_find_available_port_skips_used():
    """find_available_port should skip ports that are in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        blocked_port = s.getsockname()[1]
        # Start searching from the blocked port
        port = find_available_port(blocked_port)
        assert port != blocked_port
        assert port > blocked_port


def test_find_available_port_raises_on_exhaustion():
    """find_available_port should raise if no port is available in range."""
    with patch("obsiforge.utils.ports.is_port_available", return_value=False):
        try:
            find_available_port(50000, max_tries=5)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "No available port" in str(e)


def test_allocate_ports_returns_dict():
    """allocate_ports should return dict with rest_api and mcp_http."""
    ports = allocate_ports("test-vault")
    assert "rest_api" in ports
    assert "mcp_http" in ports
    assert isinstance(ports["rest_api"], int)
    assert isinstance(ports["mcp_http"], int)


def test_allocate_ports_no_collision():
    """rest_api and mcp_http ports should not collide."""
    ports = allocate_ports("test-vault")
    assert ports["rest_api"] != ports["mcp_http"]