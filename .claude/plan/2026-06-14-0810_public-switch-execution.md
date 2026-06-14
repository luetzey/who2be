# Public-Switch — Umsetzung der Rest-Punkte

**Stand:** 2026-06-14 0810 · **Branch:** `claude/exciting-fermi-d0imfe`
**Quelle:** Analyse der offenen Punkte aus
`.claude/plan/2026-05-27-2028_public-switch-github-repo.md` +
`docs/security-findings-phase-2.md` §TODO vor Public-Switch.

## Kontext

Die Public-Switch-Vorarbeit ist zu ~90 % erledigt (LICENSE.md, CONTRIBUTING.md,
SECURITY.md, project.json gitignored + Example, Secret-Audit sauber,
F-Phase2-01 Rate-Limits + F-12 CSP geschlossen). Bei der Code-Inspektion
zeigte sich: **F-Phase2-03 (require_role admin auf PATCH workspace) und der
Last-Admin-Advisory-Lock sind bereits im Code** — nur die Findings-Tabelle in
`security-findings-phase-2.md` wurde nicht nachgezogen.

**Entscheidungen (User, 2026-06-14):** Umfang = Repo-Härtung + GitHub-Settings
(Visibility-Flip löst der User final selbst aus); Sandbox = Variante 3a
(lokaler Branch); Commit-Identität = belassen (kein Mehrwert ohne
History-Rewrite).

## Real offen → diese Iteration

- [ ] **WP-1 — F-Phase2-02 (Low, Defense-in-Depth).** `list_linked` um
  `workspace_id` erweitern. Protocol + Pg-Impl + SQL-`AND pp.workspace_id = $2`
  + beide Service-Call-Sites (`ctx.workspace_id`) + Test-Fake. Regressionstest:
  Service reicht `ctx.workspace_id` an `list_linked` durch.
- [ ] **WP-2 — Findings-Doku nachziehen.** F-Phase2-02 → Closed (mit Fix),
  F-Phase2-03 → Closed (require_role(admin) seit Track-C-Workspaces da; SQL-Key
  IST der workspace_id, kein Re-Bind nötig), Last-Admin-Anmerkung → erledigt
  (Advisory-Lock vorhanden). Ampel auf Grün.
- [ ] **WP-3 — Sandbox-Konvention 3a dokumentieren** in `CONTRIBUTING.md`
  (kurzer Abschnitt: `sandbox/*`-Branches, kein Remote-Tracking, fertige Sachen
  via PR).
- [ ] **WP-4 — Verifikation:** `uv run ruff check .`, `uv run ruff format
  --check .`, `uv run mypy .`, betroffene Tests
  (`test_persona_playbook_service.py`).
- [ ] **WP-5 — Commit + Push + Draft-PR** auf den Feature-Branch.
- [ ] **WP-6 — GitHub-Settings via MCP** (NICHT Visibility): Description,
  Topics, Issues/Discussions/Security-Advisories, Branch-Protection auf `main`.

## Bewusst NICHT in dieser Iteration

- **Visibility Private→Public** — löst der User final selbst aus (irreversibel).
- **Branch-Protection mit „CI grün"-Required** — die CI-Runner-Infra ist laut
  `2026-06-13-1512_repo-review-remediation.md` (ST-2) derzeit umgebungsweit
  defekt. Required-Status-Check würde `main` sperren. → Branch-Protection mit
  Required-Review + kein Force-Push setzen; Status-Check-Required erst, wenn CI
  wieder grün läuft. Im PR/Antwort klar flaggen.
- **CLA-Assistant** — externer Dienst (cla-assistant.io), kann nicht per MCP
  aktiviert werden; bleibt manueller Schritt für den User (in CONTRIBUTING.md
  bereits referenziert).
- **DB-Integrationstests** — kein Docker/CI-Runner in dieser Umgebung; das
  WP-1-SQL ist per Transkriptions-Äquivalenz + Service-Contract-Test verifiziert,
  nicht gegen echtes Postgres ausgeführt (gleiche Grenze wie STR-1*).

## Acceptance

- [ ] `list_linked` trägt `workspace_id`-Filter; ruff/mypy/Tests grün.
- [ ] Findings-Doku spiegelt den realen Code-Stand (alle Phase-2-Findings Closed).
- [ ] Sandbox-3a in CONTRIBUTING.md dokumentiert.
- [ ] Draft-PR offen; GitHub-Settings gesetzt (ohne Visibility-Flip).

## Notes

2026-06-14 0810 — V1.0 Initial-Anlage nach Code-Inspektion. Scope gegenüber
der ursprünglichen TODO-Liste verkleinert, weil F-Phase2-03 + Last-Admin schon
im Code waren.
