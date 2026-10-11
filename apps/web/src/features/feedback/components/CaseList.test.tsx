import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Agent, CaseCounts, CaseRead, WorkspaceRole } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { CaseList } from './CaseList'

const { listCases, countCases, listAgents } = vi.hoisted(() => ({
  listCases: vi.fn(),
  countCases: vi.fn(),
  listAgents: vi.fn(),
}))

// Stabile API-Referenz (wie der echte `useMemo`-basierte `useApi`).
vi.mock('@/api/useApi', () => {
  const api = { listCases, countCases, listAgents }
  return { useApi: () => api }
})

let role: WorkspaceRole | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const agents = [
  { id: 'a1', name: 'coder' },
  { id: 'a2', name: 'researcher' },
] as Agent[]

function caseRead(overrides: Partial<CaseRead> = {}): CaseRead {
  return {
    id: 'case-1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    reporter_kind: 'human',
    reporter_user_id: 'u1',
    reporter_agent_id: null,
    situation: 'Fix für #512 gepusht, CI rot.',
    behavior: 'Direkt gepusht.',
    impact: null,
    expected_behavior: 'Tests vor dem Push lokal laufen lassen.',
    severity: 'medium',
    signal: 'incorrect',
    source_ref: null,
    source_feedback_id: null,
    source_memory_id: null,
    status: 'open',
    created_at: '2026-10-08T10:00:00Z',
    ...overrides,
  }
}

function counts(overrides: Partial<CaseCounts> = {}): CaseCounts {
  return {
    open: 2,
    reopened: 1,
    triaged: 4,
    in_progress: 0,
    addressed: 5,
    verified: 0,
    dismissed: 0,
    ...overrides,
  }
}

function SearchProbe() {
  return <output data-testid="search">{useLocation().search}</output>
}

const currentSearch = () => screen.getByTestId('search').textContent

function renderList(viewer: boolean, search = '') {
  role = viewer ? 'viewer' : 'editor'
  return renderInRoutes(
    <>
      <CaseList viewer={viewer} />
      <SearchProbe />
    </>,
    { path: '/w/:workspaceId/feedback', initialEntries: [`/w/ws-1/feedback${search}`] },
  )
}

beforeEach(() => {
  listCases.mockReset()
  countCases.mockReset()
  listAgents.mockReset()
  listAgents.mockResolvedValue(agents)
  countCases.mockResolvedValue(counts())
  listCases.mockResolvedValue({ items: [caseRead()], next_cursor: null })
})

describe('CaseList', () => {
  it('filtert standardmaessig auf „Offen“ und sendet dafuer open und reopened', async () => {
    renderList(false)

    await screen.findByRole('link', { name: 'coder' })
    expect(listCases).toHaveBeenCalledWith({
      agent_id: undefined,
      status: ['open', 'reopened'],
      target: undefined,
    })
    // Zaehler „Offen“ = open + reopened; „Alle“ = Summe aller Status.
    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    expect(within(group).getByRole('button', { name: /^Offen 3$/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(within(group).getByRole('button', { name: /^Alle 12$/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    // Chips mit 0 entfallen (Verworfen), der Standard bleibt.
    expect(within(group).queryByRole('button', { name: /Verworfen/ })).not.toBeInTheDocument()
  })

  it('zeigt Erwartet, Lage, Quelle, Datum, Art und verlinkt auf das Fall-Detail', async () => {
    listCases.mockResolvedValue({
      items: [caseRead({ severity: 'high' })],
      next_cursor: null,
    })
    renderList(false)

    const link = await screen.findByRole('link', { name: 'coder' })
    expect(link).toHaveAttribute('href', '/w/ws-1/feedback/cases/case-1')
    expect(
      screen.getByText('Erwartet: Tests vor dem Push lokal laufen lassen.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Lage: Fix für #512 gepusht, CI rot.')).toBeInTheDocument()
    expect(screen.getByText('Falsch')).toBeInTheDocument()
    expect(screen.getByText('Blockiert')).toBeInTheDocument()
    // Status-Pill der Zeile (der Chip „Offen 3“ heisst ebenfalls „Offen“).
    const row = link.closest('li') ?? document.body
    expect(within(row as HTMLElement).getByText('Offen')).toBeInTheDocument()
  })

  it('zeigt „Blockiert“ nur bei hoher Schwere, Muster und Selbstmeldung in der Meta-Zeile', async () => {
    listCases.mockResolvedValue({
      items: [
        caseRead({ id: 'c1', reporter_kind: 'pattern', reporter_user_id: null }),
        caseRead({
          id: 'c2',
          agent_id: 'a2',
          reporter_kind: 'agent',
          reporter_user_id: null,
          reporter_agent_id: 'a2',
          status: 'reopened',
        }),
      ],
      next_cursor: null,
    })
    renderList(false)

    await screen.findByRole('link', { name: 'researcher' })
    expect(screen.queryByText('Blockiert')).not.toBeInTheDocument()
    expect(screen.getByText(/aus Muster/)).toBeInTheDocument()
    expect(screen.getByText(/researcher \(selbst gemeldet\)/)).toBeInTheDocument()
    expect(screen.getByText('Wieder offen')).toBeInTheDocument()
  })

  it('laedt mit „Weitere laden“ die naechste Seite ueber den Cursor', async () => {
    listCases
      .mockResolvedValueOnce({ items: [caseRead()], next_cursor: 'cur-1' })
      .mockResolvedValueOnce({
        items: [caseRead({ id: 'case-2', agent_id: 'a2' })],
        next_cursor: null,
      })
    renderList(false)

    fireEvent.click(await screen.findByRole('button', { name: 'Weitere laden' }))

    await screen.findByRole('link', { name: 'researcher' })
    expect(listCases).toHaveBeenLastCalledWith(
      { agent_id: undefined, status: ['open', 'reopened'], target: undefined },
      { cursor: 'cur-1' },
    )
    expect(screen.getByRole('link', { name: 'coder' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Weitere laden' })).not.toBeInTheDocument()
  })

  it('schreibt Status, Agent und Zugeordnet-zu in die URL und filtert serverseitig', async () => {
    renderList(false)
    await screen.findByRole('link', { name: 'coder' })

    fireEvent.click(screen.getByRole('button', { name: /^Eingeordnet 4$/ }))
    await waitFor(() => expect(currentSearch()).toBe('?status=triaged'))
    await waitFor(() =>
      expect(listCases).toHaveBeenLastCalledWith({
        agent_id: undefined,
        status: ['triaged'],
        target: undefined,
      }),
    )

    fireEvent.change(screen.getByLabelText('Agent'), { target: { value: 'a2' } })
    await waitFor(() => expect(countCases).toHaveBeenLastCalledWith('a2'))

    fireEvent.change(screen.getByLabelText('Zugeordnet zu'), { target: { value: 'playbook' } })
    await waitFor(() =>
      expect(listCases).toHaveBeenLastCalledWith({
        agent_id: 'a2',
        status: ['triaged'],
        target: 'playbook',
      }),
    )
    expect(currentSearch()).toContain('target=playbook')
    // `/cases/counts` kennt `target` nicht: die Chips zeigen dann keine Zahl.
    expect(screen.getByRole('button', { name: /^Eingeordnet$/ })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Filter „Zugeordnet zu: Playbook“ entfernen' }),
    ).toBeInTheDocument()
  })

  it('„Alle“ filtert ohne Status', async () => {
    renderList(false, '?status=all')
    await screen.findByRole('link', { name: 'coder' })
    expect(listCases).toHaveBeenCalledWith({
      agent_id: undefined,
      status: undefined,
      target: undefined,
    })
  })

  it('zeigt viewer keine Facette „Zugeordnet zu“ und ignoriert target aus der URL', async () => {
    renderList(true, '?target=playbook')
    await screen.findByRole('link', { name: 'coder' })

    expect(screen.queryByLabelText('Zugeordnet zu')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Agent')).toBeInTheDocument()
    expect(listCases).toHaveBeenCalledWith({
      agent_id: undefined,
      status: ['open', 'reopened'],
      target: undefined,
    })
  })

  it('zeigt waehrend des Ladens drei Skeletons', () => {
    listCases.mockReturnValue(new Promise(() => {}))
    renderList(false)
    expect(screen.getAllByTestId('case-skeleton')).toHaveLength(3)
  })

  it('zeigt einen Fehler mit „Erneut versuchen“ und laedt neu', async () => {
    listCases.mockRejectedValueOnce(new Error('Netz weg'))
    renderList(false)

    expect(await screen.findByText('Rückmeldungen konnten nicht geladen werden.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    await screen.findByRole('link', { name: 'coder' })
    expect(listCases).toHaveBeenCalledTimes(2)
  })

  it('Leerzustand editor mit Standardfilter: „Keine offenen Fälle“ ohne Zuruecksetzen', async () => {
    listCases.mockResolvedValue({ items: [], next_cursor: null })
    countCases.mockResolvedValue(counts({ open: 0, reopened: 0 }))
    renderList(false)

    expect(await screen.findByText('Keine offenen Rückmeldungen')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Filter zurücksetzen' })).not.toBeInTheDocument()
  })

  it('Leerzustand mit anderem Filter: „Keine Treffer“ und Zuruecksetzen auf „Offen“', async () => {
    listCases.mockResolvedValue({ items: [], next_cursor: null })
    renderList(false, '?status=dismissed&agent=a1')

    expect(await screen.findByText('Keine Rückmeldung passt zu diesen Filtern.')).toBeInTheDocument()
    const resets = screen.getAllByRole('button', { name: 'Filter zurücksetzen' })
    fireEvent.click(resets[resets.length - 1])
    await waitFor(() => expect(currentSearch()).toBe(''))
  })

  it('Leerzustand viewer ohne Faelle: „Du hast noch keinen Fall gemeldet“ mit „Rückmeldung geben“', async () => {
    listCases.mockResolvedValue({ items: [], next_cursor: null })
    countCases.mockResolvedValue(
      counts({ open: 0, reopened: 0, triaged: 0, addressed: 0, dismissed: 0 }),
    )
    renderList(true)

    expect(await screen.findByText('Du hast noch keine Rückmeldung gegeben')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rückmeldung geben' })).toBeInTheDocument()
    // Ohne jeden Fall entfaellt die Filterleiste (Filter-Standard §2.3).
    expect(screen.queryByRole('group', { name: 'Nach Status filtern' })).not.toBeInTheDocument()
  })

  it('zeigt einen Hinweis, wenn die Zaehler nicht ladbar sind', async () => {
    countCases.mockRejectedValue(new Error('down'))
    renderList(false)
    expect(await screen.findByText('Zahlen gerade nicht verfügbar.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Offen$/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('gibt die Filter der Liste am Zeilen-Link an das Fall-Detail weiter', async () => {
    renderList(false, '?status=triaged&agent=a1&target=playbook')

    const link = await screen.findByRole('link', { name: 'coder' })
    expect(link).toHaveAttribute(
      'href',
      '/w/ws-1/feedback/cases/case-1?status=triaged&agent=a1&target=playbook',
    )
  })

  it('Leerzustand viewer mit Faellen, aber ohne offene: eigener Satz und „Alle meine Fälle anzeigen“', async () => {
    listCases.mockResolvedValue({ items: [], next_cursor: null })
    countCases.mockResolvedValue(counts({ open: 0, reopened: 0, triaged: 1, addressed: 0 }))
    renderList(true)

    expect(
      await screen.findByText(
        'Keine deiner Rückmeldungen ist mehr offen.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/du, ein Kollege oder ein Agent/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Alle meine Rückmeldungen anzeigen' }))
    await waitFor(() => expect(currentSearch()).toBe('?status=all'))
  })

  it('laedt und rendert erst, wenn die Rolle bekannt ist', () => {
    role = null
    renderInRoutes(<CaseList viewer />, {
      path: '/w/:workspaceId/feedback',
      initialEntries: ['/w/ws-1/feedback'],
    })
    // Rolle unbekannt: kein Abruf mit viewer-Filtern, kein viewer-Leertext.
    expect(listCases).not.toHaveBeenCalled()
    expect(countCases).not.toHaveBeenCalled()
    expect(screen.getAllByTestId('case-skeleton')).toHaveLength(3)
  })
})

describe('CaseList – Status aus Phase E (E5a)', () => {
  const phaseECounts = counts({ in_progress: 3, verified: 2, dismissed: 1 })

  it('zeigt die Chips in der Spec-Reihenfolge mit Zählern für In Arbeit und Hat gewirkt', async () => {
    countCases.mockResolvedValue(phaseECounts)
    renderList(false)
    await screen.findByRole('link', { name: 'coder' })

    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    const names = within(group)
      .getAllByRole('button')
      .map((button) => button.textContent?.replace(/\s+/g, ' ').trim())
    expect(names).toEqual([
      'Alle 18',
      'Offen 3',
      'Eingeordnet 4',
      'In Arbeit 3',
      'Geändert 5',
      'Hat gewirkt 2',
      'Verworfen 1',
    ])
    // Standard bleibt „Offen“.
    expect(within(group).getByRole('button', { name: /^Offen 3$/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('filtert per Chip serverseitig auf in_progress bzw. verified', async () => {
    countCases.mockResolvedValue(phaseECounts)
    renderList(false)
    await screen.findByRole('link', { name: 'coder' })

    fireEvent.click(screen.getByRole('button', { name: /^In Arbeit 3$/ }))
    await waitFor(() => expect(currentSearch()).toBe('?status=in_progress'))
    await waitFor(() =>
      expect(listCases).toHaveBeenLastCalledWith({
        agent_id: undefined,
        status: ['in_progress'],
        target: undefined,
      }),
    )

    fireEvent.click(screen.getByRole('button', { name: /^Hat gewirkt 2$/ }))
    await waitFor(() => expect(currentSearch()).toBe('?status=verified'))
    await waitFor(() =>
      expect(listCases).toHaveBeenLastCalledWith({
        agent_id: undefined,
        status: ['verified'],
        target: undefined,
      }),
    )
  })

  it('viewer sieht die Chips In Arbeit und Hat gewirkt ebenfalls', async () => {
    countCases.mockResolvedValue(phaseECounts)
    renderList(true)
    await screen.findByRole('link', { name: 'coder' })

    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    expect(within(group).getByRole('button', { name: /^In Arbeit 3$/ })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: /^Hat gewirkt 2$/ })).toBeInTheDocument()
  })

  it('ohne Fälle in diesen Status entfallen die beiden Chips (Zahl 0)', async () => {
    renderList(false)
    await screen.findByRole('link', { name: 'coder' })
    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    expect(within(group).queryByRole('button', { name: /In Arbeit/ })).not.toBeInTheDocument()
    expect(within(group).queryByRole('button', { name: /Hat gewirkt/ })).not.toBeInTheDocument()
  })

  it('Punktformen ohne Farbe unterscheidbar: Ring, hohl, gefüllt; das Wort steht immer da', async () => {
    listCases.mockResolvedValue({
      items: [
        caseRead({ id: 'c1', status: 'triaged' }),
        caseRead({ id: 'c2', status: 'in_progress' }),
        caseRead({ id: 'c3', status: 'addressed' }),
        caseRead({ id: 'c4', status: 'verified' }),
      ],
      next_cursor: null,
    })
    renderList(false, '?status=all')
    await screen.findAllByRole('link', { name: 'coder' })

    const pills = screen.getAllByTestId('case-row-status')
    const shapes = pills.map((pill) => [
      pill.textContent,
      within(pill).getByTestId('case-status-dot').getAttribute('data-shape'),
    ])
    expect(shapes).toEqual([
      ['Eingeordnet', 'filled'],
      ['In Arbeit', 'ring'],
      ['Geändert', 'hollow'],
      ['Hat gewirkt', 'filled'],
    ])
    // Eingeordnet und In Arbeit teilen die Farbe; die Form trennt sie.
    const [triaged, inProgress, addressed, verified] = pills.map((pill) =>
      within(pill).getByTestId('case-status-dot'),
    )
    expect(inProgress).toHaveClass('ring-2', 'ring-offset-1')
    expect(triaged).not.toHaveClass('ring-2')
    expect(addressed).toHaveClass('border-2')
    expect(verified).not.toHaveClass('border-2')
    for (const dot of [triaged, inProgress, addressed, verified]) {
      expect(dot).toHaveAttribute('aria-hidden', 'true')
    }
  })

  it('bietet in der Liste keinen Knopf, der In Arbeit oder Hat gewirkt setzt', async () => {
    listCases.mockResolvedValue({
      items: [caseRead({ id: 'c2', status: 'in_progress' }), caseRead({ id: 'c4', status: 'verified' })],
      next_cursor: null,
    })
    countCases.mockResolvedValue(phaseECounts)
    renderList(false, '?status=all')
    await screen.findAllByRole('link', { name: 'coder' })
    // Die einzigen Knoepfe mit diesen Woertern sind die Filter-Chips.
    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    for (const button of screen.queryAllByRole('button', { name: /In Arbeit|Hat gewirkt/ })) {
      expect(group).toContainElement(button)
      expect(button).toHaveAttribute('aria-pressed')
    }
  })
})

describe('CaseList (a11y)', () => {
  it('hat keine axe-Violations mit Daten', async () => {
    listCases.mockResolvedValue({
      items: [caseRead({ severity: 'high' }), caseRead({ id: 'c2', status: 'addressed' })],
      next_cursor: 'cur-1',
    })
    const { container } = renderList(false)
    await screen.findAllByRole('link', { name: 'coder' })
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit In Arbeit und Hat gewirkt (editor)', async () => {
    countCases.mockResolvedValue(counts({ in_progress: 1, verified: 1 }))
    listCases.mockResolvedValue({
      items: [caseRead({ id: 'c1', status: 'in_progress' }), caseRead({ id: 'c2', status: 'verified' })],
      next_cursor: null,
    })
    const { container } = renderList(false, '?status=all')
    await screen.findAllByRole('link', { name: 'coder' })
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)

  it('hat keine axe-Violations mit In Arbeit und Hat gewirkt (viewer)', async () => {
    countCases.mockResolvedValue(counts({ in_progress: 1, verified: 1 }))
    listCases.mockResolvedValue({
      items: [caseRead({ id: 'c1', status: 'in_progress' }), caseRead({ id: 'c2', status: 'verified' })],
      next_cursor: null,
    })
    const { container } = renderList(true, '?status=all')
    await screen.findAllByRole('link', { name: 'coder' })
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)
})
