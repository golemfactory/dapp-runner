from dataclasses import dataclass
from typing import Optional

from .base import BaseDescriptor


@dataclass
class YagnaConfig:
    api_url: Optional[str] = None
    gsb_url: Optional[str] = None
    app_key: Optional[str] = None


@dataclass
class PaymentConfig:
    budget: float
    driver: str
    network: str


@dataclass
class Config(BaseDescriptor):
    yagna: YagnaConfig
    payment: PaymentConfig
