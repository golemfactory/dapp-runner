import abc
from dataclasses import dataclass, field, fields, Field

from typing import Dict, TypeVar, Generic, Type, Optional
from yapapi.payload import Payload, vm
from yapapi.services import Service

from .base import BaseDescriptor, DescriptorError

YapapiClass = TypeVar("YapapiClass")


class YapapiFactory(Generic[YapapiClass], abc.ABC):
    @classmethod
    @abc.abstractmethod
    async def resolve(cls, *kwargs) -> Type[YapapiClass]:
        """Resolve the object based on the provided arguments."""


class PayloadDescriptor(YapapiFactory[Payload]):
    @classmethod
    async def resolve(cls, runtime: str, params: Optional[dict] = None) -> Payload:
        if runtime == "vm":
            return await vm.repo(**params)

        raise DescriptorError(f"Unimplemented {cls.__name__} for {runtime}")


class ServiceFactory(YapapiFactory[Type[Service]]):
    @classmethod
    async def resolve(cls, ):
        pass


@dataclass
class Dapp(BaseDescriptor):
    payloads: Dict[str, Payload] = field(metadata={"factory": PayloadDescriptor}, default=None)

