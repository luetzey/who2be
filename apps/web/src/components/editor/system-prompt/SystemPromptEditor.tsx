// SystemPromptEditor — BlockNote-Insel fuer System-Prompt-Templates (Welle 5).
//
// Custom-Schema: Paragraph, Heading (h1-h3), BulletList + PlaceholderInlineBlock.
// Custom-Slash-Menue: vier Placeholder-Items + essentielle Defaults.
// Focus-Gate: onChange wird erst propagiert, nachdem der User mindestens einmal
// den Editor fokussiert hat (analog BlockNoteEditor.tsx, Welle-4-Fix).
//
// Picker-State liegt im Editor-Wrapper (hier), damit die Picker-Dialoge
// ausserhalb des BlockNote-DOM-Baums (Portal) gerendert werden und kein
// overflow:hidden-Ancestor die Dialoge beschneidet.

import { useMemo, useRef, useState } from 'react'
import { BlockNoteView } from '@blocknote/mantine'
import { SuggestionMenuController, useCreateBlockNote } from '@blocknote/react'
import type { PartialBlock } from '@blocknote/core'

import { useTheme } from '@/app/theme-context'
import { type Measurable } from '@/components/ui/popover'

import { buildSystemPromptSchema, type SystemPromptSchema } from './PlaceholderBlock'
import type {
  PlaceholderClickDetail,
  PlaceholderKind,
  PlaceholderProps,
} from './PlaceholderBlock'
import { caretMeasurable } from './caretAnchor'
import { buildSlashMenuItems } from './slashMenu'
import { PlaceholderPreviewPopover } from './PlaceholderPreviewPopover'
import { PlaybookPicker } from './pickers/PlaybookPicker'
import { ResourcePicker } from './pickers/ResourcePicker'
import { PersonaFieldPicker } from './pickers/PersonaFieldPicker'
import { DateFormatPicker } from './pickers/DateFormatPicker'
import { CatalogScopePicker } from './pickers/CatalogScopePicker'
import { ResourcesCatalogScopePicker } from './pickers/ResourcesCatalogScopePicker'

// Das Schema wird einmal pro Modul-Import gebaut; keine Hot-Reload-Probleme
// weil BlockNote-Schemata statisch sind.
const systemPromptSchema = buildSystemPromptSchema()

export type SystemPromptBlock = PartialBlock<
  SystemPromptSchema['blockSchema'],
  SystemPromptSchema['inlineContentSchema'],
  SystemPromptSchema['styleSchema']
>

export interface SystemPromptEditorProps {
  /** Initial-Bloecke aus gespeichertem BlockNote-JSON (JSON.parse(body)). */
  initialBlocks?: SystemPromptBlock[]
  editable?: boolean
  /** Wird nach jeder User-Interaktion mit dem aktualisierten Block-Array aufgerufen. */
  onChange?: (blocks: SystemPromptBlock[]) => void
}

export function SystemPromptEditor({
  initialBlocks,
  editable = true,
  onChange,
}: SystemPromptEditorProps) {
  const { resolved } = useTheme()
  const userInteractedRef = useRef(false)
  // Ref auf den bn-container — Anker fuer das bubbelnde `placeholder-click`-Event.
  const containerRef = useRef<HTMLDivElement>(null)
  // Gemeinsamer Anker fuer die schwebenden Panels: Pill (Klick/Edit) oder
  // Caret (Slash-Einfuegen). Von Preview + allen Pickern geteilt.
  const anchorRef = useRef<Measurable | null>(null)

  // Picker-State: welcher Picker ist offen?
  const [openPicker, setOpenPicker] = useState<PlaceholderKind | null>(null)
  // Edit-Flow: wird eine Pill bearbeitet, haelt dies das Detail (inkl.
  // `updateInlineContent`) der betroffenen Pill. `null` = Neu-Einfuegen.
  const [pendingEdit, setPendingEdit] = useState<PlaceholderClickDetail | null>(null)

  const editor = useCreateBlockNote(
    {
      schema: systemPromptSchema,
      initialContent:
        initialBlocks !== undefined && initialBlocks.length > 0
          ? initialBlocks
          : undefined,
    },
    [],
  )

  const portalElements = useMemo(() => ({ default: null }), [])

  // Picker-Callback: im Edit-Modus die bestehende Pill in-place aktualisieren,
  // sonst eine neue Placeholder-Inline einfuegen.
  function handlePickerConfirm(props: PlaceholderProps) {
    setOpenPicker(null)
    if (pendingEdit !== null) {
      pendingEdit.updateInlineContent(props)
      setPendingEdit(null)
      return
    }
    editor.insertInlineContent([
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { type: 'placeholder', props } as any,
      ' ',
    ])
  }

  function handlePickerCancel() {
    setOpenPicker(null)
    setPendingEdit(null)
  }

  // „Bearbeiten" im Preview-Overlay: passenden Picker vorbefuellt oeffnen.
  function handleStartEdit(detail: PlaceholderClickDetail) {
    setPendingEdit(detail)
    setOpenPicker(detail.kind)
  }

  // `tools-overview` und `persona-ref` sind parameterlos — kein Picker noetig.
  // Statt einen weiteren Dialog zu mounten, insertieren wir direkt, wenn das
  // Slash-Menue den Kind anfordert.
  function handleOpenPicker(kind: PlaceholderKind) {
    if (kind === 'tools-overview') {
      handlePickerConfirm({
        kind: 'tools-overview',
        target_id: '',
        label: 'MCP-Tools-Übersicht',
      })
      return
    }
    if (kind === 'persona-ref') {
      handlePickerConfirm({
        kind: 'persona-ref',
        target_id: '',
        label: 'Persona laden (MCP)',
      })
      return
    }
    // Slash-Einfuegen: Panel am Caret verankern (kein pending Edit).
    anchorRef.current = caretMeasurable(containerRef.current)
    setOpenPicker(kind)
  }

  return (
    <>
      <div
        ref={containerRef}
        className="bn-container rounded-md border bg-background py-2"
        data-testid="system-prompt-editor"
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
            onChange?.(
              editor.document as unknown as SystemPromptBlock[],
            )
          }}
          // Slash-Menue wird ueberschrieben: nur die gefilterten + Custom-Items.
          slashMenu={false}
        >
          <SuggestionMenuController
            triggerCharacter="/"
            getItems={async (query) =>
              buildSlashMenuItems(editor, handleOpenPicker, query)
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
      />

      {/* Picker-Popover (Portal, am Anker verankert) */}
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
        initial={pendingEdit?.kind === 'resource' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <PersonaFieldPicker
        open={openPicker === 'persona-field'}
        anchorRef={anchorRef}
        initial={pendingEdit?.kind === 'persona-field' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <DateFormatPicker
        open={openPicker === 'date'}
        anchorRef={anchorRef}
        initial={pendingEdit?.kind === 'date' ? pendingEdit : undefined}
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
    </>
  )
}
