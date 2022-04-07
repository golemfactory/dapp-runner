import asyncio
from datetime import datetime, timedelta
import os

from pathlib import Path
from dapp_runner.descriptor.parser import load_yamls
from dapp_runner.descriptor import Dapp, Config

from typing import Dict

# UGLY, DIRTY POC OF A POC

from yapapi import (
    Golem,
    windows_event_loop_fix,
    __version__ as yapapi_version,
)
from yapapi.services import Cluster, ServiceState
from yapapi.log import enable_default_logger


TEXT_COLOR_RED = "\033[31;1m"
TEXT_COLOR_GREEN = "\033[32;1m"
TEXT_COLOR_YELLOW = "\033[33;1m"
TEXT_COLOR_BLUE = "\033[34;1m"
TEXT_COLOR_MAGENTA = "\033[35;1m"
TEXT_COLOR_CYAN = "\033[36;1m"
TEXT_COLOR_WHITE = "\033[37;1m"

TEXT_COLOR_DEFAULT = "\033[0m"


STARTING_TIMEOUT = timedelta(minutes=4)


async def main():
    config = await Config.new(load_yamls(Path("configs/default.yaml")))
    appkey = os.getenv("YAGNA_APPKEY")
    config.yagna.app_key = appkey
    dapp = await Dapp.new(load_yamls(Path("examples/simple-service.yaml")))

    async with Golem(
        budget=config.payment.budget,
        subnet_tag=config.yagna.subnet_tag,
        payment_driver=config.payment.driver,
        payment_network=config.payment.network,
    ) as golem:
        print_env_info(golem)

        commissioning_time = datetime.now()

        print(
            f"{TEXT_COLOR_YELLOW}"
            f"Starting..."
            f"{TEXT_COLOR_DEFAULT}"
        )

        clusters: Dict[str, Cluster] = {}

        # start the services
        for cluster_name, cluster_class in dapp.nodes.items():
            clusters[cluster_name] = await golem.run_service(
                cluster_class,
            )

        cluster = clusters["simple-service"]

        # helper functions to display / filter instances

        def instances():
            return [f"{s.provider_name}: {s.state.value}" for s in cluster.instances]

        def still_starting():
            return len(cluster.instances) < 1 or any(
                s.state == ServiceState.starting for s in cluster.instances
            )

        # wait until instances are started

        while still_starting() and datetime.now() < commissioning_time + STARTING_TIMEOUT:
            print(f"instances: {instances()}")
            await asyncio.sleep(5)

        if still_starting():
            raise Exception(f"Failed to start instances before {STARTING_TIMEOUT} elapsed :( ...")

        print(f"{TEXT_COLOR_YELLOW}All instances started :){TEXT_COLOR_DEFAULT}")

        # allow the service to run for a short while
        # (and allowing its requestor-end handlers to interact with it)

        start_time = datetime.now()

        while datetime.now() < start_time + timedelta(seconds=300):
            print(f"instances: {instances()}")
            await asyncio.sleep(5)

        print(f"{TEXT_COLOR_YELLOW}Stopping instances...{TEXT_COLOR_DEFAULT}")
        cluster.stop()

        # wait for instances to stop

        cnt = 0
        while cnt < 10 and any(s.is_available for s in cluster.instances):
            print(f"instances: {instances()}")
            await asyncio.sleep(5)

    print(f"instances: {instances()}")













def print_env_info(golem: Golem):
    print(
        f"yapapi version: {TEXT_COLOR_YELLOW}{yapapi_version}{TEXT_COLOR_DEFAULT}\n"
        f"Using subnet: {TEXT_COLOR_YELLOW}{golem.subnet_tag}{TEXT_COLOR_DEFAULT}, "
        f"payment driver: {TEXT_COLOR_YELLOW}{golem.payment_driver}{TEXT_COLOR_DEFAULT}, "
        f"and network: {TEXT_COLOR_YELLOW}{golem.payment_network}{TEXT_COLOR_DEFAULT}\n"
    )


if __name__ == "__main__":
    # This is only required when running on Windows with Python prior to 3.8:
    windows_event_loop_fix()

    enable_default_logger(
        debug_activity_api=True,
        debug_market_api=True,
        debug_payment_api=True,
        debug_net_api=True,
    )

    loop = asyncio.get_event_loop()
    task = loop.create_task(main())

    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        print(
            f"{TEXT_COLOR_YELLOW}"
            "Shutting down gracefully, please wait a short while "
            "or press Ctrl+C to exit immediately..."
            f"{TEXT_COLOR_DEFAULT}"
        )
        task.cancel()
        try:
            loop.run_until_complete(task)
            print(
                f"{TEXT_COLOR_YELLOW}Shutdown completed, thank you for waiting!{TEXT_COLOR_DEFAULT}"
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
