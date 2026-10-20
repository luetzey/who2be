# ADR-0058 — Markdown ist der Schreibstandard für Agenten, auch bei Teiländerungen

- Status: **Accepted** (Owner, 2026-10-20). Die Richtung hat der Owner am
  2026-10-16 entschieden, die vier Weichen W58-1 bis W58-4 am 2026-10-20. Beide
  Entscheidungen stehen im Wortlaut in Abschnitt 2, die Übersicht in
  Abschnitt 10.
- Datum: 2026-10-20
- Gemessen gegen: `origin/main` @ `0ddb704a` (100 Werkzeuge, `tools/list`
  114.203 Bytes). Code-Aussagen tragen einen Symbolanker (Konvention
  `docs/code-references.md`).
- Grundlage: Kanban-Karte t_5aa518a0 (Token-Optimierung W1). Dazu die
  Entscheidungsvorlage „MCP-Werkzeuge token-sparender ausliefern“ (Stand
  2026-10-09, außerhalb des Repos, §3 Option A+, §4 Paket T5, §6 Weiche W1).
- Bezug: ADR-0056 (Lesen: Text als Default, §5 Schreibpfad), ADR-0030
  (MCP-Write-Tools, PUT-Semantik), ADR-0047 (WorkArea: Markdown-Eingabe,
  Block-Anker, Patch-Operationen; dazu das tools/list-Budget), ADR-0021
  (Block-Anker, nur Überschriften), ADR-0053 (Fälle, Maßnahmen), ADR-0005
  (MCP als HTTP-Client ohne DB).
- Umfang: **nur Dokumentation.** Diese ADR ändert keinen Code. Umsetzung in
  den Paketen P1 bis P4 (Abschnitt 9).

## Inhalt

1. Kontext und Befund
2. Entscheidung (Owner-Wortlaut)
3. Markdown-Dialekt und Umfang (Frage 1)
4. Stabile Block-IDs bei Teiländerungen (Frage 3, Weiche W58-1)
5. Rundlauf-Garantie und Tests (Frage 2, mit Weiche W58-2)
6. Form der Teiländerung (Frage 4)
7. Übergang: Editor-JSON als Eingabe (Frage 5, Weiche W58-3)
8. Wirkung auf das Budget (Frage 6)
9. Paketschnitt (Frage 7)
10. Weichen (entschieden)
11. Konsequenzen

## 1. Kontext und Befund

### 1.1 Was heute geschrieben wird

Inhalte liegen als BlockNote-Editor-Dokument in der Datenbank. Die
MCP-Schreibwerkzeuge nehmen dieses Dokument roh entgegen, in zwei Formen:

| Feld | Form im Eingabe-Schema | Modell |
| --- | --- | --- |
| Persona-Profil `content.content.blocks` | Block-Liste | `packages/models/src/who2be_models/persona.py#PersonaVersionContent` |
| Modus-Felder `identity_add`, `output_style_override`, `anti_patterns` | je eine Block-Liste | `packages/models/src/who2be_models/persona.py#PersonaMode` |
| Resource `content.blocks` | Block-Liste | `packages/models/src/who2be_models/resource.py#ResourceContent` |
| Playbook `content.body` | BlockNote-JSON **als String** | `packages/models/src/who2be_models/playbook.py#PlaybookContent` |
| System-Prompt `content.body` | BlockNote-JSON als String | `packages/models/src/who2be_models/system_prompt_template.py#SystemPromptTemplateContent` |
| Externes Tool `content.usage_notes` | BlockNote-JSON als String | `packages/models/src/who2be_models/external_tool.py#ExternalToolContent` |

Ein Block ist im Schema offen (`extra="allow"`, Pflicht sind nur `id` und
`type`, `packages/models/src/who2be_models/resource.py#ResourceBlock`). Was ein
gültiger Block ist, steht deshalb nicht im Schema, sondern in Beispielen in
den Werkzeugbeschreibungen (`apps/mcp/src/who2be_mcp/server.py#create_playbook`,
`apps/mcp/src/who2be_mcp/server.py#create_system_prompt`). Alle
`update_*`-Werkzeuge haben PUT-Semantik: `content` ersetzt den Stand
vollständig (ADR-0030, `packages/models/src/who2be_models/persona.py#PersonaUpdate`).
Eine Teiländerung gibt es heute nicht. Wer einen Satz ändern will, liest den
Vollstand mit `format="full"` und schreibt ihn ganz zurück (ADR-0056 §5).

### 1.2 Die Lesefassung aus ADR-0056 ist keine Schreibvorlage

ADR-0056 liefert lesend Markdown, aber eine **Lesefassung**, keine Quelle:

- Persona und Playbook zeigen den Server-Render (`body_rendered`). Platzhalter
  sind dort **aufgelöst**, ein Playbook-Platzhalter steht also als Inhalt des
  Ziel-Playbooks im Text
  (`apps/mcp/src/who2be_mcp/text_view.py#persona_content_text`).
- Resource, System-Prompt und externes Tool laufen über die
  Klartext-Serialisierung. Sie setzt Platzhalter als `{{kind:target_id}}`,
  verliert aber Blocktyp, Überschriftenebene, Listenmarker, Code-Fences und
  Inline-Stile (`packages/models/src/who2be_models/blocknote_text.py#block_plain_text`).
- Block-IDs erscheinen nur in der Gliederung von `fetch_playbook`, nicht im
  Inhalt (`apps/mcp/src/who2be_mcp/text_view.py#playbook_text`).

Wer diese Fassung unverändert zurückschreibt, bekommt ein anderes Dokument:
Überschriften werden Absätze, aufgelöste Platzhalter werden Fließtext, alle
IDs sind neu. Die Rundlauf-Forderung der Karte (Frage 2) braucht also eine
**zweite Lesefassung**, die Quelle ist. Das ist Weiche W58-2 (Abschnitt 5.1).

### 1.3 Wer heute auf Block-IDs zeigt

Die Karte nennt Fälle, Änderungen, Resource-Links und Modi. Im Code zeigt sich
ein engeres Bild:

| Verweis | Ziel | Beleg |
| --- | --- | --- |
| Playbook → Resource-Abschnitt | `block_id` einer **Überschrift**, Nicht-Überschriften werden mit 422 `heading_anchor_required` abgelehnt | `apps/api/src/who2be_api/services/playbook_resource_link_service.py#PlaybookResourceLinkService._validate_heading_anchors` |
| Resource → Sub-Resource-Abschnitt | dito (Heading-Anker) | `packages/models/src/who2be_models/resource.py#SubResourceLinkItem` |
| Platzhalter-Pill `resource` mit `#<block_id>` | dito, wird beim Speichern zum Resource-Link | `apps/api/src/who2be_api/services/playbook_body_pills.py#extract_pills` |
| Passagen der Suche (`content_chunk`) | `block_id` der Überschrift, mit der die Passage beginnt | `apps/api/src/who2be_api/services/content_chunks.py#chunk_content` |
| Selektiver Abruf `fetch_playbook(block_ids)`, `fetch_resource(block_ids)`, `list_resource_blocks` | Heading-Anker | `apps/mcp/src/who2be_mcp/server.py#fetch_playbook`, `apps/mcp/src/who2be_mcp/server.py#list_resource_blocks` |
| Versions-Diff | **jede** Block-`id`, auch Absätze; gleiche ID = „geändert“ statt „entfernt + hinzugefügt“ | `apps/api/src/who2be_api/services/version_diff.py#_diff_block_list` |
| Fall-Zuordnung, Maßnahme | nur `entity_id` (und bei Maßnahmen-Events `version_id`), **kein** Block | `packages/models/src/who2be_models/case.py#CaseElementInput`, `packages/models/src/who2be_models/session.py#MeasureCreate` |
| Modus | über den **Namen** (case-insensitiv eindeutig), ein Modus hat keine ID | `packages/models/src/who2be_models/persona.py#PersonaVersionContent` |

Folgerung: Jeder gespeicherte Verweis auf eine Stelle im Inhalt zeigt auf eine
**Überschrift**. Nicht-Überschriften-IDs braucht nur der Versions-Diff, und
dort entscheiden sie über die Lesbarkeit, nicht über die Gültigkeit eines
Verweises. Fälle und Maßnahmen verweisen heute auf Elemente und Versionen,
nicht auf Blöcke. Die Anker-Regel in Abschnitt 4 schützt sie trotzdem mit:
Sobald ein Fall oder eine Maßnahme eine Stelle benennen soll, gibt es dafür
genau eine Ankersprache.

### 1.4 Es gibt schon einen Markdown-Schreibweg

Die WorkArea nimmt Markdown an, der Server zerlegt es deterministisch in
Blöcke mit stabilen IDs (`apps/api/src/who2be_api/services/wa_blocks.py#split_markdown`).
Lesend hängt er an jeden Block den Anker ` [#<block_id>]`
(`apps/api/src/who2be_api/services/wa_blocks.py#render_markdown`). Teiländerungen
laufen über `replace`/`insert_after`/`delete` an einem Anker mit
`expected_rev`, und bei `replace` erbt der erste neue Block die Anker-ID
(`apps/api/src/who2be_api/services/wa_blocks.py#apply_patch`,
`packages/models/src/who2be_models/workarea.py#ArtifactPatch`). Diese ADR
übernimmt Ankerform und Operationen, statt eine zweite Schreibweise zu
erfinden.

### 1.5 Bestand: was in den Inhalten wirklich vorkommt

Gezählt über die 34 verwalteten Inhaltsdateien (17 DE, 17 EN) in
`apps/api/src/who2be_api/repositories/`: Builder-Persona mit Modi,
Builder-Playbooks, Builder-Resource und Starter-Templates, zusammen 1.366
Blöcke.

| Merkmal | Vorkommen |
| --- | --- |
| Blocktypen | `bulletListItem` 620, `heading` 320, `paragraph` 302, `numberedListItem` 116, `codeBlock` 8 |
| Überschriftenebenen | 2 (250×), 3 (70×) |
| `codeBlock.language` | `json`, `markdown` |
| verschachtelte Blöcke (`children`) | 10 |
| Inline-Elemente | `text` 1.896, `placeholder` 76 |
| Inline-Stile | `bold` 298, `code` 116 |
| andere Props (Farbe, Ausrichtung) | nur Default-Werte |

Der verwaltete Bestand ist damit vollständig in Markdown abbildbar. Den
Live-Bestand der Workspaces kann diese ADR nicht zählen. Abschnitt 3.3 regelt
deshalb, was mit nicht abbildbaren Blöcken passiert, statt das auszuschließen.

## 2. Entscheidung (Owner-Wortlaut)

Owner, 2026-10-16, wörtlich zur Vorlage (Weichen W1, W2):

> „W1a, W2b“

W1a heißt: Die Schreibwerkzeuge nehmen Markdown an, der Server wandelt es in
BlockNote um. Owner am selben Tag zur Folgefrage M1 (gilt Markdown auch für
Teiländerungen?):

> „M1b lass uns bei einem Standard bleiben und diese pflegen und verbessern“

Daraus folgt die Richtung dieser ADR:

1. **Markdown ist der eine Standard**, über den Agenten Inhalte schreiben:
   Persona, System-Prompt, Playbook, Resource und, mit W58-4, die
   `usage_notes` des externen Tools. Das gilt auch für Teiländerungen.
2. Lesend liefert ADR-0056 schon Markdown. Schreibend kommt dasselbe Format
   dazu.
3. **BlockNote bleibt das Speicherformat** in der Datenbank und im
   Web-Editor. Die REST-API des Web-Editors ändert sich nicht. Es gibt keine
   Datenmigration.
4. „Ein Standard“ heißt: Editor-JSON als Agenten-Eingabe hat einen
   Auslaufplan, keinen Dauerzustand (Abschnitt 7).

Owner, 2026-10-20, wörtlich zu den vier Weichen dieser ADR (Abschnitt 10):

> „1D, 2B, 3A, 4 ja“

Das heißt:

- **W58-1 = D** (4.1): Pflicht-Anker ` [#id]` nur an Überschriften, die
  übrigen Blöcke ordnet der Server je Abschnitt zu (4.3).
- **W58-2 = B** (5.1): neuer Lesewert `format="source"`. `text` bleibt die
  Lesefassung, `full` bleibt bitgleich.
- **W58-3 = A** (7): harter Schnitt mit P3, vor dem Cloud-Release. Die
  Builder-Inhalte ziehen im selben Release mit. Ein Paket P5 gibt es nicht.
- **W58-4 = ja** (6.2): `usage_notes` des externen Tools wird ebenfalls
  Markdown.

Die nicht gewählten Optionen sind in den Abschnitten 4.1, 5.1 und 7 als
verworfen markiert. Abschnitte 3, 6, 8 und 9 hängen an keiner Owner-Weiche
und gelten mit der Annahme dieser ADR.

W2 (Werkzeug-Profile) ist nicht Teil dieser ADR.

## 3. Markdown-Dialekt und Umfang (Frage 1)

### 3.1 Optionen

- **A — CommonMark plus die GFM-Erweiterungen, die BlockNote abbildet.**
  Durchgestrichen und Aufgabenlisten aus GFM, Platzhalter als
  `{{kind:target_id}}`, Anker als ` [#id]`. Vorteil: Das kennt jedes Modell,
  und die Abbildung auf BlockNote ist eindeutig. Nachteil: GFM-Tabellen bleiben
  draußen (Abschnitt 3.3).
- **B — der WorkArea-Split unverändert.** Der Server zerlegt nur in
  Überschrift, Absatz, Liste und Code, der Rest bleibt Markdown im Block
  (`apps/api/src/who2be_api/services/wa_blocks.py#split_markdown`). Vorteil:
  Es gibt ihn schon. Nachteil: WorkArea-Blöcke tragen Markdown als Text, nicht
  BlockNote-Struktur. Eine Liste wäre ein einziger Absatz, Fett stünde als
  `**` im Text, und der Web-Editor zeigte Rohmarkdown.
- **C — voller GFM-Umfang mit HTML-Durchreichung.** Vorteil: Nichts wird
  abgelehnt. Nachteil: HTML hat in BlockNote kein Gegenstück, und das wäre
  genau der stille Verlust, den die Karte ausschließt.

**Entscheidung A** (mit Annahme dieser ADR). Nur A liefert echte
BlockNote-Struktur, und der Bestand
(1.5) braucht nichts darüber hinaus. Von B übernimmt A die Ankerform und die
Patch-Operationen, nicht den Split.

### 3.2 Abbildung (verlustfrei, in beide Richtungen)

| BlockNote | Markdown |
| --- | --- |
| `heading`, `props.level` 1–3 | `#` bis `###`, Anker am Zeilenende ` [#id]` (Abschnitt 4) |
| `paragraph` | Absatz, Leerzeile als Trenner |
| `bulletListItem` | `- ` |
| `numberedListItem` | `1. ` (die Nummer schreibt der Server neu, Zähler sind nicht Teil des Dokuments) |
| `checkListItem`, `props.checked` | `- [ ] ` / `- [x] ` |
| `codeBlock`, `props.language` | Fence mit Sprache, ```` ```json ```` |
| `children` | Einrückung um zwei Leerzeichen unter dem Elternblock |
| Inline `bold` / `italic` / `strike` / `code` | `**…**` / `*…*` / `~~…~~` / `` `…` `` |
| Inline-Link | `[Text](url)` |
| Inline `placeholder` | `{{kind:target_id}}`, bei Resource-Abschnitten `{{resource:<uuid>#<block_id>}}` |
| Zeilenumbruch im Block | harter Umbruch (`\` am Zeilenende) |

Die Überschriftenebene 1–3 ist der heutige Schnitt der Bestandsmigration
(`apps/api/src/who2be_api/migrations/0033_blocknote_only.sql@d6abcde3`, sie
klemmt auf `LEAST(3, …)`). Tiefere Ebenen sind ein Fehler (3.3).

**Platzhalter-Label.** Eine Pill trägt neben `kind` und `target_id` ein
sichtbares `label` (`packages/models/src/who2be_models/placeholder.py#PlaceholderInlineProps`).
Das Token zeigt es nicht. Beim Schreiben gilt: Eine unveränderte Pill behält
ihr Label (Abschnitt 4.3). Eine neue Pill bekommt ihr Label vom Server aus
dem Namen des Ziels. Die API hat dafür DB-Zugriff, das MCP nicht. Deshalb
läuft die Umwandlung in der API (9.2).

### 3.3 Was nicht abbildbar ist: Fehler statt stillem Verlust

Nicht abbildbar sind:

- Blocktypen ohne Markdown-Gegenstück aus dem BlockNote-Default-Satz
  (`@blocknote/core` laut `apps/web/package.json`), z. B. Tabelle, Bild,
  Video, Audio, Datei;
- Inline-Stile und Props ohne Gegenstück: Unterstreichung, Text- und
  Hintergrundfarbe, Ausrichtung ungleich links;
- Überschriften ab Ebene 4.

Die genaue Liste zieht P1 aus der installierten BlockNote-Version und legt sie
als Konstante in den Konverter (Abnahmekriterium von P1). Ein neuer Blocktyp
nach einem BlockNote-Update ist damit ein roter Test, kein stiller Verlust.

Regel, nach Richtung getrennt:

- **Lesen** (Quellfassung, 5.1): Ein nicht abbildbarer Block erscheint als
  eine geschützte Zeile `<!-- w2b:block <id> <typ> -->`, darunter, wo es geht,
  sein Klartext als Zitat. Ein Block mit nicht abbildbaren Inline-Stilen
  erscheint mit seinem Text und dem Marker `<!-- w2b:locked <id> -->`.
- **Schreiben**:
  - Marker unverändert zurück → der Server übernimmt den gespeicherten Block
    **bitgleich**. Auch ein Agent kann also ein Dokument mit Tabelle ändern,
    solange er die Tabelle nicht anfasst.
  - Marker entfernt → der Block wird gelöscht. Das ist eine bewusste Handlung
    und erscheint im Versions-Diff.
  - Text eines `locked`-Blocks geändert, oder ein Marker mit unbekannter ID →
    **422** mit `reason="block_not_representable"` und der Block-ID. Der
    Hinweis im Fehler: Diesen Block ändert der Web-Editor.
  - Markdown außerhalb des Dialekts, z. B. HTML oder eine GFM-Tabelle →
    **422** `markdown_unsupported` mit Zeile und Konstrukt. Kein Abschneiden,
    kein „bestes Bemühen“.

## 4. Stabile Block-IDs bei Teiländerungen (Frage 3, Weiche W58-1)

Das ist der Kern von M1b. Ziel: Verweise aus 1.3 bleiben über jede Änderung
per Markdown gültig, und der Versions-Diff bleibt lesbar.

### 4.1 Optionen

- **A — ID-Marker an jedem Block.** *Verworfen (Owner W58-1 = D,
  2026-10-20).* Jeder Block trägt seinen Anker
  ` [#id]`, Code-Blöcke auf eigener Zeile nach der Fence. Das ist die Form der
  WorkArea (`apps/api/src/who2be_api/services/wa_blocks.py#render_markdown`).
  - Vorteil: exakt. Jeder Block behält seine ID, auch wenn er geändert oder
    verschoben wird. Der Diff bleibt präzise.
  - Nachteil: Kosten und Lärm. Die Bestands-IDs sind 5 bis 23 Zeichen lang
    (Builder-Seeds tragen sprechende IDs wie `pb-persona-h-zweck`, im
    Web-Editor angelegte Blöcke UUIDs). Pro Block kommen grob 10–40 Bytes
    dazu, beim Bestand aus 1.5 also +15–30 % auf das Markdown **[E]**. Dazu
    kommt: Ein Modell, das 600 Listenpunkte mit Markern umschreibt, verliert
    eher einen Marker. Das kostet dann still die ID, ohne Fehler.
- **B — Anker über den Überschriftentext (Slug).** *Verworfen (W58-1 = D).*
  `## Prozedur` hat den
  Anker `prozedur`.
  - Vorteil: kein Marker im Text.
  - Nachteil: Jede Umbenennung bricht alle Verweise. Gleich lautende
    Überschriften brauchen Zähler. Es wäre eine zweite Ankersprache neben den
    bestehenden Block-IDs (ADR-0021).
- **C — nur serverseitige Zuordnung.** *Verworfen (W58-1 = D).* Kein Marker.
  Der Server ordnet neue
  und alte Blöcke per Diff (Inhalt, Position) zu.
  - Vorteil: sauberstes Markdown.
  - Nachteil: Bei Umbenennen und Verschieben zugleich ist die Zuordnung
    mehrdeutig. Ein umbenannter Abschnitt verliert seine ID, und damit hängen
    Resource-Links ins Leere (Zustand „Block gelöscht“, ADR-0021). Das ist der
    teure Fall.
- **D — Hybrid: Pflicht-Anker an Überschriften, Zuordnung für den Rest.**
  **Gewählt (Owner W58-1 = D, 2026-10-20).**
  - Überschriften tragen ` [#id]` am Zeilenende. Das ist dieselbe Form wie in
    der WorkArea.
  - Alle anderen Blöcke tragen keinen Marker. Der Server ordnet sie innerhalb
    ihres Abschnitts zu (4.3).
  - Vorteil: Genau die Blöcke, auf die gespeicherte Verweise zeigen (1.3),
    sind explizit und überleben Umbenennen und Verschieben. Die Kosten sind
    klein: Beim Bestand trägt jeder vierte Block eine Überschrift (320 von
    1.366).
  - Nachteil: Ein geänderter **und** verschobener Absatz bekommt eine neue
    ID. Der Diff zeigt ihn dann als „entfernt + hinzugefügt“ statt
    „geändert“. Einen gespeicherten Verweis bricht das nicht.

**Entscheidung D** (Owner 2026-10-20, „1D“). Sie schützt alles, was heute
gespeichert verweist, mit der
Ankersprache, die es schon gibt (ADR-0021, ADR-0047). Der einzige Preis liegt
in der Diff-Darstellung bei gleichzeitigem Ändern und Verschieben eines
Absatzes. A bleibt die Rückfallposition, wenn sich zeigt, dass Fälle oder
Maßnahmen doch auf einzelne Absätze zeigen sollen. Das wäre dann eine Frage
der Darstellung, keine Datenänderung.

### 4.2 Regeln für Überschriften-Anker (gilt bei A und D)

- Lesend steht der Anker in der Quellfassung (5.1) an jeder Überschrift.
- Schreibend gilt:
  - Überschrift mit bekannter ID → behält die ID, auch bei neuem Text, neuer
    Ebene oder neuer Position.
  - Überschrift ohne Anker → neue ID (`secrets`-basiert wie
    `apps/api/src/who2be_api/services/wa_blocks.py#new_block_id`).
  - Anker mit einer ID, die es in der Basisversion nicht gibt → 422
    `anchor_unknown`. Ein Agent kann also keine ID erfinden, die stabil
    aussieht, es aber nicht ist. Bei `create_*` gibt es keine Basisversion;
    dort ist jeder Anker unbekannt, also auch einer, der aus einem anderen
    Element kopiert wurde → ebenfalls 422 `anchor_unknown`. Wer einen Abschnitt
    übernimmt, entfernt dessen Anker; die Überschrift bekommt dann eine neue ID.
  - Dieselbe ID zweimal → 422 `anchor_duplicate`.
  - Eine Überschrift mit eingehenden Verweisen, die beim Schreiben fehlt, wird
    gelöscht wie heute im Web-Editor. Die Antwort nennt die betroffenen
    Verweise (`dangling_refs`), damit der Agent es merkt. Ein Verbot wäre eine
    Verhaltensänderung gegenüber dem Web-Editor und gehört nicht in diese ADR.

### 4.3 Zuordnung der übrigen Blöcke (Variante D)

Deterministisch, je Abschnitt (Blöcke zwischen zwei Überschriften), in dieser
Reihenfolge:

1. **Inhaltsgleich** (nach Normalform, 5.2) zu einem Block der Basisversion im
   selben Abschnitt → alte ID **und alter Block-JSON bitgleich**. Damit
   bleiben auch Props erhalten, die Markdown nicht zeigt (Pill-Label,
   Default-Props, Editor-Normalisierungen).
2. Übrige Blöcke gleichen Typs an gleicher Position im Abschnitt → alte ID,
   neuer Inhalt.
3. Rest → neue ID.

Mehrfach gleiche Absätze werden der Reihe nach zugeordnet. Die Regel ist eine
reine Funktion, testbar ohne DB.

**Modi** werden über ihren Namen zugeordnet, wie heute. Ihre drei
Inhaltsfelder sind je ein eigenes Markdown-Dokument mit eigener Zuordnung.

## 5. Rundlauf-Garantie und Tests (Frage 2, mit Weiche W58-2)

### 5.1 Weiche W58-2: woher die Schreibvorlage kommt

1.2 zeigt, dass die ADR-0056-Lesefassung keine Quelle ist. Drei Wege:

- **A — `format="text"` wird zur Quelle.** *Verworfen (Owner W58-2 = B,
  2026-10-20).* Alle lesenden Werkzeuge liefern
  Quell-Markdown mit Ankern und Platzhalter-Tokens.
  - Vorteil: wörtlich „ein Format“.
  - Nachteil: `get_persona` und `fetch_playbook` verlieren den aufgelösten
    Render. Gerade den liest ein Agent beim Start, um zu arbeiten, nicht um
    zu schreiben. Danach bräuchte er für jeden Platzhalter einen Folgeaufruf.
- **B — neuer Wert `format="source"`.** **Gewählt (Owner W58-2 = B,
  2026-10-20).** Er liefert Quell-Markdown: Kopf mit
  `id`, `version`, `status` und `base_rev` (Konflikt-Token aus 6.3, die Basis
  für die Teiländerung), Inhalt in der
  Normalform aus 5.2, Anker, Tokens. `text` bleibt die Lesefassung zum
  Arbeiten. `full` (Editor-JSON) bleibt bitgleich, ist aber nicht mehr die
  Vorlage für `update_*`.
  - Vorteil: Arbeiten und Bearbeiten bleiben getrennt. Kein Werkzeug ändert
    seine Default-Antwort, kein ADR-0056-Vertrag bricht.
  - Nachteil: drei Werte statt zwei. Etwa 60 Bytes Beschreibung je
    betroffenem Werkzeug.
- **C — die Schreibwerkzeuge liefern die Quelle mit.** *Verworfen
  (W58-2 = B).* Jedes
  `create_*`/`update_*` antwortet mit dem gespeicherten Quell-Markdown.
  - Vorteil: kein neuer Lesewert.
  - Nachteil: Für die erste Änderung an einem bestehenden Element fehlt die
    Vorlage trotzdem.

**Entscheidung B** (Owner 2026-10-20, „2B“). „Ein Standard“ meint das Format
Markdown, nicht ein einziges
Dokument für zwei Zwecke. B hält beide ADR-0056-Werte bitgleich und ersetzt
nur, was der Schreiber liest: heute `full` (JSON), künftig `source`
(Markdown). Der Hinweis in jeder Text-Antwort und in jeder
`update_*`-Beschreibung (ADR-0056 §3.5, §5) zeigt dann auf `source`.

`source` gibt es für die Werkzeuge, deren Inhalt man schreiben kann:
`get_persona`, `fetch_playbook`, `fetch_resource`, `get_system_prompt`,
`get_external_tool`, und `get_version` (Vorlage für eine Wiederherstellung).

### 5.2 Normalform und Garantie

Der Konverter definiert **eine** Markdown-Normalform: Listenmarker `-`,
Einrückung zwei Leerzeichen, genau eine Leerzeile zwischen Blöcken, Fett
`**`, kursiv `*`, Fences mit drei Backticks. `source` liefert immer die
Normalform. Garantiert wird:

- **G1 Rundlauf über den Speicher.** Für jedes abbildbare Dokument `B` gilt
  `from_markdown(to_markdown(B), base=B) == B`, bitgleich als JSON. Wer
  `source` liest und unverändert schreibt, erzeugt keine inhaltlich neue
  Version. Ob der Server eine Version ohne Änderung überhaupt anlegt
  (No-op-Schutz), ist eine eigene Frage. Diese ADR legt sie nicht fest.
- **G2 Idempotenz der Normalform.** Für jedes gültige Markdown `M` gilt
  `to_markdown(from_markdown(M)) == normalize(M)`, und
  `normalize(normalize(M)) == normalize(M)`.
- **G3 Kein stiller Verlust.** Was G1 nicht erfüllt, endet in einem 422 aus
  3.3, nie in einem gespeicherten, verkürzten Dokument.

G1 gilt dank der Zuordnung aus 4.3 Schritt 1 auch für Props, die Markdown
nicht zeigt, solange der Block unverändert ist.

### 5.3 Wie getestet wird

- **Golden-Tests über den Bestand.** Alle 34 verwalteten Inhaltsdateien
  (1.5) laufen durch G1 und G2. Eine neue verwaltete Datei fällt automatisch
  mit in den Test (Glob, keine Liste).
- **Erzeugte Dokumente (Property-Tests).** Ein Generator baut zufällige
  Blockbäume über die Grammatik aus 3.2: Typen, Ebenen, Verschachtelung,
  Stil-Kombinationen, Pills, Sonderzeichen wie `*`, `_`, `` ` ``, `#`, `[`,
  `{{` im Text. Er prüft G1 und G2. Der Seed ist fest und wird bei einem
  Fehler ausgegeben. Ohne neue Abhängigkeit: Hypothesis steht nicht in den
  Lock-Dateien, und eine neue Test-Abhängigkeit müsste durch die
  Lizenz-Gates (ADR-0033). Der Generator mit `random.Random(seed)` reicht für
  die Grammatik.
- **Escaping-Fälle als feste Tabelle**: Text, der wie Markdown aussieht, muss
  als Text zurückkommen (`1. ` am Absatzanfang, `**` ohne Gegenstück, `{{` ohne
  gültiges Token).
- **Rot-Probe.** Ein absichtlich verlustbehafteter Konverter, der z. B.
  `italic` verwirft, muss die Golden-Tests reißen lassen. So ist belegt,
  dass die Tests den Verlust sehen. Methode wie die Rot-Proben aus
  ADR-0056 §6.
- **Zuordnung (4.3)** als Tabellentest: umbenennen, verschieben, einfügen,
  löschen, doppelte Absätze. Jeweils mit erwarteter ID-Liste.
- **Nicht abbildbare Blöcke (3.3)**: Marker unverändert → bitgleich, Marker
  entfernt → gelöscht, `locked` geändert → 422.

## 6. Form der Teiländerung (Frage 4)

### 6.1 Optionen

- **A — immer das ganze Dokument (PUT) in Markdown.**
  - Vorteil: ein Weg, keine neuen Werkzeuge. Die Anker-Regeln aus 4.2 halten
    die IDs.
  - Nachteil: Eine Ein-Satz-Änderung an einem 15-KB-Playbook schickt 15 KB.
    Jedes Umschreiben des ganzen Dokuments ist eine Gelegenheit, nebenbei
    etwas zu verlieren. Das ist das Risiko, das ADR-0056 §5 heute mit drei
    Schichten Prosa absichert.
- **B — Abschnitt per Anker, nach dem WorkArea-Muster.** Ein Aufruf nennt
  einen Überschriften-Anker, eine Operation (`replace`, `insert_after`,
  `delete`) und Markdown. Ein Abschnitt reicht von der Überschrift bis vor die
  nächste Überschrift gleicher oder höherer Ebene. Das ist dieselbe
  Abschnittsgrenze wie bei den Resource-Abschnitten
  (`packages/models/src/who2be_models/resource.py#LinkedBlockSection`). Bei
  `replace` behält die Überschrift ihre ID, wenn das neue Markdown mit einer
  Überschrift ohne Anker beginnt. Das entspricht dem Anker-Erbe in
  `apps/api/src/who2be_api/services/wa_blocks.py#apply_patch`.
  - Vorteil: kleine Aufrufe. Der Rest des Dokuments bleibt unberührt und
    damit bitgleich. Bekanntes Muster.
  - Nachteil: ein neues Werkzeug. Inhalt vor der ersten Überschrift und
    Dokumente ohne Überschriften brauchen einen eigenen Anker (6.2).
- **C — Text-Patch (Suchen/Ersetzen oder Unified Diff).**
  - Vorteil: kleinste Aufrufe.
  - Nachteil: Ein Unified Diff braucht exakte Kontextzeilen. Suchen/Ersetzen
    scheitert an mehrdeutigen Treffern und berührt Anker-Marker, ohne es zu
    merken. Und es ist eine zweite Änderungssprache neben den Ankern.

**Entscheidung A und B zusammen, C nicht** (mit Annahme dieser ADR). A ist
der Vollstand (Anlegen,
größerer Umbau), B die Teiländerung. Beide sprechen dieselbe Ankersprache.

### 6.2 Werkzeuge

- **Die `create_*`/`update_*`-Werkzeuge** für Persona, Playbook, Resource,
  System-Prompt und externes Tool behalten Name und PUT-Semantik. Ihre
  BlockNote-Felder (1.1) werden zu Markdown-Strings, beim externen Tool also
  auch `usage_notes` (Owner W58-4 = ja, 2026-10-20). Strukturfelder bleiben
  typisiert: Name, Tags, Trigger, Typ, Locale, Modus-Name, `trigger`,
  `is_default`, `playbook_id`, Skills. Die Agent-Werkzeuge
  (`create_agent`/`update_agent`) tragen kein BlockNote und ändern sich nicht.
- **Ein neues Werkzeug `edit_content`** für Teiländerungen an allen fünf
  Elementarten. Ein generisches Werkzeug statt fünf, wegen des Budgets
  (Abschnitt 8):

  ```text
  edit_content(entity_type, entity_id, base_rev, op, anchor | field, markdown?)
  ```

  - `anchor`: Überschriften-ID wie in 4.2.
  - `field`: ein ganzes Markdown-Feld, für Dokumente ohne Überschrift und für
    die Modus-Felder. Beispiele: `body`, `profile`, `modes[Recherche].anti_patterns`.
  - `base_rev`: der Konflikt-Token aus dem `source`-Kopf (6.3). Weicht der
    Stand ab, antwortet der Server mit 409 `version_conflict` und nennt die
    aktuelle Version und den aktuellen `base_rev`. Das Muster ist
    `expected_rev` aus
    `packages/models/src/who2be_models/workarea.py#ArtifactPatch`. Eine
    Versionsnummer reicht dafür nicht (6.3).
- **Versionsregeln wie heute** (`apps/api/src/who2be_api/services/persona_service.py#PersonaService.update`):
  - Auf einer aktiven Version entsteht ein Draft.
  - Ist schon ein Draft offen, arbeitet `edit_content` **auf diesem Draft**,
    wenn `base_rev` zum Draft passt. Heute antwortet `update_*` dann mit 409,
    und das bleibt für den Vollstand so. Für Teiländerungen ist „am offenen
    Draft weiterarbeiten“ der gewollte Fall. Sonst bräuchte jede zweite
    Teiländerung einen Umweg über den Web-Editor.
  - Rechte, Tag-Scope, Rate-Limit und der Schutz verwalteter Inhalte gelten
    unverändert. `edit_content` ruft dieselben Service-Methoden.
- **Rechte.** `edit_content` braucht die Schreib-Capability der jeweiligen
  Elementart. Das Werkzeug ist sichtbar, wenn der Agent mindestens eine davon
  hat (Eintrag in
  `packages/models/src/who2be_models/tool_requirements.py#MCP_TOOL_REQUIREMENTS`).
  Die Prüfung je Aufruf macht der Service.

### 6.3 Konflikt-Token `base_rev`: Schutz vor stillem Überschreiben

Die Versionsnummer allein schützt den offenen Draft nicht. Der Autosave des
Web-Editors (PATCH `…/draft`,
`apps/api/src/who2be_api/services/persona_service.py#PersonaService.update_draft`)
überschreibt den Draft in place und zählt **keine** Version hoch
(`apps/api/src/who2be_api/repositories/versioned_repository.py#VersionedAggregateRepository._upsert_draft`).
Ohne eigenen Token sähe der Ablauf so aus: Ein Agent liest `source` (Draft
v5), ein Mensch speichert danach im Web-Editor, wieder als v5, dann schickt
der Agent `edit_content(…, replace §X)`. Der Server sieht v5 = v5, und die
Änderung des Menschen in §X ist still weg. Das verletzt G3 (5.2).

Optionen:

- **A — Content-Hash als `base_rev`.** Der Server bildet SHA-256 über die
  kanonische JSON-Form (sortierte Schlüssel, ohne Leerraum) von Versions-Inhalt,
  Name und Locale der Version, auf die geschrieben würde, und liefert die
  ersten 16 Hex-Zeichen im `source`-Kopf (5.1 B). `edit_content` rechnet ihn
  in derselben Transaktion unter der Zeilensperre neu, die die Schreibpfade
  heute schon nehmen
  (`apps/api/src/who2be_api/repositories/versioned_repository.py#VersionedAggregateRepository._current_version_sql`,
  `FOR UPDATE OF e`), und vergleicht.
  - Vorteil: ändert sich bei jedem inhaltlichen Schreiben, gleich über welchen
    Pfad (Autosave, `update_*`, Wiederherstellen, künftige Pfade).
    Keine Spalte, keine Migration. Kein Schreibpfad muss daran denken, einen
    Zähler zu pflegen. Rein funktional testbar.
  - Nachteil: Hash über das ganze Dokument je Schreibaufruf (bei 38 KB
    vernachlässigbar). Ein Mensch, der ändert und zurückändert, erzeugt
    denselben Hash; das ist kein Verlust, denn der Inhalt ist derselbe.
- **B — `updated_at` als `base_rev`.** Der Autosave setzt `updated_at = now()`
  auf der Entity-Zeile schon heute.
  - Vorteil: kein Rechenaufwand, Wert steht in `PersonaRead.updated_at`.
  - Nachteil: Der Schutz hängt daran, dass **jeder** künftige Schreibpfad den
    Zeitstempel setzt. Ein vergessener Pfad öffnet die Lücke wieder, ohne dass
    ein Test reißt. Metadaten-Schreibvorgänge ohne Inhaltsänderung erzeugen
    Schein-Konflikte. Der Wert sitzt an der Entity, nicht an der Version.
- **C — keine Teiländerung am offenen Draft.** `edit_content` antwortet bei
  offenem Draft mit 409 wie `update_*`, nur auf einer aktiven Version entsteht
  ein neuer Draft. Die Versionsnummer reicht dann, weil eine aktive Version
  unveränderlich ist.
  - Vorteil: kein neuer Token, kein neuer Konfliktfall.
  - Nachteil: Jede zweite Teiländerung in Folge scheitert, bis ein Mensch den
    Draft im Web-Editor veröffentlicht oder verwirft. Mehrschrittige
    Überarbeitungen durch einen Agenten (der eigentliche Zweck von M1b) gehen
    dann nur noch über den Vollstand.

**Entscheidung A** (mit Annahme dieser ADR). Der Token muss sich bei jedem
Schreiben ändern, und das
garantiert nur ein Wert, der aus dem Inhalt selbst entsteht. B verlagert die
Garantie auf eine Konvention, C opfert den Kernfall. Das ist eine technische
Folge aus G3, keine Owner-Weiche.

Regeln:

- `base_rev` ist bei `edit_content` **Pflicht**. `update_*` (Vollstand)
  braucht ihn nicht: Es schreibt nie in einen offenen Draft (409
  `draft_exists`, 6.2), sondern legt einen Draft auf einer unveränderlichen
  aktiven Version an. Schreibt jemand dazwischen, entsteht dabei selbst ein
  Draft, und der Vollstand scheitert laut.
- Die Antwort jedes erfolgreichen Schreibens trägt den neuen `base_rev`.
  Mehrere Teiländerungen nacheinander brauchen so keinen Zwischen-Lesevorgang.
- Grenze: Der Web-Editor prüft den Token nicht. Schreibt ein Agent zwischen
  zwei Autosaves, kann der nächste Autosave mit älterem Editor-Stand die
  Agenten-Änderung überschreiben. Das ist dieselbe Lage wie heute bei zwei
  offenen Browser-Tabs. Den Web-Editor anzupassen ist nicht Teil dieser ADR
  (Karte: Out-of-Scope); es ist als Folgearbeit in Abschnitt 11 vermerkt.

## 7. Übergang: Editor-JSON als Eingabe (Frage 5, Weiche W58-3)

Unstrittig ist:

- Die **REST-API** des Web-Editors nimmt weiter BlockNote-JSON. Das ist
  Speicherformat und Editor-Vertrag (Abschnitt 2, Punkt 3), keine
  Agenten-Eingabe.
- **`format="full"`** bleibt lesend bitgleich (ADR-0056 §3.2), aber nur als
  Diagnose- und Strukturweg, nicht mehr als Schreibvorlage.

Entschieden ist auch, wie lange die **MCP-Schreibwerkzeuge** Editor-JSON noch
annehmen (Owner W58-3 = A, 2026-10-20, „3A“):

- **A — harter Schnitt in einem Paket.** **Gewählt.** Mit P3 nehmen die
  MCP-Werkzeuge nur
  noch Markdown. Ein Aufruf mit Editor-JSON scheitert an der
  Schema-Validierung mit einer klaren Meldung, nie still. Die verwalteten
  Builder-Inhalte, die heute JSON-Schreibwege beschreiben, ziehen im selben
  Release mit (P4, über `BUILDER_CONTENT_VERSION` in
  `apps/api/src/who2be_api/repositories/workspace_repository.py#sync_managed_builder_content`).
  - Vorteil: sofort ein Standard. Die volle Budget-Ersparnis kommt mit P3. Es
    gibt kein Doppel-Schema und keinen Abbau-Termin, den man vergessen kann.
  - Nachteil: Fremde Agenten mit altem Prompt scheitern ab dem Tag der
    Umstellung, bis jemand ihren Prompt anpasst.
- **B — befristetes Doppelangebot.** *Verworfen (W58-3 = A).* Das Schema
  nimmt beides an (`anyOf`).
  Jeder JSON-Schreibaufruf würde gezählt, ein Abbau-Paket käme zu einem festen
  Datum oder nach 14 Tagen ohne JSON-Aufruf, je nachdem, was später eintritt.
  - Vorteil: kein Bruch für Bestandsagenten.
  - Nachteil: Bis zum Abbau wächst der Katalog, statt zu schrumpfen, denn beide
    Schemas stehen im `tools/list`. Es gibt zwei Schreibwege mit zwei
    Fehlerbildern, und für die Zählung braucht es eine neue Quelle in der
    Nutzungserfassung.
- **C — Doppelangebot ohne Frist.** *Verworfen.* Widerspricht dem
  Owner-Wortlaut („ein
  Standard“) und ist nur der Vollständigkeit halber genannt.

**Entscheidung A, vor dem Cloud-Release** (Owner 2026-10-20, „3A“). Vor dem
Release gibt es keine
fremden Konsumenten mit Bestandsschutz. Die bekannten JSON-Schreiber sind die
eigenen Builder-Inhalte, und die ziehen im selben Release mit. Der Bruch ist
laut (Schema-Fehler) und nicht still. B kauft Rücksicht, die vor dem Release
niemand braucht, und verschiebt die Ersparnis. Das Risiko für Agenten
außerhalb des Repos hat der Owner damit bewusst getragen.

## 8. Wirkung auf das Budget (Frage 6)

### 8.1 Katalog (`tools/list`): kleiner als erwartet

Gemessen am Stand `0ddb704a` mit dem In-Memory-Client, dieselbe Zählweise
wie `apps/mcp/tests/test_tool_payload_budget.py#_tools_payload_bytes`
**[B]**:

| Werkzeuge | Bytes gesamt | davon Eingabe-Schema |
| --- | ---: | ---: |
| `create_/update_persona` | 5.766 / 5.317 | 4.999 / 4.941 |
| `create_/update_agent` | 5.828 / 5.935 | 5.527 / 5.700 |
| `create_/update_playbook` | 2.456 / 2.048 | 1.628 / 1.690 |
| `create_/update_resource` | 2.243 / 1.868 | 1.621 / 1.524 |
| `create_/update_external_tool` | 2.862 / 2.655 | 2.427 / 2.305 |
| `create_/update_system_prompt` | 2.037 / 1.699 | 1.327 / 1.306 |
| **zwölf Schreibwerkzeuge zusammen** | **40.714** | |

Davon hängt am BlockNote-Format **[B]**:

- die Block-Listen-Schemas: 4 je Persona-Werkzeug, 1 je Resource-Werkzeug,
  zusammen 3.564 Bytes;
- die JSON-Beispiele in `create_playbook` und `create_system_prompt`, je etwa
  330 Bytes.

Die Agent-Werkzeuge (11,8 KB) tragen kein BlockNote. Ihr Gewicht ist die
`AgentToolPolicy`, und die ist Sache von W2 bzw. der Schema-Diät (Vorlage T2).
Playbook, System-Prompt und externes Tool haben schon heute ein String-Feld.
Dort spart Markdown nur Beschreibungstext.

Schätzung **[E]**:

| Posten | Wirkung |
| --- | ---: |
| Block-Listen → String-Felder (Persona, Resource) | −2,8 bis −3,2 KB |
| JSON-Beispiele und BlockNote-Erklärsätze → ein Markdown-Satz | −0,8 bis −1,2 KB |
| neues Werkzeug `edit_content` | +1,2 bis +1,6 KB |
| `format="source"` in sechs Lesewerkzeugen (5.1 B) | +0,3 bis +0,4 KB |
| **netto** | **−1,6 bis −2,7 KB** |

Das ist deutlich weniger als die 10–15 KB der Vorlage (§3 A+). Die Vorlage hat
am 2026-10-09 vor T1–T4 gemessen (147,6 KB, die Persona-Werkzeuge allein
15,7 KB, heute 11,1 KB) und die Agent-Werkzeuge unter den W1-Hebel gezählt
(§1.3 „Schreib-Werkzeuge für Persona und Agent“). Die Schema-Diät T2 hat einen
Teil des damaligen Hebels schon geerntet. Der Rest liegt bei der
`AgentToolPolicy`, also nicht bei W1.

Wird der Katalog-Gewinn zur Bedingung, gibt es zwei Stellschrauben, beide
außerhalb dieser ADR: Teiländerungen nur für Playbook und Resource (spart
etwa 0,4 KB Beschreibung), oder `edit_content` nur im Builder-Profil (W2).

### 8.2 Aufrufe: hier liegt der Gewinn

Der größere Effekt liegt nicht im Katalog, sondern in jedem Schreib- und
Vorlagen-Lesevorgang. Die 15 DE-Body-Dateien aus 1.5 (ohne Persona-Profil
und Modi) als JSON-String-Argument kosten 273.194 Bytes **[B]**. Als Markdown
in der Normalform aus 5.2 wären es etwa 116.000 Bytes, also **Faktor 2,4**,
je Datei zwischen 1,8 und 6,2 **[E]**. Gemessen ist die
Klartext-Serialisierung plus die Markdown-Marker je Block; die Normalform
selbst ist noch nicht gebaut, Inline-Stile kommen also noch dazu. Ein Playbook
wie `builder_playbook_agent_body.json` geht damit von 38 KB auf 16 KB je
Vollstand. Eine Teiländerung (6.1 B) schickt nur den Abschnitt. Lesend gilt
dasselbe Verhältnis für die Vorlage (`source` statt `full`).

### 8.3 Messpunkte

- **M1 Katalog:**
  `apps/mcp/tests/test_tool_payload_budget.py#test_tools_list_payload_stays_under_budget`.
  P3 trägt den gemessenen Stand vorher und nachher in den Kommentar am
  Budget-Wert.
- **M5 Argumentgröße (neu, P1):** ein Test, der für alle verwalteten
  Inhaltsdateien die Bytes des Editor-JSON-Arguments und des
  Markdown-Arguments misst und das Verhältnis ≥ 1,8 prüft, die kleinste
  gemessene Datei. Er reißt, wenn die Normalform aufbläht.
- **M6 Vorlagen-Antwort:** je Werkzeug mit `source` ein Budget-Test nach dem
  Muster aus ADR-0056 §6. `test_every_format_aware_tool_has_a_budget_test`
  erzwingt das schon.

## 9. Paketschnitt (Frage 7)

Seriell, je Paket höchstens acht Dateien, je Paket ein PR mit
Changelog-Fragment. **Keine Datenbank-Migration**: Das Speicherformat bleibt
BlockNote (Abschnitt 2).

**P1 — Konverter, ohne Verhaltensänderung** (Domäne `packages/models`).
Reine Funktionen ohne DB, wie die Klartext-Serialisierung aus ADR-0056, damit
API und MCP dieselbe Quelle nutzen.

1. `packages/models/src/who2be_models/blocknote_markdown.py` (neu:
   `to_markdown`, `from_markdown(md, base)`, `normalize`, Zuordnung 4.3,
   Darstellbarkeitsprüfung 3.3)
2. `packages/models/tests/test_blocknote_markdown_golden.py` (neu: G1/G2 über
   den Bestand, M5, Rot-Probe)
3. `packages/models/tests/test_blocknote_markdown_generated.py` (neu:
   Generator, Escaping-Tabelle)
4. `packages/models/tests/test_blocknote_markdown_ids.py` (neu: 4.2/4.3,
   3.3)
5. `packages/models/src/who2be_models/__init__.py` (Export)
6. `changelog.d/<slug>.added.md`

**P2 — Schreibweg in der API** (Domäne `apps/api`). Die API wandelt um, weil
sie die Basisversion transaktional mit dem Draft liest und die Pill-Labels
kennt (3.2). Das MCP bleibt ein dünner HTTP-Adapter (ADR-0005).

1. `packages/models/src/who2be_models/content_markdown.py` (neu:
   Eingabemodelle mit Markdown-Feldern, `ContentEdit` für 6.2)
2. `apps/api/src/who2be_api/services/content_markdown_service.py` (neu:
   Markdown → Service-Aufruf je Elementart, Label-Auflösung,
   `dangling_refs`)
3. `apps/api/src/who2be_api/routers/content_markdown.py` (neu: ein Router mit
   `{entity_type}` statt fünf, `PUT …/{entity_type}/{id}/markdown`,
   `PATCH …/{entity_type}/{id}/markdown`, `GET …?format=source`)
4. `apps/api/src/who2be_api/main.py` (Router einhängen)
5. `apps/api/tests/test_content_markdown_service.py` (neu)
6. `apps/api/tests/test_content_markdown_router.py` (neu, inkl. RBAC,
   Tag-Scope, verwaltete Inhalte, 409/422-Fälle; Pflichtfall: `source` lesen,
   Autosave über PATCH `…/draft`, dann `edit_content` mit altem `base_rev` →
   409 `version_conflict`, Draft unverändert)
7. `docs/reference/openapi.json` (neue Routen)
8. `changelog.d/<slug>.added.md`

**P3 — MCP-Umstellung** (Domäne `apps/mcp`, Hotspot `server.py`, deshalb
allein). Mit W58-3 = A ist das der harte Schnitt, vor dem Cloud-Release.

1. `apps/mcp/src/who2be_mcp/server.py` (Schreibwerkzeuge auf Markdown,
   `format="source"`, Beschreibungen)
2. `apps/mcp/src/who2be_mcp/tools/content.py` (neu: `edit_content`)
3. `apps/mcp/src/who2be_mcp/client.py` (neue Routen)
4. `packages/models/src/who2be_models/tool_requirements.py` (`edit_content`)
5. `apps/mcp/tests/test_tool_payload_budget.py` (M1, M6)
6. `apps/mcp/tests/test_content_tools.py` (neu)
7. `apps/mcp/tests/test_server.py` (Schreibwerkzeuge)
8. `changelog.d/<slug>.changed.md`

**P4 — Builder-Inhalte und Doku** (Domäne Inhalte, im selben Release wie P3).

1. `apps/api/src/who2be_api/repositories/builder_playbook_persona_body.json`
   und `…/builder_playbook_playbook_body.json` (DE)
2. die EN-Gegenstücke unter `apps/api/src/who2be_api/repositories/en/`
3. `apps/api/src/who2be_api/repositories/builder_resource_conventions_body.json`
   und EN
4. `apps/api/src/who2be_api/repositories/workspace_repository.py`
   (`BUILDER_CONTENT_VERSION` +1)
5. `docs/mcp-payload-budget.md`, `docs/mcp-claude-code.md`
6. `changelog.d/<slug>.changed.md`

Die Werkzeugzahl (100 → 101) zieht P4 nicht in `CLAUDE.md` nach. Sie steht
künftig nur in `README.md` und `ROADMAP.md`; das regelt Kanban-Karte
t_bf8ed54c.

Zählt man DE und EN einzeln, sind es mehr als acht Dateien. Dann teilt sich
P4 in P4a (Inhalte DE+EN, Version) und P4b (Doku). P4a muss vor oder mit P3
auf `main` sein, sonst beschreiben die Builder-Playbooks einen Schreibweg,
den es nicht mehr gibt.

Ein Paket P5 (Abbau einer JSON-Eingabe nach Frist) entfällt mit W58-3 = A.

**Werkzeugzahl:** 100 → 101 (`edit_content`). Budget: netto −1,6 bis
−2,7 KB auf `tools/list` (8.1, geschätzt), bei 114.203 von 180.000 Bytes.

## 10. Weichen (entschieden)

Owner, 2026-10-20, wörtlich:

> „1D, 2B, 3A, 4 ja“

| Weiche | Frage | Entscheidung | Verworfen |
| --- | --- | --- | --- |
| **W58-1** (4.1) | Wie bleiben Block-IDs bei Markdown-Änderungen stabil? | **D**: Pflicht-Anker ` [#id]` nur an Überschriften (WorkArea-Form), übrige Blöcke ordnet der Server je Abschnitt zu. | A (Anker an jedem Block), B (Slug), C (nur Server-Zuordnung) |
| **W58-2** (5.1) | Woher liest der Schreiber die Markdown-Vorlage? | **B**: neuer Lesewert `format="source"`; `text` bleibt Lesefassung, `full` bleibt bitgleich. | A (`text` wird Quelle), C (nur die Schreibantwort liefert die Quelle) |
| **W58-3** (7) | Wie lange nimmt das MCP noch Editor-JSON an? | **A**: harter Schnitt mit P3, vor dem Cloud-Release, Builder-Inhalte im selben Release, kein P5. | B (befristetes Doppelangebot mit P5), C (Doppelangebot ohne Frist) |
| **W58-4** (6.2) | Gehört `usage_notes` des externen Tools mit zum Standard? | **Ja**: `usage_notes` wird ebenfalls Markdown. Ein Feld, kein neues Werkzeug. | Nein (ein BlockNote-Schreibfeld bliebe als Ausnahme) |

Die Abschnitte 3, 6, 8 und 9 hängen an keiner Owner-Weiche und gelten mit der
Annahme dieser ADR.

## 11. Konsequenzen

**Positiv.**

- Agenten schreiben, was sie lesen, und kein Editor-JSON mehr.
- Ein Vollstand kostet etwa 40 % der heutigen Argumentgröße (8.2, Schätzung
  **[E]**, belegt erst mit M5 in P1).
- Teiländerungen schicken nur noch den betroffenen Abschnitt.
- Das PUT-Risiko aus ADR-0056 §5, nämlich eine Lesefassung als Vorlage zu
  nehmen und damit den Inhalt zu leeren, sinkt. Wer eine Teiländerung macht,
  berührt den Rest nicht.
- Verweise auf Abschnitte überleben Umbenennen und Verschieben.
- Nicht abbildbare Inhalte gehen nicht verloren, sondern blockieren laut.

**Negativ.**

- Es gibt einen Konverter mehr, und er muss mit jeder BlockNote-Version
  Schritt halten. P1 macht einen neuen Blocktyp zu einem roten Test.
- Mit W58-3 = A brechen Agenten außerhalb des Repos, die JSON schreiben, am
  Tag der Umstellung laut.
- Der Katalog schrumpft durch W1 kaum (8.1). Wer die Builder-Last senken will,
  braucht W2.
- `edit_content` auf einem offenen Draft (6.2) ist eine bewusste Abweichung von
  der 409-Regel der `update_*`-Werkzeuge. Sie muss in der Beschreibung stehen.
  Abgesichert ist sie über `base_rev` (6.3), nicht über die Versionsnummer.
- Der Schutz wirkt nur in eine Richtung: Der Web-Autosave prüft `base_rev`
  nicht und kann eine Agenten-Teiländerung überschreiben (6.3, Grenze).
  Folgearbeit außerhalb dieser ADR: den Autosave auf denselben Token
  umstellen.

**Neutral.** Das Speicherformat, der Web-Editor, die REST-API für BlockNote,
die Versionierung und alle gespeicherten Verweise bleiben unverändert. Es
gibt keine Migration.
