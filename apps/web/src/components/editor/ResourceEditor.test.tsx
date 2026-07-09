import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

// BlockNote ist eine gekapselte DOM-/ProseMirror-Insel (ADR-0022), die in
// jsdom nicht zuverlaessig mountet. Wir mocken die Editor-Module und pruefen
// nur den Wrapper-Vertrag (rendert + reicht initialContent + portalElements
// durch). Slash-Menu-Funktionalitaet selbst wird im Browser-Smoke verifiziert
// (Phase 3-fixes Track 2 DoD).
const useCreateBlockNote = vi.fn(
  (options?: unknown): { document: unknown[] } => {
    void options
    return { document: [] }
  },
)
const blockNoteViewProps = vi.fn()

vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: (options?: unknown) => useCreateBlockNote(options),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: (props: Record<string, unknown>) => {
    blockNoteViewProps(props)
    return <div data-testid="blocknote-view" />
  },
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

import { ResourceEditor } from './ResourceEditor'

describe('ResourceEditor', () => {
  it('rendert die Editor-Insel und reicht initialContent durch', () => {
    const blocks = [{ id: 'b-1', type: 'paragraph' }]
    render(<ResourceEditor initialBlocks={blocks} />)
    expect(screen.getByTestId('resource-editor')).toBeInTheDocument()
    expect(screen.getByTestId('blocknote-view')).toBeInTheDocument()
    expect(useCreateBlockNote).toHaveBeenCalledWith(
      expect.objectContaining({ initialContent: blocks }),
    )
  })

  it('nutzt undefined als initialContent bei leeren Bloecken', () => {
    render(<ResourceEditor initialBlocks={[]} />)
    expect(useCreateBlockNote).toHaveBeenCalledWith(
      expect.objectContaining({ initialContent: undefined }),
    )
  })

  it('mountet Slash-/Side-/Drag-Popover an document.body (kein Clipping)', () => {
    blockNoteViewProps.mockClear()
    render(<ResourceEditor initialBlocks={[]} />)
    expect(blockNoteViewProps).toHaveBeenCalled()
    const props = blockNoteViewProps.mock.calls[0][0] as {
      portalElements?: { default?: unknown }
    }
    expect(props.portalElements).toEqual({ default: null })
  })
})
