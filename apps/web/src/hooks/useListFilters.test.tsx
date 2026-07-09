import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { useAgentFilterParam, useListFilters, type ListFilterAccessors } from './useListFilters'

interface Item {
  name: string
  status: 'draft' | 'review' | 'active' | 'inactive' | undefined
  pending?: boolean
  tags?: string[]
  type?: string
}

const items: Item[] = [
  { name: 'Alpha', status: 'draft', tags: ['x'], type: 'workflow' },
  { name: 'Beta', status: 'review', tags: ['y'], type: 'prompt' },
  { name: 'Gamma', status: 'active', pending: true, tags: ['x', 'y'], type: 'workflow' },
  { name: 'Delta', status: 'active', tags: [], type: 'prompt' },
  { name: 'Epsilon', status: 'inactive', tags: ['z'], type: 'snippet' },
  { name: 'Zeta', status: undefined },
]

const accessors: ListFilterAccessors<Item> = {
  name: (i) => i.name,
  status: (i) => i.status,
  hasPendingDraft: (i) => i.pending,
  tags: (i) => i.tags ?? [],
  type: (i) => i.type,
}

function wrapperFor(initialEntries: string[]) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
  }
}

function renderFilters(initialEntries: string[] = ['/']) {
  return renderHook(() => useListFilters(items, accessors), { wrapper: wrapperFor(initialEntries) })
}

describe('useListFilters', () => {
  it('startet ohne Filter: alle sichtbar, Status all', () => {
    const { result } = renderFilters()
    expect(result.current.status).toBe('all')
    expect(result.current.filtered).toHaveLength(6)
    expect(result.current.active).toBe(false)
  })

  it('rechnet faceted counts inkl. attention', () => {
    const { result } = renderFilters()
    // attention = draft + review + active-mit-pending
    expect(result.current.counts.all).toBe(6)
    expect(result.current.counts.attention).toBe(3)
    expect(result.current.counts.draft).toBe(1)
    expect(result.current.counts.active).toBe(2)
    expect(result.current.counts.inactive).toBe(1)
  })

  it('liest den Status aus der URL und faellt bei Unsinn auf all zurueck', () => {
    expect(renderFilters(['/?status=review']).result.current.status).toBe('review')
    expect(renderFilters(['/?status=bogus']).result.current.status).toBe('all')
  })

  it('filtert per Status attention', () => {
    const { result } = renderFilters()
    act(() => result.current.setStatus('attention'))
    expect(result.current.filtered.map((i) => i.name).sort()).toEqual(['Alpha', 'Beta', 'Gamma'])
    expect(result.current.active).toBe(true)
  })

  it('setStatus all entfernt den Param wieder', () => {
    const { result } = renderFilters(['/?status=draft'])
    expect(result.current.filtered).toHaveLength(1)
    act(() => result.current.setStatus('all'))
    expect(result.current.status).toBe('all')
    expect(result.current.filtered).toHaveLength(6)
  })

  it('filtert per Freitext ueber den Namen', () => {
    const { result } = renderFilters()
    act(() => result.current.setQuery('ta'))
    expect(result.current.filtered.map((i) => i.name).sort()).toEqual(['Beta', 'Delta', 'Zeta'])
  })

  it('filtert per Tag und leitet availableTags sortiert ab', () => {
    const { result } = renderFilters()
    expect(result.current.availableTags).toEqual(['x', 'y', 'z'])
    act(() => result.current.setTag('x'))
    expect(result.current.filtered.map((i) => i.name).sort()).toEqual(['Alpha', 'Gamma'])
  })

  it('filtert per Typ und leitet availableTypes ab', () => {
    const { result } = renderFilters()
    expect(result.current.availableTypes).toEqual(['prompt', 'snippet', 'workflow'])
    act(() => result.current.setType('prompt'))
    expect(result.current.filtered.map((i) => i.name).sort()).toEqual(['Beta', 'Delta'])
  })

  it('kombiniert Facetten und passt die counts an die Basismenge an', () => {
    const { result } = renderFilters()
    act(() => result.current.setType('workflow'))
    // Basismenge: Alpha (draft), Gamma (active+pending) → attention beide
    expect(result.current.counts.all).toBe(2)
    expect(result.current.counts.attention).toBe(2)
    act(() => result.current.setStatus('draft'))
    expect(result.current.filtered.map((i) => i.name)).toEqual(['Alpha'])
  })

  it('reset raeumt alle Filter ab', () => {
    const { result } = renderFilters(['/?status=review&q=be&tag=y&type=prompt&agent=a1'])
    expect(result.current.active).toBe(true)
    act(() => result.current.reset())
    expect(result.current.status).toBe('all')
    expect(result.current.query).toBe('')
    expect(result.current.tag).toBe('')
    expect(result.current.type).toBe('')
    expect(result.current.agent).toBe('')
    expect(result.current.active).toBe(false)
  })

  it('liest die Agent-Facette aus der URL, ohne clientseitig zu filtern', () => {
    const { result } = renderFilters(['/?agent=a1'])
    expect(result.current.agent).toBe('a1')
    expect(result.current.active).toBe(true)
    // Serverseitige Facette: items kommen bereits gefiltert an — der Hook
    // grenzt die Liste NICHT zusaetzlich ein.
    expect(result.current.filtered).toHaveLength(6)
  })

  it('setAgent schreibt und entfernt den URL-Param', () => {
    const { result } = renderFilters()
    act(() => result.current.setAgent('a1'))
    expect(result.current.agent).toBe('a1')
    act(() => result.current.setAgent(''))
    expect(result.current.agent).toBe('')
    expect(result.current.active).toBe(false)
  })

  it('useAgentFilterParam liest denselben ?agent=-Wert', () => {
    const { result } = renderHook(() => useAgentFilterParam(), {
      wrapper: wrapperFor(['/?agent=a9']),
    })
    expect(result.current).toBe('a9')
    const empty = renderHook(() => useAgentFilterParam(), { wrapper: wrapperFor(['/']) })
    expect(empty.result.current).toBe('')
  })

  it('ohne tags/type-Accessoren bleiben die Facetten leer', () => {
    const minimal: ListFilterAccessors<Item> = {
      name: (i) => i.name,
      status: (i) => i.status,
      hasPendingDraft: (i) => i.pending,
    }
    const { result } = renderHook(() => useListFilters(items, minimal), {
      wrapper: wrapperFor(['/']),
    })
    expect(result.current.availableTags).toEqual([])
    expect(result.current.availableTypes).toEqual([])
  })
})
