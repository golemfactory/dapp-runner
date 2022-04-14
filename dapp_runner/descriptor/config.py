"""Class definitions for the Dapp Runner's configuration descriptor."""
from dataclasses import dataclass
from typing import Optional

from .base import BaseDescriptor


@dataclass
class YagnaConfig:
    """Yagna daemon configuration properties.

    Properties describing the local requestor daemon configuration that
    the Dapp Runner will use to run services on Golem.
    """

    subnet_tag: Optional[str]
    api_url: Optional[str] = None
    gsb_url: Optional[str] = None
    app_key: Optional[str] = None


@dataclass
class PaymentConfig:
    """Requestor's payment config."""

    budget: float
    driver: str
    network: str


@dataclass
class Config(BaseDescriptor["Config"]):
    """Root configuration descriptor for the Dapp Runner."""

    yagna: YagnaConfig
    payment: PaymentConfig
