# Dashboard: Aufmerksamkeits-Band um Memory-Freigaben + System-Prompt-Reviews erweitern

**Datum:** 2026-07-22 · **Branch:** `claude/autonomous-code-agent-setup-e9b9y7` · **Status:** umgesetzt

## Ziel / Completion-Condition

Das Dashboard-Band „Braucht jetzt deine Aufmerksamkeit" zeigt zusätzlich zu den
offenen Reviews (persona/playbook/resource) zwei neue Hinweise, sobald es etwas
zu tun gibt:

1. **Neue Gedächtniseinträge:** `agent_memory`-Zeilen im Status `pending`
   (Freigabe-Schleuse, ADR-0044) im aktuellen Workspace → Banner mit Anzahl +
   Link zu `/agents` (Triage lebt in der Agent-Detail-Seite,
   `AgentMemorySection`).
2. **System-Prompts brauchen Aufmerksamkeit:** System-Prompt-Templates, deren
   aktuelle Version im Status `review` steht (analog `pending_reviews`) →
   Banner mit Anzahl + Link zu `/system-prompts?status=review` (die Liste
   unterstützt den URL-Status-Filter via `useListFilters`).

„Alles erledigt" erscheint nur noch, wenn **alle drei** Signale 0 sind.

Messbar: neue KPI-Felder im Dashboard-Aggregat + gerenderte Banner, belegt
durch pytest- und Vitest-Tests; alle Gates (ruff/mypy/pytest ≥85 %,
lint/tsc/vitest/build) lokal grün.

## Design-Entscheidung (dokumentiert, nicht blockierend)

Semantik „braucht Aufmerksamkeit":

- **Gewählt:** Memories = Status `pending` (exakt die Freigabe-Schleuse);
  System-Prompts = aktuelle Version in `review` — konsistent zur bestehenden
  `pending_reviews`-Semantik der übrigen Aggregate.
- Verworfen A: Drafts mitzählen → Drafts sind Arbeitsstand des Autors, kein
  Handlungsbedarf Dritter; würde das Band verwässern.
- Verworfen B: per-Agent-Aufschlüsselung der pending Memories im Dashboard →
  mehr API-Fläche für wenig Mehrwert; die Agents-Liste ist einen Klick
  entfernt. Bei Bedarf späterer Ausbau.

## Schritte

1. **Models** (`packages/models/.../dashboard.py`): `DashboardKpis` +
   `pending_memories` und `pending_system_prompts` (beide `ge=0, default=0` —
   rückwärtskompatibel).
2. **Repository** (`dashboard_repository.py`): neue Protocol-Methode
   `attention_counts(workspace_id) -> tuple[int, int]`; eine Query mit zwei
   Scalar-Subselects (ein Roundtrip): COUNT über `agent_memory`
   (`status='pending'`) und COUNT über Templates mit
   `version = current_version AND status='review'`.
3. **Service** (`dashboard_service.py`): `attention_counts` in das bestehende
   `asyncio.gather` aufnehmen, Werte in `DashboardKpis` mappen.
4. **API-Tests:** `test_dashboard_service.py` (FakeRepo + Mapping),
   `test_dashboard_endpoint.py` (Baseline-KPIs um neue Felder ergänzen; neuer
   Integrationstest: pending Memory am Seed-Builder-Agenten + Template in
   Review → Zählwerte + Workspace-Isolation).
5. **Web-Typen** (`api/types.ts`): `DashboardKpis` + optionale Felder.
6. **DashboardPage:** Attention-Band rendert bis zu drei Banner (Reviews wie
   gehabt; Memories mit Brain-Icon + Aktion „Agenten öffnen"; System-Prompts
   mit ScrollText-Icon + Aktion „Zur Review"); „Alles erledigt" nur bei 0/0/0.
7. **Web-Tests:** `DashboardPage.test.tsx` um beide Banner-Fälle + Links
   erweitern; Alles-erledigt-Fall abgesichert.
8. **Gates:** `uv run ruff check . && uv run mypy .`, `uv run pytest --cov
   --cov-fail-under=85`; in `apps/web`: `npm run lint`, `npx tsc --noEmit`,
   `npm run test:coverage`, `npm run build`.
9. **Doku:** STATE.md aktualisieren, PR öffnen (Draft), Board/Issue-Pflege.

## Ergebnis-Log

- Schritte 1–7 wie geplant umgesetzt; keine Abweichungen. Neue KPI-Felder
  `pending_memories`/`pending_system_prompts` (Backend default 0, Web-Typen
  optional) — rückwärtskompatibel in beide Richtungen.
- Repo: `_ATTENTION_COUNTS` als ein Roundtrip mit zwei Scalar-Subselects;
  Service nimmt die Query in das bestehende `asyncio.gather` auf.
- **DoD-Belege (lokal, 2026-07-22):** ruff ✓ · mypy ✓ (334 files) ·
  pytest 1100 passed, Coverage **90,25 %** (Gate 85, gegen lokale
  Postgres-16-Instanz inkl. neuem Integrationstest
  `test_dashboard_counts_pending_memories_and_system_prompt_reviews`) ·
  Web: eslint 0 Errors (55 Warnings = Baseline von main) · tsc ✓ ·
  Vitest 912 passed + Coverage-Gate ✓ · `npm run build` ✓.
- Hinweis Umgebung: Docker fehlt in der Remote-Session; für die
  Integrationstests wurde ein lokaler Postgres-16-Cluster
  (`/var/lib/postgresql/pgdata`, User `postgres`/`postgres`, DB `who2be`)
  gestartet.
