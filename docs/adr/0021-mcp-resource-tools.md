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
