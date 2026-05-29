import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

// BlockNote ist eine gekapselte DOM-/ProseMirror-Insel (ADR-0022), die in
// jsdom nicht zuverlaessig mountet. Wir mocken die Editor-Module und pruefen
// nur den Wrapper-Vertrag (rendert + reicht initialContent durch).
const useCreateBlockNote = vi.fn(() => ({ document: [] }))

vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: (...args: unknown[]) => useCreateBlockNote(...args),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
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
})
