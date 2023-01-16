"""Test Simple, db-enabled dApp."""
import logging
import os
import signal

from goth.assertions import EventStream
from goth.runner.probe import RequestorProbe

from tests.goth_tests.utils import assert_strings_in_events

logger = logging.getLogger("goth.test.test")


async def assert_app_states(events: EventStream) -> str:
    """Compare app states."""
    return await assert_strings_in_events(
        events,
        [
            '"app": "pending"',
            '"app": "starting"',
            '"app": "running"',
            '"app": "stopping"',
            '"app": "terminated"',
        ],
        "Found all expected Simple, db-enabled dApp app states",
    )


async def assert_db_node_states(events: EventStream) -> str:
    """Compare db node states."""
    return await assert_strings_in_events(
        events,
        [
            '"db": {"0": "pending"}',
            '"db": {"0": "starting"}',
            '"db": {"0": "running"}',
            '"db": {"0": "stopping"}',
            '"db": {"0": "terminated"}',
        ],
        "Found all expected db node states",
    )


async def assert_http_node_states(events: EventStream) -> str:
    """Compare http node states."""
    return await assert_strings_in_events(
        events,
        [
            '"http": {"0": "pending"}',
            '"http": {"0": "starting"}',
            '"http": {"0": "running"}',
            '"http": {"0": "stopping"}',
            '"http": {"0": "terminated"}',
        ],
        "Found all expected http node states",
    )


async def test_simple_db_enabled_application(goth_requestor_probe: RequestorProbe) -> None:
    """Test Simple, db-enabled dApp happy path."""
    async with goth_requestor_probe.run_command_on_host(
        "dapp-runner start --config configs/goth.yaml dapp-store/apps/webapp.yaml",
        env=os.environ,
    ) as (_cmd_task, cmd_monitor, process_monitor):
        cmd_monitor.add_assertion(assert_app_states)
        cmd_monitor.add_assertion(assert_db_node_states)
        cmd_monitor.add_assertion(assert_http_node_states)
        await cmd_monitor.wait_for_pattern(
            ".*Starting app: Simple, db-enabled web application.*", timeout=10
        )
        await cmd_monitor.wait_for_pattern(".*Application started.", timeout=120)
        process = await process_monitor.get_process()
        process.send_signal(signal.SIGINT)
        await cmd_monitor.wait_for_pattern(".*Shutting down ...", timeout=10)
        await cmd_monitor.wait_for_pattern(".*Shutdown completed", timeout=10)
