# ADR-0013 — API-Versionierung: Pfad-basiert mit SemVer-Semantik

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Plan-Review 2026-05-26

## Kontext

Alle Routen liegen unter `/v1`. Bisher gab es keine Konvention, was
nach `/v1` passiert — Breaking-Change-Politik, Deprecation-Frist und
Form (Header vs. Pfad vs. Query) waren ungeklaert. MCP-Adapter und
Web-UI sind beide Konsumenten der API; ein unkontrollierter Breaking
Change wuerde stillschweigend einen oder beide brechen.

## Optionen

- **A — Header-Versionierung** (`Accept: application/vnd.who2be.v2+json`).
  Klein im URL-Raum, aber unsichtbar in Logs/Traces und schwer zu
  parallel-deployen.
- **B — Pfad-basiert, SemVer-Major im Prefix.** Breaking Changes ziehen
  `/v2`, nicht-breaking Aenderungen bleiben in `/v1`. Beide Pfade koennen
  parallel betrieben werden, bis die Migration der Clients durch ist.
- **C — Query-Parameter-Versionierung** (`?v=2`). Sichtbar, aber
  Cache-unfreundlich und nicht-Standard.

## Entscheidung

**B — Pfad-basierte Versionierung mit SemVer-Semantik.**

- **Minor / Patch (rueckwaertskompatibel):** Add neuer optionaler Felder,
  Add neuer Endpoints, Add neuer optionaler Query-Parameter — bleiben in
  `/v1`. Keine Folgepflicht fuer Clients.
- **Major (breaking):** Renamen/Entfernen von Feldern, Aenderung von
  Pflicht-Semantik, geaenderte Auth-Vertraege — erzwingen `/v2`. `/v1`
  bleibt mindestens **6 Monate** nach Release von `/v2` produktiv (oder
  bis MCP + Web auf `/v2` umgestellt sind und im RUNBOOK abgenommen).
- **Deprecation-Vertrag:** `Deprecation`- und `Sunset`-Response-Header
  auf `/v1`, Eintrag im RUNBOOK und im OpenAPI-Description-Feld.

`X-Next-Cursor`-aehnliche Header-Ergaenzungen (siehe F-09) sind explizit
*keine* Breaking Changes und bleiben innerhalb der laufenden Major-Linie.

## Konsequenzen

- Pfad-Prefix bleibt der Single Source of Truth fuer API-Version. MCP-
  Client (`apps/mcp/src/who2be_mcp/client.py`) traegt den Prefix
  konfigurierbar (heute hartkodiert `/v1` — bei `/v2`-Release Env-Var
  ergaenzen).
- Web-Client (`apps/web/src/api/client.ts`) bekommt eine Konstante
  `API_VERSION = "v1"`, damit ein zukuenftiger Major-Bump an einer
  Stelle umgeschaltet wird.
- Im OpenAPI-Description-Block wird die SemVer-Policy verlinkt
  (`docs/adr/0013-...`).
- Solange wir bei `/v1` bleiben, ist diese ADR ein Vertrag mit der
  Zukunft, kein laufender Aufwand.
</content>
</invoke>