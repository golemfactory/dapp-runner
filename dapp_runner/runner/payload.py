"""yapapi Payload bindings."""

import inspect
from typing import Dict, Union, Callable, Awaitable

from yapapi.payload import vm, Payload

from dapp_runner.descriptor.dapp import PayloadDescriptor
from .error import RunnerError


async def get_payload(desc: PayloadDescriptor) -> Payload:
    """Create an instance of yapapi Payload for a given runtime type."""
    runtimes: Dict[str, Callable[..., Union[Payload, Awaitable[Payload]]]] = {
        "vm": vm.repo
    }

    if desc.runtime in runtimes.keys():
        payload = runtimes[desc.runtime](**desc.params)
        if inspect.isawaitable(payload):
            return await payload
        return payload  # type: ignore [return-value]  # noqa

    raise RunnerError(f"Unknown runtime: `{desc.runtime}`")
