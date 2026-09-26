# MCP-Payload-Budget

Referenz (intern). Wie gross eine MCP-Werkzeug-Antwort werden darf, welche
Werkzeuge die Grenze reissen, und wie man sie zuschneidet.

## Das Problem: ein stiller Verlust

Die Laufzeit des Konsumenten (Claude Code, Claude.ai) deckelt eine **einzelne**
Tool-Antwort bei etwa **50.000 Zeichen**. Darueber wird die Antwort nicht
gekuerzt und nicht abgelehnt — sie wird **weggelegt**. Das Modell sieht sie
nicht, der Server erfaehrt nichts davon, und es gibt keinen Fehler in einem Log.

Fuer diesen Server ist das mehr als eine Unbequemlichkeit: die grossen
Lese-Werkzeuge sind genau die, mit denen ein Agent seine Arbeit **beginnt**
(`get_persona` als Boot-Schritt, `list_playbooks` fuer die Auswahl). Reisst dort
das Budget, startet der Agent ohne seine Persona oder ohne seinen Katalog — und
haelt das fuer einen leeren Workspace statt fuer einen Fehler.

Das ist eine Randbedingung des Konsumenten, **keine Who2Be-Einstellung**. Wenn
ein Budget-Test reisst, ist die Antwort zu gross; die Grenze ist nicht
verhandelbar.

## Die Ursache: Editor-JSON in der Antwort

Der Ballast ist fast immer dasselbe: **BlockNote-Editor-JSON**. Die Inhalte
liegen als Editor-Dokument in der Datenbank, und die Lese-Werkzeuge geben dieses
Dokument unveraendert weiter:

| Entitaet | Feld mit dem Editor-JSON |
| --- | --- |
| Persona, Agent | `persona.content.content.blocks` |
| Playbook | `content.body` (stringifiziertes JSON) |
| Resource | `content.blocks` |
| Externes Tool | `content.usage_notes` |

Ein Editor-Block traegt pro Absatz rund **250 Zeichen Struktur** (`props`,
`styles`, `children`, IDs) auf etwa 60 Zeichen Nutztext. Das Verhaeltnis ist der
ganze Befund: die Payload besteht ueberwiegend aus Editor-Verwaltung, nicht aus
Inhalt.

Fuer einen Agenten ist dieses JSON in den meisten Faellen **doppelt bezahlt**:

- `get_persona` und `fetch_agent` liefern den Inhalt **ohnehin** schon als
  Plain-Text in `body_rendered` bzw. `system_prompt_rendered`. Die Bloecke sind
  dieselbe Prosa ein zweites Mal, nur teurer.
- `list_playbooks` beantwortet die Frage „welches Playbook passt?\" — das traegt
  Name, Beschreibung, Tags und Triggers. Der Body gehoert in den gezielten
  Einzelabruf (`fetch_playbook`), nicht in jeden Katalog-Eintrag.
- `list_versions` beantwortet „welche Versionen gibt es?\" — das traegt
  `version`, `status`, `created_by`, `created_at`. Den Inhalt einer bestimmten
  Version liefert `get_version`.

Wer die Bloecke strukturell braucht (ein Editor-Frontend etwa), bekommt sie
weiterhin — siehe `format` unten.

## Inventar (Messung 2026-09-26, Live-Workspace)

Gemessen wurde die serialisierte Antwort gegen echte Workspace-Daten, nicht
geschaetzt.

**Ueber der Grenze:**

| Werkzeug | Zeichen | Ursache |
| --- | --- | --- |
| `list_playbooks` | 277.151 | jeder Katalog-Eintrag traegt den vollen `content.body` |
| `get_persona` | 225.559 | `persona.content.content.blocks` + Playbook-Bodies |
| `fetch_playbook` | 64.971 | `content.body` neben `body_rendered` |
| `fetch_agent` | 54.912 | Persona-Bloecke neben `system_prompt_rendered` |

`list_versions` steht nicht in der Tabelle, weil die Messung von der Historie
des gewaehlten Elements abhaengt: die Antwort ist Historien-Laenge **mal** Body.
Bei einem vielfach versionierten Playbook reisst sie, bei einem neuen nicht —
die gefaehrlichste Sorte, weil sie mit dem Alter des Workspace erst entsteht.

**Unter der Grenze (kein Handlungsbedarf):**

| Werkzeug | Zeichen |
| --- | --- |
| `list_external_tools` | 41.430 |
| `fetch_resource` (groesste Resource, 92 Bloecke) | ~22.000 |
| `search` (`limit=50`) | 13.928 |
| `list_triggers` | 11.712 |
| `list_resources` | 786 |

`list_resources` ist das Vorbild: es liefert `ResourceSummary` mit nur
`block_count` statt der Bloecke — 786 Zeichen fuer denselben Zweck, den
`list_playbooks` mit 277.151 Zeichen erfuellt.

## Die Loesung: `format="text"`, additiv

Die betroffenen Werkzeuge haben einen Parameter `format`:

- **`"full"` (Default)** — unveraenderte Antwort mit Editor-JSON. Bestehende
  Konsumenten merken von der Aenderung nichts.
- **`"text"`** — der Body bleibt leer, **alles andere bleibt vollstaendig**.

Bewusst **opt-in** und nicht als neuer Default: ein Konsument, der die Bloecke
strukturell verarbeitet, soll nicht durch ein Server-Update brechen. Ein
unbekannter Wert wird mit einem `ToolError` abgelehnt, statt still `full` zu
liefern — ein Tippfehler soll auffallen und nicht als scheinbar erfolgreicher,
aber zu grosser Aufruf enden.

Was `format="text"` **nicht** wegnimmt:

| Werkzeug | leer | bleibt vollstaendig |
| --- | --- | --- |
| `get_persona` | `persona.content.content.blocks` | `body_rendered`, Beschreibung, Traits, Tags, **Modi** |
| `fetch_agent` | Persona-Bloecke | `system_prompt_rendered`, Name, Locale, Template-ID |
| `list_playbooks` | `content.body` je Eintrag | Name, Beschreibung, Tags, Triggers, Typ, `compose_children` |
| `list_versions` | `content.body` / `.blocks` / `.usage_notes` | `version`, `status`, `locale`, `created_by`, `created_at`, Beschreibung |

Der Zuschnitt betrifft **nur die Antwort-Kopie** (`model_copy`); die Daten in
der Datenbank und die REST-Antwort bleiben unberuehrt.

Bei `list_versions` ist der Zuschnitt **typ-agnostisch**: jedes Content-Modell
traegt seinen Body unter einem anderen Namen, und geleert wird nur, was das
jeweilige Modell wirklich hat (`_HEAVY_CONTENT_FIELDS` in
`apps/mcp/src/who2be_mcp/server.py`). Ein neues Content-Modell bricht hier
nichts — es wird bloss nicht zugeschnitten, bis sein Body-Feld in der Liste
steht.

## Regressionsschutz

`apps/mcp/tests/test_tool_payload_budget.py` haelt beide Budgets: die
Kataloggroesse von `tools/list` (WP10, ADR-0047) und die Antwortgroesse je
Werkzeug.

Die Antwort-Tests messen die **serialisierte** Antwort (`model_dump_json`),
nicht Feldnamen — sie halten die Zusage „die Antwort kommt an\", nicht die
Zusage „ein Feld heisst so\". Jeder Test fuehrt seine **Rot-Probe mit**: er
belegt zuerst, dass der `full`-Pfad die Grenze mit demselben Fixture
tatsaechlich reisst, und danach, dass `text` sie haelt. Entfaellt der Zuschnitt,
werden beide Pfade gleich gross und der Test faellt. Ohne diese erste Assertion
koennte ein zu kleines Fixture den Test gruen halten, ohne dass der Text-Pfad
etwas beweist.

**Wenn ein Budget-Test reisst:** die Antwort kleiner machen — nicht die Grenze
anheben. Die 50.000 Zeichen sind nicht unsere Zahl.

**Ein neues Lese-Werkzeug** mit potenziell grosser Antwort braucht denselben
Nachweis: ein Fixture, das den `full`-Pfad ueber die Grenze bringt, und eine
Zusage fuer den Zuschnitt. Eine Liste, die ein inhaltstragendes Feld je Eintrag
mitliefert, ist der Verdachtsfall — Listen skalieren mit dem Workspace, und ein
Werkzeug, das heute bei acht Eintraegen passt, reisst bei achtzig.

## Verwandt

- [`mcp-claude-code.md`](mcp-claude-code.md) — den Server anbinden
- `apps/mcp/tests/test_tool_payload_budget.py` — haelt zusaetzlich das
  **Katalog**-Budget von `tools/list` (WP10 in
  [`adr/0047-agent-workarea-knowledge-base.md`](adr/0047-agent-workarea-knowledge-base.md)):
  andere Grenze, gleiche Versagensart — dort fliegt nicht eine Antwort, sondern
  die ganze Werkzeug-Liste
