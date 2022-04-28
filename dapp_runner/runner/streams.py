"""Components that manage Dapp Runner's data and state streams."""
import asyncio
from dataclasses import dataclass
import enum

from typing import Callable, Dict, List, TextIO, Optional

from .runner import Runner


class StreamType(enum.Enum):
    """Type of output stream."""

    DATA = "data"
    """data output"""

    STATE = "state"
    """state change"""


@dataclass
class RunnerStream:
    """Dapp Runner's output stream manager."""

    queue: asyncio.Queue
    stream: TextIO
    process_callback: Optional[Callable] = None

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

    _runner: Runner
    _streams: Dict[StreamType, List[RunnerStream]]
    _tasks: List[asyncio.Task]

    def __init__(self, runner: Runner):
        self._runner = runner
        self._streams = {}
        self._tasks = []

    def register_stream(
        self,
        stream_type: StreamType,
        stream: TextIO,
        process_callback: Optional[Callable] = None,
    ):
        """Register a stream and run the stream update task."""
        self._streams.setdefault(stream_type, [])
        runner_stream = RunnerStream(asyncio.Queue(), stream, process_callback)
        self._streams[stream_type].append(runner_stream)
        self._tasks.append(asyncio.create_task(runner_stream.update()))

    async def _feed_queue(self, queue: asyncio.Queue, stream_type: StreamType):
        while True:
            try:
                msg = await queue.get()
            except asyncio.CancelledError:
                return

            for runner_stream in self._streams[stream_type]:
                runner_stream.queue.put_nowait(msg)

    def start(self):
        """Create stream feed tasks."""
        self._tasks.extend(
            [
                asyncio.create_task(
                    self._feed_queue(self._runner.data_queue, StreamType.DATA)
                ),
                asyncio.create_task(
                    self._feed_queue(self._runner.state_queue, StreamType.STATE)
                ),
            ]
        )

    async def stop(self):
        """Stop the stream feed tasks."""
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks)
