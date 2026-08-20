# PROJECT — Aktuelles Vorhaben

_Primäre Heimat für Outcome, Why, Acceptance Criteria, Constraints und
Out of Scope des jeweils aktiven Vorhabens. Pro Vorhaben gepflegt; Historie
liegt in `.claude/plan/` und `docs/adr/`._

## Vorhaben: Public-Switch & erstes Release (v0.1.0)

Getrackt in den Issues #338–#341; Stand und Belege in
`.claude/context/STATE.md`.

### Outcome

Das Repository ist öffentlich, das erste Release `v0.1.0` ist getaggt und
veröffentlicht, und externe Contributor können über CLA, Issue-Forms und
CONTRIBUTING-Workflow beitragen.

### Why

Die Kern-App (Phasen 1–3), die Agenten-Achsen, MCP/OAuth, die
WorkArea-/KB-Achse und die Publish-Artefakte sind fertig; das Secrets-Gate
ist bestanden, die CI läuft seit 2026-08-16 wieder. Was fehlt, sind
Owner-Schritte (Settings, CLA, Flip) und die Release-Mechanik — nicht
Produktcode.

### Acceptance Criteria

1. **Owner-Schritte (#338):** Branch-Protection, Auto-delete head branches,
   Merge-Strategie, Description/Topics gesetzt; CLA-Assistant aktiv;
   Visibility Private → Public.
2. **Release-Blocker (#339):** erledigt (npm-audit clean,
   THIRD-PARTY-LICENSES.md, Pre-Publish-Nachweis dokumentiert).
3. **Publish-Artefakte (#340):** vollständig und englisch (README mit
   Badges, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, CHANGELOG,
   ROADMAP, Issue-Forms, OpenAPI-Referenz, docs-Index).
4. **Release-Mechanik (#341):** `v0.1.0`-Tag + GitHub-Release mit
   CI-grünem Lauf auf dem Release-Commit; E2E-Journeys scharf (Soft-Gate-
   Entscheidung beim Owner).

### Constraints

- Keine destruktiven GitHub-Aktionen ohne Owner (Visibility, Settings,
  Branch-Löschung bleiben Owner-Schritte).
- Lizenz bleibt FSL-1.1 (Apache 2.0 Future); CLA vor externen Beiträgen.
- Lokal = CI (Coverage-Ratchet, DoD in CONTRIBUTING).

### Out of Scope

- Cloud-Edition produktiv (Mollie-Billing live), Deploy-Live-Verifikation
  (`DEPLOY_HOST`), WP-14-Architektur-Backlog, OAuth-Phase 2 — siehe
  ROADMAP §Mid-term/Long-term.

---

## Abgeschlossen (zuletzt)

- **Externe Tools (MCP-Server-Bindings) + `tool-ref`-Placeholder** —
  umgesetzt mit PR #316 (ADR-0043); Blueprint
  `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`.
- **Agent WorkArea + Knowledge Base** (ADR-0047/0048/0049) — PR #367 ff.,
  Plan `.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md`.
