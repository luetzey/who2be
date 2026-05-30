import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

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

/*
 * BlockNote-Theme-Regression (Phase 3-fixes Runde 2, Track 2 + 4).
 *
 * BlockNote rendert Slash-Menu, Listen und Divider ueber ProseMirror +
 * contenteditable. jsdom kann das nicht zuverlaessig — und unsere Tests
 * mocken `@blocknote/mantine` ohnehin global (siehe vi.mock oben). Statt
 * eines flakigen Render-Tests pinnen wir hier deklarativ die Vertraege
 * zwischen Mantine-DOM und unseren CSS-Overrides:
 *
 *  - `main.tsx` MUSS `@blocknote/mantine/style.css` VOR `globals.css`
 *    importieren (sonst greift unser Override-Layer auf nichts).
 *  - `globals.css` MUSS die von BlockNote (v0.51, Mantine-Renderer)
 *    verwendeten Klassen treffen. Wenn Mantine eine Klasse umbenennt,
 *    schlaegt der Browser-Smoke fehl — und dieser Test schlaegt aus
 *    Symmetriegruenden mit fehl, sobald die Selektoren angepasst werden,
 *    aber das Mantine-Klassen-Inventar (Fixture unten) nicht.
 */
const WEB_ROOT = resolve(__dirname, '../../..')
const MAIN_TSX = readFileSync(resolve(WEB_ROOT, 'src/main.tsx'), 'utf8')
const GLOBALS_CSS = readFileSync(resolve(WEB_ROOT, 'src/styles/globals.css'), 'utf8')

// Mantine-Klassen-Snapshot — die hier gelisteten Klassen muessen von
// BlockNote im Slash-Menu-/Block-Render erzeugt werden. Aenderung in
// Mantine-7+/BlockNote-Update => DevTools-Probe + Anpassung beider Listen.
const MANTINE_SLASH_MENU_SELECTORS = [
  '.bn-suggestion-menu',
  '.bn-suggestion-menu-item',
  '.bn-suggestion-menu-label',
  '.bn-mt-suggestion-menu-item-body',
  '.bn-mt-suggestion-menu-item-title',
  '.bn-mt-suggestion-menu-item-subtitle',
  '.bn-mt-suggestion-menu-item-section',
]

const BLOCK_RENDER_SELECTORS = [
  '.bn-container ul',
  '.bn-block-content ul',
  '.bn-container ol',
  '.bn-block-content ol',
  '.bn-container li > p',
  '.bn-container hr',
  '.bn-container code',
]

describe('BlockNote-Theme-Integration', () => {
  it('importiert die Mantine-Baseline VOR den Tailwind-Tokens', () => {
    const mantineIdx = MAIN_TSX.indexOf("'@blocknote/mantine/style.css'")
    const globalsIdx = MAIN_TSX.indexOf("'./styles/globals.css'")
    expect(mantineIdx, 'Mantine-Baseline fehlt in main.tsx').toBeGreaterThan(-1)
    expect(globalsIdx, 'globals.css-Import fehlt in main.tsx').toBeGreaterThan(-1)
    expect(
      mantineIdx,
      'Mantine-CSS muss vor globals.css importiert werden, sonst gewinnt Mantine die Cascade',
    ).toBeLessThan(globalsIdx)
  })

  it.each(MANTINE_SLASH_MENU_SELECTORS)(
    'styled Slash-Menu-Selektor %s in globals.css',
    (selector) => {
      expect(GLOBALS_CSS).toContain(selector)
    },
  )

  it.each(BLOCK_RENDER_SELECTORS)(
    'styled Block-Render-Selektor %s in globals.css',
    (selector) => {
      expect(GLOBALS_CSS).toContain(selector)
    },
  )

  it('aktiviert list-style + decimal/disc fuer Bullet- und Numbered-Listen', () => {
    expect(GLOBALS_CSS).toMatch(/list-style:\s*disc/)
    expect(GLOBALS_CSS).toMatch(/list-style:\s*decimal/)
  })

  it('rendert den Divider mit sichtbarem border-top', () => {
    // Mehrere `border-top: 1px solid var(--border)`-Regeln existieren — wir
    // pinnen auf den hr-Block, damit ein versehentlicher Reset auffaellt.
    expect(GLOBALS_CSS).toMatch(
      /\.bn-container hr,[\s\S]*?\.bn-block-content hr\s*\{[\s\S]*?border-top:\s*1px\s+solid\s+var\(--border\)/,
    )
  })

  it('haelt Slash-Menu in Breite und Hoehe, kein horizontaler Scroll', () => {
    expect(GLOBALS_CSS).toMatch(/\.bn-mantine \.bn-suggestion-menu\s*\{[\s\S]*?overflow-x:\s*hidden/)
    expect(GLOBALS_CSS).toMatch(/\.bn-mantine \.bn-suggestion-menu\s*\{[\s\S]*?max-width:/)
    expect(GLOBALS_CSS).toMatch(/\.bn-mantine \.bn-suggestion-menu\s*\{[\s\S]*?max-height:/)
  })
})
