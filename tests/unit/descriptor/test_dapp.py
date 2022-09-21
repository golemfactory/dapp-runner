"""Tests for the Dapp descriptor."""
import pytest

from dapp_runner.descriptor import DappDescriptor, DescriptorError
from dapp_runner.descriptor.dapp import (
    PayloadDescriptor,
    ServiceDescriptor,
    CommandDescriptor,
    HttpProxyDescriptor,
    VM_PAYLOAD_CAPS_KWARG,
    VM_CAPS_VPN,
    VM_CAPS_MANIFEST,
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
                "meta": {
                    "name": "sample-app",
                    "description": "a simple application",
                    "ignored value": "some other meta information",
                },
            },
            None,
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
                        "payload": "simple-service",
                        "entrypoint": [
                            "/golem/run/simulate_observations_ctl.py",
                            "--start",
                        ],
                    }
                },
            },
            None,
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
                        "payload": "simple-service",
                        "entrypoint": [
                            ["/golem/run/simulate_observations_ctl.py", "--start"],
                        ],
                        "network": "missing",
                    }
                },
            },
            DescriptorError("Undefined network: `missing`"),
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
        payload = list(dapp.payloads.values())[0]
        service = list(dapp.nodes.values())[0]
        assert isinstance(payload, PayloadDescriptor)
        assert isinstance(service, ServiceDescriptor)

        assert isinstance(service.init, list)

    except Exception as e:  # noqa
        test_utils.verify_error(error, e)
    else:
        test_utils.verify_error(error, None)


@pytest.mark.parametrize(
    "descriptor_dict, remote_port, local_port, error, implicit_vpn",
    [
        (
            {
                "payloads": {"foo": {"runtime": "bar"}},
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "init": [],
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
            False,
        ),
        (
            {
                "payloads": {"foo": {"runtime": "bar"}},
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "init": [],
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
            False,
        ),
        (
            {
                "payloads": {"foo": {"runtime": "vm"}},
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "init": [],
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
            True,
        ),
    ],
)
def test_http_proxy_descriptor(
    test_utils, descriptor_dict, remote_port, local_port, error, implicit_vpn
):
    """Test whether the `http_proxy` descriptor is correctly interpreted."""
    try:
        dapp = DappDescriptor.load(descriptor_dict)
        service = list(dapp.nodes.values())[0]
        assert isinstance(service.http_proxy, HttpProxyDescriptor)
        ports = service.http_proxy.ports[0]
        assert ports.local_port == local_port
        assert ports.remote_port == remote_port

        # check implicit network initialization
        assert service.network

        # check implicit VPN capability for a VM runtime
        if implicit_vpn:
            payload = list(dapp.payloads.values())[0]
            assert VM_PAYLOAD_CAPS_KWARG in payload.params
            assert VM_CAPS_VPN in payload.params[VM_PAYLOAD_CAPS_KWARG]

    except Exception as e:  # noqa
        test_utils.verify_error(error, e)
    else:
        test_utils.verify_error(error, None)


@pytest.mark.parametrize(
    "descriptor_dict, implicit_manifest",
    [
        (
            {
                "payloads": {"foo": {"runtime": "vm"}},
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "init": [],
                    }
                },
            },
            False,
        ),
        (
            {
                "payloads": {"foo": {"runtime": "vm/manifest"}},
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "init": [],
                    }
                },
            },
            True,
        ),
        (
            {
                "payloads": {
                    "foo": {
                        "runtime": "vm/manifest",
                        "params": {"capabilities": ["vpn"]},
                    }
                },
                "nodes": {
                    "http": {
                        "payload": "foo",
                        "init": [],
                    }
                },
            },
            False,
        ),
    ],
)
def test_manifest_payload(descriptor_dict, implicit_manifest):
    """Test whether `manifest_support` is implicitly added to the capabilities list."""
    dapp = DappDescriptor.load(descriptor_dict)
    payload = list(dapp.payloads.values())[0]
    if implicit_manifest:
        assert VM_PAYLOAD_CAPS_KWARG in payload.params
        assert VM_CAPS_MANIFEST in payload.params[VM_PAYLOAD_CAPS_KWARG]
    elif VM_PAYLOAD_CAPS_KWARG in payload.params:
        assert VM_CAPS_MANIFEST not in payload.params[VM_PAYLOAD_CAPS_KWARG]


@pytest.mark.parametrize(
    "descriptor_dict, expected_init, error",
    [
        # ensure the simplest version of init
        # (implicitly interpreted as `run` with `args` given as a list)
        # is correctly interpreted
        (
            {
                "payload": "foo",
                "init": ["test", "blah"],
            },
            [CommandDescriptor("run", {"args": ["test", "blah"]})],
            None,
        ),
        # ensure previous, simplified `entrypoint` syntax is correctly converted
        (
            {
                "payload": "foo",
                "entrypoint": ["test", "blah"],
            },
            [CommandDescriptor("run", params={"args": ["test", "blah"]})],
            None,
        ),
        # ensure previous, regular `entrypoint` syntax is correctly converted
        (
            {
                "payload": "foo",
                "entrypoint": [["test", "blah"], ["other command"]],
            },
            [
                CommandDescriptor("run", {"args": ["test", "blah"]}),
                CommandDescriptor("run", {"args": ["other command"]}),
            ],
            None,
        ),
        # ensure that one cannot provide both `init` and `entrypoint`
        (
            {
                "payload": "foo",
                "init": ["test"],
                "entrypoint": ["test"],
            },
            None,
            DescriptorError(
                "Cannot specify both `init` and `entrypoint`. "
                "Please use `init` only."
            ),
        ),
        # check the empty init default
        (
            {
                "payload": "foo",
            },
            [],
            None,
        ),
        # ensure the shorthand `run` syntax works correctly
        (
            {
                "payload": "foo",
                "init": [["test", "blah"], ["other command"]],
            },
            [
                CommandDescriptor("run", {"args": ["test", "blah"]}),
                CommandDescriptor("run", {"args": ["other command"]}),
            ],
            None,
        ),
        # ensure the shorthand `run` form 2 syntax works correctly
        (
            {
                "payload": "foo",
                "init": [{"run": ["test", "blah"]}],
            },
            [
                CommandDescriptor("run", {"args": ["test", "blah"]}),
            ],
            None,
        ),
        # two commands in one dict (accidental user's mistake)
        (
            {
                "payload": "foo",
                "init": [
                    {
                        "run": {"args": ["test", "command"]},
                        "test": {"param": ["another", "foo"]},
                    }
                ],
            },
            [
                CommandDescriptor("run", {"args": ["test", "command"]}),
                CommandDescriptor("test", {"param": ["another", "foo"]}),
            ],
            None,
        ),
        # check the regular syntax
        (
            {
                "payload": "foo",
                "init": [
                    {"deploy": {"kwargs": {"foo": "bar"}}},
                    {"run": {"args": ["test", "command"]}},
                ],
            },
            [
                CommandDescriptor("deploy", {"kwargs": {"foo": "bar"}}),
                CommandDescriptor("run", {"args": ["test", "command"]}),
            ],
            None,
        ),
    ],
)
def test_service_init(test_utils, descriptor_dict, expected_init, error):
    """Test the ServiceDescriptor's init/entrypoint field."""
    try:
        service = ServiceDescriptor.load(descriptor_dict)
        assert isinstance(service, ServiceDescriptor)
        assert service.init == expected_init
        # the `entrypoint` should always stay empty from now on
        assert service.entrypoint == []

    except Exception as e:  # noqa
        test_utils.verify_error(error, e)
    else:
        test_utils.verify_error(error, None)


@pytest.mark.parametrize(
    "descriptor_dict, error, expected_priority",
    (
        (
            {
                "payloads": {"foo": {"runtime": "vm"}},
                "nodes": {
                    "db1": {
                        "payload": "foo",
                        "entrypoint": [],
                    },
                    "http": {
                        "payload": "foo",
                        "entrypoint": [],
                        "depends_on": ["db1", "db2"],
                    },
                    "db2": {
                        "payload": "foo",
                        "entrypoint": [],
                    },
                },
            },
            None,
            ["db2", "db1", "http"],
        ),
        (
            {
                "payloads": {"foo": {"runtime": "vm"}},
                "nodes": {
                    "one": {
                        "payload": "foo",
                        "entrypoint": [],
                    },
                    "three": {
                        "payload": "foo",
                        "entrypoint": [],
                        "depends_on": ["two"],
                    },
                    "two": {
                        "payload": "foo",
                        "entrypoint": [],
                        "depends_on": ["one"],
                    },
                },
            },
            None,
            ["one", "two", "three"],
        ),
        (
            {
                "payloads": {"foo": {"runtime": "vm"}},
                "nodes": {
                    "http": {"payload": "foo", "entrypoint": [], "depends_on": ["bar"]}
                },
            },
            DescriptorError('Unmet `depends_on`: "bar" in service: "http"'),
            [],
        ),
        (
            {
                "payloads": {"foo": {"runtime": "vm"}},
                "nodes": {
                    "http": {"payload": "foo", "entrypoint": [], "depends_on": ["db"]},
                    "db": {"payload": "foo", "entrypoint": [], "depends_on": ["http"]},
                },
            },
            DescriptorError("Service definition contains a circular `depends_on`."),
            [],
        ),
    ),
)
def test_depends_on(test_utils, descriptor_dict, error, expected_priority):
    """Test the `depends_on` parameter."""
    try:
        dapp = DappDescriptor.load(descriptor_dict)
        nodes_priority = [name for name, service in dapp.nodes_prioritized()]
        assert nodes_priority == expected_priority
    except Exception as e:  # noqa
        test_utils.verify_error(error, e)
    else:
        test_utils.verify_error(error, None)
