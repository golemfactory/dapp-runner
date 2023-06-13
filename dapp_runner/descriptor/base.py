"""Golem Application Object Model base."""
import json
import re
import typing
from typing import List, Optional

from pydantic import BaseModel


class GaomLookupError(Exception):
    """Error while performing a GAOM key lookup."""

    pass


class GaomRuntimeLookupError(GaomLookupError):
    """Accessing runtime property when not in runtime."""

    pass


class GaomQueryComponent(BaseModel):
    """A component of a GAOM key loookup query."""

    key: str
    index: Optional[int]

    def __str__(self):
        return self.key + str(f"[{self.index}]" if self.index is not None else "")


class GaomBase(BaseModel):
    """Base Golem Application Object Model class."""

    @staticmethod
    def _get_lookup_components(query: str) -> List[GaomQueryComponent]:
        """Get a list of components of the lookup query."""

        components = list()
        remainder = query
        while remainder:
            m = re.match(
                r"^(?P<key>\w+)(?:\[(?P<index>\d+)])?(?:\.|$)(?P<remainder>.*)?", remainder
            )
            if m:
                mdict = m.groupdict()
                remainder = mdict.pop("remainder", None)
                if mdict.get("index"):
                    mdict["index"] = int(mdict["index"])
                components.append(GaomQueryComponent(**mdict))
            elif remainder:
                break

        if remainder:
            raise ValueError(f"Malformed query: `{query}`")

        return components

    def _perform_generic_lookup(self, components: List[GaomQueryComponent], path: List[str]):
        """Iterate over GAOM lookup query components to arrive at a desired value."""

        data_dict = self.dict()

        for c in components:
            path.append(str(c))
            try:
                data = data_dict.get(c.key)
                if c.index is not None:
                    data = data[c.index]  # type: ignore
            except (AttributeError, KeyError, IndexError, TypeError):
                raise GaomLookupError(
                    f"{self.__class__.__name__}: " f"Cannot retrieve `{'.'.join(path)}`."
                )
            data_dict = data  # type: ignore

        return data_dict

    def _perform_gaom_lookup(
        self, components: List[GaomQueryComponent], path: List[str], is_runtime: bool
    ):
        """Recurse through GAOM objects, retrieving subsequent components."""
        if components:
            c = components[0]
            field = c.key

            if self.is_runtime_property(field) and not is_runtime:
                raise GaomRuntimeLookupError(
                    f"{self.__class__.__name__}: "
                    f"Fetching a runtime property `{field}` when not in runtime."
                )

            _type = typing.get_type_hints(self).get(field)
            _origin = typing.get_origin(_type)

            if not _origin and c.index is None:
                # field is a simple type
                if issubclass(_type, GaomBase):  # type: ignore [arg-type]
                    gaom_obj: GaomBase = getattr(self, field)
                    return gaom_obj._perform_gaom_lookup(components[1:], [field], is_runtime)
            elif _origin == typing.Union and c.index is None:
                _args = typing.get_args(_type)
                if (
                    len(_args) == 2
                    and issubclass(_args[1], type(None))
                    and issubclass(_args[0], GaomBase)
                ):
                    # field is an Optional GAOM object
                    gaom_obj: GaomBase = getattr(self, field)  # type: ignore [no-redef]
                    if gaom_obj:
                        return gaom_obj._perform_gaom_lookup(components[1:], [field], is_runtime)
            elif type(_origin) == type:
                # field is a complex type, e.g. Dict[str, GaomModel]
                _args = typing.get_args(_type)
                if (
                    issubclass(_origin, dict)
                    and c.index is None
                    and issubclass(_args[1], GaomBase)
                    and len(components) > 1
                ):
                    # field is a GAOM object dictionary
                    field_key = components[1].key
                    if components[1].index is None:
                        try:
                            gaom_obj: GaomBase = getattr(self, field)[field_key]  # type: ignore [no-redef]  # noqa
                        except KeyError:
                            raise GaomLookupError(
                                f"{self.__class__.__name__}: Cannot retrieve `{field}.{field_key}`"
                            )
                        if gaom_obj:
                            return gaom_obj._perform_gaom_lookup(
                                components[2:], [field, field_key], is_runtime
                            )
                elif (
                    issubclass(_origin, list)
                    and c.index is not None
                    and issubclass(_args[0], GaomBase)
                ):
                    # field is a GAOM object list
                    try:
                        gaom_obj: GaomBase = getattr(self, field)[c.index]  # type: ignore [no-redef]  # noqa
                    except IndexError:
                        raise GaomLookupError(
                            f"{self.__class__.__name__}: Cannot retrieve `{field}[{c.index}]`"
                        )
                    if gaom_obj:
                        return gaom_obj._perform_gaom_lookup(
                            components[1:], [f"{field}[{c.index}]"], is_runtime
                        )

        return self._perform_generic_lookup(components, path)

    def lookup(self, query: str, is_runtime: bool = False):
        """
        Perform a lookup on the GAOM object using a textual query.

        Example:
            ```
                dapp.lookup("services.db-service[1].network_node.ip")
            ```
        """
        return self._perform_gaom_lookup(self._get_lookup_components(query), list(), is_runtime)

    def is_runtime_property(self, field_name: str) -> bool:
        """Verify if the given GAOM field is a property set at runtime.

        (as opposed to something that can be part of a descriptor)
        """
        return (
            self.schema().get("properties").get(field_name).get("runtime", False)  # type: ignore [union-attr]  # noqa
        )

    def interpolate(self, root: "GaomBase", is_runtime: bool = False):
        """Interpolate GAOM lookups in this descriptor."""

        def interpolate(m):
            return root.lookup(m.group(1), is_runtime=is_runtime)

        serialized = json.dumps(self.dict())
        serialized = re.sub(r"\$\{([\w.\[\]]+)\}", interpolate, serialized)
        return self.__init__(**json.loads(serialized))  # type: ignore [misc]
