"""yapapi Service bindings."""
import attr
from typing import Dict, List, Type

from yapapi.payload import Payload
from yapapi.services import Service
from yapapi.events import ServiceEvent, CommandExecuted

from dapp_runner.descriptor.dapp import ServiceDescriptor

from .error import RunnerError


@attr.s(auto_attribs=True, repr=False)
class DataReceivedEvent(ServiceEvent):
    data: List[Dict]


class DappService(Service):
    """Yapapi Service definition for the Dapp Runner services."""

    entrypoint: List[List[str]]

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
            data_msg = self._prepare_data_msg(await entrypoint_output)
            self._ctx.emit(DataReceivedEvent, service=self, data=data_msg)
    
    @staticmethod
    def _prepare_data_msg(message: List[CommandExecuted]) -> List[Dict]:
        commands_list = []
        for e in message:
            assert isinstance(e, CommandExecuted)
            commands_list.append(
                {
                    "command": e.command.evaluate(),
                    "success": e.success,
                    "stdout": e.stdout,
                    "stderr": e.stderr,
                }
            )
        return commands_list


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
