import asyncio

from pathlib import Path
from dapp_runner.descriptor.parser import load_yamls
from dapp_runner.descriptor import Descriptor


async def test_simple_service_descriptor():
    descriptor = load_yamls(Path("examples/simple-service.yaml"))
    d = Descriptor(descriptor)
    await d.resolve()
    print(d.payloads)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    task = loop.create_task(test_simple_service_descriptor())
    loop.run_until_complete(task)
