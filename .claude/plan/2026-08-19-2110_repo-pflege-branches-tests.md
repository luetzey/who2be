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

- [x] Welle 1 Klassifikation (23×a, 48×b, 6×c1; Restliste: 1 Branch;
  Artefakte: scratchpad BRANCH_CLASSIFICATION.md + prmap.json)
- [x] Welle 2 — ABWEICHUNG: Löschung aus der Cloud-Session technisch
  gesperrt (Git-Proxy 403, Schreibrecht nur auf den Arbeits-Branch; kein
  Lösch-Tool im GitHub-MCP). Deliverable: fertiger
  `git push origin --delete`-Block (70 Branches) im Abschlussbericht —
  Owner führt lokal aus. Restliste: `claude/autonomous-code-agent-setup-4fk7ed`
  (PR #336 closed-unmerged, MCP-Tool-Import-Konzept-Doku).
- [x] Welle 3 Dependabot: #368 gemergt (lokal voll verifiziert); #245/#243/
  #242 geschlossen (Juni-Basen, Lockfile-Konflikte, #242 zudem Major);
  #384 offen mit Befund (Ruff-Bump → Format-Drift in 5 Dateien, Empfehlung
  Bump+Reformat in einem Schritt); #330/#240 (Actions-Bumps) warten auf
  lebende CI.
- [x] Welle 4 E2E: Journeys scharf implementiert (`dc897c8`) — Helper
  e2e/helpers/auth.ts, 4 Journeys, minimale data-testid-Anker. Soft-Gate
  bleibt; Gate-Härtung erst nach grünem CI-e2e-Beleg (CI-Infra weiterhin
  tot, ~4-s-Abbrüche, #338).
- [x] STATE.md-Pflege + Abschlussbericht
