# Agent-Prompts — Phase-3 Runde 3 (3 parallele Agenten)

Plan: `.claude/plan/2026-05-30-1130_phase-3-round-3-ideas.md`
(volle Architektur-Begruendung + offene Fragen).

## Parallelitaet

- **Alle drei Agenten parallel startbar.** Disjunkte Datei-Sets.
- Einziger Konflikt: Track 2 beruehrt `PersonaEditorForm.tsx`, das auch
  Track 1 anfasst. Track 1 ist sehr klein (`key`-Prop + Tests); Track 2
  rebased darauf, sobald Track 1 gemergt ist.

| Agent | Track | Datei-Schwerpunkt |
|---|---|---|
| **A — Editor-Hydration-Bugfix** | 1 | `PersonaEditorForm.tsx` + Test |
| **B — Auto-Save + Git-Status** | 2 | DetailPages + Form-Hooks + Backend-PATCH |
| **C — Agent + Template** | 3 | Neue Domain (Backend + Frontend + Migration) |

---

## Agent A — Persona-Editor-Hydration-Bugfix

```
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md (Notion-Persona +
Playbooks). Lies vor jeder Aenderung den Plan
`.claude/plan/2026-05-30-1130_phase-3-round-3-ideas.md`, Abschnitt
**Track 1**.

Ziel: Persona-Profil und System-Prompt werden nach Save + Reload wieder
korrekt im Editor angezeigt — heute bleibt der BlockNote-ProseMirror-
State auf dem alten Inhalt haengen, weil `useCreateBlockNote` nur beim
ersten Mount initialisiert.

Root-Cause (verifiziert): `apps/web/src/features/personas/components/
PersonaEditorForm.tsx` instantiiert `ResourceEditor` und
`SystemPromptEditor` ohne `key`-Prop. `ResourceDetailPage.tsx:127` zeigt
das richtige Pattern: `key={`${resource.id}-${resource.current_version}`}`.

Scope:
- `apps/web/src/features/personas/components/PersonaEditorForm.tsx`
  * Neue Required-Prop `formKey: string`.
  * Beide BlockNote-Wrapper bekommen `key={formKey}`.
- `apps/web/src/features/personas/pages/PersonaDetailPage.tsx`
  * Setzt `formKey={`${persona.id}-${persona.current_version}`}`.
- **Pruefen**, ob `PlaybookEditorForm` denselben Bug hat —
  `apps/web/src/features/playbooks/components/PlaybookEditorForm.tsx`
  + `PlaybookDetailPage.tsx`. Falls ja, identisch fixen.
- Tests:
  - `PersonaEditorForm.test.tsx`: Mock fuer BlockNoteEditor (z. B.
    `<div data-testid="bn">{JSON.stringify(initialBlocks)}</div>`),
    Test: `formKey`-Wechsel rendert neue initialBlocks.
  - Falls Playbook gefixt: analoger Test in `PlaybookEditorForm.test.tsx`.

Acceptance:
- Persona anlegen → Profil editieren → Save → reload Page-Komponente →
  Profil-Inhalt sichtbar.
- System-Prompt analog.
- Keine Behavior-Aenderung an `useCreateBlockNote`-Optionen (kein
  React-Anti-Pattern).

DoD: `npm run lint && npx tsc --noEmit && npm test -- --run && npm run build`.

Branch: `fix/persona-editor-rehydrate`
Commits: Conventional Commits, deutsche Imperative.
PR-Body: Summary, Test plan, Plan-Datei-Link.
```

---

## Agent B — Auto-Save Draft + Git-Style Status-UX

```
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-1130_phase-3-round-3-ideas.md`, Abschnitt
**Track 2** — inkl. Git-Mental-Modell-Tabelle und der Tests-Sektion.

WICHTIG: Erst starten, wenn Track 1 (`fix/persona-editor-rehydrate`)
auf main ist — gleiche Datei `PersonaEditorForm.tsx`. Rebase auf den
aktuellen main, bevor du das anfasst.

Ziel: Drafts werden waehrend des Tippens automatisch gespeichert
(Debounce 1500 ms + Flush bei blur/unmount). Der explizite Save-Button
verschwindet. Statt dessen gibt es eine BranchStatus-Komponente, die
den Stand wie Git visualisiert ("v3 active / v4 draft, du bearbeitest")
und die Actions `[Draft abschliessen]`, `[Draft verwerfen]`,
`[Veroeffentlichen]`, `[Zurueck zu Draft]`, `[Neuer Draft]` anbietet —
abhaengig vom aktuellen Status.

Scope:
- Backend:
  - Neue Route je Entity:
    - `PATCH /v1/workspaces/{ws}/personas/{id}/draft`
    - `PATCH /v1/workspaces/{ws}/playbooks/{id}/draft`
    - `PATCH /v1/workspaces/{ws}/resources/{id}/draft`
    Verhalten: Draft-Row upsert (`current_version + 1` falls keiner
    existiert, sonst Update in-place). Active bleibt unangetastet.
    409 nur fuer "kein Draft moeglich" (Edge-Cases dokumentieren).
  - `repositories/persona_repository.py` & Geschwister: neue
    `upsert_draft`-Methode (Logik nahe an existierender `update`,
    aber ohne Version-Increment auf bestehenden Draft).
  - `services/persona_service.py` & Geschwister: trennt klar
    `update_draft` (PATCH) vs `submit_for_review` (PUT → Status-Wechsel).
  - PUT bleibt erhalten, semantisch jetzt: "Draft fertigstellen + Submit
    for Review" (Status-Transition `draft → review`).
  - Migrationen: KEINE notwendig.
  - Tests in `apps/api/tests/test_personas.py`, `test_playbooks.py`,
    `test_resources.py`: PATCH-Flow (upsert, kein Active-Touch, Tenant-
    Isolation), Submit-Verhalten unveraendert.
- Frontend:
  - `apps/web/src/api/client.ts`: drei neue Methoden
    `patchPersonaDraft`, `patchPlaybookDraft`, `patchResourceDraft`.
  - Neuer Hook `apps/web/src/hooks/useAutoSaveDraft.ts`:
    - Generisch ueber Entity-Typ; nutzt `useEffect` + `setTimeout` mit
      `1500ms`-Debounce; flush bei `beforeunload` + on-blur (window-blur,
      nicht field-blur) + bei `unmount`.
    - State: `{ status: 'idle' | 'saving' | 'saved' | 'error',
      lastSavedAt?: Date, errorMessage?: string }`.
    - Akzeptiert eine `patchFn`, damit wir die Methode pro Entity injizieren.
  - Neue Komponente `apps/web/src/components/data/BranchStatus.tsx`:
    - Props: `activeVersion?`, `draftVersion?`, `currentVersion`,
      `actions: BranchAction[]`.
    - Rendert das Git-aehnliche Diagramm (klein, textuell — kein SVG
      noetig) und die Action-Buttons.
    - `aria-live="polite"` Region fuer den Save-Status.
  - `usePersonaForm` / `usePlaybookForm` / `useResourceForm`:
    - Entfernt `onSubmit`-Handler.
    - Verdrahtet `useAutoSaveDraft` mit `form.watch`.
  - `PersonaDetailPage` / `PlaybookDetailPage` / `ResourceDetailPage`:
    - Header zeigt: `<Name> · Active: vN · Du arbeitest auf Draft: vM ·
      ⏺ saved (vor Ns)` (oder Saving / Error).
    - `StatusActionBar` wird durch `BranchStatus` ersetzt; identische
      Transitions, andere Optik.
  - `PersonaEditorForm` / `PlaybookEditorForm` / `ResourceEditor`:
    - Submit-Button raus. Form bleibt unbeschnitten; Auto-Save uebernimmt.
- Tests:
  - Vitest: `useAutoSaveDraft.test.tsx` (Debounce, Flush bei unmount,
    Error-Retry, kein Server-Call bei unveraenderten Werten).
  - Vitest: `BranchStatus.test.tsx` + `*.a11y.test.tsx`.
  - Vitest: DetailPage-Integration je Entity (PATCH wird debounced,
    "Abschliessen" loest PUT aus, "Verwerfen" loest DELETE der Draft aus
    *falls dieser Endpoint schon existiert* — sonst Folgeticket).
  - Pytest: PATCH-Endpoints pro Entity.

Acceptance:
- Auto-Save sichtbar (Indikator wechselt), Server speichert in-place.
- Tab schliessen waehrend des Tippens → Re-open → Draft-Inhalt da.
- "Draft abschliessen" → Status `review`; "Veroeffentlichen" → Active
  wechselt, alte Active wird `inactive`.
- Active-Version bleibt unangetastet bis Publish.
- Keine Regression in bestehenden Status-Tests.

DoD: Beide Stacks gruen
(`uv run ruff/mypy/pytest` + `npm run lint/tsc/test/build`).

Branch: `feat/auto-save-git-status-flow`
```

---

## Agent C — Agent + SystemPromptTemplate-Hierarchie

```
Du bist Coder. Folge dem Coder-Bootstrap in CLAUDE.md. Lies den Plan
`.claude/plan/2026-05-30-1130_phase-3-round-3-ideas.md`, Abschnitt
**Track 3** — inkl. Domain-Diagramm, Placeholder-Tabelle und Routen-
Liste.

Ziel: Neues Domain-Konzept einfuehren. Agents sind die Top-Level-Konfig
(1:1 Persona, 1:1 SystemPromptTemplate). Templates haben Liquid-Style-
Placeholders. "Kopieren" rendert den finalen Prompt (Server-side
substitute) und kopiert ihn in die Zwischenablage.

Existierende Konzepte (Persona, Playbook, Resource, Workspace-Memberships)
bleiben unangetastet. `persona.system_prompt` bleibt das Persona-eigene
Voice-Statement und wird als Placeholder-Wert `{{ persona.system_prompt }}`
geliefert.

Scope:
- Migrationen:
  - `apps/api/src/who2be_api/migrations/0022_system_prompt_template.sql`
    (template + template_version analog zu persona/persona_version,
    workspace_id-FK, status-Enum).
  - `apps/api/src/who2be_api/migrations/0023_agent.sql`
    (agent: id, workspace_id, name, description, persona_id FK,
    system_prompt_template_id FK, status text NOT NULL DEFAULT 'enabled',
    created_at, updated_at).
- Models (`packages/models/src/who2be_models/`):
  - `system_prompt_template.py` (Content, Read, Create, Update, VersionRead).
  - `agent.py` (AgentRead, AgentCreate, AgentUpdate, AgentRenderResponse).
  - Re-export aus `__init__.py`.
- Backend:
  - Repository + Service + Router je Entity (analog persona). Versions-
    Logik fuer Template wie persona (mit Auto-Save aus Track 2 nur,
    wenn Track 2 schon gemergt ist — sonst klassisches PUT + Status-
    Transition fuer V1).
  - **Render-Service** `services/agent_render_service.py`:
    - Inputs: Agent → lade Template (current_version) + Persona
      (current_version) + verlinkte Playbooks + Resource-Blocks.
    - Placeholder-Aufloeser:
      - `{{ persona.name }}`, `{{ persona.description }}`,
        `{{ persona.system_prompt }}`, `{{ persona.profile }}`
        (via `blocks_to_plain_text` aus dem Models-Package; ggf. neuer
        Helper), `{{ persona.tags }}` (Komma-getrennt),
        `{{ playbooks }}` (alle Playbooks: "### NAME\nDESCRIPTION\nBODY"),
        `{{ resources }}` (deduplizierte Section-Snippets aus Playbook-
        Resource-Block-Refs).
      - Unbekannte Placeholders bleiben als Klartext, im Output mit
        `⚠ {{ unknown_field }}` markiert.
    - Output: `{ content: str, unresolved_placeholders: list[str] }`.
  - Endpoint `GET /v1/workspaces/{ws}/agents/{id}/render`.
  - MCP-Tool (optional, nur wenn Zeit reicht): `render_agent_prompt`
    als read-only Tool im `apps/mcp/src/who2be_mcp/server.py`.
- Frontend (`apps/web/src/features/agents/` + `system-prompts/`):
  - `system-prompts/`: pages (ListPage, NewPage, DetailPage), hooks
    (`useSystemPrompt`, `useSystemPromptForm`), components
    (`SystemPromptEditorForm` mit Placeholder-Hint-Tooltip,
    `PlaceholderHelp.tsx`).
  - `agents/`: pages, hooks, components
    (`AgentHierarchyView.tsx` rendert den Baum aus dem Plan-§
    "Agent-Detail-Page"; `CopyPromptButton.tsx` ruft `/render` und
    schreibt ins Clipboard).
- Routen (`apps/web/src/app/routes.tsx`):
  - `/w/:ws/agents`, `/w/:ws/agents/new`, `/w/:ws/agents/:id`.
  - `/w/:ws/system-prompts`, `/w/:ws/system-prompts/new`,
    `/w/:ws/system-prompts/:id`.
- Navigation (`apps/web/src/components/layout/AppShell.tsx`):
  - Zwei neue Nav-Items: `Agents` (Bot-Icon), `System-Prompts`
    (FileText-Icon).
- Tests:
  - Pytest: Migration-Forward, CRUD beide Entities, Tenant-Isolation,
    Permission-Matrix (Admin+Editor schreiben, Viewer nur lesen),
    Placeholder-Renderer (Unit-Tests pro Placeholder + Unknown-Fall +
    leeres Persona-Profil),
    `GET /agents/{id}/render` (200, unresolved_placeholders korrekt).
  - Vitest: AgentHierarchyView-Render (Mock-Data fuer Persona + 2
    Playbooks + 1 Resource), CopyPromptButton (clipboard-API mocken,
    Toast pruefen), Template-Editor mit Placeholder-Hint.
- Catalog-Showcase: optional, Placeholder-Help als eigene Demo-Page.

Acceptance:
- E2E manuell:
  1. Template anlegen mit Body
     `"Du bist {{ persona.name }}. {{ persona.system_prompt }}\n\nKenntnisse:\n{{ playbooks }}"`.
  2. Persona "Coach Carla" mit System-Prompt + verlinkten Playbooks.
  3. Agent anlegen, Persona + Template verknuepfen.
  4. Auf Agent-Detail "Prompt kopieren" → Clipboard enthaelt aufgeloeste
     Version, Persona-Name + Persona's Prompt + Playbook-Blocks drin,
     keine Placeholders im Output.
- Tenant-Isolation: Cross-Workspace 403/404.
- Viewer-Rolle kann Agent ansehen + Prompt kopieren, aber nicht editen.

DoD: Beide Stacks gruen
(`uv run ruff/mypy/pytest` + `npm run lint/tsc/test/build`).
Migrationen via `docker compose up -d --build --wait` auf frischer
DB + Bestandsdaten getestet.

Branch: `feat/agent-template-domain`
```

---

## Offene Fragen (vor Implementierung mit dem User klaeren)

Aus dem Plan §"Offen — bitte bestaetigen":

1. Reichen die 7 Standard-Placeholders fuer Phase 1?
2. Hard-Limit pro Workspace fuer Agents?
3. Default-Template-Bibliothek seedem oder leer starten?
4. Copy-Output Plain Text (Empfehlung) oder Markdown?

Falls die Antworten kommen, **bevor** Agent C startet, in den Prompt
oben einbauen. Sonst nutzt Agent C die Plan-Defaults und sammelt
Followups.
