"""yapapi Service bindings."""
import asyncio
from typing import Dict, List, Tuple, Type, Optional


from yapapi.contrib.service.http_proxy import HttpProxyService
from yapapi.network import Network
from yapapi.payload import Payload
from yapapi.services import Service, ServiceState

from dapp_runner.descriptor.dapp import (
    ServiceDescriptor,
    CommandDescriptor,
    EXEUNIT_CMD_RUN,
)

from .error import RunnerError


class DappService(Service):
    """Yapapi Service definition for the Dapp Runner services."""

    init: List[CommandDescriptor]
    _previous_state: Optional[ServiceState] = None
    _tasks: List[asyncio.Task]

    data_queue: asyncio.Queue
    state_queue: asyncio.Queue

    def __init__(self, init: List[CommandDescriptor], **kwargs):
        super().__init__(**kwargs)
        self.init = init
        self._tasks = []

        # initialize output queues
        self.data_queue = asyncio.Queue()
        self.state_queue = asyncio.Queue()

        self._report_state_change()

    def _report_state_change(self):
        state = self.state
        if self._previous_state != state:
            self.state_queue.put_nowait(self.state)
            self._previous_state = state

    async def start(self):
        """Start the service on a given provider."""

        # initialize the state change report
        self._report_state_change()

        # and start the task that will report termination of the service
        self._tasks.append(asyncio.create_task(self._wait_for_termination()))

        # perform the initialization of the Service
        # (which includes sending the network details within the `deploy` command)
        async for script in super().start():
            yield script

        if self.init:
            script = self._ctx.new_script()  # type: ignore  # noqa - it's asserted in super().start()
            for c in self.init:
                if c.cmd == EXEUNIT_CMD_RUN:
                    params = dict(c.params)
                    args = params.pop("args")
                    script.run(*args, **params)
                else:
                    raise RunnerError(f"Unsupported command: `{c.cmd}`.")
            init_output = yield script

            self.data_queue.put_nowait(await init_output)

    async def run(self):
        """Report a state change after switching to `running`."""
        self._report_state_change()

        async for script in super().run():
            yield script

    async def shutdown(self):
        """Report a state change after switching to `stopping`."""
        self._report_state_change()

        async for script in super().shutdown():
            yield script

    async def _wait_for_termination(self):
        while self._previous_state != ServiceState.terminated:
            await asyncio.sleep(1.0)
            self._report_state_change()


class HttpProxyDappService(DappService, HttpProxyService):
    """Yapapi Service definition enabling HTTP proxy for dapps."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


async def get_service(
    name: str,
    desc: ServiceDescriptor,
    payloads: Dict[str, Payload],
    networks: Dict[str, Network],
) -> Tuple[Type[Service], dict]:
    """Create a service class corresponding with its descriptor."""

    try:
        payload_instance = payloads[desc.payload]
    except KeyError:
        raise RunnerError(f'Undefined payload: "{desc.payload}"')

    service_instance_params: dict = {}
    service_instance_params["init"] = desc.init

    DappServiceClass = type(
        f"DappService-{name}",
        (DappService,),
        {},
    )

    if desc.http_proxy:
        if len(desc.http_proxy.ports) > 1:
            raise NotImplementedError(
                "Multiple port mappings are not currently supported."
            )

        port_mapping = desc.http_proxy.ports[0]
        service_instance_params["remote_port"] = port_mapping.remote_port
        DappServiceClass = type(
            f"DappService-{name}",
            (HttpProxyDappService,),
            {},
        )

    run_service_kwargs: dict = {
        "payload": payload_instance,
        "instance_params": [service_instance_params],
    }

    if desc.network:
        try:
            network = networks[desc.network]
        except KeyError:
            raise RunnerError(f'Undefined network: "{desc.network}"')

        run_service_kwargs["network"] = network

    if desc.ip:
        run_service_kwargs["network_addresses"] = desc.ip

    return DappServiceClass, run_service_kwargs
