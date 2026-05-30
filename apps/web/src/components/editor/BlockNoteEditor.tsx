import { useMemo } from 'react'
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

  return (
    <div className="bn-container rounded-md border bg-background py-2">
      <BlockNoteView
        editor={editor}
        editable={editable}
        theme={resolved}
        portalElements={portalElements}
        onChange={() => onChange?.(editor.document as unknown as ResourceBlock[])}
      />
    </div>
  )
}

export type { Block }
