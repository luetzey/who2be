import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ANNOUNCE_DELAY_MS, BudgetNote, EditorFooter } from './EditorFooter'
import { CONTENT_BUDGETS } from './contentBudgets.generated'
import {
  countChars,
  countWords,
  estimateLength,
  estimateText,
  estimateTokens,
  LENGTH_HELP_HREF,
  LONG_TOKEN_THRESHOLD,
  overBudget,
} from './estimate'
import i18n from '@/i18n'

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

// --- Richtwerte (ADR-0063, Builder schlank B5) ------------------------------

const words = (n: number) => Array.from({ length: n }, () => 'wort').join(' ')

describe('countWords (Zählregel der API)', () => {
  it('zählt Wörter mit Buchstabe oder Ziffer, ohne reine Zeichen', () => {
    expect(countWords([paragraph(text('eins, zwei - drei | 4 —'))])).toBe(4)
    expect(countWords([])).toBe(0)
    expect(countWords(undefined)).toBe(0)
  })

  it('lässt Codeblöcke aus, zählt Kinder, Tabellen und eine Pill als ein Wort', () => {
    const blocks = [
      paragraph(text('Lies '), pill('Onboarding-Leitfaden mit vielen Wörtern'), text(' zuerst.')),
      { type: 'codeBlock', props: {}, content: [text('print("nicht gezählt")')], children: [] },
      {
        type: 'bulletListItem',
        content: [text('Oben')],
        children: [{ type: 'bulletListItem', content: [text('Unten')], children: [] }],
      },
      {
        type: 'table',
        content: { type: 'tableContent', rows: [{ cells: [[text('A')], [text('B C')]] }] },
        children: [],
      },
    ]
    // Lies + Pill + zuerst. (3) + Oben Unten (2) + A B C (3) = 8
    expect(countWords(blocks)).toBe(8)
  })

  it('zählt die Nummer einer nummerierten Liste wie das Markdown der API', () => {
    expect(countWords([{ type: 'numberedListItem', content: [text('eins zwei')], children: [] }])).toBe(3)
  })
})

describe('Richtwerte aus der erzeugten Konstante', () => {
  it('trägt die Owner-Werte W2', () => {
    expect(CONTENT_BUDGETS.profile).toMatchObject({ target: 400, warn: 600 })
    expect(CONTENT_BUDGETS.mode).toMatchObject({ target: 150, warn: 250 })
    expect(CONTENT_BUDGETS.mode_count).toMatchObject({ target: 3, warn: 5 })
    expect(CONTENT_BUDGETS.playbook_body).toMatchObject({ target: 1000, warn: 1500 })
  })

  it('warnt ab der Schwelle, nicht darunter (wie die API)', () => {
    expect(overBudget('profile', 599)).toBe(false)
    expect(overBudget('profile', 600)).toBe(true)
    expect(overBudget('mode', 249)).toBe(false)
    expect(overBudget('mode', 250)).toBe(true)
    expect(overBudget('mode_count', 4)).toBe(false)
    expect(overBudget('mode_count', 5)).toBe(true)
    expect(overBudget('playbook_body', 1499)).toBe(false)
    expect(overBudget('playbook_body', 1500)).toBe(true)
  })
})

describe('EditorFooter mit Richtwert', () => {
  afterEach(async () => {
    await i18n.changeLanguage('de')
  })

  it('ohne budget keine Richtwert-Zeile', () => {
    render(<EditorFooter blocks={[paragraph(text(words(10)))]} />)
    expect(screen.queryByTestId('budget-note-profile')).not.toBeInTheDocument()
    expect(screen.queryByTestId('editor-footer-budget-help')).not.toBeInTheDocument()
  })

  it('unter der Schwelle: „412 Wörter · Richtwert 400“, ohne Warnfarbe', () => {
    render(<EditorFooter blocks={[paragraph(text(words(412)))]} budget="profile" />)
    const note = screen.getByTestId('budget-note-profile')
    expect(note).toHaveTextContent('412 Wörter · Richtwert 400')
    expect(note).toHaveAttribute('data-over', 'false')
    expect(note).not.toHaveClass('text-brand')
  })

  it('ab der Schwelle: Text sagt „über dem Richtwert“, Farbe nur zusätzlich', () => {
    render(<EditorFooter blocks={[paragraph(text(words(1450)))]} budget="profile" />)
    const note = screen.getByTestId('budget-note-profile')
    expect(note.textContent).toBe('1\u00a0450 Wörter · über dem Richtwert 400, Abläufe besser in ein Playbook')
    expect(note).toHaveAttribute('data-over', 'true')
    expect(note).toHaveClass('text-brand')
  })

  it('genau auf der Schwelle 600 gilt als darüber, 599 nicht', () => {
    const { rerender } = render(<EditorFooter blocks={[paragraph(text(words(599)))]} budget="profile" />)
    expect(screen.getByTestId('budget-note-profile')).toHaveAttribute('data-over', 'false')
    rerender(<EditorFooter blocks={[paragraph(text(words(600)))]} budget="profile" />)
    expect(screen.getByTestId('budget-note-profile')).toHaveAttribute('data-over', 'true')
  })

  it('Playbook: Richtwert 1 000, Warnung ab 1 500', () => {
    const { rerender } = render(
      <EditorFooter blocks={[paragraph(text(words(1499)))]} budget="playbook_body" />,
    )
    expect(screen.getByTestId('budget-note-playbook_body').textContent).toBe(
      '1\u00a0499 Wörter · Richtwert 1\u00a0000',
    )
    rerender(<EditorFooter blocks={[paragraph(text(words(1500)))]} budget="playbook_body" />)
    expect(screen.getByTestId('budget-note-playbook_body')).toHaveTextContent(
      'über dem Richtwert 1 000, besser teilen oder Nachschlagewissen in eine Resource',
    )
  })

  it('verlinkt den Hilfe-Abschnitt in einem neuen Tab', () => {
    render(
      <MemoryRouter>
        <EditorFooter blocks={[]} budget="profile" />
      </MemoryRouter>,
    )
    const link = screen.getByTestId('editor-footer-budget-help')
    expect(link).toHaveAttribute('href', LENGTH_HELP_HREF)
    expect(LENGTH_HELP_HREF).toBe('/help/persona#laenge')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveTextContent('Richtwerte erklärt')
  })

  it('im Workspace zeigt der Link direkt auf die Hilfe-Seite des Workspace', () => {
    render(
      <MemoryRouter initialEntries={['/w/ws-1/personas/p-1']}>
        <Routes>
          <Route path="/w/:workspaceId/personas/:id" element={<EditorFooter blocks={[]} budget="profile" />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByTestId('editor-footer-budget-help')).toHaveAttribute(
      'href',
      '/w/ws-1/help/persona#laenge',
    )
  })

  it('Englisch: Komma als Tausendertrenner, „guide value“', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })
    render(<EditorFooter blocks={[paragraph(text(words(1450)))]} budget="profile" />)
    expect(screen.getByTestId('budget-note-profile')).toHaveTextContent(
      '1,450 words · over the guide value 400, procedures belong in a playbook',
    )
  })
})

describe('BudgetNote', () => {
  it('Modus und Zahl der Modi, unter und über der Schwelle', () => {
    const { rerender } = render(<BudgetNote element="mode" value={120} />)
    expect(screen.getByTestId('budget-note-mode')).toHaveTextContent('Modus: 120 Wörter · Richtwert 150')
    rerender(<BudgetNote element="mode" value={250} />)
    expect(screen.getByTestId('budget-note-mode')).toHaveTextContent(
      'Modus: 250 Wörter · über dem Richtwert 150, Arbeitsschritte besser in ein Playbook',
    )
    rerender(<BudgetNote element="mode_count" value={1} />)
    expect(screen.getByTestId('budget-note-mode_count')).toHaveTextContent('1 Modus · Richtwert 3')
    rerender(<BudgetNote element="mode_count" value={5} />)
    expect(screen.getByTestId('budget-note-mode_count')).toHaveAttribute('data-over', 'true')
    expect(screen.getByTestId('budget-note-mode_count')).toHaveTextContent('5 Modi · über dem Richtwert 3')
  })
})
