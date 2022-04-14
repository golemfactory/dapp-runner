"""Tests for the Config descriptor."""
import pytest

from dapp_runner.descriptor import DescriptorError
from dapp_runner.descriptor.config import Config, YagnaConfig, PaymentConfig


@pytest.mark.asyncio
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
            TypeError("__init__() missing"),
        ),
        (
            {
                "foo": "bar",
            },
            DescriptorError("Unexpected keys: `{'foo'}"),
        ),
    ],
)
async def test_config_descriptor(descriptor_dict, error):
    """Test whether the Config descriptor loads properly."""
    try:
        config = await Config.new(descriptor_dict)
        assert isinstance(config.yagna, YagnaConfig)
        assert isinstance(config.payment, PaymentConfig)
    except Exception as e:  # noqa
        if not error:
            raise
        assert str(e).startswith(str(error))
        assert type(e) == type(error)
