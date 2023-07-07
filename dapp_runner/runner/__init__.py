import asyncio
import json
import logging
import sys
import traceback
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, TextIO

from colors import cyan, green, magenta

from dapp_runner._util import _print_env_info, cancel_and_await_tasks, json_encoder, utcnow
from dapp_runner.descriptor import Config, DappDescriptor, DescriptorError, manifest
from dapp_runner.log import enable_logger, log_name_to_level

from .error import RunnerError
from .infile import feed_from_file
from .runner import Runner
from .streams import RunnerStreamer

DEFAULT_STARTUP_TIMEOUT = 240  # seconds

logger = logging.getLogger(__name__)


def _running_time_elapsed(
    time_started: Optional[datetime],
    max_running_time: Optional[timedelta],
) -> bool:
    return bool(time_started and max_running_time and utcnow() > time_started + max_running_time)


def _update_api_config(config: Config, api_config_dict: dict):
    arg_field_map = {"enable_api": "enabled", "api_host": "host", "api_port": "port"}

    for k, v in api_config_dict.items():
        if v is not None:
            setattr(config.api, arg_field_map[k], v)


async def _run_app(
    config_dict: dict,
    api_config_dict: dict,
    dapp_dict: dict,
    data_f: TextIO,
    state_f: TextIO,
    commands_f: Optional[TextIO],
    silent=False,
    skip_manifest_validation=False,
    resume=False,
):
    """Run the dapp using the Runner."""

    config = Config(**config_dict)
    _update_api_config(config, api_config_dict)

    dapp = DappDescriptor(**dapp_dict)
    if not skip_manifest_validation:
        manifest.verify_manifests(dapp)

    r = Runner(config=config, dapp=dapp)
    _print_env_info(r.golem)
    if dapp.meta.name:
        print(f"{'Starting' if not resume else 'Resuming'} app: {green(dapp.meta.name)}\n")

    await r.start(resume=resume)
    streamer = RunnerStreamer()
    streamer.register_stream(
        r.state_queue, state_f, lambda msg: json.dumps(msg, default=json_encoder)
    )
    streamer.register_stream(r.data_queue, data_f, lambda msg: json.dumps(msg))
    if commands_f:
        streamer.add_task(feed_from_file(r.command_queue, commands_f, lambda msg: json.loads(msg)))

    if not silent:
        streamer.register_stream(
            r.state_queue,
            sys.stdout,
            lambda msg: cyan(json.dumps(msg, default=json_encoder)),
        )
        streamer.register_stream(r.data_queue, sys.stdout, lambda msg: magenta(json.dumps(msg)))

    assert r.commissioning_time  # sanity check for mypy

    startup_timeout = timedelta(seconds=config.limits.startup_timeout or DEFAULT_STARTUP_TIMEOUT)

    max_running_time: Optional[timedelta] = None
    if config.limits.max_running_time:
        max_running_time = timedelta(seconds=config.limits.max_running_time)

    logger.info(
        f"{'Starting' if not resume else 'Resuming'} app: %s, "
        "startup timeout: %s, maximum running time: %s",
        dapp.meta.name,
        startup_timeout,
        max_running_time,
    )

    time_started: Optional[datetime] = None

    try:
        while (
            not r.dapp_started
            and not r.api_shutdown
            and utcnow() < r.commissioning_time + startup_timeout
        ):
            await asyncio.sleep(1)

        if not r.api_shutdown and not r.dapp_started:
            raise Exception(f"Failed to start instances before {startup_timeout} elapsed.")

        time_started = utcnow()
        logger.info("Application started.")

        while (
            r.dapp_started
            and not r.suspend_requested
            and not r.api_shutdown
            and not _running_time_elapsed(time_started, max_running_time)
        ):
            await asyncio.sleep(1)
    finally:
        if _running_time_elapsed(time_started, max_running_time):
            logger.info("Maximum running time: %s elapsed.", max_running_time)

        if not r.suspend_requested:
            logger.info("Stopping the application...")
            await r.stop()
        else:
            logger.info("Suspending the application...")
            await r.suspend()

        logger.info("Stopping streamer...")
        await streamer.stop()
        logger.info("Streamer stopped...")


def start_runner(
    config_dict: dict,
    api_config_dict: dict,
    dapp_dict: dict,
    data: Path,
    state: Path,
    log: Path,
    dev: bool,
    debug: bool,
    log_level: str,
    commands: Optional[Path] = None,
    stdout: Optional[Path] = None,
    stderr: Optional[Path] = None,
    silent=False,
    skip_manifest_validation=False,
    resume=False,
):
    """Launch the runner in an asyncio loop and wait for its shutdown."""

    with ExitStack() as stack:
        state_f = stack.enter_context(open(str(state), "w", 1))
        data_f = stack.enter_context(open(str(data), "w", 1))

        if stdout:
            stack.enter_context(redirect_stdout(stack.enter_context(open(str(stdout), "w", 1))))

        if stderr:
            stack.enter_context(redirect_stderr(stack.enter_context(open(str(stderr), "w", 1))))

        enable_logger(
            log_file=str(log.resolve()),
            enable_warnings=dev,
            console_log_level=logging.DEBUG if debug else logging.INFO,
            file_log_level=log_name_to_level(log_level),
        )

        commands_f = stack.enter_context(open(str(commands), "w+", 1)) if commands else None

        loop = asyncio.get_event_loop()
        task = loop.create_task(
            _run_app(
                config_dict=config_dict,
                api_config_dict=api_config_dict,
                dapp_dict=dapp_dict,
                data_f=data_f,
                state_f=state_f,
                commands_f=commands_f,
                silent=silent,
                skip_manifest_validation=skip_manifest_validation,
                resume=resume,
            )
        )

        try:
            loop.run_until_complete(task)
        except KeyboardInterrupt:
            logger.info("SIGINT received, shutting down gracefully ...")
            try:
                loop.run_until_complete(cancel_and_await_tasks(task))
            except KeyboardInterrupt:
                logger.info(
                    "Another SIGINT received, graceful shutdown interrupted, exiting immediately."
                )
            else:
                logger.info("Post-SIGINT graceful shutdown completed.")
        except Exception:  # noqa
            sys.stderr.write(traceback.format_exc())


def verify_dapp(dapp_dict: dict):
    """Verify the passed app descriptor schema and report any encountered errors."""
    try:
        dapp = DappDescriptor(**dapp_dict)
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
