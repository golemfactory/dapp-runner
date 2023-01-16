"""Test `Runner` factories."""
import factory

from yapapi.services import ServiceState

from dapp_runner.runner import Runner
from tests.factories.descriptor import ConfigFactory, DappDescriptorFactory


class RunnerFactory(factory.Factory):
    """Test factory for the dapp-runner's `Runner`."""

    class Meta:  # noqa
        model = Runner

    config = factory.SubFactory(ConfigFactory)
    dapp = factory.SubFactory(DappDescriptorFactory)

    @factory.post_generation
    def desired_app_state(obj, _, extracted: ServiceState, **__):  # noqa
        if extracted:
            obj._desired_app_state = extracted
