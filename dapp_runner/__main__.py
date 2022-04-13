"""Main entry point to `dapp_runner`."""
from datetime import datetime
import logging
from pathlib import Path
from typing import Tuple

import appdirs
import click
import shortuuid

from dapp_runner import MODULE_AUTHOR, MODULE_NAME
from dapp_runner.descriptor.parser import load_yamls


logger = logging.getLogger(__name__)


@click.group()
def _cli():
    pass


def _get_run_dir(run_id: str) -> Path:
    data_dir = appdirs.user_data_dir(MODULE_NAME, MODULE_AUTHOR)
    app_dir = Path(data_dir) / run_id
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
    required=True,
    type=Path,
    help="Path to the file containing yagna-specific config.",
)
@click.argument(
    "descriptors",
    nargs=-1,
    required=True,
    type=Path,
)
def start(
    descriptors: Tuple[Path],
    **kwargs,
) -> None:
    """Start a dApp based on the provided configuration and set of descriptor files."""
    # TODO: handle the result somehow
    load_yamls(*descriptors)

    # TODO: perhaps include some name from the descriptor in the run ID?
    suffix = shortuuid.ShortUUID().random(length=6)
    start_time = datetime.now().strftime("%Y%m%d_%H:%M:%S%z")
    run_id = f"{suffix}_{start_time}"
    app_dir = _get_run_dir(run_id)

    # Provide default values for data, log and state parameters
    for param_name in ["data", "log", "state"]:
        param_value = kwargs[param_name]
        if not param_value:
            # TODO: pass these arguments further
            kwargs[param_name] = app_dir / param_name


if __name__ == "__main__":
    _cli()
