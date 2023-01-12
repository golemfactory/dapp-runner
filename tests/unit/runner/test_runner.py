"""Tests for `dapp_runner.runner`."""
from datetime import datetime, timedelta, timezone
from typing import Dict
from unittest import mock

import pytest
from yapapi.services import ServiceState

from dapp_runner.runner import Runner, _running_time_elapsed  # noqa

from tests.factories.descriptor.config import ConfigFactory
from tests.factories.descriptor.dapp import DappDescriptorFactory


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
def runner(mocker):
    """Mostly mocked out Runner instance."""

    mocker.patch("yapapi.golem.Golem._get_new_engine", mock.Mock())
    mocker.patch("yapapi.golem.Golem.start", mock.AsyncMock())
    mocker.patch("yapapi.golem.Golem.stop", mock.AsyncMock())

    runner = Runner(
        config=ConfigFactory(),
        dapp=DappDescriptorFactory(),
    )

    return runner


async def test_runner_desired_state(runner):
    """Test to check if desired app state is properly managed with app lifetime."""
    assert runner._desired_app_state == ServiceState.pending

    await runner.start()

    assert runner._desired_app_state == ServiceState.running

    await runner.stop()

    assert runner._desired_app_state == ServiceState.terminated


async def test_runner_app_state_pending():
    """Test app state reporting at initial state of Runner."""
    dapp_node_count = 2
    desired_app_state = ServiceState.pending
    nodes_states: Dict[str, Dict[int, ServiceState]] = {}

    assert (
        Runner._get_app_state_from_nodes(
            dapp_node_count, desired_app_state, nodes_states
        )
        == ServiceState.pending
    )


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
    dapp_node_count = 2
    desired_app_state = ServiceState.running

    assert (
        Runner._get_app_state_from_nodes(
            dapp_node_count, desired_app_state, nodes_states
        )
        == ServiceState.starting
    )


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
    dapp_node_count = 2
    desired_app_state = ServiceState.terminated

    assert (
        Runner._get_app_state_from_nodes(
            dapp_node_count, desired_app_state, nodes_states
        )
        == ServiceState.stopping
    )


async def test_runner_app_state_running():
    """Test app state reporting while Runner have all services running."""
    dapp_node_count = 2
    desired_app_state = ServiceState.running
    nodes_states = {
        "foo": {0: ServiceState.running},
        "bar": {0: ServiceState.running},
    }

    assert (
        Runner._get_app_state_from_nodes(
            dapp_node_count,
            desired_app_state,
            nodes_states,
        )
        == ServiceState.running
    )


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
    dapp_node_count = 2
    desired_app_state = ServiceState.terminated

    assert (
        Runner._get_app_state_from_nodes(
            dapp_node_count, desired_app_state, nodes_states
        )
        == ServiceState.terminated
    )
