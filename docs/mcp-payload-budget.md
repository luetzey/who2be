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
strukturell braucht (Diagnose, maschinelle Verarbeitung), bekommt sie
weiterhin mit `format="full"`. Ein `update_*`-Aufruf braucht sie nicht mehr:
seit ADR-0058 schreiben Agenten Markdown, die Vorlage dafuer liefert
`format="source"` (siehe unten).

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
- **`"source"`** (seit ADR-0058, nur die sechs Werkzeuge mit Schreibvorlage:
  `get_persona`, `fetch_playbook`, `fetch_resource`, `get_system_prompt`,
  `get_external_tool`, `get_version`): das Quell-Markdown mit
  Ueberschriften-Ankern `[#id]`, Platzhalter-Tokens und dem Konflikt-Token
  `base_rev` im Kopf. Das ist die Vorlage fuer `update_*` (PUT, `content`
  ersetzt den Stand vollstaendig) und `edit_content` (ein Abschnitt oder ein
  Feld). Strukturfelder stehen als JSON-Block, jedes Markdown-Feld in einem
  eigenen Fence unter seinem Feldnamen.
- **`"full"`**: die Antwort, wie sie die REST-API liefert, mit Editor-JSON.
  Seit ADR-0058 nur noch fuer strukturelle Verarbeitung und Diagnose; die
  Schreibwerkzeuge nehmen kein Editor-JSON mehr an.
- **`"outline"`**: nur bei `fetch_playbook`, Kopf und Gliederung ohne
  Prozedur.

Jede `text`-Antwort sagt selbst, dass `update_*` und `edit_content` die
Vorlage mit `format="source"` brauchen. Ein Schreiber, der die Lesefassung als Vorlage nimmt,
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

**Katalog-Budget `tools/list`:** Grenze 180.000 Bytes (bis 2026-10-14:
160.000; angehoben nach Owner-Entscheidung W-E1 b vom 2026-10-09, weil Phase E
zehn Werkzeuge ergaenzt). Gemessen wird die
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
| 2026-10-10, Draht-Form | 90 | **147.325 Bytes** |
| 2026-10-10, mit `alwaysLoad` an fünf Werkzeugen (T4) | 90 | **147.475 Bytes** |
| 2026-10-11, nach der Schema-Diaet (T2) | 90 | **138.060 Bytes** |
| 2026-10-11, nach der Beschreibungs-Diaet (T3) | 90 | **104.290 Bytes** |
| 2026-10-14, Gespraechs-Werkzeuge (E-MCP-1) | 94 | **109.963 Bytes** |
| 2026-10-14, Werkzeugluecken D7 (E-MCP-2) | 100 | **114.203 Bytes** |
| 2026-10-22, Markdown-Schreibweg (ADR-0058 P3) | 101 | **104.777 Bytes** |

Bis zur Grenze bleiben damit 75.223 Bytes. Die Rot-Probe
`test_tools_list_payload_counts_wire_only_fields` blaeht `title` bzw. `_meta`
eines einzelnen Tools ueber das Budget auf und verlangt, dass die Messung das
sieht. Misst der Test wieder nur das Schema, faellt sie.

### Katalog je Referenzprofil

Den vollen Katalog bekommt nur, wer alle Rechte hat. Ein Agent sieht beim
Start die Teilmenge, die der `PolicyFilterMiddleware` fuer seine Rechte
durchlaesst (ADR-0042). Diese Teilmenge ist die eigentliche Kennzahl „was
kostet ein Agent-Start“. Gemessen wird sie mit
`apps/mcp/src/who2be_mcp/payload_report.py`; der Bericht laesst sich jederzeit
neu erzeugen:

```bash
uv run python -m who2be_mcp.payload_report
```

Stand 2026-10-22, 101 Werkzeuge, Draht-Form wie oben, mit `alwaysLoad` (T4),
nach Schema-Diaet (T2), Beschreibungs-Diaet (T3) und Markdown-Schreibweg
(ADR-0058 P3):

| Profil | Werkzeuge | Bytes | davon sofort geladen | Start mit Tool Search |
| --- | ---: | ---: | ---: | ---: |
| Agent, Default-Policy | 38 | 29.834 | 4 / 3.870 | 6.190 |
| Agent, Default + Gedaechtnis `suggest` | 42 | 33.308 | 5 / 4.500 | 6.877 |
| Agent, Builder (alle Rechte, Lesen `all`) | 101 | 104.777 | 5 / 4.500 | 8.059 |
| Mensch/JWT, Rolle editor | 97 | 101.303 | 4 / 3.870 | 7.372 |
| alle Werkzeuge (Guard) | 101 | 104.777 | 5 / 4.500 | 8.059 |

Zum Vergleich der Stand 2026-10-11 (90 Werkzeuge, nach T3): Default-Policy
38 / 29.497, Builder 90 / 104.290, Rolle editor 86 / 100.816 Bytes. Zwischen
beiden Staenden kamen elf Werkzeuge dazu (E-MCP-1, E-MCP-2, `edit_content`);
die Ersparnis des Markdown-Schreibwegs gleicht sie beim Builder fast aus.

„Bytes“ ist die Draht-Größe von `tools/list`. „davon sofort geladen“ zählt
die sichtbaren Werkzeuge mit `alwaysLoad` und deren Bytes. „Start mit Tool
Search“ ist eine Näherung an das, was Claude Code beim Start in den Kontext
lädt: `instructions`, die Namen der übrigen Werkzeuge und die vollen
Definitionen der sofort geladenen (siehe „Start bei Tool Search“ unten).

Die Profile sind keine Nachbildung: `test_reference_profiles_measure_the_
middleware_view` schickt fuer jedes Profil ein passendes `whoami` durch die
echte Middleware und verlangt dieselbe Byte-Zahl wie der Bericht.

**Zielwerte je Agent-Start (seit T3, harter Test):** Draht-Bytes der
sichtbaren Werkzeuge plus Server-`instructions` (1.732 Bytes), die jeder
Client beim Verbinden bekommt.

| Profil | Ziel | Stand 2026-10-11 (90 Werkzeuge) | Stand 2026-10-14 (94 Werkzeuge) | Stand 2026-10-14 (100 Werkzeuge, E-MCP-2) | Stand 2026-10-22 (101 Werkzeuge, ADR-0058 P3) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Agent, Default-Policy | 35.000 | 31.101 | 31.101 | 31.101 | 31.566 |
| Agent, Builder | 120.000 | 105.894 | 111.567 | 115.807 | 106.509 |

ADR-0058 P3 (Markdown-Schreibweg) senkt den Builder-Start um 9.298 Bytes:
die zehn Schreibwerkzeuge verlieren die BlockNote-Schemata, `edit_content`
kommt mit 1.421 Bytes dazu (Aufschluesselung im Abschnitt
„Markdown-Schreibweg (W1)“ unten). Der Default-Start waechst um 465 Bytes,
nur durch die laengeren `instructions` (+128) und die `source`-Hinweise der
Lesewerkzeuge.

Das Builder-Ziel lag bis 2026-10-14 bei 110.000 Bytes. Der Owner hat es am
2026-10-14 auf 120.000 angehoben („1a“), weil die Gespraechs-Werkzeuge aus
Phase E (E-MCP-1) den Builder-Start auf 111.567 Bytes bringen. Das Default-Ziel
bleibt 35.000.

`test_agent_start_meets_target_per_profile` haelt beide Ziele; das
Katalog-Budget oben bleibt die Obergrenze daneben. Reisst ein Ziel:
Beschreibungen kuerzen. Ein Ziel hebt nur der Owner an.

Die zehn teuersten Werkzeuge (Stand 2026-10-22, 101 Werkzeuge, Bytes):

| # | Werkzeug | gesamt | Beschreibung | Schema |
| ---: | --- | ---: | ---: | ---: |
| 1 | `update_agent` | 5.935 | 112 | 5.700 |
| 2 | `create_agent` | 5.828 | 177 | 5.527 |
| 3 | `submit_session_protocol` | 3.814 | 398 | 3.268 |
| 4 | `update_persona` | 2.819 | 290 | 2.398 |
| 5 | `create_persona` | 2.731 | 415 | 2.186 |
| 6 | `submit_test_results` | 1.869 | 399 | 1.329 |
| 7 | `update_playbook` | 1.750 | 339 | 1.278 |
| 8 | `set_resource_sub_resources` | 1.728 | 204 | 1.372 |
| 9 | `update_external_tool` | 1.716 | 289 | 1.284 |
| 10 | `create_external_tool` | 1.684 | 319 | 1.224 |

Bei den drei teuersten liegt das Gewicht im Schema, nicht in der
Beschreibung: das `inputSchema` traegt das ganze Policy- bzw.
Protokoll-Modell samt seiner Docstrings. Die Agent-Werkzeuge tragen kein
BlockNote; ihr Gewicht ist die `AgentToolPolicy` und damit Sache der
Werkzeug-Profile (W2, ADR-0059), nicht des Markdown-Schreibwegs.

### Text-Guards

Drei Guards halten den Text fest, den ein Client wirklich sieht:

- **Beschreibung hoechstens 2.048 Zeichen**
  (`test_tool_descriptions_stay_under_client_cap`). Claude Code schneidet
  Werkzeugbeschreibungen dort ab; was dahinter steht, kommt beim Agenten nicht
  an. Gilt fuer alle Werkzeuge, auch den Bestand in `server.py`.
- **Erster Satz hoechstens 100 Zeichen**
  (`test_tool_first_sentences_fit_short_catalogs`). Kurzkataloge (Hermes
  `tool_search`, Claude Code Tool Search) zeigen ohne Suche nur Namen und
  ersten Satz. Der Satz soll den Zweck tragen; Bedingungen und Details
  gehoeren dahinter. Ein Satz endet an `.`, `!` oder `?` vor Leerraum oder an
  einem Absatzwechsel.
- **Keine Entwickler-Historie im Draht-Schema**
  (`test_wire_schema_developer_refs_only_shrink`). Verweise auf ADR, Phase,
  Track, Welle, WP oder Gap in den `description`-Texten des `inputSchema`
  stammen aus Pydantic-Docstrings in `packages/models` und kosten jeden
  Agenten Bytes, ohne einen Aufruf zu erklaeren. Die Ratsche
  `_DEVELOPER_REF_BASELINE` im Test ist seit der Schema-Diaet (T2) leer:
  jeder neue Verweis laesst den Test fallen. Historie gehoert in einen
  `#`-Kommentar ueber der Klasse oder in die ADR, nicht in den Docstring eines
  Modells, das als Schema ausgeliefert wird.

**Wenn ein Text-Guard reisst:** den Text kuerzen bzw. den Satz umstellen,
nicht die Grenze anheben.

### Schema-Diaet (T2)

Pydantic schreibt den Klassen-Docstring jedes Modells als `description` in
das JSON-Schema. Ueber `inputSchema` landet er bei jedem Agenten, der das
Werkzeug sieht, ueber `docs/reference/openapi.json` auch in der API-Referenz.
Regel fuer Modelle, die als Werkzeug-Eingabe dienen:

- Der **Docstring** erklaert dem Aufrufer, was das Feld bedeutet und was er
  senden darf. Kurz, ohne Projektgeschichte.
- Der **`#`-Kommentar ueber der Klasse** traegt das Warum fuer Entwickler:
  ADR, Phase, Migration, Backward-Compat.
- Ein Modell, das in vielen Schemas steckt (`ReadScope` achtmal,
  `ResourceBlock` zehnmal), bekommt einen Satz.

**Wirkung (gemessen mit `payload_report`, Stand 2026-10-11):**

| Größe | vorher | nachher |
| --- | ---: | ---: |
| Draht `tools/list`, alle Werkzeuge | 147.475 | 138.060 (−9.415) |
| Agent, Default-Policy | 46.436 | 45.938 (−498) |
| Agent, Default + Gedaechtnis `suggest` | 51.925 | 51.410 (−515) |
| Mensch/JWT, Rolle editor | 141.986 | 132.588 (−9.398) |
| Schema-Texte im Katalog | 29.615 | 20.416 (−9.199) |
| Schema-Texte mit Entwickler-Historie | 35 | 0 |

Beim Default-Agenten ist die Ersparnis klein, weil er keine Schreibwerkzeuge
sieht; die Historie sass fast ganz in den Schemas von `create_*`/`update_*`.
Fuer den Default-Agenten wirkt erst die Beschreibungs-Diaet (T3).

### Beschreibungs-Diaet (T3)

Die Werkzeugbeschreibung ist der Docstring der Funktion. Regeln:

- **Erster Satz:** Zweck und Suchwoerter. Kurzkataloge zeigen nur ihn.
- **Keine Wiederholung von Querschnittsregeln.** `format="source"` als
  PUT-Vorlage, der Status-Ablauf und die Sprachregel stehen einmal in den
  Server-`instructions`. Im Werkzeug bleibt hoechstens ein Kurzverweis; die
  PUT-Werkzeuge behalten den Pflichtsatz aus ADR-0056.
- **Kein Backward-Compat-Text.** Ein ignorierter Parameter bekommt einen
  Halbsatz („`locale` wird ignoriert“), keine Geschichte.
- **Lese-Umfang `assigned`** wird einmal erklaert, in `whoami`: Playbooks
  der Persona und die Resources, die diese Playbooks erreichen; bei
  `agent_read` nur der eigene Agent.
- **Hoechstens 1.100 Zeichen** je Werkzeug, fuer alle
  (`test_every_tool_description_stays_under_doc_cap`).

**Wirkung (gemessen mit `payload_report`, Stand 2026-10-11):**

| Größe | vorher | nachher |
| --- | ---: | ---: |
| Draht `tools/list`, alle Werkzeuge | 138.060 | 104.290 (−33.770) |
| Agent, Default-Policy | 45.938 | 29.497 (−16.441) |
| Agent, Default + Gedaechtnis `suggest` | 51.410 | 32.971 (−18.439) |
| Mensch/JWT, Rolle editor | 132.588 | 100.816 (−31.772) |
| Beschreibungen, alle Werkzeuge | 57.695 | 24.673 (−33.022) |
| Beschreibungen, Default-Agent | 26.799 | 10.705 (−16.094) |

Die Schemas bleiben unveraendert (67.381 Bytes); bei den vier teuersten
Schreibwerkzeugen liegt das Gewicht weiter dort (Weiche W1, Markdown-Eingabe;
umgesetzt mit ADR-0058, siehe naechster Abschnitt).

### Markdown-Schreibweg (W1, ADR-0058)

Seit ADR-0058 P3 nehmen die zehn `create_*`/`update_*`-Werkzeuge fuer
Persona, Playbook, Resource, System-Prompt und externes Tool nur noch
Markdown-Strings, auch `usage_notes` des externen Tools (W58-4). Ein
BlockNote-Block-Array scheitert an der Schema-Validierung; serialisiertes
Editor-JSON in einem Markdown-String weist das Werkzeug mit Feldnamen ab,
bevor die API gefragt wird (harter Schnitt, W58-3 = A). Teiländerungen laufen
ueber das neue Werkzeug `edit_content`: ein Abschnitt per
Ueberschriften-Anker `[#id]` oder ein ganzes Feld, mit dem Konflikt-Token
`base_rev` aus dem `source`-Kopf. Pflicht-Anker stehen nur an Ueberschriften,
die uebrigen Bloecke ordnet der Server je Abschnitt zu (W58-1 = D).

**Wirkung im Katalog (gemessen mit `payload_report`, vor und nach #1045):**

| Werkzeug | vorher | nachher |
| --- | ---: | ---: |
| `create_/update_persona` | 5.766 / 5.317 | 2.731 / 2.819 |
| `create_/update_playbook` | 2.456 / 2.048 | 1.681 / 1.750 |
| `create_/update_resource` | 2.243 / 1.868 | 1.350 / 1.433 |
| `create_/update_external_tool` | 2.862 / 2.655 | 1.684 / 1.716 |
| `create_/update_system_prompt` | 2.037 / 1.699 | 1.255 / 1.335 |
| zehn Schreibwerkzeuge zusammen | 28.951 | 17.754 (−11.197) |
| `create_/update_agent` (unveraendert) | 5.828 / 5.935 | 5.828 / 5.935 |
| `edit_content` (neu) | — | 1.421 |
| **Draht `tools/list`, alle Werkzeuge** | **100 / 114.203** | **101 / 104.777 (−9.426)** |
| Agent, Builder (Start-Ziel) | 115.807 | 106.509 (−9.298) |
| Agent, Default-Policy (Start-Ziel) | 31.101 | 31.566 (+465) |

ADR-0058 §8.1 hatte netto −1,6 bis −2,7 KB geschaetzt. Gemessen sind es
−9,4 KB. Die Schaetzung rechnete nur die Block-Listen-Schemas (3.564 Bytes)
und die JSON-Beispiele als BlockNote-Anteil. Gemessen faellt der Gewinn fast
ganz im `inputSchema` an: die Schemas der zehn Schreibwerkzeuge schrumpfen
von 23.768 auf 12.943 Bytes (−10.825), ihre Beschreibungen nur von 3.684 auf
3.450 Bytes (−234). Die Markdown-Eingabemodelle tragen je Inhalt ein
String-Feld statt der verschachtelten Inhaltsmodelle samt deren
Feldbeschreibungen.

**Wirkung je Aufruf:** Der groessere Effekt bleibt der je Schreib- und
Vorlagenaufruf. M5
(`packages/models/tests/test_blocknote_markdown_golden.py#M5_MIN_RATIO`)
misst ueber alle verwalteten Inhaltsdateien das Verhaeltnis von
Editor-JSON-Argument zu Markdown-Argument: kleinster Wert 1,71, Mittel 2,3.
Ein Vollstand kostet damit im Mittel gut 40 % der frueheren Argumentgroesse;
eine Teiländerung mit `edit_content` schickt nur den betroffenen Abschnitt.
Lesend gilt dasselbe Verhaeltnis fuer die Vorlage (`source` statt `full`).

### Start bei Tool Search: `instructions` und `alwaysLoad`

Claude Code (Tool Search, Default) und Hermes (`tool_search`) laden beim
Start nicht die vollen Werkzeugdefinitionen, sondern Namen bzw. einen
Kurzkatalog und die Server-`instructions`. Die vollen Definitionen holt der
Agent erst per Suche. Zwei Hebel steuern, was dabei sofort da ist. Beide
stehen in `apps/mcp/src/who2be_mcp/instructions.py`.

- **Server-`instructions`** (1.732 Bytes): Boot-Reihenfolge `whoami` →
  `get_persona` → `search_memory` → `list_triggers`/`fetch_playbook`, wann
  `search` und wann `search_content`, dazu die Regeln, die für viele Werkzeuge
  gelten: `format="source"` als Vorlage für `update_*` und `edit_content`, die
  Versions-Übergänge, die Sprache neuer Elemente, Gedächtnis-Treffer als
  Daten und `record_usage` nach jedem Einsatz. Die `instructions` gehen nicht
  über `tools/list` und zählen deshalb nicht zum Katalog-Budget.
- **`_meta["anthropic/alwaysLoad"]`** an fünf Werkzeugen: `whoami`,
  `get_persona`, `search`, `search_memory`, `record_usage`. Claude Code lädt
  deren volle Definition sofort. Andere Clients ignorieren den Schlüssel. Der
  Policy-Filter bleibt maßgeblich: wer `search_memory` nicht sehen darf,
  bekommt es auch mit `alwaysLoad` nicht.

**Wirkung (gemessen mit `payload_report`, Stand 2026-10-10):**

| Größe | vorher | nachher |
| --- | ---: | ---: |
| Draht `tools/list`, alle Werkzeuge | 147.325 | 147.475 (+150, je Werkzeug 30 Bytes `_meta`) |
| Draht `tools/list`, Default-Agent | 46.316 | 46.436 (+120) |
| Server-`instructions` | 0 | 1.604 |
| Start mit Tool Search, Default-Agent | 639 (nur Namen) | 9.103 |
| Start mit Tool Search, Builder | 1.694 (nur Namen) | 11.483 |

Der Start mit Tool Search wird damit größer, nicht kleiner. Das ist gewollt:
die fünf Werkzeuge braucht jeder Start ohnehin, vorher kamen sie erst über eine
oder mehrere Suchen in den Kontext, mit denselben Bytes plus Suchanfrage und
Suchergebnis. Gespart wird der Suchschritt, gewonnen wird ein Boot-Text, der
vorher fehlte. Beim Draht-Budget, an dem Claude Chat die Liste verwirft, ändert
sich praktisch nichts (+150 Bytes). Senken lässt es sich nur über kürzere
Beschreibungen und Schemas (T2, T3; Ergebnis siehe oben).

**Reihenfolge:** Die MCP-Spec verlangt eine deterministische Reihenfolge von
`tools/list` (Client-Cache, Prompt-Cache). Sie folgt der Registrierung im Code.
Zwei Tests halten das fest: `test_tools_list_order_is_deterministic_across_
processes` vergleicht zwei Prozesse mit verschiedenem `PYTHONHASHSEED`, und
`test_policy_filter_keeps_the_catalog_order` verlangt, dass der Filter nur
herausnimmt und nicht umordnet.

**Guards:** `test_server_instructions_reach_the_client_and_name_only_real_tools`
prüft, dass die `instructions` beim Client ankommen, höchstens 2.048 Zeichen
lang sind, keine Entwickler-Historie tragen und nur existierende
Werkzeugnamen in Backticks nennen. Wer ein Werkzeug umbenennt, muss den
Boot-Text mitziehen. `test_always_load_marks_exactly_the_boot_tools` hält die
Menge bei drei bis fünf Werkzeugen, die alle im Boot-Text stehen.

### Antwortgroesse je Werkzeug

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
  — warum `text` der Default ist
- [`adr/0058-markdown-schreibstandard-agenten.md`](adr/0058-markdown-schreibstandard-agenten.md)
  — Markdown als Schreibstandard, `format="source"` als Vorlage fuer
  `update_*` und `edit_content`
- `apps/mcp/tests/test_tool_payload_budget.py` — haelt zusaetzlich das
  **Katalog**-Budget von `tools/list` (WP10 in
  [`adr/0047-agent-workarea-knowledge-base.md`](adr/0047-agent-workarea-knowledge-base.md)):
  andere Grenze, gleiche Versagensart — dort fliegt nicht eine Antwort, sondern
  die ganze Werkzeug-Liste
