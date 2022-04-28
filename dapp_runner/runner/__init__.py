import asyncio
from colors import yellow, cyan, magenta
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import TextIO

from yapapi.log import enable_default_logger

from dapp_runner.descriptor import Config, DappDescriptor
from dapp_runner._util import _print_env_info

from .runner import Runner
from .streams import RunnerStreamer, StreamType

STARTING_TIMEOUT = timedelta(minutes=4)


async def _run_app(
    config_dict: dict,
    dapp_dict: dict,
    log: Path,
    data_f: TextIO,
    state_f: TextIO,
    silent=False,
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
    streamer = RunnerStreamer(r)
    streamer.start()
    streamer.register_stream(StreamType.STATE, state_f, lambda msg: json.dumps(msg))
    streamer.register_stream(StreamType.DATA, data_f, lambda msg: json.dumps(msg))

    if not silent:
        streamer.register_stream(
            StreamType.STATE, sys.stdout, lambda msg: cyan(json.dumps(msg))
        )
        streamer.register_stream(
            StreamType.DATA, sys.stdout, lambda msg: magenta(json.dumps(msg))
        )

    assert r.commissioning_time  # sanity check for mypy
    try:
        while (
            not r.dapp_started
            and datetime.now(timezone.utc) < r.commissioning_time + STARTING_TIMEOUT
        ):
            await asyncio.sleep(1)

        if not r.dapp_started:
            raise Exception(
                f"Failed to start instances before {STARTING_TIMEOUT} elapsed."
            )

        print(yellow("Dapp started."))

        while r.dapp_started:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    finally:
        print(yellow("Stopping the dapp..."))
        await r.stop()
        await streamer.stop()


def start_runner(
    config_dict: dict,
    dapp_dict: dict,
    data: Path,
    log: Path,
    state: Path,
    silent=False,
):
    """Launch the runner in an asyncio loop and wait for its shutdown."""

    with open(str(state), "w", 1) as state_f, open(str(data), "w", 1) as data_f:

        loop = asyncio.get_event_loop()
        task = loop.create_task(
            _run_app(config_dict, dapp_dict, log, data_f, state_f, silent)
        )

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
