"""Unit tests for dapp_runner.descriptor.service."""
import pytest
from unittest.mock import Mock

from yapapi.ctx import WorkContext, Script
from yapapi.script import Run

from dapp_runner.runner.service import DappService


@pytest.fixture
def mock_work_context():  # noqa
    return WorkContext(Mock(), Mock(), Mock(), Mock())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entrypoint, expected_script",
    [
        (
            (
                [
                    "/bin/test",
                    "blah",
                ],
            ),
            [Run("/bin/test", "blah")],
        ),
        (
            (["/bin/test", "blah"], ["/bin/blah"]),
            [Run("/bin/test", "blah"), Run("/bin/blah")],
        ),
    ],
)
async def test_service_entrypoint(mock_work_context, entrypoint, expected_script):
    """Test if the DappService's entrypoint works as expected."""
    service = DappService()
    service._ctx = mock_work_context
    service.entrypoint = entrypoint
    scripts = []
    async for s in service.start():
        scripts.append(s)

    assert len(scripts) == 2

    entrypoint_script: Script = scripts[1]
    assert len(entrypoint_script._commands) == len(expected_script)

    for i in range(len(expected_script)):
        assert (
            entrypoint_script._commands[i].evaluate() == expected_script[i].evaluate()
        )
