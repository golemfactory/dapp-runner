"""Test factories for Dapp Runner's Config descriptor."""

from factory import Factory, Faker, SubFactory

from dapp_runner.descriptor.config import Config, PaymentConfig, YagnaConfig


class YagnaConfigFactory(Factory):
    """Test factory for `YagnaConfig` objects."""

    class Meta:  # noqa
        model = YagnaConfig

    subnet_tag = "public"
    app_key = Faker("pystr")


class PaymentConfigFactory(Factory):
    """Test factory for `PaymentConfig` objects."""

    class Meta:  # noqa
        model = PaymentConfig

    budget = 1.0
    driver = "erc20"
    network = "holesky"


class ConfigFactory(Factory):
    """Test factory for `Config` objects."""

    class Meta:  # noqa
        model = Config

    yagna = SubFactory(YagnaConfigFactory)
    payment = SubFactory(PaymentConfigFactory)
