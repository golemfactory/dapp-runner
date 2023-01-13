"""Runner's input streams."""
import asyncio
import logging
from typing import Callable, Optional, TextIO

logger = logging.getLogger(__name__)

FILE_READ_INTERVAL = 1.0


async def feed_from_file(
    q: asyncio.Queue,
    f: TextIO,
    process_callback: Optional[Callable] = None,
):
    """Feed and ascyncio queue from a `TextIO` buffer (e.g. file)."""

    while True:
        msg = f.readline()
        if msg:
            try:
                if process_callback:
                    msg = process_callback(msg)
                await q.put(msg)
            except Exception as e:
                logger.error("Exception while processing a message: %s, msg: %s", e, msg)
        else:
            await asyncio.sleep(FILE_READ_INTERVAL)
