"""Tests for `dapp_runner.runner`."""
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from yapapi.services import ServiceState

from dapp_runner.runner import _running_time_elapsed  # noqa


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


async def test_runner_desired_state(mock_runner):
    """Test to check if desired app state is properly managed with app lifetime."""
    runner = mock_runner()

    assert runner._desired_app_state == ServiceState.pending

    await runner.start()

    assert runner._desired_app_state == ServiceState.running

    await runner.stop()

    assert runner._desired_app_state == ServiceState.terminated


async def test_runner_app_state_pending(mock_runner):
    """Test app state reporting at initial state of Runner."""

    runner = mock_runner(dapp__node_count=2, desired_app_state=ServiceState.pending)
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
async def test_runner_app_state_starting(mocker, mock_runner, nodes_states):
    """Test app state reporting while Runner is starting its services."""

    mocker.patch("dapp_runner.runner.Runner.dapp_state", nodes_states)
    runner = mock_runner(dapp__node_count=2, desired_app_state=ServiceState.running)
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
async def test_runner_app_state_stopping(mocker, mock_runner, nodes_states):
    """Test app state reporting while Runner is stopping its services."""

    mocker.patch("dapp_runner.runner.Runner.dapp_state", nodes_states)
    runner = mock_runner(dapp__node_count=2, desired_app_state=ServiceState.terminated)
    assert runner._get_app_state_from_nodes() == ServiceState.stopping


async def test_runner_app_state_running(mocker, mock_runner):
    """Test app state reporting while Runner have all services running."""

    nodes_states = {
        "foo": {0: ServiceState.running},
        "bar": {0: ServiceState.running},
    }

    mocker.patch("dapp_runner.runner.Runner.dapp_state", nodes_states)
    runner = mock_runner(dapp__node_count=2, desired_app_state=ServiceState.running)
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
async def test_runner_app_state_terminated(mocker, mock_runner, nodes_states):
    """Test app state reporting while Runner have all services terminated."""

    mocker.patch("dapp_runner.runner.Runner.dapp_state", nodes_states)
    runner = mock_runner(dapp__node_count=2, desired_app_state=ServiceState.terminated)
    assert runner._get_app_state_from_nodes() == ServiceState.terminated
