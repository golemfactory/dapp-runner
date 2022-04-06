"""Main entry point to `dapp_runner`."""
import logging
from pathlib import Path
from typing import Optional, Tuple

import click


logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
@click.option(
    "--app-id",
    type=str,
    help="ID of an existing distributed application.",
)
def _cli(ctx: click.Context, app_id: str):
    pass


@_cli.command()
@click.pass_context
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
    ctx: click.Context,
    data: Optional[Path],
    log: Optional[Path],
    state: Optional[Path],
    config: Path,
    descriptors: Optional[Tuple[Path]],
) -> str:
    """Start a dApp based on the provided configuration and set of descriptor files."""


if __name__ == "__main__":
    _cli()
