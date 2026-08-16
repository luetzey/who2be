<!-- Titel: Conventional-Commit-Stil (feat/fix/docs/… + Scope), siehe CONTRIBUTING.md -->

## Zusammenfassung

<!-- Was ändert dieser PR und warum? Bei Befund-/Plan-Bezug: IDs bzw. Plan-Datei verlinken. -->

## DoD-Nachweis (lokal = CI, CONTRIBUTING §DoD)

<!-- Exakte Zahlen eintragen. Die Gates laufen VOR dem Push lokal, die CI ist die
     Gegenprobe — nicht umgekehrt (CLAUDE.md §Workflow, CONTRIBUTING §DoD;
     Standards-Review 2026-07-20, GIT-3/TST-2). Dass das kein Ritual ist, zeigt
     PR #370: ein lokal übersehener Lint-Fehler wurde erst in der CI rot. -->

- [ ] Python: `uv run ruff check .` / `uv run ruff format --check .` / `uv run mypy .` grün
- [ ] Python: `uv run pytest --cov --cov-fail-under=85` — `____ passed`, Coverage `____ %`
- [ ] Web: `npm run lint` (0 Errors) / `npx tsc -b` grün
- [ ] Web: `npm run test:coverage` — `____ Tests`, Branches `____ %` (Floor 79)
- [ ] Web: `npm run build` grün
- [ ] nicht betroffene Stacks: als „n/a" markieren statt abhaken

## Kontext & Pflege

- [ ] `.claude/context/STATE.md` (immer) und `DECISIONS.md` (bei Entscheidungen) gepflegt
- [ ] Session-Link: <!-- https://claude.ai/code/session_… bzw. n/a -->
