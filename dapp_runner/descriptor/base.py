from dataclasses import dataclass, fields, Field

from typing import Type, TypeVar


class DescriptorError(Exception):
    pass


DescriptorType = TypeVar("DescriptorType", bound="BaseDescriptor")


@dataclass
class BaseDescriptor:
    @classmethod
    async def _resolve_dict(cls, f: Field, descriptor_value):
        factory = f.metadata.get("factory", None)
        if not factory:
            return descriptor_value

        d = {}
        for value_key, value_value in descriptor_value.items():
            d[value_key] = await factory.resolve(**value_value)
        return d

    @classmethod
    async def new(cls: Type[DescriptorType], descriptor_dict: dict) -> DescriptorType:
        kwargs = {}
        fields_dict = {f.name: f for f in fields(cls)}
        for descriptor_key, descriptor_value in descriptor_dict.items():
            f: Field = fields_dict.get(descriptor_key, None)
            if not f:
                break
                raise DescriptorError(f"Unexpected key: `{descriptor_key}` for {self.__class__}")
            if type(f.type) is type:
                factory = f.metadata.get("factory", None)
                kwargs[f.name] = f.type(**descriptor_value) or await factory.resolve(**descriptor_value)
            elif getattr(f.type, "__origin__", None) == dict:
                kwargs[f.name] = await cls._resolve_dict(f, descriptor_value)
            else:
                raise NotImplementedError(f"Unimplemented handler for type {f.type.__origin__}")
        return cls(**kwargs)  # type: ignore
