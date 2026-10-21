import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ANNOUNCE_DELAY_MS, EditorFooter } from './EditorFooter'
import { countChars, estimateLength, estimateText, estimateTokens, LONG_TOKEN_THRESHOLD } from './estimate'

// Schätzfunktion und Fußzeile (Editor-Paket P3). Die Fußzeile braucht kein
// ProseMirror und läuft deshalb in jsdom; das Tippen im echten Editor prüft
// e2e/editor-profiles.spec.ts.

const text = (value: string) => ({ type: 'text', text: value, styles: {} })
const pill = (label: string) => ({
  type: 'placeholder',
  props: { kind: 'playbook', target_id: 'b1f0c9b8-0000-4000-8000-000000000001', label },
})
const paragraph = (...content: unknown[]) => ({ type: 'paragraph', props: {}, content, children: [] })

describe('estimateLength', () => {
  it('leeres Dokument: 0 Zeichen, 0 Token, nicht lang', () => {
    expect(estimateLength([])).toEqual({ chars: 0, tokens: 0, long: false })
    expect(estimateLength([paragraph(), paragraph()])).toEqual({ chars: 0, tokens: 0, long: false })
    expect(estimateLength(undefined)).toEqual({ chars: 0, tokens: 0, long: false })
  })

  it('zählt Umlaute als ein Zeichen, auch zerlegt (NFD)', () => {
    const composed = 'Grüße'
    const decomposed = composed.normalize('NFD')
    expect(decomposed.length).toBe(6)
    expect(countChars(composed)).toBe(5)
    expect(countChars(decomposed)).toBe(5)
    expect(estimateLength([paragraph(text(decomposed))]).chars).toBe(5)
  })

  it('zählt Emoji außerhalb der BMP als ein Zeichen', () => {
    expect(countChars('ok 👍')).toBe(4)
  })

  it('rechnet Pills nicht ein', () => {
    const withPill = [paragraph(text('Lies '), pill('Onboarding-Leitfaden'), text(' zuerst.'))]
    expect(estimateText(withPill)).toBe('Lies  zuerst.')
    expect(estimateLength(withPill).chars).toBe(13)
    expect(estimateLength([paragraph(pill('Nur ein Verweis'))])).toEqual({ chars: 0, tokens: 0, long: false })
    // Auch eine Pill, die (etwa aus einem Import) Text mitbringt, zählt 0.
    const pillWithText = { ...pill('Mit Text'), text: 'aufgelöster Inhalt', content: [text('mehr')] }
    expect(estimateLength([paragraph(text('a'), pillWithText)]).chars).toBe(1)
  })

  it('trennt Blöcke mit einem Umbruch und zählt Kinder, Links und Tabellen', () => {
    const blocks = [
      paragraph(text('Siehe '), { type: 'link', href: 'https://who2be.de', content: [text('Doku')] }),
      paragraph(),
      {
        type: 'bulletListItem',
        content: [text('Oben')],
        children: [{ type: 'bulletListItem', content: [text('Unten')], children: [] }],
      },
      {
        type: 'table',
        content: {
          type: 'tableContent',
          rows: [
            { cells: [[text('A')], [text('B')]] },
            { cells: [{ type: 'tableCell', content: [text('C')] }, { type: 'tableCell', content: [] }] },
          ],
        },
        children: [],
      },
    ]
    expect(estimateText(blocks)).toBe('Siehe Doku\nOben\nUnten\nA | B\nC | ')
  })

  it('Token = Zeichen/4 auf 10 gerundet, bei Text mindestens 10', () => {
    expect(estimateTokens(0)).toBe(0)
    expect(estimateTokens(1)).toBe(10)
    expect(estimateTokens(39)).toBe(10)
    expect(estimateTokens(1240)).toBe(310)
    expect(estimateTokens(1259)).toBe(310)
    expect(estimateTokens(1260)).toBe(320)
  })

  it('markiert ab 8 000 geschätzten Token als lang', () => {
    const below = estimateLength([paragraph(text('x'.repeat(LONG_TOKEN_THRESHOLD * 4 - 21)))])
    expect(below.tokens).toBe(7990)
    expect(below.long).toBe(false)
    const at = estimateLength([paragraph(text('x'.repeat(LONG_TOKEN_THRESHOLD * 4)))])
    expect(at.tokens).toBe(8000)
    expect(at.long).toBe(true)
  })
})

describe('EditorFooter', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('zeigt Zeichen und Token mit Tausendertrennung', () => {
    render(<EditorFooter blocks={[paragraph(text('x'.repeat(1240)))]} />)
    expect(screen.getByTestId('editor-footer-length')).toHaveTextContent(
      '≈ 1.240 Zeichen · ≈ 310 Token (geschätzt)',
    )
    expect(screen.queryByTestId('editor-footer-long')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Wie wird die Länge geschätzt?' })).toBeInTheDocument()
  })

  it('zeigt „· lang“ ab 8 000 Token', () => {
    render(<EditorFooter blocks={[paragraph(text('x'.repeat(32_000)))]} />)
    expect(screen.getByTestId('editor-footer-long')).toHaveTextContent('· lang')
  })

  it('Live-Region ist höflich und meldet beim Öffnen nichts', () => {
    render(<EditorFooter blocks={[paragraph(text('Hallo'))]} />)
    const live = screen.getByTestId('editor-footer-live')
    expect(live).toHaveAttribute('aria-live', 'polite')
    // Die sichtbare Zeile ist keine Live-Region.
    expect(screen.getByTestId('editor-footer-length').closest('[aria-live]')).toBeNull()
    act(() => {
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS * 3)
    })
    expect(live).toHaveTextContent('')
  })

  it('meldet gedrosselt erst 1 s nach der letzten Änderung', () => {
    const { rerender } = render(<EditorFooter blocks={[paragraph(text('Hallo'))]} />)
    const live = screen.getByTestId('editor-footer-live')

    rerender(<EditorFooter blocks={[paragraph(text('Hallo W'))]} />)
    act(() => {
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS - 100)
    })
    rerender(<EditorFooter blocks={[paragraph(text('Hallo Welt'))]} />)
    act(() => {
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS - 100)
    })
    // Jeder Tastendruck schiebt die Meldung auf.
    expect(live).toHaveTextContent('')

    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(live).toHaveTextContent('Länge: etwa 10 Zeichen, etwa 10 Token (geschätzt)')
  })

  it('meldet nichts, wenn die Zahl vor Ablauf zum Stand beim Öffnen zurückkehrt', () => {
    const { rerender } = render(<EditorFooter blocks={[paragraph(text('Hallo'))]} />)
    rerender(<EditorFooter blocks={[paragraph(text('Hallo!'))]} />)
    rerender(<EditorFooter blocks={[paragraph(text('Hallo'))]} />)
    act(() => {
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS * 2)
    })
    expect(screen.getByTestId('editor-footer-live')).toHaveTextContent('')
  })
})
