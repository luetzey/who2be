# ADR-0056 — MCP: lesende Werkzeuge liefern standardmäßig lesbaren Text, Editor-JSON nur auf Wunsch

- Status: **Entwurf.** Die Richtung hat der Owner entschieden (Abschnitt 2).
  Offen ist eine Weiche zur Form der Antwort (Abschnitt 4, W1). Bis sie
  entschieden ist, wird nicht gebaut.
- Datum: 2026-10-05
- Gemessen gegen: `origin/main` @ `676fc7e0`. Code-Aussagen tragen einen
  Symbolanker (Konvention `docs/code-references.md`).
- Grundlage: Kanban-Karte t_409f1585, Owner-Entscheidung vom 2026-10-03.
- Bezug: `docs/mcp-payload-budget.md` (Antwort-Budget, `format="text"` als
  Opt-in), ADR-0047 (tools/list-Budget), ADR-0053 §6.7 (Umfang der
  MCP-Oberfläche, Reserve im tools/list-Budget), ADR-0030 (MCP-Write-Tools,
  PUT-Semantik), ADR-0021 (Playbook-Resource-Links).

## Inhalt

1. Kontext und Befund
2. Entscheidung (Owner-Wortlaut)
3. Was festgelegt ist
4. Offene Weiche W1: die Form der Text-Antwort
5. Abwärtsverhalten und der Schreibpfad
6. Umsetzung in Paketen
7. Konsequenzen

## 1. Kontext und Befund

Die Inhalte (Persona-Profil, Playbook-Body, Resource, System-Prompt,
Nutzungshinweise externer Tools) liegen als BlockNote-Editor-Dokument in der
Datenbank. Mehrere lesende Werkzeuge geben dieses Dokument unverändert an den
Agenten weiter, teils als Objekt-Liste, teils als JSON-**String** in einem
Textfeld. Der Owner hat das so beschrieben: „manche Tools [geben] auch immer
noch die Sonderzeichen zurück, wie Slash, Anführungsstriche etc.“ Beispiel:
`list_system_prompts`, dessen `content.body` ein stringifiziertes
BlockNote-Dokument ist.

Seit `docs/mcp-payload-budget.md` haben fünf Werkzeuge einen Parameter
`format` mit `"full"` als Default und `"text"` als Opt-in
(`apps/mcp/src/who2be_mcp/server.py#_RESPONSE_FORMATS`,
`apps/mcp/src/who2be_mcp/server.py#_PLAYBOOK_FORMATS`). Dass `full` Default
blieb, war damals Absicht, damit kein bestehender Konsument bricht. Diese ADR
kehrt den Default um.

### 1.1 Inventar der lesenden Werkzeuge

Erhoben aus `mcp.list_tools()` am Stand `676fc7e0` (86 Werkzeuge). Lesend sind
37. Davon tragen **zwölf** Editor-JSON in der Antwort:

| Werkzeug | Editor-JSON in | `format` heute |
| --- | --- | --- |
| `get_persona` | `persona.content.content.blocks`, `persona.content.modes[].identity_add/output_style_override/anti_patterns`, `playbooks[].content.body` | `full` (Default) / `text` |
| `fetch_agent` | `persona.content.content.blocks`, Modus-Blöcke | `full` / `text` |
| `list_playbooks` | `[].content.body` | `full` / `text` |
| `fetch_playbook` | `playbook.content.body`, `composed_playbooks[].content.body`, `linked_resources[].content.blocks` | `full` / `text` / `outline` |
| `list_versions` | `[].content.*` je Entität, Modus-Blöcke | `full` / `text` |
| `fetch_resource` | `content.blocks`, `inline_sub_resources[].content.blocks` | — |
| `get_system_prompt` | `content.body` (String) | — |
| `list_system_prompts` | `[].content.body` (String) | — |
| `get_external_tool` | `content.usage_notes` (String) | — |
| `list_external_tools` | `[].content.usage_notes` (String) | — |
| `get_version` | `content.*` je Entität | — |
| `diff_versions` | `changes[].before/after` (Rohwerte inkl. Blöcke und Body-Strings) | — |

Die übrigen 25 lesenden Werkzeuge tragen kein Editor-JSON und bleiben
unverändert: `ping`, `whoami`, `list_triggers`, `list_placeholders`,
`list_resources`, `list_agents`, `get_agent`, `list_resource_blocks`,
`find_usages`, `get_feedback`, `search`, `search_content`, `search_kb`,
`neighbors`, `search_memory`, `list_memories`, `list_test_cases`,
`query_table`, `list_tables`, `describe_table`, `timeline`,
`list_category_rules`, `read_artifact`, `list_artifacts`, `search_workarea`.
`list_placeholders` liefert in `example` ein Inline-Element als Objekt. Das
ist die Schreibvorlage für `create_system_prompt` und bleibt so.

### 1.2 Zwei Lücken im heutigen `text`-Pfad

Auch der bestehende Opt-in-Pfad hält das Versprechen „ohne Editor-JSON“ nicht
ganz:

- `fetch_playbook(format="text")` leert nur `playbook.content.body`. Die
  Bodies in `composed_playbooks` und die Blöcke in `linked_resources` bleiben
  stehen (`apps/mcp/src/who2be_mcp/server.py#fetch_playbook`).
- `get_persona`, `fetch_agent` und `list_versions` leeren das Profil, aber
  nicht die Modus-Blöcke (`identity_add`, `output_style_override`,
  `anti_patterns` sind `list[ResourceBlock]`,
  `packages/models/src/who2be_models/persona.py#PersonaMode`). Gerade diese
  Felder liest ein Agent laut Werkzeugübersicht aus `content.modes`
  (`apps/api/src/who2be_api/services/placeholders/resolvers/tools.py#_TOOLS`).

### 1.3 Escaping entsteht auch ohne Editor-JSON

Jede Werkzeug-Antwort, die ein Pydantic-Modell zurückgibt, wird als **ein
JSON-Text** an den Client geschickt. Ein Markdown-Feld darin wird dabei
escaped. Probe gegen FastMCP 3.4.7 (lokal, 2026-10-05):

```text
Modell mit Markdown-Feld:  '{"name":"n","body":"# Titel\\n\\nHallo \\"Welt\\""}'
Werkzeug gibt str zurück:  '# Titel\n\nHallo "Welt"'
```

Das Leeren der Blöcke allein beseitigt also die verschachtelten
Anführungszeichen, nicht aber `\n` und `\"` im lesbaren Feld selbst. Daraus
folgt die offene Weiche W1.

## 2. Entscheidung (Owner-Wortlaut)

Owner, 2026-10-03, wörtlich: **„2. a“**. Zur Auswahl standen:

- (a) lesende Werkzeuge liefern standardmäßig lesbaren Text, Editor-JSON nur
  auf Wunsch — **gewählt**;
- (b) nur eine Option nachrüsten, Default bleibt JSON;
- (c) JSON als Objekt statt als String.

## 3. Was festgelegt ist

Die folgenden Punkte sind im Repo belegt oder folgen direkt aus der
Owner-Entscheidung. Sie gelten unabhängig von W1.

**3.1 Ein Parameter, zwei Werte.** Alle zwölf Werkzeuge aus 1.1 haben den
Parameter `format: str` mit den Werten `"text"` (Default) und `"full"`.
`fetch_playbook` behält zusätzlich `"outline"`. Kein neuer Name, weil fünf
Werkzeuge den Parameter schon tragen und Aufrufer mit explizitem
`format="full"` oder `format="text"` weiter funktionieren. Typ bleibt `str`
mit Laufzeitprüfung (`_validate_response_format`); ein `Literal` würde jedes
inputSchema um eine `enum` vergrößern, ohne dass es zusätzlich etwas abfängt.
Unbekannte Werte werden weiter mit `ToolError` abgelehnt.

**3.2 `"full"` bleibt bitgleich.** `format="full"` liefert genau die heutige
Default-Antwort, also das Modell aus der REST-Antwort ohne Zuschnitt. Für die
fünf Bestandswerkzeuge ist das der heutige Default, für die sieben neuen die
heutige einzige Antwort. Ein Regressionstest je Werkzeug hält das fest.

**3.3 `"text"` enthält kein Editor-JSON.** Weder als String noch als
Block-Liste, auch nicht in verschachtelten Feldern (1.2). Lesbar wird der
Inhalt so:

- Persona, Agent, Playbook: aus dem serverseitigen Render, den es schon gibt
  (`body_rendered` bzw. `system_prompt_rendered`, Platzhalter aufgelöst).
- Resource, System-Prompt, externes Tool, Versions-Snapshots, Modus-Felder:
  über die kanonische Klartext-Serialisierung, die schon Single Source für
  `before_text`/`after_text` ist
  (`apps/api/src/who2be_api/services/content_text.py#blocknote_body_text`,
  `apps/api/src/who2be_api/services/placeholders/_core.py#blocks_plain_text`).
  Platzhalter erscheinen dort als stabile `{{kind:target_id}}`-Tokens, ohne
  Datenbankzugriff. Der MCP-Prozess hat keinen DB-Zugriff und importiert
  `who2be_api` nicht. Deshalb ziehen die reinen Funktionen (ohne asyncpg) nach
  `packages/models` um, und die API re-exportiert sie unter den alten Namen.
  So bleibt es eine Quelle; eine Kopie im MCP wäre eine zweite.
- `diff_versions`: `before_text`/`after_text` bleiben, `changes` behält `path`
  und `op`, die Rohwerte `before`/`after` entfallen.

**3.4 Wann `full` nötig ist, steht in der Beschreibung.** Jede der zwölf
Werkzeugbeschreibungen nennt den Default und genau einen Satz zu `full`:
„Für `update_*` (PUT, Vollstand) oder strukturelle Verarbeitung:
`format="full"`.“ Bei den fünf Bestandswerkzeugen ersetzt dieser Satz die
heutigen längeren `format`-Absätze. Netto soll das tools/list-Payload dadurch
nicht wachsen (Budget-Lage in Abschnitt 7).

**3.5 Jede `text`-Antwort trägt den Hinweis selbst.** Unabhängig von der
Beschreibung enthält jede `text`-Antwort eine kurze Zeile, dass
`format="full"` den Editor-Vollstand für `update_*` liefert. Begründung in
Abschnitt 5.

## 4. Offene Weiche W1: die Form der Text-Antwort

Abschnitt 1.3 zeigt: solange die Antwort ein JSON-Objekt ist, bleiben `\n` und
`\"` im lesbaren Feld. Die Frage ist, ob das reicht.

**Option A — gleiche Hülle, lesbare Felder.** Die Antwort bleibt ein
JSON-Objekt mit den heutigen Feldnamen. Editor-Felder werden geleert, der
Inhalt steht in einem additiven Textfeld (`body_rendered`/`body_text`). Wo das
Pflichtfeld nicht leer sein darf (`SystemPromptTemplateContent.body`,
`min_length=1`), nimmt das MCP ein eigenes Antwortmodell.
Vorteil: maschinenlesbar wie heute, kleinster Umbau, `JSON.parse` beim
Aufrufer funktioniert weiter. Nachteil: Das Escaping, das der Owner moniert,
bleibt im Textfeld (`\n`, `\"`). Das ist die heutige Form von
`format="text"`, nur als Default und ohne die Lücken aus 1.2.

**Option B — Markdown-Dokument.** Unter `text` gibt das Werkzeug einen
Markdown-String zurück: oben ein kompakter Kopf mit den Metadaten, die ein
Agent für Folgeaufrufe braucht (`id`, Name, Version, Status, Locale, Tags,
Trigger, bei Playbooks die `sections` mit `block_id`), darunter der Inhalt als
Text, bei Listen ein Abschnitt je Eintrag.
Vorteil: Das ist wörtlich, was der Owner beschrieben hat, also kein JSON und
kein Escaping. Die Antwort wird außerdem deutlich kleiner als jede
JSON-Variante. Nachteil: Es ist ein Formatbruch. Wer heute `format="text"`
setzt und das Ergebnis als JSON parst, bricht. Belegt ist das an genau einer
Stelle, der E2E-Probe
`apps/web/e2e/review-gate.spec.ts#agentSees`. Sie wird auf `format="full"`
umgestellt. Außerdem muss der Kopf je Werkzeug definiert werden.

**Option C — beides in einer Antwort.** Das Werkzeug gibt Markdown als
Text-Content und das JSON-Objekt (Variante A) als `structuredContent` zurück.
FastMCP kann das (`ToolResult(content=…, structured_content=…)`, lokal
geprobt). Vorteil: Das Modell sieht Markdown, ein strukturierter Client
bekommt JSON. Nachteil: Ob ein Client beides an das Modell gibt, entscheidet
der Client, nicht wir. Tut er das, verdoppelt sich die Antwort, und das
50.000-Zeichen-Budget aus `docs/mcp-payload-budget.md` reißt früher. Belegen
lässt sich das für Claude Code und Claude.ai von hier aus nicht.

**Empfehlung: B.** Nur B erfüllt den Owner-Wortlaut ohne Rest, und der einzige
belegte JSON-Parser des `text`-Pfads ist eine Testprobe, die umgestellt wird.
A wäre ein halber Schritt, der dieselbe Beschwerde wieder auslöst. C hängt an
Clientverhalten, das wir nicht belegen können.

## 5. Abwärtsverhalten und der Schreibpfad

**Aufrufer ohne `format`** bekommen nach der Umstellung `text` statt `full`.
Das ist die Owner-Entscheidung. Explizites `format="full"` und
`format="outline"` verhalten sich unverändert. Explizites `format="text"`
liefert unter A dieselbe Form wie heute (ohne die Lücken aus 1.2), unter B
Markdown.

**Das Risiko liegt beim Schreiben.** Die `update_*`-Werkzeuge haben
PUT-Semantik: `content` ist der vollständige neue Stand
(`packages/models/src/who2be_models/persona.py#PersonaUpdate`,
`packages/models/src/who2be_models/playbook.py#PlaybookUpdate`). Die
Builder-Playbooks schreiben genau diesen Ablauf vor: erst lesen, dann
„update_persona(persona_id, content)“
(`apps/api/src/who2be_api/repositories/builder_playbook_persona_body.json@676fc7e0`).
Heute liefert der Lese-Default die Blöcke mit, nach der Umstellung nicht mehr.
Ein Schreiber, der die Default-Antwort als Vorlage nimmt, würde das Profil
beim nächsten PUT leeren.

Abgesichert wird das in drei Schichten, weil eine einzelne Prosa-Regel leicht
überlesen wird:

1. **In der Antwort selbst** (3.5): Jede `text`-Antwort sagt, dass für
   `update_*` `format="full"` zu holen ist. Diesen Hinweis sieht der Schreiber
   in dem Moment, in dem er die Vorlage liest.
2. **In den Beschreibungen** der fünf `update_*`-Werkzeuge: ein Satz „Vorlage
   mit `format="full"` lesen; `content` ersetzt den Stand vollständig.“ Das
   ist nur Beschreibungstext. Verhalten und Schema der Schreibwerkzeuge
   bleiben unverändert (Out-of-Scope der Karte).
3. **In der Builder-Resource „Agent-Bau-Konventionen“** (DE und EN), eine
   Regel. Der Content-Sync beim Start überträgt sie in jeden Workspace
   (`apps/api/src/who2be_api/repositories/workspace_repository.py#sync_managed_builder_content`).

Schicht 2 und 3 müssen **vor** der Default-Umstellung auf `main` sein
(Paket 2 vor Paket 3).

Ein serverseitiger Schutz („PUT mit leeren Blöcken auf eine Version mit
Inhalt ablehnen“) würde den Fehler hart abfangen. Er ändert aber das
Verhalten eines Schreibwerkzeugs und liegt damit außerhalb dieser Karte. Er
ist als Folgekarte vorgemerkt, nicht beschlossen.

## 6. Umsetzung in Paketen

Seriell, je Paket höchstens acht Dateien, je Paket ein PR mit
Changelog-Fragment. Die Dateilisten gelten für Option B. Unter A entfallen in
Paket 1 der Markdown-Renderer und sein Test, unter C kommt nichts hinzu.

**Paket 1 — Grundlage, ohne Verhaltensänderung.** Die Klartext-Serialisierung
zieht nach `packages/models`, dazu der Text-Renderer im MCP. Kein Werkzeug
ändert seine Antwort.

1. `docs/adr/0056-mcp-lesende-werkzeuge-text-default.md` (Status → Accepted)
2. `packages/models/src/who2be_models/blocknote_text.py` (neu)
3. `packages/models/tests/test_blocknote_text.py` (neu)
4. `apps/api/src/who2be_api/services/placeholders/_core.py` (Re-Export)
5. `apps/api/src/who2be_api/services/content_text.py` (Import aus 2)
6. `apps/mcp/src/who2be_mcp/text_view.py` (neu: Text-Darstellung je Entität)
7. `apps/mcp/tests/test_text_view.py` (neu)
8. `changelog.d/mcp-text-view-grundlage.changed.md`

**Paket 2 — Hinweis für Schreiber, vor der Umstellung.**

1. `apps/mcp/src/who2be_mcp/server.py` (nur Beschreibungen der fünf `update_*`)
2. `apps/api/src/who2be_api/repositories/builder_resource_conventions_body.json`
3. `apps/api/src/who2be_api/repositories/en/builder_resource_conventions_body.json`
4. `apps/mcp/tests/test_tool_payload_budget.py` (Budget-Gegenprobe)
5. `changelog.d/mcp-update-format-full-hinweis.changed.md`

**Paket 3 — Default-Umstellung der fünf Bestandswerkzeuge**
(`get_persona`, `fetch_agent`, `list_playbooks`, `fetch_playbook`,
`list_versions`), einschließlich der Lücken aus 1.2.

1. `apps/mcp/src/who2be_mcp/server.py`
2. `apps/mcp/tests/test_tool_payload_budget.py`
3. `apps/mcp/tests/test_resource_tools.py`
4. `apps/mcp/tests/test_fetch_agent_tool.py`
5. `apps/mcp/tests/test_reverse_version_tools.py`
6. `apps/mcp/tests/test_server.py`
7. `apps/web/e2e/review-gate.spec.ts` (auf `format: 'full'`)
8. `changelog.d/mcp-text-default.changed.md`

Ein Probelauf mit umgestelltem Default (lokal, ohne Commit) macht genau zwölf
Bestandstests rot: acht in Datei 2, vier in Datei 3. Alle scheitern an der
Annahme „Default ist `full`“.

**Paket 4 — `format` für die sieben übrigen Werkzeuge**
(`fetch_resource`, `get_system_prompt`, `list_system_prompts`,
`get_external_tool`, `list_external_tools`, `get_version`, `diff_versions`).

1. `apps/mcp/src/who2be_mcp/server.py`
2. `apps/mcp/tests/test_resource_tools.py`
3. `apps/mcp/tests/test_system_prompt_tools.py`
4. `apps/mcp/tests/test_external_tool_tools.py`
5. `apps/mcp/tests/test_reverse_version_tools.py`
6. `apps/mcp/tests/test_tool_payload_budget.py`
7. `changelog.d/mcp-text-default-restliche-werkzeuge.changed.md`

**Paket 5 — Doku und Werkzeugübersicht im System-Prompt.**

1. `docs/mcp-payload-budget.md` (`text` ist Default; der Abschnitt „Offen“
   schrumpft, weil `list_system_prompts` und `diff_versions` unter `text`
   darunter liegen)
2. `docs/mcp-claude-code.md`
3. `docs/agent-axes.md`
4. `apps/api/src/who2be_api/services/placeholders/resolvers/tools.py`
   (`get_persona`: Modi stehen im Text, nicht mehr nur in `content.modes`)
5. der zugehörige API-Test der Werkzeugübersicht
6. `changelog.d/mcp-text-default-doku.changed.md`

**Prüfungen je Werkzeug** (ab Paket 3): eine **Rot-Probe**, die im Default
einen JSON-String oder eine Block-Liste findet und mit `format="full"`
nachweislich anschlägt (dieselbe Methode wie die bestehenden Budget-Tests, die
erst den `full`-Pfad reißen lassen), ein **Regressionstest** `full` ist
bitgleich zur REST-Antwort, ein **Budget-Test** für die Antwortgröße.
`test_every_format_aware_tool_has_a_budget_test` erzwingt Letzteres für
jedes Werkzeug mit `format`.

## 7. Konsequenzen

**Positiv.** Agenten bekommen ohne Zutun lesbaren Inhalt. Die Antwortgrößen
sinken deutlich. Die drei Fälle, die `docs/mcp-payload-budget.md` als „offen“
führt, lösen sich dadurch teilweise: `list_system_prompts` liegt unter `text`
unter der Grenze, und `diff_versions` verliert die Rohwerte. `get_system_prompt`
bleibt strukturell nah an der Grenze, weil der Body der Zweck ist.

**Negativ.** Der Default-Wechsel ist für Aufrufer ohne `format` ein
Verhaltensbruch. Das ist gewollt. Schreiber müssen `format="full"` kennen
(Abschnitt 5). Unter Option B ist die Default-Antwort nicht mehr
maschinenlesbar. Wer Struktur braucht, nimmt `full`.

**tools/list-Budget.** Am Stand `676fc7e0` misst `tools/list` 139.010 Bytes
bei 86 Werkzeugen, Budget 160.000
(`apps/mcp/tests/test_tool_payload_budget.py#_PAYLOAD_BUDGET_BYTES`).
ADR-0053 §6.7 plant noch acht weitere Werkzeuge aus seiner Liste ein. Sieben
neue `format`-Parameter kosten im Schema je rund 50 Bytes; die
Beschreibungssätze gleichen die Kürzung der fünf langen `format`-Absätze aus
(3.4). Ziel ist netto kein Wachstum. Das misst der bestehende Guard je Paket.
