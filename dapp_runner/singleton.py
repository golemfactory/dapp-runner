"""Singleton metaclass module."""


from typing import Dict


class SingletonMeta(type):
    """Metaclass implementation of singleton design pattern."""

    _instances: Dict = {}

    def __call__(cls, *args, **kwargs):
        """Create and return single instance of given `cls`."""
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
