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

/*
 * BlockNote auf Tablet/Phone (#431 K4) — CSS-Vertrag.
 *
 * Gleiches Muster wie der Block darueber und aus demselben Grund: jsdom hat
 * kein Layout, und `@blocknote/mantine` ist in dieser Datei global gemockt.
 * Die Layout-Aussagen selbst sind gerendert belegt (Chromium ueber CDP bei
 * 320 / 390 / 810px, Protokoll in
 * .claude/plan/2026-09-24-0530_431-k4-blocknote-tablet-phone.md). Hier steht
 * nur, was ein spaeterer Eingriff in globals.css nicht unbemerkt entfernen
 * darf.
 */
describe('BlockNote Tablet/Phone (#431 K4)', () => {
  // Der Rinnen-Override aus #564 (54px -> 12px) schiebt das Side-Menu aus dem
  // Viewport: BlockNote setzt es per Inline-Transform mit festem Offset nach
  // links, gemessen `x = -21` bei 320/390/767px gegen `x = 21` ab 768px.
  // Beides haengt am selben Media-Query-Block — wer die Rinne aendert, muss
  // auch diese Regel ansehen, deshalb wird die Kopplung hier gepinnt.
  it('blendet das Side-Menu im selben Media-Query wie die Rinne aus', () => {
    const phoneBlock = GLOBALS_CSS.match(
      /@media \(max-width: 767px\) \{[\s\S]*?\n\}\n/,
    )?.[0]
    expect(phoneBlock, 'Phone-Media-Query der BlockNote-Insel nicht gefunden').toBeTruthy()
    expect(phoneBlock).toMatch(/\.bn-container \.bn-editor\s*\{[\s\S]*?padding-inline:/)
    expect(phoneBlock).toMatch(/\.bn-side-menu\s*\{\s*display:\s*none/)
  })

  // Der Floor steht in docs/frontend/design-language.md §11: ">= 32px",
  // "kein interaktives Element darf darunter liegen, auf keinem Breakpoint".
  // 32px = `calc(var(--spacing) * 8)` bei `--spacing: 0.25rem`.
  // Gemessen vor dem Fix: Toolbar-Buttons 30x30, Side-Menu-Buttons 24x24,
  // Drag-Handle-Menue-Eintraege 94x30 — alle drei unter dem Floor.
  const HIT_TARGET_RULES: Array<[string, RegExp]> = [
    ['Toolbar-Buttons', /\.bn-toolbar \.bn-button,\s*\n\.bn-toolbar button\s*\{[\s\S]*?\}/],
    ['Side-Menu-Buttons', /\.bn-side-menu \.bn-button\s*\{[\s\S]*?\}/],
    ['Drag-Handle-Menue-Eintraege', /\.bn-drag-handle-menu \.mantine-Menu-item\s*\{[\s\S]*?\}/],
  ]

  it.each(HIT_TARGET_RULES)('hebt %s auf den 32px-Floor aus §11', (_label, pattern) => {
    const rule = GLOBALS_CSS.match(pattern)?.[0]
    expect(rule, 'Regel fehlt in globals.css').toBeTruthy()
    expect(rule).toMatch(/min-height:\s*calc\(var\(--spacing\) \* 8\)/)
  })

  // Der Block-Typ-Button der Toolbar (Mantine-`Button` mit Text) trug
  // `flex-shrink: 1` bei `min-width: auto` und mass bei 320px nur 18,7px
  // Breite. Ohne `flex-shrink: 0` bringt die `min-width` allein nichts.
  it('laesst Toolbar-Buttons nicht schrumpfen statt zu scrollen', () => {
    const rule = GLOBALS_CSS.match(
      /\.bn-toolbar \.bn-button,\s*\n\.bn-toolbar button\s*\{[\s\S]*?\}/,
    )?.[0]
    expect(rule).toMatch(/min-width:\s*calc\(var\(--spacing\) \* 8\)/)
    expect(rule).toMatch(/flex-shrink:\s*0/)
  })
})
