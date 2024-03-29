"""Test factories for Dapp Runner's Config descriptor."""
import factory

from dapp_runner.descriptor.config import Config, PaymentConfig, YagnaConfig


class YagnaConfigFactory(factory.Factory):
    """Test factory for `YagnaConfig` objects."""

    class Meta:  # noqa
        model = YagnaConfig

    subnet_tag = "public"
    app_key = factory.Faker("pystr")


class PaymentConfigFactory(factory.Factory):
    """Test factory for `PaymentConfig` objects."""

    class Meta:  # noqa
        model = PaymentConfig

    budget = 1.0
    driver = "erc20"
    network = "rinkeby"


class ConfigFactory(factory.Factory):
    """Test factory for `Config` objects."""

    class Meta:  # noqa
        model = Config

    yagna = factory.SubFactory(YagnaConfigFactory)
    payment = factory.SubFactory(PaymentConfigFactory)
