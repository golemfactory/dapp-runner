"""Golem Application Object Model base."""
import re
from typing import List, Optional

from pydantic import BaseModel


class GaomLookupError(Exception):
    """Error while performing a GAOM key lookup."""

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

    def lookup(self, query: str):
        """Perform a lookup on the GAOM object."""

        components = self._get_lookup_components(query)
        data_dict = self.dict()
        path: List[str] = list()

        for c in components:
            try:
                data = data_dict.get(c.key)
                if c.index is not None:
                    data = data[c.index]  # type: ignore
            except (AttributeError, KeyError):
                raise GaomLookupError(
                    f"{self.__class__.__name__}: "
                    f"Cannot retrieve `{'.'.join(path)}{'.' if path else ''}{c}`."
                )
            path.append(str(c))
            data_dict = data  # type: ignore

        return data_dict
