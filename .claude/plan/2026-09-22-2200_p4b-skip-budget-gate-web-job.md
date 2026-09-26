# P4b — Skip-Budget-Gate für den `web`-Job (coverage-Step)

Karte: t_d6e98b5e · Branch `who2be/t_d6e98b5e-nachzug-p4b-skip-budget-gate-auch-fuer-d`
Basis: rebased auf `main` @ 37510c1b

## Ausgangsmessung (lokal, Node 22.23.2, `apps/web`)

| Lauf | Kommando | Ergebnis |
|---|---|---|
| coverage-Step | `vitest run --coverage --reporter=junit` | 1217 Testfälle, **0 skipped** |
| A11y-Step | `vitest run --testNamePattern a11y --reporter=junit` | 1217 Testfälle, **1162 skipped** |

Die lokale A11y-Zahl (1162) weicht von der CI-Zahl (1131) ab, weil der Worktree
seit der PM-Messung Tests dazubekommen hat (1186 → 1217 Fälle). Das Verhältnis
ist identisch: der A11y-Step filtert per `--testNamePattern`, und Vitest weist
die herausgefilterten Tests als `skipped` aus. Bestätigt die Kartenanalyse.

## Entscheidungen

1. **JUnit per CLI-Flag am Step, nicht in `vite.config.ts`.**
   Beide Vitest-Steps teilen dieselbe Config. Ein Reporter in `vite.config.ts`
   schriebe also auch im A11y-Step eine XML — mit >1100 `skipped`-Einträgen,
   die exakt zu der Fehldiagnose einladen, die diese Karte entschärft.
   Das Flag am coverage-Step bindet das Artefakt an genau den Lauf, der die
   volle Suite fährt. Zusätzlich bleibt die lokale Entwickler-Erfahrung
   (`npm run test:coverage` ohne XML-Müll im Baum) unverändert.

2. **Skript wiederverwenden, minimal rückwärtskompatibel erweitern.**
   Getestet: das bestehende Skript liest Vitest-XML bereits korrekt
   (`<testcase>`/`<skipped/>` sind dieselbe Struktur wie bei pytest).
   Einziger Mangel: Vitest schreibt `<skipped/>` *ohne* `message`/`type`,
   also meldet der Report `1162x <ohne Grund>` — unbrauchbar zum Debuggen.
   Fix: Fallback auf den Testnamen (`<testcase name=...>`), wenn kein Grund
   dasteht. Rein additiv, der pytest-Pfad (mit `message`) bleibt unberührt und
   wird mit einem Lauf gegen eine echte pytest-XML belegt.

3. **Budget: `--max-other-skips 0`, kein Infra-Muster.**
   Das `INFRA_SKIP_PATTERN` greift auf der Web-Seite ins Leere (kein Postgres,
   kein Docker, keine Service-Container in jsdom). Es blind zu übernehmen wäre
   nicht falsch, aber auch nicht wirksam — es bleibt schlicht bei 0 Treffern.
   Der Schutz kommt hier allein aus dem Rest-Budget 0, passend zum gemessenen
   Ist-Zustand. Kein Sonderpfad, keine Web-spezifischen Muster.

4. **A11y-Step bekommt kein Gate**, mit Begründungskommentar an Ort und Stelle.

## Schritte

1. `scripts/ci/assert_skips_within_budget.py`: Testnamen-Fallback + Docstring.
2. `.github/workflows/ci.yml`, `web`-Job: JUnit-Flag am coverage-Step,
   Gate-Step `if: always()`, Artefakt-Upload, Kommentar am A11y-Step.
3. `CONTRIBUTING.md` §Definition of Done: Web-Kommandoliste nachziehen.
4. `CHANGELOG.md` Unreleased.
5. Empirischer Beleg beider Richtungen in CI (grün / rot mit `it.skip`).
