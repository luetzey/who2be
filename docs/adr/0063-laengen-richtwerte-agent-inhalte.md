# ADR-0063 — Längen-Richtwerte für Agent-Inhalte und weiche Warnung beim Schreiben

- Status: **Accepted** (Owner, 2026-10-22). Die Entscheidung steht im Wortlaut
  in Abschnitt 2.
- Datum: 2026-10-23
- Gemessen gegen: `origin/main` @ `b6aa3df0` (Builder schlank B1,
  `BUILDER_CONTENT_VERSION` 20). Code-Aussagen tragen einen Symbolanker
  (Konvention `docs/code-references.md`).
- Grundlage: Recherchebericht „Was baut der Builder, wie groß ist es, wie ginge
  es schlanker?“ (Karte t_21778371, Stand 2026-10-22, außerhalb des Repos),
  §5 und §6. Vorher-Messung: Karte t_43038535. Diese ADR entsteht auf Karte
  t_b64ccd64 (Builder schlank B4).
- Bezug: ADR-0058 (Markdown als Schreibstandard, Schreibantwort des
  Markdown-Wegs), ADR-0056 (Text-Default der Lesewerkzeuge, Antwortbudget),
  ADR-0059 (Werkzeug-Profile, Startlast).

## 1. Kontext

Was ein Agent immer lädt (Persona-Profil, Modi, Katalogzeilen), kostet in
jedem Turn und senkt mit wachsender Länge die Befolgung. Die Recherche fand
keine einzige Längen- oder Wohin-Regel im Builder. 8 von 13 realen Personas
lagen über 600 Wörtern Profil, 4 über 1 000. Vier Builder-Playbooks liegen
über 1 500 Wörtern.

Eine Regel im Playbook allein reicht nicht: Der Builder lädt sein Playbook
nicht bei jedem Schreiben. Ein deterministischer Hinweis in der
Schreibantwort erreicht ihn genau dann, wenn er schreibt.

## 2. Entscheidung (Owner-Wortlaut, 2026-10-22)

Owner per Telegram: „Alles wie empfohlen“. Für diese ADR relevant:

- **W1 (b):** Richtwerte und eine weiche Warnung beim Schreiben (API- und
  MCP-Antwort) sowie eine Anzeige im Web-Längenzähler. **Keine harte
  Grenze**, höchstens ein Missbrauchsschutz (etwa 20 000 Wörter).
- **W2, Werte:**

  | Element | Ziel | Warnung ab |
  | --- | ---: | ---: |
  | Persona-Profil | 400 Wörter | 600 Wörter |
  | je Modus (alle Textfelder zusammen) | 150 Wörter | 250 Wörter |
  | Zahl der Modi | 3 | 5 |
  | Playbook-Body | 1 000 Wörter | 1 500 Wörter |
  | Playbook-Beschreibung + Trigger | 300 Zeichen | 500 Zeichen |
  | Resource | keine Grenze | Abschnitt über 600 Wörter |
  | Inhalts-Startlast Fach-Agent | 5 KB | 8 KB |
  | Inhalts-Startlast Builder | 6 KB | 9 KB |

- **W4 (b):** Bestand wird nur gemeldet (Konsistenz-Check, Pflege-Fund),
  gekürzt nur auf Wunsch des Menschen.

## 3. Zählweise

Gezählt wird auf dem Markdown-Text in der Normalform nach ADR-0058, so wie
die Schreibantwort ihn zurückgibt:

- Wörter sind durch Leerraum getrennte Folgen mit mindestens einem Buchstaben
  oder einer Ziffer. Reine Markdown-Zeichen (`-`, `#`, `|`, `---`) zählen
  nicht.
- Codeblöcke (```` ``` ```` und `~~~`) zählen nicht. Ein nicht geschlossener
  Codeblock reicht bis zum Ende des Felds.
- Überschriften-Anker ` [#id]` zählen nicht. Pill-Tokens `{{kind:id}}` zählen
  als ein Wort.
- Beschreibung und Trigger zählen als Zeichen, beide Felder zusammen.
- Ein Resource-Abschnitt reicht von einer Überschrift (jeder Ebene) bis zur
  nächsten. Die Überschrift selbst zählt nicht mit. Unterabschnitte zählen
  getrennt, damit ein langer Abschnitt nicht zusätzlich über seine
  Eltern-Überschrift gemeldet wird.
- „Warnung ab“ heißt: ab dem Wert (`>=`). Beim Resource-Abschnitt heißt es
  „über 600“ (`>`).

Umgesetzt in
`packages/models/src/who2be_models/content_budgets.py#count_words` und
`#sections`.

## 4. Eine Quelle für die Zahlen

Die Werte stehen im Code genau einmal, in
`packages/models/src/who2be_models/content_budgets.py#BUDGETS` und den
Konstanten daneben. Die Agent-Bau-Konventionen des Builders (B1, Abschnitt
„Längen & Wohin“, Tabelle `res-conv-tab-laengen-budgets`, DE und EN) nennen
dieselben Zahlen für den Builder. Der Test
`packages/models/tests/test_content_budgets.py#test_conventions_table_matches_constants`
hält beide gleich. Das Web (B5) liest die Werte aus der API oder aus einer
daraus erzeugten Konstante, nicht aus einer zweiten Liste von Hand.

## 5. Wo die Warnung erscheint

**API.** Die Schreibantwort des Markdown-Wegs (`MarkdownWriteResult`, alle
`POST`/`PUT`/`PATCH …/markdown`) trägt das additive Feld `length_hints[]`,
sonst eine leere Liste. Ein Hinweis nennt `element` (`profile`, `mode`,
`mode_count`, `playbook_body`, `playbook_summary`, `resource_section`),
`ref` (Modusname oder Anker des Abschnitts), `value`, `unit`, `target`,
`warn` und eine kurze `message` in der Inhaltssprache des Elements, etwa:
„Profil 1 450 Wörter, Richtwert 400. Abläufe und Nachschlagewissen in
Playbook/Resource auslagern?“

Gemessen wird der **ganze Stand nach dem Schreiben**, auch bei einer
Teiländerung per `PATCH`. System-Prompt und externes Tool bekommen keine
Hinweise. Der JSON-Weg des Web-Editors bleibt unverändert; dort zeigt der
Längenzähler (B5) den Richtwert.

**MCP.** Die Schreibwerkzeuge (`create_/update_persona`,
`create_/update_playbook`, `create_/update_resource`, `edit_content` und die
übrigen Markdown-Schreiber) geben die Hinweise nicht strukturiert aus,
sondern als eine Zeile `length_note` (`null`, wenn alles im Richtwert liegt).
Grund ist das Antwortbudget: Die Zeile kostet weniger als die Hälfte des
strukturierten Felds.

**Nie blockierend.** Ein Hinweis ändert weder Status noch Speichern. Es gibt
keinen Fehlercode für Länge.

## 6. Missbrauchsschutz

Es gibt bereits eine Grenze: Jedes Markdown-Feld des Schreibwegs ist auf
200 000 Zeichen begrenzt
(`packages/models/src/who2be_models/content_markdown.py#_Markdown`), das sind
grob 25 000 bis 30 000 Wörter. Das entspricht dem Owner-Rahmen „etwa 20 000
Wörter“. Diese ADR führt deshalb keine neue Grenze ein.

## 7. Konsequenzen

- Agenten erfahren beim Schreiben, dass ein Inhalt zu lang ist, auch ohne
  geladenes Playbook. Ob sie darauf reagieren, misst die Nachher-Messung M1.
- Die Schreibantwort wird um `length_hints` länger, im Normalfall um eine
  leere Liste (API) bzw. `"length_note": null` (MCP).
- Ändern sich die Werte, ändern sich Konstanten und Konventionen im selben
  PR. Der Paritätstest verhindert, dass sie auseinanderlaufen.
- Englische Texte haben 10 bis 17 % mehr Wörter als deutsche (Vorher-Messung).
  Die Werte gelten vorerst für beide Sprachen gleich.
