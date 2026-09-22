# P4 — Uebersprungene Tests duerfen nicht als bestanden gelten

Karte: `t_3465cdaa` · Branch: `who2be/t_3465cdaa-p4-uebersprungene-tests-duerfen-nicht-al`

## Gemessener Ausgangszustand (2026-09-22, dieser Worktree)

| Fakt | Messung | Quelle |
|---|---|---|
| `WHO2BE_REQUIRE_DB` existiert bereits | ja | `conftest.py:114` (`pytest.UsageError`), `pyproject.toml:85` |
| In CI gesetzt | ja, im Job `python` | `.github/workflows/ci.yml:146-150` |
| Lokaler Lauf ohne DB/Docker | **1507 passed, 485 skipped**, exit 0 | `uv run pytest -q --junitxml` |
| Skip-Gruende (aus JUnit-XML) | 482x `… zentral uebersprungen (conftest)`, 3x inline `Keine erreichbare Datenbank …` | JUnit-Auswertung |
| Nicht-infrastrukturelle Skips | **0** | dito |
| Aggregat-Job (`all-green`) in `ci.yml` | existiert **nicht** | Job-Liste: `changes, python, web, compose-smoke, e2e, e2e-billing-cloud, audit` |

**Befund zu AK1/AK2:** Der Schalter und seine CI-Aktivierung sind bereits vorhanden — die Luecke ist
(a) er steht nirgends dort, wo ein Entwickler ihn sucht (`CONTRIBUTING.md` nennt ihn nicht), und
(b) es gibt kein Gate, das *andere* Skip-Quellen als die zentrale DB-Pruefung abfaengt.

## Entscheidung: wo das Gate haengt

Der PM-Kommentar verlangt, das Gate ueber den Aggregat-Job aus P3a rot werden zu lassen.
**Dieser Job existiert im Repo nicht**: P3a (`t_80db6454`) wurde als Dublette archiviert, die gueltige
Karte `t_b0233031` steht noch auf `ready`. `origin/main` und dieser Branch enthalten unveraendert
sieben Jobs ohne Aggregat.

Gewaehlt: **Step im bestehenden `python`-Job**, direkt nach dem Test-Step.

* Der `python`-Job wird zwangslaeufig in `needs:` des kuenftigen Aggregat-Jobs stehen (er ist einer der
  sieben). Ein Verstoss faerbt `python` rot und damit den Aggregat-Job — genau die geforderte Wirkung,
  ohne einen isolierten Job neben dem Tor.
* Kein neuer Job = keine Strukturaenderung an `ci.yml`, die mit der spaeteren P3-Karte kollidiert.
* Die JUnit-XML entsteht ohnehin nur im Job, der pytest faehrt — ein separater Job muesste sie als
  Artefakt herumreichen.

## Schwellenwert und seine Begruendung

Zwei getrennte Regeln statt einer Zahl:

1. **Infrastruktur-Skips: Budget hart 0.** Skip-Gruende, die auf fehlende DB/Docker/Postgres deuten,
   sind in CI *immer* ein Fehler — dort steht die Infrastruktur per Service-Container. Ein solcher
   Skip heisst: das Setup ist kaputt, nicht der Test irrelevant.
2. **Uebrige Skips: Budget konfigurierbar, Default 0.** Gemessen: heute null. Plattformbedingte Skips
   (windows-only o. ae.) existieren im Repo nicht; entstehen sie, hebt man das Budget bewusst per
   `--max-other-skips` an — sichtbar im Diff, mit Begruendung, statt still zu wachsen.

Basis ist die JUnit-XML (`--junitxml`), nicht die Textausgabe — wie in der Karte gefordert.

## Arbeitspakete

1. `scripts/ci/assert_skips_within_budget.py` — liest JUnit-XML, klassifiziert Skip-Gruende,
   bricht mit `::error`-Annotation ab. Enthaelt den Deny-Regex fuer Infrastruktur.
2. `.github/workflows/ci.yml` — `--junitxml=junit-python.xml` an den pytest-Aufruf, neuer Step
   "Skip-Budget-Gate" direkt danach (`if: always()`, damit ein Test-Fehlschlag das Gate nicht
   verschluckt), Upload der XML als Artefakt.
3. `CONTRIBUTING.md` — `WHO2BE_REQUIRE_DB` in der Definition of Done dokumentiert; Handoff-Regel
   "passed **und** skipped nennen".
4. `docs/adr/0041-*` / `conftest.py` bleiben unberuehrt (kein Test wird umgeschrieben, AK5).

## Fund fuer AK5 — nicht repariert, nur gelistet

Drei Tests skippen inline ohne `@pytest.mark.integration`, laufen also **nicht** in den zentralen
Guard und wuerden auch mit `WHO2BE_REQUIRE_DB=1` still skippen statt hart zu fehlen:

* `apps/api/tests/test_resources.py::test_resource_active_filter_for_api_token` (Zeile 335)
* `apps/api/tests/test_playbooks.py::test_playbook_active_filter_for_api_token`
* `apps/api/tests/test_resource_composition.py::test_sub_resource_active_filter_for_api_token`

Das neue Gate faengt sie trotzdem ab (ihr Skip-Grund matcht den Infrastruktur-Regex), aber der
fehlende Marker gehoert in ein eigenes Paket.

## Verifikation

Sieben Szenarien, alle mit **echten** pytest-Laeufen (Fixture-Suite ausserhalb des Repos), keine
von Hand gebastelte XML:

| # | Lauf | Erwartung | Ergebnis |
|---|---|---|---|
| A | echte Suite ohne DB, 1992 Faelle / 485 Infra-Skips | rot | **EXIT 1** |
| B | Fixture, 4 passed / 0 skipped | gruen | **EXIT 0** |
| C | Fixture, 1 plattformbedingter Skip, Budget 0 | rot | **EXIT 1** |
| D | dieselbe XML, `--max-other-skips 1` | gruen | **EXIT 0** |
| E | Fixture, 1 Infra-Skip, `--max-other-skips 99` | rot (Budget greift nicht) | **EXIT 1** |
| F | XML fehlt | fail-closed | **EXIT 2** |
| G | XML aus `WHO2BE_REQUIRE_DB=1`-Abbruch (`tests="0"`) | rot | **EXIT 2** |

**Fund waehrend der Verifikation (G):** Feuert der `WHO2BE_REQUIRE_DB`-Guard, bricht pytest mit
`UsageError` ab und schreibt eine XML mit `tests="0"` — die erste Fassung des Gates meldete darauf
gruen. Genau die Fehlerklasse der Karte. Das Gate bricht jetzt auch bei null Testfaellen ab.

Statisch: `uv run ruff check .` · `uv run ruff format --check .` · `uv run mypy .` — alle gruen
(751 Dateien formatiert, 465 Quelldateien typgeprueft).

Nicht lokal verifizierbar: der gruene Vollzug mit DB (kein Docker/Postgres auf dieser Maschine,
`docker info` schlaegt fehl). Den liefert der CI-Lauf des PR — er ist der eigentliche AK2-Beleg.

### CI-Belege (AK2), zwei Laeufe mit gegensaetzlichem Ausgang

| Lauf | Infrastruktur | Job `python` | Ausgabe |
|---|---|---|---|
| [35718903202](https://github.com/luetzey/who2be/actions/runs/35718903202/job/106716929196) (PR #581) | steht | **pass**, 8m24s | `2012 passed` · Gate: `2012 Testfaelle, 0 uebersprungen` · `OK` |
| [35719930468](https://github.com/luetzey/who2be/actions/runs/35719930468/job/106720580754) (Beleg-PR #582) | Postgres-Service auskommentiert | **fail**, 57s | `WHO2BE_REQUIRE_DB gesetzt, aber keine DB erreichbar — 484 Integrationstests koennen nicht laufen` (exit 4) **und** `junit-python.xml enthaelt keinen einzigen Testfall` (exit 2) |

Kein gruener Job mit Skips — ein roter Job, zweifach begruendet. Der zweite Fehler ist der Beleg
dafuer, dass die Null-Testfaelle-Pruefung noetig war: ein reiner Skip-Zaehler haette hier `0 skipped`
gesehen und gruen gemeldet.

PR #582 ist geschlossen; der Branch `p4-beleg-infra-entfernt` muss vom Owner geloescht werden
(Remote-Branch-Loeschung ist fuer Agenten gesperrt).
