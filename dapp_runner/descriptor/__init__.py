import abc
from dataclasses import dataclass, field, fields, Field

from typing import Dict, TypeVar, Generic, Type, Optional
from yapapi.payload import Payload, vm

YapapiClass = TypeVar("YapapiClass")


class YapapiDescriptor(Generic[YapapiClass], abc.ABC):
    @classmethod
    @abc.abstractmethod
    async def resolve(cls, *kwargs) -> Type[YapapiClass]:
        """Resolve the object based on the provided arguments."""


class PayloadDescriptor(YapapiDescriptor[Payload]):
    @classmethod
    async def resolve(cls, runtime: str, params: Optional[dict] = None) -> Payload:
        if runtime == "vm":
            return await vm.repo(**params)

        raise DescriptorError(f"Unimplemented {cls.__name__} for {runtime}")


@dataclass
class Descriptor:
    payloads: Dict[str, Payload] = field(metadata={"factory": PayloadDescriptor})

    def __init__(self, descriptor_dict: dict):
        self._descriptor_dict = descriptor_dict

    async def resolve(self):
        fields_dict = {f.name: f for f in fields(self)}
        for descriptor_key, descriptor_value in self._descriptor_dict.items():
            f: Field = fields_dict.get(descriptor_key, None)
            if not f:
                break
                # raise DescriptorError(f"Unexpected key: `{descriptor_key}`")
            if f.type.__origin__ == dict:
                value = {}
                for value_key, value_value in descriptor_value.items():
                    value[value_key] = await f.metadata.get("factory").resolve(**value_value)
                setattr(self, descriptor_key, value)


class DescriptorError(Exception):
    pass