"""Class definitions for the Dapp Runner's dapp descriptor."""
from dataclasses import dataclass, field

from typing import Dict, Union, List, Any, Optional

from .base import BaseDescriptor


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
    http_proxy: Optional[HttpProxyDescriptor] = None


@dataclass
class DappDescriptor(BaseDescriptor["DappDescriptor"]):
    """Root dapp descriptor for the Dapp Runner."""

    payloads: Dict[str, PayloadDescriptor]
    nodes: Dict[str, ServiceDescriptor]
