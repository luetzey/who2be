# Plan: Tabellen-UI + WorkArea-Exporte

**Datum:** 2026-08-19 · **Branch:** `feat/workarea-tables-ui-exporte` · **Status:** umgesetzt

## Context

User-Auftrag: die dokumentierte Asymmetrie „Artifacts sind sichtbar, Tabellen
nicht" (STATE §Bekannte Probleme, gefunden 2026-08-17) schließen — Tabellen
sichtbar machen — UND Datei-Exporte für Tabellen und Notizen ergänzen, damit
ein Mensch Ergebnisse aus der WorkArea ohne MCP/API in der Hand hat.

Zwei bindende User-Entscheidungen vorab: CSV **und** echtes `.xlsx`
(openpyxl genehmigt, kein reines CSV-mit-Excel-Endung); PDF über
Browser-Druck (`window.print`) statt serverseitigem PDF-Rendering — keine
schwere Dependency (weasyprint o. ä.) für ein Format, das der Browser des
Menschen bereits beherrscht.

## Wellen

**B1 — Store-Lesepfad.** `TableStore.read_table_rows` (`tablestore/engine.py`):
SQL-Bau im Store (ARC-3), explizite quotierte Katalog-Spalten statt
`SELECT *` — interne Store-Spalten (`_dedupe_hash`, `_source_artifact`)
bleiben draußen. Läuft über denselben ro-Pfad wie freies Agenten-SQL, erbt
Zeitbudget/Zell-/Result-Grenzen. Neuer `EXPORT_ROW_LIMIT = 10_000`
(deutlich über dem UI-Preview-Limit 1000 — ein Export soll die Tabelle
abbilden, nicht nur ihren Anfang).

**B2 — Renderer.** `services/wa_render.py`: `render_table_xlsx` (openpyxl,
in-memory-Workbook, Formel-Guard über dieselbe `csv_cell`/
`CSV_FORMULA_PREFIXES`-Quelle wie CSV — keine zweite Definition der
Entschärfung), `render_artifact_export_markdown` (YAML-Frontmatter, nicht
gesetzte Felder ausgelassen statt leer), `render_artifact_export_html`
(MarkdownIt wörtlich wie `agent_render_service`: `html: False`, escapet
rohes HTML aus Ingest-Material).

**B3 — Web-API-Schicht.** Typen (`TableExportFormat` etc.), Client-Methoden
mit `requestBlob`, `downloadFile`-Helper, Contract-Test gegen das
regenerierte OpenAPI-Golden.

**B4 — Endpoints + Golden + Security-Review.**
`GET /wa-tables/{id}/export?format=csv|xlsx`,
`GET /wa-artifacts/{id}/export?format=markdown|html` — Muster
`routers/_export.py` (ADR-0032): `attachment`, `response_model=None`, Lesen
für Viewer offen, `write_limit` als Rate-Limit. 5 Findings im Review, alle
behoben (Tests je Finding):
- **M-1** XLSX-Rendering blockierte den Event-Loop (~2 s beim vollen
  Result-Budget) → `asyncio.to_thread` + `write_limit` auf beiden Routen.
- **M-2** XML-illegale Steuerzeichen (openpyxl `IllegalCharacterError`) →
  Schreibpfad lehnt mit 422 ab (`_validate_cell_text`), Renderer strippt
  zusätzlich für Bestandsdaten.
- **M-3** Frontmatter-Injection über `source_system`/`source_url` →
  `_yaml_scalar` schickt jeden Wert durch `single_line`.
- **L-1** Meta-CSP (`default-src 'none'`) + `no-referrer` im HTML-Export —
  ohne sie liefen Tracking-Pixel aus Fremdquellen beim Öffnen aus `file://`,
  wo die Caddy-CSP der API nicht gilt.
- **L-2** Formel-Guard prüfte nur das erste Zeichen; Google Sheets trimmt
  beim CSV-Import führenden Whitespace vor der Auswertung. Geprüft wird jetzt
  auf einer getrimmten Kopie, präfixiert der Originalwert; `\n` ergänzt die
  Präfix-Liste.

Details und die Einordnung als sanktionierte Ausnahme von der
Rohtext-Regel der Web-UI: ADR-0047-Nachtrag 2026-08-19.

**B5 — Tabellen-UI.** Tabellen-Tab in der Area-Detailseite, in BEIDEN
Zweigen — private Agent-Areas hatten bislang gar keine Tabs, sind aber
gerade der Ort, an dem Tabellen entstehen. Katalog-Liste ohne Anlege-Button
(Tabellen legen Agenten über MCP an) und ohne `row_count` (Katalog-Pfad
liefert `null`, kein N+1 auf `describe`). Neue `TableDetailPage`
(`.../areas/{areaId}/tables/{tableId}`): Schema, Zeilenzahl, Konventionen,
Daten-Vorschau (neueste 50 Zeilen über den Query-Endpoint, explizite
quotierte Katalog-Spalten) und Export-Dropdown CSV/Excel via Blob-Download.
Hooks `useWaTables`/`useWaTable` mit getrennten Fehlerkanälen für
Schema/Konventionen vs. Vorschau — eine abgelehnte Query reißt die
Schema-Anzeige nicht mit.

**B6 — Notizen-Export.** Export-Aktionen in der ArtifactDetailPage:
Markdown-/HTML-Download über die neuen Endpoints plus „Als PDF drucken" über
`window.print` mit eigenem Print-Stylesheet (User-Entscheidung: kein
Server-PDF).

## Verifikation

Python: **1698 Tests grün**, Coverage-Gate erfüllt (`--cov-fail-under=85`).
Web: **986 Tests grün** (davon 13 neu, inkl. a11y-Durchläufe je Tab),
Coverage 86,3/80,3/82,5/87,2 (Floors 80/79/75/80); `tsc`/Lint/Build grün.

DoD-Verweise: STATE.md „Tabellen-UI + WorkArea-Exporte (2026-08-19)";
ADR-0047-Nachtrag 2026-08-19; DECISIONS.md 2026-08-19 „WorkArea-Exporte:
Formate, Grenzen, Auslieferung".
