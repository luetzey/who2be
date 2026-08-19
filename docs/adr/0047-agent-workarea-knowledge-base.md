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

## Nachtrag 2026-08-16 (Security-Review Phase 2, Wellen 3–7)

Der zweite Review (Commits `73fe887..6a8638e`) betraf die Subsysteme
Tabellen-Store, Zugriffslog und Promote. Die tragenden Entscheidungen:

- **Freies Agenten-SQL ist ein untrusted Input, auch read-only (H1–H3).**
  Die Engine-Garantie „kann nichts schreiben" war korrekt, aber sie sagt
  nichts über Kosten. Der Query-Pfad bekommt deshalb drei harte Grenzen:
  ein Zeitbudget je Query (`set_progress_handler`,
  `WHO2BE_TABLESTORE_QUERY_TIMEOUT_MS`, Default 5000 ms — eine
  `WITH RECURSIVE`-Endlosschleife blockierte sonst dauerhaft einen
  `to_thread`-Worker), eine Zell-Obergrenze (`SQLITE_LIMIT_LENGTH`, 1 MB) und
  ein Byte-Budget über das gesamte Result-Set (2 MB). `describe` läuft auf
  derselben Connection und erbt alle drei.
- **Funktions-Allowlist statt pauschalem `SQLITE_FUNCTION`-OK (H3).** Der
  Authorizer ignorierte `arg2` und erlaubte damit *jede* eingebaute Funktion —
  darunter `fts3_tokenizer`, das rohe C-Pointer liest und schreibt
  (verifiziert). Jetzt entscheidet eine Namens-Allowlist; `cast` steht bewusst
  nicht darin (es ist ein Opcode, keine Funktion), Window-Funktionen sehr wohl
  (sie laufen als `SQLITE_FUNCTION`, ohne sie bräche legitime Analytik).
  `printf`/`format` bleiben erlaubt, weil die Zell-Obergrenze ihren
  DoS-Vektor entschärft.
- **Timeout ohne neuen `ProblemReason` (H1).** Die Taxonomie ist geschlossen
  und beschreibt Berechtigungs-/Zustandsgründe; ein gerissenes Zeitbudget ist
  keiner davon (`query_not_readonly` wäre sachlich falsch — die Query *war*
  erlaubt). Statt Vokabular zu erfinden, das kein Agent verzweigen muss, geht
  der Fall den generischen Domain-Exception-Weg (Muster `TableQueryInvalid`):
  408 mit sprechendem `detail`. Die Größen-Grenzen dagegen fallen unter das
  bestehende `ingest_too_large` (413) — dieselbe Schutzfamilie wie der
  Append-Cap.
- **Compliance-Attribution ist nicht Agenten-Sache (H4).** `model_provider`/
  `model_name` sind die Grundlage der Frage „welche Daten gingen an welchen
  Anbieter". Ein agent-gebundener Token darf sie nicht setzen (403
  `missing_capability`, Muster `memory_service._require_human`) — sonst
  fälscht ein Agent seine eigene Zuordnung. Zusätzlich snapshottet
  `agent_access_log` die Config **zum Zugriffszeitpunkt** (Migration 0080,
  analog `sensitivity_at_access`); der Join auf die aktuelle Config wäre sonst
  durch eine spätere Umstellung rückwirkend fälschbar. Der `audit_log`-Eintrag
  trägt jetzt zusätzlich die `agent_id` des Aufrufers — `actor_id` ist im
  Token-Pfad der Besitzer, nicht die handelnde Maschine.
  Das Agent-UPDATE bleibt im Übrigen agent-fähig: es komplett zu sperren
  bräche den verwalteten Builder-Pfad (MCP `update_agent`), ohne die Lücke
  enger zu schließen als das Feld-Gate.
- **Append-only gilt auch gegen FK-Cascade (H5).** Migration 0079 hing
  `agent_access_log.agent_id` mit `ON DELETE CASCADE` an `agent` — der Cascade
  läuft mit Owner-Rechten, der Grant-Entzug (nur SELECT/INSERT für
  `who2be_app`) greift dort nicht: ein normaler API-Delete räumte das
  Protokoll mit ab. 0080 stellt auf `NO ACTION` um. Gewollte Konsequenz: ein
  Agent mit protokollierten Zugriffen ist **nicht löschbar** (409, Hinweis auf
  den Retention-Pfad; Stilllegen heißt `disabled`). Der Purge-Job löscht die
  Zeilen als Owner explizit vor der Org-CASCADE — der eine legitime Löschpfad.
  Das Agent-Löschen ist zudem Menschen vorbehalten und respektiert jetzt auch
  `agent_read_restrict`.
- **Ungebundene Maschinen-Tokens sind auf WorkArea/KB gesperrt (M1).** Die
  Scope-Regeln kennen zwei Fälle: Mensch (unbeschränkt ab editor) und Agent
  (Grant-gescoped). Ein `w2b_`-Token ohne `agent_id` fiel in den
  Menschen-Zweig — voller Lesezugriff auf alle Areas inklusive fremder
  privater, und weil das Zugriffslog an `agent_id` hängt, ohne jede Spur. Die
  Alternative (loggen mit nullable `agent_id`) hätte den Bezug zerstört, den
  die Auswertung braucht. Gesperrt wird als Router-Dependency in `main.py`,
  damit auch künftige Routen dieser Router sie erben.
- **Kleineres:** best-effort-Logging zählt verschluckte Fehler
  (`failed_log_writes()`) statt sie nur zu warnen (M2); `save_query_result`
  prüft das Schreib-Rate-Limit **vor** der Query nicht-konsumierend
  (`peek_write_rate`, M3) und verbraucht den Slot weiterhin nur im
  Artifact-Create; server-komponiertes Markdown entschärft Titel, SQL-Fence
  und Zellinhalte (M4), der CSV-Export präfixiert Formel-Zellen (L5, nur
  `str`-Werte — negative Zahlen bleiben Zahlen); die Timeline beantwortet
  fehlende Grants wie fehlende Tabellen mit 404 (L1) und deckelt die Zahl der
  Quellen (L2); der Promote schreibt `status_history.changed_by = user_id` und
  die Agent-Identität in die Note (L3, die Spalte gehört dem
  User-Identitätsraum) und kürzt den Slug-Stamm (L4, sonst wird ein langer
  Titel zum 500er).

## Nachtrag 2026-08-19 — die Zell-Obergrenze fehlte im Schreibpfad

Die drei harten Grenzen oben sichern den **Query**-Pfad; `_connect_rw` setzt
kein `SQLITE_LIMIT_LENGTH` (der Server schreibt, er unterliegt dem Limit
nicht). `_validate_rows` prüfte Spalten, Skalare, NOT-NULL und `occurred_at`
— Größe nicht. Damit nahm `insert_rows` eine Zelle über 1 MB an. Gemessen:

```
Schreiben ohne Limit: OK, 2 MB liegen in der Tabelle
Lesen (ro-Connection): DataError SQLITE_TOOBIG  string or blob too big
COUNT(*): 1
```

Die Folge ist nicht „ein Fehler an der falschen Stelle", sondern eine
Tabelle, die nach dem Import kaputt ist: die Zeile steht drin, aber **jedes**
`SELECT` auf die Spalte bricht ab; nur `count(*)` läuft noch. Ein Agent
konnte sich sein eigenes Material unlesbar machen, ohne dass ihm der Import
etwas meldete.

**Entscheidung:** `_validate_rows` prüft jede String-Zelle gegen dieselbe
Konstante `MAX_CELL_BYTES` (UTF-8-Bytes, wie `SQLITE_LIMIT_LENGTH` zählt) und
lehnt mit 422 ab, **bevor** geschrieben wird. Eine Quelle für die Grenze, aus
dem Store importiert — keine zweite Zahl im Service.

## Nachtrag 2026-08-19 — Exporte aus der WorkArea (Tabellen + Notizen)

Zwei neue Lese-Endpoints (ADR-0032-Muster: `attachment`, `response_model=None`,
`write_limit` als Rate-Limit, Lesen für Viewer offen, kein MCP-Tool):
`GET /wa-tables/{id}/export?format=csv|xlsx` und
`GET /wa-artifacts/{id}/export?format=markdown|html`. Drei Entscheidungen sind
tragend genug für diesen ADR statt nur für DECISIONS.md.

**(a) Der HTML-Export ist die sanktionierte Ausnahme von der Rohtext-Regel der
Web-UI.** Die WorkArea-UI rendert Artifact-Inhalte grundsätzlich als Rohtext,
nie als interpretiertes Markdown/HTML (`features/workarea/lib/blocks.ts`,
`KbNodeDetailPage.tsx`) — kein `dangerouslySetInnerHTML` im gesamten
`apps/web/src`-Baum, weil ein Client-seitiger Markdown→HTML-Renderer eine neue
Abhängigkeit UND eine Injektionsfläche für genau die Inhalte wäre, die aus
Agenten-Hand und Fremd-Ingest kommen und damit am wenigsten vertrauenswürdig
sind. Der HTML-Export tut trotzdem genau das: Markdown → HTML. Das bricht die
Regel nicht, weil keine der drei Bedingungen greift, die sie begründet
haben:
- **Serverseitig, nicht im Browser der App** — kein neuer Client-Renderer,
  keine neue Angriffsfläche IM App-Origin. Die Konfiguration ist wörtlich
  dieselbe wie `agent_render_service` (`MarkdownIt("commonmark", {"html":
  False, "breaks": True})`) — bereits geprüft, zweite Verwendung statt
  zweiter Definition.
- **`html: False` escapet rohes HTML im Quell-Markdown**, statt es
  durchzureichen — ein eingebettetes `<script>` aus Ingest-Material landet als
  Text im Export, nicht als ausführbarer Tag.
- **Immer `attachment`, nie inline** — der Export wird nie als Seite DIESER
  Origin ausgeliefert, kann also nie App-Session/Cookies erreichen. Der
  Mensch öffnet eine heruntergeladene Datei lokal, nicht eine Ansicht der
  App.
- **Meta-CSP im Dokument selbst** (`default-src 'none'; style-src
  'unsafe-inline'; img-src data:`) plus `no-referrer` deckt genau den Fall,
  den die Origin-Trennung offen lässt: öffnet der Mensch die Datei von der
  Platte (`file://`), gilt die Caddy-CSP der API dort nicht — ein
  Tracking-Pixel oder ein Fremdquellen-Bild aus dem Ingest-Material würde
  sonst beim Öffnen laden (Security-Review 2026-08-19, L-1).

**(b) Der XLSX-Formel-Guard ist keine zweite Definition der CSV-Entschärfung.**
`render_table_xlsx` (`wa_render.py`) leitet jede String-Zelle durch `csv_cell`
— dieselbe Funktion, dieselbe `CSV_FORMULA_PREFIXES`-Konstante, die den
CSV-Export gegen OWASP CSV Injection (Nachtrag 2026-08-16, L5) absichert.
Der Angriffspfad ist identisch: Fremdquellen landen über Ingest in einer
Tabelle, der Export trägt eine Formel-Zelle in die Datei eines Menschen,
Excel/Sheets führt sie beim Öffnen aus. Eine zweite Präfix-Liste in
`_xlsx_cell` hätte genau die Fehlerklasse riskiert, gegen die dieses ADR
mehrfach vorgeht — eine Entschärfung, zwei Definitionen, die auseinanderlaufen
können.

**(c) Schreibpfad-Regel erweitert: XML-illegale Steuerzeichen → 422.**
Derselbe Grundsatz wie beim Zell-Cap-Nachtrag oben (2026-08-19): wo Lese- und
Schreibpfad verschiedene Grenzen kennen, gilt die strengere beim Schreiben.
openpyxl verweigert die C0-Steuerzeichen außer Tab/LF/CR
(`IllegalCharacterError`) — SQLite und CSV nehmen sie klaglos an. Ohne
Vorab-Prüfung hätte eine einzige solche Alt-Zeile den XLSX-Export einer
Tabelle dauerhaft zum 500er gemacht, während CSV weiter funktioniert (von
außen beobachtbar, also gezielt herbeiführbar). `_validate_cell_text`
(`wa_tables.py`) prüft deshalb jede String-Zelle beim Schreiben gegen dieselbe
Zeichenmenge, die openpyxl beim Export ablehnt, und lehnt mit 422 ab, bevor
sie in die Tabelle gelangt; `_xlsx_cell` strippt zusätzlich als zweite Linie
für Bestandsdaten, die vor dieser Prüfung geschrieben wurden.

**Die fünf Review-Findings (alle behoben, Tests je Finding):**
- **M-1** — XLSX-Rendering blockierte den Event-Loop (~2 s beim vollen
  Result-Budget) → `asyncio.to_thread` + `write_limit` auf beiden Export-Routen.
- **M-2** — XML-illegale Steuerzeichen → 422 im Schreibpfad (s. (c) oben) +
  Strip im Renderer als zweite Linie.
- **M-3** — Frontmatter-Injection über `source_system`/`source_url`
  (Fremdsystem-Felder ohne Pattern-Constraint) → `_yaml_scalar` schickt jeden
  Wert durch `single_line`, ein roher Zeilenumbruch kann die
  Frontmatter-Struktur nicht mehr aufbrechen.
- **L-1** — Meta-CSP + `no-referrer` im HTML-Export (s. (a) oben).
- **L-2** — Formel-Guard prüfte nur das erste Zeichen; Google Sheets trimmt
  beim CSV-Import führenden Whitespace vor der Auswertung, ein ` =1+1` hätte
  den Guard umgangen. Geprüft wird jetzt auf einer getrimmten Kopie,
  präfixiert wird der Originalwert; `\n` ergänzt die Präfix-Liste.

**Info-Befund I-1 (nicht umgesetzt, bewusst offene Grenze):** Der
Tabellen-Export liefert bis zu `EXPORT_ROW_LIMIT` (10 000) Zeilen für EINEN
`agent_access_log`-Eintrag bzw. eine Kontingent-Einheit im Rate-Limit — das
erfasste Volumen unterzeichnet damit systematisch, wie viele Zeilen ein
Zugriff tatsächlich bewegt hat. Für ein Compliance-Zählwerk auf
Zugriffs-Ebene (nicht Zeilen-Ebene) ist das tolerierbar; für eine künftige
Volumen-genaue Auswertung nicht.
