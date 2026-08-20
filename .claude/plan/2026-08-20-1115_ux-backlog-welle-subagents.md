# UX-Backlog-Welle mit Sub-Agents (2026-08-20)

**Status: in Umsetzung (Branch `claude/autonomous-code-agent-role-7l66oo`, PR #390)**
· Playbook: Code-Task-Flow (Orchestrierung) · Auftrag: offene Aufgaben mit
right-sized Sub-Agents abarbeiten.

## Inventar-Ergebnis (2 Recherche-Agenten, Sonnet)

**UX-Backlog-Plan `2026-06-27-1200` gegen Ist-Stand:** Wunsch 5
(System-Prompt-MCP-Tools) vollständig erledigt (ADR-0040); Wunsch 6
(Tool-Anker) obsolet — durch ExternalTool-Bindings (ADR-0043) ersetzt;
Wunsch 8 (Draft-on-Edit sichtbar) erledigt (ReviewBanner-Branch-Graph);
Wunsch 3 auf Capability-Ebene erledigt (`promote_retire`-Gate). Offen:
Draft-Discard (#7), Reviewer-Preset-UI, MCP-Docstring-DX (Modi- +
Body-Format), Gruppierung nach Tag/Agent, Multi-Tag-Filter, proaktive
Freigabe-Hinweise; Quick-Release widerspricht der dokumentierten State
Machine (`TRANSITION_RULE_DOC`) → Owner-Entscheidung.

**Web-Refactor (STATE-Folgelauf-Kandidat):** tote Bars bereits in Welle 1
(19.08.) gelöscht; verbleibend ist die Inline-Transition-Logik der
Personas-/Playbooks-Detailseiten. 1:1-Migration NICHT verhaltensneutral
(Button-Texte weichen ab: „Veröffentlichen/Draft abschließen" vs. zentral
„Aktivieren/Zur Review einreichen") → Lösung: optionaler Label-Override an
der zentralen `StatusActionBar`. **Defekt entdeckt:** die E2E-Journeys
klicken `branch-action-submit/-publish`, die heutige `PersonaDetailPage`
rendert Buttons ohne `data-testid` — der Persona-Lifecycle-Journey trifft
ins Leere.

## Design-Entscheidung (dokumentiert statt Rückfrage)

Button-Texte bleiben unverändert (Label-Override), KEINE stille
Text-Vereinheitlichung — gleiche Linie wie beim bewussten Auslassen der
`SystemPromptStatusActionBar` in Welle 1. Die Alternative
(Wording-Vereinheitlichung auf `common.statusBar.*`) ist eine sichtbare
UX-Änderung und bleibt als explizite Owner-Option notiert. → DECISIONS.md.

## Arbeitspakete (datei-disjunkt) + Modell-Wahl

| WP | Issue | Inhalt | Dateien (exklusiv) | Agent/Modell |
|---|---|---|---|---|
| W1 | neu | Personas-/Playbooks-Transitionen auf zentrale `StatusActionBar` (Label-Override-Prop), `branch-action-*`-Testids, E2E-Selektor-Fix; verhaltensneutral (bestehende i18n-Keys als Override-Werte, KEINE i18n-Datei-Änderung) | `components/version/*`, `features/personas/pages/*`, `features/playbooks/pages/*`, `features/playbooks/components/ReviewBanner*`, `components/data/BranchStatus*`, `e2e/journeys.spec.ts` | Sonnet (mechanischer Umbau mit klarer Spezifikation + vorhandenem Testnetz) |
| W2 | neu | MCP-Docstring-DX: Modi-Schema in `create/update_persona`, kanonisches Body-/Placeholder-Format in `create/update_playbook` + `create/update_resource` (analog System-Prompt-Doku); Payload-Budget-Test beachten | `apps/mcp/src/who2be_mcp/server.py` (+ zugehörige mcp-Tests) | Sonnet (Doku-Präzision gegen echte Schemas, sonst mechanisch) |
| W3 | neu | Tag-Gruppierung: Playbooks-Gruppierungsmodus `tag` ergänzen; Resources bekommen Gruppierung (mind. `tag`, client-seitig); Agent-Gruppierung nur, falls ohne Backend-/N+1-Änderung möglich — sonst berichten | `features/playbooks/lib/grouping.ts`, `PlaybooksPage`, `PlaybookListToolbar`, `features/resources/**`, `i18n/locales/*` | Sonnet |
| W4 (Welle 2, nach W3) | neu | Reviewer-Preset im Agent-Policy-Editor: Preset-Auswahl (z. B. „Nur lesen" / „Editor ohne Freigabe" / „Editor mit Freigabe"), setzt Capability-Kombis inkl. `promote_retire`; reine UI, kein Backend | `features/agents/**`, `i18n/locales/*` | Sonnet |

Wellen: W1+W2+W3 parallel (disjunkt; W1 ohne i18n-Edits). W4 danach
(teilt `i18n/locales/*` mit W3). Konsolidierung (Fable, selbst): Review
gegen Issues, Integrations-Checks (`eslint`, `tsc`, volle Vitest-Suite,
`ruff`/`mypy`/pytest für W2), Standards-Drift, dann Commit/Push auf PR #390.

## Bewusst NICHT in dieser Welle (mit Grund)

- **Draft-Discard (#7):** destruktiver DB-Endpoint; Integrationstests ohne
  Postgres nicht ausführbar + CI tot = kein Sicherheitsnetz. Erste
  Python-Aufgabe nach CI-Wiederbelebung.
- **Quick-Release:** widerspricht dem dokumentierten State-Machine-Vertrag
  — Owner-Entscheidung nötig.
- **Proaktive Pflichtfeld-Hinweise (#9):** Design offen + kollidiert mit W1
  auf `StatusActionBar` — Folgewelle.
- **Backend-Normalisierung Playbook-Bodies, Multi-Tag-Filter (Backend),
  Batch-Gruppierungs-Aggregat:** DB-/API-Arbeit, gleiche Begründung wie #7.

## Verify (Konsolidierung, transkript-nachweisbar)

`npm run lint` 0 Errors · `npx tsc --noEmit` + Build · volle
`npm run test:coverage` mit Floors · gezielter e2e-Typ-Check ·
`uv run ruff check` + `mypy` + pytest (W2) · Diataxis-/Standards-Sichtung
der Diffs · testids der E2E-Journeys existieren im DOM (Vitest-Assertion).
