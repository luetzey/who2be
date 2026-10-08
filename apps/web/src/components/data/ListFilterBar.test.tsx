import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FacetSpec, StatusChipOption, StatusCounts } from '@/lib/listFilter'
import { axe } from '@/test/a11y'

import { ListFilterBar } from './ListFilterBar'

const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', () => ({ useIsMobile: () => viewport.mobile }))

beforeEach(() => {
  viewport.mobile = false
})

function counts(overrides: Partial<StatusCounts> = {}): StatusCounts {
  return { all: 0, attention: 0, draft: 0, review: 0, active: 0, inactive: 0, ...overrides }
}

function baseProps() {
  return {
    idPrefix: 'test',
    counts: counts({ all: 5, attention: 2, draft: 1, review: 1, active: 3 }),
    status: 'all' as const,
    onStatusChange: vi.fn(),
    query: '',
    onQueryChange: vi.fn(),
    active: false,
    onReset: vi.fn(),
  }
}

describe('ListFilterBar', () => {
  it('rendert Status-Chips mit Zaehler und ruft onStatusChange', () => {
    const props = baseProps()
    render(<ListFilterBar {...props} />)

    const attention = screen.getByRole('button', { name: /Braucht Aufmerksamkeit/ })
    expect(attention).toHaveTextContent('2')
    fireEvent.click(attention)
    expect(props.onStatusChange).toHaveBeenCalledWith('attention')

    fireEvent.click(screen.getByRole('button', { name: /Aktiv/ }))
    expect(props.onStatusChange).toHaveBeenCalledWith('active')
  })

  it('blendet den Attention-Chip aus, wenn es keinen gibt und er nicht gewaehlt ist', () => {
    render(<ListFilterBar {...baseProps()} counts={counts({ all: 3, active: 3 })} />)
    expect(screen.queryByRole('button', { name: /Braucht Aufmerksamkeit/ })).not.toBeInTheDocument()
  })

  it('zeigt einen Status-Chip mit 0 nur, wenn er aktuell gewaehlt ist', () => {
    render(
      <ListFilterBar
        {...baseProps()}
        status="inactive"
        counts={counts({ all: 5, active: 5, inactive: 0 })}
      />,
    )
    expect(screen.getByRole('button', { name: /Inaktiv/ })).toBeInTheDocument()
  })

  it('meldet Freitext ueber das Suchfeld', () => {
    const props = baseProps()
    render(<ListFilterBar {...props} />)
    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'foo' } })
    expect(props.onQueryChange).toHaveBeenCalledWith('foo')
  })

  it('rendert Tag-Select nur mit Optionen und meldet Auswahl', () => {
    const props = baseProps()
    render(<ListFilterBar {...props} availableTags={['a', 'b']} tag="" onTagChange={props.onQueryChange} />)
    const select = screen.getByLabelText('Tag')
    fireEvent.change(select, { target: { value: 'b' } })
    expect(props.onQueryChange).toHaveBeenCalledWith('b')
  })

  it('rendert Typ-Select mit uebersetzten Labels', () => {
    const onTypeChange = vi.fn()
    render(
      <ListFilterBar
        {...baseProps()}
        availableTypes={['workflow']}
        type=""
        onTypeChange={onTypeChange}
        typeLabel={(value) => value.toUpperCase()}
      />,
    )
    expect(screen.getByRole('option', { name: 'WORKFLOW' })).toBeInTheDocument()
  })

  it('rendert Agent-Select mit Optionen und meldet Auswahl', () => {
    const onAgentChange = vi.fn()
    render(
      <ListFilterBar
        {...baseProps()}
        agents={[
          { id: 'a1', name: 'Support-Bot' },
          { id: 'a2', name: 'QA-Bot' },
        ]}
        agent=""
        onAgentChange={onAgentChange}
      />,
    )
    const select = screen.getByLabelText('Agent')
    expect(screen.getByRole('option', { name: 'Support-Bot' })).toBeInTheDocument()
    fireEvent.change(select, { target: { value: 'a2' } })
    expect(onAgentChange).toHaveBeenCalledWith('a2')
  })

  it('zeigt den aktiven Agent-Filter als entfernbaren Chip mit Agent-Name', () => {
    const onAgentChange = vi.fn()
    render(
      <ListFilterBar
        {...baseProps()}
        agents={[{ id: 'a1', name: 'Support-Bot' }]}
        agent="a1"
        onAgentChange={onAgentChange}
      />,
    )
    const chip = screen.getByRole('button', { name: /Agent-Filter entfernen \(Support-Bot\)/ })
    expect(chip).toHaveTextContent('Agent: Support-Bot')
    fireEvent.click(chip)
    expect(onAgentChange).toHaveBeenCalledWith('')
  })

  it('faellt beim Chip auf die rohe ID zurueck, wenn der Agent unbekannt ist', () => {
    render(
      <ListFilterBar {...baseProps()} agents={[]} agent="a-geloescht" onAgentChange={vi.fn()} />,
    )
    // Kein Select (keine Agenten), aber der Chip bleibt entfernbar.
    expect(screen.queryByLabelText('Agent')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Agent-Filter entfernen \(a-geloescht\)/ }),
    ).toBeInTheDocument()
  })

  it('rendert Group-by-Select mit Optionen und meldet Auswahl', () => {
    const onGroupChange = vi.fn()
    render(
      <ListFilterBar
        {...baseProps()}
        groupOptions={[
          { value: '', label: 'Keine Gruppierung' },
          { value: 'type', label: 'Nach Typ' },
        ]}
        group=""
        onGroupChange={onGroupChange}
      />,
    )
    const select = screen.getByLabelText('Gruppieren')
    expect(screen.getByRole('option', { name: 'Keine Gruppierung' })).toBeInTheDocument()
    fireEvent.change(select, { target: { value: 'type' } })
    expect(onGroupChange).toHaveBeenCalledWith('type')
  })

  it('rendert kein Group-by-Select ohne Optionen oder Handler', () => {
    const { rerender } = render(<ListFilterBar {...baseProps()} />)
    expect(screen.queryByLabelText('Gruppieren')).not.toBeInTheDocument()
    rerender(
      <ListFilterBar
        {...baseProps()}
        groupOptions={[{ value: '', label: 'Keine Gruppierung' }]}
      />,
    )
    expect(screen.queryByLabelText('Gruppieren')).not.toBeInTheDocument()
  })

  it('zeigt den Reset-Button nur bei aktiven Filtern', () => {
    const props = baseProps()
    const { rerender } = render(<ListFilterBar {...props} active={false} />)
    expect(screen.queryByRole('button', { name: /zurücksetzen/i })).not.toBeInTheDocument()
    rerender(<ListFilterBar {...props} active />)
    fireEvent.click(screen.getByRole('button', { name: /zurücksetzen/i }))
    expect(props.onReset).toHaveBeenCalled()
  })
})


// --- Filter-Standard F0 (E1–E9) --------------------------------------------

const CASE_CHIPS: StatusChipOption[] = [
  { value: 'all', label: 'Alle', count: 4 },
  { value: 'open', label: 'Offen', count: 0, token: 'draft', keepWhenZero: true },
  { value: 'triaged', label: 'Eingeordnet', count: 3, token: 'review' },
  { value: 'addressed', label: 'Umgesetzt', count: 1, token: 'active' },
  { value: 'dismissed', label: 'Verworfen', count: 0, token: 'inactive' },
]

function targetFacet(overrides: Partial<FacetSpec> = {}): FacetSpec {
  return {
    key: 'target',
    label: 'Zugeordnet zu',
    allLabel: 'Alle Bausteine',
    options: [
      { value: 'playbook', label: 'Playbook', count: 2, hint: 'Ablauf-Baustein.' },
      { value: 'resource', label: 'Resource', count: 0 },
    ],
    value: '',
    onChange: vi.fn(),
    ...overrides,
  }
}

describe('ListFilterBar — generische Status-Chips (E1)', () => {
  it('rendert statusOptions mit Zahl, blendet 0er aus ausser Standard/gewaehlt', () => {
    const onStatusChange = vi.fn()
    render(
      <ListFilterBar
        idPrefix="cases"
        statusOptions={CASE_CHIPS}
        status="all"
        onStatusChange={onStatusChange}
        active={false}
        onReset={vi.fn()}
      />,
    )
    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    // „Offen“ bleibt trotz 0 (keepWhenZero), „Verworfen“ entfaellt.
    expect(within(group).getByRole('button', { name: 'Offen 0' })).toBeInTheDocument()
    expect(within(group).queryByRole('button', { name: /Verworfen/ })).not.toBeInTheDocument()
    expect(within(group).getByRole('button', { name: 'Alle 4' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    fireEvent.click(within(group).getByRole('button', { name: 'Eingeordnet 3' }))
    expect(onStatusChange).toHaveBeenCalledWith('triaged')
  })

  it('zeigt Chips ohne Zahl bei count null und den Hinweis countsUnavailable', () => {
    render(
      <ListFilterBar
        idPrefix="cases"
        statusOptions={CASE_CHIPS.map((chip) => ({ ...chip, count: null }))}
        status="dismissed"
        onStatusChange={vi.fn()}
        countsUnavailable
        active={false}
        onReset={vi.fn()}
      />,
    )
    // Ohne Zahl entfaellt kein Chip — die Regel greift nur bei echter 0.
    expect(screen.getByRole('button', { name: 'Verworfen' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Zahlen gerade nicht verfügbar.')).toBeInTheDocument()
  })

  it('rendert ohne counts und statusOptions keine Chip-Zeile und ohne onQueryChange keine Suche (E2)', () => {
    render(
      <ListFilterBar
        idPrefix="patterns"
        agents={[{ id: 'a1', name: 'Support-Bot' }]}
        agent=""
        onAgentChange={vi.fn()}
        active={false}
        onReset={vi.fn()}
      />,
    )
    expect(screen.queryByRole('group', { name: 'Nach Status filtern' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Suche')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Agent')).toBeInTheDocument()
  })

  it('nimmt searchPlaceholder der Seite', () => {
    render(
      <ListFilterBar
        {...baseProps()}
        searchPlaceholder="In 12 Einträgen suchen…"
      />,
    )
    expect(screen.getByLabelText('Suche')).toHaveAttribute('placeholder', 'In 12 Einträgen suchen…')
  })

  it('hebt die Chips unter md auf 40 px (E9)', () => {
    render(<ListFilterBar {...baseProps()} />)
    expect(screen.getByRole('button', { name: /^Alle/ })).toHaveClass('min-h-10', 'md:min-h-0')
  })
})

describe('ListFilterBar — generische Facetten (E3) und aktive Filter (E4)', () => {
  it('ordnet Agent → Typ → generische → Tag → Sprache', () => {
    render(
      <ListFilterBar
        {...baseProps()}
        availableTags={['a']}
        tag=""
        onTagChange={vi.fn()}
        availableTypes={['workflow']}
        type=""
        onTypeChange={vi.fn()}
        agents={[{ id: 'a1', name: 'Support-Bot' }]}
        agent=""
        onAgentChange={vi.fn()}
        locales={[{ value: 'de-DE', label: 'Deutsch' }]}
        locale=""
        onLocaleChange={vi.fn()}
        facets={[targetFacet()]}
      />,
    )
    const labels = screen.getAllByRole('combobox').map((select) => select.id)
    expect(labels).toEqual([
      'test-agent',
      'test-type',
      'test-target',
      'test-tag',
      'test-locale',
    ])
  })

  it('zeigt Zahlen an Facettenwerten, laesst 0 waehlbar und meldet Auswahl', () => {
    const facet = targetFacet()
    render(<ListFilterBar {...baseProps()} facets={[facet]} />)
    expect(screen.getByRole('option', { name: 'Alle Bausteine' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Playbook (2)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Resource (0)' })).not.toBeDisabled()
    fireEvent.change(screen.getByLabelText('Zugeordnet zu'), { target: { value: 'resource' } })
    expect(facet.onChange).toHaveBeenCalledWith('resource')
  })

  it('haengt den Hinweis des gewaehlten Werts per aria-describedby an', () => {
    render(<ListFilterBar {...baseProps()} facets={[targetFacet({ value: 'playbook' })]} />)
    expect(screen.getByLabelText('Zugeordnet zu')).toHaveAccessibleDescription('Ablauf-Baustein.')
  })

  it('zeigt jede gesetzte Facette als Chip in einer Liste, mit Zuruecksetzen am Ende', () => {
    const onTagChange = vi.fn()
    const facet = targetFacet({ value: 'playbook' })
    render(
      <ListFilterBar
        {...baseProps()}
        active
        availableTags={['intern']}
        tag="intern"
        onTagChange={onTagChange}
        availableTypes={['workflow']}
        type="workflow"
        onTypeChange={vi.fn()}
        typeLabel={() => 'Ablauf'}
        agents={[{ id: 'a1', name: 'Support-Bot' }]}
        agent="a1"
        onAgentChange={vi.fn()}
        facets={[facet]}
      />,
    )
    const list = screen.getByRole('list', { name: 'Aktive Filter' })
    const chips = within(list).getAllByRole('button')
    expect(chips.map((chip) => chip.textContent)).toEqual([
      'Agent: Support-Bot',
      'Typ: Ablauf',
      'Zugeordnet zu: Playbook',
      'Tag: intern',
    ])
    expect(
      within(list).getByRole('button', { name: 'Filter „Zugeordnet zu: Playbook“ entfernen' }),
    ).toBeInTheDocument()
    fireEvent.click(within(list).getByRole('button', { name: 'Filter „Tag: intern“ entfernen' }))
    expect(onTagChange).toHaveBeenCalledWith('')
    // Zuruecksetzen steht hinter der Liste, nicht darin.
    expect(within(list).queryByRole('button', { name: /zurücksetzen/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Filter zurücksetzen' })).toBeInTheDocument()
  })

  it('setzt nach dem Entfernen den Fokus auf den naechsten Chip, sonst Zuruecksetzen, sonst Suche', async () => {
    function Harness() {
      const [agent, setAgent] = useState('a1')
      const [tag, setTag] = useState('intern')
      const active = agent !== '' || tag !== ''
      return (
        <ListFilterBar
          {...baseProps()}
          active={active}
          agents={[{ id: 'a1', name: 'Support-Bot' }]}
          agent={agent}
          onAgentChange={setAgent}
          availableTags={['intern']}
          tag={tag}
          onTagChange={setTag}
        />
      )
    }
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: /Agent-Filter entfernen/ }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Filter „Tag: intern“ entfernen' })).toHaveFocus(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Filter „Tag: intern“ entfernen' }))
    // Nichts mehr aktiv → kein Zuruecksetzen → Suche.
    await waitFor(() => expect(screen.getByLabelText('Suche')).toHaveFocus())
  })

  it('faellt beim Entfernen des letzten Chips auf Zuruecksetzen, solange etwas aktiv bleibt', async () => {
    function Harness() {
      const [tag, setTag] = useState('intern')
      return (
        <ListFilterBar
          {...baseProps()}
          query="foo"
          active
          availableTags={['intern']}
          tag={tag}
          onTagChange={setTag}
        />
      )
    }
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'Filter „Tag: intern“ entfernen' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Filter zurücksetzen' })).toHaveFocus(),
    )
  })

  it('rendert Sortierung vor Gruppieren, ohne Chip und ohne Zaehlung (E5)', () => {
    render(
      <ListFilterBar
        {...baseProps()}
        sortOptions={[
          { value: '', label: 'Neueste zuerst' },
          { value: 'oldest', label: 'Älteste zuerst' },
        ]}
        sort="oldest"
        onSortChange={vi.fn()}
        groupOptions={[{ value: '', label: 'Keine Gruppierung' }]}
        group=""
        onGroupChange={vi.fn()}
      />,
    )
    const ids = screen.getAllByRole('combobox').map((select) => select.id)
    expect(ids).toEqual(['test-sort', 'test-group'])
    expect(screen.queryByRole('list', { name: 'Aktive Filter' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Filter' })).toBeInTheDocument()
  })

  it('rendert mit bare ohne Card (E8)', () => {
    const { container } = render(<ListFilterBar {...baseProps()} bare />)
    expect(container.querySelector('.rounded-xl, [class*="shadow"]')).toBeNull()
    expect(screen.getByLabelText('Suche')).toBeInTheDocument()
  })
})

// Unter `md` (E6): ab zwei Facetten oder mit Anzeige-Option liegen die Selects
// im Sheet. jsdom kennt keine Breakpoints — `useIsMobile` ist hier gemockt;
// ohne Mock (false) sieht der Test das Raster (`hidden md:contents`).
describe('ListFilterBar — Mobil-Sheet (E6)', () => {
  function withFacets(overrides: Record<string, unknown> = {}) {
    return {
      ...baseProps(),
      availableTags: ['a', 'b'],
      tag: '',
      onTagChange: vi.fn(),
      agents: [{ id: 'a1', name: 'Support-Bot' }],
      agent: '',
      onAgentChange: vi.fn(),
      locales: [{ value: 'de-DE', label: 'Deutsch' }],
      locale: '',
      onLocaleChange: vi.fn(),
      ...overrides,
    }
  }

  it('haelt ab md das Raster: Knopf md:hidden, Facetten hidden md:contents', () => {
    render(<ListFilterBar {...withFacets()} />)
    expect(screen.getByRole('button', { name: 'Filter' })).toHaveClass('md:hidden')
    const facets = screen.getByTestId('list-filter-facets')
    expect(facets).toHaveClass('hidden', 'md:contents')
    expect(facets).toContainElement(screen.getByLabelText('Tag'))
    expect(facets).not.toContainElement(screen.getByLabelText('Suche'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('zaehlt nur gesetzte Facetten im Knopf, nie bei 0 und nie Anzeige', () => {
    const { rerender } = render(
      <ListFilterBar
        {...withFacets({
          sortOptions: [{ value: '', label: 'Neueste zuerst' }],
          sort: '',
          onSortChange: vi.fn(),
        })}
      />,
    )
    expect(screen.getByRole('button', { name: 'Filter' })).toBeInTheDocument()
    rerender(
      <ListFilterBar
        {...withFacets({
          tag: 'a',
          locale: 'de-DE',
          groupOptions: [{ value: 'tag', label: 'Nach Tag' }],
          group: 'tag',
          onGroupChange: vi.fn(),
        })}
      />,
    )
    expect(screen.getByRole('button', { name: 'Filter (2)' })).toBeInTheDocument()
  })

  it('oeffnet unter md ein Sheet von unten mit Facetten, Anzeige und Fuss', async () => {
    viewport.mobile = true
    const props = withFacets({
      tag: 'a',
      active: true,
      resultCount: 3,
      sortOptions: [{ value: '', label: 'Neueste zuerst' }],
      sort: '',
      onSortChange: vi.fn(),
    })
    render(<ListFilterBar {...props} />)
    // Kein Inline-Raster mehr — die Selects gibt es nur im Sheet.
    expect(screen.queryByTestId('list-filter-facets')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Tag')).not.toBeInTheDocument()
    // Aktive Chips bleiben in der Karte sichtbar.
    expect(screen.getByRole('list', { name: 'Aktive Filter' })).toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: 'Filter (1)' })
    fireEvent.click(toggle)
    const dialog = await screen.findByRole('dialog', { name: 'Filter' })
    expect(dialog).toHaveAccessibleDescription('Filter wirken sofort.')
    expect(dialog).toHaveClass('max-h-[85svh]')
    const ids = within(dialog)
      .getAllByRole('combobox')
      .map((select) => select.id)
    expect(ids).toEqual(['test-sheet-agent', 'test-sheet-tag', 'test-sheet-locale', 'test-sheet-sort'])

    // Wert wirkt sofort.
    fireEvent.change(within(dialog).getByLabelText('Sprache'), { target: { value: 'de-DE' } })
    expect(props.onLocaleChange).toHaveBeenCalledWith('de-DE')

    const show = within(dialog).getByRole('button', { name: '3 Treffer zeigen' })
    expect(show).toHaveClass('min-h-11')
    fireEvent.click(show)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(toggle).toHaveFocus()
  })

  it('setzt im Sheet zurueck und schliesst; ohne Trefferzahl heisst der Fuss „Fertig“', async () => {
    viewport.mobile = true
    const props = withFacets({ active: true })
    render(<ListFilterBar {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('button', { name: 'Fertig' })).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Filter zurücksetzen' }))
    expect(props.onReset).toHaveBeenCalled()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('schliesst per Escape', async () => {
    viewport.mobile = true
    render(<ListFilterBar {...withFacets()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
    const dialog = await screen.findByRole('dialog')
    act(() => {
      fireEvent.keyDown(dialog, { key: 'Escape' })
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('laesst bei genau einer Facette ohne Anzeige das Select inline, ohne Knopf', () => {
    viewport.mobile = true
    render(
      <ListFilterBar
        idPrefix="patterns"
        agents={[{ id: 'a1', name: 'Support-Bot' }]}
        agent=""
        onAgentChange={vi.fn()}
        active={false}
        onReset={vi.fn()}
      />,
    )
    expect(screen.queryByTestId('list-filter-facets-toggle')).not.toBeInTheDocument()
    expect(screen.getByTestId('list-filter-facets')).toHaveClass('contents')
    expect(screen.getByTestId('list-filter-facets')).not.toHaveClass('hidden')
    expect(screen.getByLabelText('Agent')).toBeInTheDocument()
  })

  it('rendert keinen Filter-Knopf ohne Zusatz-Facetten', () => {
    render(<ListFilterBar {...baseProps()} />)
    expect(screen.queryByTestId('list-filter-facets-toggle')).not.toBeInTheDocument()
  })
})

describe('ListFilterBar — a11y', () => {
  it('a11y: Leiste mit Chips, Facetten und aktiven Filtern ohne axe-Violations', async () => {
    const { container } = render(
      <ListFilterBar
        idPrefix="cases"
        statusOptions={CASE_CHIPS}
        status="open"
        onStatusChange={vi.fn()}
        active
        onReset={vi.fn()}
        agents={[{ id: 'a1', name: 'Support-Bot' }]}
        agent="a1"
        onAgentChange={vi.fn()}
        facets={[targetFacet({ value: 'playbook' })]}
        countsUnavailable
      />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: offenes Sheet ohne axe-Violations', async () => {
    viewport.mobile = true
    render(
      <ListFilterBar
        {...baseProps()}
        active
        agents={[{ id: 'a1', name: 'Support-Bot' }]}
        agent="a1"
        onAgentChange={vi.fn()}
        facets={[targetFacet({ value: 'playbook' })]}
        resultCount={1}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Filter (2)' }))
    await screen.findByRole('dialog')
    expect(await axe(document.body)).toHaveNoViolations()
  })
})
