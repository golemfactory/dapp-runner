"""Goth tests for Simple Service dApp."""
import logging
import os
import signal

from goth.assertions import EventStream
from goth.runner.probe import RequestorProbe

logger = logging.getLogger("goth.test.test")


async def assert_states(events: EventStream) -> str:
    """State comparator."""
    states = (state for state in ["pending", "starting", "running", "stopping", "terminated"])
    expected_state = next(states, None)
    async for log_line in events:
        if expected_state is not None and expected_state in log_line:
            logger.info(f"found {expected_state} in {log_line}")
            expected_state = next(states, None)
    assert expected_state is None, f"{[state for state in expected_state]} were not found"
    return "Found all expected states"


async def test_simple_service(goth_requestor_probe: RequestorProbe) -> None:
    """Test Simple Service happy path."""
    async with goth_requestor_probe.run_command_on_host(
        "dapp-runner start --config configs/goth.yaml dapp-store/apps/simple-service.yaml",
        env=os.environ,
    ) as (_cmd_task, cmd_monitor, process_monitor):
        cmd_monitor.add_assertion(assert_states)
        await cmd_monitor.wait_for_pattern(
            ".*Starting app: A simple, non-networked service.*", timeout=10
        )
        await cmd_monitor.wait_for_pattern(".*Application started.", timeout=120)
        process = await process_monitor.get_process()
        process.send_signal(signal.SIGINT)
        await cmd_monitor.wait_for_pattern(".*Shutting down ...", timeout=10)
        await cmd_monitor.wait_for_pattern(".*Shutdown completed", timeout=10)
