"""Golem dapp runner.

Utilizes yapapi and yagna to spawn complete decentralized apps on Golem, according
to a specification in the dapp's descriptor.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

import appdirs
import click
import shortuuid

from dapp_runner import MODULE_AUTHOR, MODULE_NAME
from dapp_runner.descriptor.parser import load_yamls
from dapp_runner.log import LOG_CHOICES, LOG_DEBUG, enable_logger
from dapp_runner.runner import start_runner, verify_dapp

logger = logging.getLogger(__name__)


@click.group()
def _cli():
    pass


def _get_data_dir() -> Path:
    data_dir = appdirs.user_data_dir(MODULE_NAME, MODULE_AUTHOR)
    return Path(data_dir)


def _get_run_dir(run_id: str) -> Path:
    app_dir = _get_data_dir() / run_id
    app_dir.mkdir(exist_ok=True, parents=True)
    return app_dir


@_cli.command()
@click.option(
    "--data",
    "-d",
    type=Path,
    help="Path to the data file.",
)
@click.option(
    "--log",
    "-l",
    type=Path,
    help="Path to the log file.",
)
@click.option(
    "--log-level",
    type=click.Choice(LOG_CHOICES, case_sensitive=False),
    default=LOG_DEBUG,
    help="A log level to use while writing the log file",
)
@click.option(
    "--state",
    "-s",
    type=Path,
    help="Path to the state file.",
)
@click.option(
    "--commands",
    type=Path,
    help="Path to the file used to supply ingress commands executed in the running "
    "state. Any contents of the file will be truncated on startup.",
)
@click.option(
    "--stdout",
    type=Path,
    help="Redirect stdout to the specified file.",
)
@click.option(
    "--stderr",
    type=Path,
    help="Redirect stderr to the specified file.",
)
@click.option(
    "--config",
    "-c",
    type=Path,
    required=True,
    help="Path to the file containing yagna-specific config.",
)
@click.option(
    "--dev",
    is_flag=True,
    default=False,
    help="Run in a development mode (enable warnings).",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Display debug messages in the console.",
)
@click.argument(
    "descriptors",
    nargs=-1,
    required=True,
    type=Path,
)
@click.option(
    "--silent",
    is_flag=True,
)
def start(
    descriptors: Tuple[Path],
    config: Path,
    **kwargs,
) -> None:
    """Start a dApp based on the provided configuration and set of descriptor files."""
    dapp_dict = load_yamls(*descriptors)
    config_dict = load_yamls(config)

    # TODO: perhaps include some name from the descriptor in the run ID?
    prefix = shortuuid.ShortUUID().random(length=6)
    start_time = datetime.now().strftime("%Y%m%d_%H_%M_%S%z")
    run_id = f"{prefix}_{start_time}"
    app_dir = _get_run_dir(run_id)

    log_level = str(kwargs.pop("log_level")).upper()

    # Provide default values for data, log and state parameters
    for param_name in ["data", "log", "state", "commands"]:
        param_value = kwargs[param_name]
        if not param_value:
            kwargs[param_name] = app_dir / param_name

    start_runner(config_dict, dapp_dict, log_level=log_level, **kwargs)


@_cli.command()
@click.argument(
    "descriptors",
    nargs=-1,
    required=True,
    type=Path,
)
@click.pass_context
def verify(
    ctx: click.Context,
    descriptors: Tuple[Path],
) -> None:
    """Verify the app descriptor.

    Loads the descriptors and prints the interpreted value
    or reports the encountered error.
    """

    enable_logger(
        log_file=None,
        enable_warnings=True,
    )

    dapp_dict = load_yamls(*descriptors)
    ctx.exit(0 if verify_dapp(dapp_dict) else 1)


if __name__ == "__main__":
    _cli()
