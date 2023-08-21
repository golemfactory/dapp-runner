"""Main Dapp Runner module."""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Final, List, Optional

import uvicorn

from ya_net.exceptions import ApiException
from yapapi import Golem
from yapapi.config import ApiConfig
from yapapi.contrib.service.http_proxy import LocalHttpProxy
from yapapi.contrib.service.socket_proxy import SocketProxy
from yapapi.events import CommandExecuted, Event, ServiceStateChanged
from yapapi.network import Network
from yapapi.payload import Payload
from yapapi.props import com
from yapapi.services import Cluster, Service, ServiceSerialization, ServiceState
from yapapi.strategy import LeastExpensiveLinearPayuMS

from dapp_runner._util import FreePortProvider, cancel_and_await_tasks, utcnow, utcnow_iso_str
from dapp_runner.descriptor import Config, DappDescriptor
from dapp_runner.descriptor.dapp import (
    ActivityDescriptor,
    AgreementDescriptor,
    CommandDescriptor,
    NetworkDescriptor,
    NetworkNodeDescriptor,
    PortMapping,
    ServiceDescriptor,
)

from .error import RunnerError
from .payload import get_payload
from .service import DappService, get_service
from .strategy import BlacklistOnFailure

LOCAL_HTTP_PROXY_DATA_KEY: Final[str] = "local_proxy_address"
LOCAL_HTTP_PROXY_URI: Final[str] = "http://localhost"
LOCAL_TCP_PROXY_DATA_KEY: Final[str] = "local_tcp_proxy_address"
LOCAL_TCP_PROXY_ADDRESS: Final[str] = "localhost"
DEPENDENCY_WAIT_INTERVAL: Final[float] = 1.0

logger = logging.getLogger(__name__)


class Runner:
    """Distributed application runner.

    Taking the yagna configuration and distributed application descriptor, the Runner
    uses yapapi to run the desired app on Golem and allows interacting with it.
    """

    _instance: Optional["Runner"] = None

    config: Config
    dapp: DappDescriptor
    golem: Golem
    clusters: Dict[str, Cluster]
    commissioning_time: Optional[datetime]

    _payloads: Dict[str, Payload]
    _http_proxies: Dict[str, LocalHttpProxy]
    _tcp_proxies: Dict[str, SocketProxy]
    _networks: Dict[str, Network]
    _tasks: List[asyncio.Task]
    _startup_finished: bool
    suspend_requested: bool

    # TODO: Introduce ApplicationState instead of reusing ServiceState
    _desired_app_state: ServiceState

    data_queue: asyncio.Queue
    state_queue: asyncio.Queue
    command_queue: asyncio.Queue

    api_server: Optional[uvicorn.Server]

    def __init__(self, config: Config, dapp: DappDescriptor):
        self.config = config
        self.dapp = dapp

        self._base_strategy = LeastExpensiveLinearPayuMS(
            max_fixed_price=Decimal("1.0"),
            max_price_for={com.Counter.CPU: Decimal("0.2"), com.Counter.TIME: Decimal("0.1")},
        )
        self._blacklist: BlacklistOnFailure = BlacklistOnFailure(self._base_strategy)

        self.golem = Golem(
            budget=config.payment.budget,
            subnet_tag=config.yagna.subnet_tag,
            payment_driver=config.payment.driver,
            payment_network=config.payment.network,
            api_config=ApiConfig(app_key=config.yagna.app_key),  # type: ignore
            strategy=self._blacklist,
        )

        self.golem.add_event_consumer(self._detect_failures, [ServiceStateChanged])

        self.clusters = {}
        self._payloads = {}
        self._http_proxies = {}
        self._tcp_proxies = {}
        self._networks = {}
        self._tasks = []
        self.data_queue = asyncio.Queue()
        self.state_queue = asyncio.Queue()
        self.command_queue = asyncio.Queue()
        self._startup_finished = False
        self.suspend_requested = False
        self._desired_app_state = ServiceState.pending

        self._report_status_change()
        Runner._instance = self

        self.api_server = None
        self.api_shutdown = False

    @classmethod
    def get_instance(cls):
        """Get the Runner instance."""
        return cls._instance

    async def _serve_api(self):
        assert self.api_server, "Uninitialized API server, call `_start_api` first."
        try:
            await self.api_server.serve()
        finally:
            # the uvicorn server seems to consume the SIGINT / CancelledError, so
            # we have to manually mark its shutdown to trigger shutdown of the
            # whole runner
            self.api_shutdown = True

    async def _start_api(self):
        config = uvicorn.Config(
            "dapp_runner.api:app", host=self.config.api.host, port=self.config.api.port
        )
        self.api_server = uvicorn.Server(config)
        self._tasks.append(asyncio.create_task(self._serve_api()))

    async def _create_networks(self, resume=False):
        for name, desc in self.dapp.networks.items():
            if resume and desc.network_id:
                desc_dict = desc.dict()
                if desc_dict.get("mask"):
                    desc_dict["ip"] = f"{desc_dict.get('ip')}/{desc_dict.get('mask')}"
                desc_dict["_network_id"] = desc_dict.pop("network_id")
                desc_dict["nodes"] = {}
                try:
                    network = await self.golem.resume_network(desc_dict)  # type: ignore [arg-type]
                except ApiException:
                    raise RunnerError(
                        f"Could not resume network {desc_dict['_network_id']}. "
                        "Probably it has already been destroyed.",
                    )
            else:
                network = await self.golem.create_network(
                    **{k: getattr(desc, k) for k in {"ip", "owner_ip", "mask", "gateway"}}
                )

            self._networks[name] = network

            self.dapp.networks[name] = NetworkDescriptor.from_network(network)

    async def _load_payloads(self):
        for name, desc in self.dapp.payloads.items():
            self._payloads[name] = await get_payload(desc)

    async def _start_local_http_proxy(self, name: str, cluster: Cluster, port_mapping: PortMapping):
        # wait until the service is running before starting the proxy
        while not self._is_cluster_state(name, ServiceState.running):
            await asyncio.sleep(DEPENDENCY_WAIT_INTERVAL)

        port = port_mapping.local_port or FreePortProvider().get_free_port()
        proxy = LocalHttpProxy(cluster, port)
        await proxy.run()

        self._http_proxies[name] = proxy
        proxy_uri = f"{LOCAL_HTTP_PROXY_URI}:{port}"
        self.data_queue.put_nowait({name: {LOCAL_HTTP_PROXY_DATA_KEY: proxy_uri}})

        # update the GAOM mapping
        port_mapping.local_port = port
        port_mapping.address = proxy_uri

    async def _start_local_tcp_proxy(self, name: str, service: Service, port_mapping: PortMapping):
        # wait until the service is running before starting the proxy
        while not self._is_cluster_state(name, ServiceState.running):
            await asyncio.sleep(DEPENDENCY_WAIT_INTERVAL)

        port = port_mapping.local_port or FreePortProvider().get_free_port()
        proxy = SocketProxy([port])
        await proxy.run_server(service, port_mapping.remote_port)

        self._tcp_proxies[name] = proxy
        proxy_address = f"{LOCAL_TCP_PROXY_ADDRESS}:{port}"
        self.data_queue.put_nowait({name: {LOCAL_TCP_PROXY_DATA_KEY: proxy_address}})

        # update the GAOM mapping
        port_mapping.local_port = port
        port_mapping.address = proxy_address

    async def _start_service(
        self, service_name: str, service_descriptor: ServiceDescriptor, resume=False
    ):
        # if this service depends on another, wait until the dependency is up
        if service_descriptor.depends_on:
            for depends_name in service_descriptor.depends_on:
                while depends_name not in self.clusters or not self._is_cluster_state(
                    depends_name, ServiceState.running
                ):
                    await asyncio.sleep(DEPENDENCY_WAIT_INTERVAL)

        logger.debug("Starting service: %s, descriptor: %s", service_name, service_descriptor)

        service_descriptor.interpolate(self.dapp, is_runtime=True)

        cluster_class, run_params = await get_service(
            service_name, service_descriptor, self._payloads, self._networks
        )
        if not resume:
            cluster = await self.start_cluster(service_name, cluster_class, run_params)
        else:
            run_params["instances"] = [
                ServiceSerialization(
                    params=params,
                    activity_id=service_descriptor.activity.id
                    if service_descriptor.activity
                    else None,
                    agreement_id=service_descriptor.agreement.id
                    if service_descriptor.agreement
                    else None,
                    state=service_descriptor.state or ServiceState.pending.value,
                    network_node=service_descriptor.network_node.dict()
                    if service_descriptor.network_node
                    else None,
                )
                for params in run_params.pop("instance_params")
            ]
            run_params.pop("network_addresses", None)
            cluster = await self.resume_cluster(service_name, cluster_class, run_params)

        # start the tasks for the local proxies so that
        # it doesn't delay the initialization process
        if service_descriptor.http_proxy:
            for port in service_descriptor.http_proxy.ports:
                self._tasks.append(
                    asyncio.create_task(self._start_local_http_proxy(service_name, cluster, port))
                )

        if service_descriptor.tcp_proxy:
            for port in service_descriptor.tcp_proxy.ports:
                for service in cluster.instances:
                    self._tasks.append(
                        asyncio.create_task(
                            self._start_local_tcp_proxy(service_name, service, port)
                        )
                    )

        # launch queue listeners for all the service instances
        for idx in range(len(cluster.instances)):
            s = cluster.instances[idx]
            self._tasks.extend(
                [
                    asyncio.create_task(self._listen_state_queue(s, service_descriptor)),
                    asyncio.create_task(self._listen_data_queue(service_name, idx, s)),
                ]
            )

    async def _start_services(self, resume=False):
        for service_name, service_descriptor in self.dapp.nodes_prioritized():
            await self._start_service(service_name, service_descriptor, resume=resume)

        self._startup_finished = True

    async def start(self, resume=False):
        """Start the Golem engine and the dapp."""

        if self.config.api.enabled:
            await self._start_api()

        self.commissioning_time = utcnow()

        # explicitly mark that we ultimately want app in "running" state,
        # marking app into "starting" sequence.
        self._desired_app_state = ServiceState.running

        await self.golem.start()

        await self._create_networks(resume=resume)
        await self._load_payloads()

        # we start services in a separate task,
        # so that the service state can be tracked
        # while the dapp is starting
        self._tasks.append(asyncio.create_task(self._start_services(resume=resume)))

        # launch the incoming command processor
        self._tasks.append(asyncio.create_task(self._listen_incoming_command_queue()))

    async def start_cluster(self, cluster_name, cluster_class, run_params):
        """Start a single cluster for this dapp."""
        cluster = await self.golem.run_service(cluster_class, **run_params)
        self.clusters[cluster_name] = cluster
        return cluster

    async def resume_cluster(self, cluster_name, cluster_class, run_params):
        """Resume control over an existing service cluster."""
        cluster = await self.golem.resume_service(cluster_class, **run_params)
        self.clusters[cluster_name] = cluster
        return cluster

    @property
    def dapp_state(self) -> Dict[str, Dict[int, ServiceState]]:
        """Return the state of the dapp.

        State of the dapp is a dictionary containing the state of all the
        Clusters and their Service instances comprising the dapp.
        """

        cluster_states = {
            cluster_id: {
                instance_index: instance.state
                for instance_index, instance in enumerate(cluster.instances)
            }
            for cluster_id, cluster in self.clusters.items()
        }

        missing_nodes = set(self.dapp.nodes) - set(cluster_states)

        cluster_states.update({node_id: {} for node_id in missing_nodes})

        return cluster_states

    @property
    def dapp_started(self) -> bool:
        """Return True if the dapp has been started, False otherwise.

        Dapp is considered started if all instances in all commissioned service
        clusters have been started and remain running.
        """

        return self._startup_finished and all(
            [
                self._is_cluster_state(cluster_id, ServiceState.running)
                for cluster_id in self.clusters.keys()
            ]
        )

    @property
    def dapp_terminated(self) -> bool:
        """Return True if the dapp has been terminated, False otherwise.

        Dapp is considered terminated if all instances in all commissioned service
        clusters have been terminated.
        """

        return all(
            [
                self._is_cluster_state(cluster_id, ServiceState.terminated)
                for cluster_id in self.clusters.keys()
            ]
        )

    def _detect_failures(self, event: Event) -> None:
        # just a sanity check
        if not isinstance(event, ServiceStateChanged):
            return

        service = event.service
        if (
            self._desired_app_state == ServiceState.running
            and event.new == ServiceState.terminated
            and service._ctx
        ):
            self._blacklist.blacklist_node(service._ctx.provider_id)
            logger.info(
                "Blacklisting %s (%s) after a failure",
                service._ctx.provider_name,
                service._ctx.provider_id,
            )

    def _update_node_gaom(self, service: DappService, service_descriptor: ServiceDescriptor):
        # update the state in the GAOM
        service_descriptor.state = service.state.identifier

        # update the network node if possible
        if service.network_node and not service_descriptor.network_node:
            service_descriptor.network_node = NetworkNodeDescriptor.from_network_node(
                service.network_node
            )

        # update the activity if possible
        if service._ctx:  # noqa
            ctx = service._ctx  # noqa
            if not service_descriptor.activity:
                service_descriptor.activity = ActivityDescriptor.from_activity(
                    ctx._activity
                )  # noqa

            if not service_descriptor.agreement:
                service_descriptor.agreement = AgreementDescriptor(
                    id=ctx._agreement.id,  # noqa
                    provider_id=ctx.provider_id,
                    provider_name=ctx.provider_name,
                )

        # reset the GAOM state on "pending"
        if service_descriptor.state == "pending":
            service_descriptor.network_node = None
            service_descriptor.activity = None
            service_descriptor.agreement = None

    async def _listen_state_queue(
        self, service: DappService, service_descriptor: ServiceDescriptor
    ):
        """On a state change of the instance, update the Runner's state stream."""
        while True:
            await service.state_queue.get()

            # on a state change, we're publishing the state of the whole dapp
            self._report_status_change()
            self._update_node_gaom(service, service_descriptor)

    def _report_status_change(self) -> None:
        """Emit message with full state update to state queue."""

        nodes_states = self.dapp_state

        self.state_queue.put_nowait(
            {
                "nodes": nodes_states,
                "app": self._get_app_state_from_nodes(nodes_states),
                "timestamp": utcnow_iso_str(),
            }
        )

    def _get_app_state_from_nodes(
        self, dapp_state: Optional[Dict[str, Dict[int, ServiceState]]] = None
    ) -> ServiceState:
        """Return general application state based on all instances states."""
        # Collect nested node states into simple unique collection of state values

        dapp_state = dapp_state or self.dapp_state

        all_states = set(state for node in dapp_state.values() for state in node.values())

        # If we want dapp to be running -> handle other states as starting
        if self._desired_app_state == ServiceState.running:
            # Check node-to-state parity because of node dependency,
            #  states gradually rolls out

            if ({self._desired_app_state} == all_states) and (
                len(dapp_state) == len(self.dapp.nodes)
            ):
                return ServiceState.running

            return ServiceState.starting

        # If we want dapp to be terminated handle other states as stopping
        if self._desired_app_state == ServiceState.terminated:
            if {self._desired_app_state} == all_states:
                return ServiceState.terminated
            else:
                return ServiceState.stopping
        elif self._desired_app_state == ServiceState.suspended:
            return ServiceState.suspended

        # In other cases return pending
        return ServiceState.pending

    async def _listen_data_queue(self, cluster_name: str, idx: int, service: DappService):
        """Pass data messages from the instance to the Runner's queue."""
        while True:
            msg = await service.data_queue.get()

            self.data_queue.put_nowait({cluster_name: {idx: self._process_data_message(msg)}})

    @staticmethod
    def _process_data_message(message: List[CommandExecuted]) -> List[Dict]:
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

    async def _listen_incoming_command_queue(self):
        """Pass data messages from the instance to the Runner's queue."""
        while True:
            msg: Dict = await self.command_queue.get()

            for cluster_name, cluster_cmd_dict in msg.items():
                cluster = self.clusters.get(cluster_name)
                if not cluster:
                    logger.error("Command sent to an unknown service: %s", cluster_name)
                    continue

                if len(cluster_cmd_dict.keys()) != 1:
                    logger.error(
                        "Unknown command message format, "
                        "expecting a single entry: "
                        "`{instance_idx: {<command definition>}`, got %s.",
                        cluster_cmd_dict,
                    )
                    continue

                idx, cmd_def = list(cluster_cmd_dict.items())[0]
                try:
                    service: DappService = cluster.instances[int(idx)]
                except IndexError:
                    logger.error(
                        "Command for a nonexistent instance (`%s` not in `%s`)",
                        idx,
                        cluster_name,
                    )
                    continue

                logger.debug("Creating runtime command: %s", cmd_def)
                cmd = CommandDescriptor(**cmd_def)
                service.command_queue.put_nowait(cmd)

    def _is_cluster_state(self, cluster_id: str, state: ServiceState) -> bool:
        """Return True if the state of all instances in the cluster is `state`."""
        return all(s.state == state for s in self.clusters[cluster_id].instances)

    async def _stop_proxies(self):
        """Stop the HTTP and TCP proxies."""
        proxy_tasks = [p.stop() for p in self._http_proxies.values()]
        proxy_tasks.extend([p.stop() for p in self._tcp_proxies.values()])
        await asyncio.gather(*proxy_tasks)

    async def stop(self):
        """Stop the dapp and the Golem engine."""
        service_tasks: List[asyncio.Task] = []

        # explicitly mark that we want dapp in terminated state
        self._desired_app_state = ServiceState.terminated

        await self._stop_proxies()

        for cluster in self.clusters.values():
            cluster.stop()

            for s in cluster.instances:
                service_tasks.extend(s._tasks)

        networks = self._networks.values()
        await asyncio.gather(*[n.remove() for n in networks])

        await self.golem.stop()

        await asyncio.gather(*service_tasks)

        await cancel_and_await_tasks(*self._tasks)

    def request_suspend(self):
        """Signal the runner to suspend its operation."""
        self.suspend_requested = True

    async def suspend(self):
        """Suspend the application and stop the Golem engine, without killing the activities."""
        service_tasks: List[asyncio.Task] = []

        # explicitly mark that we want dapp in terminated state
        self._desired_app_state = ServiceState.suspended

        await self._stop_proxies()

        for cluster in self.clusters.values():
            cluster.suspend()

            for s in cluster.instances:
                service_tasks.extend(s._tasks)

        await self.golem.stop(wait_for_payments=False)

        await asyncio.gather(*service_tasks)

        await cancel_and_await_tasks(*self._tasks)
