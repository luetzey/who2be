"""Issuer-Identifier — geteilt zwischen API und MCP-Server."""

import pytest
from pydantic import AnyHttpUrl

from who2be_models import canonical_resource, issuer_base, issuer_identifier

# --- issuer_identifier -------------------------------------------------------
# Der Fall aus der Praxis: eine reine Origin. Jeder URL-Parser haengt ihr beim
# Parsen ein "/" an — der Client tut das mit dem Wert aus der PRM, bevor er ihn
# gegen den rohen `issuer` der AS-Metadaten haelt. Der advertisierte Identifier
# muss den Slash deshalb SELBST tragen; ohne ihn bricht der Login mit
# "issuer mismatch" ab (s. Modul-Docstring von `who2be_models.oauth_issuer`).

_ORIGIN = "https://api.example.de/"


@pytest.mark.parametrize(
    "spelling",
    [
        "https://api.example.de",
        "https://api.example.de/",
        "  https://api.example.de//  ",
        "https://API.Example.DE",
        "https://api.example.de:443",
        "HTTPS://api.example.de",
    ],
)
def test_origin_spellings_collapse_to_the_url_normal_form(spelling: str) -> None:
    assert issuer_identifier(spelling) == _ORIGIN


def test_path_survives_without_its_trailing_slash() -> None:
    # Ein Issuer MIT Pfad ist erlaubt (RFC 8414 §3.1) und bekommt von keinem
    # Parser einen Slash angehaengt — hier bleibt es bei der slash-freien Form.
    assert issuer_identifier("https://example.de/auth/") == "https://example.de/auth"
    assert issuer_identifier("https://example.de/auth") == "https://example.de/auth"


def test_is_idempotent() -> None:
    once = issuer_identifier("https://api.example.de")
    assert issuer_identifier(once) == once


@pytest.mark.parametrize(
    "configured",
    [
        "https://api.example.de",
        "https://api.example.de/",
        "https://example.de/auth",
        "http://localhost:8000",
        "http://127.0.0.1:8765",
        "https://[::1]:8443",
    ],
)
def test_identifier_is_a_fixed_point_of_the_client_parser(configured: str) -> None:
    """Die Eigenschaft, an der der Fix aus #523 gescheitert ist.

    Der Client legt den PRM-Wert in einem URL-Typ ab, bevor er vergleicht
    (`mcp/client/auth/oauth2.py`: `str(metadata.authorization_servers[0])`,
    Feldtyp `AnyHttpUrl`). Was wir advertisieren, muss diesen Parser also
    unveraendert ueberstehen — sonst vergleicht der Client unsere Form mit
    seiner und findet einen Unterschied, den die beiden Dokumente nie hatten.
    Faellt dieser Test, hat ein Parser seine Normalform geaendert: dann ist
    `issuer_identifier` nachzuziehen, nicht der Test.
    """
    identifier = issuer_identifier(configured)
    assert str(AnyHttpUrl(identifier)) == identifier


@pytest.mark.parametrize(
    "broken",
    [
        "nicht-parsebar",
        "ftp://api.example.de",
        "https://evil@api.example.de",
        "https://api.example.de:99999",
        "https:///kein-host",
    ],
)
def test_unusable_config_comes_back_only_trimmed(broken: str) -> None:
    # Fail-closed: nichts umschreiben, was wir nicht sicher zerlegen koennen.
    # Ein so konfigurierter Issuer ist kaputt — das soll er auch bleiben,
    # statt zu einer zweiten, stillschweigend erfundenen Identitaet zu werden.
    assert issuer_identifier(f"  {broken}  ") == broken


# --- issuer_base -------------------------------------------------------------


def test_base_is_the_identifier_without_the_trailing_slash() -> None:
    assert issuer_base("https://api.example.de/") == "https://api.example.de"
    assert issuer_base("https://example.de/auth/") == "https://example.de/auth"


@pytest.mark.parametrize("spelling", ["https://api.example.de", "https://api.example.de/"])
def test_endpoints_built_on_the_base_have_exactly_one_slash(spelling: str) -> None:
    assert f"{issuer_base(spelling)}/oauth/token" == "https://api.example.de/oauth/token"


# --- canonical_resource ------------------------------------------------------
# Die drei Schreibweisen, an denen der Connector-Login in der Praxis scheiterte
# (byte-exakter RFC-8707-Vergleich, ADR-0036 hatte sie als Risiko notiert).

_RESOURCE = "https://mcp.example.de/mcp"


@pytest.mark.parametrize(
    "variant",
    [
        "https://mcp.example.de/mcp",
        "https://mcp.example.de/mcp/",  # Trailing Slash
        "https://MCP.Example.DE/mcp",  # Host-Gross-/Kleinschreibung
        "https://mcp.example.de:443/mcp",  # expliziter Default-Port
        "HTTPS://MCP.EXAMPLE.DE:443/mcp/",  # alle drei zusammen
        "  https://mcp.example.de/mcp  ",  # Whitespace aus Copy-Paste
    ],
)
def test_equivalent_spellings_collapse(variant: str) -> None:
    assert canonical_resource(variant) == canonical_resource(_RESOURCE)


@pytest.mark.parametrize(
    "other",
    [
        "https://evil.example/mcp",  # fremder Host
        "https://mcp.example.de.evil.test/mcp",  # Suffix-Anhang
        "https://evil@mcp.example.de/mcp",  # Userinfo darf nicht wegfallen
        "http://mcp.example.de/mcp",  # anderes Schema
        "https://mcp.example.de:8443/mcp",  # anderer Port
        "https://mcp.example.de/MCP",  # Pfad bleibt case-sensitiv
        "https://mcp.example.de/mcp//",  # nur EIN Slash faellt
        "https://mcp.example.de/mcp/../mcp",  # Punkt-Segmente bleiben stehen
        "https://mcp.example.de/mcp#frag",  # Fragment bleibt Unterschied
    ],
)
def test_genuinely_different_resources_stay_different(other: str) -> None:
    assert canonical_resource(other) != canonical_resource(_RESOURCE)


def test_userinfo_is_not_stripped() -> None:
    # Wuerde die Userinfo wegfallen, waere `https://evil@host/x` dasselbe wie
    # `https://host/x` — die Host-Pruefung liesse sich damit aushebeln. Die
    # Funktion gibt solche URLs unveraendert (nur getrimmt) zurueck.
    assert canonical_resource("https://evil@mcp.example.de/mcp") == (
        "https://evil@mcp.example.de/mcp"
    )


@pytest.mark.parametrize(
    "unparsable",
    ["", "not-a-url", "https://", "ftp://mcp.example.de/mcp", "https://mcp.example.de:99999/mcp"],
)
def test_unparsable_input_fails_closed(unparsable: str) -> None:
    # Fail-closed: kein Rateversuch, nur getrimmt zurueck — der Vergleich gegen
    # die konfigurierte Resource schlaegt damit fehl.
    assert canonical_resource(unparsable) == unparsable.strip()


def test_query_survives_untouched() -> None:
    # Der Agent-Hint `?agent=<uuid>` haengt an der Resource und darf weder
    # umsortiert noch umkodiert werden.
    aid = "11111111-2222-3333-4444-555555555555"
    assert canonical_resource(f"https://MCP.example.de:443/mcp?agent={aid}") == (
        f"https://mcp.example.de/mcp?agent={aid}"
    )


def test_canonical_resource_is_idempotent() -> None:
    once = canonical_resource("HTTPS://MCP.EXAMPLE.DE:443/mcp/")
    assert canonical_resource(once) == once


@pytest.mark.parametrize(
    "hidden",
    [
        "https://mcp.example.de/m\tcp",  # urlsplit wuerde das TAB still entfernen
        "ht\ttps://mcp.example.de/mcp",  # auch im Schema
        "https://mcp.example.de/m\ncp",
        "https://mcp.example.de/m\rcp",
        "https://mcp.exa\tmple.de/mcp",  # und im Host
        "https://mcp.example.de/m\xa0cp",  # NBSP im Inneren
        "https://mcp.example.de/m\x00cp",  # NUL
        "https://mcp.example.de/m\x7fcp",  # DEL
    ],
)
def test_interior_control_characters_fail_closed(hidden: str) -> None:
    """`urlsplit` entfernt `\\t`/`\\r`/`\\n` still aus der GANZEN URL (bpo-43882).

    Ohne Riegel waere `…/a/1111\\t1111-…` ein gueltiger Agent-Hint — eine zweite
    Schreibweise derselben UUID, die `who2be_models.agent_uuid` gerade
    verhindern soll und die der Resource-Server nie advertised.
    """
    assert canonical_resource(hidden) != canonical_resource(_RESOURCE)
    assert canonical_resource(hidden) == hidden.strip()


def test_edge_whitespace_stays_tolerated() -> None:
    # Gegenstueck: an den RAENDERN ist Whitespace ein Copy-Paste-Artefakt und
    # wird bewusst geschluckt (Regel 1) — nur das Innere faellt fail-closed.
    assert canonical_resource("\xa0 https://mcp.example.de/mcp \r\n") == _RESOURCE


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ("https://[::1]/mcp", "https://[::1]/mcp"),
        ("https://[::1]:443/mcp", "https://[::1]/mcp"),
        ("https://[::1]:8443/mcp", "https://[::1]:8443/mcp"),
        ("https://[2001:DB8::1]/mcp", "https://[2001:db8::1]/mcp"),
    ],
)
def test_ipv6_literals_keep_their_brackets(literal: str, expected: str) -> None:
    # `parsed.hostname` gibt IPv6 ohne Klammern zurueck — ohne Korrektur waere
    # das Ergebnis `https://::1/mcp`, also keine round-trippbare URL mehr.
    assert canonical_resource(literal) == expected


@pytest.mark.parametrize(
    "port_spelling",
    [
        "https://mcp.example.de:443/mcp",
        "https://mcp.example.de:0443/mcp",
        "https://mcp.example.de:/mcp",
    ],
)
def test_default_port_spellings_collapse(port_spelling: str) -> None:
    # Fuehrende Null und leerer Port sind dieselbe Angabe (Docstring-Regel 3).
    assert canonical_resource(port_spelling) == _RESOURCE


def test_empty_fragment_collapses_but_real_one_does_not() -> None:
    assert canonical_resource(f"{_RESOURCE}#") == _RESOURCE
    assert canonical_resource(f"{_RESOURCE}#frag") != _RESOURCE
