"""Issuer-Identifier fuer den OAuth-Remote-MCP-Connector.

Der Authorization-Server (API, `routers/oauth.py`) und der Resource-Server
(MCP, `auth.py` + `agent_path.py`) nennen denselben Issuer in zwei getrennten
Metadaten-Dokumenten:

- RFC 9728 (PRM des MCP-Servers): `authorization_servers[*]`
- RFC 8414 (AS-Metadaten der API): `issuer`

Der Client liest den ersten Wert, holt damit das zweite Dokument und vergleicht
dessen `issuer` per **String-Gleichheit** (RFC 8414 §3.3). Zwei Schreibweisen
derselben URL sind damit zwei Issuer — der Connector-Login bricht ab mit
"Authorization server metadata issuer mismatch".

**Welche Schreibweise gewinnt, entscheidet nicht dieses Repo.** Der Client legt
den Wert aus der PRM in einem URL-Typ ab, bevor er vergleicht — im MCP-Python-
SDK woertlich `str(metadata.authorization_servers[0])` mit
`authorization_servers: list[AnyHttpUrl]`
(`mcp/client/auth/oauth2.py`), im TypeScript-SDK `new URL(...)`. **Beide
Parser haengen einer URL ohne Pfad ein `/` an** und lassen einen Pfad in Ruhe:

    AnyHttpUrl("https://api.example.de")   -> "https://api.example.de/"
    new URL("https://api.example.de").href -> "https://api.example.de/"

Der Slash entsteht also im Client und ist von hier aus nicht wegzukonfigurieren.
Ein slash-freier Identifier ist deshalb KEIN Fixpunkt: der Client haelt seine
geparste Form gegen den rohen `issuer` aus dem JSON und findet einen
Unterschied, den beide Dokumente nie hatten. Genau das war der Fehlschluss in
#523 — dort wurde slash-frei kanonisiert und der Login blieb kaputt.

`issuer_identifier()` liefert deshalb die **URL-Normalform**: genau den String,
den ein URL-Parser aus sich selbst wieder erzeugt. Damit stimmt der Vergleich
in beiden Richtungen — egal ob der Client die PRM parst, den `issuer` parst,
beide parst oder keinen. `test_oauth_issuer.py` haelt diese Fixpunkt-Eigenschaft
gegen `AnyHttpUrl` fest; bricht ein Parser sie kuenftig, faellt der Test.

`issuer_base()` ist dieselbe Normalform ohne den abschliessenden Slash — sie
traegt die Endpunkt-URLs der AS-Metadaten (`{base}/oauth/token`), damit dort
kein Doppel-Slash entsteht. Beide Funktionen rechnen aus derselben Quelle, sie
koennen also nicht auseinanderlaufen.

Dass die Normalisierung hier liegt und von BEIDEN Seiten importiert wird, statt
als `rstrip` an zwei Orten zu leben, bleibt richtig: die Uebereinstimmung wird
erzwungen, nicht nachtraeglich hergestellt. Gleiches Muster und gleicher Grund
wie `who2be_models.agent_uuid` — auch dort einigen sich API und MCP auf eine
Stringform, weil ein Dritter sie gegeneinander haelt.
"""

from urllib.parse import urlsplit, urlunsplit

#: Default-Ports je Schema (RFC 3986 §6.2.3) — expliziter Default ist redundant.
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _has_invisible_chars(url: str) -> bool:
    """Steuerzeichen oder inneres Whitespace — beides muss VOR `urlsplit` raus.

    `urlsplit` entfernt `\t`, `\r` und `\n` still aus der GESAMTEN URL
    (CPython bpo-43882). Danach sind sie unsichtbar weg, und zwei verschiedene
    Strings — auch zwei verschiedene **Hosts** — sehen gleich aus. Beide
    Funktionen dieses Moduls fahren denselben Riegel, damit sie nicht
    auseinanderlaufen; die Raender hat `strip()` beim Aufrufer schon geputzt.
    """
    return any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F for char in url)


def issuer_identifier(url: str) -> str:
    """Der Issuer-Identifier, wie ihn BEIDE Metadaten-Dokumente tragen.

    Ergebnis ist die Form, die ein URL-Parser (Pydantic `AnyHttpUrl`, WHATWG
    `URL`) unveraendert laesst — s. Modul-Docstring. Eingeebnet wird, was beide
    Parser einebnen, und nur das:

    1. Rand-Whitespace (`strip()`).
    2. Schema und Host in Kleinschreibung (RFC 3986 §3.2.2); der **Pfad bleibt**
       case-sensitiv.
    3. Default-Port (`:443` bei https, `:80` bei http) faellt weg
       (RFC 3986 §6.2.3).
    4. **Genau ein** abschliessender Slash faellt vom **Pfad** weg, und ein
       leerer Pfad wird zu `/`. Der Pfad selbst bleibt erhalten —
       RFC 8414 §3.1 erlaubt Issuer mit Pfad, und die Discovery-URL beider SDKs
       kommt damit zurecht. `/auth//` bleibt verschieden von `/auth`, wie in
       `canonical_resource`: kein URL-Parser ebnet das ein.

    Query und Fragment bleiben unangetastet — auch ein Slash am Ende davon. Ein
    Issuer mit beidem ist nach RFC 8414 §2 ungueltig; das ist ein
    Konfigurationsfehler und wird hier nicht stillschweigend weggeschrieben.

    Fail-closed wie `canonical_resource`, mit derselben Liste: nicht parsebar,
    fremdes Schema, ohne Host, kaputter Port, Userinfo und
    Steuerzeichen/inneres Whitespace kommen nur getrimmt zurueck. Letzteres ist
    nicht kosmetisch — ohne den Riegel wuerde `https://api.example.de\t.evil.com`
    auf den Host `api.example.de.evil.com` kollabieren, also auf einen anderen
    Server als den konfigurierten (`_has_invisible_chars`).
    Die Funktion ist idempotent.
    """
    trimmed = url.strip()
    if _has_invisible_chars(trimmed):
        return trimmed
    try:
        parsed = urlsplit(trimmed)
    except ValueError:
        return trimmed
    # `urlsplit` senkt das Schema bereits auf Kleinschreibung.
    if parsed.scheme not in _DEFAULT_PORTS or parsed.username or parsed.password:
        return trimmed
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError:  # kaputter Port
        return trimmed
    if not host:
        return trimmed
    # IPv6-Literale brauchen ihre Klammern zurueck (s. `canonical_resource`).
    netloc = f"[{host}]" if ":" in host else host
    if port is not None and port != _DEFAULT_PORTS[parsed.scheme]:
        netloc = f"{netloc}:{port}"
    # Nur der PFAD wird gekuerzt, und wie in `canonical_resource` genau um einen
    # Slash. Auf dem Rohstring wuerde `rstrip("/")` auch Slashes aus Query und
    # Fragment fressen und `/auth//` mit `/auth` gleichmachen — beides
    # Schreibweisen, die kein URL-Parser einebnet.
    path = parsed.path
    if path.endswith("/") and not path.endswith("//"):
        path = path[:-1]
    return urlunsplit((parsed.scheme, netloc, path or "/", parsed.query, parsed.fragment))


def issuer_base(url: str) -> str:
    """Praefix der Endpunkt-URLs in den AS-Metadaten — ohne Trailing Slash.

    `f"{issuer_base(...)}/oauth/token"` ergibt genau eine Slash-Ebene. Leitet
    sich aus `issuer_identifier()` ab, damit Identifier und Endpunkte nicht
    auseinanderlaufen koennen.
    """
    return issuer_identifier(url).rstrip("/")


def canonical_resource(url: str) -> str:
    """Vergleichsform einer RFC-8707-`resource`-URL.

    Der Client schickt `resource` im Authorize-Request; der Authorization-Server
    haelt sie gegen die konfigurierte MCP-Resource. Der Vergleich ist ein
    String-Vergleich — und genau daran scheitert er in der Praxis, weil Clients
    (und Menschen, die eine Connector-URL abtippen) dieselbe Resource in
    mehreren Schreibweisen nennen. Diese Funktion bringt **beide Seiten** auf
    eine Form, bevor verglichen wird. Sie ist idempotent.

    Eingeebnet wird genau das Folgende — die Liste ist abschliessend, und die
    Tests in `test_oauth_issuer.py` halten sie fest:

    1. **Whitespace an den Raendern** (`strip()`), inklusive Unicode-Whitespace:
       reines Copy-Paste-Artefakt.
    2. **Schema und Host in Kleinschreibung** — RFC 3986 §3.2.2: Host und Schema
       sind case-insensitiv. Der **Pfad bleibt** case-sensitiv.
    3. **Default-Port** (`:443` bei https, `:80` bei http) faellt weg, ebenso ein
       leerer (`host:`) und ein fuehrend genullter (`:0443`) — RFC 3986 §6.2.3.
    4. **Ein einzelner abschliessender Slash** faellt weg. Das ist bewusst
       *keine* RFC-Aequivalenz (`/mcp` und `/mcp/` sind verschiedene URIs),
       sondern eine begruendete Lockerung: MCP-Clients senden beide Formen fuer
       denselben Endpunkt, und ein `invalid_target` dafuer ist fuer den Nutzer
       nicht diagnostizierbar. Es faellt **genau einer** weg — `/mcp//` bleibt
       verschieden von `/mcp`.
    5. **Ein leeres Fragment** (`…/mcp#`) faellt weg; ein nicht-leeres bleibt.

    Bewusst NICHT eingeebnet, weil es echte Unterschiede verwischen oder ein
    Umschreiben erfordern wuerde, das selbst zur Luecke wird: Prozent-Kodierung,
    Punkt-Segmente (`/..`), Query-Reihenfolge, Pfad-Gross-/Kleinschreibung,
    IDN/Punycode.

    Fail-closed: Was nicht sicher zerlegbar ist, kommt nur getrimmt zurueck und
    faellt damit im Vergleich durch — nicht parsebar, fremdes Schema, ohne Host,
    kaputter Port, **Userinfo** (`https://evil@host/…` wuerde sonst auf
    `https://host/…` kollabieren und die Host-Pruefung aushebeln) und
    **Steuerzeichen/Whitespace im Inneren**. Letzteres ist keine Theorie:
    `urlsplit` entfernt `\t`, `\r` und `\n` still aus der GESAMTEN URL
    (CPython bpo-43882). Ohne diesen Riegel waere `…/a/11111111\t-2222-…` ein
    gueltiger Agent-Hint — also eine zweite Schreibweise derselben Agent-UUID,
    genau die Sorte Zweit-Identitaet, die `who2be_models.agent_uuid` verhindern
    soll und die der Resource-Server (`agent_path.parse_agent_id`, Regex auf dem
    ROHEN Pfad) nie advertised. AS und RS wuerden denselben String
    unterschiedlich lesen.
    """
    trimmed = url.strip()
    # Steuerzeichen und inneres Whitespace vor `urlsplit` abfangen — danach sind
    # sie unsichtbar weg (s. Docstring, geteilt mit `issuer_identifier`).
    if _has_invisible_chars(trimmed):
        return trimmed
    try:
        parsed = urlsplit(trimmed)
    except ValueError:
        return trimmed
    if parsed.scheme not in _DEFAULT_PORTS or parsed.username or parsed.password:
        return trimmed
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError:  # kaputter Port
        return trimmed
    if not host:
        return trimmed
    # IPv6-Literale brauchen ihre Klammern zurueck — `parsed.hostname` gibt sie
    # ohne aus, und `https://::1/mcp` waere keine round-trippbare URL mehr.
    netloc = f"[{host}]" if ":" in host else host
    if port is not None and port != _DEFAULT_PORTS[parsed.scheme]:
        netloc = f"{netloc}:{port}"
    path = parsed.path
    if path.endswith("/") and not path.endswith("//"):
        path = path[:-1]
    return urlunsplit((parsed.scheme, netloc, path, parsed.query, parsed.fragment))
