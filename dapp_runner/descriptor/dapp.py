"""Class definitions for the Dapp Runner's dapp descriptor."""
import abc
import asyncio
from dataclasses import dataclass, field

from typing import Dict, TypeVar, Generic, Type, Optional
from yapapi.payload import Payload, vm

from .base import BaseDescriptor, DescriptorError
from .service import DappService

YapapiClass = TypeVar("YapapiClass")


class YapapiFactory(Generic[YapapiClass], abc.ABC):
    """Base factory for a given type of yapapi object or class."""

    @classmethod
    @abc.abstractmethod
    async def resolve(cls, **kwargs) -> YapapiClass:
        """Resolve the object based on the provided arguments."""
        raise NotImplementedError()


class PayloadFactory(YapapiFactory[Payload]):
    """Factory producing instances of yapapi Payload from their descriptor."""

    @classmethod
    async def resolve(cls, runtime: str, params: Optional[dict] = None) -> Payload:  # type: ignore  # noqa
        """Create an instance of yapapi Payload for a given runtime type."""
        params = params or {}
        if runtime == "vm":
            return await vm.repo(**params)

        raise DescriptorError(f"Unimplemented {cls.__name__} for {runtime}")


class ServiceFactory(YapapiFactory[Type[DappService]]):
    """Factory producing classes of yapapi Services from their descriptor."""

    _idlock = asyncio.Lock()
    _id = 1

    @classmethod
    async def resolve(  # type: ignore
        cls, payload: str, entrypoint: list, payloads: Dict[str, Payload]
    ) -> Type[DappService]:
        """Create a service class corresponding with its descriptor."""
        async with cls._idlock:
            cls_id = cls._id
            cls._id += 1

        async def get_payload():
            return payloads[payload]

        DappServiceClass = type(
            f"DappService{cls_id}",
            (DappService,),
            {
                "get_payload": staticmethod(get_payload),
                "entrypoint": entrypoint,
            },
        )

        return DappServiceClass


@dataclass
class Dapp(BaseDescriptor):
    """Root dapp descriptor for the Dapp Runner."""

    payloads: Dict[str, Payload] = field(metadata={"factory": PayloadFactory})
    nodes: Dict[str, Type[DappService]] = field(
        metadata={"factory": ServiceFactory, "requires": ["payloads"]}
    )
