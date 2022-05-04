"""yapapi Service bindings."""
import asyncio
from typing import Dict, List, Type


from yapapi.payload import Payload
from yapapi.services import Service

from dapp_runner.descriptor.dapp import ServiceDescriptor

from .error import RunnerError


class DappService(Service):
    """Yapapi Service definition for the Dapp Runner services."""

    entrypoint: List[List[str]]

    data_queue: asyncio.Queue

    def __init__(self):
        super().__init__()

        # initialize output queues
        self.data_queue = asyncio.Queue()

    async def start(self):
        """Start the service on a given provider."""

        # perform the initialization of the Service
        # (which includes sending the network details within the `deploy` command)
        async for script in super().start():
            yield script

        if self.entrypoint:
            script = self._ctx.new_script()  # type: ignore  # noqa - it's asserted in super().start()
            for c in self.entrypoint:
                script.run(*c)
            entrypoint_output = yield script

            self.data_queue.put_nowait(await entrypoint_output)


async def get_service(
    name: str, desc: ServiceDescriptor, payloads: Dict[str, Payload]
) -> Type[DappService]:
    """Create a service class corresponding with its descriptor."""

    try:
        payload_instance = payloads[desc.payload]
    except KeyError:
        raise RunnerError(f"Undefined payload: `{desc.payload}`")

    async def get_payload():
        return payload_instance

    DappServiceClass = type(
        f"DappService-{name}",
        (DappService,),
        {
            "get_payload": staticmethod(get_payload),
            "entrypoint": desc.entrypoint,
        },
    )

    return DappServiceClass
