"""Unit tests for dapp_runner.descriptor.service."""
import asyncio

import pytest
from typing import Final
from unittest.mock import Mock

from yapapi.ctx import WorkContext, Script
from yapapi.payload import Payload
from yapapi.network import Network
from yapapi.script import Run

from dapp_runner.descriptor.dapp import (
    ServiceDescriptor,
    HttpProxyDescriptor,
    PortMapping,
    CommandDescriptor,
)
from dapp_runner.runner import RunnerError
from dapp_runner.runner.service import DappService, HttpProxyDappService, get_service


@pytest.fixture
def mock_work_context():  # noqa
    return WorkContext(Mock(), Mock(), Mock(), Mock())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "init, expected_script",
    [
        (
            [
                CommandDescriptor(params={"args": ["/bin/test", "blah"]}),
            ],
            [Run("/bin/test", "blah")],
        ),
        (
            [
                CommandDescriptor(params={"args": ["/bin/test", "blah"]}),
                CommandDescriptor(params={"args": ["/bin/blah"]}),
            ],
            [Run("/bin/test", "blah"), Run("/bin/blah")],
        ),
    ],
)
async def test_service_init(mock_work_context, init, expected_script):
    """Test if the DappService's entrypoint works as expected."""
    service = DappService(init)
    service._ctx = mock_work_context
    scripts = []
    gen = service.start()

    s = await gen.__anext__()
    while s:
        scripts.append(s)
        future_results = asyncio.get_event_loop().create_future()
        future_results.set_result("some output...")
        try:
            s = await gen.asend(future_results)
        except StopAsyncIteration:
            s = None

    assert len(scripts) == 2

    init_script: Script = scripts[1]
    assert len(init_script._commands) == len(expected_script)

    for i in range(len(expected_script)):
        assert init_script._commands[i].evaluate() == expected_script[i].evaluate()


@pytest.mark.parametrize(
    "service_kwargs, expected_attrs, expected_exc",
    [
        (
            {"init": [CommandDescriptor(params={"args": ["/some/binary"]})]},
            {
                "init": [CommandDescriptor(params={"args": ["/some/binary"]})],
                "_remote_port": 80,
                "_remote_host": None,
                "_remote_response_timeout": 30.0,
            },
            None,
        ),
        (
            {
                "init": [],
                "remote_port": 666,
                "remote_host": "imahost",
                "response_timeout": 66.6,
            },
            {
                "init": [],
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
            TypeError("__init__() missing 1 required positional argument: 'init'"),
        ),
        (
            {"init": [], "unknown_kwarg": "im-invalid"},
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


SOME_PAYLOAD: Final = Payload()
SOME_NETWORK: Final = Network(Mock(), "192.168.0.1/24", "192.168.0.1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "descriptor, payloads, networks, base_class, expected_kwargs, error",
    (
        # non-networked service
        (
            ServiceDescriptor(init=[], payload="foo"),
            {"foo": SOME_PAYLOAD},
            {},
            DappService,
            {"payload": SOME_PAYLOAD, "instance_params": [{"init": []}]},
            None,
        ),
        # networked service
        (
            ServiceDescriptor(init=[], payload="foo", network="bar"),
            {"foo": SOME_PAYLOAD},
            {"bar": SOME_NETWORK},
            DappService,
            {
                "instance_params": [{"init": []}],
                "payload": SOME_PAYLOAD,
                "network": SOME_NETWORK,
            },
            None,
        ),
        # missing payload definition
        (
            ServiceDescriptor(init=[], payload="foo"),
            {},
            {},
            None,
            {},
            RunnerError('Undefined payload: "foo"'),
        ),
        # missing network definition
        (
            ServiceDescriptor(init=[], payload="foo", network="bar"),
            {"foo": SOME_PAYLOAD},
            {},
            None,
            {},
            RunnerError('Undefined network: "bar"'),
        ),
        # network service with an http proxy
        (
            ServiceDescriptor(
                init=[],
                payload="foo",
                network="bar",
                http_proxy=HttpProxyDescriptor(ports=[PortMapping(80)]),
            ),
            {"foo": SOME_PAYLOAD},
            {"bar": SOME_NETWORK},
            HttpProxyDappService,
            {
                "instance_params": [{"init": [], "remote_port": 80}],
                "payload": SOME_PAYLOAD,
                "network": SOME_NETWORK,
            },
            None,
        ),
        # explicit IP address
        (
            ServiceDescriptor(
                init=[],
                payload="foo",
                network="bar",
                ip=["192.168.0.2"],
            ),
            {"foo": SOME_PAYLOAD},
            {"bar": SOME_NETWORK},
            DappService,
            {
                "instance_params": [{"init": []}],
                "payload": SOME_PAYLOAD,
                "network": SOME_NETWORK,
                "network_addresses": ["192.168.0.2"],
            },
            None,
        ),
    ),
)
async def test_get_service(
    test_utils, descriptor, payloads, networks, base_class, expected_kwargs, error
):
    """Verify the generated service defintion."""
    try:
        service_class, run_service_kwargs = await get_service(
            "", descriptor, payloads, networks
        )
        assert issubclass(service_class, base_class)
        assert run_service_kwargs == expected_kwargs
    except Exception as e:  # noqa
        test_utils.verify_error(error, e)
    else:
        test_utils.verify_error(error, None)
