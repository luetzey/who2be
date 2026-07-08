import { BlockNoteEditor, type Block } from '@/components/editor/BlockNoteEditor'
import type { ResourceBlock } from '@/api/types'

interface ResourceEditorProps {
  initialBlocks: ResourceBlock[]
  editable?: boolean
  onChange?: (blocks: ResourceBlock[]) => void
}

// Dunner Domaenen-Wrapper um die geteilte BlockNote-Insel (ADR-0022). Die
// eigentliche Editor-Logik (Portal-Mount, Theme, CSS-Scope) lebt in
// `@/components/editor/BlockNoteEditor` und wird auch vom Persona-System-
// Prompt sowie Playbook-Body verwendet. Reine Re-Wiring-Komponente, damit
// bestehende Call-Sites stabil bleiben.
export function ResourceEditor({ initialBlocks, editable = true, onChange }: ResourceEditorProps) {
  return (
    <div data-testid="resource-editor">
      <BlockNoteEditor
        initialBlocks={initialBlocks}
        editable={editable}
        onChange={onChange}
      />
    </div>
  )
}

export type { Block }
