import { describe, expect, it } from 'vitest'

import type { ResourceBlock } from '@/api/types'

import { blockPlainText, blockPreview, isHeadingBlock, sectionPreview } from './blockText'

function paragraph(id: string, text: string, extra?: Record<string, unknown>): ResourceBlock {
  return {
    id,
    type: 'paragraph',
    content: [{ type: 'text', text, styles: {} }],
    ...extra,
  }
}

function heading(id: string, text: string, level?: number): ResourceBlock {
  return {
    id,
    type: 'heading',
    props: level === undefined ? {} : { level },
    content: [{ type: 'text', text, styles: {} }],
  }
}

describe('blockPlainText', () => {
  it('sammelt Text aus dem content-Array eines Standard-Blocks', () => {
    expect(blockPlainText(paragraph('b1', 'Hallo Welt'))).toBe('Hallo Welt')
  })

  it('konkateniert mehrere Inline-Segmente ohne Trenner', () => {
    const block: ResourceBlock = {
      id: 'b1',
      type: 'paragraph',
      content: [
        { type: 'text', text: 'Fett', styles: { bold: true } },
        { type: 'text', text: ' und normal', styles: {} },
      ],
    }
    expect(blockPlainText(block)).toBe('Fett und normal')
  })

  it('liefert leeren String fuer Bloecke ohne content/children', () => {
    expect(blockPlainText({ id: 'b1', type: 'paragraph' })).toBe('')
  })

  it('ignoriert null-, primitive- und Nicht-Text-Nodes', () => {
    const block: ResourceBlock = {
      id: 'b1',
      type: 'paragraph',
      content: [
        null,
        42,
        'nackter-string',
        { type: 'link', href: 'https://example.com' },
        { type: 'text', text: 123 },
        { type: 'text', text: 'echt' },
      ],
    }
    expect(blockPlainText(block)).toBe('echt')
  })

  it('steigt rekursiv in children und verschachtelten content ab', () => {
    const block: ResourceBlock = {
      id: 'b1',
      type: 'bulletListItem',
      content: [{ type: 'text', text: 'Eltern' }],
      children: [
        {
          id: 'b2',
          type: 'bulletListItem',
          content: [
            {
              type: 'link',
              href: 'https://example.com',
              content: [{ type: 'text', text: '-Link' }],
            },
          ],
          children: [
            { id: 'b3', type: 'paragraph', content: [{ type: 'text', text: '-Kind' }] },
          ],
        },
      ],
    }
    expect(blockPlainText(block)).toBe('Eltern-Link-Kind')
  })

  it('behandelt table-artigen Nicht-Array-content als Objekt', () => {
    // BlockNote-Tabellen: content ist ein Objekt mit rows statt Array.
    const block: ResourceBlock = {
      id: 't1',
      type: 'table',
      content: {
        type: 'tableContent',
        rows: [{ cells: [[{ type: 'text', text: 'Zelle' }]] }],
      },
    }
    // rows/cells werden nicht rekursiv besucht (walk folgt nur content/children).
    expect(blockPlainText(block)).toBe('')
  })
})

describe('blockPreview', () => {
  it('liefert getrimmten Text unterhalb der Vorschau-Grenze unveraendert', () => {
    expect(blockPreview(paragraph('b1', '  kurz  '))).toBe('kurz')
  })

  it('faellt bei leerem Text auf den Block-Typ zurueck', () => {
    expect(blockPreview({ id: 'b1', type: 'image' })).toBe('(image)')
  })

  it('faellt bei nur-Whitespace-Text auf den Block-Typ zurueck', () => {
    expect(blockPreview(paragraph('b1', '   '))).toBe('(paragraph)')
  })

  it('kuerzt Text ueber 120 Zeichen mit Ellipse', () => {
    const long = 'x'.repeat(150)
    const preview = blockPreview(paragraph('b1', long))
    expect(preview).toBe(`${'x'.repeat(120)}…`)
    expect(preview.length).toBe(121)
  })

  it('kuerzt Text mit exakt 120 Zeichen nicht', () => {
    const exact = 'y'.repeat(120)
    expect(blockPreview(paragraph('b1', exact))).toBe(exact)
  })
})

describe('isHeadingBlock', () => {
  it('erkennt das BlockNote-Schema type="heading"', () => {
    expect(isHeadingBlock(heading('h1', 'Titel', 2))).toBe(true)
  })

  it('erkennt Legacy-Varianten wie heading_2', () => {
    expect(isHeadingBlock({ id: 'h1', type: 'heading_2' })).toBe(true)
  })

  it('lehnt Nicht-Heading-Bloecke ab', () => {
    expect(isHeadingBlock(paragraph('b1', 'Text'))).toBe(false)
  })

  it('lehnt Bloecke mit Nicht-String-Typ ab', () => {
    const broken = { id: 'b1', type: 7 } as unknown as ResourceBlock
    expect(isHeadingBlock(broken)).toBe(false)
  })
})

describe('sectionPreview', () => {
  it('liefert leeren String, wenn der Anker nicht gefunden wird', () => {
    expect(sectionPreview([paragraph('b1', 'Text')], 'missing')).toBe('')
  })

  it('liefert leeren String, wenn der Anker kein Heading ist', () => {
    expect(sectionPreview([paragraph('b1', 'Text')], 'b1')).toBe('')
  })

  it('sammelt Bloecke bis zum naechsten Heading gleichen Levels', () => {
    const blocks = [
      heading('h1', 'Abschnitt A', 2),
      paragraph('p1', 'Erster Satz.'),
      paragraph('p2', 'Zweiter Satz.'),
      heading('h2', 'Abschnitt B', 2),
      paragraph('p3', 'Gehoert nicht dazu.'),
    ]
    expect(sectionPreview(blocks, 'h1')).toBe('Erster Satz. Zweiter Satz.')
  })

  it('stoppt auch an einem Heading niedrigeren Levels', () => {
    const blocks = [
      heading('h1', 'Unterabschnitt', 3),
      paragraph('p1', 'Inhalt.'),
      heading('h2', 'Kapitel', 1),
      paragraph('p2', 'Fremd.'),
    ]
    expect(sectionPreview(blocks, 'h1')).toBe('Inhalt.')
  })

  it('nimmt tiefere Headings inklusive deren Inhalt mit', () => {
    const blocks = [
      heading('h1', 'Kapitel', 1),
      paragraph('p1', 'Intro.'),
      heading('h2', 'Unterpunkt', 2),
      paragraph('p2', 'Detail.'),
    ]
    expect(sectionPreview(blocks, 'h1')).toBe('Intro. Unterpunkt Detail.')
  })

  it('ueberspringt leere Bloecke innerhalb der Section', () => {
    const blocks = [
      heading('h1', 'Titel', 2),
      { id: 'empty', type: 'paragraph' } as ResourceBlock,
      paragraph('p1', '   '),
      paragraph('p2', 'Substanz.'),
    ]
    expect(sectionPreview(blocks, 'h1')).toBe('Substanz.')
  })

  it('liefert leeren String, wenn die Section keinen Text enthaelt', () => {
    const blocks = [heading('h1', 'Titel', 2), { id: 'empty', type: 'image' } as ResourceBlock]
    expect(sectionPreview(blocks, 'h1')).toBe('')
  })

  it('liefert leeren String fuer ein Heading am Dokumentende', () => {
    expect(sectionPreview([heading('h1', 'Letztes', 2)], 'h1')).toBe('')
  })

  it('kuerzt Sections ueber 200 Zeichen mit Ellipse', () => {
    const blocks = [heading('h1', 'Titel', 2), paragraph('p1', 'z'.repeat(250))]
    const preview = sectionPreview(blocks, 'h1')
    expect(preview).toBe(`${'z'.repeat(200)}…`)
  })

  it('leitet das Level aus dem Legacy-Suffix heading_<n> ab', () => {
    const blocks = [
      { id: 'h1', type: 'heading_2' } as ResourceBlock,
      paragraph('p1', 'Legacy-Inhalt.'),
      { id: 'h2', type: 'heading_2' } as ResourceBlock,
      paragraph('p2', 'Fremd.'),
    ]
    expect(sectionPreview(blocks, 'h1')).toBe('Legacy-Inhalt.')
  })

  it('faellt bei kaputtem Legacy-Suffix auf Level 1 zurueck', () => {
    const blocks = [
      { id: 'h1', type: 'heading_x' } as ResourceBlock,
      paragraph('p1', 'Inhalt.'),
      // Level-1-Anker: das folgende Level-2-Heading beendet die Section nicht.
      heading('h2', 'Unterpunkt', 2),
      paragraph('p2', 'Auch dabei.'),
    ]
    expect(sectionPreview(blocks, 'h1')).toBe('Inhalt. Unterpunkt Auch dabei.')
  })

  it('faellt ohne props.level und ohne Suffix auf Level 1 zurueck', () => {
    const blocks = [
      { id: 'h1', type: 'heading' } as ResourceBlock,
      paragraph('p1', 'Inhalt.'),
      heading('h2', 'Stopper', 1),
      paragraph('p2', 'Fremd.'),
    ]
    expect(sectionPreview(blocks, 'h1')).toBe('Inhalt.')
  })
})
