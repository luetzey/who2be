import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { StatusCounts } from '@/lib/listFilter'

import { ListFilterBar } from './ListFilterBar'

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

  it('zeigt den Reset-Button nur bei aktiven Filtern', () => {
    const props = baseProps()
    const { rerender } = render(<ListFilterBar {...props} active={false} />)
    expect(screen.queryByRole('button', { name: /zurücksetzen/i })).not.toBeInTheDocument()
    rerender(<ListFilterBar {...props} active />)
    fireEvent.click(screen.getByRole('button', { name: /zurücksetzen/i }))
    expect(props.onReset).toHaveBeenCalled()
  })
})
