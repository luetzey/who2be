# MCP-Payload-Budget: Inventar, Obergrenze, Regressionsschutz

Karte `t_89ffc946`. Eltern-Karte `t_4ce1b187` (PR #666) hat den `format="text"`-
Pfad fuer `fetch_playbook` eingefuehrt; diese Karte misst den **Rest** der
Werkzeuge gegen dieselbe Schwelle und haelt das Budget als Regel fest.

## Messmethode

Gemessen wurde die **serialisierte Antwort, wie sie beim Agenten ankommt** —
nicht die REST-Antwort und nicht geschaetzt. Jeder Aufruf lief live gegen den
Produktions-MCP (`mcp.luetzenburg-cloud.de`) mit dem groessten vorhandenen
Objekt je Typ (Persona `Coder`, Playbook `Code-Task-Flow`, Resource
`Dokumentations-Standards` mit 92 Bloecken, Agent `Coder`). Die Zahl ist die
Zeichenlaenge der Tool-Antwort; ueber 50 000 Zeichen legt die Laufzeit die
Antwort in eine Spillover-Datei statt sie dem Modell zu zeigen.

Die Schwelle 50 000 ist keine Who2Be-Einstellung, sondern die Vorgabe der
Laufzeit des Konsumenten. Sie ist damit nicht verhandelbar, sondern eine
Randbedingung.

## Inventar (gemessen 2026-09-26)

| Werkzeug | gemessen | Faktor zur Schwelle | Ursache |
|---|---|---|---|
| `list_playbooks()` | **277 151** | 5,5x ueber | jeder Eintrag traegt `content.body` (BlockNote-JSON) |
| `get_persona("Coder")` | **225 559** | 4,5x ueber | `content.blocks` + `body_rendered` = Profil doppelt |
| `list_versions(persona, Coder)` | **139 925** | 2,8x ueber | 11 Snapshots x vollem Content |
| `fetch_playbook(Code-Task-Flow)` | **64 971** | 1,3x ueber | wird in `t_4ce1b187` behandelt (PR #666) |
| `fetch_agent("Coder")` | **54 912** | 1,1x ueber | Persona-`content` + gerenderter Prompt |
| `list_external_tools()` | ~24 000 | unter | `usage_notes` als BlockNote-String |
| `fetch_resource(92 Bloecke)` | ~22 000 | unter | Bloecke sind der Nutzinhalt |
| `list_triggers()` | ~11 700 | unter | — |
| `search(limit=50)` | ~8 700 | unter | Snippets statt Volltext |
| `list_agents()` | ~1 900 | unter | — |
| `list_resources()` | **786** | unter | **liefert `block_count` statt Bloecke** |

`list_resources` ist der Beleg, dass das Muster loesbar ist: dieselbe Menge
Inhalt, 786 statt 277 151 Zeichen — weil die Uebersicht zaehlt, statt den
Volltext mitzuschleppen.

## Befund

Jedes Werkzeug ueber der Schwelle reisst sie aus **einem** Grund: es liefert
BlockNote-Editor-JSON mit, das denselben Text ein zweites Mal traegt. Der
Nutztext-Anteil liegt bei `get_persona` bei rund 5 % — der Rest ist `props`,
`styles`, `children` und Block-IDs. Kein Werkzeug reisst die Schwelle, weil
es zu viel Inhalt haette.

## Vorgehen

1. **Obergrenze nachziehen** (Datei: `apps/mcp/src/who2be_mcp/server.py`).
   Derselbe additive `format`-Parameter wie in PR #666, gleiche Semantik, auf
   die vier Werkzeuge ueber der Schwelle ausser `fetch_playbook`:
   `get_persona`, `fetch_agent`, `list_playbooks`, `list_versions`.
   `format="full"` bleibt Default — kein bestehender Konsument verliert etwas;
   `format="text"` laesst das Editor-JSON weg.
2. **Dokumentieren** (`docs/mcp-payload-budget.md`): das Budget als Regel, die
   Begruendung (fremde Laufzeiten schneiden ab, ohne zu melden), die
   Messmethode und das Inventar.
3. **Regressionsschutz** (`apps/mcp/tests/test_tool_payload_budget.py`): je
   Werkzeug ein Test, der die **serialisierte Antwortgroesse** gegen die
   Obergrenze prueft — Verhalten, nicht Feldnamen. Rot-Probe: jedes Fixture
   ist so bemessen, dass der `full`-Pfad die Schwelle tatsaechlich reisst;
   tut er das nicht, faellt der Test mit eigener Meldung. Damit kann der Test
   nicht gruen bleiben, wenn der Text-Pfad wegfaellt.

`fetch_playbook` wird **nicht angefasst** (Kollisionsschutz gegen `t_4ce1b187`).

## Zuschnitt

Fuenf Dateien: `server.py`, `test_tool_payload_budget.py`,
`docs/mcp-payload-budget.md`, ein `changelog.d/`-Fragment, diese Plan-Datei.
Grenze der Karte: acht.

## Nicht in dieser Karte

- Den Default auf `"text"` kippen. Waere die wirksamere Loesung, ist aber ein
  Vertragsbruch fuer bestehende Konsumenten und braucht eine eigene
  Entscheidung.
- `list_external_tools` und `fetch_resource` umbauen. Beide liegen unter der
  Schwelle; `list_external_tools` ist mit ~24 000 Zeichen der naechste
  Kandidat, wenn weitere Bindungen dazukommen — im Budget-Dokument als
  Beobachtungsposten vermerkt.
