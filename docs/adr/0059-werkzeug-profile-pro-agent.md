# ADR-0059 — Werkzeug-Profile pro Agent (Erweiterung von ADR-0042)

- Status: **Accepted** (Owner, 2026-10-21). Die Richtung hat der Owner am
  2026-10-16 entschieden (Wortlaut in Abschnitt 2), die Weichen W59-1 bis
  W59-6 am 2026-10-21 (Wortlaut in Abschnitt 11).
- Datum: 2026-10-20 (Proposed), 2026-10-22 (Accepted nachgezogen)
- Gemessen gegen: `origin/main` @ `000a7bd4` (100 Werkzeuge, `tools/list`
  114.203 Bytes, Server-`instructions` 1.604 Bytes). Code-Aussagen tragen einen
  Symbolanker (Konvention `docs/code-references.md`).
- Grundlage: Kanban-Karte t_52f61361 (Token-Optimierung W2). Dazu die
  Entscheidungsvorlage „MCP-Werkzeuge token-sparender ausliefern“ (Stand
  2026-10-09, außerhalb des Repos, §3 Option B(3), §6 Weiche W2).
- Bezug: ADR-0042 (Filter `tools/list` nach Rechten), ADR-0039 (Rechte und
  Lese-Umfang je Agent), ADR-0058 (W1, Markdown als Schreibstandard), ADR-0053
  (Lernschleife, Kurations-Posteingang), ADR-0005 (MCP als HTTP-Client ohne DB),
  ADR-0034 (HTTP-Transport, mehrere Mandanten).
- Umfang: **nur Dokumentation.** Diese ADR ändert keinen Code. Umsetzung in
  den Paketen Q1 bis Q6 (Abschnitt 10).

## Inhalt

1. Kontext und Befund
2. Entscheidung (Owner-Wortlaut)
3. Regel: wer sieht welches Werkzeug
4. Datenmodell und Migration
5. Werkzeuggruppen und mitgelieferte Profile (gemessen)
6. `whoami`, Cache und Wirkzeit
7. API und Rechte
8. Meldeweg, wenn ein Werkzeug fehlt
9. Web-Oberfläche (grob)
10. Paketschnitt
11. Entscheidungen
12. Konsequenzen

## 1. Kontext und Befund

ADR-0042 filtert `tools/list` je Anfrage nach den Rechten des Agenten
(`apps/mcp/src/who2be_mcp/policy_filter.py#PolicyFilterMiddleware`). Das wirkt
für Fach-Agenten mit Standard-Rechten gut: Sie sehen 38 von 100 Werkzeugen
(29.497 Bytes). Für Agenten mit vielen Rechten wirkt es nicht. Der Builder hat
alle Rechte
(`apps/api/src/who2be_api/repositories/workspace_repository.py#_builder_tool_policy`)
und sieht deshalb den ganzen Katalog **[B]**:

| Principal | Werkzeuge | `tools/list` (Bytes) | Start inkl. `instructions` |
| --- | ---: | ---: | ---: |
| Agent, Standard-Rechte | 38 | 29.497 | 31.101 |
| Agent, Standard + Gedächtnis `suggest` | 42 | 32.971 | 34.575 |
| Builder (alle Rechte) | 100 | 114.203 | **115.807** |
| Mensch/JWT, Rolle editor | 96 | 110.729 | 112.333 |

Gemessen mit `apps/mcp/src/who2be_mcp/payload_report.py#REFERENCE_PROFILES`,
also mit derselben Zählweise wie der Budget-Test. Der Startwert des Builders
liegt nahe an seinem Ziel von 120.000 Bytes
(`apps/mcp/tests/test_tool_payload_budget.py#_START_TARGET_BYTES`).

Rechte sind die falsche Stellschraube, um das zu ändern. Der Builder braucht
seine Rechte, damit er sie über `is_within` an andere Agenten weitergeben kann
(`packages/models/src/who2be_models/tool_policy.py#AgentToolPolicy`, Docstring
von `_builder_tool_policy`). Ob ein Werkzeug sichtbar ist, und ob ein Agent es
darf, sind zwei Fragen. ADR-0042 beantwortet beide mit derselben Antwort. Diese
ADR trennt sie: Die Rechte bleiben, wie sie sind, und ein **Werkzeug-Profil**
blendet zusätzlich aus, was ein Agent für seine Arbeit nicht braucht.

W1 (ADR-0058 §8.1) spart im Katalog nur etwa 2 KB. Das Ziel „Builder-Start
deutlich unter 116 KB“ trägt W2.

## 2. Entscheidung (Owner-Wortlaut)

Owner, 2026-10-16, wörtlich:

> „W1a, W2b“

W2b heißt: Werkzeug-Profile kommen vor dem Cloud-Release.

> „P1 können wir eine Kombination aus A und B machen? Zb durch Zusatzrechte
> oder eine Rechteverwaltung pro Profil? P2a, P3a“

Auf den Vorschlag des PM zur Form von P1, Owner 2026-10-16, wörtlich:

> „P1 ok“

Das bedeutet, und so gilt es für diese ADR und alle W2-Pakete:

- **(a)** Profile sind Vorlagen und im Web pflegbar. Mitgeliefert werden
  „Alle“, „Lesen“, „Autor“, „Kurator“ und „Builder“. Sie sind anpassbar,
  eigene Profile sind möglich.
- **(b)** Am Agenten wird ein Profil gewählt. Dazu lassen sich einzelne
  Werkzeuge zusätzlich freigeben oder sperren.
- **(c)** Rechte (ADR-0039/0042) gehen vor. Ein Profil schränkt nur ein, es
  erweitert nie.
- **(d)** Der Standard ist „Alle“. Bestehende Agenten bleiben unverändert.
- **P2a:** Dieselbe MCP-URL für alle. Das Profil hängt am Agenten, nicht an
  der Verbindung.
- **P3a:** Was außerhalb des Profils liegt, ist unsichtbar, in `tools/list`
  und in `tools/call`. Der Agent meldet „braucht Werkzeug X“, ein Mensch passt
  an.

P2a ist auch spec-konform. Die MCP-Spezifikation 2026-07-28 erlaubt, die
Werkzeugmenge nach der Berechtigung der Anfrage zu filtern, nicht aber nach
Verbindung oder Sitzungszustand (Vorlage §2.1). Das Profil hängt am Token, über
den Agenten, und ist damit Teil der Berechtigung der Anfrage.

## 3. Regel: wer sieht welches Werkzeug

### 3.1 Normative Formel

Für einen agent-gebundenen Token gilt:

```text
sichtbar(t) = rechte_sichtbar(t)                     # ADR-0042, unverändert
              UND ( t ∈ KERN  ODER  t ∈ profil_menge )

profil_menge = ( "Alle" ? alle Werkzeuge
                        : expand(profil.gruppen) ∪ profil.werkzeuge )
               ∪ agent.zusätzlich
               − agent.gesperrt
```

- `rechte_sichtbar` ist
  `packages/models/src/who2be_models/tool_requirements.py#is_tool_visible_for`
  bzw. `#is_tool_visible`, ohne jede Änderung. Daraus folgt (c): Ein Profil kann
  nur aus der Menge streichen, die die Rechte zulassen. Ein Werkzeug, das die
  Rechte verbergen, macht auch `agent.zusätzlich` nicht sichtbar.
- **KERN** sind `ping`, `whoami` und `report_problem`. Sie sind in keinem
  Profil abwählbar, auch nicht über `agent.gesperrt` (422). `report_problem`
  muss bleiben, weil es der Meldeweg aus P3a ist (Abschnitt 8). Die Rechte gehen
  auch hier vor: Ohne `feedback_write` ist `report_problem` weiterhin
  unsichtbar.
- **„Alle“** ist kein gespeichertes Profil, sondern das Fehlen eines Profils
  (`agent.tool_profile_id IS NULL`). „Alle“ mit `agent.gesperrt` ist erlaubt
  („Alle außer X“).
- **Menschen und ungebundene Tokens** (`unrestricted=True`) haben kein Profil.
  Für sie ändert sich nichts.

### 3.2 Ein Rechenweg, zwei Aufrufer

Die Formel liegt als reine Funktion in `packages/models`, im neuen Modul
`who2be_models/tool_profiles.py` (Paket Q1), zusammen mit den Werkzeuggruppen
(Abschnitt 5). Zwei Aufrufer nutzen sie, wie bei ADR-0042:

- der MCP-Adapter in `PolicyFilterMiddleware` (`tools/list`, `tools/call`),
- die API im System-Prompt-Block `tools-overview`
  (`apps/api/src/who2be_api/services/placeholders/resolvers/tools.py#ToolsOverviewResolver`).

Der zweite Aufrufer ist Pflicht. Sonst nennt der System-Prompt Werkzeuge, die
`tools/list` gar nicht liefert. Genau diesen Widerspruch hat ADR-0042 im
Nachtrag 2026-08-19 beseitigt, und der Test
`test_prompt_nennt_kein_tool_das_die_policy_herausfiltert` prüft ihn. Er wird
auf das Profil erweitert.

### 3.3 Kein Recht, keine Sicherheitsgrenze

Ein Profil ist **kein Recht**. Es geht deshalb nicht in `is_within` ein (wie
`memory_directive`), und die API setzt es nicht durch. Ein REST-Aufruf an der
MCP-Schicht vorbei bleibt so erlaubt wie heute, entschieden nach den Rechten.
Die Durchsetzung bleibt autoritativ bei der API (ADR-0039), das Profil ist
Kontext-Hygiene wie der Filter aus ADR-0042.

Fail-open gilt unverändert. Kann die Middleware die Identität nicht auflösen,
liefert sie die ungefilterte Liste (ADR-0042 §4). Ein unbekannter
Werkzeugname in einem Profil (etwa nach dem Abbau eines Werkzeugs) wird bei der
Auswertung übergangen und in der Web-Oberfläche als „entfallen“ gezeigt. Beim
Speichern lehnt die API unbekannte Namen ab (422).

## 4. Datenmodell und Migration

### 4.1 Tabelle `tool_profile` (je Workspace)

```sql
CREATE TABLE tool_profile (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    builtin_key   text NULL CHECK (builtin_key IN ('read', 'author', 'curator', 'builder')),
    name          text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    description   text NOT NULL DEFAULT '',
    groups        text[] NOT NULL DEFAULT '{}',
    tools         text[] NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, builtin_key)
);
CREATE UNIQUE INDEX tool_profile_name_uq ON tool_profile (workspace_id, lower(name));
```

- `groups` und `tools` (W59-1): Ein Profil besteht aus Werkzeuggruppen und
  einzelnen Werkzeugen, die Vereinigung zählt. Die Gruppen kommen aus dem Code
  (Abschnitt 5). Ein neues Werkzeug in einer bestehenden Gruppe erscheint damit
  ohne Migration in jedem Profil, das die Gruppe enthält, auch in angepassten.
- `builtin_key` markiert die vier mitgelieferten Profile. Sie sind anpassbar
  (Owner a), aber nicht löschbar, und lassen sich auf den Lieferstand
  zurücksetzen (Abschnitt 7). Eigene Profile haben `builtin_key IS NULL`.
- Kein `created_by`: Wer ein Profil angelegt oder geändert hat, steht im
  `audit_log` (Abschnitt 7). So trägt die Tabelle keine personenbezogenen Daten
  und braucht keinen eigenen Löschpfad.
- Mandantentrennung: RLS-Richtlinie `tenant_isolation` wie bei den übrigen
  Workspace-Tabellen (Muster in Migration 0100). Löschen des Workspace löscht
  die Profile mit (`ON DELETE CASCADE`). Der Org-Export erfasst die Tabelle ohne
  Zusatzarbeit, weil sie `workspace_id` trägt (`docs/org-export-import.md`,
  Klasse „Inhalte und Steuerung“). Beim Import muss `tool_profile` vor `agent`
  stehen (Fremdschlüssel unten).

### 4.2 Zuordnung am Agenten

```sql
ALTER TABLE agent
    ADD COLUMN tool_profile_id uuid NULL,
    ADD COLUMN tools_added     text[] NOT NULL DEFAULT '{}',
    ADD COLUMN tools_removed   text[] NOT NULL DEFAULT '{}',
    ADD CONSTRAINT agent_tool_profile_fk
        FOREIGN KEY (workspace_id, tool_profile_id)
        REFERENCES tool_profile (workspace_id, id) ON DELETE RESTRICT;
```

- Eigene Spalten, nicht in `agent.tool_policy`. Das hat zwei Gründe. Die
  Policy ist das Rechte-Objekt, und das Profil ist kein Recht (3.3). Und der
  Start-Abgleich der verwalteten Builder-Inhalte überschreibt `tool_policy`
  ganz
  (`apps/api/src/who2be_api/repositories/workspace_repository.py#sync_managed_builder_content`).
  Eine Profil-Anpassung durch einen Menschen am Builder würde sonst beim
  nächsten Start verschwinden.
- Der zusammengesetzte Fremdschlüssel pinnt das Profil auf den Workspace des
  Agenten. Ist `tool_profile_id` NULL, prüft Postgres ihn nicht (MATCH SIMPLE),
  und es gilt „Alle“.
- `ON DELETE RESTRICT`: Ein Profil, das noch an Agenten hängt, lässt sich nicht
  löschen (409, Abschnitt 7). Kein stilles Zurückfallen auf „Alle“.
- Bestand: Alle Spalten haben Standardwerte, die „Alle ohne Ausnahmen“
  bedeuten. Bestehende Agenten bleiben damit unverändert (Owner d). Einzige
  Ausnahme ist der verwaltete Builder (W59-3 = A, Abschnitt 11).
- `copy_agent` übernimmt die drei Felder. `create_agent` setzt sie nicht
  (Abschnitt 7.3).

### 4.3 Migration

Nummer: **0110**, vom PM für dieses Vorhaben vergeben
(`apps/api/src/who2be_api/migrations`, letzte auf `main` ist 0108; kein Branch
auf `origin` belegt 0109 oder höher, geprüft am 2026-10-22 gegen `fb03322a`).
Die Paket-Karte prüft die Nummer vor dem Anlegen erneut gegen `origin/main`,
weil inzwischen andere Migrationen landen können.

`0110_tool_profile.sql` enthält:

1. Tabelle, Indizes, RLS wie in 4.1.
2. Agent-Spalten und Fremdschlüssel wie in 4.2.
3. Backfill: je Bestands-Workspace die vier mitgelieferten Profile, Namen nach
   `workspace.content_locale` (DE: Lesen, Autor, Kurator, Builder; EN: Read,
   Author, Curator, Builder). Idempotent über `ON CONFLICT (workspace_id,
   builtin_key) DO NOTHING`.
4. Die verwalteten Builder-Agenten (`is_managed = true`, Builder und
   Builder-Lite) auf das Profil `builder` ihres Workspace setzen (W59-3 = A).
   Ein Mensch kann sie danach auf „Alle“ zurückstellen (7.3).

Neue Workspaces bekommen dieselben vier Zeilen beim Anlegen in
`workspace_repository.py`. Beide Schichten bleiben synchron, wie bei 0047 und
0060 (Hinweis in `migrations/README.md`).

## 5. Werkzeuggruppen und mitgelieferte Profile (gemessen)

### 5.1 Gruppen

Jedes Werkzeug gehört zu genau einer Gruppe. Das prüft ein Paritätstest gegen
`MCP_TOOL_REQUIREMENTS`, so wie ADR-0042 die Vollständigkeit des Mappings
prüft. Damit kommt eine Pflicht dazu: **Ein neues MCP-Werkzeug braucht einen
Eintrag im Mapping und eine Gruppe.** Fehlt die Gruppe, ist der Test rot.

Gemessen am Stand `000a7bd4`, Bytes je Gruppe in Draht-Form **[B]**:

| Gruppe | Werkzeuge | Bytes | Werkzeuge im Einzelnen |
| --- | ---: | ---: | --- |
| `core` | 3 | 2.606 | `ping`, `whoami`, `report_problem` |
| `read` | 18 | 13.238 | `get_persona`, `list_playbooks`, `list_triggers`, `fetch_playbook`, `list_resources`, `fetch_agent`, `list_agents`, `get_agent`, `fetch_resource`, `list_resource_blocks`, `list_external_tools`, `get_external_tool`, `find_usages`, `list_versions`, `get_version`, `diff_versions`, `search`, `search_content` |
| `feedback_memory` | 11 | 10.990 | `record_usage`, `submit_feedback`, `get_feedback`, `search_memory`, `list_memories`, `save_memory`, `list_test_cases`, `submit_test_results`, `propose_memory_change`, `report_case`, `submit_case_statement` |
| `workarea_read` | 10 | 6.137 | `read_artifact`, `list_artifacts`, `search_workarea`, `search_kb`, `neighbors`, `list_tables`, `query_table`, `describe_table`, `timeline`, `list_category_rules` |
| `workarea_write` | 15 | 14.080 | `create_artifact`, `append_artifact`, `patch_artifact`, `delete_artifact`, `ingest`, `create_node`, `update_node`, `create_edge`, `promote_artifact`, `create_table`, `delete_table`, `insert_rows`, `save_query_result`, `set_convention`, `upsert_category_rule` |
| `content_write` | 16 | 30.998 | `create_persona`, `update_persona`, `restore_persona`, `set_persona_playbooks`, `create_playbook`, `update_playbook`, `restore_playbook`, `set_playbook_resource_links`, `set_playbook_composes`, `create_resource`, `update_resource`, `restore_resource`, `set_resource_sub_resources`, `create_external_tool`, `update_external_tool`, `restore_external_tool` |
| `transition` | 4 | 3.653 | `transition_persona`, `transition_playbook`, `transition_resource`, `transition_external_tool` |
| `agent_admin` | 3 | 12.268 | `create_agent`, `update_agent`, `copy_agent` |
| `system_prompt` | 7 | 7.204 | `list_placeholders`, `list_system_prompts`, `get_system_prompt`, `create_system_prompt`, `update_system_prompt`, `restore_system_prompt`, `transition_system_prompt` |
| `curation` | 13 | 13.029 | `resolve_feedback`, `list_cases`, `assign_case_elements`, `get_case`, `triage_case`, `list_patterns`, `create_test_case`, `get_lesson`, `convert_lesson_to_case`, `get_dossier`, `submit_session_protocol`, `link_measure_draft`, `get_follow_up` |
| **zusammen** | **100** | | |

`edit_content` aus ADR-0058 (W1, Paket P3) kommt in `content_write`. Es ist bei
Umsetzung von Q1 schon auf `main`, falls die Reihenfolge des PM hält.

Die Gruppen sind fachlich geschnitten, nicht nach Rechten. `promote_artifact`
etwa verlangt das Recht `resource_write`
(`MCP_TOOL_REQUIREMENTS`), gehört aber zur Arbeit im Arbeitsbereich. Für die
Sichtbarkeit zählen ohnehin beide Achsen (3.1).

### 5.2 Mitgelieferte Profile

| Profil | Gruppen | Für wen |
| --- | --- | --- |
| **Alle** | – (kein Profil) | Standard, Bestand |
| **Lesen** | `core`, `read`, `feedback_memory`, `workarea_read` | Fach-Agenten, die nur nachschlagen und rückmelden |
| **Autor** | Lesen + `content_write`, `transition`, `workarea_write` | Agenten, die Inhalte schreiben und recherchieren |
| **Kurator** | Lesen + `transition`, `curation` | Agenten, die Rückmeldungen und Fälle sichten |
| **Builder** | `core`, `read`, `feedback_memory`, `workarea_read`, `content_write`, `transition`, `agent_admin`, `system_prompt`, `curation` | der verwaltete Builder (W59-3) |

`workarea_read` im Profil „Builder“ hat der Owner am 2026-10-21 entschieden
(W59-4, Abschnitt 11).

Gemessen mit den Rechten des Builders, also dem größten Fall, und mit den
Rechten eines Menschen in der Rolle editor **[B]**. „Start“ heißt
`tools/list` plus Server-`instructions` (1.604 Bytes), die Kennzahl aus
`test_agent_start_meets_target_per_profile`:

| Profil | Werkzeuge (Builder-Rechte) | `tools/list` | Start | Werkzeuge (editor) | `tools/list` (editor) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Alle | 100 | 114.203 | 115.807 | 96 | 110.729 |
| Lesen | 42 | 32.971 | 34.575 | 38 | 29.497 |
| Autor | 77 | 81.702 | 83.306 | 73 | 78.228 |
| Kurator | 59 | 49.653 | 51.257 | 55 | 46.179 |
| **Builder** | **85** | **100.123** | **101.727** | 81 | 96.649 |
| zum Vergleich: Builder ohne `workarea_read` (verworfen) | 75 | 93.986 | 95.590 | 71 | 90.512 |

Die Spalte „editor“ zeigt die Rechte-Seite eines Menschen nur zum Vergleich;
Menschen haben kein Profil (3.1). Die Zeilen „Alle“, „Builder“ und die
Vergleichszeile sind am 2026-10-22 mit `payload_report` gegen `000a7bd4` und
gegen `origin/main` @ `fb03322a` nachgemessen, beide bytegenau gleich.

**Wirkung für den Builder:** von 115.807 auf 101.727 Bytes beim Start, also
−14.080 Bytes (−12,2 %), bei unveränderten Rechten. `workarea_read` kostet
gegenüber der verworfenen Variante 6.137 Bytes. Mit W1 (ADR-0058 §8.1)
kommen geschätzt weitere −1,6 bis −2,7 KB dazu **[E]**.

**Der Builder verliert keinen Arbeitsschritt.** Geprüft gegen die verwalteten
Builder-Inhalte, DE und EN (System-Prompt-Templates, Persona, Modi, alle
Builder-Playbooks und die Resource Konventionen): Sie nennen 71 Werkzeuge, alle
liegen im Profil „Builder“ **[B]**. Das Profil hat zusätzlich `ping`,
`report_problem`, `get_version`, `list_resource_blocks` und die 10 Werkzeuge
aus `workarea_read`. Damit kann der Builder Rohmaterial, Knowledge Base und
Tabellen lesen, auch wenn seine Inhalte das heute nicht verlangen.
Ausgeblendet sind die 15 Werkzeuge der Gruppe `workarea_write`. Keines davon
nennen die Builder-Inhalte.

**Grenze der Messung:** Für einen Agenten mit Standard-Rechten bringt „Lesen“
nichts, weil die Rechte schon dasselbe ausblenden (38 bzw. 42 Werkzeuge in
beiden Fällen). Profile wirken bei Agenten mit vielen Rechten. Die Zahlen sind
Draht-Bytes, keine Tokens (Faustregel etwa 4 Bytes je Token, **[E]**).

### 5.3 Messpunkt im Test

`payload_report.REFERENCE_PROFILES` bekommt ein fünftes Profil „Builder mit
Profil Builder“, also Builder-Rechte und die Gruppen aus 5.2 einschließlich
`workarea_read`. Gemessen sind heute 101.727 Bytes Start.

Paket Q3 setzt dafür ein eigenes Startziel in
`test_agent_start_meets_target_per_profile`: **104.000 Bytes**. Das ist der
gemessene Wert plus Reserve für `edit_content` (ADR-0058, +1,2 bis +1,6 KB,
landet in `content_write`) und knapp 700 Bytes Luft. Das Ziel ist eine
Obergrenze gegen Wachstum, nicht die Wirkung selbst. Die Wirkung (−12 %
gegenüber „Alle“) weist Q3 mit `payload_report` in
`docs/mcp-payload-budget.md` aus. Das Ziel des Builders ohne Profil (120.000)
bleibt als Wert für „Alle“ stehen, bis der Owner es senkt.

## 6. `whoami`, Cache und Wirkzeit

### 6.1 Was `whoami` liefert

`packages/models/src/who2be_models/whoami.py#WhoAmIRead` bekommt ein Feld:

```python
tool_profile: ToolProfileGrant | None = None
# ToolProfileGrant: id (None bei "Alle"), name, groups, tools,
#                   tools_added, tools_removed
```

- `None` heißt: keine Einschränkung durch ein Profil. Das gilt für Menschen,
  ungebundene Tokens und Agenten auf „Alle“ ohne Ausnahmen.
- Der Agent sieht damit selbst, unter welchem Profil er läuft. Das braucht er
  für die Meldung aus P3a (Abschnitt 8).
- Größe: Gruppen und Ausnahmen sind kurz, typisch 100 bis 250 Bytes. Die
  ausgerechnete Werkzeugliste (bis 1,5 KB) geht bewusst **nicht** in die
  Antwort, denn `whoami` ist ein Boot-Werkzeug, das jeder Agent aufruft.

Die Middleware rechnet `profil_menge` selbst aus dem Feld aus, mit der
Funktion aus `packages/models` (3.2). Das MCP bleibt dünn und braucht keine
Datenbank (ADR-0005), und es braucht keinen zweiten API-Aufruf.

Die API füllt das Feld aus der Agent-Zeile und dem Profil. Der Ladeweg ist
derselbe wie für die Rechte
(`apps/api/src/who2be_api/core/security.py#_load_agent_tool_policy`), als
Join statt zweiter Abfrage.

### 6.2 Cache und Wirkzeit (W59-5)

Heute merkt sich die Middleware die `whoami`-Antwort je Token 300 Sekunden
(`apps/mcp/src/who2be_mcp/policy_filter.py#_WHOAMI_CACHE_TTL_SECONDS`). Eine
geänderte Zuordnung wirkt damit erst nach bis zu fünf Minuten. Das MCP läuft in
einem eigenen Prozess ohne gemeinsamen Speicher mit der API (ADR-0005). Die API
kann den Cache deshalb nicht gezielt leeren.

Für P3a („ein Mensch passt an“) heißt das: Der Mensch gibt das Werkzeug frei,
und der Agent sieht es noch bis zu fünf Minuten lang nicht. Ein Neuverbinden
hilft nicht, weil der Cache am Token hängt und nicht an der Verbindung.

**Entschieden (W59-5): TTL auf 60 Sekunden senken**, für den ganzen Eintrag. Ein
aktiver Agent erzeugt dann höchstens einen `whoami`-Aufruf je Minute und Token
an die API statt einen je fünf Minuten. `whoami` ist ein einzelner
Lesezugriff ohne eigenes Rate-Limit am Router
(`apps/api/src/who2be_api/routers/whoami.py#whoami`). Rechte-Änderungen
profitieren gleich mit. Die Web-Oberfläche nennt die Wirkzeit am
Speichern-Knopf („wirkt innerhalb einer Minute“).

`notifications/tools/list_changed` bleibt außen vor, wie in ADR-0042. Die Spec
2026-07-28 sieht für `tools/list` zusätzlich `ttlMs` vor, mit dem der Client
die Liste selbst cacht (Vorlage §2.1). Der Who2Be-Code setzt `ttlMs` heute
nirgends selbst. Paket Q3 prüft, was FastMCP dort ausliefert, und gleicht den
Wert höchstens auf die Cache-TTL an.

## 7. API und Rechte

### 7.1 Endpunkte

Alle unter `/v1/workspaces/{workspace_id}`:

| Methode und Pfad | Zweck | Rolle |
| --- | --- | --- |
| `GET /tool-profiles` | Profile mit Gruppen, Werkzeugen und Zahl der zugeordneten Agenten | viewer |
| `GET /tool-profiles/catalog` | Gruppen und ihre Werkzeuge aus dem Code, Kern-Werkzeuge | viewer |
| `POST /tool-profiles` | eigenes Profil anlegen | **admin** |
| `PUT /tool-profiles/{id}` | Name, Beschreibung, Gruppen, Werkzeuge ändern | **admin** |
| `POST /tool-profiles/{id}/reset` | mitgeliefertes Profil auf den Lieferstand setzen | **admin** |
| `DELETE /tool-profiles/{id}` | eigenes Profil löschen | **admin** |
| `PUT /agents/{agent_id}/tool-profile` | Profil, `tools_added`, `tools_removed` am Agenten setzen | editor, **nur Menschen** |

Fehler, nach ADR-0051:

- 409 `tool_profile_in_use` beim Löschen eines zugeordneten Profils, mit der
  Zahl der Agenten.
- 409 `tool_profile_builtin` beim Löschen eines mitgelieferten Profils.
- 422 `unknown_tool` bzw. `unknown_tool_group` bei Namen außerhalb des Katalogs.
- 422 `core_tool_not_removable` bei `ping`, `whoami` oder `report_problem` in
  `tools_removed`.
- 403 `human_only` bei einem agent-gebundenen Token an
  `PUT /agents/{id}/tool-profile`.

### 7.2 Wer pflegt Profile (W59-2)

**Entschieden (W59-2): Profile pflegen nur admins.** Ein Profil wirkt auf jeden Agenten,
der es nutzt, auch auf solche, die der Ändernde nicht angelegt hat. Das ist
Workspace-Konfiguration, kein Agenten-Detail. Lesen dürfen alle Mitglieder,
damit ein editor sieht, was er zuordnet.

### 7.3 Wer ordnet am Agenten zu

Ein editor ordnet zu, wie er auch sonst Agenten pflegt. **Nur Menschen**: Ein
agent-gebundener Token bekommt 403, auch der Builder. Das folgt aus P3a (der
Agent meldet, der Mensch passt an) und hat das Muster der Modell-Konfiguration
(`apps/api/src/who2be_api/services/agent_service.py#AgentService`, Gate
`is_agent_bound`). Eine Rechte-Ausweitung wäre es ohnehin nicht (3.3), aber ein
Agent soll seinen Werkzeugzuschnitt nicht selbst erweitern.

Folgen für bestehende Werkzeuge und Modelle:

- `AgentCreate` und `AgentUpdate` bekommen **keine** Profil-Felder. Damit
  ändern sich die Schemas von `create_agent` und `update_agent` nicht, und der
  Katalog wächst nicht. `AgentRead` zeigt die drei Felder (Ausgabe, kein
  Draht-Schema, `output_schema=None`).
- Der eigene Endpunkt gilt auch für **verwaltete** Agenten. `update_agent`
  lehnt sie ab (`apps/api/src/who2be_api/core/security.py#require_unmanaged`).
  Ohne diese Ausnahme könnte niemand dem Builder ein fehlendes Werkzeug
  freigeben, und P3a liefe beim wichtigsten Profil ins Leere.
- Der Start-Abgleich der Builder-Inhalte fasst die drei Spalten nicht an
  (4.2).

### 7.4 Protokoll

Jede Änderung landet im `audit_log`: `tool_profile.created`,
`tool_profile.updated`, `tool_profile.reset`, `tool_profile.deleted` mit
Profil-ID und Name, sowie `agent.tool_profile_changed` mit altem und neuem
Stand. Muster ist `agent.model_config_changed`.

### 7.5 MCP

**Keine neuen MCP-Werkzeuge.** Profile pflegt ein Mensch im Web. Werkzeugzahl
vorher und nachher: **100 → 100** (mit W1 vorher 101 → 101). Budget `tools/list`
gesamt: unverändert 114.203 von 180.000 Bytes, bis auf zwei Textzeilen:

- die `whoami`-Beschreibung nennt `tool_profile` (+ etwa 80 Bytes),
- die Server-`instructions` nennen den Meldeweg (+ etwa 120 Bytes, Abschnitt 8).

Die Startlast je Profil steht in 5.2.

## 8. Meldeweg, wenn ein Werkzeug fehlt (W59-6)

P3a verlangt zwei Dinge: Der Agent erfährt, dass ein Werkzeug am Profil
scheitert, und ein Mensch bekommt die Meldung.

**Fehlermeldung bei `tools/call`.** `PolicyFilterMiddleware.on_call_tool`
unterscheidet künftig zwei Fälle:

- Die Rechte verbergen das Werkzeug: Meldung wie heute („nicht freigeschaltet,
  prüfe deine Berechtigungen via whoami“).
- Nur das Profil verbirgt es:

  > Werkzeug `X` liegt nicht in deinem Werkzeug-Profil „Autor“. Brauchst du
  > es, melde es mit `report_problem` (`category="tool_request"`, in `note`
  > das Werkzeug und wofür). Ein Mensch passt dein Profil an.

  Die Meldung nennt keine Rechte und verspricht keine Freigabe.

**Woher der Agent den Namen kennt.** Aus `tools/list` nicht, das Werkzeug ist
ja unsichtbar. Er kennt ihn aus Playbooks, Resources oder dem System-Prompt.
Ein Satz in den Server-`instructions` deckt den Fall ab, in dem er es nicht
aufruft, sondern nur vermisst: „Fehlt dir ein Werkzeug, das ein Playbook nennt,
melde es mit `report_problem` und `category=\"tool_request\"`.“
(`apps/mcp/src/who2be_mcp/instructions.py#SERVER_INSTRUCTIONS`, der
2.048-Zeichen-Test bleibt eingehalten).

**Wohin die Meldung geht.** **Entschieden (W59-6): neue Kategorie `tool_request`
für `report_problem`**
(`packages/models/src/who2be_models/feedback.py#SystemFeedbackCategory`). Sie
landet im vorhandenen Kurations-Posteingang. Die Spalte `signal` hat keinen
Datenbank-CHECK (Migration 0059), es braucht also keine Migration, nur den
Enum-Wert. Der Posteingang zeigt bei `tool_request` einen Knopf „Profil des
Agenten öffnen“ (Paket Q5b). Die meldende `agent_id` steht schon heute an jeder
Rückmeldung.

Ein Fall (`report_case`, ADR-0053) passt nicht. Fälle beschreiben Verhalten
eines Agenten, das jemand bewerten soll. „Mir fehlt ein Werkzeug“ ist eine
Konfigurationsbitte.

## 9. Web-Oberfläche (grob)

Die Spezifikation erstellt @designer vor Q5a/Q5b. Festgelegt ist hier nur der
Umfang:

- **Einstellungen → Werkzeug-Profile** (nur admin schreibt, alle lesen): Liste
  mit Name, Werkzeugzahl und Zahl der Agenten. Bearbeiten über
  Gruppen-Schalter mit Werkzeugzahl je Gruppe, darunter einzelne Werkzeuge.
  Kern-Werkzeuge sind gesetzt und gesperrt. Bei mitgelieferten Profilen gibt es
  „Auf Lieferstand zurücksetzen“, Löschen nur bei eigenen. Entfallene
  Werkzeugnamen (3.3) erscheinen markiert.
- **Agent bearbeiten → Werkzeuge**: Profil wählen (erster Eintrag „Alle“),
  darunter „zusätzlich freigeben“ und „sperren“ je Werkzeug, die effektive Zahl
  sichtbarer Werkzeuge, und der Hinweis „Rechte gehen vor. Ein Profil blendet
  nur aus.“ Werkzeuge, die die Rechte verbergen, sind als solche markiert und
  nicht zuschaltbar. Auch beim verwalteten Builder bedienbar.
- **Posteingang**: Meldungen `tool_request` mit Sprung zum Agenten (8).
- Byte-Angaben zeigt die Oberfläche nicht. Die API kennt die Draht-Größe nicht,
  und eine Zahl, die nicht stimmt, ist schlechter als keine.

## 10. Paketschnitt

Seriell, je Paket höchstens acht Dateien, je Paket ein PR mit
Changelog-Fragment.

**Abgrenzung zu W1 (ADR-0058, P1 bis P4b).** W2 startet erst, wenn P3 und P4b
auf `main` sind (Reihenfolge des PM, Hotspot `apps/mcp/src/who2be_mcp/server.py`).
Die Dateien überschneiden sich trotzdem an vier Stellen: `main.py` und
`openapi.json` (W1 P2), `test_tool_payload_budget.py` (W1 P3),
`workspace_repository.py` (W1 P4a). Deshalb laufen W1- und W2-Pakete nicht
parallel. Bewusst **nicht** angefasst werden `tool_requirements.py` und
`server.py`: Die Gruppen liegen in einem neuen Modul, und die Filterung bleibt
in der Middleware.

**Q1 — Modell und SSoT** (Domäne `packages/models`, ohne Verhaltensänderung)

1. `packages/models/src/who2be_models/tool_profiles.py` (neu: `TOOL_GROUPS`,
   `CORE_TOOLS`, `BUILTIN_PROFILES`, `ToolProfileGrant`, Ein- und
   Ausgabemodelle, `effective_tool_set` und die Sichtbarkeit mit Profil als
   Hülle um `is_tool_visible`/`is_tool_visible_for`; `tool_requirements.py`
   bleibt unverändert)
2. `packages/models/src/who2be_models/whoami.py` (Feld `tool_profile`)
3. `packages/models/src/who2be_models/feedback.py` (`tool_request`)
4. `packages/models/src/who2be_models/__init__.py` (Export)
5. `packages/models/tests/test_tool_profiles.py` (neu: jedes Werkzeug in genau
   einer Gruppe, Kern nicht abwählbar, Formel, Rechte gehen vor, mitgelieferte
   Profile decken die Builder-Inhalte DE und EN, Profil „Builder“ enthält
   `workarea_read` (W59-4), Rot-Probe)
6. `changelog.d/<slug>.added.md`

**Q2a — Datenbank und Repository** (Domäne `apps/api`, Datenhaltung)

1. `apps/api/src/who2be_api/migrations/0110_tool_profile.sql` (neu, Nummer
   0110 vom PM vergeben, vor dem Anlegen gegen `origin/main` prüfen)
2. `apps/api/src/who2be_api/migrations/README.md` (Hinweis Doppelschicht)
3. `apps/api/src/who2be_api/repositories/tool_profile_repository.py` (neu)
4. `apps/api/src/who2be_api/repositories/workspace_repository.py` (Seed neuer
   Workspaces, Zuordnung des verwalteten Builders nach W59-3 = A)
5. `apps/api/src/who2be_api/repositories/agent_repository.py` (Spalten lesen,
   `deep_copy` übernimmt sie)
6. `apps/api/tests/test_tool_profile_repository.py` (neu: RLS, Cascade,
   RESTRICT, Seed-Parität Migration/Code, Bestand bleibt „Alle“)
7. `changelog.d/<slug>.added.md`

**Q2b — API und `whoami`** (Domäne `apps/api`, Schnittstelle)

1. `apps/api/src/who2be_api/services/tool_profile_service.py` (neu: CRUD,
   Zuordnung, Audit, Fehlercodes)
2. `apps/api/src/who2be_api/routers/tool_profiles.py` (neu: Endpunkte aus 7.1)
3. `apps/api/src/who2be_api/main.py` (Router einhängen)
4. `apps/api/src/who2be_api/routers/whoami.py` (Feld `tool_profile`)
5. `apps/api/tests/test_tool_profiles_api.py` (neu: Rollen, `human_only`,
   verwalteter Builder, 409/422, Audit)
6. `apps/api/tests/test_whoami.py` (Feld `tool_profile`)
7. `docs/reference/openapi.json`
8. `changelog.d/<slug>.added.md`

Der Ladeweg aus 6.1 (Join in `_load_agent_tool_policy`) betrifft
`core/security.py` als neunte Datei. Liefert `whoami.py` das Feld über eine
eigene Repository-Abfrage, bleibt es bei acht. Die Paket-Karte entscheidet das
nach Lage des Codes, die Grenze von acht Dateien gilt.

**Q3 — MCP-Filter** (Domäne `apps/mcp`, ohne `server.py`)

1. `apps/mcp/src/who2be_mcp/policy_filter.py` (Profil in `tools/list` und
   `tools/call`, zwei Meldungen, TTL 60 s nach W59-5)
2. `apps/mcp/src/who2be_mcp/instructions.py` (Satz zum Meldeweg)
3. `apps/mcp/src/who2be_mcp/payload_report.py` (Referenzprofil „Builder mit
   Profil Builder“, Gruppen aus `who2be_models/tool_profiles.py`, keine
   zweite Kopie)
4. `apps/mcp/tests/test_policy_filter.py` (Profil, Kern, fail-open, Rechte
   gehen vor)
5. `apps/mcp/tests/test_tool_payload_budget.py` (Startziel 104.000 Bytes für
   „Builder mit Profil Builder“ aus 5.3, M2 je Profil)
6. `docs/mcp-payload-budget.md` (Tabelle je Profil)
7. `changelog.d/<slug>.changed.md`

Die `whoami`-Beschreibung (7.5) steht in `server.py`. Sie wird in Q3 nur
geändert, wenn `server.py` zu dem Zeitpunkt frei ist; sonst trägt die
`instructions`-Zeile den Hinweis allein.

**Q4 — System-Prompt-Block** (Domäne `apps/api`, Rendern)

1. `apps/api/src/who2be_api/services/placeholders/resolvers/tools.py` (Profil
   über `RenderContext.agent_id` laden, Formel aus Q1 anwenden)
2. `apps/api/tests/test_placeholder_renderer.py` (Test aus 3.2 auf das Profil
   erweitert)
3. `changelog.d/<slug>.changed.md`

**Q5a — Web: Profile verwalten** und **Q5b — Web: Zuordnung am Agenten und
Posteingang** (Domäne `apps/web`). Dateilisten nach der Spezifikation von
@designer. Je Paket höchstens acht Dateien, Bildschirmfotos und Messwerte nach
der Abgabe-Regel des Teams.

**Q6 — Builder-Hinweis** (Domäne Inhalte, optional). Ein Satz im
Builder-Playbook „Agent“ (DE und EN), dass ein neuer Agent ein passendes Profil
bekommen sollte, mit `BUILDER_CONTENT_VERSION` +1
(`apps/api/src/who2be_api/repositories/workspace_repository.py#BUILDER_CONTENT_VERSION`).
Nur nach W1 P4a, weil beide dieselben Dateien und dieselbe Versionszahl
anfassen.

Reihenfolge: Q1 → Q2a → Q2b → Q3 → Q4 → Q5a → Q5b → Q6. Q3 kann vor Q2b
gemergt werden, weil das Feld `tool_profile` optional ist und die Middleware
bei `None` wie heute filtert. Das Ziel „Builder deutlich unter 116 KB“ ist mit
Q2a (Zuordnung) und Q3 (Filter) erreicht und messbar.

## 11. Entscheidungen

Owner, 2026-10-21 (Telegram), wörtlich:

> „Alle wie empfohlen, aber W59-4 ja“

Damit gilt für diese ADR und alle W2-Pakete:

| Weiche | Frage | Entschieden | Verworfen |
| --- | --- | --- | --- |
| **W59-1** (4.1) | Woraus besteht ein Profil? | **C: Gruppen und einzelne Werkzeuge.** Neue Werkzeuge einer Gruppe kommen automatisch an, Einzelwerkzeuge bleiben möglich. | A: nur eine Werkzeugliste (jedes neue Werkzeug muss in jedes Profil nachgetragen werden, angepasste Profile veralten still). B: nur Gruppen (keine Feinsteuerung im Profil, nur am Agenten). |
| **W59-2** (7.2) | Wer pflegt Profile? | **admin.** Zuordnung am Agenten: editor, nur Menschen. | editor pflegt auch Profile (wirkt auf fremde Agenten). |
| **W59-3** (4.3) | Bekommt der verwaltete Builder automatisch „Builder“? | **A: ja, neue und bestehende Workspaces**, per Migration und Seed. Einzige Ausnahme von (d), begründet damit, dass der verwaltete Builder ohnehin vom Code gepflegt wird. Ein Mensch kann es zurück auf „Alle“ stellen (7.3). | B: nur neue Workspaces (Bestand behält 115,8 KB). C: nein, ein Mensch ordnet zu (das Ziel hängt dann an Handarbeit je Workspace). |
| **W59-4** (5.2) | Enthält „Builder“ das Lesen im Arbeitsbereich? | **Ja, `workarea_read` dazu** (abweichend von der Empfehlung): 85 Werkzeuge, `tools/list` 100.123 Bytes, Start 101.727 Bytes, −14.080 Bytes (−12,2 %) gegenüber „Alle“. | Nein (75 Werkzeuge, Start 95.590 Bytes, −17,5 %). |
| **W59-5** (6.2) | Wie schnell wirkt eine Änderung? | **Cache-TTL 60 s** statt 300 s. | 300 s bleiben (bis zu fünf Minuten Wartezeit nach einer Freigabe). |
| **W59-6** (8) | Wohin meldet der Agent ein fehlendes Werkzeug? | **`report_problem` mit neuer Kategorie `tool_request`**, Posteingang mit Sprung zum Agenten. | A: Kategorie `mcp` wie heute (geht zwischen echten Fehlern unter). B: `report_case` (Fall, fachlich falsch, siehe 8). |

Der Grundsatz vom 2026-10-16 bleibt unverändert (Abschnitt 2): „P1 ok“, P2a,
P3a, Rechte gehen vor, Standard „Alle“. W59-3 ist die einzige Ausnahme von (d)
und mit dieser Entscheidung ausdrücklich gedeckt.

Die Formel (3.1), die Gruppen (5.1) und die mitgelieferten Profile (5.2)
stehen im Code nur an einer Stelle, in `who2be_models/tool_profiles.py`
(Paket Q1). MCP-Filter, System-Prompt-Block, Workspace-Seed und
`payload_report` beziehen sie von dort. Die SQL-Migration kann das Modul nicht
importieren; ihr Seed wird per Paritätstest dagegen geprüft (Q2a).

Alles Übrige in dieser ADR folgt aus dem Owner-Wortlaut in Abschnitt 2 oder
aus dem Repo und hängt an keiner Weiche.

## 12. Konsequenzen

**Positiv.**

- Der Builder startet mit 101,7 statt 115,8 KB (−14.080 Bytes, −12,2 %),
  ohne ein Recht zu verlieren und ohne einen Schritt seiner Playbooks (5.2).
  Er behält das Lesen im Arbeitsbereich (`workarea_read`, W59-4).
- Auch andere Agenten mit vielen Rechten lassen sich zuschneiden, ohne an den
  Rechten zu drehen. Rechte und Sichtbarkeit sind getrennte Fragen.
- System-Prompt und `tools/list` bleiben deckungsgleich (3.2).
- Keine neue Verbindungs-URL, kein neues MCP-Werkzeug, Katalog unverändert.

**Negativ.**

- Was ein Agent nicht sieht, kann er nicht nutzen. Ein zu enges Profil endet
  in einer Meldung und Wartezeit, bis ein Mensch reagiert (Abschnitt 8, 6.2).
- Ein neues Werkzeug braucht künftig zusätzlich eine Gruppe (5.1). Ein neues
  Werkzeug in einer neuen Gruppe erscheint in keinem Profil außer „Alle“, bis
  eine Migration entscheidet, welche mitgelieferten Profile die Gruppe
  bekommen.
- Eine Tabelle, drei Spalten und eine Einstellungsseite mehr.
- Ausnahme von (d) beim verwalteten Builder (W59-3 = A): Er bekommt auch in
  bestehenden Workspaces das Profil „Builder“, ein Mensch kann zurückstellen.
- W59-4 kostet gegenüber der Empfehlung 6.137 Bytes je Builder-Start
  (101.727 statt 95.590). Dafür muss kein Mensch `workarea_read` nachträglich
  freigeben, wenn der Builder Rohmaterial oder Tabellen lesen soll.
- Die Cache-TTL von 60 s (W59-5) erzeugt bis zu fünfmal so viele
  `whoami`-Aufrufe je aktivem Token wie heute.

**Neutral.** Die API setzt Profile nicht durch. Wer die REST-API direkt
aufruft, wird nach Rechten beurteilt wie bisher. Das ist gewollt, weil ein
Profil kein Recht ist (3.3).
