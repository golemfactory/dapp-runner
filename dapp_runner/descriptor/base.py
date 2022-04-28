"""Dapp runner descriptor base classes."""
from dataclasses import dataclass, fields, Field

from typing import Generic, Type, TypeVar, Dict, List, Any, Union


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
                f"{cls.__name__}.{desc}: {e.__class__.__name__}: {str(e)}"
            )

    @classmethod
    def _load_dict(cls, f: Field, descriptor_value: Dict[str, Any]) -> Dict[str, Any]:
        try:
            entry_type = getattr(f.type, "__args__", None)[
                1
            ]  # type: ignore [index] # noqa
        except (TypeError, IndexError):
            entry_type = None

        # is the dict's value type defined as a simple type?
        if type(entry_type) is type:
            out = {}
            for k, v in descriptor_value.items():
                out[k] = cls._instantiate_value(f"{f.name}[{k}]", f, entry_type, v)
            return out
        return descriptor_value

    @classmethod
    def _load_list(cls, f: Field, descriptor_value: List[Any]) -> List[Any]:
        try:
            entry_type = getattr(f.type, "__args__", None)[
                0
            ]  # type: ignore [index] # noqa
        except (TypeError, IndexError):
            entry_type = None

        # is the list's value type defined as a simple type?
        if type(entry_type) is type:
            out = []
            for i in range(len(descriptor_value)):
                v = descriptor_value[i]
                out.append(cls._instantiate_value(f"{f.name}[{i}]", f, entry_type, v))
            return out
        return descriptor_value

    @classmethod
    def load(
        cls: Type[DescriptorType], descriptor_dict: Dict[str, Any]
    ) -> DescriptorType:
        """Create a new descriptor object from its dictionary representation."""
        resolved_kwargs: Dict[str, Any] = {}
        for f in fields(cls):
            # if the fields value is not provided in the descriptor, we're leaving
            # that to the instantiated class' `__init__` to warn about that
            if f.name not in descriptor_dict.keys():
                continue

            descriptor_value = descriptor_dict.get(f.name)

            # field is a simple type (i.e. not a `typing` type hint)
            if type(f.type) is type:
                resolved_kwargs[f.name] = cls._instantiate_value(
                    f.name, f, f.type, descriptor_value
                )

            # field is an Optional[simple type] -> Union[type, NoneType]
            elif (
                getattr(f.type, "__origin__", None) is Union
                and len(f.type.__args__) == 2
                and f.type.__args__[1] is type(None)  # noqa
                and type(f.type.__args__[0]) is type
            ):
                resolved_kwargs[f.name] = cls._instantiate_value(
                    f.name, f, f.type.__args__[0], descriptor_value
                )

            # field is a `Dict`
            elif getattr(f.type, "__origin__", None) is dict:
                resolved_kwargs[f.name] = cls._load_dict(f, descriptor_value)  # type: ignore [arg-type] # noqa

            # field is a `List`
            elif getattr(f.type, "__origin__", None) is list:
                resolved_kwargs[f.name] = cls._load_list(f, descriptor_value)  # type: ignore [arg-type] # noqa

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
