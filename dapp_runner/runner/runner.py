"""Main Dapp Runner module."""
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List

from yapapi import Golem
from yapapi.events import CommandExecuted
from yapapi.payload import Payload
from yapapi.services import Cluster, ServiceState

from dapp_runner.descriptor import Config, DappDescriptor

from .payload import get_payload
from .service import (
    get_service,
    DappService,
    DappServiceMessage,
    DappServiceMessageType,
)


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
    _tasks: List[asyncio.Task]

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
        self._tasks = []
        self.data_queue = asyncio.Queue()
        self.state_queue = asyncio.Queue()

    async def _load_payloads(self):
        for name, desc in self.dapp.payloads.items():
            self._payloads[name] = await get_payload(desc)

    async def start(self):
        """Start the Golem engine and the dapp."""
        self.commissioning_time = datetime.now(tz=timezone.utc)
        await self.golem.start()

        await self._load_payloads()

        for service_name, service_descriptor in self.dapp.nodes.items():
            cluster_class = await get_service(
                service_name, service_descriptor, self._payloads
            )
            cluster = await self.start_cluster(service_name, cluster_class)

            # launch queue listeners for all the service instances
            for idx in range(len(cluster.instances)):
                s = cluster.instances[idx]
                self._tasks.append(
                    asyncio.create_task(
                        self._listen_service_queue(service_name, idx, s)
                    )
                )

    async def start_cluster(self, cluster_name, cluster_class):
        """Start a single cluster for this dapp."""
        cluster = await self.golem.run_service(cluster_class)
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

        return all(
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

    async def _listen_service_queue(
        self, cluster_name: str, idx: int, service: DappService
    ):
        """Pass instance messages to one of the Runner's queues.

        Listen to the out queue of a specific service instance and reflect the received
        message in either the data or the state queue in the Runner.
        """
        while True:
            try:
                signal = await service.receive_message()
            except asyncio.CancelledError:
                return

            msg: DappServiceMessage = signal.message

            if msg.msg_type == DappServiceMessageType.STATE:
                self.state_queue.put_nowait(self.dapp_state)
            elif msg.msg_type == DappServiceMessageType.DATA:
                self.data_queue.put_nowait(
                    {cluster_name: {idx: self._process_data_message(msg.msg)}}
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

        for cluster in self.clusters.values():
            cluster.stop()

            for s in cluster.instances:
                service_tasks.extend(s._tasks)

        await self.golem.stop()
        await asyncio.gather(*service_tasks)
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks)
