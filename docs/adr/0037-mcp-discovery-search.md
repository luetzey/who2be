# ADR-0037 — MCP Discovery & Search (Volltext jetzt, Vektor-bereit)

- Status: Accepted (umgesetzt: MCP-Tool `search` + `GET /search`, Volltext;
  Proposed → Accepted 2026-07-08)
- Datum: 2026-06-27
- Kontext: AI-native-Optimierung des MCP-Toolsets; Agenten muessen Inhalte
  *finden*, nicht nur per UUID/Name abrufen.
- Bezug: ADR-0005 (MCP als HTTP-Client), ADR-0021 (MCP-Resource-Tools),
  ADR-0030 (MCP-Write-Tools), `.claude/plan/2026-06-04_embedding-mode-resource-compose.md`
  (vorhandene Embedding-Infrastruktur)

## Kontext

Heute kann ein Agent Kernelemente nur ueber `list_*` (komplette Liste, optional
Tag-/Trigger-Filter, exakter Treffer) und `get`/`fetch` (per UUID/Name) abrufen.
Eine inhaltliche Suche („finde Playbooks zum Thema Reklamation") fehlt — der
Agent muss Volllisten laden und selbst durchsuchen. Das skaliert nicht und ist
das Gegenteil von AI-native: der teure Kontext des Agenten wird mit irrelevanten
Listen gefuellt.

## Entscheidung

Wir fuehren **eine Such-Schnittstelle in zwei Stufen hinter einem stabilen
Tool-Vertrag** ein.

- **Neues MCP-Tool `search`** (duenner Adapter, ADR-0005/0030):
  `search(query: str, types: list[Literal["persona","playbook","resource"]] | None,
  tags: list[str] | None, limit: int = 20)` → rangsortierte Treffer
  (`SearchHit{type, id, name, snippet, score}`). Spiegelt 1:1 einen neuen
  REST-Endpunkt `GET /v1/workspaces/{ws}/search`.
- **Stufe A (dieser ADR, sofort):** serverseitige **Postgres-Volltextsuche**
  (`tsvector` ueber Titel + Tags + gerenderten Body der **aktiven** Version,
  GIN-Index pro Element-Typ). `ts_rank` liefert die Reihenfolge. Kein neuer
  Infra-Baustein.
- **Stufe B (spaeter, separater Plan):** **semantische Suche** ueber die bereits
  vorgesehene Embedding-Infrastruktur (pgvector). Derselbe Tool-Vertrag, ein
  zusaetzlicher `mode: "text" | "semantic" | "hybrid"`-Parameter — der Agent
  merkt von der Umstellung nichts.

## Rechte & Sichtbarkeit

- **Nur `status='active'`** — wie alle MCP-Reads (ADR-0030 §Persistence-Injection).
  Draft/Review sind nicht suchbar; kein Leak unfertiger Inhalte.
- **Read-Scope greift** (ADR-0023 / Per-Agent-Policy): Ergebnisse werden gegen
  `visible_playbook_ids()`/`visible_resource_ids()` gefiltert. Ein Agent mit
  `assigned`-Scope findet nur in seinem zugewiesenen Set; `none` blendet den Typ
  aus. Die Filterung passiert serverseitig **vor** dem Ranking, nicht im Adapter.

## Konsequenzen

- Neuer Router `routers/search.py` + `SearchService`/`SearchRepository`; ein
  geteiltes `SearchHit`-Model in `packages/models`.
- Migration: `tsvector`-Spalten (generated columns) + GIN-Indizes auf den
  Content-Tabellen, gepflegt pro aktiver Version.
- MCP: `search`-Tool + 403/422-Mapping wie gehabt; `tools-overview`-Platzhalter
  (System-Prompt) listet `search` nur, wenn der Agent mindestens einen
  Read-Scope ≠ `none` hat.
- Stufe B ist bewusst nicht praejudiziert: der Tool-Vertrag ist vektor-bereit,
  die Entscheidung pgvector-Schema bleibt einem Folge-ADR vorbehalten.
