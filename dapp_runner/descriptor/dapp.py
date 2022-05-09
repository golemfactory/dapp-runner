"""Class definitions for the Dapp Runner's dapp descriptor."""
from dataclasses import dataclass, field

from typing import Dict, Union, List, Any, Optional, Final

from .base import BaseDescriptor, DescriptorError

from yapapi.payload import vm

NETWORK_DEFAULT_NAME: Final[str] = "default"
PAYLOAD_RUNTIME_VM: Final[str] = "vm"
VM_PAYLOAD_CAPS_KWARG: Final[str] = "capabilities"


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
class HttpProxyDescriptor(BaseDescriptor["HttpProxyDescriptor"]):
    """HTTP Proxy descriptor."""

    def __ports_factory(value: str) -> PortMapping:  # type: ignore [misc]  # noqa
        ports = [int(p) for p in value.split(":")]
        port_mappping = PortMapping(remote_port=ports.pop())
        if ports:
            port_mappping.local_port = ports.pop()
        return port_mappping

    ports: List[PortMapping] = field(metadata={"factory": __ports_factory})


@dataclass
class ServiceDescriptor(BaseDescriptor["ServiceDescriptor"]):
    """Yapapi Service descriptor."""

    def __entrypoint_factory(  # type: ignore [misc]  # noqa
        value: Union[List[List[str]], List[str]]  # noqa
    ) -> List[List[str]]:
        if isinstance(value[0], str):
            return [value]  # type: ignore [list-item] # noqa
        return value  # type: ignore [return-value] # noqa

    payload: str
    entrypoint: List[List[str]] = field(metadata={"factory": __entrypoint_factory})
    network: Optional[str] = None
    http_proxy: Optional[HttpProxyDescriptor] = None


@dataclass
class NetworkDescriptor(BaseDescriptor["NetworkDescriptor"]):
    """Yapapi network descriptor."""

    ip: str = field(default="192.168.0.0/24")
    owner_ip: Optional[str] = None
    mask: Optional[str] = None
    gateway: Optional[str] = None


@dataclass
class DappDescriptor(BaseDescriptor["DappDescriptor"]):
    """Root dapp descriptor for the Dapp Runner."""

    payloads: Dict[str, PayloadDescriptor]
    nodes: Dict[str, ServiceDescriptor]
    networks: Dict[str, NetworkDescriptor] = field(default_factory=dict)

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

    def __implicit_http_proxy_init(self):
        """Implicitly add a default network to all http proxy nodes."""
        for node in self.nodes.values():
            if node.http_proxy and not node.network:
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

    def __post_init__(self):
        self.__validate_nodes()
        self.__implicit_http_proxy_init()
        self.__implicit_vpn()
