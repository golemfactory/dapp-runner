"""Main Dapp Runner module."""
from datetime import datetime, timezone
from typing import Optional, Dict, List, Generator, Any

from yapapi import Golem
from yapapi.events import CommandExecuted
from yapapi.payload import Payload
from yapapi.services import Cluster, ServiceState

from dapp_runner.descriptor import Config, DappDescriptor

from .payload import get_payload
from .service import get_service


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
            await self.start_cluster(service_name, cluster_class)

    async def start_cluster(self, cluster_name, cluster_class):
        """Start a single cluster for this dapp."""
        self.clusters[cluster_name] = await self.golem.run_service(cluster_class)

    @property
    def dapp_state(self) -> dict:
        """Return the state of the dapp.

        State of the dapp is a dictionary containing the state of the all the
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
        clusters have been started and are remaining running.
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

    @staticmethod
    def _process_data_message(message: List[CommandExecuted]) -> Generator:
        for e in message:
            assert isinstance(e, CommandExecuted)
            yield {
                "command": e.command.evaluate(),
                "success": e.success,
                "stdout": e.stdout,
                "stderr": e.stderr,
            }

    def dapp_data(self):
        """Return data messages accumulated in the Dapp instances."""
        out_messages = {}
        for cluster_id, cluster in self.clusters.items():
            cluster_messages = {}
            for idx in range(len(cluster.instances)):
                instance = cluster.instances[idx]
                instance_messages: List[Dict[str, Any]] = []
                while True:
                    signal = instance.receive_message_nowait()
                    if not signal:
                        break
                    instance_messages.extend(self._process_data_message(signal.message))
                if instance_messages:
                    cluster_messages[idx] = instance_messages
            if cluster_messages:
                out_messages[cluster_id] = cluster_messages
        if out_messages:
            return out_messages

    def _is_cluster_state(self, cluster_id: str, state: ServiceState) -> bool:
        """Return True if the state of all instances in the cluster is `state`."""
        return all(s.state == state for s in self.clusters[cluster_id].instances)

    async def stop(self):
        """Stop the dapp and the Golem engine."""
        for cluster in self.clusters.values():
            cluster.stop()

        await self.golem.stop()
