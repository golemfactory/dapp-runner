"""Test factories for Dapp Runner's Dapp descriptor."""
import factory

from dapp_runner.descriptor.dapp import (
    DappDescriptor,
    PayloadDescriptor,
    ServiceDescriptor,
)


class PayloadDescriptorFactory(factory.Factory):
    """Test factory for `PayloadDescriptor` objects."""

    class Meta:  # noqa
        model = PayloadDescriptor

    runtime = "fake_runtime"


class ServiceDescriptorFactory(factory.Factory):
    """Test factory for `ServiceDescriptor` objects."""

    class Meta:  # noqa
        model = ServiceDescriptor

    payload = factory.Faker("pystr")


class DappDescriptorFactory(factory.Factory):
    """Test factory for `DappDescriptor` objects."""

    class Meta:  # noqa
        model = DappDescriptor

    payloads = factory.DictFactory()
    nodes = factory.DictFactory()

    @factory.post_generation
    def node_count(obj, _create, extracted, **__):  # noqa
        """Automatically generate entries in the nodes dictionary."""

        if extracted:
            for i in range(extracted):
                obj.payloads[f"node{i}"] = PayloadDescriptorFactory()
                obj.nodes[f"node{i}"] = ServiceDescriptorFactory(payload=f"node{i}")
