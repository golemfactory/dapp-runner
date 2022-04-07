from typing import Union, List

from yapapi.services import Service


class DappService(Service):
    entrypoint: List[Union[List[str], str]]

    async def start(self):
        # perform the initialization of the Service
        # (which includes sending the network details within the `deploy` command)
        async for script in super().start():
            yield script

        if self.entrypoint:
            script = self._ctx.new_script()
            if isinstance(self.entrypoint[0], str):
                # only one command to execute
                script.run(*self.entrypoint)
            else:
                # multiple commands
                for c in self.entrypoint:
                    script.run(*c)
            yield script
