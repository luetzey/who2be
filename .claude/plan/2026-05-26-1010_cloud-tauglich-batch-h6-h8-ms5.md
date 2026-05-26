# Cloud-tauglich-Batch — H6 + H8 + MS-5 (P1/P2/P3 Status-Switch)

**Datum:** 2026-05-26
**Branch:** `claude/loving-davinci-RoA0c`
**Plan-Datei:** dieselbe (living document)

## Goal (Completion-Condition)

1. `.github/workflows/ci.yml` hat einen `audit`-Job, der `pip-audit` (Python-Workspace) und `npm audit --omit=dev --audit-level=high` (Web) ausfuehrt und bei High/Critical mit Exit ≠ 0 failt.
2. Die 5 npm-moderate-Vulns sind entweder durch Dep-Upgrade beseitigt **oder** im neuen `deploy/hetzner/RUNBOOK.md` mit Begruendung als akzeptiert dokumentiert.
3. `deploy/hetzner/RUNBOOK.md` enthaelt eine **CVE-Response**-Sektion (H6) und eine **Secret-Rotation**-Sektion (H8) mit Schritt-fuer-Schritt-Anleitungen pro Secret (`JWT_SECRET`, `WHO2BE_API_TOKEN`, `STORAGE_BOX_*`, `RESTIC_PASSWORD`, `BACKUP_GPG_RECIPIENT`); jeweils Trigger / Schritte / Verifikation.
4. Alle bestehenden Test-Suites bleiben gruen: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q`, `npm run lint`, `npx tsc -b`, `npm test`.
5. P1/P2/P3 sind im Code verifiziert vorhanden (useListData<T>-Hook + Refactor, saving-disabled in beiden Detail-Pages, detail-Pass-through im client.ts, PlaybooksPage-Test). Notion-Status-Switch + Change-Log-Note (kein Code).

## Scope (was hier passiert)

### H6 — Supply-Chain-Gate (TASK-289, P1)

- Neuer CI-Job `audit` in `.github/workflows/ci.yml` (parallel zu `python` / `web` / `compose-smoke`):
  - `pip-audit` ueber `uv pip list` / direkt aus `uv.lock`; `--strict`, fail bei High/Critical
  - `npm audit --omit=dev --audit-level=high` in `apps/web`
- Versuch: vite/vitest auf aktuelle Versionen heben — wenn `npm test` + `npm run build` weiter gruen, sind die 5 moderates damit beseitigt.
  - Fallback: moderates akzeptieren (alle dev-only, keine Prod-Surface) und im neuen RUNBOOK begruendet.
- RUNBOOK-Sektion **CVE-Response** dokumentiert: was tun, wenn der Audit-Job rot wird (Triage-Schritte, Bypass-Optionen, Eskalation).

### H8 — Secret-Rotation-Runbook (TASK-291, P2)

- Neu: `deploy/hetzner/RUNBOOK.md` (existiert noch nicht). Wird hier von H6 mit-erstellt; H8 ergaenzt **Secret-Rotation**-Sektion.
- Pro Secret eine Subsection mit:
  - **Trigger:** wann rotieren (Kompromittierung, Mitarbeiter-Abgang, Routine ≥6 Monate)
  - **Schritte:** konkrete Compose-/Hetzner-Kommandos (neuen Wert generieren, `.env` editieren, Stack restart, Migrations-Validierung)
  - **Verifikation:** Smoke-Curl / Login-Test / Backup-Roundtrip
- Disjunkt zum Hetzner-`README.md` (operativ), referenziert Secrets aus `deploy/hetzner/.env.example`.

### MS-5 P1/P2/P3 — Status-Switch in Notion

- **P1 (TASK-292)** — `apps/web/src/hooks/useListData.ts` existiert (29 Zeilen), `usePersonas/usePlaybooks/useTokens` sind je 11 Zeilen und konsumieren den Hook, `useListData.test.tsx` existiert.
- **P2 (TASK-293)** — `PersonaDetailPage.tsx` Zeile 26+122 und `PlaybookDetailPage.tsx` Zeile 25+137 tracken `saving` + `disabled={saving}`; `client.ts` `readErrorMessage()` liest `body.detail`.
- **P3 (TASK-294)** — `apps/web/src/pages/PlaybooksPage.test.tsx` existiert (62 Zeilen).
- Plan: Test-Suite einmal voll fahren als Verifikation, dann die drei Notion-Tasks auf `Done` setzen mit Plan-Pointer.

## Schritte

1. **H6.1** — vite/vitest probehalber upgraden (`npm i -D vite@latest vitest@latest @vitest/mocker@latest vite-node@latest`), `npm test` + `npm run build` laufen lassen.
2. **H6.2** — `pip-audit`-Verfuegbarkeit checken (`uv tool run pip-audit --help`), Workspace-Audit lokal laufen lassen.
3. **H6.3** — `.github/workflows/ci.yml` um `audit`-Job erweitern.
4. **H8.1** — `deploy/hetzner/RUNBOOK.md` erstellen mit Sektionen: CVE-Response (H6) + Secret-Rotation pro Secret (H8) + Pointer aus `deploy/hetzner/README.md`.
5. **Verify** — alle 5 Suiten gruen (ruff/mypy/pytest, lint/tsc/vitest); CI-Workflow yaml mit `actionlint`/`docker compose config`-Aequivalent (`python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`) syntaxgepruefft.
6. **MS-5** — Test-Suite-Lauf reicht als Verifikation; Notion-Status fuer P1/P2/P3 auf Done.
7. **Commit + Push** — Conventional Commits, getrennt nach H6 / H8 / RUNBOOK. Push auf `claude/loving-davinci-RoA0c`.
8. **Notion-Doku** — Change-Log in Projekt-`## Notes` mit Pointer auf diese Plan-Datei; Task-Status TASK-289/-291/-292/-293/-294 → Done bzw. Review.

## Out of Scope (bewusst)

- H5/H7 (Caddy-Header, Prometheus) — brauchen Caddy-Live-Smoke gegen Hetzner, gehoeren in eine spaetere Session
- Tatsaechlicher CVE-Response-Drill — nur Doku, kein Live-Walk-through
- MS-2/MS-4-Tasks — separate Sessions, andere Voraussetzungen

## Risiken

- Vite 5 → 7/8 + Vitest 2 → 3/4 ist semver-major; APIs koennten brechen. Mitigation: lokaler `npm test` + `npm run build` gating; bei Bruch sauberer Rollback auf 5.x und stattdessen RUNBOOK-Akzeptanz dokumentieren.
- `pip-audit` koennte gegen `uv.lock` False-Positives haben (z.B. dev-only). Mitigation: bei Fund eines False-Positives mit `--ignore-vuln` und Begruendung im RUNBOOK.
