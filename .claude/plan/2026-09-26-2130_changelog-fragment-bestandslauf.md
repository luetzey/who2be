# Changelog-Fragment aus PR #666 auf die Namensform bringen + Bestands-Lauf im CI

Karte: `t_21376d5c` (Reviewer-Fund aus `t_89ffc946`, Runde 2)

## Ziel / Done-Condition

- `uv run python scripts/changelog_fragments.py check` → exit 0 über den
  **Gesamtbestand** von `changelog.d/`.
- Der Fall fällt beim nächsten Mal in der CI auf, nicht erst manuell.
- Zuschnitt: höchstens 3 Dateien.

## Befund (selbst gemessen)

Auf `origin/main` (0bab50b8):

```
$ uv run python scripts/changelog_fragments.py check
Fragmente fehlerhaft:
20260926_183000_fetch_playbook_text_format.md: erwartete Form ist
<slug>.<typ>.md (Typ: added, changed, deprecated, removed, fixed, security)
exit=1
```

Warum die CI das nicht fängt: der Job `changelog-guard`
(`.github/workflows/ci.yml:617`) ruft ausschließlich
`changelog_fragments.py guard --base "$BASE_SHA"`. `guard` urteilt über die
**gegen die Basis geänderten** Dateien. Das Fragment stammt aus PR #666 und
liegt bereits auf `main` — es steht in keinem aktuellen Diff und ist damit für
`guard` strukturell unsichtbar.

## Schritt 1 — Fragment auf die Form bringen

`changelog.d/20260926_183000_fetch_playbook_text_format.md`
→ `changelog.d/fetch-playbook-text-format.added.md`

Beim Nachmessen kam ein **zweiter** Verstoß derselben Datei heraus, den die
Karte nicht kannte: `check` meldete nach dem Rename

```
fetch-playbook-text-format.added.md: muss ein Markdown-Listenpunkt sein und
mit '- ' beginnen (Folgeabsaetze um zwei Leerzeichen eingerueckt)
```

Das Fragment trug den Keep-a-Changelog-Header `### Added` im Body. Der ist im
Verfahren redundant — die Kategorie steckt im Dateinamen, `collect` setzt die
Überschrift selbst — und verletzt die Inhaltsregel aus `changelog.d/README.md`.
Die zwei Header-Zeilen sind deshalb entfernt; der Listenpunkt selbst bleibt
Wort für Wort unverändert (`collect --dry-run` zeigt ihn unter `### Added`).


## Schritt 2 — Design-Weiche: wo läuft der Bestands-Lauf?

Der Bestands-Lauf wird ergänzt — ohne ihn ist die Lücke dieselbe wie heute,
nur einmal weniger besetzt. Offen war nur *wo*:

- **A — eigener Step im Job `changelog-guard`.** Der Job läuft bewusst ohne
  `needs: changes` und ohne `if:` (Begründung steht im Job-Kommentar:
  `CHANGELOG.md` passt auf die Doku-Allowlist des `changes`-Jobs, ein
  CHANGELOG-only-PR bekäme `code=false`). Ein Bestands-Lauf dort läuft also
  bei **jedem** PR, auch bei reinen Doku-PRs — und genau ein reiner Doku-PR
  ist es, der ein Fragment anlegt. Kostet nichts: `uv run --no-project`, das
  Skript braucht nur die Standardbibliothek.
- **B — Step im Job `python`.** Der hängt am `changes`-Gate (`code == true`).
  Ein PR, der nur ein Fragment anlegt, ist Doku → der Job läuft nicht → das
  Gate verfehlt seinen Zielfall nicht gelegentlich, sondern strukturell.
  Derselbe Denkfehler, den der Kommentar an `changelog-guard` bereits für das
  bestehende Gate ausschließt.
- **C — nicht ergänzen, nur umbenennen.** Billigste Variante, lässt die Lücke
  aber offen: ein Fragment mit falschem Namen bleibt bis zum nächsten
  `collect`-Lauf beim Release unentdeckt, und dort stört es am teuersten.

**Gewählt: A.** B verfehlt den Zielfall aus dem schon im Repo dokumentierten
Grund, C beseitigt nur das Symptom.

Eigener Step neben dem `guard`-Step, damit die beiden Aussagen getrennt
bleiben: *geänderte Dateien* (guard) vs. *Bestand* (check). Bei Rot sagt der
Step-Name, welche der beiden Aussagen gebrochen ist.

Der Step braucht keinen PR-Kontext und keinen Base-SHA — `check` liest nur das
Verzeichnis. Er läuft deshalb auch beim Push auf `main`, wo der `guard`-Step
sich bewusst überspringt.

`all-green` bindet `changelog-guard` bereits über `needs` — das neue Gate ist
damit ohne weitere Änderung im Required Check enthalten.

## Betroffene Dateien (3)

1. `changelog.d/20260926_183000_fetch_playbook_text_format.md` → `changelog.d/fetch-playbook-text-format.added.md` (Rename)
2. `.github/workflows/ci.yml` (ein Step im Job `changelog-guard`)
3. diese Plan-Datei

Kein eigenes Changelog-Fragment: reine CI-/Repo-Hygiene ohne Wirkung auf das
Produkt; das umbenannte Fragment trägt seinen Text unverändert weiter.

## Verifikation

```bash
uv run python scripts/changelog_fragments.py check                  # exit 0
uv run python scripts/changelog_fragments.py guard --base origin/main
uv run pytest scripts/tests/test_changelog_fragments.py             # unberührt, grün
python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())"
```
