"""Unit-Tests fuer die Offline-Lizenz-Verifikation (Ed25519, `licensing/crypto.py`).

Signiert mit einem **Test-only** Private-Key (nie im Repo) und prueft den
Roundtrip + die Ablehnung manipulierter/kaputter Tokens. Belegt die Guardrail:
unverifizierte Payloads erreichen den Kern nie.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from who2be_api.licensing.crypto import (
    LicenseError,
    load_public_key,
    verify_license_token,
)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def sign_license(private_key: Ed25519PrivateKey, payload: dict[str, Any]) -> str:
    """Test-Helper: baut ein '<payload>.<sig>'-Lizenz-Token."""
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = private_key.sign(payload_bytes)
    return f"{_b64url(payload_bytes)}.{_b64url(signature)}"


def write_public_key(private_key: Ed25519PrivateKey, keys_dir: Path) -> None:
    """Schreibt nur den Public-Key in den `keys/`-Slot (signing_key.pub)."""
    pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (keys_dir / "signing_key.pub").write_bytes(pem)


def test_valid_license_roundtrips() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = sign_license(private_key, {"features": ["core", "sso"], "mcp_monthly_quota": 5000})
    payload = verify_license_token(token, private_key.public_key())
    assert payload["features"] == ["core", "sso"]
    assert payload["mcp_monthly_quota"] == 5000


def test_tampered_signature_is_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = sign_license(private_key, {"features": ["core"]})
    payload_part, _, sig_part = token.partition(".")
    # Andere Identitaet signiert NICHT diese Payload → Signatur passt nicht.
    forged = sign_license(Ed25519PrivateKey.generate(), {"features": ["sso", "audit_export"]})
    forged_sig = forged.split(".")[1]
    tampered = f"{payload_part}.{forged_sig}"
    assert sig_part  # sanity
    with pytest.raises(LicenseError):
        verify_license_token(tampered, private_key.public_key())


def test_malformed_token_is_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    with pytest.raises(LicenseError):
        verify_license_token("not-a-valid-token", private_key.public_key())
    with pytest.raises(LicenseError):
        verify_license_token("only-one-part", private_key.public_key())


def test_load_public_key_from_dir(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    write_public_key(private_key, tmp_path)
    loaded = load_public_key(tmp_path)
    assert loaded is not None
    # Verifiziert ein echtes Token mit dem geladenen Key.
    token = sign_license(private_key, {"features": ["core"]})
    assert verify_license_token(token, loaded)["features"] == ["core"]


def test_load_public_key_missing_returns_none(tmp_path: Path) -> None:
    assert load_public_key(tmp_path) is None


def test_load_public_key_invalid_pem_raises(tmp_path: Path) -> None:
    (tmp_path / "signing_key.pub").write_bytes(b"-----BEGIN PUBLIC KEY-----\nnonsense\n")
    with pytest.raises(LicenseError):
        load_public_key(tmp_path)
