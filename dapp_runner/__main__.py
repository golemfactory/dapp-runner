import asyncio
from datetime import datetime, timedelta, timezone
import os

from pathlib import Path
from dapp_runner.descriptor.parser import load_yamls
from dapp_runner.descriptor import Dapp, Config
from dapp_runner.runner import Runner

from yapapi import (
    Golem,
    windows_event_loop_fix,
    __version__ as yapapi_version,
)
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


def print_env_info(golem: Golem):
    print(
        f"yapapi version: {TEXT_COLOR_YELLOW}{yapapi_version}{TEXT_COLOR_DEFAULT}\n"
        f"Using subnet: {TEXT_COLOR_YELLOW}{golem.subnet_tag}{TEXT_COLOR_DEFAULT}, "
        f"payment driver: {TEXT_COLOR_YELLOW}{golem.payment_driver}{TEXT_COLOR_DEFAULT}, "
        f"and network: {TEXT_COLOR_YELLOW}{golem.payment_network}{TEXT_COLOR_DEFAULT}\n"
    )


async def main():
    config = await Config.new(load_yamls(Path("configs/default.yaml")))
    appkey = os.getenv("YAGNA_APPKEY")
    config.yagna.app_key = appkey
    dapp = await Dapp.new(load_yamls(Path("examples/simple-service.yaml")))

    runner = Runner(config=config, dapp=dapp)
    print_env_info(runner.golem)

    await runner.start()
    try:
        while not runner.dapp_started and datetime.now(timezone.utc) < runner.commissioning_time + STARTING_TIMEOUT:
            print(runner.dapp_state)
            await asyncio.sleep(5)

        if not runner.dapp_started:
            raise Exception(
                f"Failed to start instances before {STARTING_TIMEOUT} elapsed."
            )

        print(f"{TEXT_COLOR_YELLOW}Dapp started.{TEXT_COLOR_DEFAULT}")

        while runner.dapp_started:
            print(runner.dapp_state)
            await asyncio.sleep(5)

    except asyncio.CancelledError:
        pass
    finally:
        print(f"{TEXT_COLOR_YELLOW}Stopping the dapp...{TEXT_COLOR_DEFAULT}")
        await runner.stop()


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
