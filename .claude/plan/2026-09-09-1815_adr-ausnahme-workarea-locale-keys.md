# #510 — ADR-0051-Ausnahme: die sechs WorkArea-Gruende ohne Locale-Key

Betriebsmodus: **produktiv**. Ein-Datei-Doku-Paket, `size/S`.

**Keine Muster-Entscheidung noetig** — der Absatz folgt dem bestehenden
Formvorbild `## Ausnahme (2026-09-08, W7b von #491/#502)` in derselben Datei.

## Umsetzung

Ein Abschnitt ans Ende von `docs/adr/0051-api-fehlercodes.md` (nach Zeile 214),
plus CHANGELOG- und STATE-Eintrag. Kein Produktivcode, keine Locale-Keys.

Selbst umgesetzt statt delegiert: Phase-3-Ausnahme („triviale Aenderungen ohne
Design-Entscheidung"). Die Substanz ist im Issue entschieden; ein Sub-Agent
haette nur den Text abgeschrieben.

## Angaben von #510 nachgeprueft (Regel 25)

| Angabe | Ergebnis |
|---|---|
| Formvorbild `## Ausnahme (W7b)` | Zeile **189** ✓ |
| §5-Grundlage („ein Grund ohne Locale-Key …") | Zeile **114** ✓ |
| Fundstelle `TableDetailPage.tsx:46-48` | woertlich ✓ |
| Null Web-Aufrufer (`insertRows`/`queryTable`/`waTimeline`/`promoteArtifact`) | **0 / 0 / 0 / 0** ✓ |
| Die sechs Gruende auf `main` | **6** Treffer in `errors.py` ✓ |

Keine Korrektur noetig.

## Verifikation

`grep` auf die sechs Gruende im ADR · `measure_gate_reasons.py` (muss
unveraendert 98 / 75 melden) · `localeParity.test.ts`.

## DoD

PR mit `Closes #510`, `Closes #506`, `Closes #491`; CHANGELOG unter Unreleased;
STATE fortgeschrieben. Der Kommentar an #506, der AK 5 als *ersetzt* ausweist,
steht seit dem 2026-09-09 (Anlage von #510).
