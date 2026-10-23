<!-- Titel: Conventional-Commit-Stil (feat/fix/docs/… + Scope), siehe CONTRIBUTING.md -->

Issue: Closes #___

<!-- Pflichtzeile (CONTRIBUTING.md §Issue reference). Sie steht als EIGENE Zeile
     ganz oben und beginnt am Zeilenanfang mit `Issue:` — kein Spiegelstrich,
     keine Überschrift davor, nicht in einen Satz eingebettet. Genau eine Form:

       Issue: Closes #NNN                         Merge erledigt das Issue (GitHub schliesst es)
       Issue: Refs #NNN                           Teilarbeit an Tracking-/Epic-Issue, bleibt offen
                                                  (Queue-Regel 19, #442)
       Issue: n/a (Kanban card <id>, <Kontext>)   kein Issue, z. B. Kanban-Karte, Dependabot, Hotfix

     Selbstprüfung (muss `true` liefern):
       gh pr view <n> --json body -q '.body|test("(?m)^Issue:")' -->

Hilfe: geändert | n/a – <Grund>

<!-- Hilfe-Zeile (CONTRIBUTING.md §Hilfe aktuell halten). Auf GENAU EINE Form
     kürzen — bleibt die Zeile so stehen, zählt sie als ungültig:

       Hilfe: geändert            apps/web/src/help/ ist im Diff mitgeändert
       Hilfe: n/a – <Grund>       Grund aus der festen Liste: intern | kein UI-Text |
                                  nur Tests | Folgekarte <id> (t_… oder #NNN)

     Ändert der PR Komponenten unter apps/web/src/features/*/components/ oder
     bestehende Werte in apps/web/src/i18n/locales/*.json ohne Hilfe-Änderung
     und ohne gültige n/a-Zeile, warnt der CI-Job `changes` (keine Sperre). -->

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
