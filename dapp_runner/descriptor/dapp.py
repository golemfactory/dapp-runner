"""Class definitions for the Dapp Runner's dapp descriptor."""
import logging
import re
from typing import Any, Dict, Final, List, Optional, Tuple, Union

import networkx
from pydantic import Field, PrivateAttr, validator

from yapapi.ctx import Activity
from yapapi.network import Network
from yapapi.network import Node as NetworkNode
from yapapi.payload import vm

from .base import GaomBase
from .error import DescriptorError

NETWORK_DEFAULT_NAME: Final[str] = "default"

PAYLOAD_RUNTIME_VM: Final[str] = "vm"
PAYLOAD_RUNTIME_VM_MANIFEST: Final[str] = "vm/manifest"

VM_PAYLOAD_CAPS_KWARG: Final[str] = "capabilities"

DEPENDENCY_ROOT: Final[str] = ""

EXEUNIT_CMD_RUN: Final[str] = "run"

VM_CAPS_VPN: Final[str] = "vpn"
VM_CAPS_MANIFEST: Final[str] = "manifest-support"

logger = logging.getLogger(__name__)


class PayloadDescriptor(GaomBase):
    """Yapapi Payload descriptor."""

    runtime: str
    params: Dict[str, Any] = Field(default_factory=dict)

    class Config:  # noqa: D106
        extra = "forbid"


class PortMapping(GaomBase):
    """Port mapping for a http proxy."""

    remote_port: int
    local_port: Optional[int] = None
    address: Optional[str] = Field(runtime=True)

    class Config:  # noqa: D106
        extra = "forbid"


class ProxyDescriptor(GaomBase):
    """Proxy descriptor."""

    ports: List[PortMapping]

    class Config:  # noqa: D106
        extra = "forbid"

    @validator("ports", pre=True, each_item=True)
    def __ports__preprocess(cls, v):
        if isinstance(v, PortMapping) or isinstance(v, dict):
            return v

        try:
            return re.match(
                r"^(?:(?P<local_port>\d+)\:)?(?P<remote_port>\d+)$", v
            ).groupdict()  # type: ignore [union-attr]
        except AttributeError:
            raise ValueError("Expected format: `remote_port` or `local_port:remote_port`.")


class HttpProxyDescriptor(ProxyDescriptor):
    """HTTP proxy descriptor."""


class SocketProxyDescriptor(ProxyDescriptor):
    """TCP socket proxy descriptor."""


class CommandDescriptor(GaomBase):
    """Exeunit command descriptor."""

    cmd: str = EXEUNIT_CMD_RUN
    params: Dict[str, Any] = Field(default_factory=dict)

    class Config:  # noqa: D106
        extra = "forbid"

    @classmethod
    def canonize_input(cls, value: Union[str, List, Dict]):
        """Convert a single command descriptor to its canonical form.

        Supported formats:

        ```yaml
        init:
          - test:
              args: ["/bin/rm", "/var/log/nginx/access.log", "/var/log/nginx/error.log"]
              from: "aa"
              to: "b"
          - aaa:
              args: ["/bin/rm", "/var/log/nginx/access.log", "/var/log/nginx/error.log"]
              from: "aa"
              to: "b"
        ```

        ```yaml
        init: ["/docker-entrypoint.sh"]
        ```

        ```yaml
        init:
          - run:
              args:
                - "/docker-entrypoint.sh"
        ```

        ```yaml
        init:
            - ["/docker-entrypoint.sh"]
            - ["/bin/chmod", "a+x", "/"]
            - ["/bin/sh", "-c", 'echo "Hello from inside Golem!" > /usr/share/nginx/html/index.html']  # noqa
        ```

        """
        if isinstance(value, list):
            # assuming it's a `run`
            return {"cmd": EXEUNIT_CMD_RUN, "params": {"args": value}}
        elif isinstance(value, dict) and len(value.keys()) == 1:
            # we don't want to support malformed entries
            # where multiple commands are present in a single dictionary
            for cmd, params in value.items():
                if cmd == EXEUNIT_CMD_RUN and isinstance(params, list):
                    # support shorthand `run` notation:
                    # - run:
                    #    - ["/golem/run/simulate_observations_ctl.py", "--start"]
                    params = {"args": params}
                return {"cmd": cmd, "params": params}
        elif isinstance(value, dict) and set(value.keys()) == {"cmd", "params"}:
            return value
        else:
            raise DescriptorError(f"Cannot parse the command descriptor `{value}`.")


class NetworkNodeDescriptor(GaomBase):
    """GAOM model reflecting yapapi's network `Node`."""

    node_id: str
    ip: str

    class Config:  # noqa: D106
        extra = "forbid"

    @classmethod
    def from_network_node(cls, network_node: NetworkNode):
        """Get a NetworkNodeDescriptor based on a `NetworkNode` object."""
        return cls(
            node_id=network_node.node_id,
            ip=network_node.ip,
        )


class ActivityDescriptor(GaomBase):
    """GAOM model referring to yagna's Activity."""

    id: str

    class Config:  # noqa: D106
        extra = "forbid"

    @classmethod
    def from_activity(cls, activity: Activity):
        """Get an ActivityDescriptor based on an `Activity` object."""
        return cls(id=activity.id)


class AgreementDescriptor(GaomBase):
    """GAOM model referring to yagna's Agreement."""

    id: str
    provider_id: str
    provider_name: str

    class Config:  # noqa: D106
        extra = "forbid"


class ServiceDescriptor(GaomBase):
    """Yapapi Service descriptor."""

    payload: str
    init: List[CommandDescriptor] = Field(default_factory=list)
    network: Optional[str] = None
    ip: List[str] = Field(default_factory=list)
    http_proxy: Optional[HttpProxyDescriptor] = None
    tcp_proxy: Optional[SocketProxyDescriptor] = None
    depends_on: List[str] = Field(default_factory=list)

    state: Optional[str] = Field(runtime=True, default=None)
    network_node: Optional[NetworkNodeDescriptor] = Field(runtime=True, default=None)
    agreement: Optional[AgreementDescriptor] = Field(runtime=True, default=None)
    activity: Optional[ActivityDescriptor] = Field(runtime=True, default=None)

    class Config:  # noqa: D106
        extra = "forbid"

    @validator("init", pre=True)
    def __init__canonize_commands(cls, v):
        if len(v) and isinstance(v[0], str):
            # support single line definitions, e.g. `init: ["/docker-entrypoint.sh"]`
            v = [v]

        return [CommandDescriptor.canonize_input(v) for v in v]


class NetworkDescriptor(GaomBase):
    """Yapapi network descriptor."""

    ip: str = "192.168.0.0/24"
    owner_ip: Optional[str] = None
    mask: Optional[str] = None
    gateway: Optional[str] = None
    network_id: Optional[str] = Field(runtime=True)
    owner_id: Optional[str] = Field(runtime=True)
    state: Optional[str] = Field(runtime=True, default=None)

    class Config:  # noqa: D106
        extra = "forbid"

    @classmethod
    def from_network(cls, network: Network):
        """Get a NetworkDescriptor based on yapapi's `Network` object."""
        network_serialized = network.serialize()

        return cls(
            ip=network.network_address,
            owner_ip=network.owner_ip,
            mask=network.netmask,
            gateway=network.gateway,
            network_id=network_serialized["_network_id"],
            owner_id=network_serialized["owner_id"],
            state=network_serialized["state"],
        )


class MetaDescriptor(GaomBase):
    """Meta descriptor for the app.

    Silently ignores unknown fields.
    """

    name: str = ""
    description: str = ""
    author: str = ""
    version: str = ""


class DappDescriptor(GaomBase):
    """Root dapp descriptor for the Dapp Runner."""

    payloads: Dict[str, PayloadDescriptor]
    nodes: Dict[str, ServiceDescriptor]
    networks: Dict[str, NetworkDescriptor] = Field(default_factory=dict)
    meta: MetaDescriptor = Field(default_factory=MetaDescriptor)

    _dependency_graph: networkx.DiGraph = PrivateAttr()

    class Config:  # noqa: D106
        extra = "forbid"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__validate_nodes()
        self.__implicit_proxy_init()
        self.__implicit_vpn()
        self.__implicit_manifest_support()
        self._resolve_dependencies()

    def __validate_nodes(self):
        """Ensure that required payloads and optional networks are defined."""
        for node in self.nodes.values():
            if node.payload not in self.payloads:
                raise DescriptorError(f"Undefined payload: `{node.payload}`")
            if node.network and node.network not in self.networks:
                raise DescriptorError(f"Undefined network: `{node.network}`")

    def __default_network(self) -> str:
        """Get the name of the default network for the dapp."""
        if not self.networks:
            self.networks[NETWORK_DEFAULT_NAME] = NetworkDescriptor()
        return list(self.networks.keys())[0]

    def __implicit_proxy_init(self):
        """Implicitly add a default network to all http/tcp proxy nodes."""
        for node in self.nodes.values():
            if node.http_proxy or node.tcp_proxy and not node.network:
                node.network = self.__default_network()

    def __implicit_vpn(self):
        """Add a VPN capability requirements to any network-connected VM payloads."""
        for node in self.nodes.values():
            if (
                node.network
                and self.payloads[node.payload].runtime == PAYLOAD_RUNTIME_VM
                and VM_PAYLOAD_CAPS_KWARG not in self.payloads[node.payload].params
            ):
                self.payloads[node.payload].params[VM_PAYLOAD_CAPS_KWARG] = [vm.VM_CAPS_VPN]

    def __implicit_manifest_support(self):
        """Add `manifest-support` capability to `vm/manifest` payloads ."""
        for payload in self.payloads.values():
            if (
                payload.runtime == PAYLOAD_RUNTIME_VM_MANIFEST
                and VM_PAYLOAD_CAPS_KWARG not in payload.params
            ):
                payload.params[VM_PAYLOAD_CAPS_KWARG] = [VM_CAPS_MANIFEST]

    def _resolve_depends_on(self):
        """Resolve dependencies from the `depends_on` clause."""

        for name, service in self.nodes.items():
            if service.depends_on:
                for depends_name in service.depends_on:
                    if depends_name not in self.nodes:
                        raise DescriptorError(
                            f'Unmet `depends_on`: "{depends_name}"' f' in service: "{name}".'
                        )
                    self._dependency_graph.add_edge(name, depends_name)
            else:
                self._dependency_graph.add_edge(DEPENDENCY_ROOT, name)

    def _resolve_dependencies(self):
        """Resolve instantiation priorities."""

        # initialize the dependency graph and add a root node
        self._dependency_graph: networkx.DiGraph = networkx.DiGraph()
        self._dependency_graph.add_node(DEPENDENCY_ROOT)

        # for now, we only care about the order of services,
        # later we can enhance the dependency graph to
        # take all the other entities into consideration
        self._resolve_depends_on()

        if not networkx.is_directed_acyclic_graph(self._dependency_graph):
            raise DescriptorError("Service definition contains a circular `depends_on`.")

    def nodes_prioritized(self) -> List[Tuple[str, ServiceDescriptor]]:
        """Get a dict-items-like list of services, ordered by dependencies."""
        return [
            (name, self.nodes[name])
            for name in reversed(list(networkx.topological_sort(self._dependency_graph)))
            if name != DEPENDENCY_ROOT
        ]
