import { BlockNoteView } from '@blocknote/mantine'
import { useCreateBlockNote } from '@blocknote/react'
import type { Block, PartialBlock } from '@blocknote/core'

import { useTheme } from '@/app/theme-context'
import type { ResourceBlock } from '@/api/types'

interface ResourceEditorProps {
  initialBlocks: ResourceBlock[]
  editable?: boolean
  onChange?: (blocks: ResourceBlock[]) => void
}

// Gekapselte BlockNote-Insel (ADR-0022): eigenes Style-Scope (@blocknote/mantine),
// lokale Inter-Schrift (kein CDN/CSP). Das offene BlockNote-Block-Schema und
// unser schema-generiertes `ResourceBlock` sind strukturell gleich (id + type +
// offene Felder), aber nominal verschieden — daher die `unknown`-Bruecken.
export function ResourceEditor({ initialBlocks, editable = true, onChange }: ResourceEditorProps) {
  const { resolved } = useTheme()
  const editor = useCreateBlockNote({
    initialContent:
      initialBlocks.length > 0 ? (initialBlocks as unknown as PartialBlock[]) : undefined,
  })

  // `bn-container` aktiviert den scopeden CSS-Theme-Fix (Phase 3-B):
  // Headings + Popover-Surfaces innerhalb der BlockNote-Insel. Siehe
  // styles/globals.css §BlockNote-Insel.
  return (
    <div
      className="bn-container rounded-md border bg-background py-2"
      data-testid="resource-editor"
    >
      <BlockNoteView
        editor={editor}
        editable={editable}
        theme={resolved}
        onChange={() => onChange?.(editor.document as unknown as ResourceBlock[])}
      />
    </div>
  )
}

export type { Block }
