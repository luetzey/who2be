# Offene Aufgaben abarbeiten — Schritt-für-Schritt (2026-08-20)

**Status: in Umsetzung (dieser Branch, PR #390)** · Playbook: Code-Task-Flow
· Auftrag: „Alle offenen Aufgaben erledigen — Coder macht alles Codebare,
Owner nur das Nicht-Codebare."

Umgebung dieser Session: kein Docker, kein Postgres erreichbar →
DB-Integrationstests skippen (zugleich exakt die Repro-Umgebung für #385);
volle Coverage-DoD ist CI-Sache, lokal laufen ruff/mypy/Unit-Suiten.

## Teil A — Coder (diese Session, Reihenfolge = Abarbeitung)

| # | Aufgabe | Issue | Inhalt |
|---|---|---|---|
| A1 | Test-Skip-Guard | #385 | `test_resource_slug_children_duplicate.py` nutzt DB-Fixtures ohne `@pytest.mark.integration` → der zentrale conftest-Skip greift nicht (17 ERRORs statt Skips). Fix: `pytestmark = pytest.mark.integration` (Modul-Ebene); gleiche Lücke in `test_external_tools.py` prüfen/schließen. Repro zuerst (failing/error), dann grün/geskippt. PR schließt #385. |
| A2 | Dependabot-Bump + Reformat in einem Schritt | #384 | Die 8 Pakete der `python-minor-patch`-Gruppe per `uv lock --upgrade-package` bumpen (pytest 9.1.1, mypy 2.3.1, ruff 0.16.3, fastapi 0.141.1, pydantic-settings 2.15.0, pypdf 6.16.1, redis 8.1.0, fastmcp 3.4.7), dann `ruff format .` (erwarteter Drift: 5 Dateien), `ruff check`, `mypy`, lauffähige Test-Suiten. Kommentar auf #384: superseded durch PR #390. |
| A3 | Versionierung konsolidieren (Teil von #341 WP-8) | #341 | Root-`pyproject.toml` `version = "0"` → `0.1.0`. Tag + GitHub-Release bleiben bewusst NACH Merge + grünem CI (Blocker: CI-Infra, #338 O1). |
| A4 | Doku & Abschluss | — | STATE.md + Plan-README nachziehen, PR #390 (Titel/Body) aktualisieren, Issue-Kommentare (#384, #385-Close via PR-Keyword). Kein CHANGELOG-Eintrag (Test-Hygiene + minor/patch-Bumps ohne Nutzer-Außenwirkung). |

**Bewusst NICHT in Teil A:** `continue-on-error` des e2e-Jobs entfernen
(#341 WP-9 verlangt zuerst einen grünen CI-Lauf als Beleg); Tag/Release
(braucht gemergten, CI-grünen Stand); #330/#240 (Actions-Bumps — nur per CI
verifizierbar); PR #314 (Owner-Entscheidung).

## Teil B — Owner (Reihenfolge mit Abhängigkeiten)

1. **#338 O1 (Blocker für alles Weitere):** GitHub-Actions-Billing/Runner
   klären — Symptom seit 2026-08-19 ~16:37: jeder Lauf bricht nach 2–8 s ab,
   `runner_id: 0`, keine Logs. Alternative: Public-Flip vorziehen (freie
   Actions-Minuten), dann ist O1 obsolet. → Danach auf PR #390 „Re-run all
   jobs" (mir fehlt das Recht, 403).
2. **PR #390 reviewen + mergen** (schließt #385; #384 schließt Dependabot
   selbst, sobald der Lock-Stand auf `main` ist).
3. **#338 O2:** Settings → Branch-Protection `main`, „Automatically delete
   head branches", Merge-Strategie festlegen, Description + Topics setzen
   (Textvorschläge in PR #389).
4. **#388:** die zwei vorbereiteten `git push origin --delete`-Blöcke
   ausführen (70 Branches); Restliste `…-setup-4fk7ed` sichten → löschen
   oder Inhalt retten.
5. **#338 O3:** CLA-Assistant (cla-assistant.io) aktivieren, Link in
   CONTRIBUTING.md eintragen (Platzhalter existiert).
6. **Nach erstem grünem CI-Lauf** (Owner stößt an oder sagt mir Bescheid):
   ich erledige #341 WP-8/9-Rest — Tag `v0.1.0` + GitHub-Release mit Notes,
   `continue-on-error` aus dem e2e-Job entfernen; Dependabot #330/#240
   lassen sich dann per CI verifizieren und mergen.
7. **#341 WP-10 (optional vor Public, Pflicht vor 1.0):** Deploy-Pipeline
   einmal end-to-end (`DEPLOY_HOST` setzen, `deploy/hetzner/scripts/deploy.sh`).
8. **PR #314** (Pitch-Dossier, Draft seit Juli): mergen oder schließen.
9. **#338 O4 (Finale):** Visibility Private → Public — erst nach grünem
   CI-Lauf. Danach: Social-Preview-Bild, README-Screenshot/GIF, ggf.
   Discussions.

## Verify (Teil A, transkript-nachweisbar)

- A1: Testdatei ohne DB vorher = 17 ERRORs, nachher = Skips; Suite-Lauf ohne
  neue Fehler.
- A2: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`
  grün; lauffähige pytest-Suiten grün (DB-Tests geskippt, Anzahl genannt);
  Lock-Diff nur die 8 Pakete + Transitives.
- A3: `uv sync` läuft mit neuer Version; kein weiterer Verweis auf `"0"`.
