"""Test Simple Service dApp."""
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
        "Found all expected Simple Service app states",
    )


async def assert_service_node_states(events: EventStream) -> str:
    """Compare simple service node states."""
    return await assert_strings_in_events(
        events,
        [
            '{"simple-service": {"0": "pending"}}',
            '{"simple-service": {"0": "starting"}}',
            '{"simple-service": {"0": "running"}}',
            '{"simple-service": {"0": "stopping"}}',
            '{"simple-service": {"0": "terminated"}}',
        ],
        "Found all expected Simple Service node states",
    )


async def test_simple_service(goth_requestor_probe: RequestorProbe) -> None:
    """Test Simple Service happy path."""
    async with goth_requestor_probe.run_command_on_host(
        "dapp-runner start --config configs/goth.yaml dapp-store/apps/simple-service.yaml",
        env=os.environ,
    ) as (_cmd_task, cmd_monitor, process_monitor):
        cmd_monitor.add_assertion(assert_app_states)
        cmd_monitor.add_assertion(assert_service_node_states)
        await cmd_monitor.wait_for_pattern(
            ".*Starting app: A simple, non-networked service.*", timeout=10
        )
        await cmd_monitor.wait_for_pattern(".*Application started.", timeout=120)
        process = await process_monitor.get_process()
        process.send_signal(signal.SIGINT)
        await cmd_monitor.wait_for_pattern(".*Shutting down ...", timeout=10)
        await cmd_monitor.wait_for_pattern(".*Shutdown completed", timeout=10)
