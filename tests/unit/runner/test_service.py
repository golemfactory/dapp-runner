"""Unit tests for dapp_runner.descriptor.service."""
import asyncio

import pytest
from unittest.mock import Mock

from yapapi.ctx import WorkContext, Script
from yapapi.script import Run

from dapp_runner.runner.service import DappService, HttpProxyDappService


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
    service = DappService(entrypoint)
    service._ctx = mock_work_context
    scripts = []
    gen = service.start()

    s = await gen.__anext__()
    while s:
        scripts.append(s)
        future_results = asyncio.get_event_loop().create_future()

        # the mock is sent as the return value of the `yield script` in the service
        mock_exescript_awaitable = asyncio.sleep(0.01)  # type: ignore [var-annotated]

        future_results.set_result(mock_exescript_awaitable)
        try:
            s = await gen.asend(future_results)
        except StopAsyncIteration:
            s = None

    assert len(scripts) == 2

    entrypoint_script: Script = scripts[1]
    assert len(entrypoint_script._commands) == len(expected_script)

    for i in range(len(expected_script)):
        assert (
            entrypoint_script._commands[i].evaluate() == expected_script[i].evaluate()
        )


@pytest.mark.parametrize(
    "service_kwargs, expected_attrs, expected_exc",
    [
        (
            {"entrypoint": ["/some/binary"]},
            {
                "entrypoint": ["/some/binary"],
                "_remote_port": 80,
                "_remote_host": None,
                "_remote_response_timeout": 10.0,
            },
            None,
        ),
        (
            {
                "entrypoint": ["/some/binary"],
                "remote_port": 666,
                "remote_host": "imahost",
                "response_timeout": 66.6,
            },
            {
                "entrypoint": ["/some/binary"],
                "_remote_port": 666,
                "_remote_host": "imahost",
                "_remote_response_timeout": 66.6,
            },
            None,
        ),
        (
            {
                "remote_port": 666,
            },
            {},
            TypeError(
                "__init__() missing 1 required positional argument: 'entrypoint'"
            ),
        ),
        (
            {"entrypoint": ["/some/binary"], "unknown_kwarg": "im-invalid"},
            {},
            TypeError("__init__() got an unexpected keyword argument 'unknown_kwarg'"),
        ),
    ],
)
def test_proxy_dapp_service(test_utils, service_kwargs, expected_attrs, expected_exc):
    """Test if HttpProxyDappService has its inherited fields initialized correctly."""
    try:
        proxy_service = HttpProxyDappService(**service_kwargs)

        for name, value in expected_attrs.items():
            assert getattr(proxy_service, name) == value
    except Exception as e:
        test_utils.verify_error(expected_exc, e)
