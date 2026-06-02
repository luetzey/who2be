// PlaybookBodyEditor — BlockNote-Insel fuer den Playbook-Body (Welle 5).
//
// Analog zum SystemPromptEditor, aber bewusst reduziert: nur Playbook- und
// Resource-Pills sind erlaubt (kein Persona-Feld/Datum/MCP-Tools). Das
// gemeinsame PlaceholderBlock-Schema bleibt unveraendert — wir filtern nur
// die Slash-Items via `allowedKinds`. Die Resource-Pill darf einen
// Heading-Anker tragen (`allowBlockAnchor`), damit `target_id` die Form
// `<uuid>#<block_id>` annehmen kann.
//
// Picker-State liegt hier im Wrapper, damit die Dialoge ausserhalb des
// BlockNote-DOM (Portal) gerendert werden (kein overflow-Clipping).

import { useMemo, useRef, useState } from 'react'
import { BlockNoteView } from '@blocknote/mantine'
import { SuggestionMenuController, useCreateBlockNote } from '@blocknote/react'

import { useTheme } from '@/app/theme-context'
import {
  buildSystemPromptSchema,
  type PlaceholderClickDetail,
  type PlaceholderKind,
  type PlaceholderProps,
} from '@/components/editor/system-prompt/PlaceholderBlock'
import type { SystemPromptBlock } from '@/components/editor/system-prompt/SystemPromptEditor'
import { PlaceholderPreviewDialog } from '@/components/editor/system-prompt/PlaceholderPreviewDialog'
import { buildSlashMenuItems } from '@/components/editor/system-prompt/slashMenu'
import { PlaybookPicker } from '@/components/editor/system-prompt/pickers/PlaybookPicker'
import { ResourcePicker } from '@/components/editor/system-prompt/pickers/ResourcePicker'

// Das Schema wird einmal pro Modul-Import gebaut (statisch, siehe
// SystemPromptEditor). Wir teilen bewusst dasselbe Schema — alle Pill-Kinds
// bleiben gueltig; nur das Slash-Menue ist reduziert.
const playbookBodySchema = buildSystemPromptSchema()

// Nur diese beiden Kinds sind im Playbook-Body erlaubt.
const ALLOWED_KINDS: Set<PlaceholderKind> = new Set(['playbook', 'resource'])

export type PlaybookBodyBlock = SystemPromptBlock

export interface PlaybookBodyEditorProps {
  /** Initial-Bloecke aus gespeichertem BlockNote-JSON (JSON.parse(body)). */
  initialBlocks?: PlaybookBodyBlock[]
  editable?: boolean
  /** Wird nach jeder User-Interaktion mit dem aktualisierten Block-Array aufgerufen. */
  onChange?: (blocks: PlaybookBodyBlock[]) => void
}

export function PlaybookBodyEditor({
  initialBlocks,
  editable = true,
  onChange,
}: PlaybookBodyEditorProps) {
  const { resolved } = useTheme()
  const userInteractedRef = useRef(false)
  // Ref auf den bn-container — Anker fuer das bubbelnde `placeholder-click`-Event.
  const containerRef = useRef<HTMLDivElement>(null)

  const [openPicker, setOpenPicker] = useState<PlaceholderKind | null>(null)
  // Edit-Flow: Detail (inkl. `updateInlineContent`) der bearbeiteten Pill.
  const [pendingEdit, setPendingEdit] = useState<PlaceholderClickDetail | null>(null)

  const editor = useCreateBlockNote(
    {
      schema: playbookBodySchema,
      initialContent:
        initialBlocks !== undefined && initialBlocks.length > 0 ? initialBlocks : undefined,
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
    // Nur playbook/resource sind erlaubt; alles andere ignorieren (defensiv).
    if (!ALLOWED_KINDS.has(kind)) return
    setOpenPicker(kind)
  }

  // „Bearbeiten" im Preview-Overlay: nur erlaubte Kinds koennen hier existieren.
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
        data-testid="playbook-body-editor"
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
            onChange?.(editor.document as unknown as PlaybookBodyBlock[])
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

      {/* Pill-Preview-Overlay: lauscht auf Klicks im bn-container. */}
      <PlaceholderPreviewDialog
        containerRef={containerRef}
        editable={editable}
        onEdit={handleStartEdit}
      />

      <PlaybookPicker
        open={openPicker === 'playbook'}
        initial={pendingEdit?.kind === 'playbook' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
      <ResourcePicker
        open={openPicker === 'resource'}
        allowBlockAnchor
        initial={pendingEdit?.kind === 'resource' ? pendingEdit : undefined}
        onConfirm={handlePickerConfirm}
        onCancel={handlePickerCancel}
      />
    </>
  )
}
