# MCP-Token T4: Server-instructions und alwaysLoad für Boot-Werkzeuge

Karte t_180a98ab. Quelle: `/home/luetzey/recherche/who2be-mcp-token-optimierung-2026-10.md`
§3 Option B(1)(2), §4 (T4). Owner-Entscheidung T4a (2026-10-09).

## Outcome

Fertig heißt: Der Server liefert `instructions` (Boot-Reihenfolge und
Querschnittsregeln, ≤ 2 048 Zeichen, nur existierende Werkzeugnamen). Genau
fünf Boot-Werkzeuge (`whoami`, `get_persona`, `search`, `search_memory`,
`record_usage`) tragen `_meta["anthropic/alwaysLoad"] = true`. Die Reihenfolge
von `tools/list` ist über Prozesse mit verschiedenem Hash-Seed gleich, und der
Policy-Filter erhält sie. Die Wirkung ist mit `payload_report` gemessen und in
`docs/mcp-payload-budget.md` festgehalten.

## Out of Scope

- Text- und Schema-Diät (T2, T3): Beschreibungen werden nicht gekürzt, auch
  wenn `instructions` Regeln jetzt einmal zentral nennt.
- Rollen-Toolsets (T6) und `ttlMs`/`cacheScope`-Cache-Hinweise.

## Schritte

1. `who2be_mcp/instructions.py` (neu): `SERVER_INSTRUCTIONS`,
   `ALWAYS_LOAD_TOOLS`, `ALWAYS_LOAD_META`. Kein Import aus `server.py`, damit
   die Datei ohne Werkzeug-Registrierung lesbar bleibt.
2. `server.py`: `FastMCP("who2be", instructions=...)`; `meta=ALWAYS_LOAD_META`
   an den fünf Decorators.
3. `payload_report.py`: Spalte „sofort geladen“ je Profil (Bytes der
   alwaysLoad-Werkzeuge, die das Profil sieht) plus Zeile mit der Länge der
   `instructions`.
4. Tests (`test_tool_payload_budget.py`): instructions kommen über den Client
   an, ≤ 2 048 Zeichen, jeder genannte Werkzeugname existiert (Rot-Probe mit
   erfundenem Namen); alwaysLoad genau auf der Menge, 3–5 Werkzeuge, alle in
   den instructions genannt; Reihenfolge stabil unter zwei Hash-Seeds
   (Subprozess) und vom Filter erhalten.
5. Doku `docs/mcp-payload-budget.md` (Abschnitt „Start bei Tool Search“) und
   `docs/mcp-claude-code.md` falls dort Startverhalten beschrieben ist;
   Changelog-Fragment.

## Verifikation

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
uv run pytest apps/mcp/tests --cov ... (DoD-Kommando aus CONTRIBUTING.md)
uv run python -m who2be_mcp.payload_report   # vorher/nachher
```

Fotos: entfällt, keine sichtbare UI-Änderung.
