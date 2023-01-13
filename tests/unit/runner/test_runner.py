"""Tests for `dapp_runner.runner`."""
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from yapapi.services import ServiceState

from dapp_runner.runner import Runner, _running_time_elapsed  # noqa

from tests.factories.runner import mock_runner


def _some_datetime(offset: int = 0):
    return datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=offset)


@pytest.mark.parametrize(
    "time_started, max_running_time, expected",
    (
        (None, None, False),
        (_some_datetime(-100), None, False),
        (None, timedelta(seconds=100), False),
        (_some_datetime(-100), timedelta(seconds=101), False),
        (_some_datetime(-100), timedelta(seconds=99), True),
    ),
)
@mock.patch("dapp_runner.runner.utcnow", _some_datetime)
def test_running_time_elapsed(time_started, max_running_time, expected):
    """Test the `_running_time_elapsed` function."""
    assert _running_time_elapsed(time_started, max_running_time) == expected


@pytest.fixture(scope="function")
def runner():
    """Mostly mocked out Runner instance."""
    with mock_runner() as runner:
        yield runner


async def test_runner_desired_state(runner):
    """Test to check if desired app state is properly managed with app lifetime."""

    assert runner._desired_app_state == ServiceState.pending

    await runner.start()

    assert runner._desired_app_state == ServiceState.running

    await runner.stop()

    assert runner._desired_app_state == ServiceState.terminated


async def test_runner_app_state_pending():
    """Test app state reporting at initial state of Runner."""

    with mock_runner(dapp__node_count=2, desired_app_state=ServiceState.pending) as runner:
        assert runner._get_app_state_from_nodes() == ServiceState.pending


@pytest.mark.parametrize(
    "nodes_states",
    (
        {"foo": {0: ServiceState.pending}},
        {"foo": {0: ServiceState.starting}},
        {"foo": {0: ServiceState.running}},
        {"foo": {0: ServiceState.stopping}},
        {"foo": {0: ServiceState.terminated}},
        {
            "foo": {0: ServiceState.starting},
            "bar": {0: ServiceState.starting},
        },
        {
            "foo": {0: ServiceState.stopping},
            "bar": {0: ServiceState.stopping},
        },
        {
            "foo": {0: ServiceState.terminated},
            "bar": {0: ServiceState.terminated},
        },
        {
            "foo": {0: ServiceState.running},
            "bar": {0: ServiceState.terminated},
        },
    ),
)
async def test_runner_app_state_starting(nodes_states):
    """Test app state reporting while Runner is starting its services."""

    with mock.patch("dapp_runner.runner.Runner.dapp_state", nodes_states):
        with mock_runner(dapp__node_count=2, desired_app_state=ServiceState.running) as runner:
            assert runner._get_app_state_from_nodes() == ServiceState.starting

@pytest.mark.parametrize(
    "nodes_states",
    (
        {"foo": {0: ServiceState.pending}},
        {"foo": {0: ServiceState.starting}},
        {"foo": {0: ServiceState.running}},
        {"foo": {0: ServiceState.stopping}},
        {
            "foo": {0: ServiceState.starting},
            "bar": {0: ServiceState.starting},
        },
        {
            "foo": {0: ServiceState.stopping},
            "bar": {0: ServiceState.stopping},
        },
        {
            "foo": {0: ServiceState.running},
            "bar": {0: ServiceState.running},
        },
        {
            "foo": {0: ServiceState.running},
            "bar": {0: ServiceState.terminated},
        },
    ),
)
async def test_runner_app_state_stopping(nodes_states):
    """Test app state reporting while Runner is stopping its services."""

    with mock.patch("dapp_runner.runner.Runner.dapp_state", nodes_states):
        with mock_runner(dapp__node_count=2, desired_app_state=ServiceState.terminated) as runner:
            assert runner._get_app_state_from_nodes() == ServiceState.stopping

async def test_runner_app_state_running():
    """Test app state reporting while Runner have all services running."""

    nodes_states = {
        "foo": {0: ServiceState.running},
        "bar": {0: ServiceState.running},
    }

    with mock.patch("dapp_runner.runner.Runner.dapp_state", nodes_states):
        with mock_runner(dapp__node_count=2, desired_app_state=ServiceState.running) as runner:
            assert runner._get_app_state_from_nodes() == ServiceState.running


@pytest.mark.parametrize(
    "nodes_states",
    (
        {"foo": {0: ServiceState.terminated}},
        {
            "foo": {0: ServiceState.terminated},
            "bar": {0: ServiceState.terminated},
        },
    ),
)
async def test_runner_app_state_terminated(nodes_states):
    """Test app state reporting while Runner have all services terminated."""

    with mock.patch("dapp_runner.runner.Runner.dapp_state", nodes_states):
        with mock_runner(dapp__node_count=2, desired_app_state=ServiceState.terminated) as runner:
            assert runner._get_app_state_from_nodes() == ServiceState.terminated
