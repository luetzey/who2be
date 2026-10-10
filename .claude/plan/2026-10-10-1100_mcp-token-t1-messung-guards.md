# MCP-Token T1: Messung und Guards je Referenzprofil

Karte t_09c2de21. Quelle: `/home/luetzey/recherche/who2be-mcp-token-optimierung-2026-10.md` §4 (T1), §5 (M2).

## Outcome

`tools/list` hat eine reproduzierbare Kennzahl je Referenzprofil, drei Guards
gegen Katalog-Wachstum am falschen Ort und eine Top-10-Tabelle in
`docs/mcp-payload-budget.md`. Zielwerte je Profil (T4a) kommen erst in T3.

## Schritte

1. `who2be_mcp/payload_report.py` (neu): Draht-Liste von `tools/list` über den
   In-Memory-Client, Profil-Filter über `is_tool_visible_for` (dieselbe Quelle
   wie die Middleware), Helfer erster Satz und Entwickler-Verweise, `main()`
   druckt die Tabellen (`uv run python -m who2be_mcp.payload_report`).
2. Tests in `test_tool_payload_budget.py`:
   - (a) Profile: Default, Default+Gedächtnis, Builder, Editor. Kennzahl,
     Ordnung, Gegenprobe gegen die echte Middleware (Default-Profil).
   - (b) Beschreibung ≤ 2 048 Zeichen, alle Werkzeuge.
   - (c) erster Satz ≤ 100 Zeichen, alle Werkzeuge.
   - (d) Entwickler-Verweise (ADR/Phase/Track/Welle/WP/Gap) im `inputSchema`:
     Ratsche mit dem heutigen Bestand je Werkzeug, T2 leert sie.
3. Bestand anpassen, damit (b)/(c) grün sind: `get_persona` < 2 048,
   erster Satz `update_external_tool` und `list_artifacts`.
4. Doku: Profil-Tabelle, Top-10, Guards, Ratsche.
5. Changelog-Fragment.

## Verifikation

ruff check/format, mypy, `pytest apps/mcp/tests`, changelog check.
