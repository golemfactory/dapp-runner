"""Main entry point to `dapp_runner`."""
import logging
from pathlib import Path
from typing import Tuple
import uuid

import appdirs
import click

from dapp_runner import MODULE_AUTHOR, MODULE_NAME
from dapp_runner.descriptor.parser import load_yamls


logger = logging.getLogger(__name__)


def _common_options(wrapped_func):
    wrapped_func = click.option(
        "--app-id",
        type=str,
        help="ID of an existing distributed application.",
    )(wrapped_func)
    return wrapped_func


@click.group()
def _cli():
    pass


def _get_app_dir(app_id: str) -> Path:
    data_dir = appdirs.user_data_dir(MODULE_NAME, MODULE_AUTHOR)
    app_dir = Path(data_dir) / app_id
    app_dir.mkdir(exist_ok=True, parents=True)
    return app_dir


@_cli.command()
@_common_options
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
) -> str:
    """Start a dApp based on the provided configuration and set of descriptor files."""
    app_id = kwargs["app_id"] or str(uuid.uuid4())
    app_dir = _get_app_dir(app_id)

    for param_name in ["data", "log", "state"]:
        param_value = kwargs[param_name]
        if not param_value:
            # TODO: pass these arguments further
            kwargs[param_name] = app_dir / param_name

    # TODO: handle the result somehow
    load_yamls(descriptors)

    return app_id


if __name__ == "__main__":
    _cli()
