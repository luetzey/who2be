# ADR-0053 — Lernschleife: Gedächtnis 2.0, Fälle, Prüffälle, Feedback-Gespräch

- Status: **Accepted** (Owner, 2026-09-28) — alle Weichen in Abschnitt 8 sind
  entschieden, P4 per Nachtrag vom 2026-09-28. Nachtrag Phase C vom
  2026-10-01 (PM-Entscheidungen vom 2026-09-30): 3.1.1, 3.1.2, 3.1.6, 6.4,
  Anhang A.2 und B. Nachtrag C0b vom 2026-10-01 (Owner-Entscheidungen
  Phase C 2 = a, 3 = b; W4 = a, W5 = a): workspace-weite Sicht, Stapel,
  Not-Aus — 3.1.1, 3.1.2, 6.1, 6.4.1, Anhang A.2.
- Datum: 2026-09-28
- Gemessen gegen: `origin/main` @ `ef0756a3`. Alle Code-Aussagen tragen einen
  Symbolanker oder einen SHA-Permalink (Konvention `docs/code-references.md`).
- Bezug: ADR-0038 (Usage-/Feedback-Flywheel), ADR-0040 (Builder verfasst
  System-Prompts, Mensch aktiviert), ADR-0044 (Agent-Memory), ADR-0047
  (WorkArea/KB, Zugriffslog, „kein Runtime-Host“), ADR-0051 (Fehlervokabular
  `ProblemReason`), ADR-0023 (Rollen `admin > editor > viewer`).
- Ergänzt bei Annahme: ADR-0038 (Abschnitt 7) und ADR-0044 (§2, §4 — siehe
  Abschnitt 7). Keine der beiden wird abgelöst.

## Inhalt

1. Kontext, Owner-Vorgaben, Leitsatz
2. Ist-Stand (belegt)
3. Datenmodell je Aggregat
4. Freigabematrix Art × Herkunft und was „auto“ nicht absichert
5. Migrationsweg und Rückweg
6. MCP- und API-Verträge (Phasen B–E)
7. Abbildung auf OWASP ASI06 und ADR-0038
8. Weichen (entschieden)
9. Konsequenzen
10. Anhang A — Kollisionsmatrix der Pakete
11. Anhang B — gesetzte Zahlen und ihre Herleitung

---

## 1. Kontext, Owner-Vorgaben, Leitsatz

**Leitsatz: schnelles Gedächtnis, langsames Verhalten.** Das Gedächtnis darf
schnell und — wenn der Nutzer es so einstellt — automatisch lernen. Das
grundsätzliche Verhalten eines Agenten (Persona, Playbooks, Resources,
System-Prompt, Tool-Policy) ändert sich nur über
**Entwurf → Prüffälle → menschliche Freigabe → Wirkungsmessung**. Kein Agent
aktiviert etwas; kein Lernvorschlag fließt direkt in einen Prompt.

Owner-Vorgaben vom 2026-09-28 (sinngemäß):

- Das komplette Gedächtnis nach Hermes-Vorbild in Who2Be abbilden.
- Der Nutzer entscheidet, ob Gedächtniseinträge automatisch freigegeben werden.
- Funktional und sicher.
- Aus dem Gedächtnis Muster erkennen und daraus Feedback ableiten.
- Feedback durch Nutzer, Agent und Builder; Feedback-Gespräche wie in einer
  Personalabteilung.
- Ziel: Der Agent wird mit jedem Handeln besser, hinterfragt und speichert;
  Feedback verbessert das grundsätzliche Verhalten.

Diese ADR legt Datenmodell, Rechte, Verträge und die Freigabelogik so fest,
dass die rund 30 Umsetzungspakete der Phasen B–F ohne weitere
Architekturfrage gebaut werden können. Sie trifft keine Entscheidung, die der
Owner nicht in A4 bestätigt.

Randbedingungen, die für alles unten gelten:

- **Who2Be ist kein Runtime-Host** (ADR-0047, Nicht-Ziele). Modelle laufen im
  Client des Nutzers (Hermes, Claude Code, …). Who2Be führt keine LLM-Aufrufe
  aus, auch nicht für Prüffälle oder Gespräche.
- **Who2Be bleibt LLM-frei** in der Bewertung (ADR-0044, „Keine
  Extraktions-Pipeline/kein LLM-Judge“). Mustererkennung ist deterministisch.
- **Mandantentrennung** über RLS-Policy `tenant_isolation` auf
  `workspace_id` für jede neue Tabelle, Muster aus
  `apps/api/src/who2be_api/migrations/0053_feedback_flywheel.sql@c600e97c`.
- **Fehler** tragen einen `reason` aus
  `packages/models/src/who2be_models/errors.py#ProblemReason` (ADR-0051).

## 2. Ist-Stand (belegt)

### 2.1 Gedächtnis

- Tabelle `agent_memory` mit `status ∈ {pending, active, rejected}`, `fact ≤ 300`,
  `context ≤ 200`, `category`, `importance 1–10`, `source` (Default `'agent'`),
  `retrieval_count`, `last_retrieved_at`, `agent_id NOT NULL` mit
  `ON DELETE CASCADE` —
  `apps/api/src/who2be_api/migrations/0066_agent_memory.sql@448b1e2c`.
  Die Spalte `source` wird heute nie anders als mit dem Default befüllt:
  `apps/api/src/who2be_api/repositories/memory_repository.py#PgMemoryRepository.insert`
  schreibt sie nicht.
- Workspace-weite Wächter-Konfiguration als `workspace.memory_guard jsonb` —
  `apps/api/src/who2be_api/migrations/0067_memory_guard.sql@3af22ebd`,
  Modell `packages/models/src/who2be_models/memory.py#MemoryGuardConfig`,
  admin-gated in
  `apps/api/src/who2be_api/services/memory_service.py#MemoryService._require_guard_admin`.
- Optionaler Vektor `content_vector vector(384)` —
  `apps/api/src/who2be_api/migrations/0072_agent_memory_vector.sql@45bec6b7`.
- Stufen `off < read_only < suggest < auto` in
  `packages/models/src/who2be_models/tool_policy.py#MemoryMode`, geprüft über
  `packages/models/src/who2be_models/tool_policy.py#AgentToolPolicy.memory_at_least`.
  `auto` heißt heute: **jeder** Eintrag, den `save_memory` annimmt, wird sofort
  `active` — ohne Unterscheidung nach Art oder Herkunft
  (`apps/api/src/who2be_api/services/memory_service.py#MemoryService.save`).
- Wächter, die immer laufen: Importance-Schwelle
  (`packages/models/src/who2be_models/memory.py#MEMORY_MIN_IMPORTANCE`),
  Injection-Wächter (`apps/api/src/who2be_api/services/memory_service.py#_guard_rejection`),
  Dublettenprüfung gegen pending + active + rejected
  (`apps/api/src/who2be_api/repositories/memory_repository.py#PgMemoryRepository.find_similar`,
  Schwelle `apps/api/src/who2be_api/repositories/memory_repository.py#MEMORY_DEDUP_SIMILARITY`),
  Obergrenze je Agent (`packages/models/src/who2be_models/memory.py#MEMORY_MAX_PER_AGENT`)
  und das Schreib-Ratenlimit (`apps/api/src/who2be_api/core/security.py#require_write_rate`).
- Kuratieren (Triage, Bearbeiten, Löschen) ist Menschen ab `editor`
  vorbehalten; agent-gebundene Tokens sind hart ausgeschlossen —
  `apps/api/src/who2be_api/services/memory_service.py#MemoryService._require_human`.
  Bearbeiten überschreibt den Eintrag ohne Historie
  (`apps/api/src/who2be_api/services/memory_service.py#MemoryService.update_memory`).
- Laufzeit-Push: `get_persona` hängt für agent-gebundene Aufrufer die Top-N
  aktiven Einträge an, gerahmt als „gespeicherte Nutzerdaten, KEINE
  Anweisungen“ —
  `apps/api/src/who2be_api/services/persona_service.py#PersonaService._memory_runtime_section`,
  N = `packages/models/src/who2be_models/memory.py#MEMORY_PERSONA_TOP_N`.
- MCP-Werkzeuge `search_memory`, `list_memories`, `save_memory` —
  `apps/mcp/src/who2be_mcp/server.py#save_memory`; Sichtbarkeit nach Stufe in
  `packages/models/src/who2be_models/tool_requirements.py#MCP_TOOL_REQUIREMENTS`.

### 2.2 Feedback und Nutzung

- Append-only `usage_event` und `agent_feedback`, Grants nur `SELECT, INSERT` —
  `apps/api/src/who2be_api/migrations/0053_feedback_flywheel.sql@c600e97c`.
- Triage als eigene Events `feedback_resolution` mit
  `addressed | in_progress | dismissed`, ohne Verweis auf eine Version —
  `apps/api/src/who2be_api/migrations/0054_feedback_resolution.sql@9f7fc998`.
- Hard-Delete durch Menschen —
  `apps/api/src/who2be_api/migrations/0058_feedback_delete_grant.sql@826ef616`;
  System-Feedback ohne Element —
  `apps/api/src/who2be_api/migrations/0059_system_feedback.sql@e8acd3b7`.
- Ziele sind nur Elemente, nie der Agent:
  `packages/models/src/who2be_models/feedback.py#FeedbackTarget`.
- Inhalts-Feedback verlangt `editor`:
  `apps/api/src/who2be_api/services/feedback_service.py#FeedbackService.submit_feedback`.
  Ein `viewer` kann heute nichts melden.
- Nutzung ist Selbstauskunft des Agenten
  (`apps/api/src/who2be_api/services/feedback_service.py#FeedbackService.record_usage`),
  und die Aggregation zählt über alle Versionen eines Elements
  (`apps/api/src/who2be_api/repositories/feedback_repository.py#PgFeedbackRepository.summarize`).
- Die Migrationen 0055 und 0056 haben aktive Builder-Versionen direkt
  geschrieben (Betreiberpfad für verwaltete Inhalte) —
  `apps/api/src/who2be_api/migrations/0055_builder_feedback_refresh.sql@6df0de03`,
  `apps/api/src/who2be_api/migrations/0056_builder_playbook_feedback.sql@31deb1e5`;
  der Verwaltungs-Marker kam mit
  `apps/api/src/who2be_api/migrations/0057_managed_aggregates.sql@5ac904e5`.

### 2.3 Zugriffslog, Aktivierung, Rollen

- `agent_access_log` schreibt der Server selbst, best-effort, No-op für
  Menschen — `apps/api/src/who2be_api/services/access_log.py#log_access`,
  Schema `apps/api/src/who2be_api/migrations/0079_agent_access_log.sql@c1a25a02`.
  Es ist auf WorkArea/KB beschränkt (`ref_kind ∈ {artifact, node, table, blob}`),
  tagesweise dedupliziert und hat seit 0080 keinen Cascade auf den Agenten.
- Aktivieren und Zurückziehen sind `admin`-Sache —
  `apps/api/src/who2be_api/services/version_status.py#required_role_for_transition`;
  System-Prompts kann kein Agent-Token scharfschalten —
  `apps/api/src/who2be_api/services/version_status.py#_require_transition_capability`.
- Agent-gebundene Tokens sind seit 0088 auf `editor` gedeckelt —
  `apps/api/src/who2be_api/migrations/0088_agent_bound_token_role_cap.sql@3771bb55`,
  `apps/api/src/who2be_api/core/security.py#cap_agent_bound_role`.
- Die eine Quelle für „kommt der Aufruf von einem Agenten?“ ist
  `apps/api/src/who2be_api/core/security.py#is_agent_bound`.

### 2.4 Was fehlt (Befunde, die diese ADR schließt)

Keine Arten und keine Herkunft im Gedächtnis; kein gemeinsames
Nutzergedächtnis; keine Historie, kein Rollback, kein Verfall; Agenten können
nichts ändern oder löschen, auch nicht vorschlagen; kein Fall mit erwartetem
Verhalten; der Agent ist kein Feedback-Ziel; kein Gesprächsprotokoll; kein
Prüffall, kein Regressionslauf; Nutzung und Signale ohne Bezug auf die Version.

## 3. Datenmodell je Aggregat

Gemeinsame Regeln für **jede** neue Tabelle:

- `workspace_id uuid NOT NULL`, RLS aktiviert, Policy `tenant_isolation`
  (USING und WITH CHECK auf `app.current_tenant`), Muster aus Migration 0053.
- Append-only-Tabellen erhalten für `who2be_app` nur `SELECT, INSERT`
  (Muster aus Migration 0053). Wo `UPDATE` oder `DELETE` nötig ist, steht es ausdrücklich
  dabei.
- Freitexte sind Daten. Sie werden im Web escaped angezeigt und fließen in
  keinen gerenderten Prompt (ADR-0038). Ausnahmen gibt es genau zwei und sie
  sind unten benannt: aktive Gedächtniseinträge der Arten `user_fact` und
  `agent_note` beim Abruf.
- Status- und Enum-Werte sind Pydantic-validiert; in der DB steht ein `CHECK`
  dort, wo eine Invariante sicherheitsrelevant ist (Kennzeichnung „DB-CHECK“).
- DSGVO: Jede Tabelle mit Personenbezug kommt in den Art.-20-Export
  (`apps/api/src/who2be_api/services/gdpr_export_service.py`), in das VVT
  (`docs/compliance/vvt.md`) und in die Purge-Anonymisierung
  (`apps/api/src/who2be_api/repositories/account_repository.py#PgAccountPurgeRepository.purge_account_data`).
  Das ist Teil des jeweiligen Schema-Pakets, nicht Nacharbeit.

### 3.1 Gedächtniseintrag (Erweiterung von `agent_memory`)

Der Eintrag bleibt in `agent_memory`. Dadurch bleiben Wächter, Dublettenprüfung,
Vektor, Export und Triage-Oberfläche eine Quelle (Weiche M1).

Neue Spalten:

| Spalte | Typ | Bedeutung |
|---|---|---|
| `kind` | text, DB-CHECK | `user_fact` (Fakt über den Nutzer) · `agent_note` (Arbeitsnotiz: Umgebung, Werkzeug-Eigenheiten) · `lesson` (Lernvorschlag, prozedural). Default für Bestand: `user_fact`. |
| `scope` | text, DB-CHECK | `agent` (Gedächtnis dieses Agenten) · `user` (Nutzergedächtnis). Default `agent`. |
| `subject_user_id` | uuid NULL | bei `scope='user'` Pflicht: der Nutzer, um den es geht. |
| `origin` | text, DB-CHECK | vom Agenten deklariert: `user_stated` · `inferred` · `external_content` (Werkzeug, Web, Dokument). Bestand: `legacy_unknown`. |
| `source` | text, DB-CHECK (bestehend) | vom **Server** aus dem Aufrufweg gesetzt: `agent` · `human` · `import`. Wird ab C1 wirklich befüllt. |
| `confirmed_at` / `confirmed_by` | timestamptz / uuid NULL | menschliche Bestätigung. Ein Eintrag, der über die Matrix automatisch aktiv wurde, ist aktiv, aber **unbestätigt**. |
| `expires_at` | timestamptz NULL | Verfallszeitpunkt für unbestätigte Einträge (Abschnitt 3.1.3). |
| `occurrence_count` | int NOT NULL DEFAULT 1 | nur für `lesson`: wie oft derselbe Lernvorschlag eingereicht wurde. |
| `converted_case_id` | uuid NULL | nur für `lesson`: der Fall, zu dem er wurde. |

Status: `pending · active · rejected · expired · converted`.

Invarianten (DB-CHECK):

- `kind='lesson'` ⇒ `status ∈ {pending, rejected, converted}`. **Ein
  Lernvorschlag kann in der Datenbank nie `active` werden.** Alle Abrufpfade
  filtern heute schon auf `status='active'`
  (`apps/api/src/who2be_api/repositories/memory_repository.py#PgMemoryRepository.search_active`,
  `apps/api/src/who2be_api/repositories/memory_repository.py#PgMemoryRepository.list_active`).
  Damit ist „Lernvorschläge fließen nie in den Prompt“ strukturell und nicht
  per Filter erzwungen, den ein neuer Abrufpfad vergessen könnte.
- `scope='user'` ⇒ `subject_user_id IS NOT NULL`, `kind='user_fact'` und
  `agent_id IS NULL`.
- `scope='agent'` ⇒ `agent_id IS NOT NULL`.
- `status='converted'` ⇔ `converted_case_id IS NOT NULL`.

`agent_id` wird nullable (für `scope='user'`) und bekommt eine Begleitspalte
`created_by_agent_id uuid NULL REFERENCES agent ON DELETE SET NULL`. Grund:
Ein Nutzerfakt darf nicht verschwinden, weil der Agent gelöscht wird, der ihn
zuerst gehört hat. Der bestehende Cascade auf `agent_id` bleibt für
`scope='agent'` unverändert. Dass er einen Nutzerfakt nie erreicht, sichert
die dritte Bedingung der ersten Invariante (`agent_id IS NULL` bei
`scope='user'`) als DB-CHECK. Der Agent, der den Fakt eingereicht hat, steht
ausschließlich in `created_by_agent_id`.

#### 3.1.1 Nutzergedächtnis je Workspace — mit Abweichung vom Plan

Der Plan sagt „gemeinsames Nutzergedächtnis **je Workspace**“ (G-W1). Beim
Lesen des Codes komme ich zu einer engeren Empfehlung: **je Workspace und
Nutzer** (`workspace_id, subject_user_id`).

Begründung: Ein Workspace hat mehrere Mitglieder (ADR-0023). Ein
Nutzergedächtnis je Workspace würde Fakten über Nutzer A den Agenten von
Nutzer B zeigen. Das verletzt ASI06 #3 („Memory segmentation: Isolate user
sessions …“). Für den Hermes-Fall ändert die engere Form nichts: Alle
Profil-Tokens gehören demselben Besitzer (`api_token.owner_id`, im Kontext
`ctx.user_id`, `apps/api/src/who2be_api/core/security.py#WorkspaceContext`),
also teilen sich alle Profile dieses Besitzers ein Nutzergedächtnis. Das ist
das Hermes-Bild USER.md ↔ Nutzer. Siehe Weiche M2.

Rechte am Nutzergedächtnis:

| Handlung | Wer |
|---|---|
| lesen (Abruf) | Agenten des Workspace mit `memory_mode ≥ read_only`, deren Token-Besitzer `subject_user_id` ist |
| vorschlagen | wie `save_memory` heute, mit `scope='user'` |
| triagieren, bearbeiten, bestätigen | der Nutzer selbst (jede Rolle ≥ `viewer`); ein `admin` nur löschen |
| sehen in der Oberfläche | der Nutzer selbst; `admin` nur Anzahl und Löschung, nicht den Inhalt |

Die zweite und vierte Zeile weichen vom heutigen Memory-Recht (`editor+`) ab.
Das ist Absicht: Ein Fakt über eine Person gehört dieser Person.
Exportieren darf ihr Nutzergedächtnis ebenfalls nur die Person selbst. Den
Admin-Pfad „Anzahl sehen, alles löschen“ legt 6.4.1 fest (Owner W5 = a).

Obergrenze: Je `(workspace_id, subject_user_id)` höchstens **500** Einträge
mit `scope='user'`, gezählt über alle Status — wie heute die Agentengrenze
(`packages/models/src/who2be_models/memory.py#MEMORY_MAX_PER_AGENT`), die
ebenfalls `rejected` mitzählt. Neue Konstante `MEMORY_MAX_PER_USER` daneben.
Die Zahl ist eine gesetzte Annahme (Anhang B). Wird sie erreicht, antwortet
der Server 409 `memory_cap_reached` mit `params={maximum, scope:'user'}`;
es gibt keinen neuen `ProblemReason`. Einträge mit `scope='user'` tragen
`agent_id IS NULL` und zählen deshalb nicht gegen die Agentengrenze.

#### 3.1.2 Historie und Rollback

Neue Tabelle `agent_memory_event`, append-only (`SELECT, INSERT`):

| Spalte | Bedeutung |
|---|---|
| `id`, `workspace_id`, `memory_id` (FK `agent_memory` ON DELETE CASCADE) | |
| `event` | `created · auto_activated · approved · rejected · edited · confirmed · expired · reactivated · change_proposed · delete_proposed · proposal_accepted · proposal_rejected · rolled_back · converted · merged · auto_revoked` (`auto_revoked` per Nachtrag C0b, 6.4.1; Migration in C3) |
| `actor_kind` | `human · agent · system` |
| `actor_id`, `agent_id` | wer; `system` für Verfallsjob und Matrix |
| `before`, `after` | jsonb-Schnappschuss von `fact, category, importance, status, kind, origin` |
| `reason` | Freitext ≤ 500 (Triage-Notiz, Vorschlagsbegründung) |
| `created_at` | |

**Rollback** ist kein Löschen, sondern ein neues Event `rolled_back`, das den
Zustand aus `before` eines gewählten Events wiederherstellt — nur durch einen
Menschen. Die bestehende Spalte `triage_note` bleibt für die Oberfläche und
wird mit jedem Triage-Event gespiegelt.

**`merged`** schreibt der Server, wenn ein `lesson`-Vorschlag auf einen
bestehenden `lesson`-Eintrag trifft (3.1.6). Das Event hängt am Treffer,
`actor_kind='agent'`, `agent_id` ist der einreichende Agent; `before` und
`after` sind gleich, weil sich der Treffer inhaltlich und im Status nicht
ändert. Ein eigenes Event statt `created` mit Verweis, weil `created` dann
zwei Bedeutungen hätte („Eintrag entstanden“ und „Wiederholung eines
anderen“) und jede Auswertung der Historie unterscheiden müsste. Mit
`merged` liefert die Historie jede Wiederholung mit Zeitpunkt.

**Löschen** bleibt Hard-Delete (ADR-0044, DSGVO Art. 17). Die Historie geht
per Cascade mit. Zurück bleibt eine inhaltsfreie Zeile in `audit_log`
(`action='memory.deleted'`, `target=<memory_id>`), dasselbe Muster wie
`apps/api/src/who2be_api/migrations/0088_agent_bound_token_role_cap.sql@3771bb55`.
Damit ist nachvollziehbar, *dass* gelöscht wurde, ohne den gelöschten Inhalt
aufzubewahren (Weiche M5).

#### 3.1.3 Verfall

- Verfall betrifft nur **unbestätigte** Einträge: `pending` und
  automatisch aktivierte `active` ohne `confirmed_at`.
- `expires_at = created_at + 30 Tage` (gesetzte Annahme, Anhang B).
- **Abrufe verlängern nichts.** Nur eine menschliche Bestätigung setzt
  `expires_at = NULL`. Grund: Verfall über Abrufhäufigkeit würde gerade den
  Eintrag verlängern, der oft ausgespielt wird (Wettbewerbsrecherche §3,
  Zeile „Verfallsdatum“).
- Der Verfallsjob setzt `status='expired'` und schreibt `expired`. Er löscht
  nicht: Abgelaufene Einträge bleiben Teil der Dublettenbasis (sonst reicht
  der Agent denselben Fakt erneut ein, derselbe Grund wie für `rejected` in
  ADR-0044 §3). Ein Mensch kann `reactivate` auslösen.
- Der Job läuft als eigener Einstiegspunkt neben
  `apps/api/src/who2be_api/core/purge.py` (CLI, Owner-Connection), nicht im
  Request-Pfad.

#### 3.1.4 Änderungs- und Löschvorschläge von Agenten

Neue Tabelle `agent_memory_proposal`:

| Spalte | Bedeutung |
|---|---|
| `id`, `workspace_id`, `memory_id` (FK ON DELETE CASCADE), `agent_id` | |
| `action` | `change · delete` |
| `new_fact` | bei `change` Pflicht, ≤ 300, durchläuft dieselben Wächter wie `save_memory` |
| `reason` | Pflicht, ≤ 200 |
| `status` | `pending · accepted · rejected` — `UPDATE` nur auf `status` |
| `decided_by`, `decided_at` | |

Ein Agent darf nur Einträge vorschlagen, die er abrufen darf (eigenes
Agentengedächtnis, eigenes Nutzergedächtnis). Vorschläge werden **nie**
automatisch angenommen, auch nicht unter `auto` (Abschnitt 4, Zeile
„Änderung/Löschung“). Annahme durch einen Menschen schreibt
`proposal_accepted` plus `edited` bzw. löscht.

#### 3.1.5 Grenzen für Agentennotizen

`agent_note` ist das Gegenstück zu Hermes MEMORY.md. Heute verbietet der
Werkzeugtext von `save_memory` Repo- und Code-Fakten
(`apps/mcp/src/who2be_mcp/server.py#save_memory`). Neu:

- erlaubt: Umgebung, Werkzeug-Eigenheiten, Arbeitskonventionen dieses Agenten;
- weiter verboten: Repo- und Code-Fakten (die gehören ins Repo),
  Zugangsdaten und Geheimnisse (Secret-Scan in C2), Angaben über Dritte;
- gleiche Längen- und Importance-Grenzen wie `user_fact`; eigene Obergrenze
  je Agent (gesetzte Annahme: 200, Anhang B), getrennt von
  `MEMORY_MAX_PER_AGENT`, damit Notizen die Nutzerfakten nicht verdrängen.

#### 3.1.6 Lernvorschläge und Wiederholung

Die heutige Dublettenprüfung weist einen ähnlichen Eintrag mit 409 ab
(`apps/api/src/who2be_api/services/memory_service.py#MemoryService.save`,
`reason='memory_duplicate'`). Für `lesson` wäre das falsch: Die Wiederholung
**ist** das Signal, aus dem die Mustererkennung ein Muster macht. Deshalb:
Ein neuer `lesson`-Vorschlag wird gegen **alle** `lesson`-Einträge desselben
Agenten geprüft, unabhängig vom Status (`pending`, `rejected`, `converted`).
Trifft er einen, erhöht der Server dort `occurrence_count` und schreibt das
Event `merged` (3.1.2), statt abzulehnen. Die Antwort ist 200 mit
`merged_into=<id>`. Es entsteht keine neue Zeile; der Merge zählt deshalb
nicht gegen eine Obergrenze. Für `user_fact` und `agent_note` bleibt 409.

**Der Status des Treffers ändert sich nie:** Ein `rejected` bleibt
`rejected`, ein `converted` bleibt `converted`, ein `pending` bleibt
`pending`. Begründung:

- Die Wiederholung ist Signal für die Mustererkennung (D5), auch wenn der
  Mensch die Lektion schon abgelehnt hat.
- Bei `converted` ist sie zusätzlich Signal für die Nachschau: Die Maßnahme
  aus dem Fall wirkt offenbar nicht.
- Ein Agent darf eine abgelehnte Lektion nicht durch erneutes Einreichen
  wiederbeleben. Das ist dieselbe Logik wie `rejected` als Dublettenbasis in
  ADR-0044 §3.

### 3.2 Prüffall und Prüflauf

`test_case` — was geprüft wird:

| Spalte | Bedeutung |
|---|---|
| `id`, `workspace_id` | |
| `agent_id` | Pflicht: der Agent, dessen Verhalten geprüft wird und in dessen Kontext der Client den Prüffall ausführt (FK ON DELETE CASCADE) |
| `entity_type`, `entity_id` | optional: das Element, auf das der Prüffall zielt (`persona · playbook · resource · external_tool · system_prompt_template`). Welche Prüffälle für eine Elementversion gelten, regelt Abschnitt 3.2.1 (Weiche P4) |
| `title` | ≤ 200 |
| `input` | die Eingabe (Nutzernachricht, ggf. Kontext), ≤ 8 000 |
| `expected_behavior` | die **vom Menschen formulierte** Regel, ≤ 2 000 |
| `check_kind` | `human_rule` (Mensch bewertet) · `must_contain` · `must_not_contain` (deterministisch, Muster in `check_pattern`) |
| `check_pattern` | nur bei den beiden deterministischen Arten |
| `origin_case_id` | optional: der Fall, aus dem der Prüffall stammt |
| `origin_measure_id` | optional: die Maßnahme |
| `status` | `active · retired` — `UPDATE` nur auf `status` |
| `supersedes_id` | optional: der Prüffall, den dieser korrigiert (FK `test_case` ON DELETE SET NULL, gleicher Workspace) |
| `created_by_kind`, `created_by` | `human · agent`; der Builder darf anlegen |
| `created_at` | |

Inhalt ist unveränderlich. Eine Korrektur ist ein neuer Prüffall mit
`supersedes_id` auf den alten plus `retired` am alten, beides in einer
Transaktion. Grund: Ein Prüffall, dessen
Erwartung sich still ändert, macht jede spätere Vorher/Nachher-Messung
wertlos.

`test_run` — ein Ergebnis, append-only:

| Spalte | Bedeutung |
|---|---|
| `id`, `workspace_id`, `test_case_id` | |
| `subject_entity_type`, `subject_version_id` | die geprüfte **Version** (Entwurf oder aktiv). Keine FK, weil die Versionen in fünf Tabellen liegen; die Zugehörigkeit prüft der Service |
| `runs_total`, `runs_passed` | mehrere Läufe je Fall (Feedback-Recherche §3.2, Stufe 3); `runs_total >= 1`, `0 <= runs_passed <= runs_total` |
| `verdict` | `pass · fail · error`; `pass` nur bei `runs_passed = runs_total` (n/n). Inkonsistente Meldungen lehnt der Server mit 422 `test_run_verdict_inconsistent` ab (6.1) |
| `output_excerpt` | ≤ 4 000 |
| `attestation` | DB-CHECK mit zwei Werten: `client_self_report` (Meldung über Agent-Token/MCP) · `human_rating` (Meldung eines Menschen über die Web-Session; erfordert per CHECK `reported_by_user_id`) |
| `model_provider`, `model_name` | Schnappschuss wie in `agent_access_log` (0080) |
| `reported_by_agent_id`, `reported_by_user_id` | |
| `created_at` | |

`attestation` ist Pflicht und in der Oberfläche sichtbar. Der Server setzt
den Wert aus dem Aufrufweg, nie aus dem Request-Body. Ergebnisse über
Agent-Token/MCP sind Selbstauskunft des Clients (Weiche P1). Prüffälle mit
`check_kind='human_rule'` meldet der Client-Runner nur mit Ausgabe und
`verdict='error'`; die Bewertung macht ein Mensch in der Web-Oberfläche als
neues `test_run` mit `attestation='human_rating'`. Es zählt das letzte
Ergebnis. Sollte Who2Be später selbst ausführen, wäre das ein dritter Wert.

Rechte:

| Handlung | Mensch | Agent-Token |
|---|---|---|
| Prüffälle lesen | `editor` | eigener Agent; Builder mit `case_triage` für alle |
| Prüffälle anlegen / zurückziehen | `editor` | Builder mit `case_triage` (anlegen, nicht zurückziehen) |
| Ergebnisse melden | `editor` | jeder Agent mit `test_report` für Prüffälle, die er lesen darf |

#### 3.2.1 Welche Prüffälle gelten für eine Elementversion? (Weiche P4)

Aktiviert wird eine **Elementversion**
(`apps/api/src/who2be_api/services/version_status.py#VersionStatusService.transition_playbook_version`
und die vier Geschwister), ohne Agent im Kontext. Ein Prüffall hängt aber an
einem Agenten. Elemente werden geteilt:

- Eine Persona kann mehreren Agenten gehören — `agent.persona_id` ist nur
  indiziert, nicht eindeutig
  (`apps/api/src/who2be_api/migrations/0023_agent.sql@28ea5c8c`); dasselbe gilt
  für `agent.system_prompt_template_id`.
- Playbooks hängen n:m an Personas
  (`apps/api/src/who2be_api/migrations/0004_persona_playbook.sql@0615c441`) und
  zusätzlich über Composites
  (`apps/api/src/who2be_api/migrations/0028_playbook_composition.sql@fe0108c6`).
- Resources hängen über Blockverweise an Playbooks und über Composites an
  Resources — Rückwärtssuche heute in
  `apps/api/src/who2be_api/repositories/usage_repository.py#PgUsageRepository.list_resource_usages`
  und
  `apps/api/src/who2be_api/repositories/usage_repository.py#PgUsageRepository.list_resource_parent_composites`.
- External Tools haben **keine** gespeicherte Verknüpfung. Sie werden beim
  Rendern über ihren Alias aufgelöst
  (`apps/api/src/who2be_api/services/placeholders/resolvers/tool_ref.py#ToolRefResolver`).

Auflösungsregel (Option (a) in P4, entschieden): Für eine Version `V` des
Elements `E` gilt die Vereinigung aus

1. **direkt gebundenen Prüffällen:** `status='active'` und
   `(entity_type, entity_id) = E`, gleich an welchem Agenten;
2. **Prüffällen der betroffenen Agenten:** `status='active'` und `agent_id`
   in der Menge der Agenten, die `E` **heute** erreichen:

| Elementart | betroffene Agenten |
|---|---|
| `persona` | `agent.persona_id = E` |
| `system_prompt_template` | `agent.system_prompt_template_id = E` |
| `playbook` | Agenten, deren Persona `E` direkt verknüpft oder ein Composite verknüpft, das `E` (transitiv) enthält |
| `resource` | Agenten der Playbooks, die `E` direkt oder über ein Resource-Composite referenzieren, dann weiter wie `playbook` |
| `external_tool` | keine — nur Teil 1 (direkt gebunden). Der Bericht weist das aus (`scope_note='no_reference_index'`) |

Regeln dazu:

- **Maßgeblich ist die Verknüpfung zum Zeitpunkt der Berichtsabfrage**, nicht
  die bei Anlage des Prüffalls. Die Verknüpfungstabellen sind nicht
  versioniert (Kommentar in Migration 0004); eine historische Auflösung gäbe
  es nicht.
- **Gleiche Menge für Bericht (6.2) und Aktivierung (6.3).** Beide rufen
  dieselbe Service-Funktion; der Bericht gruppiert nach Agent und nennt je
  Agent, über welchen Weg er betroffen ist (`via`).
- **Geteiltes Playbook, viele Agenten:** Alle Prüffälle aller betroffenen
  Agenten gehören dazu — das ist die Regression aus LW5. Fehlende Ergebnisse
  zählen als `missing` und führen in den Pfad „Bestätigung plus Grund“ aus
  6.3, nicht in einen Block. Der Bericht zeigt die Zahl betroffener Agenten
  vorn, damit die Breite einer Änderung sichtbar ist, bevor jemand aktiviert.
- **Ausführung:** Der Client führt jeden Prüffall im Kontext von
  `test_case.agent_id` aus und setzt dabei die zu prüfende Version an die
  Stelle der aktiven; die Version liest er über `get_version`
  (`apps/mcp/src/who2be_mcp/server.py#get_version`). Einen serverseitigen
  Render mit Versionsersatz legt diese ADR nicht fest.
- **Leere Menge** (kein Agent betroffen, kein direkter Prüffall): Der Bericht
  ist leer, die Aktivierung braucht keine Bestätigung.

### 3.3 Fall

`agent_case` — die Einzelrückmeldung nach SBI plus erwartetem Verhalten:

| Spalte | Bedeutung |
|---|---|
| `id`, `workspace_id` | |
| `agent_id` | Pflicht: der Agent, um dessen Verhalten es geht (F-W1). FK ON DELETE CASCADE |
| `reporter_kind` | `human · agent · builder · pattern` |
| `reporter_user_id`, `reporter_agent_id` | |
| `situation` | Pflicht, ≤ 4 000 |
| `behavior` | Pflicht, ≤ 4 000 |
| `impact` | optional, ≤ 2 000 (Spec-F1, siehe Abschnitt 8) |
| `expected_behavior` | Pflicht, ≤ 2 000 |
| `severity` | `low · medium · high`, Default `medium` |
| `signal` | optional, das heutige Vier-Werte-Signal aus `packages/models/src/who2be_models/feedback.py#FeedbackSignal` als schnelle Kategorie |
| `source_ref` | optional, ≤ 500: Verweis auf Lauf, Artifact, Unterhaltung |
| `source_feedback_id` | optional: das Alt-Feedback, aus dem der Fall übernommen wurde |
| `source_memory_id` | optional: der Lernvorschlag, aus dem der Fall wurde |
| `status` | abgeleitet aus dem letzten `agent_case_event` (Muster `feedback_resolution`) |
| `created_at` | |

Der Inhalt ist nach dem Anlegen unveränderlich; Ergänzungen sind Events.

`agent_case_event` (append-only): `case_id`, `event`, `actor_kind`, `actor_id`,
`note ≤ 2 000`, `version_entity_type`, `version_id`, `measure_id`, `created_at`.

Zustände und erlaubte Übergänge:

```text
open ──► triaged ──► in_progress ──► addressed ──► verified
  │         │             │              │
  └─────────┴──────►  dismissed          └──► reopened ──► triaged
```

| Übergang | Wer | Pflicht |
|---|---|---|
| → `triaged` | Mensch `editor`; Builder mit `case_triage` | Zuordnung zu ≥ 1 Element oder zu `model_limit` |
| → `in_progress` | wie `triaged` | `measure_id` |
| → `addressed` | **System**, wenn die mit der Maßnahme verknüpfte Version durch einen Menschen aktiv wird; sonst Mensch `editor` | `version_entity_type`, `version_id` (F-W6) |
| → `verified` | Mensch `editor` nach Nachschau mit Einstufung `effective` | `measure_id` mit Nachschau-Ergebnis |
| → `reopened` | Mensch `editor`; System bei Nachschau `ineffective` | Begründung |
| → `dismissed` | Mensch `editor` | Begründung (Regel aus dem Pflege-Playbook) |

Agent-Tokens — auch der Builder — können `addressed`, `verified` und
`dismissed` **nie** setzen (F-W7, „Partei, nicht Richter“). Das prüft der
Service über `apps/api/src/who2be_api/core/security.py#is_agent_bound`, nicht
über eine Capability, damit es sich nicht versehentlich freischalten lässt.

`agent_case_element` — n:m-Zuordnung, im Gespräch oder bei der Triage:

| Spalte | Bedeutung |
|---|---|
| `case_id`, `workspace_id` | |
| `target` | `persona · playbook · resource · external_tool · system_prompt_template · tool_policy · memory · model_limit` |
| `entity_id` | NULL bei `tool_policy` (hängt am Agenten) und `model_limit` („Modellgrenze, keine Änderung sinnvoll“) |
| `assigned_by_kind`, `assigned_by`, `created_at` | |
| Löschen | erlaubt (`DELETE`), weil eine Zuordnung korrigierbar sein muss; das Event `element_unassigned` hält es fest |

`agent_case_statement` — die Schilderung des betroffenen Agenten ohne
Selbstnote: `case_id`, `agent_id` (muss `agent_case.agent_id` sein),
`followed_instruction`, `missing_information`, `conflict` (je ≤ 2 000),
`created_at`. Append-only; eine neue Schilderung ersetzt die alte in der
Anzeige, die alte bleibt.

Rechte:

| Handlung | Mensch | Agent-Token |
|---|---|---|
| Fall melden | jede Rolle ab `viewer` (F-W4) | `feedback_write` (Default an, ADR-0038) — für den eigenen und für andere Agenten des Workspace |
| eigene gemeldete Fälle lesen | ab `viewer` | eigene |
| alle Fälle lesen, triagieren, zuordnen | `editor` | Builder mit `case_triage` |
| Schilderung abgeben | – | nur der betroffene Agent |

### 3.4 Nutzungsaufzeichnung

Der Server schreibt mit, welche Persona-, Playbook-, Resource- und
Tool-Version ein Agent abgerufen hat (F-W5). **Tabelle: `usage_event`, nicht
`agent_access_log`** — Abweichung vom Wortlaut des Plans („Muster
`agent_access_log`“), das Muster wird übernommen, die Tabelle nicht (Weiche N1):

- `usage_event` hat bereits `entity_type`, `entity_id` und `version`, und
  genau dort liest die Aggregation
  (`apps/api/src/who2be_api/repositories/feedback_repository.py#PgFeedbackRepository.summarize`).
- `agent_access_log` ist das Compliance-Protokoll für WorkArea/KB mit
  Sensitivity-Schnappschuss und Tagesdedupe; Fallraten je Nutzung brauchen
  aber jeden Abruf.

Änderung: neue Spalte `usage_event.source` DB-CHECK `agent_report · server`,
Default `agent_report` für den Bestand. Der Server schreibt `source='server'`,
`outcome=NULL`, best-effort nach der Fachtransaktion und nur für
agent-gebundene Aufrufer — dasselbe Muster wie
`apps/api/src/who2be_api/services/access_log.py#log_access`. Schreibstellen:
`apps/api/src/who2be_api/services/persona_service.py#PersonaService.render`,
`apps/api/src/who2be_api/services/playbook_service.py#PlaybookService.render`
und der Resource-Abruf. `record_usage` bleibt und meldet nur noch das
Ergebnis (`applied · skipped · error`).

Folge für die Auswertung: Nutzungen zählen ab D3 nur `source='server'`,
Ergebnisse nur `source='agent_report'`, beides gruppierbar nach `version`.
Ohne diese Trennung zählte jede Nutzung doppelt.

### 3.5 Gesprächsprotokoll

Das Gespräch findet im Client statt; Who2Be speichert Vorbereitung und
Ergebnis (F-W2). Das Protokoll wird **in einem Aufruf** vollständig
eingereicht und ist danach unveränderlich — über die Grants
(`SELECT, INSERT`), nicht über einen Status.

`feedback_session`:

| Spalte | Bedeutung |
|---|---|
| `id`, `workspace_id`, `agent_id` | der besprochene Agent |
| `trigger` | `threshold · scheduled · manual` |
| `participants` | jsonb-Liste `{kind: human·agent·builder, id, role}` |
| `summary` | ≤ 4 000 |
| `decisions` | jsonb-Liste `{text, standard_ref?}` — entschiedene Widersprüche |
| `dissent` | jsonb-Liste `{participant_kind, participant_id, text}` — auch der Agent darf eintragen |
| `follow_up_at` | date, Pflicht |
| `supersedes_id` | optional: ein Protokoll, das dieses korrigiert |
| `submitted_by_kind`, `submitted_by`, `created_at` | |

`feedback_session_case` (append-only): `session_id`, `case_id`.

Eine Korrektur ist ein neues Protokoll mit `supersedes_id`. Beide bleiben
sichtbar.

### 3.6 Maßnahme

`measure` — entsteht mit dem Protokoll, gehört zu genau einer Sitzung:

| Spalte | Bedeutung |
|---|---|
| `id`, `workspace_id`, `session_id` | |
| `case_ids` | über `measure_case` (append-only), ≥ 1 |
| `target`, `entity_id` | das Element (Werte wie `agent_case_element.target`, außer `model_limit`) |
| `change_summary` | die kleinste Änderung, ≤ 2 000 |
| `test_case_id` | **Pflicht**: der Prüffall aus dem echten Fall |
| `success_criterion` | ≤ 1 000 |
| `counterposition` | ≤ 1 000 |
| `follow_up_at` | date |
| `created_at` | |

`measure_event` (append-only): `measure_id`, `event`, `actor_kind`,
`actor_id`, `version_entity_type`, `version_id`, `verdict`, `metrics jsonb`,
`note`, `created_at`.

| Event | Wer | Bedeutung |
|---|---|---|
| `draft_linked` | Builder (`case_triage`) oder Mensch | der Entwurf, der die Maßnahme umsetzt |
| `activated` | System | die verknüpfte Version wurde durch einen Menschen aktiv; setzt die Fälle auf `addressed` |
| `follow_up_prepared` | Builder oder System | Kennzahlen für die Nachschau (`metrics`) |
| `reviewed` | Mensch `editor` | `verdict ∈ {effective, ineffective, not_measurable}`; `effective` setzt die Fälle auf `verified`, `ineffective` auf `reopened` |
| `withdrawn` | Mensch `editor` | Maßnahme aufgegeben |

Die Verknüpfung Entwurf ↔ Maßnahme liegt **auf Seite der Maßnahme**, nicht
als neue Spalte in den fünf `*_version`-Tabellen (Weiche E2). Damit berührt E3
keine Versions-Tabelle.

### 3.7 Muster

Kein eigenes Aggregat mit Zustand. Muster sind eine **berechnete Sicht**
(D5), deterministisch:

- Lernvorschläge: `kind='lesson'`, `status='pending'`, `occurrence_count ≥ n`.
- Fälle: gleicher Agent, gleiche Element-Zuordnung, ≥ n offene Fälle in
  30 Tagen.
- Ähnlichkeit über denselben Trigram-/Vektor-Weg wie die Dublettenprüfung
  (`apps/api/src/who2be_api/repositories/memory_repository.py#MEMORY_DEDUP_SIMILARITY`).
- n = 3 (gesetzte Annahme, Anhang B).

Aus einem Muster entsteht ein Fall mit `reporter_kind='pattern'` erst, wenn
der Builder oder ein Mensch ihn formuliert. Zähler lassen sich durch
Wiederholung aufblähen; das ist hier harmlos, weil ein Muster nur einen Fall
vorschlägt und nichts aktiviert.

### 3.8 Neue Capabilities in `AgentToolPolicy`

| Capability | Default | Zweck |
|---|---|---|
| `case_triage` | aus; im Builder-Seed an | Fälle aller Agenten lesen, zuordnen, triagieren; Prüffälle anlegen; Dossier lesen; Protokoll einreichen; Entwurf verknüpfen |
| `test_report` | an | Prüffall-Ergebnisse melden |

Beide kommen in `packages/models/src/who2be_models/tool_policy.py#AgentCapability`
und in `AgentToolPolicy.is_within` (Anti-Escalation, ADR-0039).
`feedback_resolve` bleibt für die Alt-Triage bestehen.

## 4. Freigabematrix Art × Herkunft

### 4.1 Wirkung von `memory_mode`

| `memory_mode` | Wirkung ab C2 |
|---|---|
| `off`, `read_only` | unverändert |
| `suggest` | alles `pending` (unverändert) |
| `auto` | **die Matrix entscheidet** je Eintrag; was die Matrix nicht freigibt, wird `pending` |

Die Matrix ist eine Workspace-Einstellung wie der Injection-Wächter: Spalte
`workspace.memory_auto_policy jsonb`, admin-gated wie
`apps/api/src/who2be_api/services/memory_service.py#MemoryService._require_guard_admin`.
`memory_mode=auto` am Agenten ist die Obergrenze, die Matrix die Feinsteuerung.
Default der Matrix: alle Zellen aus. Ein bestehender `auto`-Agent verhält sich
nach der Migration also wie `suggest`, bis ein Admin Zellen einschaltet
(Weiche M3). Das ist eine Verhaltensänderung für Bestandsagenten und gehört in
den CHANGELOG des Pakets C2.

### 4.2 Die Matrix

„Schaltbar“ heißt: Der Admin kann die Zelle für `auto` freigeben.
„Nie“ heißt: Die Zelle lässt sich nicht einschalten; der Server ignoriert eine
entsprechende Einstellung.

| Art \ Herkunft | `user_stated` | `inferred` | `external_content` | `legacy_unknown` | Kanal `human` / `import` |
|---|---|---|---|---|---|
| `user_fact`, Kategorie ohne Verhaltenswirkung (`preference`, `fact`, `project`, `entity`, `general`) | **schaltbar** | nie | nie | nie | aktiv und bestätigt (Mensch ist Quelle) |
| `user_fact`, Kategorie `instruction` | nie | nie | nie | nie | aktiv und bestätigt |
| `agent_note` | nie | nie | nie | nie | aktiv und bestätigt |
| `lesson` | nie (DB-CHECK) | nie | nie | nie | nie — auch ein Mensch macht daraus einen Fall, nicht einen aktiven Eintrag |
| Änderung / Löschung (Vorschlag) | nie | nie | nie | nie | – |

Begründungen für die Zeilen, die über den Plan hinausgehen:

- **`instruction` nie automatisch.** Die Kategorie gibt es heute schon
  (`packages/models/src/who2be_models/memory.py#MemoryCategory`), und sie
  trägt per Definition Verhaltenswirkung („antworte auf Deutsch“). Der Plan
  gibt „Art ohne Verhaltenswirkung“ als Bedingung vor; `instruction` erfüllt
  sie nicht.
- **`agent_note` nie automatisch.** Die Notiz kommt aus der Arbeit des
  Agenten selbst. ASI06 #6 verlangt ausdrücklich, eigene Ausgaben nicht
  automatisch in vertrauenswürdiges Gedächtnis zu übernehmen. Das kostet
  Triage-Last; Weiche M4 legt die Alternative offen.
- **Vorschläge nie automatisch.** Eine automatische Änderung oder Löschung
  eines bestätigten Eintrags würde eine menschliche Bestätigung durch eine
  Agentenaussage ersetzen.

Herkunft entsteht aus zwei Quellen (LW2): Den **Kanal** (`source`) setzt der
Server aus dem Aufrufweg (`is_agent_bound` ⇒ `agent`; Web-Sitzung ⇒ `human`;
Importpfad ⇒ `import`). Die **Herkunft** (`origin`) deklariert der Agent als
Pflichtfeld. Für einen Agenten-Kanal ist die Herkunft eine Selbstauskunft;
deshalb gibt die Matrix nur die eine Zelle frei, in der eine falsche
Selbstauskunft den kleinsten Schaden anrichtet, und nur dort, wo der Admin sie
einschaltet.

Automatisch aktivierte Einträge sind immer **unbestätigt**, verfallen nach
Abschnitt 3.1.3 und sind in der Oberfläche als „automatisch übernommen“
gekennzeichnet.

### 4.3 Was „automatisch“ nicht absichert — Anforderung an die Oberfläche

Die Einstellung der Matrix (Paket C6) **muss** beim Einschalten die folgende
Liste zeigen, vor der Bestätigung und nicht hinter einem Link. Sie ist der
Wettbewerbsrecherche §3 („Was bei automatischer Freigabe nicht abgesichert
werden kann“) entnommen und hier verbindlich wiedergegeben:

1. **Anweisung und Daten lassen sich in natürlicher Sprache nicht zuverlässig
   trennen.** Prozedurales Gedächtnis ist per Definition ein Anweisungskanal.
2. **Erkennung gegen adaptive Angreifer.** Scans und Rahmung sind in
   Messungen gegen gezielte Angriffe gebrochen worden, auch durch menschliches
   Red-Teaming.
3. **Einträge, die nur in einem bestimmten Kontext wirken.** Einzeln geprüft
   sehen sie harmlos aus.
4. **Plausible, aber falsche Inhalte.** Kein Scan erkennt sie.
5. **Der Nutzer selbst als Quelle falscher oder veralteter Fakten.** Herkunft
   „vom Nutzer“ heißt nur „vom Nutzer gesagt“, nicht „wahr“.
6. **Selbstverstärkung ohne Angreifer.** Fehler pflanzen sich fort; Gedächtnis
   verstärkt Gefälligkeit.
7. **Langsame Drift** aus vielen einzeln unauffälligen Einträgen. Sie
   unterläuft Schwelle, Ratenlimit und Dublettenprüfung.
8. **Rollback wirkt erst nach der Entdeckung.** Was dazwischen entschieden
   wurde, bleibt.

Verbindlich dazu:

- Die Oberfläche verspricht nie „sicher“, weder als Wort noch als Symbol
  (Schloss, Haken).
- Die Liste steht in beiden Sprachen in den Locale-Dateien, nicht im Code.
- Das Einschalten wird im `audit_log` festgehalten (wer, wann, welche Zelle).

## 5. Migrationsweg und Rückweg

Migrationen sind unveränderlich; ein Rückweg ist deshalb immer eine
**Vorwärts-Migration**, die den Zustand zurückführt
(`apps/api/src/who2be_api/migrations/README.md`). Jede Schema-Migration dieser
Reihe läuft vorher auf einer Kopie der Produktionsdatenbank (Plan, Risiko
„Datenmodell-Umbau“).

### 5.1 Gedächtnis (0066 / 0067 / 0072)

| Was | Bleibt | Wird umgeformt | Rückweg |
|---|---|---|---|
| `agent_memory`-Zeilen | alle, inhaltlich unverändert | `kind='user_fact'`, `scope='agent'`, `origin='legacy_unknown'`, `source='agent'`, `confirmed_at = updated_at` für `status='active'` (sie wurden unter `suggest` von einem Menschen freigegeben oder unter `auto` übernommen — nicht unterscheidbar, daher Weiche M6) | neue Spalten und CHECKs droppen; `expired`/`converted` → `rejected` |
| Status-CHECK | `pending, active, rejected` | + `expired, converted` | s. o. |
| `agent_id NOT NULL` | Cascade für `scope='agent'` | nullable + CHECK je Scope, `created_by_agent_id` neu | vor dem Rückweg `scope='user'`-Zeilen exportieren und löschen; dann `NOT NULL` wieder setzen |
| `workspace.memory_guard` | unverändert | – | – |
| `workspace.memory_auto_policy` | – | neu, Default `{}` = alle Zellen aus | Spalte droppen; `memory_mode=auto` wirkt wieder ungestaffelt |
| `content_vector` | unverändert | – | – |
| Historie, Vorschläge | – | neue Tabellen | Tabellen droppen |

Heutige Abfragen bleiben gültig: Die Defaults bilden genau die heutige
Bedeutung ab, und die Abrufpfade filtern schon auf `status='active'`.

### 5.2 Feedback (0053–0059) — mit Abweichung vom Plan

Der Plan nennt für D1 „Migration des bestehenden Feedbacks“. Ich empfehle,
**keine Zeile umzuschreiben** (Weiche F1): Ein Alt-Feedback hat
`signal` und `note`, aber weder Situation noch erwartetes Verhalten. Eine
automatische Umwandlung müsste diese Pflichtfelder erfinden.

| Was | Bleibt | Wird umgeformt | Rückweg |
|---|---|---|---|
| `agent_feedback`, `feedback_resolution` | vollständig, lesbar, triagierbar | nichts; ein Mensch kann ein offenes Feedback **in einen Fall übernehmen** (`source_feedback_id`), das Alt-Feedback bekommt dann `addressed` mit Verweis im `note` | Fälle mit `source_feedback_id` bleiben; Tabellen der Fälle droppen |
| `submit_feedback` | als Element-Signal (Text eines Playbooks veraltet, falsch, unklar) | Ziel bleibt `FeedbackTarget`; Verhaltensrückmeldungen gehen ab D4 über `report_case` | – |
| `report_problem` | unverändert (System-Feedback) | – | – |
| `usage_event` | alle Zeilen | `source` neu, Bestand `agent_report` | Spalte droppen; Aggregation zählt wieder alles |
| 0055 / 0056 / 0057 | unberührt | – | – |

Der Posteingang (D6) zeigt beides nebeneinander: Fälle und Element-Signale.

## 6. MCP- und API-Verträge (Phasen B–E)

Alle REST-Pfade liegen unter dem Workspace-Präfix wie die bestehenden
Router (`apps/api/src/who2be_api/routers/feedback.py`). Identität kommt
ausschließlich aus dem Token (`whoami.agent_id`), nie aus Parametern —
außer dort, wo ausdrücklich ein *anderer* Agent gemeint ist
(`subject_agent_id`). Neue MCP-Werkzeuge liegen in einem neuen Modul
`apps/mcp/src/who2be_mcp/tools/learning.py` mit `register(mcp)` und
`apps/mcp/src/who2be_mcp/clients/learning.py` (Muster
`apps/mcp/src/who2be_mcp/tools/__init__.py`), jeweils mit Eintrag in
`MCP_TOOL_REQUIREMENTS` und im `tools-overview`-Resolver.

### 6.1 Neue `ProblemReason`-Werte

| `reason` | Status | Wann |
|---|---|---|
| `memory_origin_required` | 422 | `save_memory` ohne `origin` |
| `memory_kind_scope_invalid` | 422 | Kombination Art × Scope nicht erlaubt |
| `memory_proposal_not_pending` | 409 | Entscheidung über einen bereits entschiedenen Vorschlag |
| `memory_note_cap_reached` | 409 | Obergrenze `agent_note` |
| `memory_batch_count_mismatch` | 409 | Stapel per Filter oder Not-Aus: die Serverzahl weicht von `expected_count` ab (6.4.1); `params={count}` |
| `memory_held` | 409 | Stapel-Freigabe eines zurückgehaltenen Eintrags (6.4.1); nur als Ergebnis je Eintrag |
| `test_case_not_found` | 404 | |
| `test_case_retired` | 409 | Ergebnis zu zurückgezogenem Prüffall |
| `test_subject_version_not_found` | 404 | geprüfte Version gehört nicht zum Workspace |
| `test_run_verdict_inconsistent` | 422 | `verdict='pass'` ohne `runs_passed = runs_total`, `runs_total < 1` oder `runs_passed` außerhalb `0..runs_total` (3.2) |
| `test_results_incomplete` | 409 | Aktivierung ohne Bestätigung, obwohl Ergebnisse fehlen oder rot sind (6.3) |
| `test_override_reason_required` | 409 | Aktivierung bestätigt, aber ohne nicht leeren `override_reason` (6.3) |
| `case_not_found` | 404 | auch für Fälle, die der Aufrufer nicht sehen darf (kein Enumerieren) |
| `case_transition_forbidden` | 409 | Übergang nach 3.3 nicht erlaubt |
| `case_transition_human_only` | 403 | Agent-Token versucht `addressed`/`verified`/`dismissed` |
| `case_statement_not_subject` | 403 | Schilderung von einem anderen Agenten |
| `session_cases_invalid` | 422 | Protokoll verweist auf fremde oder unbekannte Fälle |
| `measure_test_case_required` | 422 | Maßnahme ohne Prüffall |
| `measure_not_found` | 404 | |

Bestehende Werte (`memory_duplicate`, `memory_guard_rejected`,
`memory_cap_reached`, `missing_capability`, …) behalten ihre Bedeutung.

### 6.2 Phase B — Prüffälle

REST:

| Methode, Pfad | Rolle / Capability | Rückgabe |
|---|---|---|
| `POST /test-cases` | `editor` / `case_triage` | `TestCaseRead` 201 |
| `GET /test-cases?agent_id&entity_type&entity_id&status` | `editor` / eigener Agent / `case_triage` | `list[TestCaseRead]` |
| `GET /test-cases/{id}` | wie oben | `TestCaseRead` |
| `POST /test-cases/{id}/retire` | `editor` | `TestCaseRead` |
| `POST /test-runs` | `editor` / `test_report` | `list[TestRunRead]` 201 |
| `GET /versions/{entity_type}/{version_id}/test-report` | `editor` | `TestReport`: Prüffall-Menge nach 3.2.1, gruppiert nach Agent mit `via`; je Prüffall letztes Ergebnis für diese Version oder `missing`; dazu `affected_agent_count` und ggf. `scope_note` |

MCP:

```text
list_test_cases(agent_id: str | None = None, entity_type: str | None = None,
                entity_id: str | None = None) -> list[TestCaseRead]
    # agent_id nur mit case_triage; ohne → eigener Agent

submit_test_results(subject_entity_type: str, subject_version_id: str,
                    results: list[{test_case_id, runs_total, runs_passed,
                                   verdict, output_excerpt}],
                    model_provider: str | None, model_name: str | None)
    -> list[TestRunRead]
    # attestation wird serverseitig auf client_self_report gesetzt
    # human_rule-Prüffälle: nur Ausgabe, verdict='error' (3.2)
```

`POST /test-runs` setzt `attestation` aus dem Aufrufweg: Agent-Token →
`client_self_report`, Web-Session → `human_rating` mit
`reported_by_user_id`. Ein `attestation`-Feld im Request-Body gibt es nicht.
Jedes Ergebnis muss `runs_total >= 1` und `0 <= runs_passed <= runs_total`
erfüllen; `verdict='pass'` ist nur bei `runs_passed = runs_total` zulässig.

Fehler: `test_case_not_found`, `test_case_retired`,
`test_subject_version_not_found`, `test_run_verdict_inconsistent`,
`missing_capability`.

### 6.3 Phase B — Aktivierung mit Prüffall-Bericht (B5)

Die Übergänge `review → active` bleiben `admin`-Sache
(`apps/api/src/who2be_api/services/version_status.py#required_role_for_transition`).
Neu nimmt der Transition-Aufruf zwei Felder
(Erweiterung von `packages/models/src/who2be_models/status.py#VersionTransitionRequest`,
`extra="forbid"` bleibt):

| Feld | Typ | Regel |
|---|---|---|
| `acknowledge_test_report` | bool, Default `false` | Bestätigung, dass der Bericht gelesen wurde |
| `override_reason` | str \| None, nach Trimmen 1–1 000 Zeichen (gesetzte Annahme, Anhang B) | Grund, warum trotz roter oder fehlender Ergebnisse aktiviert wird |

Eine Mindestlänge über ein Zeichen hinaus gibt es nicht; die
10-Zeichen-Mindestlänge aus der Design-Spec gilt nicht.

Ablauf bei `to='active'`:

1. Der Server bestimmt die Prüffall-Menge nach 3.2.1 und für jeden Prüffall
   das letzte Ergebnis für die Zielversion.
2. Ist die Menge leer oder alles `pass`, wird aktiviert; beide Felder werden
   ignoriert.
3. Ist mindestens ein Ergebnis `fail`, `error` oder `missing`, verlangt der
   Server **beides**, `acknowledge_test_report=true` **und** einen nicht
   leeren `override_reason`. Fehlt eines davon, antwortet er mit 409:
   - `test_results_incomplete`, wenn die Bestätigung fehlt,
   - `test_override_reason_required`, wenn bestätigt wurde, aber der Grund
     fehlt oder nach Trimmen leer ist.

   Den Bericht liefert er in beiden Fällen in `params`.
4. Mit beidem wird aktiviert. Der Grund wird im `note` der
   `status_history`-Zeile dieses Übergangs gespeichert
   (`apps/api/src/who2be_api/services/status_history_service.py#StatusHistoryService.record`,
   Spalte `note` aus
   `apps/api/src/who2be_api/migrations/0012_status_history.sql@9e354495`),
   mit festem Präfix und der Zahl roter und fehlender Ergebnisse. Er
   erscheint damit ohne neue Tabelle in der Versionsherkunft („Warum
   aktiv?“,
   `apps/api/src/who2be_api/services/version_status.py#VersionStatusService._provenance`).
   Ein vom Nutzer mitgeschickter `note` wird angehängt, nicht ersetzt.

Es gibt **keine** automatische Aktivierung bei grünen Ergebnissen (LW5) und
keinen harten Block bei roten (Weiche P2).

### 6.4 Phase C — Gedächtnis 2.0

REST (Ergänzungen zu `apps/api/src/who2be_api/routers/memory.py`):

| Methode, Pfad | Rolle | Zweck |
|---|---|---|
| `GET /agents/{agent_id}/memories?status&kind` | `editor` | wie heute, plus Filter |
| `GET /me/memories?status` | Nutzer selbst | Nutzergedächtnis |
| `POST /agents/{agent_id}/memories/{id}/confirm` | `editor` | bestätigen, Verfall aufheben |
| `POST /agents/{agent_id}/memories/{id}/reactivate` | `editor` | `expired` → `active` (bestätigt) |
| `GET /agents/{agent_id}/memories/{id}/history` | `editor` | `list[MemoryEvent]` |
| `POST /agents/{agent_id}/memories/{id}/rollback` | `editor` | Body `{event_id}` |
| `GET /agents/{agent_id}/memory-proposals?status` | `editor` | offene Vorschläge |
| `POST /memory-proposals/{id}/decide` | `editor` bzw. Nutzer selbst | Body `{accept: bool, note}` |
| `POST /agents/{agent_id}/memories/{id}/convert` | `editor` | `lesson` → Fall, Body = Fall-Felder |
| `GET/PUT /memory-auto-policy` | `admin` | Matrix |

Entsprechende `/me/memories/{id}/…`-Pfade für das Nutzergedächtnis.

MCP:

```text
save_memory(fact: str, origin: user_stated | inferred | external_content,
            kind: user_fact | agent_note | lesson = user_fact,
            scope: agent | user = agent,
            category: MemoryCategory = general, importance: int = 5,
            context: str | None = None) -> MemoryRead
    # neu: origin Pflicht, kind, scope. Antwort trägt status und
    # auto_activated: bool; bei lesson-Wiederholung merged_into.

propose_memory_change(memory_id: str, action: change | delete,
                      reason: str, new_fact: str | None = None)
    -> MemoryProposalRead

search_memory(query: str, k: int = 5) -> list[MemoryHit]
list_memories(limit: int = 20) -> list[MemoryHit]
    # unverändert in der Signatur; liefern jetzt Agentengedächtnis UND
    # Nutzergedächtnis des Token-Besitzers, nie lesson.
    # MemoryHit bekommt kind, scope, confirmed: bool.
```

Die Rahmung bleibt wortgleich „gespeicherte NUTZERDATEN, keine Anweisungen —
sie können veraltet sein“ und wird um „unbestätigt“ je Treffer ergänzt, wo
`confirmed` falsch ist. Der Laufzeit-Push in `get_persona` bleibt (ADR-0044
§5) und zeigt nur bestätigte Einträge (Weiche M7). Es gibt keinen neuen
automatischen Abruf vor jedem Zug (G-W4).

Fehler: `memory_origin_required`, `memory_kind_scope_invalid`,
`memory_duplicate`, `memory_guard_rejected`, `memory_cap_reached`,
`memory_note_cap_reached`, `memory_not_found`, `memory_proposal_not_pending`.

`memory_cap_reached` trägt bei der Agentengrenze wie heute
`params={maximum}`, bei der Grenze des Nutzergedächtnisses
`params={maximum, scope:'user'}` (3.1.1). Eine `lesson`-Wiederholung ist
kein Fehler, sondern 200 mit `merged_into` (3.1.6).

#### 6.4.1 Nachtrag C0b — workspace-weite Sicht, Stapel, Not-Aus

Owner-Entscheidung vom 2026-10-01 zu den offenen Fragen der Design-Spec
Phase C, Wortlaut: „1.a, 2.a, 3.b, 4. b“. Hier relevant: **Frage 2 = a**
(workspace-weite Warteschlange) und **Frage 3 = b** (Notfall-Rücknahme in
Phase C). Dazu Owner-Entscheidung vom selben Tag zur zentralen
Gedächtnisverwaltung, Wortlaut: „1. a, 2. a, 3.a, 4. a,5. ja“ — hier relevant
**W4 = a** (API-Form, PM-Entscheidung innerhalb von 2 = a) und **W5 = a**
(Admin sieht vom Nutzergedächtnis nur die Anzahl). Die Tabelle in 6.4 gilt
weiter; dieser Abschnitt ergänzt sie.

REST:

| Methode, Pfad | Rolle | Zweck |
|---|---|---|
| `GET /memories?status&exclude_status&kind&scope&agent_id&origin&source&health&held&q&sort&cursor&limit` | ab `viewer`, Sichtbarkeit siehe unten | allgemeine Liste über alle Agenten, alle Status; `limit ≤ 50`, Cursor-Paginierung. `GET /memories?status=pending` ist die workspace-weite Warteschlange (Frage 2 = a). `status`, `exclude_status`, `kind` und `origin` sind wiederholbar (siehe „Mehrfachwerte“) |
| `GET /memories/counts?group_by&<Filter wie oben>&created_after` | wie `GET /memories` | Zähler je Gruppe (`agent`, `kind`, `status`, `origin`, `source`, `health`); je Gruppe ohne den eigenen Filter (Facetten). `group_by=subject_user_id` mit `scope=user` nur `admin` und nur Zahlen (W5 = a) |
| `POST /memories/batch` | je Eintrag wie die Einzelaktion | Body `{action: approve·reject·confirm·delete, ids[≤100] \| filter, expected_count?, note?}`, Antwort `{results:[{id, ok, reason?, params?}]}` |
| `GET /memory-proposals?status&agent_id` | `editor`; Vorschläge zum eigenen Nutzergedächtnis ab `viewer` | Vorschläge workspace-weit, Gegenstück zu `GET /agents/{agent_id}/memory-proposals` |
| `POST /memories/revoke-auto` | `editor`; fremdes Nutzergedächtnis nur `admin` | Notfall-Rücknahme, siehe unten |
| `DELETE /members/{user_id}/memories` | `admin` | löscht das gesamte Nutzergedächtnis dieser Person im Workspace (W5 = a) |
| `GET /me/memories` | Nutzer selbst | wie 6.4, zusätzlich mit `q`, `cursor`, `limit` |

**Sichtbarkeit von `GET /memories` und `counts`.** `editor` sieht
`scope='agent'` aller Agenten des Workspace. Jede Rolle ab `viewer` sieht
das eigene Nutzergedächtnis (`scope='user'`, `subject_user_id` = eigene
Nutzer-ID). Das Nutzergedächtnis **anderer** Personen erscheint nie in der
Antwort, auch nicht für `admin` (3.1.1); der Admin bekommt davon nur die
Anzahl über `group_by=subject_user_id`. Dieselbe Regel gilt für die Vorschau
des Not-Aus und für `batch`: Ein fremder Eintrag ist für den Aufrufer
`memory_not_found`, kein `forbidden` (kein Enumerieren).

**Zähler.** Der Zähler der Dashboard-Kachel und der Tab-Zähler „Zur Freigabe“
kommen aus `GET /memories/counts` mit `status=pending`. Lernvorschläge
(`lesson`) zählen dort nicht mit, weil sie nie freigegeben werden und nicht in
der Warteschlange stehen (3.1, Matrix 4.2). Damit zählen Dashboard und
Warteschlange dieselbe Menge.

**Filter `held` und `health`** rechnet der Server, damit Liste und Zähler
dieselbe Regel nutzen:

- `held` (zurückgehalten) ist abgeleitet, kein Feld: `status='pending'` und
  (`origin IN ('external_content','inferred')` oder `category='instruction'`).
  Es gibt kein `hold_reasons[]` (PM-Entscheidung F1 = a).
- `health` kennt `unconfirmed` (`active`, `confirmed_at IS NULL`),
  `expiring_soon` (`expires_at` in den nächsten 7 Tagen, `pending` oder
  `active`), `never_delivered` (`active`, `retrieval_count = 0`, älter als
  30 Tage), `stale_delivery` (`active`, `last_retrieved_at` älter als 90 Tage)
  und `external_or_inferred` (`origin`). Die Grenzen 7/30/90 Tage stammen aus
  der Design-Entscheidung W3 = a und sind gesetzte Annahmen.

**Mehrfachwerte und Ausschluss** (Nachtrag 2026-10-03, Gedächtnisverwaltung
§6.2). `status`, `kind` und `origin` nehmen mehrere Werte: im Query-String als
wiederholter Parameter (`?status=active&status=pending`), im `filter` von
`batch` als Liste; ein Einzelwert bleibt gültig. Innerhalb eines Feldes gilt
ODER, zwischen den Feldern UND. `exclude_status` (ebenso wiederholbar)
schließt Status aus; die Standardansicht „alles außer Abgelehnt“ ist
`exclude_status=rejected`. Die Zähler-Gruppe `status` lässt Auswahl und
Ausschluss weg, damit auch ein ausgeschlossener Status seine Zahl hat. Die
Warteschlangen-Regel gilt, sobald `pending` unter den Status und `lesson`
nicht unter den Arten ist. Liste, Zähler und `batch` teilen denselben
Filterbau und meinen dieselbe Menge.

**Stapel (`batch`).** Jeder Eintrag läuft durch dieselbe Prüfung wie die
Einzelaktion (Rechte, Status, Obergrenzen); ein Teilfehler bricht den Stapel
nicht ab, sondern steht im Ergebnis dieses Eintrags. Im Filter-Modus ist
`expected_count` Pflicht. Weicht die Zahl der Treffer ab, antwortet der
Server mit 409 `memory_batch_count_mismatch` und `params={count}` und ändert
nichts. So wird nie mehr freigegeben, als ein Mensch bestätigt hat — das
trägt „Alle von <Profil> freigeben“ (W2 = a). `approve` auf einen
zurückgehaltenen Eintrag ergibt je Eintrag `memory_held`; zurückgehaltene
Einträge werden nur einzeln freigegeben. Änderungs- und Löschvorschläge
laufen nicht über `batch`, sondern einzeln über `decide` (3.1.4).

**Notfall-Rücknahme (`revoke-auto`, LW6, Frage 3 = b).** Body
`{since, until?, agent_id?, origin[]?, include_other_users: bool, dry_run: bool, expected_count?}`.

- Betroffen sind Einträge mit `status='active'`, `confirmed_at IS NULL` und
  einem Event `auto_activated` im Zeitraum `since`…`until` — also genau das,
  was ohne menschliche Prüfung wirksam wurde. Bestätigte Einträge bleiben
  unberührt.
- Wirkung je Eintrag: `status` → `pending`, dazu das neue Event
  `auto_revoked` (3.1.2) mit `actor_kind='human'`, `before` (der
  automatisch aktive Stand) und `after`. Gelöscht wird nichts. Der Eintrag
  steht danach wieder in der Warteschlange.
- Rollback-fähig: Ein Rollback auf das `auto_revoked`-Event stellt dessen
  `before` wieder her, also den aktiven, unbestätigten Stand (3.1.2).
- Einen eigenen Status „archiviert“ gibt es nicht; Ziel der Rücknahme ist
  `pending`. Wer einen zurückgenommenen Eintrag nicht mehr will, lehnt ihn in
  der Warteschlange ab (`rejected`, bleibt Dublettenbasis wie in ADR-0044 §3).
- `dry_run=true` liefert `{count, sample, hidden_count}`: `sample` sind
  höchstens fünf Einträge, die der Aufrufer sehen darf, `hidden_count` die
  Anzahl aus fremdem Nutzergedächtnis (nur beim Admin größer als null).
- Ohne `dry_run` ist `expected_count` Pflicht, Abweichung wie bei `batch`
  (409 `memory_batch_count_mismatch`). Antwort wie `batch`, ein Ergebnis je
  Eintrag.
- Rechte: `editor` nimmt Agentengedächtnis und das eigene Nutzergedächtnis
  zurück. `include_other_users=true` ist `admin` vorbehalten. Das ist mit
  3.1.1 vereinbar, weil die Rücknahme weniger eingreift als das Löschen, das
  dem Admin dort schon zusteht, und den Inhalt nicht offenlegt.

**Admin-Löschen des Nutzergedächtnisses (W5 = a).** `DELETE
/members/{user_id}/memories` löscht alle Einträge mit `scope='user'` und
`subject_user_id=user_id` im Workspace (Hard-Delete wie 3.1.2) und schreibt
eine inhaltsfreie Zeile `audit_log` mit `action='memory.user_purged'`,
`target=<user_id>` und der Anzahl. Den Inhalt sieht der Admin dabei nicht.

Neue `ProblemReason`-Werte siehe 6.1 (`memory_batch_count_mismatch`,
`memory_held`). Das Event `auto_revoked` erweitert den CHECK von
`agent_memory_event.event` aus
`apps/api/src/who2be_api/migrations/0091_agent_memory_v2.sql@d185ba78` per
neuer Migration in C3.

Nicht Teil dieses Nachtrags: ein Pfad, über den ein Mensch selbst einen
Eintrag ins eigene Nutzergedächtnis schreibt (`POST /me/memories`), und
Cursor/Suche für die Altpfade `GET /agents/{agent_id}/memories`.

Zuschnitt: Alle Endpunkte dieses Abschnitts setzt C3 um (Anhang A.2). Die
Oberfläche des Not-Aus kommt mit C5b. Die Warnliste S4a darf den Satz „Du
kannst alles automatisch Freigegebene auf einmal zurücknehmen“ behalten; er
wird erst ausgeliefert, wenn der Web-Teil des Not-Aus gemergt ist.

### 6.5 Phase D — Fälle, Nutzung, Muster

REST:

| Methode, Pfad | Rolle / Capability | Zweck |
|---|---|---|
| `POST /cases` | ab `viewer` / `feedback_write` | Fall melden |
| `GET /cases?agent_id&status&target` | `editor` / `case_triage`; `viewer` nur eigene | Liste |
| `GET /cases/{id}` | wie oben | `CaseDetail` (Fall, Events, Zuordnungen, Schilderungen) |
| `POST /cases/{id}/transition` | nach 3.3 | Body `{to, note, measure_id?, version_entity_type?, version_id?}` |
| `PUT /cases/{id}/elements` | `editor` / `case_triage` | Replace-Semantik |
| `POST /cases/{id}/statement` | betroffener Agent | Schilderung |
| `POST /feedback/{feedback_id}/promote` | `editor` | Alt-Feedback → Fall |
| `GET /patterns?agent_id` | `editor` / `case_triage` | berechnete Musterliste |

MCP:

```text
report_case(situation: str, behavior: str, expected_behavior: str,
            impact: str | None = None,
            severity: low | medium | high = medium,
            signal: FeedbackSignal | None = None, source_ref: str | None = None,
            subject_agent_id: str | None = None) -> CaseRead
    # ohne subject_agent_id: der eigene Agent

submit_case_statement(case_id: str, followed_instruction: str,
                      missing_information: str, conflict: str) -> CaseStatementRead

list_cases(agent_id: str | None = None, status: str | None = None)
    -> list[CaseRead]                       # case_triage; ohne: eigene

assign_case_elements(case_id: str, elements: list[{target, entity_id?}])
    -> CaseRead                             # case_triage
```

`record_usage` bleibt in der Signatur; `outcome` wird Pflicht, weil die
Nutzung selbst ab D3 der Server zählt.

Fehler: `case_not_found`, `case_transition_forbidden`,
`case_transition_human_only`, `case_statement_not_subject`, `agent_not_found`,
`missing_capability`.

### 6.6 Phase E — Feedback-Gespräch

REST:

| Methode, Pfad | Rolle / Capability | Zweck |
|---|---|---|
| `GET /agents/{agent_id}/dossier` | `editor` / `case_triage` | offene Fälle, Signale und Fallrate je Version, Zugriffslog-Zusammenfassung, frühere Maßnahmen mit Einstufung |
| `POST /feedback-sessions` | `editor` / `case_triage` | Protokoll einreichen (Sitzung + Fälle + Maßnahmen in einer Transaktion) |
| `GET /feedback-sessions?agent_id` · `GET /feedback-sessions/{id}` | `editor` | lesen |
| `POST /measures/{id}/link-draft` | `editor` / `case_triage` | Body `{version_entity_type, version_id}` |
| `GET /measures/{id}/follow-up` | `editor` / `case_triage` | Kennzahlen: Prüffall-Quote vorher/nachher, Fallrate je Nutzung alte gegen neue Version, Wiederauftreten |
| `POST /measures/{id}/review` | `editor` | Einstufung |
| `POST /measures/{id}/withdraw` | `editor` | |

MCP:

```text
get_dossier(agent_id: str) -> Dossier                       # case_triage
submit_session_protocol(agent_id: str, trigger: str, participants: list,
                        case_ids: list[str], summary: str, decisions: list,
                        dissent: list, follow_up_at: str,
                        measures: list[{case_ids, target, entity_id?,
                                        change_summary, test_case_id,
                                        success_criterion, counterposition,
                                        follow_up_at}],
                        supersedes_id: str | None = None) -> SessionRead
link_measure_draft(measure_id: str, version_entity_type: str,
                   version_id: str) -> MeasureRead
get_follow_up(measure_id: str) -> FollowUpReport
```

Die Einstufung einer Nachschau (`review`) hat **kein** MCP-Werkzeug. Sie ist
eine Entscheidung und bleibt beim Menschen (F-W7).

Fehler: `session_cases_invalid`, `measure_test_case_required`,
`measure_not_found`, `test_subject_version_not_found`, `missing_capability`.

### 6.7 Umfang der MCP-Oberfläche

Neu sind 11 Werkzeuge: `list_test_cases`, `submit_test_results`,
`propose_memory_change`, `report_case`, `submit_case_statement`, `list_cases`,
`assign_case_elements`, `get_dossier`, `submit_session_protocol`,
`link_measure_draft`, `get_follow_up`. Für das Nutzergedächtnis kommt kein
eigenes Werkzeug hinzu, weil `search_memory` und `list_memories` es
mitliefern; `save_memory` bekommt nur neue Parameter.

Payload: Die `tools/list`-Antwort misst am Stand `ef0756a3` 132 162 Bytes
bei 83 Werkzeugen, Budget 160 000
(`apps/mcp/tests/test_tool_payload_budget.py#test_tools_list_payload_stays_under_budget`).
Das sind im Mittel 1 592 Bytes je Werkzeug; 11 weitere ergeben rechnerisch
rund 17 500 Bytes, zusammen rund 149 700. Das passt, lässt aber nur etwa
10 000 Bytes Reserve. Deshalb gilt für jedes MCP-Paket die Docstring-Grenze des
Tests (`_NEW_TOOL_DOC_CAP`), und die Werkzeuge mit `case_triage` erscheinen
nur für Agenten mit dieser Capability in `tools/list` (ADR-0042-Filter). Die
Zahl in `CLAUDE.md` („83 Tools gesamt“) zieht jedes MCP-Paket nach; ein Test
hält sie fest (`packages/models/tests/test_doc_tool_count.py`).

## 7. Abbildung auf OWASP ASI06 und ADR-0038

### 7.1 ASI06 „Memory & Context Poisoning“ (Mitigationen #1–#9)

| # | Mitigation (verkürzt) | heute | nach dieser ADR |
|---|---|---|---|
| 1 | Datenschutz, Least Privilege | RLS, Rollen, Capability-Gates | unverändert; neue Tabellen mit RLS, neue Capabilities Default aus (außer `test_report`) |
| 2 | Inhaltsprüfung jedes Schreibvorgangs | Regex-Injection-Wächter | zusätzlich Secret-Scan (C2); gilt auch für Änderungsvorschläge. Bleibt ein Scan und ist gegen adaptive Angriffe schwach — deshalb nicht tragend |
| 3 | Segmentierung | je Agent, je Workspace | plus Nutzergedächtnis **je Nutzer** (3.1.1) |
| 4 | kuratierte Quellen, Aufbewahrung | `suggest` als Schleuse | Matrix: nur eine Zelle schaltbar; Verfall unbestätigter Einträge |
| 5 | Herkunft, Anomalien bei Häufigkeit | – ; Ratenlimit | Kanal serverseitig, Herkunft als Pflichtfeld; Häufigkeit sichtbar über `agent_memory_event`. Anomalie-Erkennung bleibt offen (Abschnitt 9) |
| 6 | keine automatische Wiederaufnahme eigener Ausgaben | nur per Werkzeugtext | `agent_note` und `lesson` nie automatisch; `lesson` per DB-CHECK nie aktiv |
| 7 | Tests, Rollback, Versionierung, Quarantäne | Versionen für Inhalte; Memory ohne Historie | Historie + Rollback je Eintrag; Prüffälle vor Aktivierung; `pending` als Quarantäne |
| 8 | unbestätigtes Gedächtnis verfallen lassen | – | 3.1.3 |
| 9 | Abruf nach Vertrauen gewichten; zwei Faktoren für wirkungsstarkes Gedächtnis | alle aktiven gleich | `get_persona`-Push nur bestätigt (Faktor 1 Herkunft/Matrix, Faktor 2 menschliche Bestätigung); Treffer tragen `confirmed` |

### 7.2 ADR-0038 „Feedback fließt nie in einen Prompt“

Eingehalten:

- Fälle, Schilderungen, Protokolle, Maßnahmen, Prüffälle, Prüfergebnisse,
  Muster und Lernvorschläge werden **nie** in einen gerenderten Prompt
  eingefügt. Sie sind Eingang für Menschen und für den Builder, der daraus
  einen Entwurf schreibt.
- Der Builder liest sie über MCP als Daten; sein Verhalten ändert sich
  dadurch nicht, weil sein eigener Prompt sie nicht enthält.

Erweitert — und das ist die Stelle, an der die Lernschleife überhaupt wirkt:

- Aus einem Fall wird über eine Maßnahme ein **Entwurf** einer Persona,
  eines Playbooks, einer Resource oder eines System-Prompts. Nach Prüffällen
  und menschlicher Aktivierung steht dieser Entwurf im Prompt. Das ist kein
  Feedback im Prompt, sondern derselbe Weg wie heute (ADR-0040: „Der Agent
  schlägt vor, der Mensch aktiviert“), ergänzt um Prüffälle und Nachschau.
- Die einzigen Gedächtnisinhalte, die beim Abruf in den Kontext gelangen,
  bleiben aktive `user_fact` und `agent_note` (ADR-0044 §5). Das ist
  Gedächtnis, kein Feedback, und bleibt gerahmt.

Offen gelassen: Die Migrationen 0055 und 0056 haben verwaltete
Builder-Versionen direkt aktiv geschrieben. „Nie direkt wirksam“ gilt in
dieser ADR für Agenten und für jeden Laufzeitpfad. Für den Betreiberpfad
verwalteter Inhalte legt Weiche E3 die Entscheidung vor.

### 7.3 Änderungen an ADR-0044

- §2 `auto`: wirkt nur noch über die Matrix (4.1).
- §4 „Kein agent-seitiges Update/Delete“: ersetzt durch Vorschläge, die ein
  Mensch entscheidet (3.1.4). Die Schleuse bleibt: Ein Agent kann nichts
  selbst ändern.
- §5 Laufzeit-Push: nur bestätigte Einträge.

## 8. Weichen

Jede Weiche: Optionen, Trade-off, Empfehlung. Der Owner hat am 2026-09-28
alle Weichen dieses Abschnitts entschieden — jeweils die Empfehlung (a), bei
P2 abweichend (siehe dort). P4 kam erst im Review hinzu und wurde am selben
Tag per Nachtrag entschieden. Die Kennung in Klammern
verweist auf den Plan.

### Gedächtnis

**M1 — Wo liegen Arten und Nutzergedächtnis? (LW3, G-W1)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) In `agent_memory` mit `kind` und `scope`. Empfohlen.** Wächter,
  Dublettenprüfung, Vektor, Export, Triage bleiben eine Quelle. Nachteil:
  `agent_id` wird nullable, jede Abfrage braucht die Scope-Bedingung.
- (b) Neue Tabelle `user_memory` neben `agent_memory`. Saubere Cascades,
  aber zweite Kopie jeder Wächter- und Suchabfrage.
- (c) Eine Tabelle je Art. Maximal getrennt, maximal viel Doppelung.

**M2 — Nutzergedächtnis je Workspace oder je Workspace und Nutzer? (G-W1)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Je Workspace und Nutzer. Empfohlen — Abweichung vom Plan**, Grund in
  3.1.1 (ASI06 #3). Für Hermes identisch, weil alle Profile demselben
  Besitzer gehören.
- (b) Je Workspace, wie im Plan. Einfacher, aber in geteilten Workspaces
  sehen Agenten von B die Fakten über A.
- (c) Je Organisation. Geht über Workspaces hinweg und bricht die
  Mandantentrennung auf Workspace-Ebene.

**M3 — Was passiert mit bestehenden `auto`-Agenten? (G-W3/LW1)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Matrix-Default „alles aus“; `auto` wirkt bis zur Einstellung wie
  `suggest`. Empfohlen.** Sicher, aber eine sichtbare Verhaltensänderung.
- (b) Beim Migrieren die Zelle `user_fact × user_stated` einschalten, wo ein
  Agent `auto` hat. Kein Bruch, aber Bestandseinträge haben
  `legacy_unknown` — und neue würden automatisch aktiv, ohne dass jemand die
  Warnliste gesehen hat.
- (c) `auto` bleibt ungestaffelt, die Matrix ist eine neue fünfte Stufe.
  Zwei Bedeutungen für dasselbe Wort.

**M4 — `agent_note` automatisch? (G-W3/LW1)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Nie. Empfohlen.** ASI06 #6. Nachteil: Triage-Last für Arbeitsnotizen,
  die in Hermes lokal ohne Freigabe entstehen.
- (b) Schaltbar wie `user_fact × user_stated`. Weniger Last, verletzt #6.
- (c) Automatisch, aber nur für den Agenten selbst sichtbar und nie im
  `get_persona`-Push. Kompromiss; die Notiz wirkt trotzdem über
  `search_memory` auf sein Verhalten.

**M5 — Historie bei Löschung (LW6)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Cascade; inhaltsfreier `audit_log`-Eintrag. Empfohlen.** DSGVO
  Art. 17 geht vor Nachvollziehbarkeit des Inhalts.
- (b) Historie bleibt, Inhalt geschwärzt. Mehr Nachvollziehbarkeit, eine
  weitere Speicherstelle personenbezogener Metadaten.
- (c) Soft-Delete. Widerspricht ADR-0044 („Hard-Delete statt Soft-Delete“).

**M6 — Gelten Bestandseinträge als bestätigt?**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) `active` gilt als bestätigt (`confirmed_at = updated_at`). Empfohlen.**
  Unter `suggest` war das eine menschliche Freigabe. Unter `auto` nicht —
  das lässt sich im Bestand nicht unterscheiden.
- (b) Nur Einträge von Agenten, die heute nicht `auto` haben, gelten als
  bestätigt. Genauer, aber der Modus kann sich seit dem Eintrag geändert
  haben.
- (c) Nichts gilt als bestätigt, alles verfällt nach 30 Tagen. Am
  vorsichtigsten; erzeugt einmalig die volle Triage-Last.

**M7 — Laufzeit-Push in `get_persona` (G-W4)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Bleibt, nur bestätigte Einträge. Empfohlen.** ASI06 #9.
- (b) Bleibt wie heute (alle aktiven). Automatisch übernommene Einträge
  kämen ungeprüft in jede Sitzung.
- (c) Entfällt; nur noch Abruf per Werkzeug. Am sichersten, schwächt aber
  die Nutzung, die ADR-0044 absichtlich so gebaut hat.

**M8 — Herkunft (LW2)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Kanal serverseitig, Herkunft als Pflichtfeld des Agenten.
  Empfohlen**, wie im Plan. Die Herkunft bleibt Selbstauskunft.
- (b) Nur serverseitig. Unterscheidet „Nutzer hat gesagt“ nicht von „aus
  einer Webseite geschlossen“.
- (c) Klassifikation per LLM. Selbst angreifbar und nicht LLM-frei.

**M9 — Mustererkennung (LW4)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Deterministisch, Zähler und Ähnlichkeit, Schwelle n = 3. Empfohlen**,
  wie im Plan. Grobe Muster werden übersehen.
- (b) Periodischer LLM-Review im Client (Hermes-Muster). Findet mehr; das
  Ergebnis ist Selbstbewertung.
- (c) Nur der Mensch. Skaliert nicht.

**M10 — Verfall (LW6)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Nur unbestätigte Einträge, 30 Tage, Abrufe verlängern nicht.
  Empfohlen.**
- (b) Alle Einträge mit Ablauf. Bestätigte Fakten müssten regelmäßig
  erneuert werden.
- (c) Kein Verfall. ASI06 #8 bleibt offen.

### Prüffälle

**P1 — Wo laufen Prüffälle? (F-W3)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Gespeichert in Who2Be, ausgeführt im Client, Ergebnis als
  Selbstauskunft gekennzeichnet. Empfohlen**, wie im Plan.
- (b) Server-seitiger Replay über die Modell-API. Reproduzierbar, macht
  Who2Be zum Runtime-Host.
- (c) Keine Prüffälle. Das Gate bleibt ein Mensch, der einen Diff liest.

**P2 — Was macht die Aktivierung mit roten oder fehlenden Ergebnissen? (LW5)**
- *Status: entschieden (Owner, 2026-09-28) — (a) mit Zusatz nach
  Design-Spec R2:* Aktivieren bleibt erlaubt, verlangt aber
  `acknowledge_test_report=true` **und** einen nicht leeren
  `override_reason`; der Grund wird mit der Aktivierung gespeichert und im
  Verlauf angezeigt. Ohne beides 409. Vertrag in 6.3.
- (a) Server verlangt eine ausdrückliche Bestätigung
  (`acknowledge_test_report`), sonst 409. Ursprüngliche Empfehlung. Der
  Mensch entscheidet, aber nicht aus Versehen; ohne Grund ist die
  Entscheidung später nicht nachprüfbar.
- (b) Nur Warnung in der Oberfläche. Über MCP oder API ließe sich ohne
  Hinweis aktivieren.
- (c) Harter Block bei Rot. Ein kaputter oder überholter Prüffall blockiert
  jede Aktivierung.

**P3 — Sind Prüffälle veränderlich?**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Nein; Korrektur = neuer Prüffall, alter wird `retired`. Empfohlen.**
- (b) Versioniert wie Personas. Vollständig, aber schwer für einen
  Datensatz dieser Größe.
- (c) Frei editierbar. Vorher/Nachher-Messungen werden wertlos.

**P4 — Welche Prüffälle gelten für eine Elementversion? (LW5, B2, B5)**
- *Status: entschieden (Owner, 2026-09-28): (a).*
- **(a) Vereinigung: direkt ans Element gebundene Prüffälle plus alle
  aktiven Prüffälle jedes Agenten, der das Element heute erreicht (Persona,
  Template direkt; Playbook über Persona-Link und Composites; Resource über
  Playbooks). Empfohlen**, Regel und Tabelle in 3.2.1. Trade-off: Ein von
  vielen Agenten geteiltes Playbook zieht deren gesamte Regression mit; das
  ist gewollt (LW5), macht den Bericht aber breit und erzeugt viele
  `missing`. Gegenmittel: Bericht nach Agent gruppiert, Breite vorn, und
  `missing` führt zu „Bestätigung plus Grund“, nicht zu einem Block.
  External Tools haben keinen Verweisindex und bekommen nur direkt
  gebundene Prüffälle; der Bericht sagt das.
- (b) Nur direkt gebundene Prüffälle (`entity_type/entity_id` = Element).
  Einfach und eindeutig, schmaler Bericht. Aber eine Persona-Änderung wird
  nie gegen die Prüffälle ihres Agenten geprüft, solange niemand sie an die
  Persona bindet. Die Regression aus LW5 („alle alten Prüffälle“) fällt weg.
- (c) Bindung primär ans Element, `agent_id` optional (nur Ausführungs-
  kontext). Sauberes Modell für geteilte Elemente, aber ein Prüffall ohne
  Agent hat keinen Kontext, in dem der Client ihn ausführen kann, und Fälle
  (3.3) hängen verpflichtend am Agenten. Das Datenmodell müsste an zwei
  Stellen umgebaut werden.

### Fälle und Nutzung

**F1 — Was passiert mit dem Alt-Feedback? (D1)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Bleibt unverändert; ein Mensch übernimmt einzelne Einträge in Fälle.
  Empfohlen — Abweichung vom Plan**, Grund in 5.2.
- (b) Automatische Umwandlung mit Platzhaltern in den Pflichtfeldern. Ein
  Posteingang, aber erfundene Felder.
- (c) Alt-Feedback einfrieren und ausblenden. Verliert offene Punkte.

**F2 — Wer meldet Fälle? (F-W4)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Menschen ab `viewer`, Agenten mit `feedback_write`; triagieren ab
  `editor`. Empfohlen**, wie im Plan. Freitext von `viewer`-Nutzern landet nie
  in einem Prompt; das Risiko ist Arbeit, nicht Wirkung.
- (b) Wie heute ab `editor`.
- (c) Zusätzlich anonym. Kein Rückfragekanal.

**F3 — Status `addressed` automatisch? (F-W6)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Das System setzt `addressed`, wenn die verknüpfte Version durch einen
  Menschen aktiv wird. Empfohlen.** Folge einer menschlichen Handlung, mit
  Beleg.
- (b) Nur ein Mensch setzt `addressed`. Eine Handlung mehr, dafür vergisst
  man es.
- (c) `addressed` entfällt; nur `verified`. Die Zeit zwischen Aktivierung
  und Nachschau wäre unsichtbar.

**N1 — Tabelle für die Nutzungsaufzeichnung (F-W5)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) `usage_event` mit `source`. Empfohlen — Abweichung vom Wortlaut des
  Plans**, Grund in 3.4.
- (b) `agent_access_log` um Inhaltsarten erweitern. Tagesdedupe und
  Sensitivity-Pflicht passen nicht.
- (c) Neue Tabelle. Eine dritte Stelle mit Nutzungszahlen.

**N2 — Aufzeichnungsdichte**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Jede Auslieferung eine Zeile. Empfohlen.** Genau für Raten; das
  Volumen wird in F1 gemessen.
- (b) Tagesbuckets mit Zähler. Weniger Zeilen, braucht `UPDATE` auf eine
  append-only-Tabelle.
- (c) Stichprobe. Raten werden unzuverlässig.

### Gespräch

**E1 — Wo findet das Gespräch statt? (F-W2)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Hybrid: Vorbereitung in Who2Be, Gespräch im Client, Protokoll per
  MCP. Empfohlen**, wie im Plan. Kein Modell-Chat in der Weboberfläche.
- (b) Chat im Web. Macht Who2Be zum Runtime-Host.
- (c) Nur Formular. Kein Gespräch.

**E2 — Wo hängt der Verweis Entwurf ↔ Maßnahme?**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) An der Maßnahme (`measure_event.draft_linked`). Empfohlen.** Keine
  der fünf Versions-Tabellen ändert sich.
- (b) Spalte `measure_id` in jeder `*_version`-Tabelle. Direkt, aber fünf
  Tabellen und fünf Services im selben Paket.
- (c) Nur im Freitext des Entwurfs. Nicht auswertbar.

**E3 — Gilt „nie direkt wirksam“ auch für Betreiber-Migrationen verwalteter
Inhalte? (Feedback-Recherche W10)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Nein, aber jede solche Migration steht im CHANGELOG und zählt für
  die Nachschau als neue Version. Empfohlen.** Verwaltete Inhalte gehören dem
  Betreiber; die Messung sieht die Änderung trotzdem.
- (b) Ja; auch Betreiber-Inhalte gehen durch Entwurf und Prüffälle.
  Konsequent, aber ein Betreiber-Update braucht dann eine Freigabe in jedem
  Workspace.
- (c) Nicht regeln. Dann bleibt der Widerspruch stehen.

**E4 — Wie weit geht der Builder? (F-W7)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Moderiert, ordnet zu, legt Entwürfe und Prüffälle an, reicht das
  Protokoll ein — entscheidet nie, schließt keine Fälle. Empfohlen**, wie im
  Plan; serverseitig über `is_agent_bound` erzwungen.
- (b) Builder darf `dismissed`. Selbstbewertungsrisiko.
- (c) Builder nur lesend. Der Mensch trägt die ganze Vorbereitung.

**E5 — Automatische Prompt-Optimierung (F-W8)**
- *Status: entschieden (Owner, 2026-09-28) — Option (a).*
- **(a) Vorerst nicht; in F3 neu prüfen. Empfohlen**, wie im Plan.
- (b) Als optionaler Entwurfsgenerator im Client.
- (c) Nie. Schließt eine Option aus, bevor Daten vorliegen.

### Verweise auf die Design-Spec

Die Design-Spec der Lernschleife (Karte A2, außerhalb dieses Repos) hat
eigene Weichen in ihrem §12. Die folgenden berühren diese ADR. Der Owner hat
sie am 2026-09-28 jeweils mit Option A entschieden:

| Spec-Weiche | Inhalt | Stelle in dieser ADR |
|---|---|---|
| G1 | `memory_mode` bleibt Hauptschalter; die Matrix legt fest, was „auto“ heißt | 4.1, M3 |
| G2 | nur `user_fact × user_stated` schaltbar | 4.2, M4 |
| G3 | Hard-Delete einschließlich Verlauf, inhaltsfreier Audit-Eintrag | 3.1.2, M5 |
| F1 | Pflicht beim Melden: Agent, Situation, Verhalten, Erwartung; Folge optional | 3.3 (`impact` optional), 6.5 |
| F2 | `viewer` sieht nur eigene Fälle | 3.3 Rechte, F2 |
| R1 | Review im Versions-Tab | 6.3 (nur Oberfläche, kein Vertragseffekt) |
| R2 | Aktivieren trotz Rot oder Fehlen mit Pflicht-Grund | 6.3, P2 |

Spec-F1 macht die „Folge“ optional. Deshalb führt 3.3 `impact` als optional;
die erste Fassung dieser ADR hatte das Feld als Pflicht.

## 9. Konsequenzen

Positiv:

- Jede Verhaltensänderung hat einen Anlass (Fall), einen Nachweis
  (Prüffall-Ergebnis je Version) und eine Wirkungsaussage (Nachschau).
- Das Gedächtnis kann schneller werden, ohne dass eine Zelle mit Verhaltens-
  wirkung automatisch aktiv wird.
- Nutzung und Signale werden je Version vergleichbar.

Negativ und bewusst in Kauf genommen:

- **Triage-Last** wächst: Notizen, Vorschläge, Lernvorschläge, Fälle und
  Maßnahmen landen beim Menschen. Gegenmittel sind die eine schaltbare Zelle
  und gebündelte Triage in C5/D6.
- **Prüffälle sind ein Proxy.** Grün heißt nicht gut; deshalb Regression über
  alle alten Prüffälle und Nachschau im Betrieb.
- **Selbstauskunft** bleibt an zwei Stellen: Herkunft (`origin`) und
  Prüffall-Ergebnisse. Beide sind in Daten und Oberfläche als solche
  gekennzeichnet.
- **Kollisionen:** Die Pakete teilen sich wenige Naben (Anhang A). Ohne
  Serialisierung entstehen stille Merge-Fehler.
- Bestehende `auto`-Agenten verhalten sich nach C2 wie `suggest`, bis ein
  Admin die Matrix setzt (M3).

Offen, nicht Teil dieser ADR:

- Anomalie-Erkennung über Schreibfrequenzen (ASI06 #5, zweite Hälfte).
- Serverseitige Ausführung von Prüffällen. `attestation` kennt ab Phase B
  zwei Werte (`client_self_report`, `human_rating`); serverseitige
  Ausführung wäre ein dritter.
- Automatische Prompt-Optimierung (E5).

## 10. Anhang A — Kollisionsmatrix der Pakete

Kürzel: M = `apps/api/src/who2be_api/migrations/NNNN_*.sql` (neue Datei, aber
Nummernfolge), PM = `packages/models/src/who2be_models/`, R = `…/repositories/`,
S = `…/services/`, RT = `…/routers/`. „neu“ = neue Datei, sonst Änderung.

### A.1 Naben — hier kollidiert jedes Paket der Spalte

| Nabe | Pakete | Regel |
|---|---|---|
| Migrationsnummer (M) | B1, C1, C2 (Matrix-Spalte), C3, D1, D3, E2 | eine Kette, in dieser Reihenfolge |
| `PM/__init__.py` (Exporte) | B1, C1, C3, D1, E2 | mit der Schema-Kette |
| `packages/models/src/who2be_models/errors.py#ProblemReason` + `apps/api/src/who2be_api/main.py` (`_PROBLEM_TITLES`) | B2, B5, C2, C3, C4, D2, D4, E2 | mit der API-Kette; ein Test hält die Titel-Tabelle vollständig |
| `PM/tool_policy.py` (Capabilities, `is_within`) | B1 (`test_report`), D1 (`case_triage`) | in B1 beide anlegen, D1 nutzt sie |
| `apps/api/src/who2be_api/main.py` (`include_router`) | B2, C3, D2, E2 | API-Kette |
| `docs/reference/openapi.json` | B2, B5, C3, C4, D2, D6, E1, E2 | API-Kette; regenerieren (`scripts/export_openapi.py`), nie von Hand lösen |
| `apps/web/src/api/types.ts` | B4, B5, C5, C6, D6, E5 | Web-Kette |
| `apps/web/src/i18n/locales/{de,en}.json` | B4, B5, C5, C6, D6, E5 | Web-Kette |
| `apps/mcp/src/who2be_mcp/server.py` (ein `register`-Aufruf, `save_memory`) | B3, C4, D4, E1 | MCP-Kette |
| `packages/models/src/who2be_models/tool_requirements.py#MCP_TOOL_REQUIREMENTS` + `S/placeholders/resolvers/tools.py` (`_TOOLS`) | B3, C4, D4, E1 | MCP-Kette |
| `CLAUDE.md` (Werkzeuganzahl) | B3, C4, D4, E1 | MCP-Kette; Test `test_doc_tool_count.py` |
| `S/gdpr_export_service.py`, `docs/compliance/vvt.md`, `docs/compliance/data-retention-and-erasure.md`, `R/account_repository.py` | B1, C1, D1, E2 | Schema-Kette |

### A.2 Dateien je Paket (Backend-Spur)

| Paket | Dateien |
|---|---|
| B1 | M neu; PM `test_case.py` neu, `tool_policy.py`, `__init__.py`; R `test_case_repository.py` neu; Test RLS neu; Compliance-Naben |
| B2 | S `test_case_service.py` neu (inkl. Auflösung nach 3.2.1); R `usage_repository.py` bzw. neue Abfrage für betroffene Agenten; RT `test_cases.py` neu; `main.py`; `errors.py`; `openapi.json`; Test neu |
| B3 | `tools/learning.py` neu; `clients/learning.py` neu; `server.py`; `tool_requirements.py`; `resolvers/tools.py`; `CLAUDE.md`; Test neu |
| B5 (API-Teil) | PM `status.py` (`VersionTransitionRequest` + `override_reason`); `errors.py`; S `version_status.py`; RT der Transitions (`personas.py`, `playbooks.py`, `resources.py`, `system_prompts.py`, `external_tools.py`) — **über der 8er-Grenze**, in B5a (Modell, Fehler, Service) und B5b (Router) teilen |
| C1a | M neu; PM `memory.py` (inkl. `MEMORY_MAX_PER_USER`), `__init__.py`; R `memory_repository.py` (inkl. Zählabfrage je `(workspace_id, subject_user_id)`); Test |
| C1b | Compliance-Naben (`S/gdpr_export_service.py`, `docs/compliance/vvt.md`, `docs/compliance/data-retention-and-erasure.md`, `R/account_repository.py`); Test |
| C2a | M neu (Matrix-Spalte); S `memory_service.py` (Freigabematrix, Pflichtfeld `origin` im Speicherpfad, `lesson`-Merge 3.1.6, Obergrenzen 3.1.1 und 3.1.5); RT `memory.py` (`GET/PUT /memory-auto-policy`); `errors.py`; `main.py`; `openapi.json`; Test |
| C2b | S `memory_service.py` (Secret-Scan, Ratenbegrenzung); neuer Verfallsjob neben `core/purge.py`; Test |
| C3 | M neu (Vorschläge, Event `auto_revoked`); S `memory_service.py`; RT `memory.py` (Vorschläge, Historie/Rollback, `/me/memories`, `GET /memories`, `counts`, `batch`, `revoke-auto`); RT `members.py` (`DELETE /members/{user_id}/memories`); R `memory_repository.py`; `errors.py`; `main.py`; `openapi.json`; Test — **über der 8er-Grenze**, in C3a (Migration, Repository, Service) und C3b (Router, OpenAPI) teilen |
| C4 | `server.py` (`save_memory`); `tools/learning.py`; `clients/learning.py`; `tool_requirements.py`; `resolvers/tools.py`; S `persona_service.py` (Push nur bestätigt); `CLAUDE.md` |
| D1 | M neu; PM `case.py` neu, `__init__.py`; R `case_repository.py` neu; Test; Compliance-Naben |
| D2 | S `case_service.py` neu; RT `cases.py` neu; RT `feedback.py` (promote); `main.py`; `errors.py`; `openapi.json`; Test |
| D3 | M neu (`usage_event.source`); S `persona_service.py`, `playbook_service.py`, `resource_service.py`; R `feedback_repository.py` (`summarize`, `overview`, `unused` trennen nach `source`); Test |
| D4 | wie B3 plus `record_usage`-Text in `server.py` |
| D5 | S `pattern_service.py` neu; RT `cases.py`; R `case_repository.py`, `memory_repository.py`; Test |
| E1 | S `dossier_service.py` neu; RT `sessions.py` neu; MCP-Naben |
| E2 | M neu; PM `session.py` neu, `__init__.py`; R `session_repository.py` neu; S `session_service.py` neu; Compliance-Naben — **über 8, in E2a (Schema) und E2b (Service/API) teilen** |
| E3 | S `session_service.py`; S `version_status.py` (Event `activated` → Fälle `addressed`); Test |

Kollisionen innerhalb der Backend-Spur, die über die Naben hinausgehen:

- `S/memory_service.py`: C2a, C2b, C3 — nacheinander.
- `RT/memory.py`: C2a, C3 — nacheinander.
- `S/persona_service.py`: C4 (Push), D3 (Nutzung) — nacheinander.
- `S/version_status.py`: B5, E3 — nacheinander.
- `R/memory_repository.py`: C1a, C3, D5 — nacheinander.
- `R/feedback_repository.py`: D3 allein; D6 liest nur.
- `RT/cases.py`: D2, D5 — nacheinander.

**Zuschnitt Phase C (Ist-Zuschnitt der Karten, PM 2026-09-30).** Die
Zeilen C1a bis C3 oben ersetzen die frühere Grobteilung C1/C2/C3. Wo
Abschnitt A.1, A.3 und der Fließtext noch „C1“ oder „C2“ sagen, sind C1a/C1b
bzw. C2a/C2b gemeint.

| Karte | Inhalt |
|---|---|
| C1a | Schema, Modelle, Repository (3.1–3.1.2, 5.1) |
| C1b | Compliance-Naben (Export, VVT, Löschkonzept, Purge) |
| C2a | Freigabematrix (Abschnitt 4) inkl. `GET/PUT /memory-auto-policy` (Router) und Pflichtfeld `origin` im Speicherpfad |
| C2b | Secret-Scan, Ratenbegrenzung, Verfallsjob (3.1.3) |
| C3 | Vorschläge (3.1.4), Historie/Rollback (3.1.2), `/me/memories`; dazu laut Nachtrag C0b (6.4.1) workspace-weite Liste, Zähler, Stapel, Not-Aus-Endpunkt und Admin-Löschen des Nutzergedächtnisses |
| C4 | MCP (6.4) |
| Web | C6 → C5a → C5b, eine Kette wegen `apps/web/src/i18n/locales/{de,en}.json` (A.1, A.3). C5a: Warteschlange aus `GET /memories?status=pending`, Zähler aus `counts`. C5b: zusätzlich die Oberfläche des Not-Aus (6.4.1) |

`GET/PUT /memory-auto-policy` gehört damit zu C2a, nicht zu C3.

### A.3 Web-Spur

| Paket | Dateien (Auswahl) |
|---|---|
| B4 | neues Feature `apps/web/src/features/test-cases/`; Naben |
| B5 | `apps/web/src/components/version/VersionDiffView.tsx`, Aktivierungsdialog; Naben |
| C5 | `apps/web/src/features/agents/components/AgentMemorySection.tsx` (Triage, Verlauf, Rollback); Naben |
| C6 | `apps/web/src/features/settings/components/MemoryGuardSection.tsx` bzw. neue Sektion daneben; Naben |
| D6 | `apps/web/src/features/feedback/components/FeedbackInbox.tsx`, `apps/web/src/components/feedback/GiveFeedbackDialog.tsx`, neue Fall-Seiten; Naben |
| E5 | neues Feature `apps/web/src/features/sessions/`; Naben |

`AgentMemorySection.tsx` (C5) und `MemoryGuardSection.tsx` (C6) sind
getrennt; C5 und C6 kollidieren nur in den Naben.

### A.4 Hermes/Builder-Spur

B6, C7, D7, E4 liegen außerhalb dieses Repos (Profile, Skills, Skripte) —
bis auf die Builder-Playbooks im Repo
(`apps/api/src/who2be_api/repositories/builder_playbook_maintenance_body.json`
und Nachbarn). Änderungen an verwalteten Builder-Inhalten laufen nach
Weiche E3.

## 11. Anhang B — gesetzte Zahlen und ihre Herleitung

| Zahl | Wo | Art | Herleitung |
|---|---|---|---|
| 30 Tage | Verfall unbestätigter Einträge | **gesetzte Annahme** | Hermes-Curator verwendet 14 und 30 Tage für Skills (Wettbewerbsrecherche §3). 30 statt 14, weil Who2Be-Triage wöchentlich gedacht ist: vier Gelegenheiten zur Bestätigung vor dem Verfall. In F1 anhand der Quote „verfallen ohne Sichtung“ überprüfen |
| n = 3 | Musterschwelle | **gesetzte Annahme** | Belegt ist „mindestens 2 Belege“ (Honcho) und ein Startwert 2 (ExpeL). 3 statt 2, damit eine einzelne Sitzung mit einer Wiederholung noch kein Muster erzeugt |
| 30 Tage | Zeitfenster für Fall-Muster | **gesetzte Annahme** | gleich dem Verfall, damit beide Sichten denselben Zeitraum zeigen |
| 200 | Obergrenze `agent_note` je Agent | **gesetzte Annahme** | 40 % von `MEMORY_MAX_PER_AGENT` (500), damit Nutzerfakten Vorrang behalten |
| 500 | Obergrenze Nutzergedächtnis je `(workspace_id, subject_user_id)`, `MEMORY_MAX_PER_USER` (3.1.1) | **gesetzte Annahme** | gleich der Agentengrenze `packages/models/src/who2be_models/memory.py#MEMORY_MAX_PER_AGENT`, weil ein Nutzergedächtnis über alle Profile desselben Besitzers geteilt wird; gezählt über alle Status wie dort. In F1 anhand der Füllstände überprüfen |
| 300 / 200 / 500 | Längen `fact` / `context` / Notiz | übernommen | `packages/models/src/who2be_models/memory.py#MEMORY_FACT_MAX_LENGTH`, `#MEMORY_CONTEXT_MAX_LENGTH`, `#MEMORY_TRIAGE_NOTE_MAX_LENGTH` |
| 2 000 | Freitextfelder Fall/Maßnahme | übernommen | gleiche Grenze wie `note` in `packages/models/src/who2be_models/feedback.py#FeedbackCreate` |
| 1 000 | `override_reason` (6.3) | **gesetzte Annahme** | Halbe `note`-Grenze von `packages/models/src/who2be_models/status.py#VersionTransitionRequest` (2 000), weil beide zusammen in dieselbe `status_history.note` geschrieben werden und dort unter 2 000 plus Präfix bleiben sollen. Ein Grund ist ein bis drei Sätze |
| 4 000 / 8 000 | `situation`, `behavior`, `output_excerpt` / `input` | **gesetzte Annahme** | Ein Fall zitiert Ein- und Ausgabe; 2 000 reichen dafür erfahrungsgemäß nicht. Obergrenze, damit ein Fall kein Transkript wird |
| 132 162 / 160 000 / 1 592 | MCP-Payload | gemessen | `_tools_payload_bytes()` aus `apps/mcp/tests/test_tool_payload_budget.py` am Stand `ef0756a3`; 132 162 / 83 = 1 592 |
| 11 | neue MCP-Werkzeuge | abgeleitet | Aufzählung 6.7 |
