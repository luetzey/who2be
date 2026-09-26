# Blockselektion als Regelweg fuer Playbook-Abrufe (Karte t_6e029d6b)

Stand: 2026-09-26, nach dem Merge von PR #666 (`format="text"`).

## Ist-Stand (Schritt 1 der Karte, nachgemessen im Code)

- `fetch_playbook` kennt heute `playbook_id`, `locale`, `format` — **kein**
  `block_ids`. Der Vorbefund aus der Elternkarte ist bestaetigt
  (`apps/mcp/src/who2be_mcp/server.py:496`).
- `block_ids` existiert nur auf dem Resource-Pfad
  (`fetch_resource`, `server.py:665`) und schneidet dort `content.blocks`
  clientseitig — das geht, weil eine Resource ihre Bloecke als Liste
  ausliefert.
- Fuer Playbooks liegt die Prozedur als **flacher Plain-Text** in
  `body_rendered` (`GET .../playbooks/{id}/rendered`), erzeugt vom
  Placeholder-Renderer. Ein flacher String hat keine Anker — clientseitiges
  Schneiden im MCP-Prozess ist damit nicht moeglich.
  => Die Granularitaet muss **serverseitig** entstehen, dort wo der Body noch
  BlockNote-JSON ist.
- Auffindbarkeit (Schritt 2): weder `list_playbooks` noch `list_triggers`
  liefern eine Gliederung. Der Fund der Karte trifft zu — die Blockstruktur
  ist heute nur ueber einen Vollabruf sichtbar.

## Entscheidung

Die Section-Semantik des Resource-Pfades (ADR-0021, Heading-Only-Anker) auf
Playbooks uebertragen — dieselbe Regel, dieselbe Anker-Form:

1. `PlaybookService.render(ctx, id, block_ids=None)` schneidet den
   BlockNote-Body **vor** dem Rendern auf die gewaehlten Sections und liefert
   zusaetzlich immer die Gliederung (`sections`).
   Eine Section = ein Heading-Block + alles bis zum naechsten Heading
   gleicher Ebene (identisch zu `block_section_text`).
2. `GET .../playbooks/{id}/rendered?sections=<csv>` reicht die Auswahl durch.
   Methode/Pfad/operationId bleiben unveraendert => das OpenAPI-Golden bleibt
   unberuehrt.
3. `fetch_playbook(playbook_id, block_ids=[...])` schneidet; `format="outline"`
   liefert **nur** die Gliederung (kein Body, kein Editor-JSON) — damit ist
   die Blockstruktur ohne Vollabruf auffindbar.
4. Werkzeugbeschreibung: selektiver Weg als Regelfall (outline -> block_ids),
   Vollabruf als ausdrueckliche Ausnahme fuer strukturelle Konsumenten.

Modellwahl: `ResourceBlockAnchor` (block_id/level/text) wird wiederverwendet
statt ein zweites, feldgleiches Modell anzulegen — derselbe
Heading-Anker-Vertrag. Caveat im Handoff (Name sagt "Resource").

Additivitaet: ohne `block_ids`/`format` ist der Render-Pfad byte-identisch zu
heute (der Original-Body-String wird unveraendert durchgereicht).

## Dateien (Zuschnitt: hoechstens acht)

1. `apps/api/src/who2be_api/services/playbook_service.py` — Split + render
2. `apps/api/src/who2be_api/routers/playbooks.py` — `?sections=`
3. `apps/mcp/src/who2be_mcp/client.py` — Durchreichung + sections
4. `apps/mcp/src/who2be_mcp/server.py` — `block_ids`, `format="outline"`, Doku
5. `apps/api/tests/test_playbook_service.py` — Split-/Schnitt-Verhalten
6. `apps/mcp/tests/test_resource_tools.py` — Rot-Probe (gemessene Groesse)
7. `changelog.d/…md`

## Verifikation

- Rot-Probe: gemessene serialisierte Antwortgroesse Blockauswahl vs.
  Vollabruf; Mutation der tragenden Stellen muss rot werden.
- `ruff check/format`, `mypy`, volle Suite, Lizenz-Gate (CONTRIBUTING DoD).
