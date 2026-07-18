// PersonaProfileEditor — BlockNote-Insel fuer den Persona-Profil-Body (Track F).
//
// Analog zum PlaybookBodyEditor, aber mit dem vollen Persona-Pill-Satz: Slash-
// Refs auf einzelne Playbooks/Resources plus die Katalog-Pills
// `playbooks-catalog` (all|triggered) und `resources-catalog` (all|tag). So
// wird die Persona — wie der System-Prompt — fetch-time-dynamisch konfiguriert
// (der MCP-`get_persona`-Render loest die Katalog-Pills gegen die aktiven
// Playbooks/Resources des Workspace auf).
//
// Das gemeinsame PlaceholderBlock-Schema bleibt unveraendert — wir filtern nur
// die Slash-Items via `allowedKinds`. Picker-State liegt hier im Wrapper, damit
// die Dialoge ausserhalb des BlockNote-DOM (Portal) gerendert werden.

import { useMemo, useRef, useState } from 'react'
import { BlockNoteView } from '@blocknote/mantine'
import { SuggestionMenuController, useCreateBlockNote } from '@blocknote/react'

import { useTheme } from '@/app/theme-context'
import type { ResourceBlock } from '@/api/types'
import {
  buildSystemPromptSchema,
  type PlaceholderClickDetail,
  type PlaceholderKind,
  type PlaceholderProps,
} from '@/components/editor/system-prompt/PlaceholderBlock'
import type { SystemPromptBlock } from '@/components/editor/system-prompt/SystemPromptEditor'
import { PlaceholderPreviewPopover } from '@/components/editor/system-prompt/PlaceholderPreviewPopover'
import { caretMeasurable } from '@/components/editor/system-prompt/caretAnchor'
import { buildSlashMenuItems } from '@/components/editor/system-prompt/slashMenu'
import { PlaybookPicker } from '@/components/editor/system-prompt/pickers/PlaybookPicker'
import { ResourcePicker } from '@/components/editor/system-prompt/pickers/ResourcePicker'
import { CatalogScopePicker } from '@/components/editor/system-prompt/pickers/CatalogScopePicker'
import { ResourcesCatalogScopePicker } from '@/components/editor/system-prompt/pickers/ResourcesCatalogScopePicker'
import { ToolPicker } from '@/components/editor/system-prompt/pickers/ToolPicker'
import { type Measurable } from '@/components/ui/popover'

// Das Schema wird einmal pro Modul-Import gebaut (statisch, geteilt mit dem
// SystemPromptEditor). Alle Pill-Kinds bleiben gueltig; nur das Slash-Menue ist
// auf den Persona-Satz reduziert.
const personaProfileSchema = buildSystemPromptSchema()

// Der volle Persona-Pill-Satz (kein Persona-Feld/-Ref/Datum/MCP-Tools-
// Uebersicht — die Persona referenziert nicht sich selbst). `tool-ref` (WP-5)
// ist additiv: reine Alias-Referenz, kein Composition-/Link-Sync beim
// Speichern.
const ALLOWED_KINDS: Set<PlaceholderKind> = new Set([
  'playbook',
  'resource',
  'playbooks-catalog',
  'resources-catalog',
  'tool-ref',
])

export interface PersonaProfileEditorProps {
  /** Initial-Bloecke aus dem gespeicherten Persona-Profil (`content.content.blocks`). */
  initialBlocks?: ResourceBlock[]
  editable?: boolean
  /** Wird nach jeder User-Interaktion mit dem aktualisierten Block-Array aufgerufen. */
  onChange?: (blocks: ResourceBlock[]) => void
  /** Persona-ID fuer die Pill-Vorschau (Katalog-Pills loesen sonst nicht auf). */
  personaId?: string
}

export function PersonaProfileEditor({
  initialBlocks,
  editable = true,
  onChange,
  personaId,
}: PersonaProfileEditorProps) {
  const { resolved } = useTheme()
  const userInteractedRef = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const anchorRef = useRef<Measurable | null>(null)

  const [openPicker, setOpenPicker] = useState<PlaceholderKind | null>(null)
  const [pendingEdit, setPendingEdit] = useState<PlaceholderClickDetail | null>(null)

  const editor = useCreateBlockNote(
    {
      schema: personaProfileSchema,
      initialContent:
        initialBlocks !== undefined && initialBlocks.length > 0
          ? (initialBlocks as unknown as SystemPromptBlock[])
          : undefined,
    },
    [],
  )

  const portalElements = useMemo(() => ({ default: null }), [])

  function handlePickerConfirm(props: PlaceholderProps) {
    setOpenPicker(null)
    if (pendingEdit !== null) {
      pendingEdit.updateInlineContent(props)
      setPendingEdit(null)
      return
    }
    editor.insertInlineContent([
      // `as any` noetig, weil BlockNotes `insertInlineContent`-Signatur das
      // Custom-Placeholder-Inline-Schema nicht kennt (Typing-Grenze der
      // Custom-Schema-API); die Props selbst sind via `PlaceholderProps` typisiert.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { type: 'placeholder', props } as any,
      ' ',
    ])
  }

  function handlePickerCancel() {
    setOpenPicker(null)
    setPendingEdit(null)
  }

  function handleOpenPicker(kind: PlaceholderKind) {
    // Nur der Persona-Satz ist erlaubt; alles andere defensiv ignorieren.
    if (!ALLOWED_KINDS.has(kind)) return
    anchorRef.current = caretMeasurable(containerRef.current)
    setOpenPicker(kind)
  }

  function handleStartEdit(detail: PlaceholderClickDetail) {
    if (!ALLOWED_KINDS.has(detail.kind)) return
    setPendingEdit(detail)
    setOpenPicker(detail.kind)
  }

  return (
    <>
      <div
        ref={containerRef}
        className="bn-container rounded-md border bg-background py-2"
        data-testid="persona-profile-editor"
        onFocusCapture={() => {
          userInteractedRef.current = true
        }}
      >
        <BlockNoteView
          editor={editor}
          editable={editable}
          theme={resolved}
          portalElements={portalElements}
          onChange={() => {
            if (!userInteractedRef.current) return
            onChange?.(editor.document as unknown as ResourceBlock[])
          }}
          slashMenu={false}
        >
          <SuggestionMenuController
            triggerCharacter="/"
            getItems={async (query) =>
              buildSlashMenuItems(editor, handleOpenPicker, query, ALLOWED_KINDS)
            }
          />
        </BlockNoteView>
      </div>

      {/* Pill-Preview-Popover: lauscht auf Klicks im bn-container. */}
      <PlaceholderPreviewPopover
        containerRef={containerRef}
        anchorRef={anchorRef}
        editable={editable}
        onEdit={handleStartEdit}
        personaId={personaId}
      />

      <PlaybookPicker
        open={openPicker === 'playbook'}
        anchorRef={anchorRef}
        initial={pendingEdit?.kind === 'playbook' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <ResourcePicker
        open={openPicker === 'resource'}
        anchorRef={anchorRef}
        allowBlockAnchor
        initial={pendingEdit?.kind === 'resource' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <CatalogScopePicker
        open={openPicker === 'playbooks-catalog'}
        anchorRef={anchorRef}
        initial={pendingEdit?.kind === 'playbooks-catalog' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <ResourcesCatalogScopePicker
        open={openPicker === 'resources-catalog'}
        anchorRef={anchorRef}
        initial={pendingEdit?.kind === 'resources-catalog' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <ToolPicker
        open={openPicker === 'tool-ref'}
        anchorRef={anchorRef}
        initial={pendingEdit?.kind === 'tool-ref' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
    </>
  )
}
