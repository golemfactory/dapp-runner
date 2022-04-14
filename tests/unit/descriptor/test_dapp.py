"""Tests for the Dapp descriptor."""
import pytest

from yapapi.payload.vm import _VmPackage  # noqa

from dapp_runner.descriptor.dapp import Dapp, DappService, DescriptorError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "descriptor_dict, error",
    [
        (
            {
                "payloads": {
                    "simple-service": {
                        "runtime": "vm",
                        "params": {
                            "image_hash": "8b11df59f84358d47fc6776d0bb7290b0054c15ded2d6f54cf634488"  # noqa
                        },
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
                        "runtime": "other",
                    }
                },
            },
            DescriptorError("Unimplemented PayloadFactory for runtime: `other`"),
        ),
        (
            {
                "payloads": {
                    "simple-service": {
                        "runtime": "vm",
                        "params": {
                            "image_hash": "8b11df59f84358d47fc6776d0bb7290b0054c15ded2d6f54cf634488"  # noqa
                        },
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
async def test_dapp_descriptor(descriptor_dict, error):
    """Test whether the Dapp descriptor loads correctly."""
    try:
        dapp = await Dapp.new(descriptor_dict)
        payload = dapp.payloads[list(dapp.payloads.keys())[0]]
        service_cls = dapp.nodes[list(dapp.nodes.keys())[0]]
        assert isinstance(payload, _VmPackage)
        assert issubclass(service_cls, DappService)
        assert await service_cls.get_payload() == payload
    except Exception as e:  # noqa
        if not error:
            raise
        assert str(e).startswith(str(error))
        assert type(e) == type(error)
