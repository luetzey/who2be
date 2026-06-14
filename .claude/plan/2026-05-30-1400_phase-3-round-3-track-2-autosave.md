# Phase-3 Runde 3 — Track 2: Auto-Save + Git-Style Status-Flow

Branch: `feat/auto-save-git-status-flow` (cloud session: `claude/intelligent-bardeen-j6Jwt`)

Eltern-Plan: `.claude/plan/2026-05-30-1130_phase-3-round-3-ideas.md` §Track 2.

## Outcome (Acceptance)

1. Auto-Save: Drafts werden während des Tippens automatisch gespeichert
   (Debounce 1500 ms + Flush bei `beforeunload`/window-blur/unmount).
2. Save-Button ist weg. UI-Indikator: `idle | saving | saved | error`
   (aria-live).
3. `BranchStatus`-Komponente löst `StatusActionBar` auf den Detail-Pages
   ab, visualisiert wie Git (`v3 active / v4 draft`) und bietet die
   Actions `[Draft abschliessen]`, `[Veroeffentlichen]`, `[Zurueck zu
   Draft]`, `[Reaktivieren als Draft]` abhängig vom Status.
4. Active-Version bleibt unangetastet bis Publish.
5. Keine Regression in bestehenden Status-Tests; PUT-Semantik bleibt am
   Backend unverändert (Plan-Eintrag: "Submit-Verhalten unveraendert").
6. Beide Stacks grün (`uv run ruff/mypy/pytest`, `npm run lint/tsc/test/build`).

## Architektur-Entscheidungen

- **PUT bleibt am Backend wie gehabt** (Draft-on-Edit aus Active, 409 bei
  bestehendem Draft). Frontend ruft PUT nicht mehr — `Draft abschliessen`
  nutzt den existierenden Transition-Endpoint. Begründung:
  - Bestehende Test-Suite bleibt grün (siehe
    `test_persona_put_on_active_creates_draft_and_blocks_second_edit`).
  - PATCH/transition decoupled — eine Verantwortung pro Endpoint.
- **PATCH-Verhalten**: `upsert_draft`.
  - Kein Draft vorhanden → neue Version (`current_version + 1`) als
    `draft`, `current_version` rückt nach. Active wird nicht angefasst
    (kein Auto-Inactivieren — das passiert erst bei Publish).
  - Draft vorhanden → in-place Update der Draft-Row, **kein**
    Version-Increment.
  - 404 wenn Entity nicht existiert. Sonst keine 409-Fälle (single-user-
    Vereinfachung Phase 1 — siehe Plan §"Offen — Konflikt-Handling").
- **„Draft verwerfen"** (DELETE-draft-Endpoint) ist Folgeticket — Button
  wird in der ersten Iteration **nicht** gerendert. Notiz im Code-
  Kommentar.
- **„Neuer Draft" auf Active** entfällt als expliziter Button — der
  erste Edit triggert PATCH und erzeugt den Draft automatisch.

## Backend (apps/api)

### Neue Routes

```
PATCH /v1/workspaces/{ws}/personas/{id}/draft     → PersonaUpdate body
PATCH /v1/workspaces/{ws}/playbooks/{id}/draft    → PlaybookUpdate body
PATCH /v1/workspaces/{ws}/resources/{id}/draft    → ResourceUpdate body
```

Response: `{Persona,Playbook,Resource}Read` mit Status-Feldern.

### Repository

Neue Methode pro Repo (`upsert_draft`):

- Transaction, `FOR UPDATE OF p` auf Identitäts-Zeile.
- `existing_draft_version = SELECT version FROM .._version WHERE status='draft'`
  - Wenn vorhanden → `UPDATE .._version SET content=$, … WHERE version=draft_version`.
    Identitäts-Zeile bleibt unverändert (current_version zeigt schon auf den Draft).
  - Sonst → `INSERT INTO .._version (version=current+1, status='draft', …)`,
    `UPDATE .. SET current_version=current+1, name=COALESCE($,name), updated_at=now() WHERE id=$`.
- Active wird nie modifiziert (kein Auto-Inactivieren — das macht erst die
  Publish-Transition).
- Rückgabe: gleicher Outcome-Wrapper-Typ wie `update`, `conflict=None`
  semantisch nie gesetzt.

Edge-Cases dokumentiert:
- Current=active, kein Draft → neue Draft v(n+1), Active bleibt v(n).
- Current=draft → in-place Update.
- Current=review → in-place Update? Nein — Review-Version wird NICHT
  überschrieben, der Editor sollte hier nicht editieren. Frontend verhindert
  das. Sicherheitshalber: wenn Current=review **und** kein Draft existiert,
  geben wir 409 zurück (kein PATCH auf Review-State ohne expliziten
  „Zurück zu Draft"). Das ist ein Pflicht-Edge-Case zum Dokumentieren.
- Current=inactive → es kann gar keinen Draft geben (Active fehlt
  ebenfalls), neue Draft v(n+1) wird angelegt.

### Service

`update_draft(ctx, id, data)` parallel zu `update(...)`:
- Selber RBAC-Gate (`editor`+).
- Mapped `conflict='review_pending'` → 409.
- Mapped `None` → 404.

PUT (`update`) bleibt unverändert.

### Tests (`apps/api/tests`)

Ergänzungen in `test_personas.py`, `test_playbooks.py`, `test_resources.py`:

- `test_<entity>_patch_draft_upserts_in_place` — zwei PATCH-Calls,
  `current_version` bleibt konstant beim zweiten, Content sieht den
  zweiten Body.
- `test_<entity>_patch_draft_creates_draft_from_active_without_touching_active`
  — Active auf v1 promoten, PATCH liefert v2 draft, v1 bleibt active.
- `test_<entity>_patch_draft_review_state_returns_409` — Edge-Case.
- `test_<entity>_patch_draft_cross_workspace_404` — Tenant-Isolation.

## Frontend (apps/web)

### `api/client.ts`

```ts
patchPersonaDraft(id, input): Promise<Persona>
patchPlaybookDraft(id, input): Promise<Playbook>
patchResourceDraft(id, input): Promise<Resource>
```

Pfade: `PATCH ${ws}/{entity}s/${id}/draft`.

### `hooks/useAutoSaveDraft.ts` (neu, generic)

Signatur:
```ts
function useAutoSaveDraft<T>(opts: {
  values: T
  isReady: boolean                   // erst speichern, wenn die Form-
                                       // Daten initialisiert sind (sonst
                                       // wirft form.reset einen leeren
                                       // PATCH).
  patchFn: (input: T) => Promise<void>
  debounceMs?: number                // default 1500
}): {
  status: 'idle' | 'saving' | 'saved' | 'error'
  lastSavedAt: Date | null
  errorMessage: string | null
  flush: () => Promise<void>
}
```

Implementierung:
- `useEffect` auf `values`: setTimeout(1500ms). Bei Re-Trigger Timeout
  abbrechen.
- `flush()` führt den PATCH sofort aus (für blur/unmount/beforeunload).
- `beforeunload`-Listener flusht ohne await; `window.blur`-Listener flusht
  async; Cleanup beim unmount.
- Werte-Vergleich: speichert nur, wenn sich der serialisierte Wert seit dem
  letzten erfolgreichen Save geändert hat — kein leerer PATCH nach
  Re-Render.

### `components/data/BranchStatus.tsx`

Props:
```ts
interface BranchStatusProps {
  activeVersion?: number
  draftVersion?: number
  reviewVersion?: number
  inactiveVersion?: number
  currentVersion: number
  saveState: { status: 'idle' | 'saving' | 'saved' | 'error'; lastSavedAt: Date | null; errorMessage: string | null }
  actions: BranchAction[]
}
interface BranchAction {
  key: string
  label: string
  onClick: () => void
  variant: 'brand' | 'default' | 'outline' | 'destructive'
  disabled?: boolean
}
```

Render:
- Branch-Linie (textuell): `● v3 active ── ○ v4 draft (du)`.
- Action-Buttons als `<Button>`-Reihe (Toolbar mit `role="toolbar"`).
- aria-live="polite"-Region mit Save-Status-Text
  („Speichert …" / „Gespeichert vor 4 s" / „Fehler: …").

### `hooks/usePersonaForm.ts` etc.

- `onSubmit` entfällt.
- Statt dessen wird `form.watch()` in `useAutoSaveDraft` reingereicht.
- Hook gibt `{ form, autoSave }` zurück.

### DetailPages

- Submit-Button raus.
- `StatusActionBar` ersetzt durch `BranchStatus`. Action-Mapping:
  - Draft existiert → `[Draft abschliessen]` (transition draft→review).
  - Review existiert → `[Veroeffentlichen]` + `[Zurueck zu Draft]`.
  - Nur Inactive current → `[Reaktivieren als Draft]` (inactive→draft).
- Header-Description: `"Active: vN · Du arbeitest auf Draft: vM · ⏺ saved (vor 4s)"`.

### Tests

- `useAutoSaveDraft.test.tsx`: Debounce, Flush bei unmount, kein PATCH
  bei unveränderten Werten, Error-Recovery.
- `BranchStatus.test.tsx` + `BranchStatus.a11y.test.tsx`.
- DetailPage-Integrationstests pro Entity: PATCH debounced, „Abschliessen"
  ruft Transition.

## DoD

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`,
  `uv run pytest -q`.
- `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`.

## Vorgehen (chronologisch)

1. Backend Repository `upsert_draft` (Persona zuerst, dann Playbook,
   Resource — copy-pattern).
2. Backend Service + Router PATCH (drei Entities parallel).
3. Backend-Tests.
4. Frontend `api/client.ts` + Hook `useAutoSaveDraft` + Test.
5. Frontend `BranchStatus` + Tests.
6. Hooks `usePersonaForm`/`usePlaybookForm`/`useResourceForm` umbauen.
7. DetailPages umbauen.
8. EditorForm-Komponenten: Save-Button raus, bestehende Tests anpassen.
9. Lint/Typecheck/Build/Test beide Stacks grün.
10. Commit + push.
