"""Kanonische UUID-Form fuer Agent-Resource-Identitaeten (Issue #404).

Der MCP-Resource-Server (`.../a/{uuid}`-Pfad, `apps/mcp/agent_path.py`) und der
OAuth-Authorization-Server (RFC-8707-`resource`-Parameter,
`apps/api/services/oauth_service.py`) muessen fuer dieselbe Agent-UUID
dieselbe Strenge durchsetzen: eine Resource-URL IST die Resource-Identitaet —
mehrere Schreibweisen derselben UUID waeren mehrere Identitaeten (mehrere
advertisierte PRM-Resourcen, mehrere Connector-„Identitaeten" fuer denselben
Agenten, u. a. eine Umgehung der Duplikat-Erkennung von Clients). Deshalb
bewusst NICHT `uuid.UUID(...)`: das akzeptiert zusaetzlich geschweifte Klammern
(`{...}`), das `urn:uuid:`-Prefix und Formen ohne Bindestriche. Kanonisch ist
ausschliesslich die 8-4-4-4-12-Hex-Form MIT Bindestrichen.

`AGENT_UUID_PATTERN` ist das rohe (unverankerte) Muster zum Einbetten in
groessere Regexe (z. B. Pfad-Routen); `AGENT_UUID_RE` die verankerte Variante
fuer den Volltreffer-Test eines einzelnen Strings; `is_canonical_agent_uuid`
der Bequemlichkeits-Wrapper darum.
"""

import re

#: Rohes (unverankertes) Muster — zum Einbetten in andere Regexe.
AGENT_UUID_PATTERN = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

#: Verankerte Variante fuer den Volltreffer-Test eines einzelnen Strings.
AGENT_UUID_RE = re.compile(rf"^{AGENT_UUID_PATTERN}$")


def is_canonical_agent_uuid(value: str) -> bool:
    """`True`, wenn `value` eine UUID in kanonischer 8-4-4-4-12-Hex-Form ist."""
    return AGENT_UUID_RE.match(value) is not None
