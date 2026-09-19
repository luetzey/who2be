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


def canonical_issuer(url: str) -> str:
    """Kanonische Form eines Issuer-Identifiers: getrimmt, ohne Trailing Slash.

    Ein Pfad bleibt erhalten (RFC 8414 §3.1 erlaubt Issuer mit Pfad), nur die
    abschliessenden Slashes fallen weg. Die Funktion ist idempotent.
    """
    return url.strip().rstrip("/")
