from datetime import datetime, timezone
import socket

from yapapi import Golem, __version__ as yapapi_version

from colors import yellow


def get_free_port(range_start: int = 8080, range_end: int = 9090) -> int:
    """Get the first available port on localhost within the specified range.

    The range is inclusive on both sides (i.e. `range_end` will be included).
    Raises `RuntimeError` when no free port could be found.
    """
    for port in range(range_start, range_end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                pass

    raise RuntimeError(
        f"No free ports found. range_start={range_start}, range_end={range_end}"
    )


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
