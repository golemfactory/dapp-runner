import asyncio
import socket
from asyncio import Task
from datetime import datetime, timezone
from typing import Any, Generator

import statemachine
from colors import yellow

from yapapi import Golem
from yapapi import __version__ as yapapi_version

from dapp_runner.singleton import SingletonMeta


class FreePortProvider(metaclass=SingletonMeta):
    """Provide free port to reserve by dapp-runner.

    Usage of singleton prevents race condition on single dapp-runner instance
    when reserving free ports.
    This is temporary solution until issue https://github.com/golemfactory/yapapi/issues/1098
    is resolved and proper fix can be implemented.
    """

    _generator: Generator[int, None, None]

    def __init__(self, range_start: int = 8080, range_end: int = 9090):
        self._generator = self._free_port_generator(range_start, range_end)

    def _free_port_generator(
        self, range_start: int = 8080, range_end: int = 9090
    ) -> Generator[int, None, None]:
        """Yield the first available port on localhost within the specified range.

        The range is inclusive on both sides (i.e. `range_end` will be included).
        Raises `RuntimeError` when no free port could be found.
        """
        return_port = None
        for port in range(range_start, range_end + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    return_port = port
                except OSError:
                    pass
            if return_port is not None:
                yield return_port
                return_port = None

        raise RuntimeError(f"No free ports found. range_start={range_start}, range_end={range_end}")

    def get_free_port(self) -> int:
        """Get next available port on localhost."""
        return next(self._generator)


def _print_env_info(golem: Golem):
    print(
        f"yapapi version: {yellow(yapapi_version)}\n"
        f"Using subnet: {yellow(golem.subnet_tag)}, "
        f"payment driver: {yellow(golem.payment_driver)}, "
        f"and network: {yellow(golem.payment_network)}\n"
    )


def utcnow() -> datetime:
    """Get a timezone-aware datetime for _now_."""
    return datetime.now(tz=timezone.utc)


def utcnow_iso_str() -> str:
    """Get ISO formatted timezone-aware string for _now_."""
    return utcnow().isoformat()


def json_encoder(obj: Any):
    """Handle additional object types for `json.dump*` encoding."""

    if isinstance(obj, statemachine.State):
        return obj.name

    return obj


async def cancel_and_await_tasks(*tasks: Task) -> None:
    """Cancel and await cleanup of provided tasks."""

    # Mark all remaining tasks as cancelled at once
    for task in tasks:
        task.cancel()

    # Give tasks a chance for cleanup by awaiting and
    #  expecting CancelledError (default asyncio behaviour)
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
