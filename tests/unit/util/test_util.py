"""Unit tests for dapp_runner._util."""
from unittest import mock

import pytest

from dapp_runner._util import get_free_port


@mock.patch("socket.socket.bind", mock.Mock(side_effect=[OSError, None]))
def test_get_free_port_available():
    """Test if the first available port is correctly returned."""
    assert get_free_port() == 8081


@mock.patch("socket.socket.bind", mock.Mock(side_effect=OSError))
def test_get_free_port_exceeded(test_utils):
    """Test if the expected error is raised when no free port was found."""
    with pytest.raises(RuntimeError) as e:
        get_free_port()
        test_utils.verify_error(
            RuntimeError("No free ports found. range_start=8080, range_end=9090"), e
        )
