import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PlaybookListToolbar } from './PlaybookListToolbar'

// Responsive-Vertrag #573 (Haelfte A). Die Zahl 40 px stammt aus AK 5 dieses
// Issues, NICHT aus der Norm: `docs/frontend/design-language.md` §11 ist die
// einzige Quelle des Hit-Target-Floors und setzt ihn auf >= 32 px; 40 px ist
// dort die Praeferenz `size="default"`, `size="sm"` (36 px) bleibt zulaessig.
// Die hier gemessenen 28 px der Filter-Chips unterschreiten dagegen den
// Norm-Floor und waeren auch ohne das AK ein Defekt.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1700_573-w3-playbooks-haelfte-a-responsive.md
// gegen das gebaute Stylesheet in Chromium belegt.

const baseProps = {
  counts: { all: 12, attention: 3, active: 7, draft: 2, review: 0, inactive: 0 },
  status: 'all' as const,
  onStatusChange: vi.fn(),
  query: 'Onboarding',
  onQueryChange: vi.fn(),
  active: true,
  onReset: vi.fn(),
  availableTags: ['vertrieb'],
  tag: '',
  onTagChange: vi.fn(),
  availableTypes: ['workflow'],
  type: '',
  onTypeChange: vi.fn(),
  agents: [{ id: 'a-1', name: 'Coach Carla' }],
  agent: 'a-1',
  onAgentChange: vi.fn(),
  locales: [{ value: 'de-DE', label: 'Deutsch (Deutschland)' }],
  locale: 'de-DE',
  onLocaleChange: vi.fn(),
  groupOptions: [{ value: '', label: 'Keine' }],
  group: '',
  onGroupChange: vi.fn(),
}

describe('PlaybookListToolbar — Responsive (#573)', () => {
  it('laesst die Status-Segmentgruppe umbrechen', () => {
    render(<PlaybookListToolbar {...baseProps} />)

    // Gemessen: die Gruppe lief bei 320 px mit vier sichtbaren Segmenten
    // 388,5 px breit in einen 288 px breiten Innenraum (+100,5 px). Ohne
    // `flex-wrap` waechst sie mit jedem weiteren Status weiter.
    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    expect(group).toHaveClass('flex-wrap')
  })

  it('haelt die Segment-Buttons unterhalb md auf dem 40-px-Hit-Target aus AK 5', () => {
    render(<PlaybookListToolbar {...baseProps} />)

    // Gemessen 32 px (`h-8`). `min-h-10` hebt das unterhalb `md` auf 40 px,
    // ab `md` faellt die Verdichtung der Segmentleiste zurueck.
    const segment = screen.getByRole('button', { name: /Alle/ })
    expect(segment).toHaveClass('min-h-10')
    expect(segment).toHaveClass('md:min-h-0')
  })

  it('haelt den Suchfeld-Clear unterhalb md auf dem 40-px-Hit-Target aus AK 5', () => {
    render(<PlaybookListToolbar {...baseProps} />)

    // Gemessen 32 x 32 px (`size-8`). Nur die Hoehe waechst: das `pr-9` des
    // Feldes laesst rechts 36 px Platz, eine breitere Flaeche wuerde den Text
    // ueberdecken.
    const clear = screen.getByRole('button', { name: 'Suche leeren' })
    expect(clear).toHaveClass('h-10')
    expect(clear).toHaveClass('md:h-8')
  })

  it('hebt die Filter-Chips ueber den Norm-Floor aus §11', () => {
    render(<PlaybookListToolbar {...baseProps} />)

    // Gemessen 28 px (`h-7`) — das unterschreitet den in §11 verbindlich
    // gesetzten Floor von >= 32 px und ist unabhaengig von AK 5 ein Defekt.
    for (const name of [
      'Agent-Filter entfernen (Coach Carla)',
      'Sprachfilter entfernen (Deutsch (Deutschland))',
    ]) {
      const chip = screen.getByRole('button', { name })
      expect(chip).toHaveClass('h-10')
      expect(chip).toHaveClass('md:h-7')
    }
  })
})
