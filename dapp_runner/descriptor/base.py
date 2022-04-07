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
        resolved_kwargs = {}
        for f in fields(cls):
            descriptor_value = descriptor_dict.get(f.name)
            if not descriptor_value:
                break

            if type(f.type) is type:
                factory = f.metadata.get("factory", None)
                resolved_kwargs[f.name] = f.type(**descriptor_value) or await factory.resolve(**descriptor_value)
            elif getattr(f.type, "__origin__", None) == dict:
                resolved_kwargs[f.name] = await cls._resolve_dict(f, descriptor_value)
            else:
                raise NotImplementedError(f"Unimplemented handler for type {f.type.__origin__}")

        unexpected_keys = set(descriptor_dict.keys()) - set(f.name for f in fields(cls))
        if unexpected_keys:
            pass
            #raise DescriptorError(f"Unexpected keys: `{unexpected_keys}` for {cls}")
        return cls(**resolved_kwargs)  # type: ignore
