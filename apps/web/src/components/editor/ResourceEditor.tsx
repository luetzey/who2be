import { useState } from 'react'

import { BlockNoteEditor, type Block } from '@/components/editor/BlockNoteEditor'
import { EditorFooter } from '@/components/editor/EditorFooter'
import type { ResourceBlock } from '@/api/types'

interface ResourceEditorProps {
  initialBlocks: ResourceBlock[]
  editable?: boolean
  onChange?: (blocks: ResourceBlock[]) => void
  /**
   * Einsatzort (editorProfiles.ts). Nur der Resource-Inhalt setzt `resource`
   * und bekommt damit die Tabelle (Editor-W1); Persona-Modi und
   * Tool-Hinweise bleiben beim Default `plain`.
   */
  profile?: 'resource' | 'plain'
}

// Duenner Wrapper um die geteilte BlockNote-Insel (ADR-0022). Die eigentliche
// Editor-Logik (Portal-Mount, Theme, CSS-Scope) lebt in
// `@/components/editor/BlockNoteEditor`. Lebt hier in `@/components/editor/`
// (nicht im resources-Feature), weil neben den Resource-Forms auch der
// Persona-Modi-Editor die Komponente nutzt — Cross-Feature-Imports sind per
// Lint-Gate verboten, Geteiltes wandert nach `@/components/`.
//
// Die Laengen-Fusszeile (Editor-Paket P3) haengt hier, damit Resource-Inhalt,
// Persona-Modi und Tool-Hinweise sie gleichermassen bekommen (Spec §3.2).
export function ResourceEditor({
  initialBlocks,
  editable = true,
  onChange,
  profile = 'plain',
}: ResourceEditorProps) {
  const [doc, setDoc] = useState<ResourceBlock[]>(initialBlocks)
  return (
    <div data-testid="resource-editor">
      <BlockNoteEditor
        initialBlocks={initialBlocks}
        editable={editable}
        onChange={(blocks) => {
          setDoc(blocks)
          onChange?.(blocks)
        }}
        profile={profile}
      />
      <EditorFooter blocks={doc} />
    </div>
  )
}

export type { Block }
