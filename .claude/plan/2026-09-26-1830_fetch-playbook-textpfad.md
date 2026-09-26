# fetch_playbook: Text-Pfad ohne Editor-JSON (additiv)

Karte: `t_4ce1b187` · Branch: `who2be/t_4ce1b187-mcp-fetch_playbook-liefert-gerenderten-t`

## 1. Ist-Stand — gemessen, nicht angenommen

Messung gegen den Live-Endpunkt fuer `Code-Task-Flow`
(`e1258818-23c2-42ef-b794-422bb5adb7da`), Aufschluesselung der
`fetch_playbook`-Antwort (Zeichen des serialisierten `result`-Strings):

| Feld | Zeichen |
|---|---:|
| **gesamt** | **61 293** |
| `playbook` | 36 608 |
| ├ `playbook.content.body` (BlockNote-JSON) | **35 355** |
| ├ `playbook.content.description` | 440 |
| ├ `playbook.content.triggers` / `tags` / `type` | 136 |
| `body_rendered` (Prozedurtext) | 24 622 |
| `linked_blocks` / `linked_resources` / `composed_playbooks` / `locale` | 10 |

Entscheidender Befund, der die Annahme der Karte korrigiert:

**`body_rendered` existiert bereits und wird bereits ausgeliefert.**
`server.py:540` ruft `client.get_playbook_rendered(parsed)`, der API-Endpunkt
`GET .../playbooks/{id}/rendered` liefert ihn
(`playbook_service.py:198`, `PlaybookRenderResponse`). Der Playbook-Pfad
folgt dem Persona-/Resource-Muster also schon.

Der Ballast ist ein anderer: **`playbook.content.body` — 35 355 Zeichen
escaped BlockNote-Editor-JSON — wird zusaetzlich mitgeliefert.** Es ist
dieselbe Prozedur ein zweites Mal, nur in Editor-Form. 35 355 von 61 293
Zeichen sind 57,7 % reine Dopplung.

Rechnung: 61 293 − 35 355 = **25 938 Zeichen** — unter dem
Ergebnisbudget der Laufzeit (50 000).

## 2. Aenderung — additiv, ein Schnitt

Neuer Parameter am MCP-Tool:

```python
async def fetch_playbook(
    playbook_id: str,
    locale: str | None = None,
    format: Literal["full", "text"] = "full",
) -> PlaybookWithResources
```

- `format="full"` (**Default, unveraendert**): Antwort wie bisher, inklusive
  `content.body`. Kein bestehender Konsument sieht eine Aenderung.
- `format="text"`: `playbook.content.body` wird im Antwort-Objekt geleert.
  `body_rendered` traegt den Prozedurtext; alle uebrigen Felder
  (Metadaten, Links, Composites, Tags, Triggers) bleiben vollstaendig.

**Warum nur am MCP-Tool und nicht an der REST-API:** Der Who2Be-Editor liest
die REST-Route `GET .../playbooks/{id}` direkt und braucht das BlockNote-JSON
zum Rendern. Der Parameter sitzt ausschliesslich im MCP-Tool-Zuschnitt — die
REST-Antwort bleibt Byte fuer Byte identisch, also kann kein struktureller
Konsument Struktur verlieren. Das ist zugleich der kleinste Schnitt.

## 3. Rot-Probe

Ein Verhaltens-Test, kein Feldnamen-Test: Ein gemocktes Playbook mit
realistisch grossem BlockNote-Body wird ueber beide Pfade geholt, die
**serialisierte Antwort** wird gemessen.

- `format="text"` haelt eine Obergrenze und traegt den Prozedurtext.
- `format="full"` liegt nachweislich darueber (Regressionsanker: der Default
  hat sich nicht still mitgeaendert).

Ohne die Aenderung schlaegt der Test fehl, weil der Text-Pfad dann dieselbe
Payload liefert wie der Default und die Obergrenze reisst.

## 4. Dateien (Zuschnitt: hoechstens acht)

1. `.claude/plan/2026-09-26-1830_fetch-playbook-textpfad.md` (dieser Plan)
2. `apps/mcp/src/who2be_mcp/server.py`
3. `apps/mcp/tests/test_resource_tools.py`
4. `changelog.d/<fragment>.md`

## 5. Verifikation

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest --cov --cov-fail-under=85
```

## 6. Ausdruecklich nicht in dieser Karte

Kein `applied`-Umbau, kein Katalog-Kuerzen, keine Persona-Aenderung, keine
anderen MCP-Werkzeuge. Der Default bleibt `full`, damit die Wirkung dieser
einen Aenderung isoliert messbar bleibt.
