from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

from yapapi import Golem
from yapapi.services import Cluster, ServiceState

from ..descriptor import Config, Dapp


class Runner:
    config: Config
    dapp: Dapp
    golem: Golem
    clusters: Dict[str, Cluster]
    commissioning_time: Optional[datetime]

    def __init__(self, config: Config, dapp: Dapp):
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

    async def start(self):
        """Start the Golem engine and the dapp."""
        self.commissioning_time = datetime.now(tz=timezone.utc)
        await self.golem.start()

        for cluster_id, cluster_class in self.dapp.nodes.items():
            await self.start_cluster(cluster_id, cluster_class)

    async def start_cluster(self, cluster_name, cluster_class):
        """Start a single cluster for this dapp."""
        self.clusters[cluster_name] = await self.golem.run_service(
            cluster_class
        )

    @property
    def dapp_state(self):
        return {
            cluster_id: self.clusters[cluster_id].instances
            for cluster_id in self.clusters.keys()
        }

    @property
    def dapp_started(self):
        return all([
            self._is_cluster_state(cluster_id, ServiceState.running)
            for cluster_id in self.clusters.keys()
        ])

    @property
    def dapp_terminated(self):
        return all([
            self._is_cluster_state(cluster_id, ServiceState.terminated)
            for cluster_id in self.clusters.keys()
        ])

    def _is_cluster_state(self, cluster_id: str, state: ServiceState) -> bool:
        return all(
            s.state == state
            for s in self.clusters[cluster_id].instances
        )

    async def stop(self):
        """Stop the dapp and the Golem engine."""
        for cluster in self.clusters.values():
            cluster.stop()

        await self.golem.stop()
