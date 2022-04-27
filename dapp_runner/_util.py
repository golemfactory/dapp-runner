from datetime import datetime, timezone
from yapapi import Golem, __version__ as yapapi_version
from colors import yellow


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
