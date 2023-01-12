"""Test factories for Dapp Runner's Dapp descriptor."""
import factory

from dapp_runner.descriptor.dapp import DappDescriptor


class DappDescriptorFactory(factory.Factory):
    """Test factory for `DappDescriptor` objects."""

    class Meta:  # noqa
        model = DappDescriptor

    payloads = factory.DictFactory()
    nodes = factory.DictFactory()
