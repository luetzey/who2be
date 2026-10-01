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

// Mobil-Spec M4, Owner-Weiche W2=a. Vorher scrollte der Wrapper
// (`overflow-x-auto` um `ul.min-w-max`, Zeilen `whitespace-pre`) bei 320 px
// 9.189 px Inhalt in 208 px. jsdom hat kein Layout, deshalb ist das hier ein
// Klassen- und DOM-Vertrag. Die Layout-Zahlen (Chromium gegen das gebaute
// Stylesheet, 320/390/430/1280) stehen in
// .claude/plan/2026-10-01-1740_mobil-p4-diff-umbruch.md und im PR.
describe('VersionDiffView – Umbruch statt Seitwaerts-Scroll (Mobil-Spec M4)', () => {
  const URL_NO_BREAK =
    'https://intranet.example.com/richtlinien/feedbackkulturundgespraechsfuehrung/leitfaden.pdf'

  function renderTextDiff() {
    return render(
      <VersionDiffView
        diff={makeDiff({
          before_text: 'Titel\n\nAlte Beschreibung',
          after_text: `Titel\n\nNeue Beschreibung ${URL_NO_BREAK}`,
        })}
      />,
    )
  }

  it('hat keinen horizontalen Scroller und keine Mindestbreite mehr', () => {
    const { container } = renderTextDiff()
    const list = screen.getByLabelText('Inhalts-Diff')
    expect(list).not.toHaveClass('min-w-max')
    expect(list.parentElement).not.toHaveClass('overflow-x-auto')
    // Auch kein anderes Element im Diff haelt Zeilen ungebrochen oder scrollt.
    // Klassen einzeln pruefen: `not.toHaveClass(a, b)` schluege nur an, wenn
    // ALLE zugleich gesetzt waeren.
    for (const el of container.querySelectorAll('*')) {
      for (const cls of ['overflow-x-auto', 'overflow-auto', 'overflow-x-scroll', 'min-w-max']) {
        expect(el).not.toHaveClass(cls)
      }
      if (el.getAttribute('data-testid') !== 'diff-gutter') {
        expect(el).not.toHaveClass('whitespace-pre')
      }
    }
  })

  it('setzt jede Zeile als Grid mit fester Rinne links und umbrechendem Text', () => {
    renderTextDiff()
    const lines = screen.getByLabelText('Inhalts-Diff').querySelectorAll('li[data-kind]')
    expect(lines.length).toBeGreaterThan(0)
    for (const line of lines) {
      expect(line).toHaveClass('grid', 'grid-cols-[1.25rem_1fr]')
      const [gutter, text] = Array.from(line.children)
      expect(gutter).toHaveAttribute('data-testid', 'diff-gutter')
      // Folgezeilen stehen in der zweiten Spalte, also unter dem Text.
      expect(text).toHaveAttribute('data-testid', 'diff-line-text')
      expect(text).toHaveClass('min-w-0', 'whitespace-pre-wrap', 'wrap-anywhere')
    }
    // Die URL ohne Trennstelle steht in der umbrechenden Text-Spalte.
    expect(screen.getByText(new RegExp(URL_NO_BREAK.replaceAll('.', '\\.')))).toHaveClass(
      'wrap-anywhere',
    )
    // Auch die Hunk-Kopfzeile darf brechen.
    expect(screen.getByText('@@ -1,3 +1,3 @@')).toHaveClass('wrap-anywhere')
  })

  it('zeigt +/- sichtbar in der Rinne und behaelt die Screenreader-Praefixe', () => {
    renderTextDiff()
    const removed = screen.getByLabelText('Inhalts-Diff').querySelector('li[data-kind="removed"]')
    const added = screen.getByLabelText('Inhalts-Diff').querySelector('li[data-kind="added"]')
    const context = screen.getByLabelText('Inhalts-Diff').querySelector('li[data-kind="context"]')

    // Farbe ist nicht das einzige Merkmal: das Zeichen steht sichtbar da,
    // nur fuer Screenreader ausgeblendet (die lesen das Wort-Praefix).
    const removedGutter = removed?.querySelector('[data-testid="diff-gutter"]')
    expect(removedGutter).toHaveTextContent('-')
    expect(removedGutter).toHaveAttribute('aria-hidden', 'true')
    expect(removedGutter).not.toHaveClass('sr-only')
    expect(added?.querySelector('[data-testid="diff-gutter"]')).toHaveTextContent('+')

    // Das Praefix steht im Text-Element vor dem Inhalt; der zugaengliche
    // Text der Zeile lautet also „Entfernte Zeile Alte Beschreibung".
    const removedText = removed?.querySelector('[data-testid="diff-line-text"]')
    expect(removedText?.firstElementChild).toHaveClass('sr-only')
    expect(removedText).toHaveTextContent('Entfernte Zeile Alte Beschreibung')
    expect(added?.querySelector('[data-testid="diff-line-text"]')).toHaveTextContent(
      /^Hinzugefügte Zeile Neue Beschreibung/,
    )
    // Kontextzeilen bekommen kein Praefix.
    expect(context?.querySelector('.sr-only')).toBeNull()
  })
})
