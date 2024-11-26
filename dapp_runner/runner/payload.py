"""yapapi Payload bindings."""

import base64
import inspect
import json
import logging
from typing import Awaitable, Callable, Dict, Union

from yapapi.payload import Payload, vm
from yapapi.payload.manifest import Manifest

from dapp_runner.descriptor.dapp import (
    PAYLOAD_RUNTIME_VM,
    PAYLOAD_RUNTIME_VM_MANIFEST,
    PayloadDescriptor,
)

from .error import RunnerError

logger = logging.getLogger(__name__)


async def resolve_manifest(desc: PayloadDescriptor):
    """Resolve a dynamically-generated manifest payload.

    When the payload definition contains the `manifest_generate` key, it
    attempts to construct a correctly constructed manifest based on a simplified
    set of parameters and replaces the `manifest_generate` with a new `manifest` key.

    Example payload:

    ```yaml
    payloads:
        backend:
            runtime: "vm/manifest"
            params:
                manifest_generate:
                    image_hash: "e3c964343169d0a08b66751bfba89a90ec97544d8752c9a3e4ae0901"
                    outbound_urls:
                        - "http://bor.golem.network"
                        - "https://geth.golem.network:55555"
                        - "https://bor.golem.network"
                        - "http://geth.testnet.golem.network:55555"
    ```

    """

    if "manifest" in desc.params and "manifest_generate" in desc.params:
        raise RunnerError(
            "Ambiguous payload definition: "
            f"both `manifest` and `manifest_generate` specified. ({desc.params})"
        )
    elif "manifest" not in desc.params and "manifest_generate" in desc.params:
        manifest_generate_params = desc.params.pop("manifest_generate")
        logger.debug("Generating a manifest implicitly, params: %s", manifest_generate_params)
        manifest_obj = await Manifest.generate(**manifest_generate_params)

        manifest = json.dumps(manifest_obj.dict(by_alias=True))

        logger.debug("Generated manifest: %s", manifest)
        encoded_manifest = base64.b64encode(manifest.encode("utf-8")).decode("ascii")

        desc.params["manifest"] = encoded_manifest


async def get_payload(desc: PayloadDescriptor) -> Payload:
    """Create an instance of yapapi Payload for a given runtime type."""
    runtimes: Dict[str, Callable[..., Union[Payload, Awaitable[Payload]]]] = {
        PAYLOAD_RUNTIME_VM: vm.repo,
        PAYLOAD_RUNTIME_VM_MANIFEST: vm.manifest,
    }

    runtime = desc.runtime.lower()

    if runtime in runtimes.keys():
        if runtime == PAYLOAD_RUNTIME_VM_MANIFEST:
            # Create a copy of params to modify
            params = desc.params.copy()

            # Handle manifest file path
            if "manifest_path" in params:
                with open(params["manifest_path"], "rb") as f:
                    params["manifest"] = f.read()
                del params["manifest_path"]

            # Handle node descriptor path
            if "node_descriptor_path" in params:
                with open(params["node_descriptor_path"]) as f:
                    params["node_descriptor"] = json.load(f)
                del params["node_descriptor_path"]

            await resolve_manifest(PayloadDescriptor(runtime=desc.runtime, params=params))
            payload = runtimes[desc.runtime](**params)
        else:
            payload = runtimes[desc.runtime](**desc.params)

        if inspect.isawaitable(payload):
            return await payload
        return payload  # type: ignore [return-value]  # noqa

    raise RunnerError(f"Unknown runtime: `{desc.runtime}`")
