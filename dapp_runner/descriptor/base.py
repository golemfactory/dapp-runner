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

    @classmethod
    def _instantiate_value(cls, desc: str, f: Field, value_type, value):
        try:
            if type(value_type) is type and issubclass(value_type, BaseDescriptor):
                return value_type.load(value)
            elif f.metadata.get("factory"):
                return f.metadata["factory"](value)
            elif type(value) is dict:
                return value_type(**value)
            else:
                return value_type(value)
        except Exception as e:
            raise DescriptorError(
                f"{cls.__name__}`{desc}`: {e.__class__.__name__}: {str(e)}"
            )

    @classmethod
    def load(
        cls: Type[DescriptorType], descriptor_dict: Dict[str, Any]
    ) -> DescriptorType:
        """Create a new descriptor object from its dictionary representation."""
        resolved_kwargs: Dict[str, Any] = {}
        for f in fields(cls):
            descriptor_value = descriptor_dict.get(f.name)
            if not descriptor_value:
                continue

            # field is a simple type
            if type(f.type) is type:
                resolved_kwargs[f.name] = cls._instantiate_value(
                    f.name, f, f.type, descriptor_value
                )

            # field is an Optional simple type
            elif (
                str(f.type).startswith("typing.Optional")
                and type(f.type.__args__[0]) is type
            ):
                resolved_kwargs[f.name] = cls._instantiate_value(
                    f.name, f, f.type.__args__[0], descriptor_value
                )

            # field is a `Dict`
            elif getattr(f.type, "__origin__", None) == dict:
                try:
                    entry_type = getattr(f.type, "__args__", None)[1]  # type: ignore [index] # noqa
                except (TypeError, IndexError):
                    entry_type = None

                # is the dict's value type defined as a simple type?
                if type(entry_type) is type:
                    resolved_kwargs[f.name] = {}
                    for k, v in descriptor_value.items():
                        resolved_kwargs[f.name][k] = cls._instantiate_value(
                            f"{f.name}[{k}]", f, entry_type, v
                        )
                # otherwise, just load it as a generic dict
                else:
                    resolved_kwargs[f.name] = descriptor_value

            # field is a `List`
            elif getattr(f.type, "__origin__", None) == list:
                try:
                    entry_type = getattr(f.type, "__args__", None)[0]  # type: ignore [index] # noqa
                except (TypeError, IndexError):
                    entry_type = None

                # is the list's value type defined as a simple type?
                if type(entry_type) is type:
                    resolved_kwargs[f.name] = []
                    for i in range(len(descriptor_value)):
                        v = descriptor_value[i]
                        resolved_kwargs[f.name].append(
                            cls._instantiate_value(f"{f.name}[{i}]", f, entry_type, v)
                        )
                # otherwise, just load it as a generic list
                else:
                    resolved_kwargs[f.name] = descriptor_value

            else:
                raise NotImplementedError(
                    f"{cls.__name__}.{f.name}: Unimplemented handler for {f.type}"
                )

        unexpected_keys = set(descriptor_dict.keys()) - set(f.name for f in fields(cls))
        if unexpected_keys:
            raise DescriptorError(
                f"Unexpected keys: `{unexpected_keys}` for `{cls.__name__}`"
            )
        return cls(**resolved_kwargs)
