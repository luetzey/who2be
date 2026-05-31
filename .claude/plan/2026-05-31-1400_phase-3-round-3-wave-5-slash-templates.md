# Welle 5 — Slash-Template-Foundation (#5 + #7)

Phase 3 Runde 3, Welle 5. Vorgaenger: PR #76 (Welle 1+3), PR #77 (Welle 4).
Branch: `feat/phase-3-round3-wave5`.

## Ziel (User-Vorgabe)

> „Slash-/Persona, Slash-/Playbook etc. im System-Prompt-Editor. Placeholder
> abstrakt definiert, damit ich muehelos neue hinzufuegen kann. Und ich will
> ein bestimmtes Playbook verlinken koennen, nicht 'alle die der Agent
> sieht'."

Konkret: System-Prompt-Templates erhalten einen BlockNote-Editor mit einem
**reduzierten Block-Set** und einem **eigenen Slash-Menue**, das vier
typisierte Placeholder als Custom-Inline-Blocks einfuegt. Beim MCP-Read
expandiert der Server diese Tokens zu echtem Text, sodass der Client den
fertigen Prompt sieht.

## Antworten auf die drei Designfragen (vom User bestaetigt)

- **F1 — Initial-Placeholder-Set:** `playbook`, `resource`, `persona-field`,
  `date`. Spaeter nachschiebbar: `resource-block`, `list-playbooks`, etc.
- **F2 — Body-Format:** Schema-Bump (Migration `0026`) ergaenzt
  `system_prompt_template.body_format text` mit Default `'plain'`. Neue Templates
  speichern `'blocknote'`. Alte Templates bleiben unangetastet.
- **F3 — Expansion bei MCP-Read:** Server expandiert. MCP-Konsumenten sehen
  den finalen Plain-Text.

## Datenmodell

### Placeholder als BlockNote-Custom-Inline-Block

```ts
// Frontend-Schema
type PlaceholderProps = {
  kind: 'playbook' | 'resource' | 'persona-field' | 'date'
  target_id: string   // UUID fuer playbook/resource, Feldname fuer
                      // persona-field, '' fuer date
  label: string       // sichtbares Label im Editor (z.B. "Playbook: Reset-Mail")
}
```

Im Body-JSON erscheint der Placeholder als Inline-Element:
```json
{
  "type": "placeholder",
  "props": { "kind": "playbook", "target_id": "abc-…", "label": "Playbook: Reset-Mail" }
}
```

### Backend-Pydantic

```python
class Placeholder(BaseModel):
    kind: Literal["playbook", "resource", "persona-field", "date"]
    target_id: str  # UUID | "name" | "description" | ""
```

### Migration `0026_system_prompt_template_body_format.sql`

```sql
ALTER TABLE system_prompt_template
  ADD COLUMN body_format text NOT NULL DEFAULT 'plain';
ALTER TABLE system_prompt_template
  ADD CONSTRAINT system_prompt_template_body_format_check
  CHECK (body_format IN ('plain', 'blocknote'));
```

`body` bleibt `text`. Bei `body_format='blocknote'` enthaelt `body` BlockNote-
JSON als Stringified-JSON; bei `'plain'` ist es weiter Plain-Text.

## Placeholder-Registry (Backend)

```python
# apps/api/src/who2be_api/services/placeholders/registry.py
class PlaceholderResolver(Protocol):
    async def resolve(
        self, target_id: str, ctx: RenderContext, db: Database
    ) -> str: ...

REGISTRY: dict[str, PlaceholderResolver] = {
    "playbook":      PlaybookResolver(),
    "resource":      ResourceResolver(),
    "persona-field": PersonaFieldResolver(),
    "date":          DateResolver(),
}
```

Neuen Placeholder hinzufuegen = ein Resolver + ein Eintrag im Dict, plus
Frontend-Slash-Menue-Item + ggf. Picker. Das ist die geforderte
Abstraktheit.

### Render-Context

```python
class RenderContext(BaseModel):
    workspace_id: UUID
    persona_id: UUID | None   # Persona des Agents (fuer persona-field)
    now: datetime
    locale: str = "de-DE"
```

### Renderer

```python
# apps/api/src/who2be_api/services/placeholders/renderer.py
async def render_template_body(
    body_text: str, body_format: str, ctx: RenderContext, db: Database
) -> str:
    if body_format != "blocknote":
        return body_text
    doc = json.loads(body_text)
    return await _walk_blocks(doc, ctx, db)
```

`_walk_blocks` traversiert BlockNote-JSON, sammelt alle Inline-Elemente
vom Typ `placeholder`, ruft fuer jedes den passenden Resolver, ersetzt im
Plain-Text-Output. Saubere Trennung Walking ↔ Resolving.

### Resolver-Verhaltensregeln

- **playbook**: `target_id` ist UUID. Sucht Active-Version im Workspace.
  Bei nicht gefunden → `"<Playbook nicht verfuegbar>"` (lokalisiert).
- **resource**: analog.
- **persona-field**: `target_id ∈ {"name", "description"}`. Bei
  `ctx.persona_id is None` → leerer String + Warning-Log.
- **date**: `target_id` ist Format-Slug (`""` → ISO, `"human"` →
  `"31. Mai 2026"`). Standardisiert auf `ctx.locale`.

### Caching

In Welle 5 noch **nicht**. Resolver-Calls einzeln in DB. Sobald
Renderer-Calls > 1000 / Sek werden oder Templates mit > 50 Placeholdern
auftauchen, koennen wir Per-Render-LRU drueberlegen.

## MCP-Integration

Neuer Tool-Endpoint:

```python
@mcp.tool
async def fetch_agent(agent_id_or_slug: str) -> AgentWithRenderedPrompt:
    """Laedt einen Agent samt Persona + RENDER-tem Systemprompt
    (Placeholder bereits expandiert)."""
```

Returntyp:
```python
class AgentWithRenderedPrompt(BaseModel):
    id: UUID
    name: str
    persona: PersonaRead
    system_prompt_rendered: str    # finaler Plain-Text
    system_prompt_template_id: UUID
```

Der Renderer laeuft serverseitig in der MCP-Route gegen die Workspace-DB.
RenderContext wird aus dem Agent-Eintrag konstruiert (`persona_id` aus
`agent.persona_id`).

`get_persona` bleibt unveraendert — Personae und Templates sind
orthogonal.

## Frontend-Architektur

### Neuer Editor-Subbaum

```
apps/web/src/components/editor/system-prompt/
├── SystemPromptEditor.tsx     // BlockNote-Insel mit Custom-Schema
├── PlaceholderBlock.tsx       // Custom-Inline-Block (Pill-Render)
├── PlaceholderPicker.tsx      // Modal mit Tab je Placeholder-Kind
├── pickers/
│   ├── PlaybookPicker.tsx     // listPlaybooks → Combobox
│   ├── ResourcePicker.tsx     // listResources → Combobox
│   ├── PersonaFieldPicker.tsx // Radio: name | description
│   └── DateFormatPicker.tsx   // Radio: iso | human
└── slashMenu.ts               // BlockNote-Slash-Menu-Custom-Items
```

### BlockNote-Schema

Custom Inline Block via `createBlockNoteSchema({ ...defaultInlineSpecs,
placeholder: spec })`. Spec rendert als Pill mit Icon + Label, ist
read-only inline, beim Klick oeffnet sich der Picker zum Bearbeiten.

### Slash-Menue

Nur die vier Custom-Items + ein paar essentielle BlockNote-Defaults
(Paragraph, Heading, Bulleted-List). NICHT die volle Default-Liste (z. B.
keine Tables, Images, Audio — wuerden im Prompt-Kontext keinen Sinn machen).

### Body-Format-Wechsel

Bei Erstanlage einer neuen Template-Version (oder beim Wechsel von einer
alten `plain`-Version auf eine neue Editor-Version) speichert das Frontend
`body_format='blocknote'`. Existierende Plain-Templates werden in der
UI **als Read-Only-Textarea** angezeigt, mit einem CTA „In BlockNote-
Editor migrieren". Erst nach Klick wird der Body in einen Single-
Paragraph-Block gewandelt und das Format umgestellt.

## Tests

### Backend
- `test_placeholder_renderer.py` — Unit pro Resolver + Integration mit echter
  DB (Workspace-Setup, Test-Persona, Test-Playbook, Test-Resource).
- `test_fetch_agent_mcp.py` — End-to-End: Template mit allen vier
  Placeholder-Kinds → expandierter String enthaelt die richtigen Inhalte.

### Frontend
- `SystemPromptEditor.test.tsx` — BlockNote mocked (Standard-Pattern, siehe
  PlaybookDetailPage.test.tsx). Pruefen: Schema akzeptiert `placeholder`-
  Block; Slash-Menue rendert die vier Items.
- `PlaceholderBlock.test.tsx` — Pill-Render fuer alle vier Kinds.
- `PlaybookPicker.test.tsx`, `ResourcePicker.test.tsx` — Picker laden + filtern.

## Agenten-Plan (sequenziell)

Beide branchen aus `feat/phase-3-round3-wave5`. Frontend startet ERST,
wenn Backend-Token-JSON-Shape fixiert ist (Schema oben).

### PR-E1 — Backend
**Agent:** `backend-developer` Sonnet, Worktree, Branch
`feat/wave5-backend-placeholder-renderer`.

Liefert: Migration `0026`, Models-Erweiterung, Registry + 4 Resolver,
Renderer, neuer MCP-Tool `fetch_agent`, Tests. Wenn das MCP-Tool
strittig ist (z. B. weil ein Agent ohne Persona moeglich ist) → kurz im
Plan-Bericht dokumentieren und einen sinnvollen Fallback waehlen.

### PR-E2 — Frontend
**Agent:** `frontend-developer` Sonnet, Worktree, Branch
`feat/wave5-frontend-system-prompt-editor`.

Liefert: SystemPromptEditor + PlaceholderBlock + 4 Picker, Verkabelung
in `SystemPromptDetailPage` und `SystemPromptNewPage`, Backwards-Compat
fuer `body_format='plain'`, Tests, Lint/TSC/Build clean.

### Integration

Ich selbst — Merges, Sammel-Test, Stack-Rebuild, User-Smoke. Bei
Konflikten zwischen den beiden Sub-Branches dokumentier ich die
Resolution.

## Out of Scope (Welle 5)

- Placeholder-Caching jenseits Per-Render-Walk.
- `resource-block`-Placeholder (eine Picker-Ebene komplexer).
- Conditional-Placeholders (`{{if persona.name}}...{{endif}}`).
- Edit-History auf Placeholder-Ebene (welche Version eines Playbooks zur
  Render-Zeit galt — wir nehmen immer Active).
- Migration alter Plain-Templates batch — User-getriggert via UI-CTA.
