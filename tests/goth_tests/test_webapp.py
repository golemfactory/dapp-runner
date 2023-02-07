"""Test Simple, db-enabled dApp."""
import json
import logging
import os
import signal
from functools import partial
from pathlib import Path

import pytest
import requests

from goth.runner.probe import RequestorProbe

from tests.goth_tests.utils import assert_app_states, assert_node_states

logger = logging.getLogger("goth.test.test")


@pytest.mark.skip(reason="https://github.com/golemfactory/yagna/issues/2387")  # ToDo
@pytest.mark.parametrize("goth_probe_use_proxy", [False], indirect=True)
async def test_simple_db_enabled_application(
    goth_probe_use_proxy: bool,
    log_dir: Path,
    goth_requestor_probe: RequestorProbe,
) -> None:
    """Test Simple, db-enabled dApp happy path."""
    webapp_command = (
        "dapp-runner start"
        f" --config configs/goth.yaml -l {str(log_dir / __name__)}.log"
        " dapp-store/apps/webapp.yaml"
    )
    async with goth_requestor_probe.run_command_on_host(
        webapp_command,
        env={**os.environ, "PYTHONUNBUFFERED": "TRUE"},
    ) as (_cmd_task, cmd_monitor, process_monitor):
        cmd_monitor.add_assertion(assert_app_states)
        cmd_monitor.add_assertion(
            partial(assert_node_states, "db"),
            name='assert_node_states("db")',
        )
        cmd_monitor.add_assertion(
            partial(assert_node_states, "http"),
            name='assert_node_states("http")',
        )
        await cmd_monitor.wait_for_pattern(
            ".*Starting app: Simple, db-enabled web application.*", timeout=30
        )
        await cmd_monitor.wait_for_pattern(".*Application started.", timeout=180)

        proxy_address_log = await cmd_monitor.wait_for_pattern(
            ".*local_proxy_address.*", timeout=10
        )
        try:
            url = json.loads(
                proxy_address_log[proxy_address_log.index("{") : proxy_address_log.rindex("}") + 1]
            )["http"]["local_proxy_address"]
        except (ValueError, KeyError) as err:
            raise AssertionError(
                f"Couldn't retrieve http node url address from {proxy_address_log}"
            ) from err
        payload = "Hello from Goth"
        requests.post(url, data={"message": payload})
        response = requests.get(url)
        assert response.status_code == 200, response.text
        assert payload in response.text

        process = await process_monitor.get_process()
        process.send_signal(signal.SIGINT)
        await cmd_monitor.wait_for_pattern(".*Shutting down ...", timeout=30)
        await cmd_monitor.wait_for_pattern(".*Shutdown completed", timeout=30)
