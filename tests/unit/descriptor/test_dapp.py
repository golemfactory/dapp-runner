"""Tests for the Dapp descriptor."""
import pytest

from dapp_runner.descriptor import DappDescriptor, DescriptorError
from dapp_runner.descriptor.dapp import PayloadDescriptor, ServiceDescriptor


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
                "payloads": {
                    "simple-service": {
                        "runtime": "vm",
                        "params": {"image_hash": "some-hash"},
                    }
                },
                "nodes": {
                    "simple-service": {
                        "payload": "other",
                        "entrypoint": [
                            ["/golem/run/simulate_observations_ctl.py", "--start"],
                        ],
                    }
                },
            },
            DescriptorError("Undefined payload: `other`"),
        ),
        (
            {
                "unsupported": {},
            },
            DescriptorError("Unexpected keys: `{'unsupported'}"),
        ),
    ],
)
def test_dapp_descriptor(descriptor_dict, error):
    """Test whether the Dapp descriptor loads correctly."""
    try:
        dapp = DappDescriptor.load(descriptor_dict)
        payload = dapp.payloads[list(dapp.payloads.keys())[0]]
        service_cls = dapp.nodes[list(dapp.nodes.keys())[0]]
        assert isinstance(payload, PayloadDescriptor)
        assert isinstance(service_cls, ServiceDescriptor)
    except Exception as e:  # noqa
        if not error:
            raise
        assert str(error) in str(e)
        assert type(e) == type(error)
