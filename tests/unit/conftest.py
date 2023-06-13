"""Pytest configuration file containing the utilities for Dapp Runner unit tests."""
import asyncio
from typing import Tuple
from unittest import mock

import pytest

from tests.factories.runner import RunnerFactory


class Utils:
    """Utilities for Dapp Runner tests."""

    @staticmethod
    def verify_error(expected_error: Tuple[type, str], actual_error):
        """Verify expected error vs an actual error.

        Example usage:

            @pytest.mark.parametrize("params, expected_error", [ ... ])
            def test_error(params, expected_error, test_utils):
                try:
                    ...
                except Exception as e:
                    test_utils.verify_error(expected_error, e)
                else:
                    test_utils.verify_error(expected_error, None)

        """

        if expected_error and not actual_error:
            raise AssertionError(f"Expected exception: {expected_error}")
        if actual_error:
            if not expected_error:
                raise
            assert expected_error[1] in str(actual_error)
            assert type(actual_error) == expected_error[0]


@pytest.fixture
def test_utils():
    """Pytest fixture that exposes the Utils class."""
    return Utils


@pytest.fixture(scope="session")
def event_loop():
    """Make async fixtures use same event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    yield loop

    loop.close()


@pytest.fixture
def mock_runner(mocker):
    """Get a mostly mocked out Runner instance."""

    def _mock_runner(**kwargs):
        mocker.patch("yapapi.golem.Golem._get_new_engine", mock.Mock())
        mocker.patch("yapapi.golem.Golem.start", mock.AsyncMock())
        mocker.patch("yapapi.golem.Golem.stop", mock.AsyncMock())

        return RunnerFactory(**kwargs)

    return _mock_runner
