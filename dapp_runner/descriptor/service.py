"""yapapi Service bindings."""
from typing import Union, List

from yapapi.services import Service


class DappService(Service):
    """Yapapi Service definition for the Dapp Runner services."""

    entrypoint: Union[List[List[str]], List[str]]

    async def start(self):
        """Start the service on a given provider."""

        # perform the initialization of the Service
        # (which includes sending the network details within the `deploy` command)
        async for script in super().start():
            yield script

        if self.entrypoint:
            script = self._ctx.new_script()  # type: ignore  # noqa - it's asserted in super().start()
            if isinstance(self.entrypoint[0], str):
                # only one command to execute
                script.run(*self.entrypoint)
            else:
                # multiple commands
                for c in self.entrypoint:
                    script.run(*c)
            yield script
