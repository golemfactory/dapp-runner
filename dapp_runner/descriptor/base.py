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
    def _load_dict(
        cls, f: Field, field_type, descriptor_value: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            entry_type = getattr(field_type, "__args__", None)[
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
    def _load_list(cls, f: Field, field_type, descriptor_value: List[Any]) -> List[Any]:
        try:
            entry_type = getattr(field_type, "__args__", None)[
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
    def _resolve_field(cls, f: Field, descriptor_value: Any, field_type=None):
        # field has a load function defined, so we're delegating the responsibility
        if f.metadata.get("load"):
            return f.metadata["load"](descriptor_value)

        elif not field_type:
            field_type = f.type

        # field is a simple type (i.e. not a `typing` type hint)
        if type(field_type) is type:
            return cls._instantiate_value(f.name, f, field_type, descriptor_value)

        # field is an Optional -> Union[..., NoneType]
        elif (
            getattr(field_type, "__origin__", None) is Union
            and len(field_type.__args__) == 2
            and field_type.__args__[1] is type(None)  # noqa
        ):
            return cls._resolve_field(f, descriptor_value, field_type.__args__[0])

        # field is a `Dict`
        elif getattr(field_type, "__origin__", None) is dict:
            return cls._load_dict(f, field_type, descriptor_value)

        # field is a `List`
        elif getattr(field_type, "__origin__", None) is list:
            return cls._load_list(f, field_type, descriptor_value)

        else:
            raise NotImplementedError(
                f"{cls.__name__}.{f.name}: Unimplemented handler for {field_type}"
            )

    @classmethod
    def load(
        cls: Type[DescriptorType], descriptor_dict: Dict[str, Any]
    ) -> DescriptorType:
        """Create a new descriptor object from its dictionary representation."""
        resolved_kwargs: Dict[str, Any] = {}
        for f in fields(cls):
            # skip non-init fields
            if not f.init:
                continue

            # if the fields value is not provided in the descriptor, we're leaving
            # that to the instantiated class' `__init__` to warn about that
            if f.name not in descriptor_dict.keys():
                continue

            descriptor_value = descriptor_dict.get(f.name)
            resolved_kwargs[f.name] = cls._resolve_field(f, descriptor_value)

        unexpected_keys = set(descriptor_dict.keys()) - set(f.name for f in fields(cls))
        if unexpected_keys:
            raise DescriptorError(
                f"Unexpected keys: `{unexpected_keys}` for `{cls.__name__}`"
            )
        return cls(**resolved_kwargs)
