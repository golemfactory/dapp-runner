"""Main Dapp Runner module."""
import asyncio
from dataclasses import asdict
from datetime import datetime
import logging
from typing import Optional, Dict, List, Final

from yapapi import Golem
from yapapi.contrib.service.http_proxy import LocalHttpProxy
from yapapi.contrib.service.socket_proxy import SocketProxy
from yapapi.events import CommandExecuted
from yapapi.network import Network
from yapapi.payload import Payload
from yapapi.services import Cluster, Service, ServiceState

from dapp_runner.descriptor import Config, DappDescriptor
from dapp_runner.descriptor.dapp import PortMapping, ServiceDescriptor
from dapp_runner._util import get_free_port, utcnow

from .payload import get_payload
from .service import get_service, DappService

LOCAL_HTTP_PROXY_DATA_KEY: Final[str] = "local_proxy_address"
LOCAL_TCP_PROXY_DATA_KEY: Final[str] = "local_tcp_proxy_address"
DEPENDENCY_WAIT_INTERVAL: Final[float] = 1.0

logger = logging.getLogger(__name__)


class Runner:
    """Distributed application runner.

    Taking the yagna configuration and distributed application descriptor, the Runner
    uses yapapi to run the desired app on Golem and allows interacting with it.
    """

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

    data_queue: asyncio.Queue
    state_queue: asyncio.Queue

    def __init__(self, config: Config, dapp: DappDescriptor):
        self.config = config
        self.dapp = dapp

        self.golem = Golem(
            budget=config.payment.budget,
            subnet_tag=config.yagna.subnet_tag,
            payment_driver=config.payment.driver,
            payment_network=config.payment.network,
            app_key=config.yagna.app_key,
        )

        self.clusters = {}
        self._payloads = {}
        self._http_proxies = {}
        self._tcp_proxies = {}
        self._networks = {}
        self._tasks = []
        self.data_queue = asyncio.Queue()
        self.state_queue = asyncio.Queue()
        self._startup_finished = False

    async def _create_networks(self):
        for name, desc in self.dapp.networks.items():
            self._networks[name] = await self.golem.create_network(**asdict(desc))

    async def _load_payloads(self):
        for name, desc in self.dapp.payloads.items():
            self._payloads[name] = await get_payload(desc)

    async def _start_local_http_proxy(
        self, name: str, cluster: Cluster, port_mapping: PortMapping
    ):
        # wait until the service is running before starting the proxy
        while not self._is_cluster_state(name, ServiceState.running):
            await asyncio.sleep(DEPENDENCY_WAIT_INTERVAL)

        port = port_mapping.local_port or get_free_port()
        proxy = LocalHttpProxy(cluster, port)
        await proxy.run()

        self._http_proxies[name] = proxy
        self.data_queue.put_nowait(
            {name: {LOCAL_HTTP_PROXY_DATA_KEY: f"http://localhost:{port}"}}
        )

    async def _start_local_tcp_proxy(
        self, name: str, service: Service, port_mapping: PortMapping
    ):
        # wait until the service is running before starting the proxy
        while not self._is_cluster_state(name, ServiceState.running):
            await asyncio.sleep(DEPENDENCY_WAIT_INTERVAL)

        port = port_mapping.local_port or get_free_port()
        proxy = SocketProxy([port])
        await proxy.run_server(service, port_mapping.remote_port)

        self._tcp_proxies[name] = proxy
        self.data_queue.put_nowait(
            {name: {LOCAL_TCP_PROXY_DATA_KEY: f"localhost:{port}"}}
        )

    async def _start_service(
        self, service_name: str, service_descriptor: ServiceDescriptor
    ):
        # if this service depends on another, wait until the dependency is up
        if service_descriptor.depends_on:
            for depends_name in service_descriptor.depends_on:
                while depends_name not in self.clusters or not self._is_cluster_state(
                    depends_name, ServiceState.running
                ):
                    await asyncio.sleep(DEPENDENCY_WAIT_INTERVAL)

        logger.debug(
            "Starting service: %s, descriptor: %s", service_name, service_descriptor
        )
        cluster_class, run_params = await get_service(
            service_name, service_descriptor, self._payloads, self._networks
        )
        cluster = await self.start_cluster(service_name, cluster_class, run_params)

        # start the tasks for the local proxies so that
        # it doesn't delay the initialization process
        if service_descriptor.http_proxy:
            for port in service_descriptor.http_proxy.ports:
                self._tasks.append(
                    asyncio.create_task(
                        self._start_local_http_proxy(service_name, cluster, port)
                    )
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
                    asyncio.create_task(self._listen_state_queue(s)),
                    asyncio.create_task(self._listen_data_queue(service_name, idx, s)),
                ]
            )

    async def _start_services(self):
        for service_name, service_descriptor in self.dapp.nodes_prioritized():
            await self._start_service(service_name, service_descriptor)

        self._startup_finished = True

    async def start(self):
        """Start the Golem engine and the dapp."""
        self.commissioning_time = utcnow()
        await self.golem.start()

        await self._create_networks()
        await self._load_payloads()

        # we start services in a separate task,
        # so that the service state can be tracked
        # while the dapp is starting
        self._tasks.append(asyncio.create_task(self._start_services()))

    async def start_cluster(self, cluster_name, cluster_class, run_params):
        """Start a single cluster for this dapp."""
        cluster = await self.golem.run_service(cluster_class, **run_params)
        self.clusters[cluster_name] = cluster
        return cluster

    @property
    def dapp_state(self) -> dict:
        """Return the state of the dapp.

        State of the dapp is a dictionary containing the state of all the
        Clusters and their Service instances comprising the dapp.
        """

        return {
            cluster_id: {
                idx: self.clusters[cluster_id].instances[idx].state.name
                for idx in range(len(self.clusters[cluster_id].instances))
            }
            for cluster_id in self.clusters.keys()
        }

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

    async def _listen_state_queue(self, service: DappService):
        """On a state change of the instance, update the Runner's state stream."""
        while True:
            try:
                await service.state_queue.get()
            except asyncio.CancelledError:
                return

            # on a state change, we're publishing the state of the whole dapp
            self.state_queue.put_nowait(self.dapp_state)

    async def _listen_data_queue(
        self, cluster_name: str, idx: int, service: DappService
    ):
        """Pass data messages from the instance to the Runner's queue."""
        while True:
            try:
                msg = await service.data_queue.get()
            except asyncio.CancelledError:
                return

            self.data_queue.put_nowait(
                {cluster_name: {idx: self._process_data_message(msg)}}
            )

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

    def _is_cluster_state(self, cluster_id: str, state: ServiceState) -> bool:
        """Return True if the state of all instances in the cluster is `state`."""
        return all(s.state == state for s in self.clusters[cluster_id].instances)

    async def stop(self):
        """Stop the dapp and the Golem engine."""
        service_tasks: List[asyncio.Task] = []

        proxy_tasks = [p.stop() for p in self._http_proxies.values()]
        proxy_tasks.extend([p.stop() for p in self._tcp_proxies.values()])
        await asyncio.gather(*proxy_tasks)

        for cluster in self.clusters.values():
            cluster.stop()

            for s in cluster.instances:
                service_tasks.extend(s._tasks)

        networks = self._networks.values()
        await asyncio.gather(*[n.remove() for n in networks])

        await self.golem.stop()

        await asyncio.gather(*service_tasks)
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks)
