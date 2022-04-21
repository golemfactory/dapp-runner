import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Callable, Dict, List, TextIO

from yapapi.log import enable_default_logger

from dapp_runner.descriptor import Config, Dapp
from dapp_runner._util import (
    _print_env_info,
    TEXT_COLOR_CYAN,
    TEXT_COLOR_YELLOW,
    TEXT_COLOR_DEFAULT,
    TEXT_COLOR_MAGENTA,
)

from .runner import Runner

STARTING_TIMEOUT = timedelta(minutes=4)
STATE_INTERVAL = timedelta(seconds=1)
STATE_PRINT_INTERVAL = timedelta(seconds=1)
DATA_QUEUE_INTERVAL = timedelta(seconds=1)
DATA_INTERVAL = timedelta(seconds=1)
DATA_PRINT_INTERVAL = timedelta(seconds=1)


async def _update_stream(
    interval: timedelta,
    stream: TextIO,
    fn: Callable,
    only_changes=True,
    void_value=None,
):
    previous_output = void_value

    def write_stream():
        nonlocal previous_output

        output = fn()
        if output != void_value:
            if not only_changes or output != previous_output:
                stream.write(str(output) + "\n")
            previous_output = output

    try:
        while True:
            write_stream()
            await asyncio.sleep(interval.total_seconds())
    except asyncio.CancelledError:
        write_stream()


async def _run_app(
    config_dict: dict,
    dapp_dict: dict,
    log: Path,
    data_f: TextIO,
    state_f: TextIO,
    silent=False,
):
    """Run the dapp using the Runner."""
    config = await Config.new(config_dict)
    dapp = await Dapp.new(dapp_dict)

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
    data_queues: Dict[str, asyncio.Queue] = {
        "print": asyncio.Queue(),
        "stream": asyncio.Queue(),
    }

    async def feed_data_queues():
        while True:
            data = r.dapp_data()
            if data:
                for q in data_queues.values():
                    q.put_nowait(data)
            await asyncio.sleep(DATA_QUEUE_INTERVAL.total_seconds())

    def get_data(queue_name: str):
        try:
            return data_queues[queue_name].get_nowait()
        except asyncio.QueueEmpty:
            pass

    stream_tasks: List[asyncio.Task] = [
        asyncio.create_task(t)
        for t in [
            feed_data_queues(),
            _update_stream(STATE_INTERVAL, state_f, lambda: json.dumps(r.dapp_state)),
            _update_stream(
                DATA_INTERVAL,
                data_f,
                lambda: json.dumps(get_data("stream")),
                void_value=json.dumps(None),
            ),
        ]
    ]

    if not silent:
        stream_tasks.extend(
            [
                asyncio.create_task(t)
                for t in [
                    _update_stream(
                        STATE_PRINT_INTERVAL,
                        sys.stdout,
                        lambda: f"{TEXT_COLOR_CYAN}{json.dumps(r.dapp_state)}{TEXT_COLOR_DEFAULT}",
                    ),
                    _update_stream(
                        DATA_PRINT_INTERVAL,
                        sys.stdout,
                        lambda: f"{TEXT_COLOR_MAGENTA}{json.dumps(get_data('print'))}{TEXT_COLOR_DEFAULT}",
                        void_value=f"{TEXT_COLOR_MAGENTA}{json.dumps(None)}{TEXT_COLOR_DEFAULT}",
                    ),
                ]
            ]
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

        print(f"{TEXT_COLOR_YELLOW}Dapp started.{TEXT_COLOR_DEFAULT}")

        while r.dapp_started:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    finally:
        print(f"{TEXT_COLOR_YELLOW}Stopping the dapp...{TEXT_COLOR_DEFAULT}")
        await r.stop()

        for t in stream_tasks:
            t.cancel()
        await asyncio.gather(*stream_tasks)


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
            print(f"{TEXT_COLOR_YELLOW}Shutting down ...{TEXT_COLOR_DEFAULT}")
            task.cancel()
            try:
                loop.run_until_complete(task)
                print(f"{TEXT_COLOR_YELLOW}Shutdown completed{TEXT_COLOR_DEFAULT}")
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
