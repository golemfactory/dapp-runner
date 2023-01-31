"""Unit tests for dapp_runner._util."""
import asyncio
from unittest import mock

import pytest

from dapp_runner._util import _free_port_generator, get_free_port


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear free port generator lru cache before very test in this module."""
    _free_port_generator.cache_clear()


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


async def test_get_free_port_asynchronous():
    """Test if when called asynchronously multiple times different ports were returned."""

    async def _get_free_port():
        return get_free_port()

    t1 = asyncio.create_task(_get_free_port())
    t2 = asyncio.create_task(_get_free_port())
    assert await t1 != await t2
