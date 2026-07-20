<!-- Titel: Conventional-Commit-Stil (feat/fix/docs/… + Scope), siehe CONTRIBUTING.md -->

## Zusammenfassung

<!-- Was ändert dieser PR und warum? Bei Befund-/Plan-Bezug: IDs bzw. Plan-Datei verlinken. -->

## DoD-Nachweis (lokal = CI, CONTRIBUTING §DoD)

<!-- Exakte Zahlen eintragen — solange CI nicht verlässlich läuft (Actions-Billing),
     ist dieser Block der Merge-Beleg (Standards-Review 2026-07-20, GIT-3/TST-2). -->

- [ ] Python: `uv run ruff check .` / `uv run ruff format --check .` / `uv run mypy .` grün
- [ ] Python: `uv run pytest --cov --cov-fail-under=85` — `____ passed`, Coverage `____ %`
- [ ] Web: `npm run lint` (0 Errors) / `npx tsc -b` grün
- [ ] Web: `npm run test:coverage` — `____ Tests`, Branches `____ %` (Floor 79)
- [ ] Web: `npm run build` grün
- [ ] nicht betroffene Stacks: als „n/a" markieren statt abhaken

## Kontext & Pflege

- [ ] `.claude/context/STATE.md` (immer) und `DECISIONS.md` (bei Entscheidungen) gepflegt
- [ ] Session-Link: <!-- https://claude.ai/code/session_… bzw. n/a -->
