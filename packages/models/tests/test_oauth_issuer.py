"""Kanonische Issuer-Identifier-Form — geteilt zwischen API und MCP-Server."""

from who2be_models import canonical_issuer


def test_trailing_slash_is_stripped() -> None:
    # Der Fall aus der Praxis: eine reine Origin. Pydantics `AnyHttpUrl` haengt
    # ihr beim Validieren ein "/" an — der Issuer-Identifier darf das nicht.
    assert canonical_issuer("https://api.example.de/") == "https://api.example.de"
    assert canonical_issuer("https://api.example.de") == "https://api.example.de"


def test_path_survives_without_its_trailing_slash() -> None:
    # Ein Issuer MIT Pfad ist erlaubt (RFC 8414 §3.1) — nur der Slash faellt.
    assert canonical_issuer("https://example.de/auth/") == "https://example.de/auth"
    assert canonical_issuer("https://example.de/auth") == "https://example.de/auth"


def test_repeated_slashes_and_whitespace_collapse() -> None:
    # Aus `.env`-Dateien kommen gern Leerzeichen und doppelte Slashes.
    assert canonical_issuer("  https://api.example.de//  ") == "https://api.example.de"


def test_is_idempotent() -> None:
    once = canonical_issuer("https://api.example.de/")
    assert canonical_issuer(once) == once
