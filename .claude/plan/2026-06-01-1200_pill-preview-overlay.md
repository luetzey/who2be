# Plan: Pill-Preview-Overlay im BlockNote-Editor

**Stand:** 2026-06-01 · living document
**Ziel:** Klick auf eine Inline-Pill öffnet ein read-only Overlay, das den
**aufgelösten Output** des Platzhalters zeigt (kein Editieren). Gilt in allen
Editoren mit Pills (`SystemPromptEditor` + `PlaybookBodyEditor`).

## Outcome / Completion-Condition (messbar)

- Neuer Endpoint `GET /v1/workspaces/{ws}/placeholders/preview` liefert für ein
  einzelnes `{kind, target_id}` den aufgelösten Text + `unresolved`-Flag.
- Klick auf eine Pill in beiden Editoren öffnet einen Dialog mit diesem Text.
- DoD beider Stacks grün: `uv run ruff check . && uv run mypy . && uv run pytest -q`
  und `npm run lint && npx tsc --noEmit && npm test && npm run build`.

## Design-Entscheidung (Begründung statt 3-Optionen-Rückfrage)

- **Overlay = bestehendes `Dialog`-Primitive** (kein neues `@radix-ui/react-popover`):
  konsistent mit den Picker-Dialogen, Portal-sicher (kein overflow-Clipping im
  `bn-container`), `shadow-modal`-Token existiert bereits. Nur-Vorschau braucht
  kein Anker-Popover.
- **Pill→Wrapper-Signal = CustomEvent `placeholder-click`** (genau der im
  Code-Kommentar `PlaceholderBlock.tsx:72` vorgesehene Mechanismus): entkoppelt
  die BlockNote-Inline-Render-Funktion vom React-State des Wrappers; bubblet zum
  `bn-container`, wo ein nativer Listener ihn abfängt.
- **Resolving = bestehende `REGISTRY`-Resolver wiederverwenden** — kein neues
  Resolving. Der Preview-Service ruft `REGISTRY[kind].resolve(...)` direkt auf
  (Single-Placeholder), nicht `render_template_body` (das ist für ganze Bodies).
- **persona-field ohne Persona-Kontext:** In beiden Editoren gibt es keine feste
  Persona → Resolver liefert Miss (`unresolved=true`, leerer Text). Das Overlay
  zeigt dafür einen erklärenden Hinweis statt Leere. `persona_id` ist optionaler
  Query-Param (für spätere Agenten-Kontexte vorbereitet).

## Arbeitspakete

### A — Backend (datei-disjunkt)
1. `apps/api/src/who2be_api/services/placeholder_preview_service.py` (neu):
   `PlaceholderPreviewResponse(kind, target_id, text, unresolved)` +
   `PlaceholderPreviewService.preview(ctx, kind, target_id, persona_id)`.
   Unbekanntes `kind` → `HTTPException 422`.
2. `apps/api/src/who2be_api/routers/placeholders.py` (neu): `GET /placeholders/preview`.
3. `apps/api/src/who2be_api/main.py`: Router unter `_WORKSPACE_PREFIX` registrieren.
4. `apps/api/tests/test_placeholder_preview.py` (neu, integration, skip-if-no-db):
   date/ISO+human, tools-overview, playbook-Miss, unknown-kind→422, unauth→401.

### B — Frontend API-Schicht
5. `apps/web/src/api/types.ts`: `PlaceholderPreview { text: string; unresolved: boolean }`.
6. `apps/web/src/api/client.ts`: `previewPlaceholder({kind, target_id, persona_id?})`.
7. `apps/web/src/api/useApi.ts` / Api-Interface: Methode aufnehmen.

### C — Frontend UI
8. `apps/web/src/components/editor/system-prompt/PlaceholderBlock.tsx`: `onClick`
   im Pill-`<span>` → dispatcht `placeholder-click`-CustomEvent (bubbles) mit
   `{kind, target_id, label}`. Konstante Event-Name + Detail-Typ exportieren.
9. `apps/web/src/components/editor/system-prompt/PlaceholderPreviewDialog.tsx` (neu):
   nimmt `containerRef`, hört auf `placeholder-click`, fetcht Preview via `useApi`,
   rendert `Dialog` mit Output (Loading/Error/Miss-Hinweis/Text als `<pre>`-Block).
10. `SystemPromptEditor.tsx` + `PlaybookBodyEditor.tsx`: `containerRef` an
    `bn-container` hängen, `<PlaceholderPreviewDialog containerRef={ref}/>` mounten.

### D — Frontend Tests
11. `PlaceholderPreviewDialog.test.tsx`: Event feuern → Dialog zeigt Text (api-mock).
12. `PlaceholderBlock.test.tsx`: Klick dispatcht CustomEvent mit korrektem Detail.

## Risiken / offene Punkte
- Klick vs. Cursor-Platzierung im Edit-Modus: `stopPropagation` im onClick; Pill ist
  atomic (`content:'none'`), daher unkritisch.
- `target_id` mit `#`-Anker (Resource-Section): via `URLSearchParams` korrekt
  encodiert.
