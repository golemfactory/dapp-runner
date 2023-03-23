"""Tests for the Config descriptor."""
import pytest
from pydantic import ValidationError

from dapp_runner.descriptor.config import Config, PaymentConfig, YagnaConfig


@pytest.mark.parametrize(
    "descriptor_dict, error",
    [
        (
            {
                "yagna": {"subnet_tag": "devnet-beta"},
                "payment": {
                    "budget": 1.0,
                    "driver": "erc20",
                    "network": "rinkeby",
                },
            },
            None,
        ),
        (
            {
                "yagna": {"subnet_tag": "devnet-beta"},
            },
            (ValidationError, "payment"),
        ),
        (
            {
                "yagna": {"subnet_tag": "devnet-beta"},
                "payment": {
                    "budget": 1.0,
                    "driver": "erc20",
                    "network": "rinkeby",
                },
                "foo": "bar",
            },
            (ValidationError, "extra fields not permitted"),
        ),
    ],
)
def test_config_descriptor(descriptor_dict, error):
    """Test whether the Config descriptor loads properly."""
    try:
        config = Config(**descriptor_dict)
        assert isinstance(config.yagna, YagnaConfig)
        assert isinstance(config.payment, PaymentConfig)
        # raise Exception(config.payment)

    except Exception as e:  # noqa
        if not error:
            raise

        assert str(error[1]) in str(e)
        assert type(e) == error[0]
