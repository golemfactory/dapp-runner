import asyncio
from colors import yellow, cyan, magenta, green
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import traceback
from typing import TextIO, Optional

from yapapi.log import enable_default_logger

from dapp_runner.descriptor import Config, DappDescriptor, DescriptorError
from dapp_runner._util import _print_env_info

from .runner import Runner
from .error import RunnerError
from .streams import RunnerStreamer

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
        log_file=str(log.resolve()),
        debug_activity_api=True,
        debug_market_api=True,
        debug_payment_api=True,
        debug_net_api=True,
    )

    r = Runner(config=config, dapp=dapp)
    _print_env_info(r.golem)
    if dapp.meta.name:
        print(f"Starting app: {green(dapp.meta.name)}\n")

    await r.start()
    streamer = RunnerStreamer()
    streamer.register_stream(r.state_queue, state_f, lambda msg: json.dumps(msg))
    streamer.register_stream(r.data_queue, data_f, lambda msg: json.dumps(msg))

    if not silent:
        streamer.register_stream(
            r.state_queue, sys.stdout, lambda msg: cyan(json.dumps(msg))
        )
        streamer.register_stream(
            r.data_queue, sys.stdout, lambda msg: magenta(json.dumps(msg))
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
    stdout: Optional[Path] = None,
    stderr: Optional[Path] = None,
    silent=False,
):
    """Launch the runner in an asyncio loop and wait for its shutdown."""

    with ExitStack() as stack:
        state_f = stack.enter_context(open(str(state), "w", 1))
        data_f = stack.enter_context(open(str(data), "w", 1))

        if stdout:
            stack.enter_context(
                redirect_stdout(stack.enter_context(open(str(stdout), "w", 1)))
            )

        if stderr:
            stack.enter_context(
                redirect_stderr(stack.enter_context(open(str(stderr), "w", 1)))
            )

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
        except Exception:  # noqa
            sys.stderr.write(traceback.format_exc())


def verify_dapp(dapp_dict: dict):
    """Verify the passed app descriptor schema and report any encountered errors."""
    try:
        dapp = DappDescriptor.load(dapp_dict)
        print(dapp)
    except DescriptorError as e:
        print(e)
        return False

    return True


__all__ = (
    "Runner",
    "RunnerStreamer",
    "RunnerError",
    "start_runner",
    "verify_dapp",
)
