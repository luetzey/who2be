# Repo-Pflege: Branch-Hygiene + Dependabot-Triage + E2E-Spitze

_2026-08-19 · Ausführung mit right-sized Sub-Agents · User-Policies per
AskUserQuestion bestätigt_

## Auftrag & Policies (User)

1. **Branch-Hygiene:** 83 Remote-Branches, 8 mit offenem PR → alles Tote
   löschen (per Merge-Commit enthalten, squash-/inhaltlich gemergt, oder
   nie PR't mit leerem Diff); nie-PR'te mit echtem Delta nur berichten.
2. **Dependabot-PRs (#384, #368, #330, #245, #243, #242, #240):** lokal
   verifizieren + mergen (Muster PR #386 — lokales Stack-DoD ersetzt die
   tote CI); Veraltetes schließen (Dependabot legt neu auf).
3. **Testpyramide:** Unten/Mitte solide (Python 1698/~91 %, Web
   956/~86,5 %, Contract-Tests); Lücke = leere E2E-Spitze (4 fixme-Stubs
   seit Juni, ADR-0041). → Login-/Seed-Helper + 4 Journeys umsetzen; kein
   Unit-Test-Ausbau um der Zahl willen.

## Rahmenbedingungen

- CI-Infra tot (alle Jobs ~4 s, auch `main`; Owner-Checkliste #338).
- Lokal kein Docker/Postgres → Playwright-E2E hier nicht ausführbar;
  E2E-Schärfung (`fixme` → aktiv) erst nach grünem CI-Beleg.
- Repo-Setting „Auto-delete head branches" = Owner-Empfehlung, nicht von
  mir setzbar.

## Wellen

| Welle | Inhalt | Ausführung | Modell + Begründung |
| --- | --- | --- | --- |
| 1 | Branch-Klassifikation (a/b/c1/c2) read-only | Sub-Agent | Haiku 4.5 — Listenarbeit nach festen Regeln, kein Design-Urteil |
| 2 | Löschung a/b/c1 in Batches, c2-Restliste | Orchestrator (Fable) | destruktiv bleibt beim Orchestrator |
| 3 | Dependabot-Triage je PR: lokal DoD → merge/close | Sub-Agent sequenziell | Sonnet — mechanisch, aber Debug-Urteil bei Rot nötig |
| 4 | E2E: loginAs-/Seed-Helper + 4 Journeys, Draft-PR | Sub-Agent | Sonnet, Eskalation Opus nur bei Auth-Injektions-Blockade |

Sub-Agents committen/löschen nie; Verifikation + Commits + destruktive
GitHub-Aktionen beim Orchestrator.

## Status

- [ ] Welle 1 Klassifikation
- [ ] Welle 2 Löschung + Gegenprobe (`git ls-remote`)
- [ ] Welle 3 Dependabot (je PR Ergebnis dokumentiert)
- [ ] Welle 4 E2E-PR (Draft, Aktivierung wartet auf CI-Beleg)
- [ ] STATE.md-Pflege + Abschlussbericht
