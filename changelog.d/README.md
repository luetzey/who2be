# Changelog-Fragmente

Dieses Verzeichnis ersetzt das direkte Schreiben in `CHANGELOG.md`.

**Warum:** `CHANGELOG.md` ist eine Sammeldatei — jeder PR schreibt an dieselbe
Stelle, und git merged dort messbar oft still falsch, ohne Konfliktmarker. In
einer Welle dieses Repos stand danach ein Warnabsatz doppelt im CHANGELOG.
Legt jeder PR stattdessen eine **eigene** Datei an, kann der Konflikt
strukturell nicht entstehen.

## Ein Fragment anlegen

Dateiname: `<slug>.<typ>.md`

- `<slug>` — frei wählbar, sinnvoll ist der Branch- oder PR-Bezug
  (`oauth-issuer`, `pr-560`). Er taucht im CHANGELOG nicht auf; er sorgt nur
  dafür, dass zwei PRs verschiedene Dateien anlegen.
- `<typ>` — eine Kategorie aus [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
  `added`, `changed`, `deprecated`, `removed`, `fixed`, `security`.

Inhalt: der Markdown-Listenpunkt, genau so wie er im CHANGELOG stehen soll —
mit führendem `- `, Folgeabsätze um zwei Leerzeichen eingerückt.

```markdown
- Der OAuth-Issuer trägt jetzt die URL-Normalform mit Schrägstrich.

  Clients parsen den Metadatenwert in einen URL-Typ, bevor sie vergleichen;
  jeder Parser normalisiert einen Origin ohne Pfad zu `https://host/`.
```

## Kommandos

```bash
uv run python scripts/changelog_fragments.py check                # Form prüfen
uv run python scripts/changelog_fragments.py collect --dry-run    # Vorschau
uv run python scripts/changelog_fragments.py collect              # übernehmen
```

`collect` trägt die Fragmente in die `## [Unreleased]`-Sektion ein und löscht
sie — das passiert **beim Release**, nicht in jedem PR.

Ausführliche Begründung inklusive der Abwägung gegen towncrier und gegen
`merge=union`: siehe Modul-Docstring in `scripts/changelog_fragments.py`.
