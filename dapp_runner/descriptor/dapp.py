"""Class definitions for the Dapp Runner's dapp descriptor."""
from dataclasses import dataclass, field

from typing import Dict, Union, List, Any

from .base import BaseDescriptor


@dataclass
class PayloadDescriptor:
    """Yapapi Payload descriptor."""

    runtime: str
    params: Dict[str, Any] = field(default_factory=dict)


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


@dataclass
class DappDescriptor(BaseDescriptor["DappDescriptor"]):
    """Root dapp descriptor for the Dapp Runner."""

    payloads: Dict[str, PayloadDescriptor]
    nodes: Dict[str, ServiceDescriptor]
