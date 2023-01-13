"""Test Simple Service dApp."""
import logging
import os
import signal
from functools import partial
from pathlib import Path

import pytest

from goth.runner.probe import RequestorProbe

from tests.goth_tests.utils import assert_app_states, assert_node_states

logger = logging.getLogger("goth.test.test")


@pytest.mark.parametrize("goth_probe_use_proxy", [False], indirect=True)
async def test_simple_service(
    goth_probe_use_proxy: bool, log_dir: Path, goth_requestor_probe: RequestorProbe
) -> None:
    """Test Simple Service happy path."""
    service_command = (
        "dapp-runner start"
        f" --config configs/goth.yaml -l {str(log_dir / __name__)}.log"
        " dapp-store/apps/simple-service.yaml"
    )
    async with goth_requestor_probe.run_command_on_host(
        service_command,
        env={**os.environ, "PYTHONUNBUFFERED": "TRUE"},
    ) as (_cmd_task, cmd_monitor, process_monitor):
        cmd_monitor.add_assertion(assert_app_states)
        cmd_monitor.add_assertion(
            partial(assert_node_states, "simple-service"),
            name='assert_node_states("simple-service")',
        )
        await cmd_monitor.wait_for_pattern(
            ".*Starting app: A simple, non-networked service.*", timeout=300
        )
        await cmd_monitor.wait_for_pattern(".*Application started.", timeout=180)
        process = await process_monitor.get_process()
        process.send_signal(signal.SIGINT)
        await cmd_monitor.wait_for_pattern(".*Shutting down ...", timeout=30)
        await cmd_monitor.wait_for_pattern(".*Shutdown completed", timeout=30)
