"""Golem dapp runner.

Utilizes yapapi and yagna to spawn complete decentralized apps on Golem, according
to a specification in the dapp's descriptor.
"""
from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Tuple

import appdirs
import click
import shortuuid


from dapp_runner import MODULE_AUTHOR, MODULE_NAME
from dapp_runner.descriptor.parser import load_yamls
from dapp_runner.runner import start_runner


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
    "--state",
    "-s",
    type=Path,
    help="Path to the state file.",
)
@click.option(
    "--config",
    "-c",
    type=Path,
    required=True,
    help="Path to the file containing yagna-specific config.",
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

    # TODO this should be applied uniformly across any fields,
    # for now, making an exception for the app key
    appkey = config_dict["yagna"].get("app_key", "")
    if appkey.startswith("$"):
        config_dict["yagna"]["app_key"] = os.environ[appkey[1:]]

    # TODO: perhaps include some name from the descriptor in the run ID?
    prefix = shortuuid.ShortUUID().random(length=6)
    start_time = datetime.now().strftime("%Y%m%d_%H:%M:%S%z")
    run_id = f"{prefix}_{start_time}"
    app_dir = _get_run_dir(run_id)

    # Provide default values for data, log and state parameters
    for param_name in ["data", "log", "state"]:
        param_value = kwargs[param_name]
        if not param_value:
            kwargs[param_name] = app_dir / param_name

    start_runner(config_dict, dapp_dict, **kwargs)


if __name__ == "__main__":
    _cli()
