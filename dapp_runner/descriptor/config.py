"""Class definitions for the Dapp Runner's configuration descriptor."""
from dataclasses import dataclass, field
import os
from typing import Optional

from .base import BaseDescriptor


@dataclass
class YagnaConfig(BaseDescriptor["YagnaConfig"]):
    """Yagna daemon configuration properties.

    Properties describing the local requestor daemon configuration that
    the Dapp Runner will use to run services on Golem.
    """

    def __app_key__factory(value: str):  # type: ignore [misc]  # noqa
        # TODO this should be applied uniformly across any fields,
        # for now, making an exception for the app key

        if value and value.startswith("$"):
            return os.environ[value[1:]]

        return value

    subnet_tag: Optional[str]
    api_url: Optional[str] = None
    gsb_url: Optional[str] = None
    app_key: Optional[str] = field(
        metadata={"factory": __app_key__factory}, default=None
    )


@dataclass
class PaymentConfig:
    """Requestor's payment config."""

    budget: float
    driver: str
    network: str


@dataclass
class LimitsConfig:
    """Limits of the running app."""

    startup_timeout: Optional[int] = None  # seconds
    max_running_time: Optional[int] = None  # seconds


@dataclass
class Config(BaseDescriptor["Config"]):
    """Root configuration descriptor for the Dapp Runner."""

    yagna: YagnaConfig
    payment: PaymentConfig
    limits: LimitsConfig = field(default_factory=LimitsConfig)
