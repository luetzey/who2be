import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { VersionDiff } from '@/api/types'

import { VersionDiffView } from './VersionDiffView'

function makeDiff(overrides: Partial<VersionDiff> = {}): VersionDiff {
  return {
    version: 2,
    against: 'active',
    against_version: 1,
    identical: false,
    changes: [],
    ...overrides,
  }
}

describe('VersionDiffView', () => {
  it('meldet identische Versionen', () => {
    render(<VersionDiffView diff={makeDiff({ identical: true, against_version: 1 })} />)
    expect(screen.getByText('Keine Unterschiede zwischen v2 und v1.')).toBeInTheDocument()
  })

  it('rendert ohne before_text/after_text den Feld-Diff wie bisher (Fallback)', () => {
    render(
      <VersionDiffView
        diff={makeDiff({
          changes: [
            { path: 'description', op: 'changed', before: 'alt', after: 'neu' },
            { path: 'blocks[b1]', op: 'added', before: null, after: { id: 'b1' } },
          ],
        })}
      />,
    )
    expect(screen.getByText('description')).toBeInTheDocument()
    expect(screen.getByText('blocks[b1]')).toBeInTheDocument()
    // JSON-Wert-Rendering des Content-Felds bleibt im Fallback erhalten.
    expect(screen.getByText(/\{"id":"b1"\}/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Inhalts-Diff')).not.toBeInTheDocument()
  })

  it('rendert mit before_text/after_text einen unified Zeilen-Diff', () => {
    render(
      <VersionDiffView
        diff={makeDiff({
          before_text: 'Zeile eins\nZeile zwei',
          after_text: 'Zeile eins\nZeile neu',
          changes: [{ path: 'blocks[b1]', op: 'changed', before: {}, after: {} }],
        })}
      />,
    )
    const list = screen.getByLabelText('Inhalts-Diff')
    expect(list).toBeInTheDocument()
    expect(screen.getByText('@@ -1,2 +1,2 @@')).toBeInTheDocument()
    expect(screen.getByText('Zeile zwei')).toBeInTheDocument()
    expect(screen.getByText('Zeile neu')).toBeInTheDocument()
    expect(screen.getByText('Entfernte Zeile')).toBeInTheDocument()
    expect(screen.getByText('Hinzugefügte Zeile')).toBeInTheDocument()
    // Content-Feld-Aenderung erscheint NICHT mehr als JSON-Badge.
    expect(screen.queryByText('blocks[b1]')).not.toBeInTheDocument()
  })

  it('zeigt Nicht-Content-Felder weiterhin als kompakte Badges', () => {
    render(
      <VersionDiffView
        diff={makeDiff({
          before_text: 'a',
          after_text: 'b',
          changes: [
            { path: 'name', op: 'changed', before: 'Alt', after: 'Neu' },
            { path: 'tags', op: 'changed', before: ['x'], after: ['y'] },
            { path: 'body', op: 'changed', before: '[]', after: '[]' },
            { path: 'content.blocks[b2]', op: 'removed', before: {}, after: null },
            { path: 'modes[0].name', op: 'changed', before: 'A', after: 'B' },
          ],
        })}
      />,
    )
    expect(screen.getByText('name')).toBeInTheDocument()
    expect(screen.getByText('tags')).toBeInTheDocument()
    expect(screen.queryByText('body')).not.toBeInTheDocument()
    expect(screen.queryByText('content.blocks[b2]')).not.toBeInTheDocument()
    expect(screen.queryByText('modes[0].name')).not.toBeInTheDocument()
  })

  it('laesst den Zeilen-Diff weg, wenn beide Texte gleich sind', () => {
    render(
      <VersionDiffView
        diff={makeDiff({
          before_text: 'gleich',
          after_text: 'gleich',
          changes: [{ path: 'tags', op: 'changed', before: ['x'], after: ['y'] }],
        })}
      />,
    )
    expect(screen.queryByLabelText('Inhalts-Diff')).not.toBeInTheDocument()
    expect(screen.getByText('tags')).toBeInTheDocument()
  })
})
