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

import { buildSystemPromptSchema, type SystemPromptSchema } from './PlaceholderBlock'
import type { PlaceholderKind, PlaceholderProps } from './PlaceholderBlock'
import { buildSlashMenuItems } from './slashMenu'
import { PlaybookPicker } from './pickers/PlaybookPicker'
import { ResourcePicker } from './pickers/ResourcePicker'
import { PersonaFieldPicker } from './pickers/PersonaFieldPicker'
import { DateFormatPicker } from './pickers/DateFormatPicker'

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

  // Picker-State: welcher Picker ist offen?
  const [openPicker, setOpenPicker] = useState<PlaceholderKind | null>(null)

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

  // Picker-Callback: insertet den Placeholder-Inline-Block nach Bestaetigung.
  function handlePickerConfirm(props: PlaceholderProps) {
    setOpenPicker(null)
    editor.insertInlineContent([
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { type: 'placeholder', props } as any,
      ' ',
    ])
  }

  function handlePickerCancel() {
    setOpenPicker(null)
  }

  // `tools-overview` ist parameterlos — kein Picker noetig. Statt einen
  // weiteren Dialog zu mounten, insertieren wir direkt, wenn das Slash-
  // Menue den Kind anfordert.
  function handleOpenPicker(kind: PlaceholderKind) {
    if (kind === 'tools-overview') {
      handlePickerConfirm({
        kind: 'tools-overview',
        target_id: '',
        label: 'MCP-Tools-Übersicht',
      })
      return
    }
    setOpenPicker(kind)
  }

  return (
    <>
      <div
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

      {/* Picker-Dialoge (ausserhalb des bn-container) */}
      <PlaybookPicker
        open={openPicker === 'playbook'}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <ResourcePicker
        open={openPicker === 'resource'}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <PersonaFieldPicker
        open={openPicker === 'persona-field'}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <DateFormatPicker
        open={openPicker === 'date'}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
    </>
  )
}
