"""Pytest configuration file containing the utilities for Dapp Runner unit tests."""
import asyncio

import pytest


class Utils:
    """Utilities for Dapp Runner tests."""

    @staticmethod
    def verify_error(expected_error, actual_error):
        """Verify expected error vs an actual error.

        Example usage:

            @pytest.mark.parametrize("params, expected_error", [ ... ])
            def test_error(params, expected_error, test_utils):
                try:
                    ...
                except Exception as e:
                    test_utils.verify_error(error, e)
                else:
                    test_utils.verify_error(error, None)

        """

        if expected_error and not actual_error:
            raise AssertionError(f"Expected exception: {expected_error}")
        if actual_error:
            if not expected_error:
                raise
            assert str(expected_error) in str(actual_error)
            assert type(actual_error) == type(expected_error)


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
