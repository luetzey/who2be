# Zeitzonen-Flake: test_placeholder_preview vergleicht UTC-Endpunkt gegen date.today()

Kanban: `t_09f7eb4a` · Branch: `who2be/t_09f7eb4a-zeitzonen-flake-test_placeholder_preview`
Basis: `69bfeda6`

## Befund (gemessen, nicht vermutet)

Der Endpunkt rechnet in UTC, und zwar durchgaengig:

- `apps/api/src/who2be_api/services/placeholder_preview_service.py:70` —
  `RenderContext(now=datetime.now(UTC))`.
- `apps/api/src/who2be_api/services/placeholders/resolvers/date.py:47-58` —
  formatiert genau dieses `ctx.now`, kein eigener Zeitbegriff.
- Dieselbe UTC-Wahl in allen weiteren `RenderContext`-Erzeugern:
  `persona_service.py:314`, `playbook_service.py:188`,
  `agent_render_service.py:103`, `agent_fetch_rendered_service.py:135`,
  `entity_export_service.py:154`.

Der Test vergleicht dagegen gegen Ortszeit:

- `apps/api/tests/test_placeholder_preview.py:85` — `date.today().isoformat()`
- `apps/api/tests/test_placeholder_preview.py:91` — `date.today().year`

Zwischen 0:00 und 2:00 Ortszeit (CEST) ist in UTC noch der Vortag — die
Assertion in Zeile 85 ist in diesem Fenster strukturell rot.

## Keine Design-Weiche (Aufgabe 4 geprueft, nicht uebergangen)

Die Frage "soll die Platzhalter-Aufloesung fachlich in Ortszeit rechnen?" ist
durch das Repo belegt beantwortet, nicht durch Urteil:

- Es gibt im ganzen Repo keinen Ortszeit-Zeitbegriff. `grep` nach
  `date.today|localtime|astimezone|datetime.now()` (ohne tz) findet
  **ausschliesslich** die zwei Testzeilen oben — jede andere Zeitnahme in
  `apps/` und `packages/` ist explizit `datetime.now(UTC)`.
- Die Unit-Tests des Resolvers legen UTC schon als Vertrag fest:
  `test_placeholder_renderer.py:1225ff` speist `datetime(..., tzinfo=UTC)`.
- Der Renderer stempelt sichtbar in UTC: `wa_render.py:103`
  (`"%Y-%m-%d %H:%M UTC"`).
- Eine nutzerbezogene Zeitzone einzufuehren ist durch das Out-of-Scope der
  Karte ausdruecklich ausgeschlossen.

=> Der Endpunkt bleibt bei UTC (serverseitig korrekt). Der Test wird
korrigiert, nicht die Produktion. Kein `needs_input`.

## Muster-Entscheidung

Keine Muster-Entscheidung noetig — Ein-Datei-Testfix plus eine Lint-Regel, keine
neue Struktur. Insbesondere KEIN eingefuehrter Zeit-Port/Clock-Abstraktion: die
Variabilitaets-Schwelle ist nicht erreicht (ein einziger Zeitbegriff, UTC).

## Arbeitspakete

1. **Test auf UTC ziehen** (`apps/api/tests/test_placeholder_preview.py`)
   `date.today()` -> `datetime.now(UTC).date()`, damit Test und Endpunkt
   denselben Zeitbegriff verwenden. Import `date` entfaellt.

2. **Fix an der Klasse, nicht an der Zeile** (`pyproject.toml`)
   `DTZ` (flake8-datetimez) in `[tool.ruff.lint] select` aufnehmen. Messung
   vorher: `uv run ruff check --select DTZ .` findet repo-weit **genau die zwei
   Zeilen aus Paket 1** und sonst nichts — die Regel ist damit ab sofort
   kostenlos scharf und verhindert den Rueckfall, statt ihn beim naechsten
   Nachtlauf erneut zu entdecken.

## Verifikation (Rotprobe, beide Zeitzonen)

```bash
TZ=Europe/Berlin uv run pytest apps/api/tests/test_placeholder_preview.py
TZ=UTC           uv run pytest apps/api/tests/test_placeholder_preview.py
# Gegenprobe, dass die Assertion ueberhaupt greift: Nachtfenster simulieren
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest --cov --cov-fail-under=85
```

Web-Stack unberuehrt (kein `apps/web/`-Diff) — die Web-DoD-Kommandos entfallen
begruendet.

## Ausgefuehrt / Ergebnis

### Diff (2 Dateien, +16/-5)

- `apps/api/tests/test_placeholder_preview.py:85,91` — `date.today()` ->
  `datetime.now(UTC).date()` bzw. `.year`; Import `date` entfaellt. Kommentar
  benennt die Ursache, damit der naechste Leser nicht dieselbe Nacht braucht.
- `pyproject.toml:60ff` — `DTZ` in `[tool.ruff.lint] select`.

Kein Produktionscode angefasst. Kein `apps/web/`-Diff.

### Rotprobe (Aufgabe 3 — vier Laeufe, nicht behauptet)

Voraussetzung: der Test skippt ohne DB (`_db_reachable()`), ein Skip haette also
nichts bewiesen. Ich habe dafuer eine **eigene** pgvector-DB hochgezogen
(`podman`, Port 55443) — der bereits laufende Fremd-Stack `who2be-ndtest`
wurde nicht angefasst.

| TZ | lokal / UTC | Ergebnis |
|---|---|---|
| `Europe/Berlin` | 2026-09-26 13:07 / 11:07 | 1 passed |
| `UTC` | 11:07 / 11:07 | 1 passed |
| `Pacific/Kiritimati` (+14) | **2026-09-27** 01:07 / 2026-09-26 11:07 | 1 passed |
| `Pacific/Midway` (-11) | 2026-09-26 00:07 / 11:07 | 1 passed |

Kiritimati und Midway liegen bewusst dabei: dort besteht der Tagesversatz
*rund um die Uhr*, waehrend `Europe/Berlin` ihn nur zwischen 0:00 und 2:00
zeigt — ein Mittagslauf unter CEST ist kein Beweis.

**Gegenprobe, dass die Assertion ueberhaupt greift** (sonst waere ein gruener
Test nur Tautologie): die alte Fassung per `git stash` zurueckgeholt und unter
`TZ=Pacific/Kiritimati` gefahren — reproduziert exakt den Originalfehler der
Karte:

    E  AssertionError: assert '2026-09-26' == '2026-09-27'
       apps/api/tests/test_placeholder_preview.py:85

Danach `git stash pop` + `diff -q` gegen eine Kopie: Fix-Fassung bit-identisch
wiederhergestellt.

### Fix an der Klasse (Aufgabe 2)

`grep` allein haette nur gesucht, nicht abgesichert. Stattdessen `ruff --select DTZ`
als Messung eingesetzt: die Regel findet repo-weit **genau die zwei Zeilen dieses
Bugs** und sonst nichts — jede andere Zeitnahme in `apps/` und `packages/` ist
bereits explizit `datetime.now(UTC)`. Damit ist `DTZ` kostenlos scharf
schaltbar; nach dem Fix laeuft `uv run ruff check .` sauber durch. Der Rueckfall
scheitert ab jetzt lokal am Linter, statt in einem Nachtlauf aufzutauchen.

### Betroffene Software-Elemente

Nur Test- und Konfigebene, kein Produktivsymbol geaendert — die dreiklassige
Aufrufer-Analyse entfaellt begruendet. `DTZ` wirkt auf alle 750 Python-Dateien;
das ist mit `ruff check .` (grün) vollstaendig geprueft, nicht abgeschaetzt.

### Rest-Test-Liste

Keine. Verhaltensneutral: keine geaenderte oder neue Produktivfunktion, damit
keine ungedeckte. Der geaenderte Test deckt sich selbst ab; Coverage 91.52 %
(Gate 85 %).

### Definition of Done (`CONTRIBUTING.md` §DoD)

    uv run ruff check .                         All checks passed!
    uv run ruff format --check .                750 files already formatted
    uv run mypy .                               Success: no issues in 464 source files
    uv run pytest --cov --cov-fail-under=85     1903 passed, 91.52% (TZ=Europe/Berlin)
                                                1903 passed, 91.52% (TZ=UTC)
    piplicenses --fail-on "GPL;AGPL;..."        Exit 0

Web-Stack ohne Diff — die `apps/web/`-Kommandos entfallen begruendet.

### Aufraeumen

Die Test-DB `w2b-tz-t09f7eb4a` (podman) wird nach dem Lauf entfernt; sie ist
reines Verifikations-Werkzeug und nicht Teil des Diffs.

