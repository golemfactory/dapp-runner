"""Main Dapp Runner module."""
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List

from yapapi import Golem
from yapapi.payload import Payload
from yapapi.services import Cluster, ServiceState

from dapp_runner.descriptor import Config, DappDescriptor

from .payload import get_payload
from .service import get_service, DataReceivedEvent


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

    async def _monitor_state_changes(self):
        #   NOTE: in the future `yapapi` should emit a ServiceStateChanged event whenever service
        #         changes state and then we'll remove the loop/task and replace it with
        #         _state_event_consumer, just like the _data_event_consumer below
        prev_state = self.dapp_state
        while True:
            await asyncio.sleep(0.01)
            new_state = self.dapp_state
            if new_state != prev_state:
                self.state_queue.put_nowait(new_state)
                prev_state = new_state

    def _data_event_consumer(self, event: DataReceivedEvent) -> None:
        cluster_name = next(name for name, cluster in self.clusters.items() if cluster is event.service.cluster)
        instance_idx = event.service.cluster.instances.index(event.service)
        self.data_queue.put_nowait(
            {cluster_name: {instance_idx: event.data}}
        )

    async def _load_payloads(self):
        for name, desc in self.dapp.payloads.items():
            self._payloads[name] = await get_payload(desc)

    async def start(self):
        """Start the Golem engine and the dapp."""
        self.commissioning_time = datetime.now(tz=timezone.utc)
        self._tasks.append(asyncio.create_task(self._monitor_state_changes()))
        self.golem.add_event_consumer(self._data_event_consumer, [DataReceivedEvent])
        await self.golem.start()

        await self._load_payloads()

        for service_name, service_descriptor in self.dapp.nodes.items():
            cluster_class = await get_service(
                service_name, service_descriptor, self._payloads
            )
            await self.start_cluster(service_name, cluster_class)

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

    def _is_cluster_state(self, cluster_id: str, state: ServiceState) -> bool:
        """Return True if the state of all instances in the cluster is `state`."""
        return all(s.state == state for s in self.clusters[cluster_id].instances)

    async def stop(self):
        """Stop the dapp and the Golem engine."""

        for cluster in self.clusters.values():
            cluster.stop()

        await self.golem.stop()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks)
