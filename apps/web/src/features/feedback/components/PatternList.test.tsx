import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Agent, PatternListRead, PatternRead } from '@/api/types'
import { notify } from '@/lib/feedback'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { PatternList } from './PatternList'

const {
  listPatterns,
  listAgents,
  countCases,
  countMemories,
  getMemory,
  getCase,
  getPlaybook,
  copyToClipboard,
} = vi.hoisted(() => ({
  listPatterns: vi.fn(),
  listAgents: vi.fn(),
  countCases: vi.fn(),
  countMemories: vi.fn(),
  getMemory: vi.fn(),
  getCase: vi.fn(),
  getPlaybook: vi.fn(),
  copyToClipboard: vi.fn(),
}))

// Stabile API-Referenz (wie der echte `useMemo`-basierte `useApi`).
vi.mock('@/api/useApi', () => {
  const api = {
    listPatterns,
    listAgents,
    countCases,
    countMemories,
    getMemory,
    getCase,
    getPlaybook,
  }
  return { useApi: () => api }
})

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/lib/clipboard', () => ({ copyToClipboard }))

const agents = [
  { id: 'a1', name: 'coder' },
  { id: 'a2', name: 'researcher' },
] as Agent[]

const LESSON: PatternRead = {
  source: 'lesson',
  agent_id: 'a1',
  element: null,
  count: 4,
  evidence_ids: ['m1'],
  first_seen: '2026-10-01T10:00:00Z',
  last_seen: '2026-10-05T10:00:00Z',
}

const CASES: PatternRead = {
  source: 'case',
  agent_id: 'a2',
  element: { target: 'playbook', entity_id: 'pb1' },
  count: 3,
  evidence_ids: ['c1', 'c2', 'c3'],
  first_seen: '2026-10-02T10:00:00Z',
  last_seen: '2026-10-06T10:00:00Z',
}

function list(patterns: PatternRead[], threshold = 3): PatternListRead {
  return { threshold, window_days: 30, patterns }
}

function SearchProbe() {
  return <output data-testid="search">{useLocation().search}</output>
}

const currentSearch = () => screen.getByTestId('search').textContent

// Nur die Muster-Zeilen, nicht die Listen der Filterleiste.
const rowsOf = async () => within(await screen.findByTestId('pattern-list')).getAllByRole('listitem')

function renderList(search = '') {
  return renderInRoutes(
    <>
      <PatternList />
      <SearchProbe />
    </>,
    { path: '/w/:workspaceId/feedback', initialEntries: [`/w/ws-1/feedback${search}`] },
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  listAgents.mockResolvedValue(agents)
  listPatterns.mockResolvedValue(list([LESSON, CASES]))
  countCases.mockResolvedValue({
    open: 0,
    reopened: 0,
    triaged: 0,
    in_progress: 0,
    addressed: 0,
    verified: 0,
    dismissed: 0,
  })
  countMemories.mockResolvedValue({ total: 0 })
  getPlaybook.mockResolvedValue({ id: 'pb1', name: 'Code-Task-Flow' })
  getMemory.mockResolvedValue({
    id: 'm1',
    fact: 'Vor dem Push lokal testen.',
    status: 'pending',
    created_at: '2026-10-05T10:00:00Z',
  })
  getCase.mockImplementation((id: string) =>
    Promise.resolve({
      case: { id, expected_behavior: `Erwartet ${id}`, created_at: '2026-10-03T10:00:00Z' },
    }),
  )
  copyToClipboard.mockResolvedValue(undefined)
})

describe('PatternList — Liste', () => {
  it('zeigt Fall-Muster vor Lernvorschlag-Mustern mit Zaehlung, ohne Status', async () => {
    renderList()

    const rows = await rowsOf()
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText('Ähnliche Fälle 3×')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Dieselbe Korrektur 4×')).toBeInTheDocument()
    expect(
      await within(rows[0]).findByText(
        '3 offene Fälle zu researcher, alle zugeordnet zu Playbook: Code-Task-Flow, in 30 Tagen.',
      ),
    ).toBeInTheDocument()
    expect(
      within(rows[1]).getByText('Ein Lernvorschlag von coder kam 4-mal mit ähnlichem Wortlaut.'),
    ).toBeInTheDocument()
    // Schwelle aus der Antwort, nicht fest kodiert (Q8).
    expect(screen.getByText(/ab 3 Treffern erscheint hier ein Muster/)).toBeInTheDocument()
    // Kein Zustand: weder Status noch Verwerfen.
    expect(screen.queryByRole('button', { name: /Verwerfen/ })).not.toBeInTheDocument()
  })

  it('nimmt eine andere Schwelle aus der Antwort', async () => {
    listPatterns.mockResolvedValue(list([LESSON], 5))
    renderList()
    expect(await screen.findByText(/ab 5 Treffern erscheint hier ein Muster/)).toBeInTheDocument()
  })

  it('filtert nach Agent ueber `?agent=` und den Server-Parameter', async () => {
    renderList()
    await rowsOf()
    expect(listPatterns).toHaveBeenLastCalledWith(undefined)

    fireEvent.change(screen.getByRole('combobox', { name: /Agent/ }), { target: { value: 'a1' } })
    await waitFor(() => expect(currentSearch()).toBe('?agent=a1'))
    await waitFor(() => expect(listPatterns).toHaveBeenLastCalledWith('a1'))
  })

  it('zeigt bei leerem Filter-Ergebnis „Keine Treffer“ mit Zuruecksetzen', async () => {
    listPatterns.mockResolvedValue(list([]))
    renderList('?agent=a2')

    expect(await screen.findByText('Keine Treffer')).toBeInTheDocument()
    // Filterleiste und Leer-Zustand bieten beide „Zuruecksetzen“.
    fireEvent.click(screen.getAllByRole('button', { name: 'Filter zurücksetzen' }).at(-1)!)
    await waitFor(() => expect(currentSearch()).toBe(''))
  })

  it('zeigt ohne Muster den Leer-Zustand mit Schwelle, wenn es Material gibt', async () => {
    listPatterns.mockResolvedValue(list([]))
    countMemories.mockResolvedValue({ total: 2 })
    renderList()

    expect(await screen.findByText('Noch keine Muster')).toBeInTheDocument()
    expect(screen.getByText(/Ab 3 Treffern erscheint ein Muster/)).toBeInTheDocument()
    // Filter erst, wenn es etwas zu filtern gibt.
    expect(screen.queryByRole('combobox', { name: /Agent/ })).not.toBeInTheDocument()
  })

  it('zeigt ohne jedes Material den Hinweis und „Fall melden“', async () => {
    listPatterns.mockResolvedValue(list([]))
    renderList()

    expect(
      await screen.findByText('Muster brauchen Lernvorschläge oder Fälle. Es gibt noch keine.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fall melden' })).toBeInTheDocument()
    expect(countMemories).toHaveBeenCalledWith({ kind: 'lesson' })
  })

  it('zeigt einen Ladefehler mit „Erneut versuchen“', async () => {
    listPatterns.mockRejectedValueOnce(new Error('kaputt'))
    renderList()

    expect(await screen.findByText('Muster konnten nicht berechnet werden.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    expect(await rowsOf()).toHaveLength(2)
  })
})

describe('PatternList — Sheet', () => {
  it('oeffnet das Sheet per Klick, schreibt `?pattern=` und listet Belege', async () => {
    renderList()
    const rows = await rowsOf()
    fireEvent.click(within(rows[0]).getByRole('link'))

    const sheet = await screen.findByTestId('pattern-sheet')
    expect(currentSearch()).toBe('?pattern=case.a2.playbook.pb1')
    expect(within(sheet).getByRole('heading', { name: 'Ähnliche Fälle 3×' })).toBeInTheDocument()
    expect(within(sheet).getByText('Warum ist das ein Muster?')).toBeInTheDocument()

    const evidence = within(sheet).getByTestId('pattern-evidence')
    const link = await within(evidence).findByRole('link', { name: 'Erwartet c1' })
    expect(link).toHaveAttribute('href', '/w/ws-1/feedback/cases/c1')

    // Fall-Muster: „Fälle ansehen“ mit Agent und Zuordnung als Filter.
    expect(within(sheet).getByRole('link', { name: /Fälle ansehen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback?tab=cases&agent=a2&target=playbook',
    )
  })

  it('kopiert einen Builder-Text nur mit IDs, nie mit Inhalt', async () => {
    renderList('?pattern=case.a2.playbook.pb1')
    const sheet = await screen.findByTestId('pattern-sheet')

    const builder = within(sheet).getByTestId('pattern-builder')
    const text = within(builder).getByRole<HTMLTextAreaElement>('textbox').value
    expect(text).toContain('c1, c2, c3')
    expect(text).toContain('pb1')
    expect(text).not.toContain('Erwartet')

    fireEvent.click(within(builder).getByRole('button', { name: 'Kopieren' }))
    await waitFor(() => expect(copyToClipboard).toHaveBeenCalledWith(text))
  })

  it('bietet bei Lernvorschlag-Mustern „Fall anlegen“ und verlinkt den Beleg ins Gedaechtnis', async () => {
    renderList('?pattern=lesson.a1.m1')
    const sheet = await screen.findByTestId('pattern-sheet')

    const link = await within(sheet).findByRole('link', { name: 'Vor dem Push lokal testen.' })
    expect(link).toHaveAttribute('href', '/w/ws-1/memory?entry=m1')
    await waitFor(() =>
      expect(within(sheet).getByRole('button', { name: 'Fall anlegen' })).toBeEnabled(),
    )
  })

  it('markiert geloeschte Belege', async () => {
    getMemory.mockRejectedValue(new ApiError(404, 'weg'))
    renderList('?pattern=lesson.a1.m1')
    const sheet = await screen.findByTestId('pattern-sheet')
    expect(await within(sheet).findByText('Gelöschter Eintrag')).toBeInTheDocument()
  })

  it('zeigt zuerst 20 Belege, dann „Alle n Belege anzeigen“', async () => {
    const ids = Array.from({ length: 25 }, (_, index) => `c${String(index).padStart(2, '0')}`)
    listPatterns.mockResolvedValue(list([{ ...CASES, count: 25, evidence_ids: ids }]))
    renderList('?pattern=case.a2.playbook.pb1')
    const sheet = await screen.findByTestId('pattern-sheet')

    const evidence = within(sheet).getByTestId('pattern-evidence')
    expect(within(evidence).getAllByRole('listitem')).toHaveLength(20)
    fireEvent.click(within(sheet).getByRole('button', { name: 'Alle 25 Belege anzeigen' }))
    expect(within(evidence).getAllByRole('listitem')).toHaveLength(25)
  })

  it('meldet ein verschwundenes Muster und schliesst das Sheet', async () => {
    renderList('?pattern=lesson.a1.gibts-nicht')

    await waitFor(() => expect(notify.info).toHaveBeenCalledWith('Dieses Muster gilt nicht mehr.'))
    await waitFor(() => expect(currentSearch()).toBe(''))
    expect(screen.queryByTestId('pattern-sheet')).not.toBeInTheDocument()
  })

  it('hat im offenen Sheet keine axe-Verstoesse', async () => {
    renderList('?pattern=case.a2.playbook.pb1')
    const sheet = await screen.findByTestId('pattern-sheet')
    await within(sheet).findByRole('link', { name: 'Erwartet c1' })
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)
})

// Tab „Muster“: eigener axe-Lauf fuer die Liste (PM 2026-10-09: das
// a11y-`it()` steht hier, nicht in `FeedbackOverviewPage.a11y.test.tsx`).
// 15 s wie das a11y-Projekt (`vite.config.ts`), axe in jsdom ist CPU-gebunden.
describe('PatternList (a11y)', () => {
  it('hat in der Liste keine axe-Verstoesse', async () => {
    const { container } = renderList()
    await within(await screen.findByTestId('pattern-list')).findByText(/Code-Task-Flow/)
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)
})
