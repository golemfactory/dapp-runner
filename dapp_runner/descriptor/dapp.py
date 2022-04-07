import abc
import asyncio
from dataclasses import dataclass, field, fields, Field

from typing import Dict, TypeVar, Generic, Type, Optional
from yapapi.payload import Payload, vm
from ..service import DappService

from .base import BaseDescriptor, DescriptorError

YapapiClass = TypeVar("YapapiClass")


class YapapiFactory(Generic[YapapiClass], abc.ABC):
    @classmethod
    @abc.abstractmethod
    async def resolve(cls, *kwargs) -> Type[YapapiClass]:
        """Resolve the object based on the provided arguments."""


class PayloadFactory(YapapiFactory[Payload]):
    @classmethod
    async def resolve(cls, runtime: str, params: Optional[dict] = None) -> Payload:
        if runtime == "vm":
            return await vm.repo(**params)

        raise DescriptorError(f"Unimplemented {cls.__name__} for {runtime}")


class ServiceFactory(YapapiFactory[Type[DappService]]):
    _idlock = asyncio.Lock()
    _id = 1

    @classmethod
    async def resolve(cls, payload: str, entrypoint: list, payloads: Dict[str, Payload]) -> Type[DappService]:
        async with cls._idlock:
            cls_id = cls._id
            cls._id += 1

        @staticmethod
        async def get_payload():
            return payloads[payload]

        DappServiceClass = type(
            f"DappService{cls_id}",
            (DappService, ),
            {
                "get_payload": get_payload,
                "entrypoint": entrypoint,
            }
        )

        return DappServiceClass


@dataclass
class Dapp(BaseDescriptor):
    payloads: Dict[str, Payload] = field(metadata={"factory": PayloadFactory}, default=None)
    nodes: Dict[str, Type[DappService]] = field(metadata={"factory": ServiceFactory, "requires": ["payloads"]}, default=None)
