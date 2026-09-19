"""Kanonische Issuer-Identifier-Form fuer den OAuth-Remote-MCP-Connector.

Der Authorization-Server (API, `routers/oauth.py`) und der Resource-Server
(MCP, `auth.py` + `agent_path.py`) nennen denselben Issuer in zwei getrennten
Metadaten-Dokumenten:

- RFC 9728 (PRM des MCP-Servers): `authorization_servers[*]`
- RFC 8414 (AS-Metadaten der API): `issuer`

Der LLM-Client liest den ersten Wert, holt damit das zweite Dokument und
vergleicht dessen `issuer` per **String-Gleichheit** (RFC 8414 §3.3: der
zurueckgegebene `issuer` MUSS identisch mit dem Identifier sein, aus dem die
Metadaten-URL gebaut wurde). Zwei Schreibweisen derselben URL sind damit zwei
Issuer — der Connector-Login bricht mit "issuer mismatch" ab.

Deshalb ist die Kanonisierung hier zentral und wird von BEIDEN Seiten
importiert, statt als `rstrip` an zwei Orten zu leben: die Uebereinstimmung
wird erzwungen, nicht nachtraeglich hergestellt. Gleiches Muster und gleicher
Grund wie `who2be_models.agent_uuid` — auch dort einigen sich API und MCP auf
eine Stringform, weil ein Dritter sie gegeneinander haelt.

Die Falle, aus der das entstanden ist: Pydantics `AnyHttpUrl` — der Feldtyp
der SDK-Metadaten-Modelle — haengt einer URL OHNE Pfad beim Validieren ein
`/` an (`https://api.example.de` wird zu `https://api.example.de/`). Ein
Issuer, der durch ein solches Modell gelaufen ist, ist also nicht mehr der
konfigurierte String.
"""

from urllib.parse import urlsplit, urlunsplit

#: Default-Ports je Schema (RFC 3986 §6.2.3) — expliziter Default ist redundant.
_DEFAULT_PORTS = {"http": 80, "https": 443}


def canonical_issuer(url: str) -> str:
    """Kanonische Form eines Issuer-Identifiers: getrimmt, ohne Trailing Slash.

    Ein Pfad bleibt erhalten (RFC 8414 §3.1 erlaubt Issuer mit Pfad), nur die
    abschliessenden Slashes fallen weg. Die Funktion ist idempotent.
    """
    return url.strip().rstrip("/")


def canonical_resource(url: str) -> str:
    """Vergleichsform einer RFC-8707-`resource`-URL.

    Der Client schickt `resource` im Authorize-Request; der Authorization-Server
    haelt sie gegen die konfigurierte MCP-Resource. Der Vergleich ist ein
    String-Vergleich — und genau daran scheitert er in der Praxis, weil Clients
    (und Menschen, die eine Connector-URL abtippen) dieselbe Resource in
    mehreren Schreibweisen nennen. Diese Funktion bringt **beide Seiten** auf
    eine Form, bevor verglichen wird. Sie ist idempotent.

    Eingeebnet werden genau drei Unterschiede:

    1. **Schema und Host in Kleinschreibung** — RFC 3986 §3.2.2: Host und Schema
       sind case-insensitiv. Der **Pfad bleibt** case-sensitiv.
    2. **Expliziter Default-Port faellt weg** (`:443` bei https, `:80` bei http)
       — RFC 3986 §6.2.3.
    3. **Ein einzelner abschliessender Slash faellt weg.** Das ist bewusst
       *keine* RFC-Aequivalenz (`/mcp` und `/mcp/` sind verschiedene URIs),
       sondern eine begruendete Lockerung: MCP-Clients senden beide Formen fuer
       denselben Endpunkt, und ein `invalid_target` dafuer ist fuer den Nutzer
       nicht diagnostizierbar. Es faellt **genau einer** weg — `/mcp//` bleibt
       verschieden von `/mcp`.

    Bewusst NICHT eingeebnet, weil es echte Unterschiede verwischen oder ein
    Umschreiben erfordern wuerde, das selbst zur Luecke wird: Prozent-Kodierung,
    Punkt-Segmente (`/..`), Query-Reihenfolge, Pfad-Gross-/Kleinschreibung,
    IDN/Punycode.

    Fail-closed: Was nicht sicher zerlegbar ist — nicht parsebar, ohne Host,
    oder mit Userinfo (`https://evil@host/…` wuerde sonst auf `https://host/…`
    kollabieren und die Host-Pruefung aushebeln) — kommt nur getrimmt zurueck
    und faellt damit im Vergleich durch.
    """
    trimmed = url.strip()
    try:
        parsed = urlsplit(trimmed)
    except ValueError:
        return trimmed
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return trimmed
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError:  # kaputter Port
        return trimmed
    if not host:
        return trimmed
    if port is not None and port != _DEFAULT_PORTS[parsed.scheme]:
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = parsed.path
    if path.endswith("/") and not path.endswith("//"):
        path = path[:-1]
    return urlunsplit((parsed.scheme, netloc, path, parsed.query, parsed.fragment))
