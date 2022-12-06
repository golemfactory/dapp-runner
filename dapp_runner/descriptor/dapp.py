"""Class definitions for the Dapp Runner's dapp descriptor."""
import logging
from dataclasses import dataclass, field, fields
import networkx
from typing import Dict, List, Any, Optional, Final, Tuple
import warnings

from .base import BaseDescriptor, DescriptorError

from yapapi.payload import vm

NETWORK_DEFAULT_NAME: Final[str] = "default"

PAYLOAD_RUNTIME_VM: Final[str] = "vm"
PAYLOAD_RUNTIME_VM_MANIFEST: Final[str] = "vm/manifest"

VM_PAYLOAD_CAPS_KWARG: Final[str] = "capabilities"

DEPENDENCY_ROOT: Final[str] = ""

EXEUNIT_CMD_RUN: Final[str] = "run"

VM_CAPS_VPN: Final[str] = "vpn"
VM_CAPS_MANIFEST: Final[str] = "manifest-support"

logger = logging.getLogger(__name__)


@dataclass
class PayloadDescriptor:
    """Yapapi Payload descriptor."""

    runtime: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortMapping:
    """Port mapping for a http proxy."""

    remote_port: int
    local_port: Optional[int] = None


@dataclass
class ProxyDescriptor(BaseDescriptor["ProxyDescriptor"]):
    """Proxy descriptor."""

    def __ports_factory(value: str) -> PortMapping:  # type: ignore [misc]  # noqa
        ports = [int(p) for p in value.split(":")]
        port_mappping = PortMapping(remote_port=ports.pop())
        if ports:
            port_mappping.local_port = ports.pop()
        return port_mappping

    ports: List[PortMapping] = field(metadata={"factory": __ports_factory})


@dataclass
class HttpProxyDescriptor(ProxyDescriptor):
    """HTTP proxy descriptor."""


@dataclass
class SocketProxyDescriptor(ProxyDescriptor):
    """TCP socket proxy descriptor."""


@dataclass
class CommandDescriptor:
    """Exeunit command descriptor."""

    cmd: str = EXEUNIT_CMD_RUN
    params: Dict[str, Any] = field(default_factory=dict)


class _CommandDescriptorList:
    """Preprocessor for the exescript commands."""

    def _process_command(self, c):
        if isinstance(c, list):
            # assuming it's a `run`
            self.commands.append(CommandDescriptor(params={"args": c}))
        elif isinstance(c, dict):
            for cmd, params in c.items():
                if cmd == EXEUNIT_CMD_RUN and isinstance(params, list):
                    # support shorthand `run` notation:
                    # - run:
                    #    - ["/golem/run/simulate_observations_ctl.py", "--start"]
                    params = {"args": params}
                self.commands.append(CommandDescriptor(cmd=cmd, params=params))
        else:
            raise DescriptorError(f"Cannot parse the command descriptor `{c}`.")

    def __init__(self):
        self.commands = list()

    @classmethod
    def load_commands(cls, value) -> List[CommandDescriptor]:
        """Load the contents of the commands list."""
        commands_list = cls()

        if len(value) > 0 and isinstance(value[0], str):
            # support single line definitions, e.g. `init: ["/docker-entrypoint.sh"]`
            value = [value]

        for c in value:
            commands_list._process_command(c)

        return commands_list.commands


@dataclass
class ServiceDescriptor(BaseDescriptor["ServiceDescriptor"]):
    """Yapapi Service descriptor."""

    payload: str
    init: List[CommandDescriptor] = field(
        metadata={"load": _CommandDescriptorList.load_commands}, default_factory=list
    )
    entrypoint: List[List[str]] = field(default_factory=list)
    network: Optional[str] = None
    ip: List[str] = field(default_factory=list)
    http_proxy: Optional[HttpProxyDescriptor] = None
    tcp_proxy: Optional[SocketProxyDescriptor] = None
    depends_on: List[str] = field(default_factory=list)

    def __validate_entrypoint(self):
        if self.entrypoint:
            warnings.warn(
                f"`{type(self).__name__}.entrypoint` is deprecated. "
                f"Please use `init` instead.",
                DeprecationWarning,
            )
            if self.init:
                raise DescriptorError(
                    "Cannot specify both `init` and `entrypoint`. "
                    "Please use `init` only."
                )
            if isinstance(self.entrypoint[0], str):
                self.entrypoint = [self.entrypoint]  # noqa
            for c in self.entrypoint:
                self.init.append(
                    CommandDescriptor(cmd=EXEUNIT_CMD_RUN, params={"args": c})
                )
        # ensure it's not used anymore
        self.entrypoint = []

    def __post_init__(self):
        self.__validate_entrypoint()


@dataclass
class NetworkDescriptor(BaseDescriptor["NetworkDescriptor"]):
    """Yapapi network descriptor."""

    ip: str = field(default="192.168.0.0/24")
    owner_ip: Optional[str] = None
    mask: Optional[str] = None
    gateway: Optional[str] = None


@dataclass
class MetaDescriptor:
    """Meta descriptor for the app.

    Silently ignores unknown fields.
    """

    name: str = ""
    description: str = ""
    author: str = ""
    version: str = ""

    def __init__(self, **kwargs):
        for f in fields(self):
            if f.name in kwargs:
                setattr(self, f.name, f.type(kwargs.pop(f.name)))
        if kwargs:
            logger.debug("Unrecognized `meta` fields: %s", kwargs)


@dataclass
class DappDescriptor(BaseDescriptor["DappDescriptor"]):
    """Root dapp descriptor for the Dapp Runner."""

    payloads: Dict[str, PayloadDescriptor]
    nodes: Dict[str, ServiceDescriptor]
    networks: Dict[str, NetworkDescriptor] = field(default_factory=dict)
    meta: MetaDescriptor = field(default_factory=MetaDescriptor)

    _dependency_graph: networkx.DiGraph = field(init=False)

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
                self.payloads[node.payload].params[VM_PAYLOAD_CAPS_KWARG] = [
                    vm.VM_CAPS_VPN
                ]

    def __implicit_manifest_support(self):
        """Add `manifest-support` capability to `vm/manifest` payloads ."""
        for payload in self.payloads.values():
            if (
                payload.runtime == PAYLOAD_RUNTIME_VM_MANIFEST
                and VM_PAYLOAD_CAPS_KWARG not in payload.params
            ):
                payload.params[VM_PAYLOAD_CAPS_KWARG] = [VM_CAPS_MANIFEST]

    def _resolve_dependencies(self):
        """Resolve instantiation priorities."""

        # initialize the dependency graph and add a root node
        self._dependency_graph: networkx.DiGraph = networkx.DiGraph()
        self._dependency_graph.add_node(DEPENDENCY_ROOT)

        # for now, we only care about the order of services,
        # later we can enhance the dependency graph to
        # take all the other entities into consideration

        for name, service in self.nodes.items():
            if service.depends_on:
                for depends_name in service.depends_on:
                    if depends_name not in self.nodes:
                        raise DescriptorError(
                            f'Unmet `depends_on`: "{depends_name}"'
                            f' in service: "{name}".'
                        )
                    self._dependency_graph.add_edge(name, depends_name)
            else:
                self._dependency_graph.add_edge(DEPENDENCY_ROOT, name)

        if not networkx.is_directed_acyclic_graph(self._dependency_graph):
            raise DescriptorError(
                "Service definition contains a circular `depends_on`."
            )

    def nodes_prioritized(self) -> List[Tuple[str, ServiceDescriptor]]:
        """Get a dict-items-like list of services, ordered by dependencies."""
        return [
            (name, self.nodes[name])
            for name in reversed(
                list(networkx.topological_sort(self._dependency_graph))
            )
            if name != DEPENDENCY_ROOT
        ]

    def __post_init__(self):
        self.__validate_nodes()
        self.__implicit_proxy_init()
        self.__implicit_vpn()
        self.__implicit_manifest_support()
        self._resolve_dependencies()
