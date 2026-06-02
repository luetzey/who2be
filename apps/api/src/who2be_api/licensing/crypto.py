"""Offline-Verifikation signierter On-Prem-Lizenzen (Ed25519, Plan §3.5/§3.6).

Guardrails:
- **Kein Phone-Home** — die Lizenz wird rein lokal gegen den oeffentlichen
  Schluessel `K_pub` geprueft.
- **Nur der Public-Key liegt im Repo** (`keys/`), niemals der Private-Key. Mit
  `K_pub` laesst sich verifizieren, aber nicht signieren.

Lizenz-Token-Format (kompakt, URL-safe): ``<b64url(payload_json)>.<b64url(sig)>``.
Die Signatur deckt exakt die rohen Payload-Bytes (vor dem Base64-Decode) ab.
"""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

_KEYS_DIR = Path(__file__).resolve().parent / "keys"
# Datei-Slot fuer den oeffentlichen Signing-Key. Heute nur `.gitkeep`
# (Plan: "K_pub … heute .gitkeep"); im Deployment wird hier die echte
# `K_pub`-PEM hinterlegt, NIE der Private-Key.
_PUBLIC_KEY_FILENAME = "signing_key.pub"


class LicenseError(Exception):
    """Lizenz fehlt, ist fehlerhaft kodiert oder die Signatur stimmt nicht."""


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (binascii.Error, ValueError) as exc:
        raise LicenseError("Lizenz-Token ist nicht gueltig Base64url-kodiert.") from exc


def load_public_key(keys_dir: Path | None = None) -> Ed25519PublicKey | None:
    """Laedt `K_pub` aus dem `keys/`-Slot; `None`, wenn (noch) keiner hinterlegt ist.

    Ein fehlender Key ist On-Prem regulaer (reines OSS) — der Aufrufer faellt dann
    auf `OSS_ENTITLEMENT` zurueck statt zu scheitern.
    """
    path = (keys_dir or _KEYS_DIR) / _PUBLIC_KEY_FILENAME
    if not path.exists():
        return None
    pem = path.read_bytes()
    if not pem.strip():
        return None
    try:
        key = load_pem_public_key(pem)
    except (ValueError, TypeError) as exc:
        raise LicenseError("K_pub ist kein gueltiger PEM-Public-Key.") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseError("K_pub ist kein Ed25519-Public-Key.")
    return key


def verify_license_token(token: str, public_key: Ed25519PublicKey) -> dict[str, Any]:
    """Verifiziert die Ed25519-Signatur und liefert den Payload als Dict.

    Wirft `LicenseError` bei kaputtem Format **oder** ungueltiger Signatur — der
    Payload wird ausschliesslich nach erfolgreicher Verifikation zurueckgegeben,
    damit nie unverifizierte Daten in den Kern gelangen.
    """
    parts = token.strip().split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise LicenseError("Lizenz-Token-Format erwartet '<payload>.<signature>'.")
    payload_bytes = _b64url_decode(parts[0])
    signature = _b64url_decode(parts[1])
    try:
        public_key.verify(signature, payload_bytes)
    except InvalidSignature as exc:
        raise LicenseError("Lizenz-Signatur ist ungueltig.") from exc
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise LicenseError("Lizenz-Payload ist kein gueltiges JSON.") from exc
    if not isinstance(payload, dict):
        raise LicenseError("Lizenz-Payload muss ein JSON-Objekt sein.")
    return payload
