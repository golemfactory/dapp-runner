import asyncio
from colors import cyan, magenta, green
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import sys
import traceback
from typing import TextIO, Optional

from dapp_runner.descriptor import Config, DappDescriptor, DescriptorError
from dapp_runner._util import _print_env_info, utcnow

from .runner import Runner
from .error import RunnerError
from .streams import RunnerStreamer

DEFAULT_STARTUP_TIMEOUT = 240  # seconds

logger = logging.getLogger(__name__)


def _running_time_elapsed(
    time_started: Optional[datetime],
    max_running_time: Optional[timedelta],
) -> bool:
    return bool(
        time_started and max_running_time and utcnow() > time_started + max_running_time
    )


async def _run_app(
    config_dict: dict,
    dapp_dict: dict,
    data_f: TextIO,
    state_f: TextIO,
    silent=False,
):
    """Run the dapp using the Runner."""
    config = Config.load(config_dict)
    dapp = DappDescriptor.load(dapp_dict)

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

    startup_timeout = timedelta(
        seconds=config.limits.startup_timeout or DEFAULT_STARTUP_TIMEOUT
    )

    max_running_time: Optional[timedelta] = None
    if config.limits.max_running_time:
        max_running_time = timedelta(seconds=config.limits.max_running_time)

    logger.info(
        "Starting app: %s, startup timeout: %s, maximum running time: %s",
        dapp.meta.name,
        startup_timeout,
        max_running_time,
    )

    time_started: Optional[datetime] = None

    try:
        while not r.dapp_started and utcnow() < r.commissioning_time + startup_timeout:
            await asyncio.sleep(1)

        if not r.dapp_started:
            raise Exception(
                f"Failed to start instances before {startup_timeout} elapsed."
            )

        time_started = utcnow()
        logger.info("Application started.")

        while r.dapp_started and not _running_time_elapsed(
            time_started, max_running_time
        ):
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Sigint received.")
    finally:
        if _running_time_elapsed(time_started, max_running_time):
            logger.info("Maximum running time: %s elapsed.", max_running_time)

        logger.info("Stopping the application...")
        await r.stop()
        await streamer.stop()


def start_runner(
    config_dict: dict,
    dapp_dict: dict,
    data: Path,
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
            _run_app(config_dict, dapp_dict, data_f, state_f, silent)
        )

        try:
            loop.run_until_complete(task)
        except KeyboardInterrupt:
            logger.info("Shutting down ...")
            task.cancel()
            try:
                loop.run_until_complete(task)
                logger.info("Shutdown completed")
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
