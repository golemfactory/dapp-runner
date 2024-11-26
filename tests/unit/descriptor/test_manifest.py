"""Test `dapp_runner`'s manifest validation support."""

import json
from base64 import standard_b64encode
from datetime import datetime, timedelta
from typing import Optional
from unittest import mock

import pytest
from dateutil.tz import UTC
from OpenSSL import crypto

from yapapi.payload.manifest import Manifest

from dapp_runner.descriptor import DappDescriptor, manifest
from dapp_runner.descriptor.dapp import PAYLOAD_RUNTIME_VM_MANIFEST, PayloadDescriptor


@pytest.fixture
@mock.patch(
    "yapapi.payload.manifest.vm.resolve_package_url",
    mock.AsyncMock(return_value="hash:sha3:some_image_hash:some_image_url"),
)
async def minimal_manifest() -> Manifest:
    """Minimal manifest fixture."""
    return await Manifest.generate("some-hash")


async def _get_payload(manifest: Manifest) -> dict:
    """Get payload with properly encoded manifest."""
    manifest_json = json.dumps(manifest.dict(by_alias=True))
    manifest_b64 = standard_b64encode(manifest_json.encode("ascii")).decode("ascii")

    return {
        "runtime": PAYLOAD_RUNTIME_VM_MANIFEST,
        "params": {"manifest": manifest_b64},
    }


async def _get_descriptor(manifest: Manifest) -> dict:
    return {
        "payloads": {"test": await _get_payload(manifest)},
        "nodes": {
            "test": {
                "payload": "test",
                "init": [],
            }
        },
    }


def _format_cert_timestamp(time: datetime) -> bytes:
    return time.strftime("%Y%m%d%H%M%SZ").encode("ascii")


def _set_key_and_cert(
    payload: PayloadDescriptor,
    not_after: datetime = datetime.now(UTC) + timedelta(days=1),
    not_before: datetime = datetime.now(UTC) - timedelta(days=1),
    sig_key: Optional[crypto.PKey] = None,
):
    pkey = crypto.PKey()
    pkey.generate_key(crypto.TYPE_RSA, 512)

    if not sig_key:
        sig_key = pkey

    cert = crypto.X509()
    cert.set_pubkey(pkey)
    cert.set_notAfter(_format_cert_timestamp(not_after))
    cert.set_notBefore(_format_cert_timestamp(not_before))
    cert.sign(pkey, "sha256")

    cert_bytes = standard_b64encode(crypto.dump_certificate(crypto.FILETYPE_PEM, cert)).decode(
        "ascii"
    )

    payload.params["manifest_cert"] = cert_bytes
    payload.params["manifest_sig_algorithm"] = "sha256"
    payload.params["manifest_sig"] = standard_b64encode(
        crypto.sign(sig_key, payload.params["manifest"], "sha256")
    ).decode("ascii")


async def test_verify_manifests(minimal_manifest):
    """Test Dapp's verify_manifests."""
    descriptor = await _get_descriptor(minimal_manifest)
    dapp = DappDescriptor(**descriptor)
    manifest.verify_manifests(dapp)


async def test_verify_manifest(minimal_manifest):
    """Test verify_manifest for a single Payload descriptor."""
    descriptor = await _get_payload(minimal_manifest)
    payload = PayloadDescriptor(**descriptor)
    manifest.verify_manifest("test", payload)


@pytest.mark.parametrize(
    "overrides, error_msg",
    (
        (
            {"created_at": datetime.now(UTC) + timedelta(days=1)},
            "Manifest creation date is set to future",
        ),
        (
            {"expires_at": datetime.now(UTC) - timedelta(days=1)},
            "Manifest already expired",
        ),
    ),
)
async def test_verify_manifest_dates_outside_bounds(minimal_manifest, overrides, error_msg):
    """Test error reporting for a manifest out of bounds."""
    for k, v in overrides.items():
        setattr(minimal_manifest, k, v)
    descriptor = await _get_payload(minimal_manifest)
    payload = PayloadDescriptor(**descriptor)
    with pytest.raises(ValueError) as e_info:
        manifest.verify_manifest("test", payload)

    assert error_msg in str(e_info)


async def test_verify_manifest_cert(minimal_manifest):
    """Test manifest with a certificate."""
    descriptor = await _get_payload(minimal_manifest)
    payload = PayloadDescriptor(**descriptor)
    _set_key_and_cert(payload)
    manifest.verify_manifest("test", payload)


@pytest.mark.parametrize(
    "overrides, error_msg",
    (
        (
            {"not_before": datetime.now(UTC) + timedelta(days=1)},
            "Manifest certificate is not yet valid",
        ),
        (
            {"not_after": datetime.now(UTC) - timedelta(days=1)},
            "Manifest certificate is no longer valid",
        ),
    ),
)
async def test_verify_manifest_cert_dates_outside_bounds(minimal_manifest, overrides, error_msg):
    """Test manifest with a certificate."""
    descriptor = await _get_payload(minimal_manifest)
    payload = PayloadDescriptor(**descriptor)

    _set_key_and_cert(payload, **overrides)

    with pytest.raises(ValueError) as e_info:
        manifest.verify_manifest("test", payload)

    assert error_msg in str(e_info)


async def test_verify_manifest_cert_sig_broken(minimal_manifest):
    """Test manifest with a certificate."""
    descriptor = await _get_payload(minimal_manifest)
    payload = PayloadDescriptor(**descriptor)

    fake_key = crypto.PKey()
    fake_key.generate_key(crypto.TYPE_RSA, 4096)

    _set_key_and_cert(payload, sig_key=fake_key)

    with pytest.raises(ValueError) as e_info:
        manifest.verify_manifest("test", payload)

    assert "Manifest signature verification failed" in str(e_info)
