"""Tests fuer ``scripts/gen_apple_client_secret.py``.

Das Skript erzeugt Signing-Material, das ein Betreiber blind in seine `.env`
kopiert. Ein falsch gebautes JWT faellt ihm erst auf, wenn die Apple-Anmeldung
in Produktion scheitert — und dann mit einer generischen 500, die die Ursache
nicht nennt. Deshalb pruefen diese Tests nicht, dass „irgendein Token"
herauskommt, sondern die **Struktur gegen Apples Vorgabe**: ES256, `kid` im
Header, `iss`/`sub`/`aud` richtig belegt, Signatur mit dem echten Schluessel
verifizierbar, und die Sechs-Monats-Grenze eingehalten.

Der Schluessel wird im Test frisch erzeugt (P-256, wie Apple ihn ausgibt) —
kein Fixture-Material im Repo.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gen_apple_client_secret import (  # noqa: E402
    APPLE_AUDIENCE,
    APPLE_MAX_LIFETIME_SECONDS,
    AppleSecretError,
    build_claims,
    main,
    sign_client_secret,
)

TEAM_ID = "ABCDE12345"
KEY_ID = "FGHIJ67890"
SERVICES_ID = "de.example.web"
ISSUED_AT = 1_800_000_000


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


@pytest.fixture
def p8_key() -> bytes:
    """Ein frischer P-256-Schluessel im PKCS#8-PEM-Format — wie Apples `.p8`."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class TestBuildClaims:
    def test_belegt_die_claims_nach_apples_vorgabe(self) -> None:
        claims = build_claims(
            team_id=TEAM_ID,
            services_id=SERVICES_ID,
            issued_at=ISSUED_AT,
            lifetime_seconds=3600,
        )

        # iss = Team-ID (das Secret gehoert dem Team), sub = Services-ID
        # (dieselbe, die als client_id geht), aud = Apples Validierungsserver.
        assert claims["iss"] == TEAM_ID
        assert claims["sub"] == SERVICES_ID
        assert claims["aud"] == APPLE_AUDIENCE
        assert claims["iat"] == ISSUED_AT
        assert claims["exp"] == ISSUED_AT + 3600

    def test_lehnt_laufzeit_ueber_sechs_monaten_ab(self) -> None:
        # Apple: "It's an error to request an expiration time more than
        # 15777000 seconds (six months) in the future." Ein Token darueber
        # wuerde Apple bei JEDEM Login mit invalid_client abweisen — besser
        # hier scheitern als in Produktion.
        with pytest.raises(AppleSecretError, match="sechs Monate"):
            build_claims(
                team_id=TEAM_ID,
                services_id=SERVICES_ID,
                issued_at=ISSUED_AT,
                lifetime_seconds=APPLE_MAX_LIFETIME_SECONDS + 1,
            )

    def test_genau_am_apple_maximum_ist_noch_erlaubt(self) -> None:
        claims = build_claims(
            team_id=TEAM_ID,
            services_id=SERVICES_ID,
            issued_at=ISSUED_AT,
            lifetime_seconds=APPLE_MAX_LIFETIME_SECONDS,
        )

        assert claims["exp"] == ISSUED_AT + APPLE_MAX_LIFETIME_SECONDS

    @pytest.mark.parametrize("lifetime", [0, -1])
    def test_lehnt_nicht_positive_laufzeit_ab(self, lifetime: int) -> None:
        with pytest.raises(AppleSecretError, match="positiv"):
            build_claims(
                team_id=TEAM_ID,
                services_id=SERVICES_ID,
                issued_at=ISSUED_AT,
                lifetime_seconds=lifetime,
            )


class TestSignClientSecret:
    def test_header_traegt_es256_und_die_key_id(self, p8_key: bytes) -> None:
        # Ohne `kid` kann Apple nicht wissen, mit welchem der (bis zu mehreren)
        # Keys signiert wurde, und weist das Secret ab.
        token = sign_client_secret(
            private_key_pem=p8_key,
            key_id=KEY_ID,
            claims=build_claims(
                team_id=TEAM_ID,
                services_id=SERVICES_ID,
                issued_at=ISSUED_AT,
                lifetime_seconds=3600,
            ),
        )

        header = json.loads(_b64url_decode(token.split(".")[0]))
        assert header["alg"] == "ES256"
        assert header["kid"] == KEY_ID

    def test_signatur_ist_mit_dem_oeffentlichen_schluessel_verifizierbar(
        self, p8_key: bytes
    ) -> None:
        """Der eigentliche Prueffall: ein echter ECDSA-Verify.

        Apple prueft die Signatur gegen den hochgeladenen Key. Nur ein Verify
        belegt, dass die DER->r||s-Umwandlung im Skript stimmt — ein
        fehlerhaftes Padding erzeugt ein Token, das strukturell korrekt
        aussieht und trotzdem jeden Login scheitern laesst.
        """
        token = sign_client_secret(
            private_key_pem=p8_key,
            key_id=KEY_ID,
            claims=build_claims(
                team_id=TEAM_ID,
                services_id=SERVICES_ID,
                issued_at=ISSUED_AT,
                lifetime_seconds=3600,
            ),
        )
        header_b64, payload_b64, signature_b64 = token.split(".")

        raw_signature = _b64url_decode(signature_b64)
        assert len(raw_signature) == 64, "ES256 verlangt r||s mit je 32 Byte"

        public_key = serialization.load_pem_private_key(p8_key, password=None)
        assert isinstance(public_key, ec.EllipticCurvePrivateKey)
        r = int.from_bytes(raw_signature[:32], "big")
        s = int.from_bytes(raw_signature[32:], "big")
        # Wirft InvalidSignature, wenn das Skript falsch signiert.
        public_key.public_key().verify(
            encode_dss_signature(r, s),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            ec.ECDSA(hashes.SHA256()),
        )

    def test_lehnt_einen_nicht_ec_schluessel_mit_klarer_meldung_ab(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        rsa_pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with pytest.raises(AppleSecretError, match="kein EC-Schluessel"):
            sign_client_secret(
                private_key_pem=rsa_pem,
                key_id=KEY_ID,
                claims=build_claims(
                    team_id=TEAM_ID,
                    services_id=SERVICES_ID,
                    issued_at=ISSUED_AT,
                    lifetime_seconds=3600,
                ),
            )


class TestCli:
    def test_gibt_das_token_auf_stdout_und_das_ablaufdatum_auf_stderr(
        self, tmp_path: Path, p8_key: bytes, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Die Trennung ist Absicht: `… > secret.txt` soll nur das Token
        # enthalten, das Ablaufdatum aber trotzdem sichtbar bleiben.
        key_file = tmp_path / "AuthKey_FGHIJ67890.p8"
        key_file.write_bytes(p8_key)

        exit_code = main(
            [
                "--team-id",
                TEAM_ID,
                "--key-id",
                KEY_ID,
                "--services-id",
                SERVICES_ID,
                "--p8",
                str(key_file),
            ]
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        token = captured.out.strip()
        assert len(token.split(".")) == 3
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        assert payload["sub"] == SERVICES_ID
        assert "Gueltig bis" in captured.err
        assert "KALENDER" in captured.err

    def test_fehlende_p8_datei_ist_ein_fehler_mit_meldung(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = main(
            [
                "--team-id",
                TEAM_ID,
                "--key-id",
                KEY_ID,
                "--services-id",
                SERVICES_ID,
                "--p8",
                str(tmp_path / "gibtsnicht.p8"),
            ]
        )

        assert exit_code == 1
        assert "nicht lesbar" in capsys.readouterr().err

    def test_zu_lange_laufzeit_bricht_mit_exit_1(
        self, tmp_path: Path, p8_key: bytes, capsys: pytest.CaptureFixture[str]
    ) -> None:
        key_file = tmp_path / "AuthKey_FGHIJ67890.p8"
        key_file.write_bytes(p8_key)

        exit_code = main(
            [
                "--team-id",
                TEAM_ID,
                "--key-id",
                KEY_ID,
                "--services-id",
                SERVICES_ID,
                "--p8",
                str(key_file),
                "--lifetime-seconds",
                str(APPLE_MAX_LIFETIME_SECONDS + 1),
            ]
        )

        assert exit_code == 1
        assert "sechs Monate" in capsys.readouterr().err
