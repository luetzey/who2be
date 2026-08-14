# ADR-0047 — Agent WorkArea + Knowledge Base (Umbrella)

- Status: Akzeptiert
- Datum: 2026-08-13
- Kontext: Umbrella-ADR zum Vorhaben „Agent WorkArea + Knowledge Base";
  vollständiger Plan inkl. Datenmodell, API-/MCP-Schnitt und Arbeitspaketen:
  `.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md`
  (User-Entscheidungen 1–7 vom 2026-08-13, siehe DECISIONS.md).
- Bezug: ADR-0005 (MCP = reiner HTTP-Client), ADR-0021 (Block-Anker
  `<id>#<block_id>`), ADR-0030 (MCP-Write-Tools), ADR-0038
  (Kurationsprinzip), ADR-0039 (feinkörnige Agent-Schreibrechte),
  ADR-0042 (Tool-Sichtbarkeits-SSoT), ADR-0048 (Blob-Storage),
  ADR-0049 (Tabellen-Store)

## Kontext

Agenten haben in Who2Be keinen Arbeitsort: Das Resource-Aggregat
(draft/review/active, 409 bei bestehendem Draft) ist für kuratiertes Wissen
richtig, für hochfrequentes Agenten-Schreiben aber ein Dauerkonflikt. Zudem
fehlt eine verknüpfte, belegpflichtige Wissensschicht — Aussagen ohne Herkunft
und Kanten ohne Beleg sind in einer AgentDB wertlos.

Dieses Vorhaben führt zwei neue, **unversionierte** Subsysteme ein:

- **WorkArea** — Rohmaterial der Agenten (docs/tables/blobs), lockfrei bzw.
  optimistisch (rev-basiert), pro Area isoliert.
- **Knowledge Base (KB)** — kuratierte Aussagen (`kb_node`) mit getypten
  Kanten (`kb_edge`) und serverseitiger Belegpflicht.

**Abgrenzung zu Resources:** Am Resource-Aggregat ändert sich **nichts**. Die
einzige Brücke ist der explizite Übergang `promote_artifact` → Resource-Draft
(Delegation an den bestehenden `ResourceService.create`, Provenance als
`status_history`-Note); ein Promote erzeugt nie direkt `active`. WorkArea/KB
sind *Kontext-Speicher für Agenten*, kein zweiter Content-Stamm.

## Optionen

### O1 — Verortung des Agenten-Arbeitsorts

- **A (gewählt): Eigene unversionierte Subsysteme neben dem
  Resource-Aggregat.** Lockfreies Append bzw. optimistisches `rev`-Patch
  passt zu hochfrequentem Agenten-Schreiben; Promote bleibt die einzige,
  explizite Brücke ins kuratierte Aggregat.
- **B: Resource-Aggregat erweitern (Agent-Drafts).** Verworfen — der
  Status-Workflow (409 bei bestehendem Draft) ist genau der Dauerkonflikt;
  jede Aufweichung schwächt die Kurations-Garantien des Aggregats.
- **C: Externes System (Wiki/CMS/Dateiablage) anbinden.** Verworfen — bricht
  Workspace-Tenancy, RLS und die Belegpflicht; Who2Be soll die
  Kontext-Schicht selbst tragen (User-Entscheidung 2: bestehender Stack).

### O2 — Doc-Format (Plan-Entscheidung 3.3)

- **A (gewählt): Block-Liste mit Markdown-Inhalt.** `wa_artifact.content` =
  JSONB-Liste `[{block_id (8-stellig, serverseitig vergeben), kind
  heading|paragraph|code|list, level?, md}]`. API/MCP nimmt **Markdown** an,
  der Server splittet deterministisch; `read` liefert Markdown mit
  Anker-Annotation. Anker-Sprache = ADR-0021 (`<artifact_id>#<block_id>`) →
  Suchtreffer sind direkt `read(id, anchor)`-fähig.
- **B: Volles BlockNote-JSON als Autorenformat.** Verworfen — agent-feindlich
  (Modelle schreiben schlecht valides Editor-JSON), Payload-Last.
- **C: Purer Markdown-Text.** Verworfen — Anker-Stabilität über Edits ist
  prinzipiell ungelöst (Zeilen-/Offset-Anker verrutschen).

Schreibsemantik: `append` = atomares `content || $blocks, rev+1` (lockfrei);
`patch` = `WHERE rev = $expected_rev`, 0 Zeilen → 409 `rev_conflict`
(aktuelle rev im detail). Promote nutzt einen kleinen deterministischen
Block→BlockNote-Konverter.

### O3 — Area-Grants + KB-Sichtbarkeit (Plan-Entscheidung 3.5)

- **A (gewählt): Materialisierte Grants + `kb_node_source_area`.**
  `work_area_grant(area_id, agent_id, level read|write)`; die private Area
  wird bei erstem Zugriff auto-angelegt inkl. materialisierter
  Owner-Grant-Row (uniforme Filter-SQL). `kb_node_source_area` wird bei
  `create_node` aus content_ref/source_ref aufgelöst und bei
  `derived_from`-Kanten monoton ge-UNION-t (Parent-Menge ist schon
  transitiv; Kanten im MVP nicht löschbar → nie Re-Berechnung).
- **B: Rekursive CTE zur Lesezeit.** Verworfen — Kosten am heißesten Pfad
  (jeder KB-Read/Search).
- **C: Agent-ID-Snapshot am Node.** Verworfen — materialisiert mutable
  Grants statt stabiler Areas; Grant-Änderungen liefen ins Leere.

Lesbarkeit: Ein Agent muss ALLE Quell-Areas eines Nodes lesen dürfen
(NOT-EXISTS-Join **in der SQL-WHERE**, nie Post-Processing); leere
Schnittmenge → nur Menschen. Menschen: `editor`+ liest alles (auch private
Agent-Areas — „privat" heißt privat gegenüber anderen **Agenten**,
User-Entscheidung 5), Viewer sehen nur shared Areas. Neuer Helper
`core/workarea_scope.py` (`readable_area_ids`/`writable_area_ids`/
`ensure_area_access` → 403 `area_forbidden`; fehlender Read-Grant → 404
`not_found`, kein Existenz-Leak). `whoami` bekommt das Feld
`work_areas: [{id, name, scope, level}]`.

### O4 — Lauf-Protokoll (Plan-Entscheidung 3.6, User-Entscheidung 6)

- **A (gewählt): Auto-Zugriffslog + Modell-Config am Agenten.**
  `agent_access_log` append-only, geschrieben in den Read-/Write-Services
  für agent-gebundene Tokens, dedupliziert per
  `UNIQUE (agent_id, ref_kind, ref_id, operation, access_date)` +
  `ON CONFLICT DO NOTHING`; `sensitivity_at_access` snapshottet der Server.
  `agent.model_provider`/`model_name` (nullable text) pflegt der Mensch über
  den bestehenden Agent-Update-Pfad; jede Änderung schreibt `audit_log`. Die
  Betreiber-Query („welche Elemente gingen je an einen externen Anbieter")
  wird in `docs/compliance/` dokumentiert.
- **B: `record_run`-Selbstauskunfts-Tool.** Verworfen — Vollständigkeit
  hinge an Agenten-Disziplin; ein vergessener Call = Lücke im Protokoll.
- **C: Session-Lauf-Kontext im MCP-Server.** Verworfen — Zustand im
  MCP-Server bricht ADR-0005 (reiner HTTP-Client).

**Dokumentierte Grenze:** Who2Be ist kein Runtime-Host — die LLM-Aufrufe
passieren in externen MCP-Clients. Das Modell gilt daher **pro
Agent-Konfiguration, nicht pro Einzelaufruf**; das Protokoll belegt „Element X
ging an einen Agenten, der laut Konfiguration auf Modell Y läuft", nicht den
konkreten Inferenz-Call.

### O5 — MCP-Schnitt (Plan-Entscheidung 3.2)

- **A (gewählt): Hybrid.** Bestand bleibt in `server.py`; neue Domains als
  Registrierungs-Module `apps/mcp/src/who2be_mcp/tools/{workarea,kb,tables}.py`
  mit `register(mcp)`, Client-Methoden in `clients/{workarea,kb,tables}.py`.
  Voraussetzung für datei-disjunkte parallele Arbeitspakete.
- **B: Alles weiter in `server.py`.** Verworfen — Wellen-Konflikt (jedes
  parallele WP editiert dieselbe 1600-LOC-Datei).
- **C: Voll-Refactoring des Bestands in Module.** Verworfen — Risiko ohne
  Feature-Nutzen.

Dazu ein neuer Drift-Guard `apps/mcp/tests/test_tool_payload_budget.py`:
tools/list-JSON-Bytes gegen ein fixes Budget (Baseline messen, ×1,45),
Docstring-Cap ≤ 1100 Zeichen/Tool.

## Entscheidung

Wir bauen WorkArea + KB als unversionierte Subsysteme im bestehenden Stack
(apps/api + apps/mcp + packages/models, Workspace-Tenancy, dieselbe
Postgres-DB), mit den oben gewählten Optionen O1A–O5A. Tragende Regeln:

1. **Belegpflicht (KB):** Jeder `kb_node` trägt `source_ref` NOT NULL
   (`sha256:<h> | url:<u> | artifact:<uuid>[#block]`). Jede `kb_edge`
   verlangt **mindestens einen Evidence-Anker pro Seite**
   (`kb_edge_evidence`, geprüft im Service in derselben Transaktion — kein
   Teilzustand); unauflösbare Anker → 422 `anchor_unresolvable`.
2. **Tier-Regeln:** `tier verified|derived|hypothesis`.
   `update_node(tier='derived')` von hypothesis verlangt
   `additional_source_ref` mit anderem `source_ref_kind`; derived→verified
   per Update immer 422 `tier_upgrade_forbidden` (Heben auf verified ist
   P2-UI-Thema, menschliche Kuration).
3. **Korrelations-Disziplin:** `co_occurs_with`-Kanten verlangen
   `co_query/co_n/co_from/co_to`; n < 20 → 422 `correlation_underpowered`
   (tatsächliches n im detail; DB-CHECK als Backstop). Aus
   Gleichzeitigkeits-Evidence entsteht ausschließlich `co_occurs_with` —
   die Timeline persistiert **nie** eine Kante aus bloßer Gleichzeitigkeit.
4. **Zeitachse:** `occurred_at` + `occurred_precision (day|minute|unknown)`
   sind Pflicht auf Artifacts und Nodes; kein Server-Fallback auf `now()`
   (Ausweg: `precision=unknown`).
5. **Capabilities & Gates:** Neue Capabilities `workarea_write`, `kb_write`,
   `kb_edge_write` in der `AgentToolPolicy` (jsonb, keine Migration;
   `is_within`-Anti-Eskalation erweitert); Gates laufen serverseitig
   (`require_capability` + `ensure_area_access` + `require_write_rate`),
   Read-Scoping als SQL-Prädikat vor dem Ranking (ADR-0037-Linie).
6. **Getrennte Suchen:** `search_workarea` und `search_kb` als zwei Tools
   („nie beide" strukturell erzwungen); eigener Chunk-Index `wa_chunk` —
   `content_chunk` wird **nicht** erweitert.

## Konsequenzen

- Migrationen 0073–0079 (`work_area`/`work_area_grant`, `wa_artifact`,
  `wa_blob`, `wa_chunk`, `kb_node`/`kb_edge`/`kb_edge_evidence`/
  `kb_node_source_area`/`kb_conflict`, `wa_table`/`wa_category_rule`/
  `wa_source_convention`, `agent_access_log` + Agent-Modell-Felder) — alle
  mit `workspace_id NOT NULL` + RLS `tenant_isolation` (Muster 0066/0070).
- 13 neue ProblemReasons (u. a. `rev_conflict`, `evidence_missing`,
  `anchor_unresolvable`, `tier_upgrade_forbidden`,
  `correlation_underpowered`, `area_forbidden`, `query_not_readonly`,
  `blobstore_unconfigured`) — vollständig in WP1, damit `main.py` konfliktfrei
  bleibt.
- 7 neue Router (work_areas, wa_artifacts, wa_ingest, wa_search, kb,
  wa_tables, wa_timeline) + whoami-Erweiterung; 23 neue MCP-Tools
  (58 → 81), jedes mit Eintrag in `MCP_TOOL_REQUIREMENTS` (ADR-0042) und
  `resolvers/tools.py::_TOOLS`.
- Die P1-Schemafelder (`ttl_expires_at`, `status live|stale`,
  `derivation_depth`, `kb_conflict`) werden **jetzt** angelegt (Conflict
  brauchen Kategorisierung und Korrelation bereits), die P1-Logik selbst
  nicht.
- Ingest-Pipeline synchron und teilzustand-frei (SSRF-Guard, pypdf/bs4,
  SHA-256-Dedup, eine Postgres-Transaktion); Details ADR-0048.
- Umsetzung in 20 WPs / 7 datei-disjunkten Wellen; `security-reviewer` nach
  Welle 2 und 5 (CLAUDE.md-Pflicht für externe Inputs/MCP-Tools).

## Bewusst nicht entschieden / Ausblick

- **Nicht-Ziele (bindend):** kein CMS/Wiki, kein Runtime-Host, kein CRDT
  (rev-basierte Optimistik reicht dem Agenten-Schreibmuster), kein
  Cross-Workspace-Zugriff. PROJECT.md wird im Doku-WP entsprechend gerahmt.
- **Spec-P1 außerhalb dieses Plans:** TTL/Verfall (H), Challenger (I),
  Drift (J) — nur die Schemafelder liegen schon.
- **Spec-P2:** UI, Graph-Visualisierung, semantische Suche über
  WorkArea/KB (ADR-0046-Infrastruktur läge bereit).
- **Heben derived→verified** bleibt der P2-UI (menschliche Kuration)
  vorbehalten.

## Nachtrag 2026-08-13 (Security-Review Wellen 1–2)

- **Sourcelose KB-Nodes area-beschränkter Aufrufer (H2):** Ein Node, dessen
  Belege keine lesbare Artifact-Area treffen (`url:`/`sha256:` ohne
  Artifact-Bezug), erbt beim Anlegen durch einen agent-gebundenen Token die
  **private Area des Agenten** als Quell-Area. Ohne diese Regel wäre der Node
  quell-frei und damit workspace-weit sichtbar — ein Exfiltrationskanal aus
  privaten Areas. Menschen (editor+) legen weiterhin quell-freie,
  workspace-sichtbare kuratierte Aussagen an; Agenten teilen breiter, indem
  sie Artifact-Belege aus shared Areas zitieren.
- **Node-Updates (M5):** Sichtbarkeit ist keine Schreib-Erlaubnis — Agenten
  ändern nur selbst erstellte Nodes, `verified`-Nodes ändern ausschließlich
  Menschen (editor+).
- **Rollen-Gate (H1):** Alle WorkArea-/KB-Schreibpfade prüfen wie die übrigen
  Write-Services zuerst `require_role(editor)` (Token-gepinnte Rolle), dann
  Capability + Rate — ein bewusst lesend angelegter Agent-Token (viewer)
  schreibt nie.
