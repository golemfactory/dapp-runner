"""Tests for `dapp_runner.runner`."""
from datetime import datetime, timezone, timedelta
import pytest
from unittest import mock

from yapapi.services import ServiceState

from dapp_runner.descriptor import Config, DappDescriptor
from dapp_runner.descriptor.config import YagnaConfig, PaymentConfig
from dapp_runner.runner import _running_time_elapsed, Runner  # noqa


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


@pytest.fixture
def runner_config():
    return Config(
        yagna=YagnaConfig(
            subnet_tag="public",
        ),
        payment=PaymentConfig(
            budget=1,
            driver="erc20",
            network="rinkeby",
        ),
    )


@pytest.fixture
def dapp_descriptor():
    return DappDescriptor(
        payloads={},
        nodes={},
    )


@pytest.fixture
def runner(runner_config, dapp_descriptor, mocker):
    # TODO: How to mock Golem inside of Runner?
    runner = Runner(
        config=runner_config,
        dapp=dapp_descriptor,
    )

    # Naive simplification of two nodes
    mocker.patch.object(
        runner.dapp,
        "nodes",
        {
            "foo": None,
            "bar": None,
        },
    )

    return runner


async def test_runner_desired_state(runner):
    # TODO: Any way to avoid using non-public api?
    assert runner._desired_app_state == ServiceState.pending

    await runner.start()

    assert runner._desired_app_state == ServiceState.running

    await runner.stop()

    assert runner._desired_app_state == ServiceState.terminated


async def test_runner_app_state_pending(runner):
    assert runner._get_app_state_from_nodes({}) == ServiceState.pending.name


@pytest.mark.parametrize(
    "nodes_states",
    (
        {"foo": {"0": ServiceState.pending.name}},
        {"foo": {"0": ServiceState.starting.name}},
        {"foo": {"0": ServiceState.running.name}},
        {"foo": {"0": ServiceState.stopping.name}},
        {"foo": {"0": ServiceState.terminated.name}},
        {
            "foo": {"0": ServiceState.starting.name},
            "bar": {"0": ServiceState.starting.name},
        },
        {
            "foo": {"0": ServiceState.stopping.name},
            "bar": {"0": ServiceState.stopping.name},
        },
        {
            "foo": {"0": ServiceState.terminated.name},
            "bar": {"0": ServiceState.terminated.name},
        },
        {
            "foo": {"0": ServiceState.running.name},
            "bar": {"0": ServiceState.terminated.name},
        },
    ),
)
async def test_runner_app_state_starting(runner, nodes_states):
    await runner.start()

    assert runner._get_app_state_from_nodes(nodes_states) == ServiceState.starting.name

    await runner.stop()


@pytest.mark.parametrize(
    "nodes_states",
    (
        {"foo": {"0": ServiceState.pending.name}},
        {"foo": {"0": ServiceState.starting.name}},
        {"foo": {"0": ServiceState.running.name}},
        {"foo": {"0": ServiceState.stopping.name}},
        {
            "foo": {"0": ServiceState.starting.name},
            "bar": {"0": ServiceState.starting.name},
        },
        {
            "foo": {"0": ServiceState.stopping.name},
            "bar": {"0": ServiceState.stopping.name},
        },
        {
            "foo": {"0": ServiceState.running.name},
            "bar": {"0": ServiceState.running.name},
        },
        {
            "foo": {"0": ServiceState.running.name},
            "bar": {"0": ServiceState.terminated.name},
        },
    ),
)
async def test_runner_app_state_stopping(runner, nodes_states):
    await runner.stop()

    assert runner._get_app_state_from_nodes(nodes_states) == ServiceState.stopping.name


async def test_runner_app_state_running(runner):
    await runner.start()

    assert (
        runner._get_app_state_from_nodes(
            {
                "foo": {"0": ServiceState.running.name},
                "bar": {"0": ServiceState.running.name},
            }
        )
        == ServiceState.running.name
    )

    await runner.stop()


@pytest.mark.parametrize(
    "nodes_states",
    (
        {"foo": {"0": ServiceState.terminated.name}},
        {
            "foo": {"0": ServiceState.terminated.name},
            "bar": {"0": ServiceState.terminated.name},
        },
    ),
)
async def test_runner_app_state_terminated(runner, nodes_states):
    await runner.stop()

    assert (
        runner._get_app_state_from_nodes(nodes_states) == ServiceState.terminated.name
    )
