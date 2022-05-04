"""Components that manage Dapp Runner's data and state streams."""
import asyncio
from collections import defaultdict
from dataclasses import dataclass

from typing import Callable, Dict, List, Optional, TextIO, Any, TypeVar, Generic

Msg = TypeVar("Msg")


@dataclass
class RunnerStream(Generic[Msg]):
    """Dapp Runner's output stream manager."""

    queue: asyncio.Queue
    stream: TextIO
    process_callback: Optional[Callable] = None
    """callback processing the queue messages"""

    async def update(self):
        """Await the queue and write to the output stream."""
        while True:
            try:
                msg = await self.queue.get()
            except asyncio.CancelledError:
                return

            if self.process_callback:
                msg = self.process_callback(msg)

            self.stream.write(str(msg) + "\n")


class RunnerStreamer:
    """Dapp Runner's stream writer."""

    _streams: Dict[asyncio.Queue, List[RunnerStream]]
    _tasks: List[asyncio.Task]

    def __init__(self):
        self._streams = defaultdict(list)
        self._tasks = []

    def register_stream(
        self,
        runner_queue: asyncio.Queue,
        stream: TextIO,
        process_callback: Optional[Callable] = None,
    ):
        """Register a stream and run the stream update task."""

        if runner_queue not in self._streams:
            self._init_queue(runner_queue)

        runner_stream: RunnerStream[Any] = RunnerStream(
            asyncio.Queue(), stream, process_callback
        )
        self._streams[runner_queue].append(runner_stream)
        self._tasks.append(asyncio.create_task(runner_stream.update()))

    async def _feed_queue(self, queue: asyncio.Queue):
        while True:
            try:
                msg = await queue.get()
            except asyncio.CancelledError:
                return

            for runner_stream in self._streams[queue]:
                runner_stream.queue.put_nowait(msg)

    def _init_queue(self, runner_queue: asyncio.Queue):
        """Start the feed task for the given queue."""
        self._tasks.append(asyncio.create_task(self._feed_queue(runner_queue)))

    async def stop(self):
        """Stop the stream feed tasks."""
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks)
