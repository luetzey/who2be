#!/usr/bin/env python3
"""Erzeugt das ``GOTRUE_EXTERNAL_APPLE_SECRET`` — ein ES256-JWT fuer Apple.

Warum es dieses Skript gibt
---------------------------
Google und GitHub geben einen Client-Secret-String aus, den man kopiert und
einsetzt. **Apple gibt keinen Secret-String heraus.** Was Apple herausgibt, ist
eine ``.p8``-Schluesseldatei; das Secret muss daraus lokal als JWT signiert
werden — und dieses JWT **laeuft ab**, nach hoechstens sechs Monaten
(15 777 000 s, Apple: „It's an error to request an expiration time more than
15777000 seconds (six months) in the future").

GoTrue erneuert es nicht. Es liest ``GOTRUE_EXTERNAL_APPLE_SECRET`` als opaken
String und haengt ihn beim Token-Tausch an Apple. Laeuft das JWT ab, antwortet
Apple ``invalid_client``, GoTrue macht daraus eine generische 500, und die
Apple-Anmeldung faellt **still** aus, waehrend Google und GitHub weiterlaufen.
Deshalb nennt dieses Skript das Ablaufdatum in seiner Ausgabe: es ist der Wert,
der in den Kalender gehoert.

Ohne dieses Skript bliebe dem Betreiber nur, sein Signing-Material durch einen
fremden Online-Generator oder ein Gist zu schicken. Das Skript nutzt die
``cryptography``-Bibliothek, die im Repo ohnehin schon Dependency ist
(``apps/api/pyproject.toml``), und schreibt den Schluessel nirgends hin.

Benutzung
---------
::

    uv run python scripts/gen_apple_client_secret.py \\
        --team-id ABCDE12345 \\
        --key-id FGHIJ67890 \\
        --services-id de.example.web \\
        --p8 ~/Downloads/AuthKey_FGHIJ67890.p8

Die vier Werte kommen aus dem Apple-Developer-Portal; wo genau, steht in
``deploy/hetzner/supabase/README.md`` (Abschnitt „Sign in with Apple").
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import sys
from pathlib import Path

# Apple: "It's an error to request an expiration time more than 15777000
# seconds (six months) in the future, as measured by the clock on Apple's
# servers." Genau am Limit zu landen ist riskant, wenn Apples Uhr ein paar
# Sekunden vorgeht — deshalb ist der Default etwas darunter (180 Tage).
APPLE_MAX_LIFETIME_SECONDS = 15_777_000
DEFAULT_LIFETIME_SECONDS = 180 * 24 * 3600

APPLE_AUDIENCE = "https://appleid.apple.com"


class AppleSecretError(Exception):
    """Fehlerhafte Eingabe — mit einer Meldung, die dem Betreiber hilft."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_claims(
    *,
    team_id: str,
    services_id: str,
    issued_at: int,
    lifetime_seconds: int,
) -> dict[str, str | int]:
    """Baut die JWT-Payload nach Apples Vorgabe.

    ``iss`` ist die Team-ID (das Secret gehoert dem Developer-Team), ``sub`` die
    Services-ID — dieselbe, die als ``client_id`` verwendet wird — und ``aud``
    ist immer der Apple-Validierungsserver.
    """
    if lifetime_seconds <= 0:
        raise AppleSecretError("--lifetime-seconds muss positiv sein.")
    if lifetime_seconds > APPLE_MAX_LIFETIME_SECONDS:
        raise AppleSecretError(
            f"Apple lehnt Laufzeiten ueber {APPLE_MAX_LIFETIME_SECONDS} s "
            f"(sechs Monate) ab — angefragt: {lifetime_seconds} s."
        )
    return {
        "iss": team_id,
        "iat": issued_at,
        "exp": issued_at + lifetime_seconds,
        "aud": APPLE_AUDIENCE,
        "sub": services_id,
    }


def sign_client_secret(
    *,
    private_key_pem: bytes,
    key_id: str,
    claims: dict[str, str | int],
) -> str:
    """Signiert die Claims als ES256-JWT mit dem ``.p8``-Schluessel.

    Die Imports liegen bewusst in der Funktion: das Modul soll sich auch ohne
    installierte ``cryptography`` importieren (und auf Claims-Ebene testen)
    lassen.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.utils import int_to_bytes

    key = load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise AppleSecretError(
            "Der Schluessel ist kein EC-Schluessel. Apple gibt fuer Sign in with "
            "Apple einen P-256-Schluessel aus (`.p8`, beginnt mit "
            "'-----BEGIN PRIVATE KEY-----')."
        )

    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}."
        f"{_b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    )

    # ES256 braucht die Signatur als r||s (je 32 Byte), nicht als DER —
    # `cryptography` liefert DER, deshalb die Umwandlung.
    der_signature = key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_signature)
    raw_signature = int_to_bytes(r, 32) + int_to_bytes(s, 32)

    return f"{signing_input}.{_b64url(raw_signature)}"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erzeugt GOTRUE_EXTERNAL_APPLE_SECRET (ES256-JWT) aus dem .p8-Key.",
    )
    parser.add_argument(
        "--team-id",
        required=True,
        help="10-stellige Team-ID (Apple-Portal oben rechts bzw. Membership-Seite).",
    )
    parser.add_argument(
        "--key-id",
        required=True,
        help="10-stellige Key-ID des Sign-in-with-Apple-Keys (steht im Dateinamen "
        "AuthKey_<KEY_ID>.p8).",
    )
    parser.add_argument(
        "--services-id",
        required=True,
        help="Services-ID, z. B. de.example.web — NICHT die App-ID. Derselbe Wert "
        "gehoert in GOTRUE_EXTERNAL_APPLE_CLIENT_ID.",
    )
    parser.add_argument(
        "--p8",
        required=True,
        type=Path,
        help="Pfad zur .p8-Datei von Apple. Sie ist nur EINMAL herunterladbar.",
    )
    parser.add_argument(
        "--lifetime-seconds",
        type=int,
        default=DEFAULT_LIFETIME_SECONDS,
        help=f"Laufzeit in Sekunden (Default {DEFAULT_LIFETIME_SECONDS} = 180 Tage, "
        f"Apple-Maximum {APPLE_MAX_LIFETIME_SECONDS}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    try:
        private_key_pem = args.p8.read_bytes()
    except OSError as exc:
        print(f"`.p8`-Datei nicht lesbar: {exc}", file=sys.stderr)
        return 1

    issued_at = int(dt.datetime.now(tz=dt.UTC).timestamp())
    try:
        claims = build_claims(
            team_id=args.team_id,
            services_id=args.services_id,
            issued_at=issued_at,
            lifetime_seconds=args.lifetime_seconds,
        )
        token = sign_client_secret(
            private_key_pem=private_key_pem,
            key_id=args.key_id,
            claims=claims,
        )
    except AppleSecretError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    expires_at = dt.datetime.fromtimestamp(int(claims["exp"]), tz=dt.UTC)
    # Ablaufdatum auf stderr, Token auf stdout: so bleibt `… > secret.txt`
    # brauchbar, ohne dass die wichtigste Information dabei verschwindet.
    print(
        "GOTRUE_EXTERNAL_APPLE_SECRET erzeugt.\n"
        f"  Gueltig bis: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
        "  DIESES DATUM IN DEN KALENDER. Laeuft das Secret ab, faellt die\n"
        "  Apple-Anmeldung still aus (Apple: invalid_client -> GoTrue: 500),\n"
        "  waehrend Google und GitHub weiterlaufen. Erneuern heisst: dieses\n"
        "  Skript erneut laufen lassen und den neuen Wert in die .env schreiben\n"
        "  — der `.p8`-Key bleibt derselbe, kein Portal-Besuch noetig.",
        file=sys.stderr,
    )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
