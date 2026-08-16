import { describe, expect, it } from 'vitest'

import { buildAnchor, parseAnchoredMarkdown, splitAnchor } from './blocks'

describe('parseAnchoredMarkdown', () => {
  it('trennt Bloecke am Anker-Suffix', () => {
    const md = ['# Titel [#aaaaaaaa]', '', 'Ein Absatz. [#bbbbbbbb]'].join('\n')
    expect(parseAnchoredMarkdown(md)).toEqual([
      { blockId: 'aaaaaaaa', text: '# Titel' },
      { blockId: 'bbbbbbbb', text: 'Ein Absatz.' },
    ])
  })

  it('haelt Code-Bloecke mit Leerzeilen zusammen', () => {
    // Der Anker eines Code-Blocks steht auf eigener Zeile NACH der Fence —
    // ein Split an `\n\n` wuerde den Rumpf hier zerreissen.
    const md = [
      '```python',
      'a = 1',
      '',
      'b = 2',
      '```',
      '[#cccccccc]',
      '',
      'Danach. [#dddddddd]',
    ].join('\n')
    const blocks = parseAnchoredMarkdown(md)
    expect(blocks).toHaveLength(2)
    expect(blocks[0].blockId).toBe('cccccccc')
    expect(blocks[0].text).toBe('```python\na = 1\n\nb = 2\n```')
    expect(blocks[1]).toEqual({ blockId: 'dddddddd', text: 'Danach.' })
  })

  it('haelt mehrzeilige Bloecke zusammen', () => {
    const md = ['- eins', '- zwei [#eeeeeeee]'].join('\n')
    expect(parseAnchoredMarkdown(md)).toEqual([
      { blockId: 'eeeeeeee', text: '- eins\n- zwei' },
    ])
  })

  it('verschluckt Text ohne Anker nicht', () => {
    expect(parseAnchoredMarkdown('Nur Text ohne Anker.')).toEqual([
      { blockId: null, text: 'Nur Text ohne Anker.' },
    ])
  })

  it('liefert fuer leeren Inhalt keine Bloecke', () => {
    expect(parseAnchoredMarkdown('')).toEqual([])
    expect(parseAnchoredMarkdown('\n\n')).toEqual([])
  })
})

describe('buildAnchor / splitAnchor', () => {
  it('baut und zerlegt symmetrisch', () => {
    const anchor = buildAnchor('11111111-2222-3333-4444-555555555555', 'aaaaaaaa')
    expect(anchor).toBe('11111111-2222-3333-4444-555555555555#aaaaaaaa')
    expect(splitAnchor(anchor)).toEqual({
      artifactId: '11111111-2222-3333-4444-555555555555',
      blockId: 'aaaaaaaa',
    })
  })

  it('zerlegt auch KB-Belege der Form artifact:<uuid>#<block>', () => {
    expect(splitAnchor('artifact:abc#b1')).toEqual({
      artifactId: 'artifact:abc',
      blockId: 'b1',
    })
  })

  it('liefert null ohne verwertbaren Trenner', () => {
    expect(splitAnchor('ohne-trenner')).toBeNull()
    expect(splitAnchor('#nurblock')).toBeNull()
    expect(splitAnchor('nurartifact#')).toBeNull()
  })
})
