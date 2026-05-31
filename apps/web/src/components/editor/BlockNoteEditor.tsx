import { useMemo, useRef } from 'react'
import { BlockNoteView } from '@blocknote/mantine'
import { useCreateBlockNote } from '@blocknote/react'
import type { Block, PartialBlock } from '@blocknote/core'

import { useTheme } from '@/app/theme-context'
import type { ResourceBlock } from '@/api/types'

interface BlockNoteEditorProps {
  initialBlocks: ResourceBlock[]
  editable?: boolean
  onChange?: (blocks: ResourceBlock[]) => void
}

// Geteilte BlockNote-Insel (ADR-0022) fuer Profil/System-Prompt/Playbook-Body/
// Resource-Body. `portalElements.default = null` hebt Slash-/Side-/Drag-Menue
// auf `document.body`, damit kein `overflow:hidden`-Ancestor (Card, Section)
// das Popover beschneidet (Phase 3-fixes Track 2). Theme-Surfaces fuer die
// Popover-Layer kommen aus styles/globals.css §BlockNote-Insel.
export function BlockNoteEditor({
  initialBlocks,
  editable = true,
  onChange,
}: BlockNoteEditorProps) {
  const { resolved } = useTheme()
  const editor = useCreateBlockNote({
    initialContent:
      initialBlocks.length > 0 ? (initialBlocks as unknown as PartialBlock[]) : undefined,
  })
  const portalElements = useMemo(() => ({ default: null }), [])
  // Welle 4-Fix: BlockNote normalisiert beim Mount sein Dokument (ergaenzt
  // Block-IDs, Default-Props, leeren Standard-Paragraph). Dabei feuert
  // `onChange` einmal mit dem normalisierten Stand, der NICHT identisch zu
  // `initialBlocks` ist. Wuerden wir das durchreichen, wertet der
  // `useAutoSaveDraft`-Hook im Parent das als User-Edit und PATCH-t den
  // Draft sofort — beim reinen Oeffnen einer Active-Version legt der Server
  // dadurch eine neue Draft-Version an, ohne dass der User getippt hat.
  // Loesung: `onChange` erst propagieren, nachdem der Editor mindestens
  // einmal vom User fokussiert wurde (Klick / Tab-Stop). Programmatische
  // Mount-Normalisierungen werden geschluckt.
  const userInteractedRef = useRef(false)

  return (
    <div
      className="bn-container rounded-md border bg-background py-2"
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
          if (!userInteractedRef.current) {
            return
          }
          onChange?.(editor.document as unknown as ResourceBlock[])
        }}
      />
    </div>
  )
}

export type { Block }
