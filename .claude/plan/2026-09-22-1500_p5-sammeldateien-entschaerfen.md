# P5: Sammeldateien entschaerfen — Fragment-Muster fuer CHANGELOG, Paritaets-Pruefung fuer i18n

Karte: kanban `t_25a1e9f2` · Branch `who2be/t_25a1e9f2-p5-sammeldateien-entschaerfen-fragment-m`
Grundlage: `/home/luetzey/recherche/workflow-idee-code-review-2026-09-22.md`, Abschnitt P5 + Quellen [10][13][20][26][17][12]

## Problem

Drei Dateien wurden in dieser Welle **ohne Konfliktmarker** inhaltlich falsch
gemerged: doppelter Warnabsatz in `CHANGELOG.md`, konkurrierende Schluessel
(`auth.signup.captcha` neben `auth.captcha`) in `de.json`/`en.json`. Gefunden
wurde das nur durch einen Cherry-pick-Gegencheck der Baum-Identitaet.

Gits eigene Grundrate stiller Fehl-Merges liegt bei 3 % (ASE 2024, 6045
Szenarien, GEMESSEN [20]). Bei drei Auflaesungsrunden ueber 18/9/1 Dateien ist
das kein Pech, sondern die Erwartung.

## Entscheidung 1 — eigenes Skript statt towncrier (AC 1)

**Gewaehlt: ein eigenes Python-Skript `scripts/changelog_fragments.py`.**
Begruendung, gegen towncrier abgewogen:

1. **Das Repo ist zweisprachig.** Ein reiner `apps/web`-Beitrag ist ein
   TS-Beitrag; towncrier ist ein Python-Packaging-Werkzeug und wuerde als
   Python-Dependency in `pyproject.toml` landen, obwohl der CHANGELOG beide
   Staecke beschreibt. Das *Anlegen* eines Fragments ist in beiden Varianten
   werkzeugfrei (Datei anlegen) — nur das Zusammenfuehren braucht eine
   Laufzeit, und die ist mit `uv run` ohnehin da. Eine zusaetzliche
   Dependency kauft dafuer nichts.
2. **AC 3 verlangt, dass der bestehende CHANGELOG unveraendert bleibt.**
   towncrier baut den CHANGELOG aus einem eigenen Template an einem
   Marker-Kommentar neu auf und kennt die `## [Unreleased]`-Struktur von
   *Keep a Changelog* mit ihren `### Fixed`/`### Security`-Unterabschnitten
   nicht. Unsere Eintraege sind mehrabsaetzige Fliesstexte mit Einrueckung —
   genau das, was ein generierendes Werkzeug umformatiert.
3. **Der Zusammenbau ist trivial.** ~150 Zeilen, vollstaendig getestet, keine
   Konfiguration, keine Template-Sprache, kein Versions-Pin, der veraltet.

Das eigentliche, belegte Gegenmittel ist ohnehin nicht das Werkzeug, sondern
das *Muster*: „Rather than […] having one single file which developers all
write to and produce merge conflicts, towncrier reads 'news fragments'" [26].
Zwei PRs schreiben nie dieselbe Datei — der Konflikt kann strukturell nicht
entstehen. Das Muster uebernehmen wir, das Werkzeug nicht.

**Ausdruecklich NICHT gewaehlt: `merge=union`.** Die git-Doku warnt selbst
(„Do not use this if you do not understand the implications." [10]), und der
scikit-learn-Verlauf ist exakt unser doppelter Warnabsatz [13]. Es tauscht
einen sichtbaren Konflikt gegen einen stillen Fehler.

### Form

- Verzeichnis `changelog.d/` im Repo-Root.
- Fragment: `<slug>.<typ>.md`, Typ aus *Keep a Changelog*
  (`added|changed|deprecated|removed|fixed|security`).
- Inhalt: der Markdown-Listenpunkt, so wie er im CHANGELOG stehen soll.
- `uv run python scripts/changelog_fragments.py check` — Namens-/Typ-Pruefung.
- `uv run python scripts/changelog_fragments.py collect` — fuehrt die
  Fragmente in die `## [Unreleased]`-Sektion ein (in die vorhandenen
  `### Typ`-Unterabschnitte, fehlende werden in kanonischer Reihenfolge
  angelegt) und loescht sie. `--dry-run` zeigt das Ergebnis nur an.
- Tests: `scripts/tests/test_changelog_fragments.py`, neu in `testpaths`.

## Entscheidung 2 — Paritaets-/Waisen-Pruefung fuer i18n (AC 4)

Fuer Sprachschluesseldateien gibt es laut Recherche **kein** etabliertes
Fragment-Aequivalent („Kein etabliertes Muster fuer i18n-Konflikte") — also
eine Pruefung statt einer Umstrukturierung. `localeParity.test.ts` deckt heute
nur `common.errors` ab; der Captcha-Fall lag ausserhalb.

- `apps/web/src/i18n/audit.ts` — drei Pruefungen:
  1. **Schluesselgleichheit** ueber *alle* Namespaces (beide Richtungen).
  2. **Doppelte Schluessel im Rohtext** — `JSON.parse` verschluckt sie still,
     deshalb ein eigener Tokenizer ueber den Dateiinhalt.
  3. **Verwaiste Schluessel** — im Code nicht referenziert. Statische
     `t('…')`-Aufrufe und `…Key: '…'`-Literale werden exakt aufgeloest,
     dynamische Template-Literale (`` t(`common:status.${s}`) ``) als
     Praefix, unter dem alle Schluessel als benutzt gelten.
- `apps/web/src/i18n/audit.test.ts` — Fixture-Tests inkl. **Nachstellung des
  Captcha-Fehlerfalls** (AC 4: „belege das").
- CLI `apps/web/scripts/check-i18n.ts` + npm-Script `i18n:check`
  (via `vite-node`, bereits devDependency).
- Laeuft ueber den Vitest-Lauf automatisch in CI mit — kein Eingriff in
  `ci.yml` (dort arbeitet parallel P3a/P4).

## Entscheidung 3 — DoD-Ergaenzung (AC 5)

`CONTRIBUTING.md`, Abschnitt *Definition of Done*: nach **jeder**
Konfliktaufloesung wird der Nettodiff gelesen. Das Ausbleiben von
Konfliktmarkern ist kein Beleg. Genannt wird der Cherry-pick-Vergleich der
Baum-Identitaet als das Verfahren, das die drei Fehler tatsaechlich gefunden
hat, plus `git merge-tree` als mechanische Gegenprobe (Exit 0/1 [12]).

**Bewusste Mitnahme:** `CONTRIBUTING.md:79` dokumentiert `npx tsc --noEmit`
(prueft im Projekt-Referenz-Setup null Dateien); korrekt ist `npx tsc -b`, wie
`ci.yml` es auch faehrt. Die Zeile steht im selben DoD-Block, den diese Karte
ergaenzt — sie hier stehen zu lassen waere das Dokumentieren eines bekannten
Fehlers. PR #549 zieht dieselbe Korrektur fuer `CLAUDE.md:152/:234` nach;
`CLAUDE.md` wird hier deshalb **nicht** angefasst.

## Out of Scope

`merge=union`; bestehende CHANGELOG-Eintraege umbauen; i18n-Struktur aendern;
Uebersetzungen ergaenzen; `ci.yml` anfassen.

## Unterwegs dazugekommen (nicht im Ursprungsplan)

**Waisen-Baseline (`apps/web/src/i18n/orphan-baseline.json`).** Die
Waisen-Pruefung meldete am echten Baum 174 Schluessel, auf die kein Code
verweist — nach drei Runden Nachschaerfen der Erkennung (Plural-Suffixe,
dynamische Praefixe ab innerer Punkt-Grenze, Schluessel als Record-Werte) und
stichprobenweiser Gegenpruefung von Hand ist das belegter Altbestand, kein
Erkennungsfehler. Ihn aufzuraeumen ist out of scope ("Die i18n-Struktur
aendern"), das Gate ohne Baseline waere dauerhaft rot. Deshalb ein Ratchet wie
beim Coverage-Floor: der Test bricht nur bei **neuen** Waisen, und ein zweiter
Test verhindert, dass die Baseline unbemerkt Altlasten behaelt, die laengst
wieder angebunden sind.

**`mypy_path` um `scripts` ergaenzt.** Ohne den Eintrag findet mypy das
Werkzeug-Modul nicht, obwohl pytest es importieren kann.

**`CONTRIBUTING.md:79` `npx tsc --noEmit` -> `npx tsc -b`** (siehe
Entscheidung 3).

## Verifikation (lokal gefahren, 2026-09-22)

Python (Repo-Root):
- `uv run ruff check .` — All checks passed
- `uv run ruff format --check .` — 754 files already formatted
- `uv run mypy .` — Success: no issues found in 466 source files
- `uv run pytest --cov --cov-fail-under=85` — **1443 passed, 485 skipped**,
  0 failed. Coverage 63.4 % < 85 %: die 485 Skips sind der bekannte
  Ohne-DB-Zustand (`conftest.py`, ADR-0041), den Karte P4 adressiert. Der
  Floor ist lokal ohne DB nicht erreichbar und nicht von dieser Karte
  verursacht — die 25 neuen Tests in `scripts/tests/` laufen alle durch.
- OSS-Lizenz-Gate — Exit 0

Web (`apps/web/`, Node 22.23.2 gemaess `.nvmrc`; unter dem lokal aktiven
Node 26 fallen 135 Tests an fehlendem `window.localStorage` aus — reine
Toolchain-Abweichung, nicht Code):
- `npm run lint` — 0 errors (66 vorbestehende warnings)
- `npx tsc -b` — Exit 0
- `npm run test:coverage` — **1180 passed / 195 Dateien, 0 failed**;
  Coverage 87.09 / 81.68 / 82.69 / 88.11 gegen Floors 80 / 79 / 75 / 80
- `npm run test:a11y` — 55 passed
- `npm run build` — Exit 0
- `npm run license:check` — Exit 0
- `npm run i18n:check` — alle Pruefungen gruen

**Beleg zu AC 4 (Fehlerfall nachgestellt).** Der Captcha-Schluessel wurde in
die **echten** Locale-Dateien eingespielt und das CLI darueber gefahren:

- Fall A (`auth.captcha` nur in `de.json`): Paritaets-Pruefung **und**
  Waisen-Pruefung schlagen an, Exit 1.
- Fall B (`auth.captcha` in **beiden** Dateien — die Form aus der Welle):
  Paritaet gruen, Duplikat-Pruefung gruen, **Waisen-Pruefung meldet
  `auth.captcha` in beiden Locales**, Exit 1.
- Beide Nachstellungen anschliessend per `git checkout --` zurueckgenommen;
  dieselbe Konstellation steht dauerhaft als Fixture-Test in
  `audit.test.ts` (`describe('Nachstellung des Fehlmerges aus dieser Welle')`),
  inklusive zweier Tests, die festhalten, dass Paritaet und Duplikat-Pruefung
  ihn allein **nicht** faengen.

**Beleg zu AC 3.** `git diff --stat CHANGELOG.md` ist leer; `collect --dry-run`
zeigt den Eintrag korrekt unter `### Changed` der `## [Unreleased]`-Sektion,
ohne den Bestand anzufassen.

## Schritte

1. [x] Recherchebericht + Repo-Stand lesen, Plan ablegen
2. [x] `scripts/changelog_fragments.py` + Tests
3. [x] `changelog.d/` mit README-Platzhalter
4. [x] `testpaths` um `scripts/tests` ergaenzen
5. [x] `apps/web/src/i18n/audit.ts` + Tests inkl. Captcha-Nachstellung
6. [x] CLI + npm-Script `i18n:check`
7. [x] `CONTRIBUTING.md`: Fragment-Verfahren mit Beispiel + DoD-Ergaenzung
8. [x] DoD lokal fahren (beide Staecke), Ergebnisse in den Bericht
9. [x] PR oeffnen, Review anfordern
