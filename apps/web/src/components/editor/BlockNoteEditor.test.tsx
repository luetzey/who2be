import { describe, expect, it, vi } from 'vitest'

vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => null,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

import type { ResourceBlock } from '@/api/types'

import { blocksToPlainText, plainTextToBlocks } from './plaintext'

describe('blocksToPlainText / plainTextToBlocks', () => {
  it('roundtripped einen Plaintext-Prompt verlustfrei', () => {
    const text = 'Sei direkt.\nKein Marketing-Geschwurbel.'
    const blocks = plainTextToBlocks(text)
    expect(blocksToPlainText(blocks)).toBe(text)
  })

  it('extrahiert Text aus verschachtelten Inline-Containern (z. B. Link)', () => {
    const blocks: ResourceBlock[] = [
      {
        id: 'b-1',
        type: 'paragraph',
        content: [
          { type: 'text', text: 'Siehe ' },
          {
            type: 'link',
            content: [{ type: 'text', text: 'Doku' }],
          },
        ],
      } as unknown as ResourceBlock,
    ]
    expect(blocksToPlainText(blocks)).toBe('Siehe Doku')
  })

  it('ignoriert Bloecke ohne Inhalt', () => {
    expect(blocksToPlainText([])).toBe('')
    expect(plainTextToBlocks('')).toEqual([])
  })
})
