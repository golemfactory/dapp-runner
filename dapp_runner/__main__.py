"""Main entry point to `dapp_runner`."""
import logging
from pathlib import Path
from typing import Optional, Tuple

import click


logger = logging.getLogger(__name__)


def common_options(wrapped_func):
    wrapped_func = click.option(
        "--app-id",
        type=str,
        help="ID of an existing distributed application.",
    )(wrapped_func)
    return wrapped_func


@click.group()
def _cli():
    pass


@_cli.command()
@common_options
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
    app_id: Optional[str],
    data: Optional[Path],
    log: Optional[Path],
    state: Optional[Path],
    config: Path,
    descriptors: Optional[Tuple[Path]],
) -> str:
    """Start a dApp based on the provided configuration and set of descriptor files."""


if __name__ == "__main__":
    _cli()
