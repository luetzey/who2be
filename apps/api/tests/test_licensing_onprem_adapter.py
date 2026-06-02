"""Unit-Tests fuer den On-Prem-Entitlement-Adapter (offline, K_pub)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_licensing_crypto import sign_license, write_public_key  # type: ignore[import-not-found]

from who2be_api.core.config import Settings
from who2be_api.licensing.adapters.onprem import OnPremEntitlementAdapter
from who2be_api.licensing.entitlement import OSS_ENTITLEMENT


def test_no_license_key_falls_back_to_oss() -> None:
    adapter = OnPremEntitlementAdapter(Settings(edition="onprem", license_key=""))
    assert asyncio.run(adapter.resolve(uuid4())) == OSS_ENTITLEMENT


def test_license_without_pubkey_falls_back_to_oss(tmp_path: Path) -> None:
    # Kein signing_key.pub im keys_dir ⇒ keine Verifikation moeglich ⇒ OSS.
    private_key = Ed25519PrivateKey.generate()
    token = sign_license(private_key, {"features": ["core"]})
    adapter = OnPremEntitlementAdapter(
        Settings(edition="onprem", license_key=token), keys_dir=tmp_path
    )
    assert asyncio.run(adapter.resolve(uuid4())) == OSS_ENTITLEMENT


def test_valid_license_is_parsed(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    write_public_key(private_key, tmp_path)
    token = sign_license(
        private_key,
        {"features": ["core", "sso"], "mcp_monthly_quota": 9000},
    )
    adapter = OnPremEntitlementAdapter(
        Settings(edition="onprem", license_key=token), keys_dir=tmp_path
    )
    ent = asyncio.run(adapter.resolve(uuid4()))
    assert ent.is_active()
    assert ent.features == frozenset({"core", "sso"})
    assert ent.mcp_monthly_quota == 9000


def test_tampered_license_does_not_grant_features(tmp_path: Path) -> None:
    # Eine fremd signierte Lizenz darf KEINE Features gewaehren — Fallback auf OSS,
    # aber der manipulierte Payload (z. B. "alle Features") wird nie uebernommen.
    legit_key = Ed25519PrivateKey.generate()
    write_public_key(legit_key, tmp_path)
    forged = sign_license(Ed25519PrivateKey.generate(), {"features": ["sso", "audit_export"]})
    adapter = OnPremEntitlementAdapter(
        Settings(edition="onprem", license_key=forged), keys_dir=tmp_path
    )
    # Faellt auf OSS zurueck (unbegrenzt On-Prem) — die geschmuggelten Claims werden
    # nicht aus der unverifizierten Lizenz uebernommen.
    assert asyncio.run(adapter.resolve(uuid4())) == OSS_ENTITLEMENT
