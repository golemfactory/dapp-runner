"""Class definitions for the Dapp Runner's configuration descriptor."""
import os
from typing import Optional

from pydantic import BaseModel, Field, validator


class YagnaConfig(BaseModel):
    """Yagna daemon configuration properties.

    Properties describing the local requestor daemon configuration that
    the Dapp Runner will use to run services on Golem.
    """

    subnet_tag: Optional[str]
    api_url: Optional[str] = None
    gsb_url: Optional[str] = None
    app_key: Optional[str] = None

    class Config:  # noqa: D106
        extra = "forbid"

    @validator("app_key", always=True)
    def __app_key__extrapolate(cls, v):
        # TODO this should be applied uniformly across any fields,
        # for now, making an exception for the app key

        if v and v.startswith("$"):
            return os.environ[v[1:]]

        return v


class PaymentConfig(BaseModel):
    """Requestor's payment config."""

    budget: float
    driver: str
    network: str

    class Config:  # noqa: D106
        extra = "forbid"


class LimitsConfig(BaseModel):
    """Limits of the running app."""

    startup_timeout: Optional[int] = None  # seconds
    max_running_time: Optional[int] = None  # seconds

    class Config:  # noqa: D106
        extra = "forbid"


class ApiConfig(BaseModel):
    """Configuration of the built-in API Server."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    class Config:  # noqa: D106
        extra = "forbid"


class Config(BaseModel):
    """Root configuration descriptor for the Dapp Runner."""

    yagna: YagnaConfig
    payment: PaymentConfig
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)

    class Config:  # noqa: D106
        extra = "forbid"
