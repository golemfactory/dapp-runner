"""Unit tests for dapp_runner._util."""
from unittest import mock

from dapp_runner._util import get_free_port


@mock.patch("socket.socket.connect_ex", mock.Mock(side_effect=[1, 0]))
def test_get_free_port_available():
    """Test if the first available port is correctly returned."""
    assert get_free_port() == 8081


@mock.patch("socket.socket.connect_ex", mock.Mock(return_value=1))
def test_get_free_port_exceeded(test_utils):
    """Test if the expected error is raised when no free port was found."""
    try:
        get_free_port()
    except Exception as e:
        test_utils.verify_error(
            OverflowError("No free ports found. range_start=8080, range_end=9090"), e
        )
