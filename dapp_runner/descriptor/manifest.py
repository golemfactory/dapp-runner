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


def _get_manifest(params) -> Optional[Manifest]:
    manifest_str = params.get("manifest")
    if manifest_str:
        manifest_dict = json.loads(standard_b64decode(manifest_str))
        return Manifest.parse_obj(manifest_dict, by_alias=True)

    return None


def _get_manifest_cert(params) -> Optional[crypto.X509]:
    cert_str = params.get("manifest_cert")
    if cert_str:
        return crypto.load_certificate(crypto.FILETYPE_PEM, standard_b64decode(cert_str))

    return None


def verify_manifest(payload_name: str, payload: PayloadDescriptor) -> None:
    """Verify a single payload manifest, if present."""

    manifest = _get_manifest(payload.params)
    cert = _get_manifest_cert(payload.params)
    sig = standard_b64decode(payload.params.get("manifest_sig", ""))
    sig_algorithm = payload.params.get("manifest_sig_algorithm", "")

    now = datetime.now(UTC)

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
