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
- `list_playbooks` beantwortet die Frage „welches Playbook passt?“ — das traegt
  Name, Beschreibung, Tags und Triggers. Der Body gehoert in den gezielten
  Einzelabruf (`fetch_playbook`), nicht in jeden Katalog-Eintrag.
- `list_versions` beantwortet „welche Versionen gibt es?“ — das traegt
  `version`, `status`, `created_by`, `created_at`. Den Inhalt einer bestimmten
  Version liefert `get_version`.

Dazu kommt das Escaping: solange die Antwort ein JSON-Objekt ist, steht jedes
lesbare Feld darin mit `\n` und `\"` (ADR-0056, Abschnitt 1.3). Wer die Bloecke
strukturell braucht (ein Editor-Frontend, ein `update_*`-Aufruf), bekommt sie
weiterhin — siehe `format` unten.

## Inventar (Messung 2026-09-26, Live-Workspace, vor ADR-0056)

Gemessen wurde die serialisierte Antwort gegen echte Workspace-Daten, nicht
geschaetzt. Die Zahlen beschreiben die damalige Default-Antwort, also das, was
heute `format="full"` liefert. Unter dem heutigen Default `format="text"`
bleiben die Werkzeuge aus den Tabellen „Ueber der Grenze“ und
„Beobachtungsposten“ mit den Fixtures der Budget-Tests unter der Grenze (siehe
Regressionsschutz). Zwei Faelle bleiben auch dort nah an der Grenze, siehe
„Offen“.

**Ueber der Grenze:**

| Werkzeug | Zeichen | Ursache |
| --- | --- | --- |
| `list_playbooks` | 277.151 | jeder Katalog-Eintrag traegt den vollen `content.body` |
| `get_persona` | 225.559 | `persona.content.content.blocks` + Playbook-Bodies |
| `list_versions` | 139.925 (Persona `Coder`, 11 Snapshots) | Historien-Laenge **mal** Body |
| `fetch_playbook` | 64.971 | `content.body` neben `body_rendered` |
| `fetch_agent` | 54.912 | Persona-Bloecke neben `system_prompt_rendered` |
| `diff_versions` | 52.116 | `before_text` + `after_text` tragen den Body **zweimal** |
| `list_system_prompts` | 50.766 (6 Templates x 8.000 Zeichen) | jeder Eintrag traegt `content.body` |
| `get_system_prompt` | 50.441 (Body am Modell-Maximum) | der Body **ist** der Zweck — strukturell |

Die `list_versions`-Zahl gilt fuer ein konkretes Element: die Antwort ist
Historien-Laenge **mal** Body. Bei einem vielfach versionierten Element reisst
sie, bei einem neuen nicht — die gefaehrlichste Sorte, weil sie mit dem Alter
des Workspace erst entsteht und kein Testdatensatz sie vorwegnimmt.

`list_system_prompts` reisst schon bei **einem einzigen** Template am
Modell-Maximum (50.473 Zeichen), weil `SystemPromptTemplateContent.body` auf
50.000 Zeichen validiert ist — das Antwortbudget ist damit strukturell
ueberschritten, bevor ein zweiter Eintrag dazukommt.

**Beobachtungsposten** (unter der Grenze, aber nah dran):

| Werkzeug | Zeichen | warum beobachtet |
| --- | --- | --- |
| `get_version` | 49.223 (Body 49.000) | ein Body am Modell-Maximum (50.000) reisst |
| `list_external_tools` | 41.430 | Listen-Fall, skaliert mit dem Workspace |

**Unter der Grenze (kein Handlungsbedarf):**

| Werkzeug | Zeichen |
| --- | --- |
| `fetch_resource` (groesste Resource, 92 Bloecke) | ~22.000 |
| `search` (`limit=50`) | 13.928 |
| `list_triggers` | 11.712 |
| `list_resources` | 786 |

`list_resources` ist das Vorbild: es liefert `ResourceSummary` mit nur
`block_count` statt der Bloecke — 786 Zeichen fuer denselben Zweck, den
`list_playbooks` mit 277.151 Zeichen erfuellt.

## Die Loesung: `format="text"` als Default (ADR-0056)

Die zwoelf lesenden Werkzeuge mit Editor-JSON haben einen Parameter `format`.
Die Entscheidung steht in
[`adr/0056-mcp-lesende-werkzeuge-text-default.md`](adr/0056-mcp-lesende-werkzeuge-text-default.md).

- **`"text"` (Default)**: ein Markdown-Dokument statt eines JSON-Objekts. Oben
  steht ein kurzer Kopf mit den Metadaten fuer Folgeaufrufe (`id`, Version,
  Status, Locale, je nach Werkzeug Tags, Trigger, Gliederung), darunter der
  Inhalt als Klartext. Kein Editor-JSON, kein Escaping. Platzhalter erscheinen
  als `{{kind:target_id}}`.
- **`"full"`**: die Antwort, wie sie die REST-API liefert, mit Editor-JSON.
  Das ist die Vorlage fuer die `update_*`-Werkzeuge (PUT, `content` ersetzt den
  Stand vollstaendig) und fuer strukturelle Verarbeitung.
- **`"outline"`**: nur bei `fetch_playbook`, Kopf und Gliederung ohne
  Prozedur.

Jede `text`-Antwort sagt selbst, dass `update_*` die Vorlage mit
`format="full"` braucht. Ein Schreiber, der die Lesefassung als Vorlage nimmt,
wuerde den Inhalt beim naechsten PUT leeren. Deshalb steht der Hinweis an drei
Stellen: in der Antwort, in den Beschreibungen der `update_*`-Werkzeuge und in
der Builder-Resource „Agent-Bau-Konventionen“ (ADR-0056, Abschnitt 5).

Ein unbekannter Wert wird mit einem `ToolError` abgelehnt, bevor die API
gefragt wird. Ein Tippfehler soll auffallen, statt still einen anderen
Zuschnitt zu liefern.

Was die Lesefassung je Werkzeug traegt:

| Werkzeug | Kopf | Inhalt |
| --- | --- | --- |
| `get_persona` | `id`, Version, Status, Locale, Tags, aktiver Modus | Beschreibung, gerendertes Profil, Traits, **Modi** (Trigger, Identitaet, Output-Stil, Anti-Patterns), Playbook-Katalog mit `id` und Trigger |
| `fetch_agent` | `id`, Persona, Template, Locale | gerenderter System-Prompt, Modi |
| `list_playbooks` | je Eintrag `id`, Version, Status, Typ, Tags, Trigger, Kinder | Beschreibung, kein Body |
| `fetch_playbook` | wie `list_playbooks` | Gliederung mit `block_id`, Prozedur, Verweise, eingebettete Resources und Sub-Playbooks als Klartext |
| `fetch_resource` | `id`, Slug, Version, Status, Locale, Tags | Beschreibung, Bloecke als Klartext, Sub-Resources |
| `get_system_prompt` | `id`, Slug, Version, Status, Locale | Body als Klartext |
| `list_system_prompts` | je Eintrag wie `get_system_prompt` | Beschreibung, kein Body |
| `get_external_tool` | `id`, Alias, Version, Status, Locale | Felder, Nutzungshinweise als Klartext |
| `list_external_tools` | je Eintrag wie `get_external_tool` | Felder, keine Nutzungshinweise |
| `list_versions` | je Version Nummer, Status, Locale, Zeitpunkt, Autor | kein Inhalt (den liefert `get_version`) |
| `get_version` | wie `list_versions` | Snapshot-Inhalt als Klartext |
| `diff_versions` | Version, Vergleichsstand, identisch ja/nein | Aenderungspfade, Klartext vorher/nachher; die Rohwerte `before`/`after` entfallen |

Die Darstellung liegt an einer Stelle, `apps/mcp/src/who2be_mcp/text_view.py`.
Der Klartext der Bloecke kommt aus derselben Serialisierung wie
`before_text`/`after_text` (`who2be_models.blocknote_text`). Die Daten in der
Datenbank und die REST-Antwort bleiben unberuehrt.

Bei `get_persona` gehoeren Profil **und** Playbook-Katalog zum Zuschnitt:
gemessen tragen die Playbook-Bodies mehr bei als das Persona-Profil selbst.
Unter `text` stehen je Playbook nur Name, `id` und Trigger; den Body liefert
`fetch_playbook`.

**Bruch gegenueber dem Stand vor ADR-0056:** Bis dahin war `full` der Default,
und `text` lieferte bei fuenf Werkzeugen ein JSON-Objekt mit geleertem Body.
Wer ohne `format` aufruft und JSON erwartet, setzt jetzt `format="full"`.

## Offen: was unter `text` nah an der Grenze bleibt

Unter `full` gelten die Messwerte aus dem Inventar unveraendert. Unter `text`
bleiben zwei Faelle, bei denen der Inhalt selbst gross werden kann.

**`get_system_prompt`** bleibt strukturell nah an der Grenze, weil der Body
der Zweck des Aufrufs ist. `SystemPromptTemplateContent.body` ist auf 50.000
Zeichen begrenzt. Ein BlockNote-Body schrumpft unter `text` deutlich, weil die
Editor-Struktur entfaellt. Ein Body, der als einfacher Text gespeichert ist
(Alt-Bestand), kommt dagegen unveraendert an und kann samt Kopf knapp ueber
der Grenze liegen.
*Weg darunter:* Paginierung des Bodys (Offset/Limit wie `read_file`) oder das
Modell-Maximum auf einen Wert senken, der samt Rahmen unter 50.000 bleibt.
Beides aendert einen bestehenden Vertrag und braucht eine Entscheidung.

**`diff_versions`** verliert unter `text` die Rohwerte, traegt den Klartext
aber weiter **zweimal**, vorher und nachher, jeweils vollstaendig. Bei einem
sehr langen Inhalt kann das allein die Grenze erreichen.
*Weg darunter:* die beiden Klartext-Abschnitte auf die geaenderten Abschnitte
beschraenken (die `changes`-Liste weiss bereits, welche das sind). Der
Diff-Konsument im Web nutzt `before_text`/`after_text` fuer die Zeilenansicht.
Das betrifft also einen Frontend-Vertrag und ist kein reiner Server-Zuschnitt.

`list_system_prompts`, frueher der dritte offene Fall, ist erledigt: die
Lesefassung traegt je Eintrag Kopf und Beschreibung, keinen Body. Ein eigenes
Summary-Modell ist dafuer nicht mehr noetig.

## Regressionsschutz

`apps/mcp/tests/test_tool_payload_budget.py` haelt beide Budgets: die
Kataloggroesse von `tools/list` (WP10, ADR-0047) und die Antwortgroesse je
Werkzeug.

**Katalog-Budget `tools/list`:** Grenze 160.000 Bytes. Gemessen wird die
`tools`-Liste so, wie der Server sie auf den Draht legt: ein In-Memory-Client
ruft `tools/list` durch den echten Handler samt Middleware auf, gezaehlt wird
utf-8 mit `ensure_ascii=False`, ohne den JSON-RPC-Umschlag. Damit zaehlen auch
die Felder mit, die nicht aus dem Werkzeug-Schema stammen: seit FastMCP 4
traegt jedes Tool `title` und `_meta`. Die fruehere Messung nur ueber `name`,
`description` und `inputSchema` sah diese Felder nicht.

| Stand | Tools | gemessen |
| --- | --- | --- |
| 2026-08-13, Einfuehrung (name/description/inputSchema) | 71 | 110.133 Bytes |
| 2026-10-06, alte Messung auf FastMCP 4.0.11 | 86 | 136.764 Bytes |
| 2026-10-06, Draht-Form auf FastMCP 4.0.11 | 86 | **142.295 Bytes** |

Bis zur Grenze bleiben damit 17.705 Bytes. Die Rot-Probe
`test_tools_list_payload_counts_wire_only_fields` blaeht `title` bzw. `_meta`
eines einzelnen Tools ueber das Budget auf und verlangt, dass die Messung das
sieht. Misst der Test wieder nur das Schema, faellt sie.

Die Antwort-Tests messen die Antwort so, wie sie ankommt: unter `text` den
Markdown-String, unter `full` das serialisierte Modell (`model_dump_json`).
Sie halten die Zusage „die Antwort kommt an“, nicht die Zusage „ein Feld heisst
so“. Jeder Test fuehrt seine **Rot-Probe mit**: er
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

Dass das nicht vergessen wird, haelt ein eigener Guard:
`test_every_format_aware_tool_has_a_budget_test` liest die registrierten
Tool-Schemata und die vorhandenen Testnamen und meldet jedes Werkzeug mit
Budget-`format`, zu dem kein Test existiert. Er faellt also, wenn ein neuer
`format`-Pfad **ohne** Rot-Probe dazukommt — oder wenn ein bestehender Nachweis
verschwindet. Die Antwort darauf ist ein Test, nicht ein Eintrag in einer
Ausnahmeliste.

Ein zweiter Guard, `test_system_prompt_body_cannot_be_emptied_for_a_cheap_
response`, haelt fest, warum `get_system_prompt` den Body als Klartext traegt
statt ihn zu leeren: `min_length=1` verbietet einen leeren Body, und
`max_length` liegt am Antwortbudget. Aendert sich eines der beiden Limits,
faellt er, und der Abschnitt „Offen“ ist nachzuziehen.

## Verwandt

- [`mcp-claude-code.md`](mcp-claude-code.md) — den Server anbinden
- [`adr/0056-mcp-lesende-werkzeuge-text-default.md`](adr/0056-mcp-lesende-werkzeuge-text-default.md)
  — warum `text` der Default ist und `full` die Vorlage fuer `update_*`
- `apps/mcp/tests/test_tool_payload_budget.py` — haelt zusaetzlich das
  **Katalog**-Budget von `tools/list` (WP10 in
  [`adr/0047-agent-workarea-knowledge-base.md`](adr/0047-agent-workarea-knowledge-base.md)):
  andere Grenze, gleiche Versagensart — dort fliegt nicht eine Antwort, sondern
  die ganze Werkzeug-Liste
