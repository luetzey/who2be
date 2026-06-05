"""On-Prem-Lizenz-Werkzeug: signierten Key gegen `K_pub` verifizieren (ADR-0028).

Ersetzt das entfernte rohe `who2be-set-entitlement`-CLI (G-3). Es gibt On-Prem
**keinen** Tabellen-Write mehr: Das Entitlement entsteht ausschliesslich aus dem
signierten, K_pub-verifizierten Lizenz-Key, der als Umgebungsvariable
`WHO2BE_LICENSE_KEY` vorliegt und bei jedem Start neu verifiziert wird
(Entscheidung Q2: Env-Validierung, keine Persistenz).

Dieses CLI nimmt **nur** signierte Keys ueber den Verifikationspfad an und zeigt
das resultierende Entitlement an — ein Betreiber prueft damit einen gekauften Key,
bevor er ihn als Env setzt und neu startet. Es schreibt nichts.

CLI:
    who2be-license verify [KEY]   # KEY weggelassen → WHO2BE_LICENSE_KEY aus der Env
"""

from __future__ import annotations

import argparse
import sys

from who2be_api.core.config import get_settings
from who2be_api.licensing.crypto import LicenseError, load_public_key, verify_license_token
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.license import entitlement_from_license


def _format(entitlement: Entitlement) -> str:
    features = ", ".join(sorted(entitlement.features)) or "(keine)"
    expires = entitlement.expires_at.isoformat() if entitlement.expires_at else "unbegrenzt"
    return (
        "Lizenz gueltig (Signatur ok).\n"
        f"  status:            {entitlement.status}\n"
        f"  features:          {features}\n"
        f"  expires_at:        {expires}\n"
        f"  mcp_monthly_quota: {entitlement.mcp_monthly_quota}\n"
        f"  mcp_rate_per_min:  {entitlement.mcp_rate_per_min}"
    )


def verify_key(key: str) -> Entitlement:
    """Verifiziert den Key gegen den hinterlegten `K_pub`. Wirft `LicenseError`.

    Refuse-by-default: ohne hinterlegten `K_pub` oder bei ungueltiger Signatur
    schlaegt die Pruefung fehl — es wird nie ein unverifizierter Payload akzeptiert.
    """
    key = key.strip()
    if not key:
        raise LicenseError("Kein Lizenz-Key angegeben (Argument oder WHO2BE_LICENSE_KEY).")
    public_key = load_public_key()
    if public_key is None:
        raise LicenseError(
            "Kein K_pub hinterlegt (licensing/keys/signing_key.pub) — Verifikation nicht moeglich."
        )
    payload = verify_license_token(key, public_key)
    return entitlement_from_license(payload)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="who2be-license",
        description="Verifiziert einen signierten On-Prem-Lizenz-Key gegen K_pub.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify", help="Signierten Lizenz-Key gegen K_pub pruefen.")
    verify.add_argument(
        "key",
        nargs="?",
        default=None,
        help="Lizenz-Key; weggelassen → WHO2BE_LICENSE_KEY aus der Umgebung.",
    )
    return parser.parse_args(argv)


def cli() -> None:
    """Console-Entrypoint fuer `who2be-license`."""
    args = _parse_args()
    key = args.key if args.key is not None else get_settings().license_key
    try:
        entitlement = verify_key(key)
    except LicenseError as exc:
        print(f"Lizenz ungueltig: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(_format(entitlement))


if __name__ == "__main__":
    cli()
