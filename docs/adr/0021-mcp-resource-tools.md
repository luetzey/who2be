# ADR 0021 — MCP-Resource-Tools

- Status: Akzeptiert
- Datum: 2026-05-29
- Kontext: Phase 2.2 (Resources mit Block-Editor)

## Kontext

Resources sind eine zweite, versionierte Wissensebene (Block-Dokumente).
Playbooks koennen auf einzelne Bloecke einer Resource verweisen (Block-Refs).
Agenten brauchen lesenden Zugriff: ganze Resources, gezielte Bloecke und die
Block-Refs eines Playbooks. Der MCP-Server ist ein duenner HTTP-Adapter
(ADR-0005) ohne Geschaeftslogik.

## Entscheidung

Drei Aenderungen am FastMCP-Server (`apps/mcp`):

- **`list_resources()`** — liefert die aktiven Resources des Workspaces als
  Kurzform (`id`, `name`, `block_count`).
- **`fetch_resource(resource_id, block_ids?)`** — liefert die aktive Version;
  mit `block_ids` nur die angefragten Bloecke in angefragter Reihenfolge
  (Filter clientseitig im Tool ueber `content.blocks`).
- **`fetch_playbook`** gibt zusaetzlich `linked_blocks: ResourceLinkRead[]`
  zurueck (neues `PlaybookWithResources`-Modell, analog `PersonaWithPlaybooks`).

**Kein Auto-Inline:** `fetch_playbook` liefert nur Pointer (`resource_id`,
`block_id`), ein `available`-Flag und eine kurze Plain-Text-`preview` (200
Zeichen, serverseitig). Blockinhalte zieht der Agent bei Bedarf gezielt ueber
`fetch_resource`. Das haelt Playbook-Antworten klein und ueberlaesst dem
Agenten die Kontroll ueber den Kontext.

**Block-Refs zeigen immer auf `latest active`** — kein Version-Pin. Existiert
der referenzierte Block in der aktiven Resource-Version nicht (mehr), ist
`available=false` und es gibt keine Vorschau.

## Konsequenzen

- Agenten koennen Wissen gezielt nachladen statt grosse Dokumente inline zu
  bekommen — bessere Token-Oekonomie.
- Workspace-Isolation bleibt serverseitig (Token traegt `workspace_id`); die
  Tools kennen den Workspace aus dem Token, kein neuer Tool-Parameter.
- "Block geloescht" ist ein sichtbarer Zustand statt eines stillen 404.

## Alternativen

- **Auto-Inline der verlinkten Bloecke in `fetch_playbook`** — verworfen:
  blaeht Antworten auf und nimmt dem Agenten die Kontextkontrolle.
- **Version-Pin der Block-Refs** — verworfen: Refs sollen automatisch der
  aktiven Version folgen; Pinning waere ein spaeteres Opt-in.

## Referenzen

- Plan: `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md` (§2.2.D)
- ADR-0005 (MCP als HTTP-Client), ADR-0020 (Status pro Version)

## Nachtrag 2026-10-23 — `fetch_resource` schneidet Abschnitte wie `fetch_playbook`

`fetch_resource(block_ids=[…])` filterte bisher exakt die genannten Bloecke.
Ein Ueberschriften-Anker aus `list_resource_blocks` lieferte darum nur die
Ueberschrift, obwohl Werkzeugbeschreibung und `list_resource_blocks`
Abschnitte versprachen. `fetch_playbook` schnitt dagegen schon Abschnitte.

Fuer Resources gilt jetzt dieselbe Abschnittsregel wie fuer Playbooks:

- Ein Ueberschriften-Anker liefert seinen Abschnitt, also die Ueberschrift
  bis vor die naechste Ueberschrift **gleicher oder hoeherer** Ebene. Tiefere
  Ueberschriften bleiben im Abschnitt.
- Ein Anker, der keine Ueberschrift ist, bleibt ein Einzelblock.
- Die Abschnitte folgen der angefragten Reihenfolge. Ueberlappen sie sich,
  kommt jeder Block nur einmal, an der Stelle seines ersten Vorkommens.
- Unbekannte Anker treffen wie bisher nichts. Eine Auswahl ohne Treffer
  liefert einen leeren Body und nicht still das Volldokument.

Die Regel hat genau eine Implementierung:
`who2be_models.blocknote_text.section_blocks` (mit `is_heading_block` und
`heading_level`). Playbook-Schnitt, `fetch_resource`, die Block-Ref-Vorschau
(`section_block_ids`) und der Resource-Resolver nutzen sie gemeinsam. Sie liegt
im Modell-Paket, weil der MCP-Prozess `who2be_api` nicht importieren darf
(ADR-0005).

Dabei wird auch die Abbruch-Bedingung vereinheitlicht. Die API-Kopie brach
bisher nur am naechsten Heading **gleicher** Ebene ab, die Web-Vorschau
(`sectionPreview`) schon an gleicher oder hoeherer Ebene. Nur die zweite Form
ist ein Abschnitt im Sinne einer Gliederung. Ein h3-Anker direkt vor einem h2
reichte vorher ueber das h2 hinaus bis zum naechsten h3 oder ans
Dokumentende. Das trifft auch den Playbook-Schnitt und die Block-Ref-Vorschau.
Faelle, in denen auf eine tiefere Ebene direkt eine hoehere folgt, liefern
jetzt weniger Bloecke. Alle anderen bleiben gleich.

Beim Playbook-Schnitt bleibt die Ausgabe in Dokument-Reihenfolge, weil dort
der Body neu gerendert wird. Bei Resources gilt wie bisher die angefragte
Reihenfolge.
