"""Goth tests utils."""
import logging
from typing import List

from goth.assertions import EventStream

logger = logging.getLogger("goth.test.test")


async def assert_strings_in_events(
    event_stream: EventStream, strings: List[str], success_message: str
):
    """Check if given strings are present in given event_stream."""
    strings_gen = (s for s in strings)
    expected_string = next(strings_gen, None)
    async for log_line in event_stream:
        if expected_string is not None and expected_string in log_line:
            logger.info(f"found {expected_string} in {log_line}")
            expected_string = next(strings_gen, None)
    assert expected_string is None, f"{[s for s in strings_gen]} were not found"
    return success_message
