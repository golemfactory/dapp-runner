"""Manifest verification support."""

import json
import logging
import re
from base64 import standard_b64decode
from datetime import datetime
from typing import Optional

from dateutil.tz import UTC
from OpenSSL import crypto

from yapapi.payload.manifest import Manifest

from .dapp import PAYLOAD_RUNTIME_VM_MANIFEST, DappDescriptor, PayloadDescriptor

logger = logging.getLogger(__name__)


def _read_json_file(file_path: str) -> dict:
    """Read and return JSON content from a file."""
    with open(file_path) as f:
        return json.load(f)


def _get_manifest(params) -> Optional[Manifest]:
    """Get manifest from either direct content, base64 string, or file path."""
    if "manifest" in params:
        manifest_content = params["manifest"]
        # If manifest is a base64 string, decode it first
        if isinstance(manifest_content, str):
            try:
                manifest_content = json.loads(standard_b64decode(manifest_content))
            except Exception:
                # If not base64 or not JSON, try using it directly
                try:
                    manifest_content = json.loads(manifest_content)
                except json.JSONDecodeError:
                    raise ValueError("Manifest content is neither valid base64 nor valid JSON")
    elif "manifest_path" in params:
        manifest_content = _read_json_file(params["manifest_path"])
    else:
        return None

    return Manifest.parse_obj(manifest_content, by_alias=True)


def _get_node_descriptor(params) -> Optional[dict]:
    """Get node descriptor from file path."""
    if "node_descriptor_path" in params:
        return _read_json_file(params["node_descriptor_path"])
    return None


def _read_base64_file(file_path: str) -> str:
    """Read and return base64 encoded content from a file."""
    with open(file_path, "rb") as f:
        return f.read().decode("utf-8")


def _get_manifest_cert(params) -> Optional[crypto.X509]:
    """Get certificate from either direct content or file path."""
    if "manifest_cert" in params:
        cert_str = params["manifest_cert"]
    elif "manifest_cert_path" in params:
        cert_str = _read_base64_file(params["manifest_cert_path"])
    else:
        return None

    return crypto.load_certificate(crypto.FILETYPE_PEM, standard_b64decode(cert_str))


def verify_manifest(payload_name: str, payload: PayloadDescriptor) -> None:
    """Verify a single payload manifest, if present."""
    manifest = _get_manifest(payload.params)
    node_descriptor = _get_node_descriptor(payload.params)
    print(f"Node Descriptor: {node_descriptor}")
    print(f"Manifest: {manifest}")
    # When node_descriptor is present, only manifest is required
    if node_descriptor:
        if not manifest:
            raise ValueError(f"`{payload_name}`: node_descriptor requires a manifest to be present")
        # Skip other verifications when using node_descriptor
        return

    # Only proceed with cert/sig verification if no node_descriptor is present
    if manifest:
        print(f"Manifest: {manifest}")
        cert = _get_manifest_cert(payload.params)
        sig = standard_b64decode(payload.params.get("manifest_sig", ""))
        sig_algorithm = payload.params.get("manifest_sig_algorithm", "")

    now = datetime.now(UTC)

    # If node_descriptor is present, manifest must also be present
    if node_descriptor and not manifest:
        raise ValueError(f"`{payload_name}`: node_descriptor requires a manifest to be present")

    if manifest:
        if manifest.created_at > now:
            raise ValueError(f"`{payload_name}`: Manifest creation date is set to future.")

        if manifest.expires_at < now:
            raise ValueError(f"`{payload_name}`: Manifest already expired.")

    if cert:
        if cert.get_notBefore():
            not_valid_before = datetime.strptime(
                cert.get_notBefore().decode("ascii"), "%Y%m%d%H%M%SZ"  # type: ignore [union-attr]
            ).replace(tzinfo=UTC)

            if now < not_valid_before:
                raise ValueError(
                    f"`{payload_name}`: Manifest certificate is not yet valid "
                    f"(not valid before: {not_valid_before})."
                )

        if cert.get_notAfter():
            not_valid_after = datetime.strptime(
                cert.get_notAfter().decode("ascii"), "%Y%m%d%H%M%SZ"  # type: ignore [union-attr]
            ).replace(tzinfo=UTC)

            if now > not_valid_after:
                raise ValueError(
                    f"`{payload_name}`: Manifest certificate is no longer valid "
                    f"(not valid after: {not_valid_after})."
                )

        if not sig:
            logger.warning(
                "`%s`: Manifest certificate provided but no signature present.",
                payload_name,
            )

    if sig:
        matches = re.findall(
            b"-----BEGIN CERTIFICATE-----\n.*?\n-----END CERTIFICATE-----\n",
            standard_b64decode(payload.params.get("manifest_cert", "")),
            re.MULTILINE | re.DOTALL,
        )
        in_cert = matches.pop()
        read_cert = crypto.load_certificate(crypto.FILETYPE_PEM, in_cert)
        try:
            crypto.verify(read_cert, sig, payload.params.get("manifest", ""), sig_algorithm)
        except crypto.Error:
            raise ValueError(f"`{payload_name}`: Manifest signature verification failed.")


def verify_manifests(dapp: DappDescriptor) -> None:
    """Verify manifests in the dapp's payloads."""

    for payload_name, payload in dapp.payloads.items():
        if payload.runtime == PAYLOAD_RUNTIME_VM_MANIFEST:
            verify_manifest(payload_name, payload)
