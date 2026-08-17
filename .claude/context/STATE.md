# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-08-16_

Ist-Zustands-Snapshot, kein Changelog. Die Umsetzungs-Historie (per-Run-Details,
Branch-Namen, DoD-Belege) lebt in `.claude/plan/*` (Status-Übersicht:
[`.claude/plan/README.md`](../plan/README.md)) und den gemergten PRs.

## Funktioniert (Ist-Zustand)

### Kern-App (Phase 1–3)

- Tenancy (`User → org_member → Organization → Workspace → Entity`), API hart
  auf `/v1/workspaces/{ws_id}/…`; Status-Workflow draft→review→active→inactive
  pro Version + Dashboard; RBAC `admin > editor > viewer` (ADR-0023) +
  Magic-Link-Invitations. Pläne:
  `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`,
  `.claude/plan/2026-05-29-1900_phase-3-ux-polish.md`.
- Resources + BlockNote-Insel (ADR-0022), Placeholder-Pills (ADR-0025),
  Composite-Playbooks/Persona-Modi/Resource-Tags (ADR-0024,
  `docs/agent-axes.md`), Content-i18n (ADR-0027), Einzel-Delete/-Export
  (ADR-0032), Account-Lifecycle + DSGVO-Purge/-Export.
- Listen-UX mit URL-Filtern (`useListFilters`/`ListFilterBar`: Status/Agent/
  Tag/Typ/Gruppierung), Playbooks- + Dashboard-Design-Refresh (Pläne
  2026-07-11/-12), MFA-Login-Step-up (`docs/mfa-admin.md`).
- Reload-sichere Deep-Links: `SessionProvider` exponiert `sessionLoaded`,
  `RequireAuth` wartet den Session-Bootstrap ab (Ladeanzeige statt sofortigem
  `/login`-Redirect) und gibt beim echten Logout die Ziel-URL als `?next=` an
  die LoginPage weiter — vorher warf jeder Reload den User aufs Dashboard.
- Dashboard-Aufmerksamkeits-Band zeigt neben offenen Entity-Reviews auch
  pending Memory-Vorschläge (ADR-0044, Link → Agents) und System-Prompt-
  Templates in Review (Link → `/system-prompts?status=review`); KPI-Felder
  `pending_memories`/`pending_system_prompts` (Plan
  `.claude/plan/2026-07-22-1650_dashboard-attention-memories-system-prompts.md`).
- Agenten-Übersicht zeigt pro Agent offene Gedächtnis-Vorschläge:
  List-Enrichment `pending_memory_count` (Batch-Aggregat, kein N+1) +
  klickbarer Aufmerksamkeits-Pill → Deep-Link `#memory` scrollt zur
  Gedächtnis-Sektion der Detail-Seite und hebt sie kurz hervor (Plan
  `.claude/plan/2026-07-24-1623_agents-pending-memory-badge.md`).
- **Sprache als durchgängiges Konzept (ADR-0045, ersetzt UI-Teil von
  ADR-0027; PR #357, Issues #348–#356):** ein Element = eine Sprache
  (`locale` auf der Identitäts-Zeile aller 5 Content-Typen, Migration 0069;
  System-Prompts erstmals mit Sprachwahl), Reads locale-agnostisch,
  `?locale=` als Listenfilter, `LocaleBadge` + Sprachfilter in der Web-UI,
  Workspace-`content_locale` bei Anlage (vorbelegt aus UI-Sprache,
  Personal-Workspace aus `preferred_locale`), automatische
  Output-Sprachanweisung im Agent-Renderer (`services/agent_language.py`),
  MCP-Tools mit locale-Metadatum + Builder-Sprach-Tagging, komplettes
  EN-Rollout-Paket (`repositories/builder_content.py` + `repositories/en/`,
  14 Sidecars) mit locale-bewusstem Seeding/Sync
  (`BUILDER_CONTENT_VERSION = 12`). Plan
  `.claude/plan/2026-07-24-1900_sprache-vertiefen-ein-element-eine-sprache.md`.

### MCP + OAuth

- MCP-HTTP-Transport (ADR-0034) + OAuth-2.1-Remote-Connector (ADR-0036,
  per-Agent-URL `?agent=<uuid>`); Refresh-Reuse reject-only statt
  Ketten-Revocation (DECISIONS 2026-07-05); OAuth-Smoke beide Editionen grün.
- **81 Tools** (58 + 23 aus WorkArea/KB/Tabellen, ADR-0047): Read + Write
  (ADR-0030), `search` + `search_content`
  (ADR-0037/0046), Versions-/
  Discovery-Tools, System-Prompt-Tools (ADR-0040), feinkörnige
  Agent-Schreibrechte inkl. Rate-Limit (ADR-0039). `tools/list` pro Agent
  policy-gefiltert (fail-open, SSoT `who2be_models.tool_requirements`,
  ADR-0042, PR #305) — neue Tools brauchen einen Mapping-Eintrag.

### Builder

- Managed Builder-Agent (Persona mit 3 Modi, 6 Playbooks, Konventions-
  Resource) + Managed-Lock, Deep-Copy-Duplizieren, Content-Start-Sync
  (`BUILDER_CONTENT_VERSION`, Stand 11 = `external_tool_write` +
  Playbook „External Tool anlegen & pflegen" + Konventions-Sektion;
  Stand 10 = Memory `suggest`/`recommended`). Befähigung + UI-Polish:
  PR #301/#302; Richtungsentscheidungen in DECISIONS 2026-07-09/-10/-11
  und 2026-07-21 (Memory-Triage/-Guard bewusst UI-only). Plan:
  `.claude/plan/2026-07-21-0810_builder-external-tool-write.md`.

### Feedback-Flywheel (ADR-0038)

- Append-only `usage_event` + `agent_feedback`, Triage
  (`feedback_resolution`), Posteingang inkl. System-Feedback
  (`report_problem`), Hard-Delete, Capability `feedback_resolve` +
  MCP-Tool `resolve_feedback`.

### Agent-Memory (ADR-0044)

- Kuratiertes Langzeitgedächtnis pro Agent: `memory_mode`
  off<read_only<suggest<auto + Freigabe-Schleuse pending→Triage→active;
  MCP `search_memory`/`list_memories`/`save_memory`, Laufzeit-Einbindung via
  `get_persona`, Placeholder-Kind `memory`; Injection-Wächter konfigurierbar
  (`memory_guard`, PR #327–#329). Pläne:
  `.claude/plan/2026-07-18-1500_agent-memory.md` + 2026-07-19-*.

### External Tools (ADR-0043)

- Versionierte Aggregate `external_tool` (instruktiv, Alias-Referenz),
  Placeholder `tool-ref` mit Fetch-Time-Expansion, 6 MCP-Tools + Web-Features
  (PR #316; Plan `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`).

### Editionen / Deploy

- Ein Codebase, zwei Build-Profile (ADR-0028/0029): `org_entitlement` als
  SSoT, On-Prem via `WHO2BE_LICENSE_KEY`, Billing build-isoliert
  (`packages/billing`, Web via `VITE_WHO2BE_EDITION`). Deploy
  `deploy/hetzner` (Caddy `api.`/`app.`/`mcp.`, `--profile mcp-http`).

### Standards / CI

- Standards-Schicht (`docs/standards/`, `AGENTS.md`, `.claude/context/`),
  FSL-1.1 + CONTRIBUTING/SECURITY (Public-Switch vorbereitet), OSS-Lizenz-
  Gates (ADR-0033), Test-Pyramide + Coverage-Ratchet (ADR-0041);
  Security-Findings Phase 1+2 alle Closed.
- Standards-Review 2026-07-08: WP-1–8 umgesetzt
  (`docs/standards-review-2026-07-08.md` §3); heutiger Lauf s. u.
- **CI-Gate seit 2026-08-16 wieder aktiv** (war seit 2026-07-19 durch
  Actions-Billing tot, GIT-2 im Standards-Review 2026-07-20). Alle fünf Jobs
  laufen: `python` · `web` · `e2e` · `compose-smoke` · `audit`. Beleg — das
  Krankheitsbild war Abbruch nach 2–6 s mit `runner_id: 0` und ohne Logs;
  jetzt echte Runner (`runner_id: 1000005113` ff.) und echte Laufzeiten
  (`python` 8 min inkl. Postgres-Service und voller pytest-Suite, `e2e`
  2:50 min mit Compose-Up + Playwright, `compose-smoke` baut zusätzlich das
  `runtime-cloud`-Image). Entscheidend: der erste Lauf (`31950241038`, PR
  #370) war **rot und zu Recht** — er fand zwei ESLint-Errors, die ein
  lokaler Lauf durchgelassen hatte. Ein Gate, das einen echten Defekt fängt,
  ist keins mehr auf dem Papier. Damit ist die lokale DoD-Ausführung wieder
  Vorstufe statt Ersatz.

### Release-Vorbereitung / Pre-Publish-Nachweis (2026-07-22)

- **Release-Audit** (Repo-Publish-Flow, Issues #338–#341): Ergebnis „noch
  nicht release-fertig" — Blocker waren npm-audit, fehlende NOTICES und der
  tote CI-Nachweis; Wellen 1–2 umgesetzt (dieser Run). Welle 3 (#341) wartete
  auf die CI-Reaktivierung — die ist seit 2026-08-16 da (s. §Standards / CI),
  der Block ist damit entsperrt.
- **Secrets-Gate bestanden:** kein Secret im Tree (nur Dev-/Test-Platzhalter
  und `${VAR}`-Injektionen); History sauber — nie `.env`/`.pem`/`.key`
  committet, gitleaks + 8 Pattern-Scans über alle Commits negativ
  (`.claude/plan/2026-05-27-2028_public-switch-github-repo.md`); **kein
  History-Rewrite nötig**.
- **npm-audit-Triage:** 3 CVEs (tar critical, undici + brace-expansion high)
  waren ausschließlich Dev-Tooling (eslint-Kette, jsdom, license-checker/
  node-gyp); `npm audit --omit=dev` war durchgehend clean → kein
  Runtime-Risiko. Per `npm audit fix` (nur Lockfile, 12 transitive Pakete)
  geschlossen; `npm audit` jetzt 0 Findings, Web-DoD danach grün
  (917 Tests, Coverage Statements 86,96 %/Branches 81,14 %).
- **Publish-Artefakte:** CODE_OF_CONDUCT.md (Contributor Covenant 2.1),
  ROADMAP.md, CHANGELOG.md, README-Ausbau, `LICENSE.md → LICENSE`,
  `THIRD-PARTY-LICENSES.md` + Generator
  (`scripts/gen_third_party_notices.sh`, OSS-1/ADR-0033).

## In Arbeit

- **Semantische Suche & Passage-Retrieval (ADR-0046)** — vollständig umgesetzt
  (Wellen 1–3).
  - *Welle 1:* `content_chunk` (Migration 0070, Schnitt an Heading-Blöcken,
    FTS-Config pro Sprache), Chunk-Aufbau im Transition-Pfad, `search_content`
    als REST + MCP-Tool (Passagen statt Aggregate), Backfill-CLI
    `who2be-retrieval-backfill`, plus zwei behobene Fehler der bestehenden Suche
    (Read-Scope hinter dem `LIMIT`; 403 auf Fremdtypen).
  - *Welle 2:* `content_vector` (Migration 0071, **fail-soft** ohne pgvector),
    asyncpg-Vektor-Codec mit dynamischer Schema-Auflösung, `EmbeddingPort` +
    lokaler fastembed-Adapter in der optionalen Dep-Gruppe `embeddings`,
    Hybrid-Ranking per RRF, `mode`-Parameter (`auto|text|semantic|hybrid`),
    Vektor-Backfill. Postgres-Images lokal/CI/Testcontainers auf
    `pgvector/pgvector:pg16`.
  - *Welle 3:* `content_vector` auf `agent_memory` (Migration 0072, fail-soft),
    `search_active` von der lexikografischen `ORDER BY`-Kaskade auf
    **RRF-Fusion über vier Zweige** umgebaut (FTS, ILIKE, Trigram, Vektor),
    semantischer Zweig im Dedup-Wächter, best-effort-Embedding im
    Laufzeit-Schreibpfad, Memory-Vektor-Backfill. Der MCP-Docstring, der seit
    ADR-0044 „semantisch" versprach, ist damit eingelöst.
  - Memory hat zwei komplementäre Testdateien: die Baseline hält fest, was der
    lexikalische Pfad kann und wo seine Grenzen liegen; `test_memory_semantic`
    belegt, dass der Vektor-Zweig genau diese Grenzen löst — ohne die
    lexikalischen Fähigkeiten zu verdrängen.
  - *Nachzug (2026-07-26, Content-Stand 14):* Der Builder weiß jetzt, was das
    Feature von ihm verlangt — neuer Abschnitt „Auffindbarkeit & Retrieval" in
    den Agent-Bau-Konventionen (Überschriften sind Chunk-Grenzen, nur aktive
    Versionen sind auffindbar, Passage vor Volltext, `mode`, Sprachgrenze) +
    semantisches Gedächtnis in der Memory-Sektion; `search_content` in Persona
    und Playbooks (DE + EN). Dazu die dabei gefundene Lücke geschlossen: Seed
    und Start-Sync schreiben aktive Versionen an `_transition` vorbei, ein
    frischer Workspace hatte deshalb **null** Passagen — beide Pfade stoßen den
    Chunk-Lauf jetzt selbst an (Seed gescopet, Start-Sync nur nach
    Content-Bump).
  - **DoD:** Python 1256 pytest / Coverage ~90 %; ruff + format-check + mypy
    grün; Web unberührt (keine Änderung unter `apps/web/`).
  - **Offen:** Kalibrierung der drei Schwellen (`_MIN_VECTOR_SIMILARITY` je
    Korpus, `_DEDUP_VECTOR_SIMILARITY`) gegen das reale Modell — der
    Modell-Download ist in der Entwicklungsumgebung per Netz-Policy gesperrt.
    Die Retrieval-Mechanik ist gegen deterministische Test-Vektoren mit
    bekannter Geometrie belegt, die Modell-Qualität nicht.
- **Standards-Review 2026-07-20** (`docs/standards-review-2026-07-20.md`,
  PR #331): Phase A mit 12 Prüf-Agenten; Phase B Wellen 1–3 umgesetzt
  (SEC-1/2/3, LIC-1, DEP-1/2/6, LIC-4, OSS-2, FE-1/10/11, Kosmetik-Sweep,
  GIT-8, Memory-Pflege). **DoD:** Python 1155 pytest / Coverage 89,74 %;
  Web 912 Vitest / Branches 81,07 %; alle Gates lokal grün.
- OAuth-Connector: E2E mit echtem Claude/ChatGPT-Client offen; TTL-Cleanup
  der OAuth-Tabellen, optionale Audience-Trennung, aal2-Consent (Phase 2).

### Agent WorkArea + Knowledge Base (ADR-0047/0048/0049) — WP1–WP20 umgesetzt

Zweite Achse neben der kuratierten Resource-Achse: **unversionierter
Arbeitsbereich** für Agenten plus **belegpflichtige Knowledge Base**. Plan
`.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md` (20 WPs in
7 Wellen), PR #367.

- **WorkArea:** `work_area` (private je Agent, auto-angelegt; shared per
  Grant — Grant-Vergabe ist Menschen-Sache), `wa_artifact` (doc/table/blob,
  `occurred_at` als Pflicht-Input ohne `now()`-Fallback, optimistische
  Nebenläufigkeit über `rev`), `wa_chunk` als **eigener** Suchindex
  (`content_chunk` bleibt unangetastet — kuratierte und arbeitende Achse
  trennen auch im Retrieval).
- **Ingest (Pipeline B):** Datei-/URL-Ingest mit 20-MB-Limit, SSRF-Schutz,
  content-addressed Blob-PUT (`blobs/{ws}/{sha256}`) vor **einer** Postgres-
  Transaktion; Doppel-Ingest dedupliziert ohne zweites Objekt.
- **BlobStore (ADR-0048):** Port + MinIO-/In-Memory-Adapter; ohne
  `WHO2BE_BLOBSTORE_*` liefern nur Ingest/Blob-Reads 503, alles andere läuft
  unverändert (gültiger Betriebsmodus).
- **Tabellen-Store (ADR-0049):** SQLite je Area, Datei = Isolationsgrenze;
  read-only als Engine-Garantie (`mode=ro` + `query_only` + Authorizer mit
  Opcode- **und** Funktions-Allowlist + Zeit-/Zell-/Result-Budgets).
  Deterministische Kategorisierung + Quellen-Konventionen; Timeline-Merge.
- **Knowledge Base:** Belegpflicht je Aussage (`source_ref`), Tier-Regeln
  (`verified`/`derived`/`hypothesis`), Kanten inkl. Korrelations-Disziplin
  (`co_occurs_with` nur mit n ≥ 20 + Zeitfenster), Konflikt-Erfassung.
- **Compliance:** `agent_access_log` (Auto-Protokoll, Modell-/Sensitivitäts-
  **Snapshot** zum Zugriffszeitpunkt, FK `NO ACTION`), Betreiber-Query in
  `docs/compliance/agent-access-log.md`; VVT V18–V20.
- **Retention (WP20):** `who2be-purge` deckt jetzt drei Speicher ab —
  `cleanup_expired_artifacts` (Area-Frist `retention_days`, Default `NULL` =
  unbegrenzt, auch privat), `cleanup_orphan_blobs` (Katalog-Zeile ohne
  Artifact **und** Objekt ohne Zeile, je > 24 h; Objekt-Sweep nur mit
  Storage-Zeitstempel) und `cleanup_deleted_area_stores` (SQLite-Dateien
  gelöschter Areas). GDPR-Export trägt Areas/Artifacts/Blob-Metadaten/
  Tabellen-Zeilen (Cap 10 000 + `truncated`)/KB/Zugriffslog.
- **MCP:** 58 → **81 Tools** (`tools/workarea.py`, `tools/tables.py`,
  `tools/kb.py`), policy-gefiltert, Payload-Budget grün.
- **Security-Reviews:** nach Welle 2 und Welle 5 je ein Durchlauf; Phase 2
  siehe eigener Abschnitt unten.
- **DoD (2026-08-16):** `ruff check` + `ruff format --check` (439 Dateien) +
  `mypy .` (439 Quellen, strict) grün; **1632 pytest gesamt, Coverage 90,98 %**
  (Gate 85 %); `apps/api/tests` allein 1152 grün.
- **Bewusst offen:**
  - *P1-Backlog:* KB-TTL-Verfall (`ttl_expires_at` wird gesetzt, aber nicht
    automatisch ausgewertet), Challenger-/Gegenbeleg-Mechanik,
    Drift-Erkennung auf Aussagen.
  - *P2-Backlog:* Web-UI für WorkArea/KB (heute API-/MCP-only),
    Graph-Visualisierung der Kanten, semantische Suche auf `wa_chunk`
    (Vektor-Zweig wie ADR-0046 auf der Resource-Achse).
  - *Manuelle Compose-Verifikation steht aus* (WP3-Punkt): `docker compose up`
    → minio healthy → Bootstrap legt Bucket an und terminiert → ohne
    Blobstore-Env Ingest = 503 → mit Env PDF-Ingest-Smoke, Objekt unter
    `blobs/{ws}/{sha}`, Doppel-Ingest ohne zweites Objekt. Braucht eine
    Umgebung mit Docker; in der Entwicklungsumgebung nicht ausführbar.
  - *Tabellen-Import kappt Zell-Breiten nicht* — s. §Bekannte Probleme.

### Security-Härtung Agent-WorkArea (2026-08-16, Phase-2-Review)

Zweiter Review-Durchlauf über Tabellen-Store, Zugriffslog und Promote
(Commits `73fe887..6a8638e`); alle Findings umgesetzt, Regressionstests in
`apps/api/tests/test_security_fixes_phase2.py`, Begründungen im
ADR-0047-Nachtrag 2026-08-16 und in DECISIONS.

- Freies Agenten-SQL hat jetzt Ressourcen-Grenzen: Zeitbudget je Query/
  describe (408), Zell-Cap 1 MB und Result-Budget 2 MB (413). Der Authorizer
  prüft SQL-Funktionen namentlich (`fts3_tokenizer` & Co. verweigert).
- Zugriffslog ist fälschungsfest: Modell-Config wird zum Zugriffszeitpunkt
  gesnapshottet (Migration 0080), agent-gebundene Tokens dürfen sie nicht
  setzen, und der FK hält gegen Cascade-Löschung (Agent-Delete mit
  Protokollzeilen → 409, Purge bleibt der Löschpfad).
- Kleineres: Rate-Limit vor der Query (`peek_write_rate`), Markdown-/
  CSV-Injektion im server-gerenderten Export, Timeline-Existenz-Orakel und
  -Quellen-Deckel, Promote-Aktor + Längen-Schnitte.

### Arbeitsbereich in der Web-UI + Builder-Rechte (2026-08-16)

Das WorkArea/KB-Feature war nach PR #367/#369 **nur über MCP erreichbar** —
die drei Betreiber-Stellschrauben lagen in der Web-UI brach. Nachgezogen:

- **Agenten-Editor:** `workarea_write`/`kb_write`/`kb_edge_write` sind
  Checkboxen im Policy-Editor; ohne sie konnte ein Betreiber einem
  Fach-Agenten den Arbeitsbereich gar nicht freischalten. Dazu eine Sektion
  „Modell-Konfiguration" (`model_provider`/`model_name`) — das Feld ist
  Menschen vorbehalten und war damit ohne UI **tot**, obwohl die
  Compliance-Auskunft des Zugriffslogs daran hängt.
- **Modell-Config ist wieder leerbar:** `AgentUpdate` hatte `min_length=1` +
  COALESCE, ein gesetzter Wert war nicht mehr zu entfernen (der Code nannte
  das selbst einen offenen Punkt). Neuer Vertrag: `''` = explizit auf NULL,
  weggelassen = unverändert; Drei-Wege-`CASE` im Repository, Audit greift.
- **Neuer Endpunkt `GET /work-areas/{area_id}/grants`** (Menschen-only,
  Viewer dürfen lesen) — der Grant-Editor braucht den Ist-Stand, es gab nur
  `PUT`/`DELETE`.
- **Lese-Ansicht `features/workarea`:** Bereiche (+ Anlage geteilter
  Bereiche), Bereichs-Detail mit Inhalten und Freigaben, Artifact-Ansicht mit
  Block-Ankern, WorkArea-Suche und Knowledge-Base-Suche/-Detail inkl.
  Beleg-Rückverweis und Fallzahl bei `co_occurs_with`.
- **Builder darf die Tools nutzen** (`BUILDER_CONTENT_VERSION` 14 → 15): rein
  policy-seitig, der Start-Sync verteilt es an Bestands-Builder. Ohne die
  Flags könnte der Builder sie wegen `is_within` auch keinem Fach-Agenten
  vergeben — das ist der eigentliche Zweck.

Zwei bewusste Entscheidungen der Lese-Ansicht: Artifact-Inhalte werden als
**Rohtext mit Ankern** gerendert (kein Markdown→HTML — der Inhalt stammt von
Agenten und aus Ingest-Fremdquellen), und `url:`-Belege der KB bleiben
**unverlinkter Text** aus demselben Grund. Einziger Inhalts-Write der UI ist
das Löschen eines Artifacts (editor+).

**DoD:** Python 1639 pytest / Coverage 90,98 %; Web 970 Vitest (Statements
86,2 %, Branches 80,43 %); ruff/mypy/tsc/lint/build lokal grün.

### Tabellen-Store war im Deployment unbenutzbar (2026-08-16, behoben)

Beim Live-Test der Tabellen-Achse antwortete `create_table` mit **500**.
Ursache war eine Folge meines eigenen Fixes aus PR #369: das dort ergaenzte
Named Volume auf `/data/tablestore` legt Docker als `root:root` an, weil das
Image das Verzeichnis nicht mitbringt — der API-Container laeuft aber als
`USER who2be` (uid 1000). Damit scheiterte schon das `mkdir` in
`tablestore/engine.py::_connect_rw` mit `PermissionError`.

Der Volume-Fix hat also den stillen Datenverlust beseitigt und dabei das
Schreiben ganz verhindert. Verifiziert war damals nur `docker compose
config`, nie ein echter Schreibvorgang — die Luecke lag zwischen
„Konfiguration korrekt" und „funktioniert".

Zwei Teile behoben (PR #372):

- `apps/api/Dockerfile` legt `/data/tablestore` im Image an und uebergibt es
  dem Service-Nutzer; Docker uebernimmt Eigentuemer und Rechte beim ersten
  Mount eines leeren Named Volume.
- Neuer Reason `tablestore_unavailable` (503): Datei-/Rechte-Fehler des
  Stores werden zentral uebersetzt (`services/wa_tables._store_failures`)
  statt als nacktes 500 durchzulaufen. Der Detail-Text nennt die
  Stellschraube, nicht Pfad oder OS-Fehler; die Ursache steht im Log.

### `describe_table` antwortete mit 500 (2026-08-16, behoben)

Der Live-Test nach dem Redeploy zeigte: der Tabellen-Store hat überlebt (7
Zeilen, `query_table`/`timeline`/`list_category_rules` alle 200) — nur
`describe_table` lief in ein **500**. Die Volume-Hypothese war damit
widerlegt; der Fehler steckte in Postgres, nicht in SQLite.

Ursache war eine Kette aus drei für sich harmlosen Teilen:

1. `upsert_convention` band `json.dumps(convention)` an `$4::jsonb`. Der Cast
   aktiviert den jsonb-Codec des App-Pools (`core/db.init_connection`,
   `encoder=json.dumps`) — der String wurde ein **zweites** Mal verpackt, in
   `wa_source_convention.convention` stand ein JSON-*String*.
2. Für dieselbe Zeile gab es **zwei** Mapper. Der tolerante
   (`wa_rule_repository`) trug alles, was über die Regel-/Konventions-Routen
   lief; der strenge (`wa_table_repository`) hing an genau einem Aufrufer —
   dem describe-Pfad — und starb an der Zeilenform.
3. Kein Test deckte die Kombination: der einzige describe-Test prüfte
   `conventions == []`.

Folge im Betrieb: sobald eine Area der dokumentierten Reihenfolge folgte
(Konvention setzen → importieren), war `describe_table` für diese Area tot —
ausgerechnet das Tool, das Agenten als „DER Einstieg vor jeder Query"
angeboten wird. Die Web-UI war nicht betroffen (sie ruft describe nicht auf).

Behoben (PR folgt in diesem Branch):

- **Write:** `upsert_convention` bindet das dict; `memory_guard` ebenso.
  `audit_log.detail` nutzt `$6::text::jsonb` — diese Form ist auf beiden
  Connection-Arten korrekt, weil der Executor dort offen ist.
- **Ein Mapper:** die Kopie in `wa_table_repository` ist entfallen, der
  Service liest Konventionen über `wa_rule_repository`.
- **Bestandsdaten:** Migration `0081` packt doppelt encodierte Werte aus
  (`wa_source_convention`, `workspace.memory_guard`); `audit_log` bewusst
  nicht — ein Audit-Trail wird nicht rückwirkend umgeschrieben.
- **Regressionsschutz:** ein Roundtrip-Test hätte nichts gefunden (der
  tolerante Leser hält ihn grade), deshalb prüfen die Tests den
  **gespeicherten Zustand** (`jsonb_typeof = 'object'`), dazu describe mit
  gesetzter Konvention, ein Migrationstest gegen nachgestellten Altbestand
  und ein Drift-Guard über alle Repositories.

### Suchtreffer-Anker lieferte nur die Überschrift (2026-08-16, behoben)

Befund A aus dem Builder-Test. Der dokumentierte Weg lautet
`search_workarea` → `read_artifact(anchor)`. Der Treffer-Anker ist per
Konstruktion die `block_id` des **Heading-Blocks** der Passage
(`wa_chunks.build_chunks`) — der Lesepfad gab darauf aber genau diesen einen
Block zurück. Der Agent bekam also `## Fehlercodes` ohne eine Zeile Inhalt
und musste doch das ganze Dokument laden, also genau das, was die Suche
vermeiden soll.

Warum es kein Test fand: der bestehende End-to-End-Test benutzt ein Dokument
aus EINEM Absatz ohne Überschrift. Dort sind „ein Block" und „die Passage"
dasselbe — die einzige Dokumentform, in der beide Verhalten
ununterscheidbar sind.

Behoben: `wa_chunks.split_sections` ist jetzt die gemeinsame Quelle der
Passagen-Grenzen für Index UND Lesepfad; `passage_for_anchor` löst einen
Anker auf. Ein Anker, der eine Passage eröffnet, liefert die ganze Passage
(bis zur nächsten Überschrift); jeder andere Anker weiterhin genau seinen
Block — das ist der Blick vor einem `patch_artifact`. Die Tool-Beschreibungen
in `apps/mcp` sagen beide Fälle jetzt an. Gegenprobe gefahren: ohne den Fix
liefert der Read `'## Fehlercodes [#…]'`, der neue Test wird rot.

### KB-Suche fand keine deutschen Wortformen (2026-08-17, behoben)

Befund B aus dem Builder-Test. `kb_node.search` indizierte mit
`to_tsvector('simple', content)` (0077) und die Abfrage nutzte konsistent
`plainto_tsquery('simple', …)` — kein Mismatch, aber **kein Stemming**. Eine
Aussage über den „Fehlercode" war damit für eine Suche nach „Fehlercodes"
unsichtbar, während `search_workarea` denselben Text fand (`wa_chunk` bildet
über `locale` auf `german`/`english` ab). Für einen Agenten ist der
Unterschied nicht lesbar: kein Treffer sieht aus wie kein Wissen.

Die Begründung in 0077 („Aussagen sind kurz und ggf. gemischtsprachig")
bleibt dort stehen; 0082 revidiert die Entscheidung, weil ihr Preis im
Betrieb sichtbar wurde. `workspace.content_locale` (0069) sagt längst, in
welcher Sprache ein Workspace schreibt.

Behoben: Migration `0082` gibt `kb_node` eine `locale`-Spalte (Backfill aus
dem Workspace) und ersetzt die generierte `search`-Spalte durch die
locale-abhängige Config — der Neuaufbau der Spalte **ist** der Reindex.
`services/kb.create_node` leitet die Sprache serverseitig über den
bestehenden `resolve_content_locale` ab; `KbNodeCreate` bekommt bewusst
**kein** `locale`-Feld.

Dazu: die Abbildung Sprache → Textsuch-Config lag zweimal wörtlich identisch
im Code (`content_chunk_repository`, `wa_search_repository`). Statt einer
dritten Kopie gibt es jetzt `repositories/fts_config.fts_config_expr`, das
alle drei Suchpfade nutzen. Gegenprobe: alle drei neuen Tests waren vor dem
Fix rot (`Fehlercodes` → `[]`, fehlende Spalte, fehlender Backfill).

### MCP verschluckte die Reason-Codes (2026-08-17, behoben)

Befund C aus dem Builder-Test. Die API antwortet an ihren Gates mit
`application/problem+json` und trägt dort `reason` — ein geschlossenes
Vokabular, ausdrücklich gebaut, damit „ein Agent darauf deterministisch
verzweigen kann, ohne den `detail`-Freitext zu parsen" (`models/errors.py`).
Der MCP-Client hat genau dieses Feld verworfen: bei 403/409/422 reichte er
nur `detail` durch, bei allen übrigen Statuses (400/408/413/429/503) nicht
einmal das — der Agent sah `Who2Be-API-Fehler (503).` und konnte weder
erkennen, dass ein Retry sinnlos ist, noch warum.

Behoben: eine Stelle (`client.problem_message`) statt zwei, angewandt auf
**alle** Fehler-Statuses. Die Meldung führt weiter mit der Prosa und hängt
`(reason=…, actionable_by=…)` an — greppbar, ohne den Lesefluss zu stören.
Antworten ohne Taxonomie (FastAPI-`HTTPException`, Validierungsfehler)
bleiben unverändert; es wird nichts erfunden. Gegenprobe: die neuen Tests
sind ohne den Fix rot, u. a. mit `Who2Be-API-Fehler (503).` statt der
Begründung.

## Bekannte Probleme

- **Tabellen-Import kappt Zell-Breiten nicht** (gefunden 2026-08-16): der
  Lesepfad deckelt Zellen auf 1 MB, der Schreibpfad nicht — ein Agent kann
  eine überbreite Zelle importieren und damit die eigene Tabelle für alle
  Queries auf dieser Spalte unlesbar machen (413). Kein System-DoS, aber ein
  Selbstschuss; Fix wäre eine Längenprüfung in `_validate_rows` (422).
- **Tabellen-Store-Verzeichnisse überleben den Hard-Purge** (bewusst, WP20):
  `cleanup_deleted_area_stores` fasst nur Verzeichnisse an, deren Workspace
  noch existiert — Schutz gegen einen Purge-Lauf gegen die falsche/leere DB.
  Nach einem Org-/Workspace-Hard-Purge bleiben die SQLite-Dateien deshalb
  liegen und werden nur gemeldet (`unknown_store_dirs` + WARNING). Die
  Nachbereinigung ist ein dokumentierter Betreiber-Schritt (RUNBOOK
  §Tabellen-Store-Backup, Löschkonzept §4a) — kein automatischer Pfad.
- **Blob-Objekt-Sweep hat eine Scope-Lücke** (dokumentiert): Objekte werden je
  Workspace gesucht, der im `wa_blob`-Katalog vorkommt. Ein Workspace, dessen
  allererster Ingest scheitert, hat nie eine Katalog-Zeile — sein einzelnes
  Objekt bleibt liegen (Alternative wäre ein Bucket-Vollscan je Cron-Lauf).
- **`audit_log.detail`: Altzeilen bleiben doppelt JSON-kodiert** (Rest des
  Befunds von 2026-08-16): der Schreibpfad ist korrigiert
  (`$6::text::jsonb`), die BESTEHENDEN Zeilen werden bewusst nicht
  umgeschrieben — ein Audit-Trail wird nicht rückwirkend angefasst. Wer
  `detail` per SQL (`->>`) auswertet, muss für Altzeilen mit einem
  JSON-*String* rechnen. Dass dieselbe Fehlerklasse woanders einen Endpunkt
  gekillt hat, steht oben (§`describe_table` antwortete mit 500).
- **Tool-Übersicht nennt Schreib-Tools ohne Capability** (gefunden
  2026-08-16): die kuratierten `_TOOLS`-Gruppen des `tools-overview`-Resolvers
  führen Read- und Write-Tools in EINER Signatur-Zeile. Ist die Gruppe wegen
  ihrer Reads sichtbar, liest ein Agent auch die Namen der Schreib-Tools, die
  er nicht halten darf (`tools/list` filtert sie korrekt weg — er bekäme also
  einen Fehler). Kein Sicherheitsproblem, aber irreführender Prompt; Fix wäre
  eine Trennung der gemischten Gruppen.
- E2E-Gate bleibt Soft, bis die CI-Infra dauerhaft stabil ist. Die
  Voraussetzung — eine überhaupt laufende CI — ist seit 2026-08-16 wieder
  gegeben (§Standards / CI); ob der Soft-Gate-Status fällt, ist eine
  Owner-Entscheidung (`coverage.all/E2E` im Standards-Review §4).
- Offene Owner-Entscheidungen: `docs/standards-review-2026-07-20.md` §4
  (ADR-0002 enforce vs. amend, Branch-Protection/Merge-Strategie,
  On-Prem-RLS, Cloud-Image-Deploy, LIC-1-Mechanik, coverage.all/E2E/CLA).

## Nächste Schritte (nicht-Code, manuell beim Owner)

Als Owner-Checkliste getrackt in Issue #338 (Welle 3 der Release-Mechanik
in #341):

1. ~~Actions-Billing klären~~ — erledigt, das CI-Gate läuft seit 2026-08-16
   wieder (§Standards / CI). Bleibt: der Public-Flip (Punkt 3).
2. GitHub-Settings: Branch-Protection, Auto-delete head branches,
   Merge-Strategie, Description/Topics/Discussions.
3. CLA-Assistant aktivieren; Visibility Private → Public (finaler Flip).
