# Who2Be — Blueprint v2 (post Plan-Review)

> Loest `.claude/plan/2026-05-24_who2be-mvp-roadmap.md` als
> aktiven Master-Plan ab. Der alte Plan bleibt als Historie liegen.
> Projekt-Blueprint-Output (Coder, Playbook V1.2).
> Notion-Projekt: PROJ-19 "Who2Be" (`364be537-2ab8-81ff-94e5-e8827c2228a4`).

## Context

Stand 2026-05-26: MS-1 (Web-UI), MS-2 C1-C4 (Hetzner + Compose +
CI/CD), MS-3 H1-H3 (Rate-Limiting + JSON-Logs + Security-Review)
und die Backend-Followups F-02/F-09 sind gemerged. Offen: MS-2
C5/C6, MS-3 H4, MS-4 B1-B4. Plan-Review v2 zieht F-12 aus dem
Followup-Buffer in eine eigene Task (H5), splittet das Backup in
local+offsite (C5a/C5b), ergaenzt CI-Supply-Chain-Gate (H6),
Prometheus-Metriken (H7) und Secret-Rotation-Runbook (H8), und
verankert die Codebase-Review-Findings (`useListData`-Refactor,
Save-disabled, Detail-Errors, PlaybooksPage-Test) als MS-5 Post-MVP.

## Architektur-Referenz (unveraendert)

- Modularer Monolith, geschichtet — ADR-0001/0002.
- Raw asyncpg + nummerierte SQL-Migrationen — ADR-0003.
- Versionierung ueber History-Tabellen — ADR-0004.
- MCP-Server = HTTP-Adapter — ADR-0005.
- Dual-Auth Supabase-JWT + `w2b_`-Token — ADR-0006.
- Strukturierte Logs — ADR-0007.

## Neue ADRs (Plan-Review v2)

| ADR | Entscheidung | Status |
|---|---|---|
| 0008 | Token-Hash-Vergleich bleibt nicht-konstantzeit, Re-Eval-Trigger via Prometheus | Accepted |
| 0009 | JSONB-Content: strict-on-write, lax-on-history | Accepted |
| 0010 | Observability: Prometheus + Grafana ueber `/v1/internal/metrics`, Caddy blockt extern | Accepted |
| 0011 | Backup: GPG-encrypted Dump + restic auf Hetzner Storage Box | Accepted |
| 0012 | MCP-Write-Tools sind post-MVP (deferred) | Deferred |
| 0013 | API-Versionierung: pfad-basiert mit SemVer-Semantik | Accepted |

## Diff gegen alten Plan (2026-05-24-Roadmap)

**Hinzugefuegt:**
- MS-3 **H5** (Caddy-Hardening, ehemals F-12-Followup)
- MS-3 **H6** (Supply-Chain-CVE-Gate in CI)
- MS-3 **H7** (Prometheus + Grafana)
- MS-3 **H8** (Secret-Rotation-Runbook)
- MS-5 **P1/P2/P3** (Web-Polish-Phase aus Codebase-Review)

**Geaendert:**
- MS-2 **C5** aufgesplittet in **C5a** (local+gpg) und **C5b** (offsite-restic)
- MS-4 **B4** mit verbindlicher Vergleichs-Baseline + Rollback-Pfad
- MS-4 **B1** Daten-Output-Pfad raus aus `data/` (.gitkeep), rein nach
  `scripts/brainstormer/` + `data/` in `.gitignore`
- `PersonaContent`/`PlaybookContent` in zwei Models geteilt (write-strict /
  read-lax) — ADR-0009
- W6 Local-Smoke vom Done-Kriterium degradiert auf Dev-Aid; C6 ist das
  verbindliche Smoke

**Entfernt:**
- F-12 als blosses "Followup" ohne Task
- F-04 als implizit-vergessenes Accepted (durch ADR-0008 mit Re-Eval-Trigger ersetzt)
- `data/brainstormer/.gitkeep`

**Out-of-Scope MVP (verschriftlicht):**
- MCP-Write-Tools (ADR-0012)
- Web-Pagination-Controls (warten auf Prometheus-Signal)
- Managed-DB-Wechsel
- Tracing-Stack (Tempo/Jaeger)

---

## Milestones (offen + neu)

### MS-2 — Cloud-Deploy (Restarbeit)

**C5a — Local-Encrypted-Dump**
- Outcome: `pg_dump -Fc | gpg -e -r <recipient>` schreibt
  `/var/backups/who2be/dump-<ts>.pgc.gpg`. Cron daily 03:15 UTC.
- Context: `deploy/hetzner/scripts/backup.sh` (ersetzt Status-quo-Plan),
  `deploy/hetzner/RUNBOOK.md` (Backup-Sektion).

**C5b — Offsite-Sync (restic auf Hetzner Storage Box)**
- Outcome: `restic` mit SFTP-Backend auf Storage Box. Retention
  7d/4w/6m. `restic snapshots` zeigt Hetzner-Snapshots ≤ 26h alt.
- Context: `deploy/hetzner/scripts/backup.sh` (restic-Sektion),
  `deploy/hetzner/RUNBOOK.md` (Restore-Sektion mit Schluessel-
  Handling). Secrets: `STORAGE_BOX_*`, `RESTIC_PASSWORD`,
  `BACKUP_GPG_RECIPIENT`.

**C6 — E2E-Smoke gegen Hetzner**
- Outcome: `curl https://api.<domain>/v1/health` → 200/`db:ok`,
  `POST /v1/tokens` mit echtem Web-JWT funktioniert, RUNBOOK-Eintrag.
- Context: nur `deploy/hetzner/RUNBOOK.md` (Smoke-Sektion).

### MS-3 — Hardening (offen + neu)

**H4 — Restore-Drill produktiv**
- Outcome: GPG+restic restore in Test-DB; `GET /v1/personas` liefert
  identische Liste; RUNBOOK-Log.
- Context: `deploy/hetzner/RUNBOOK.md` (Restore-Drill-Sektion).
- Dependency: MS-2 C5a + C5b done.

**H5 — Caddy-Hardening (Security-Header + CSP + /internal-Block)**
- Outcome: Caddy setzt `Strict-Transport-Security`,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  restriktive CSP. `/v1/internal/*` → 403 von extern.
  `WHO2BE_DOCS_PUBLIC=false` schliesst `/docs` (F-13-Toggle).
- Context: `deploy/hetzner/Caddyfile`, neu
  `deploy/hetzner/tests/test_headers.sh`, optional
  `apps/api/src/who2be_api/main.py` (FastAPI(`docs_url=None`) bei
  `WHO2BE_DOCS_PUBLIC=false`).
- Schliesst: F-12, F-13.

**H6 — Supply-Chain-Gate (pip-audit + npm audit)**
- Outcome: CI-Job in `.github/workflows/ci.yml` faehrt `pip-audit`
  und `npm audit --omit=dev --audit-level=high`. Fail bei
  High/Critical, PR-Comment bei Moderate. Initial-Pass dokumentiert
  und Moderate-Findings (Session-Hook 5 moderate) adressiert oder
  bewusst akzeptiert.
- Context: `.github/workflows/ci.yml`, RUNBOOK-Eintrag fuer
  CVE-Response-Pfad.

**H7 — Prometheus-Metriken + Grafana**
- Outcome: `prometheus-fastapi-instrumentator` exposes
  `/v1/internal/metrics`. Prometheus + Grafana in Compose. Grafana
  unter `app.<domain>/grafana/` mit Basic-Auth. Dashboard `who2be-red.json`:
  Requests/s pro Pfad, P50/P95/P99-Latenz, Error-Rate, Custom-Counter
  `who2be_auth_token_attempts_total{result}`.
- Context: neu `apps/api/src/who2be_api/core/metrics.py`,
  `apps/api/pyproject.toml` (+`prometheus-fastapi-instrumentator>=7`),
  `deploy/hetzner/who2be/docker-compose.yml` (+prometheus, +grafana),
  neu `deploy/hetzner/grafana/dashboards/who2be-red.json`,
  `deploy/hetzner/Caddyfile` (grafana-Route).
- Tests: `apps/api/tests/test_metrics.py` (200/Content-Type),
  Caddy-Block-Smoke siehe H5.
- Schliesst: ADR-0010-Vertrag.

**H8 — Secret-Rotation-Runbook**
- Outcome: `deploy/hetzner/RUNBOOK.md` enthaelt Schritt-fuer-Schritt-
  Rotation fuer `JWT_SECRET`, `WHO2BE_API_TOKEN`, `STORAGE_BOX_*`,
  `RESTIC_PASSWORD`, `BACKUP_GPG_RECIPIENT`. Pure Doku, kein Code.
- Context: nur `deploy/hetzner/RUNBOOK.md`.

### MS-4 — Brainstormer-Migration

**B1 — Notion-Export**
- Outcome: `scripts/brainstormer/export_from_notion.py` zieht
  Persona + 5 Playbooks (Body, Tags, Triggers) aus Notion und schreibt
  JSON-Files nach `data/brainstormer/`. `data/` ist `.gitignore`'d.
- Context: neu `scripts/brainstormer/export_from_notion.py`,
  `.gitignore` (+`data/`). **Kein `data/brainstormer/.gitkeep`** —
  bewusst, um sensibles Prompt-Engineering nicht eincheckbar zu machen.

**B2 — Import in Hetzner-Instanz**
- Outcome: `scripts/brainstormer/import_to_who2be.py` ruft
  `POST /v1/personas` und `POST /v1/playbooks` mit API-Token gegen die
  Hetzner-API. Web zeigt Persona + 5 Playbooks; `GET
  /v1/personas/{id}/playbooks` listet die 5 Links.
- Context: neu `scripts/brainstormer/import_to_who2be.py`.

**B3 — MCP-Endpoint-Verifikation gegen Hetzner**
- Outcome: `get_persona("brainstormer")`,
  `list_playbooks(tag="brainstorming")`, `fetch_playbook(id)` gegen
  `WHO2BE_API_BASE_URL=https://api.<domain>` liefern erwartete Daten.
  Skip-Test wenn Env nicht gesetzt.
- Context: neu `apps/mcp/tests/test_against_remote.py`.

**B4 — Claude-Chat-Smoke + Vergleichs-Baseline**
- Outcome: 3 vordefinierte Prompts werden im echten Claude-Chat
  einmal mit Notion-MCP und einmal mit Who2Be-MCP gefahren. Diff
  beider Antworten wird im RUNBOOK festgehalten. Bei Abweichung
  Rollback-Pfad (Notion-Konfiguration wieder aktivieren) dokumentiert.
- Context: `deploy/hetzner/RUNBOOK.md` (Acceptance-Section,
  Vergleichs-Tabelle).

### MS-5 — Web-Polish (Post-MVP, blockiert MVP nicht)

**P1 — `useListData<T>`-Extraktion**
- Outcome: Generischer Hook `apps/web/src/hooks/useListData.ts`;
  `usePersonas`, `usePlaybooks`, `useTokens` shrinken zu 1-Zeiler-
  Aufrufen. Vitest fuer Loading/Error/Success-Bahnen.
- Context: neu `apps/web/src/hooks/useListData.ts`, drei
  bestehende Hooks gekuerzt.
- Schliesst: Codebase-Review-Finding F3, F4 (Hook-Test-Luecke).

**P2 — Save-`disabled`-State + Backend-`detail`-Pass-through**
- Outcome: PersonaDetailPage und PlaybookDetailPage haben
  `saving`-State + `disabled={saving}`. `apps/web/src/api/client.ts`
  liest `{ "detail": ... }` aus JSON-Body und nutzt es als
  Fehler-Message.
- Context: `apps/web/src/pages/PersonaDetailPage.tsx`,
  `apps/web/src/pages/PlaybookDetailPage.tsx`,
  `apps/web/src/api/client.ts`, 2-3 neue Vitest-Cases.
- Schliesst: Codebase-Review-Findings F2, F5.

**P3 — PlaybooksPage-Test**
- Outcome: Vitest fuer Render + Tag-Filter in `PlaybooksPage`.
- Context: neu `apps/web/src/pages/PlaybooksPage.test.tsx`.
- Schliesst: Codebase-Review-Finding F4 (PlaybooksPage ohne Test).

---

## Quer durch alle Milestones

- **Test-Disziplin** unveraendert: Bei Bugfixes erst ein
  reproduzierender, fehlschlagender Test. Vor jedem Commit
  `uv run ruff check . && uv run mypy . && uv run pytest -q` bzw.
  `npm run lint && npx tsc --noEmit && npm test`.
- **Branch-/Commit-Konvention** unveraendert.
- **Notion-Doku:** Pro abgeschlossener Task ein Notes-Eintrag auf
  der Projekt-Seite, Pointer auf `.claude/plan/`-Detail-Plan.

## Verifikation der MVP-Completion-Condition

Unveraendert gegenueber dem alten Plan (Punkte 1-5), plus:

6. Caddy-Smoke (`test_headers.sh`) zeigt alle erwarteten Header und
   blockt `/v1/internal/*` extern (MS-3 H5).
7. `restic snapshots` listet einen Hetzner-Snapshot juenger als 26h
   (MS-2 C5b).
8. `H4`-Restore-Drill ist im RUNBOOK abgehakt.
9. Grafana RED-Dashboard ist erreichbar und zeigt > 0 Requests
   (MS-3 H7).
10. CI-Job "supply-chain" ist gruen ohne High/Critical (MS-3 H6).

## Hand-Off

- Detail-Pruefung gegen Code in den jeweiligen Task-Plans (eigene
  `.claude/plan/`-Dateien bei Pickup).
- Notion-Summary auf der PROJ-19-Seite (kurzer Block + Pointer
  hier).
- Notion-Tasks fuer MS-2 C5a/C5b/C6, MS-3 H4-H8, MS-4 B1-B4,
  MS-5 P1-P3 (= 15 Tasks). MS-5 als neue Milestone-Page.
</content>
</invoke>