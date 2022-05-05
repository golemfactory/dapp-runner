"""Tests for the Dapp descriptor."""
import pytest

from dapp_runner.descriptor import DappDescriptor, DescriptorError
from dapp_runner.descriptor.dapp import (
    PayloadDescriptor,
    ServiceDescriptor,
    HttpProxyDescriptor,
)


@pytest.mark.parametrize(
    "descriptor_dict, error",
    [
        (
            {
                "payloads": {
                    "simple-service": {
                        "runtime": "vm",
                        "params": {"image_hash": "some-hash"},
                    }
                },
                "nodes": {
                    "simple-service": {
                        "payload": "simple-service",
                        "entrypoint": [
                            ["/golem/run/simulate_observations_ctl.py", "--start"],
                        ],
                    }
                },
            },
            None,
        ),
        (
            {
                "nodes": {
                    "simple-service": {
                        "payload": "simple-service",
                        "entrypoint": [
                            ["/golem/run/simulate_observations_ctl.py", "--start"],
                        ],
                    }
                },
            },
            TypeError("__init__() missing "),
        ),
        (
            {
                "unsupported": {},
            },
            DescriptorError("Unexpected keys: `{'unsupported'}"),
        ),
    ],
)
def test_dapp_descriptor(descriptor_dict, error, test_utils):
    """Test whether the Dapp descriptor loads correctly."""
    try:
        dapp = DappDescriptor.load(descriptor_dict)
        payload = dapp.payloads[list(dapp.payloads.keys())[0]]
        service = dapp.nodes[list(dapp.nodes.keys())[0]]
        assert isinstance(payload, PayloadDescriptor)
        assert isinstance(service, ServiceDescriptor)
    except Exception as e:  # noqa
        test_utils.verify_error(error, e)
    else:
        test_utils.verify_error(error, None)


@pytest.mark.parametrize(
    "descriptor_dict, remote_port, local_port, error",
    [
        (
            {
                "payloads": {},
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "entrypoint": [],
                        "http_proxy": {
                            "ports": [
                                "2525:25",
                            ]
                        },
                    }
                },
            },
            25,
            2525,
            None,
        ),
        (
            {
                "payloads": {},
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "entrypoint": [],
                        "http_proxy": {
                            "ports": [
                                "80",
                            ]
                        },
                    }
                },
            },
            80,
            None,
            None,
        ),
    ],
)
def test_http_proxy_descriptor(
    descriptor_dict, remote_port, local_port, error, test_utils
):
    """Test whether the `http_proxy` descriptor is correctly interpreted."""
    try:
        dapp = DappDescriptor.load(descriptor_dict)
        service = dapp.nodes[list(dapp.nodes.keys())[0]]
        assert isinstance(service.http_proxy, HttpProxyDescriptor)
        ports = service.http_proxy.ports[0]
        assert ports.local_port == local_port
        assert ports.remote_port == remote_port
    except Exception as e:  # noqa
        test_utils.verify_error(error, e)
    else:
        test_utils.verify_error(error, None)
