import { describe, expect, it } from 'vitest'

import { computeLineDiff, formatHunkHeader } from './lineDiff'

describe('computeLineDiff', () => {
  it('liefert keine Hunks fuer identische Texte', () => {
    expect(computeLineDiff('a\nb\nc', 'a\nb\nc')).toEqual([])
  })

  it('liefert keine Hunks fuer zwei leere Texte', () => {
    expect(computeLineDiff('', '')).toEqual([])
  })

  it('markiert alles als added, wenn before leer ist', () => {
    const hunks = computeLineDiff('', 'eins\nzwei')
    expect(hunks).toHaveLength(1)
    expect(hunks[0].lines).toEqual([
      { kind: 'added', text: 'eins', beforeLine: null, afterLine: 1 },
      { kind: 'added', text: 'zwei', beforeLine: null, afterLine: 2 },
    ])
    expect(hunks[0].beforeCount).toBe(0)
    expect(hunks[0].afterStart).toBe(1)
    expect(hunks[0].afterCount).toBe(2)
  })

  it('markiert alles als removed, wenn after leer ist', () => {
    const hunks = computeLineDiff('eins\nzwei', '')
    expect(hunks).toHaveLength(1)
    expect(hunks[0].lines.map((l) => l.kind)).toEqual(['removed', 'removed'])
    expect(hunks[0].afterCount).toBe(0)
  })

  it('rendert eine Aenderung als removed+added mit Kontextzeilen', () => {
    const before = 'a\nb\nc\nd\ne'
    const after = 'a\nb\nX\nd\ne'
    const hunks = computeLineDiff(before, after)
    expect(hunks).toHaveLength(1)
    expect(hunks[0].lines.map((l) => [l.kind, l.text])).toEqual([
      ['context', 'a'],
      ['context', 'b'],
      ['removed', 'c'],
      ['added', 'X'],
      ['context', 'd'],
      ['context', 'e'],
    ])
  })

  it('begrenzt Kontext und trennt weit auseinanderliegende Aenderungen in Hunks', () => {
    const mid = Array.from({ length: 20 }, (_, i) => `m${i}`)
    const before = ['start', ...mid, 'ende'].join('\n')
    const after = ['START', ...mid, 'ENDE'].join('\n')
    const hunks = computeLineDiff(before, after, 3)
    expect(hunks).toHaveLength(2)
    // Hunk 1: Aenderung an Zeile 1 + max. 3 Kontextzeilen danach.
    expect(hunks[0].lines.map((l) => l.kind)).toEqual(['removed', 'added', ...Array(3).fill('context')])
    // Hunk 2: 3 Kontextzeilen davor + Aenderung an der letzten Zeile.
    expect(hunks[1].lines.map((l) => l.kind)).toEqual([...Array(3).fill('context'), 'removed', 'added'])
    expect(hunks[1].beforeStart).toBe(19)
  })

  it('fasst nahe Aenderungen in einen Hunk zusammen', () => {
    const before = 'a\nb\nc\nd\ne\nf'
    const after = 'A\nb\nc\nd\ne\nF'
    const hunks = computeLineDiff(before, after, 3)
    expect(hunks).toHaveLength(1)
  })

  it('zaehlt Zeilennummern beider Seiten korrekt', () => {
    const hunks = computeLineDiff('a\nb', 'a\nneu\nb')
    expect(hunks).toHaveLength(1)
    const added = hunks[0].lines.find((l) => l.kind === 'added')
    expect(added).toEqual({ kind: 'added', text: 'neu', beforeLine: null, afterLine: 2 })
    const lastContext = hunks[0].lines.at(-1)
    expect(lastContext).toEqual({ kind: 'context', text: 'b', beforeLine: 2, afterLine: 3 })
  })

  it('behandelt lange Zeilen ohne Umbruch als eine Zeile', () => {
    const long = 'x'.repeat(5000)
    const hunks = computeLineDiff('kurz', long)
    expect(hunks).toHaveLength(1)
    expect(hunks[0].lines.map((l) => l.kind)).toEqual(['removed', 'added'])
    expect(hunks[0].lines[1].text).toHaveLength(5000)
  })
})

describe('formatHunkHeader', () => {
  it('formatiert den Git-Hunk-Header', () => {
    expect(
      formatHunkHeader({ beforeStart: 3, beforeCount: 4, afterStart: 3, afterCount: 5, lines: [] }),
    ).toBe('@@ -3,4 +3,5 @@')
  })

  it('nutzt Start 0 bei leerer Seite', () => {
    const hunks = computeLineDiff('', 'neu')
    expect(formatHunkHeader(hunks[0])).toBe('@@ -0,0 +1,1 @@')
  })
})
