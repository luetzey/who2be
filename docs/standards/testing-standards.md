# Test-Strategie & QA

Tests sind Teil der Definition of Done, nicht ein nachgelagerter Schritt.
Repo-spezifische Strategie: [`../adr/0032-test-strategie-pyramide.md`](../adr/0032-test-strategie-pyramide.md);
DoD-Befehle in [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

## Prinzipien

- **Testpyramide:** zum Großteil schnelle Unit-Tests, ergänzt durch
  Integrations-Tests, wenige End-to-End-Tests.
- **TDD-Disziplin:** bei Bugfixes **zuerst** einen reproduzierenden,
  fehlschlagenden Test schreiben, dann fixen. Edge Cases explizit.
- **Definition-of-Done:** Tests sind Teil der Acceptance Criteria; vor Abschluss
  müssen sie grün sein.
- **Code-Reviews** als Qualitäts-Gate für die Standard-Einhaltung.

## Im Repo

- Python: `pytest` (`uv run pytest -q`); DB-Integrationstests skippen ohne
  Postgres-Container. Coverage-Ratchets als Gate.
- Web: `vitest` (`npm test`), A11y-Tests (`vitest-axe`) für klickbare/eingebbare
  Komponenten (ADR-0016).
- E2E: vorhanden, aber Soft-Gate solange die CI-Runner-Infra instabil ist.

## Anti-Patterns

- **Umgekehrte Pyramide** (viele langsame E2E, wenig Unit).
- **Fix ohne reproduzierenden Test** — Regression nicht abgesichert.
- **Tests „später"** — heißt in der Praxis nie.
- **Review überspringen** — kein Qualitäts-Gate.
