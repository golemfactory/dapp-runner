"""Dapp runner descriptor base classes."""
from dataclasses import dataclass, fields, Field

from typing import Generic, Type, TypeVar, Dict, Any


class DescriptorError(Exception):
    """Error while loading a Dapp Runner descriptor."""

    pass


DescriptorType = TypeVar("DescriptorType", bound="BaseDescriptor")


@dataclass
class BaseDescriptor(Generic[DescriptorType]):
    """Base dapp runner descriptor class.

    Descriptor classes serve as factories of the entities defined in the specific
    part of the descriptor tree.
    """

    class _Factory:
        """Helper class handling the factory definitions in the descriptor fields."""

        def __init__(self, f: Field, resolved_kwargs: Dict[str, Any]):
            self.f = f
            self.resolved_kwargs = resolved_kwargs

        def __bool__(self):
            return "factory" in self.f.metadata

        async def resolve(self, value):
            required = {
                k: v
                for k, v in self.resolved_kwargs.items()
                if k in self.f.metadata.get("requires", [])
            }
            return await self.f.metadata["factory"].resolve(**value, **required)

    @classmethod
    async def new(
        cls: Type[DescriptorType], descriptor_dict: Dict[str, Any]
    ) -> DescriptorType:
        """Create a new object from its descriptor."""
        resolved_kwargs: Dict[str, Any] = {}
        for f in fields(cls):
            descriptor_value = descriptor_dict.get(f.name)
            if not descriptor_value:
                break
            factory = cls._Factory(f, resolved_kwargs)
            if type(f.type) is type:
                if factory:
                    resolved_kwargs[f.name] = await factory.resolve(descriptor_value)
                else:
                    resolved_kwargs[f.name] = f.type(**descriptor_value)
            elif getattr(f.type, "__origin__", None) == dict:
                if not factory:
                    resolved_kwargs[f.name] = descriptor_value
                else:
                    resolved_kwargs[f.name] = {}
                    for k, v in descriptor_value.items():
                        resolved_kwargs[f.name][k] = await factory.resolve(v)
            else:
                raise NotImplementedError(
                    f"Unimplemented handler for type {f.type.__origin__}"
                )

        unexpected_keys = set(descriptor_dict.keys()) - set(f.name for f in fields(cls))
        if unexpected_keys:
            raise DescriptorError(
                f"Unexpected keys: `{unexpected_keys}` for `{cls.__name__}`"
            )
        return cls(**resolved_kwargs)  # type: ignore
