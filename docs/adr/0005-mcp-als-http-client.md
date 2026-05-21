# ADR-0005 — MCP-Server als HTTP-Client der REST-API

- Status: Akzeptiert
- Datum: 2026-05-21
- Kontext: Who2Be MVP (PROJ-19)

## Kontext

Der MCP-Server liefert Agenten Lese-Zugriff (`get_persona`, `list_playbooks`,
`fetch_playbook`). Zu entscheiden ist, wie er an die Daten kommt. Die
Repo-Konvention (CLAUDE.md) legt fest: `packages/models` ist die **einzige**
geteilte Abhaengigkeit zwischen API und MCP.

## Optionen

- **A — MCP ruft die REST-API ueber HTTP:** MCP ist ein duenner Client,
  Auth/Logik/Versionierung liegen nur in der API.
- **B — MCP teilt eine Repository-/Service-Schicht mit der API:** Direkter
  DB-Zugriff aus dem MCP-Prozess. Verletzt die "models-only"-Konvention und
  dupliziert Auth-/Owner-Logik.
- **C — MCP mit eigener, schlanker Read-DB-Schicht:** Eigener Lesepfad zur DB,
  aber zweite Stelle fuer SQL und Owner-Pruefung.

## Entscheidung

Option A. Der MCP-Server spricht ueber einen `httpx`-Client gegen die API und
sendet den Agenten-API-Token (`WHO2BE_API_TOKEN`). Damit bleibt die API der
einzige DB-Eigentuemer und die einzige Stelle fuer Auth, Owner-Pruefung und
Versionierung; die Repo-Konvention "models einzige geteilte Abhaengigkeit"
ist eingehalten.

## Konsequenzen

- Geschaeftslogik existiert genau einmal — keine Drift zwischen API und MCP.
- Der MCP-Server bleibt ein duenner Auslieferungs-Adapter (analog zur Web-UI).
- Im Betrieb muss die API erreichbar sein, damit der MCP-Server funktioniert —
  auf einer gemeinsamen Hetzner-Instanz unkritisch.
- Ein zusaetzlicher netzinterner HTTP-Hop pro MCP-Aufruf — fuer die erwartete
  Last vernachlaessigbar.
