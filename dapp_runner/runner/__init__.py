import asyncio
from colors import yellow
from datetime import datetime, timedelta, timezone
from pathlib import Path

from yapapi.log import enable_default_logger

from dapp_runner.descriptor import Config, DappDescriptor
from dapp_runner._util import _print_env_info

from .runner import Runner

STARTING_TIMEOUT = timedelta(minutes=4)


async def _run_app(
    config_dict: dict, dapp_dict: dict, data: Path, log: Path, state: Path
):
    """Run the dapp using the Runner."""
    config = Config.load(config_dict)
    dapp = DappDescriptor.load(dapp_dict)

    enable_default_logger(
        log_file=str(log),
        debug_activity_api=True,
        debug_market_api=True,
        debug_payment_api=True,
        debug_net_api=True,
    )

    r = Runner(config=config, dapp=dapp)
    _print_env_info(r.golem)

    await r.start()
    assert r.commissioning_time  # sanity check for mypy
    try:
        while (
            not r.dapp_started
            and datetime.now(timezone.utc) < r.commissioning_time + STARTING_TIMEOUT
        ):
            print(r.dapp_state)
            await asyncio.sleep(5)

        if not r.dapp_started:
            raise Exception(
                f"Failed to start instances before {STARTING_TIMEOUT} elapsed."
            )

        print(yellow("Dapp started."))

        while r.dapp_started:
            print(r.dapp_state)
            await asyncio.sleep(5)

    except asyncio.CancelledError:
        pass
    finally:
        print(yellow("Stopping the dapp..."))
        await r.stop()


def start_runner(
    config_dict: dict, dapp_dict: dict, data: Path, log: Path, state: Path
):
    """Launch the runner in an asyncio loop and wait for its shutdown."""

    loop = asyncio.get_event_loop()
    task = loop.create_task(_run_app(config_dict, dapp_dict, data, log, state))

    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        print(yellow("Shutting down ..."))
        task.cancel()
        try:
            loop.run_until_complete(task)
            print(yellow("Shutdown completed"))
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
