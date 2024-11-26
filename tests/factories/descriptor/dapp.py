"""Test factories for Dapp Runner's Dapp descriptor."""

from factory import DictFactory, Factory, Faker, post_generation

from dapp_runner.descriptor.dapp import DappDescriptor, PayloadDescriptor, ServiceDescriptor


class PayloadDescriptorFactory(Factory):
    """Test factory for `PayloadDescriptor` objects."""

    class Meta:  # noqa
        model = PayloadDescriptor

    runtime = "fake_runtime"


class ServiceDescriptorFactory(Factory):
    """Test factory for `ServiceDescriptor` objects."""

    class Meta:  # noqa
        model = ServiceDescriptor

    payload = Faker("pystr")


class DappDescriptorFactory(Factory):
    """Test factory for `DappDescriptor` objects."""

    class Meta:  # noqa
        model = DappDescriptor

    payloads = DictFactory()
    nodes = DictFactory()

    @post_generation
    def node_count(obj, _create, extracted, **__):  # noqa
        """Automatically generate entries in the nodes dictionary."""
        if extracted:
            for i in range(extracted):
                obj.payloads[f"node{i}"] = PayloadDescriptorFactory()
                obj.nodes[f"node{i}"] = ServiceDescriptorFactory(payload=f"node{i}")
