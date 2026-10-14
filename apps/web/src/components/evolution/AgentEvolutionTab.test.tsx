import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  CaseCounts,
  InboxCounts,
  MeasureEvent,
  MeasureRead,
  SessionListItem,
  WorkspaceRole,
} from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { AgentEvolutionTab, EvolutionTabCount } from './AgentEvolutionTab'

const api = vi.hoisted(() => ({
  countCases: vi.fn(),
  listPatterns: vi.fn(),
  listSessions: vi.fn(),
  getSession: vi.fn(),
  getPersona: vi.fn(),
  getPlaybook: vi.fn(),
  getResource: vi.fn(),
  getExternalTool: vi.fn(),
  getSystemPromptTemplate: vi.fn(),
}))

vi.mock('@/api/useApi', () => ({ useApi: () => api }))

let role: WorkspaceRole | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

// Anfragen, die nur editor stellen darf (§3.7: viewer ohne Reviews/Muster).
const EDITOR_ONLY = ['listSessions', 'getSession', 'listPatterns'] as const

const AGENT = { id: 'a1', name: 'Support-Assistent' }

function counts(overrides: Partial<CaseCounts> = {}): CaseCounts {
  return {
    open: 1,
    reopened: 1,
    triaged: 2,
    in_progress: 0,
    addressed: 0,
    verified: 0,
    dismissed: 0,
    ...overrides,
  }
}

function inboxCounts(overrides: Partial<InboxCounts> = {}): InboxCounts {
  return {
    follow_ups_due: 1,
    memory_approval: 0,
    versions_review: null,
    system_prompts_review: null,
    cases_open: 2,
    patterns: 1,
    total: 3,
    ...overrides,
  }
}

function ev(event: MeasureEvent['event'], created_at: string): MeasureEvent {
  return {
    id: `ev-${event}`,
    measure_id: 'm',
    event,
    actor_kind: 'human',
    actor_id: null,
    version_entity_type: null,
    version_id: null,
    verdict: null,
    metrics: null,
    note: null,
    created_at,
  }
}

function measure(overrides: Partial<MeasureRead> = {}): MeasureRead {
  return {
    id: 'm1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    session_id: 's1',
    case_ids: ['c1', 'c2', 'c3'],
    target: 'playbook',
    entity_id: 'pb1',
    change_summary: 'Rückgabefrist aus Resource lesen statt raten',
    test_case_id: 't1',
    success_criterion: '',
    counterposition: '',
    follow_up_at: '2026-10-13',
    state: 'activated',
    events: [ev('activated', '2026-09-26T10:00:00Z')],
    created_at: '2026-09-25T10:00:00Z',
    ...overrides,
  }
}

function review(overrides: Partial<SessionListItem> = {}): SessionListItem {
  return {
    id: 's1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    trigger: 'manual',
    participants: [],
    summary: 'Erstattungen: Frist falsch genannt',
    decisions: [],
    dissent: [],
    follow_up_at: '2026-10-13',
    supersedes_id: null,
    submitted_by_kind: 'agent',
    submitted_by: 'builder',
    case_ids: ['c1', 'c2', 'c3'],
    created_at: '2026-09-25T10:00:00Z',
    case_count: 3,
    measure_count: 2,
    next_follow_up_at: '2026-10-13',
    due_measure_count: 1,
    superseded_by_id: null,
    ...overrides,
  }
}

const S1_MEASURES = [
  measure(),
  measure({
    id: 'm2',
    target: 'persona',
    entity_id: 'p1',
    change_summary: 'Bei Eskalation zuerst Teamlead nennen',
    follow_up_at: '2026-10-24',
    case_ids: ['c4'],
    events: [ev('draft_linked', '2026-09-27T10:00:00Z')],
    state: 'draft_linked',
  }),
  // Abgeschlossen: erscheint nicht unter „Aenderungen“.
  measure({ id: 'm3', events: [ev('withdrawn', '2026-09-28T10:00:00Z')], state: 'withdrawn' }),
]

function renderTab(inbox: InboxCounts | null = inboxCounts(), failed = false) {
  return renderInRoutes(<AgentEvolutionTab agent={AGENT} inbox={{ counts: inbox, failed }} />, {
    path: '/w/:workspaceId/agents/:id',
    initialEntries: ['/w/ws-1/agents/a1?tab=evolution'],
  })
}

function withData() {
  api.listSessions.mockResolvedValue({
    items: [
      review(),
      review({
        id: 's0',
        trigger: 'scheduled',
        summary: '',
        created_at: '2026-09-02T10:00:00Z',
        case_count: 1,
        measure_count: 1,
        next_follow_up_at: null,
        due_measure_count: 0,
        submitted_by_kind: 'human',
      }),
    ],
    next_cursor: null,
  })
  api.getSession.mockImplementation((id: string) =>
    Promise.resolve({
      session: review({ id }),
      measures: id === 's1' ? S1_MEASURES : [],
    }),
  )
}

function empty() {
  api.countCases.mockResolvedValue(counts({ open: 0, reopened: 0, triaged: 0 }))
  api.listPatterns.mockResolvedValue({ threshold: 3, window_days: 30, patterns: [] })
  api.listSessions.mockResolvedValue({ items: [], next_cursor: null })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-14T10:00:00'))
  role = 'editor'
  api.countCases.mockResolvedValue(counts())
  api.listPatterns.mockResolvedValue({
    threshold: 3,
    window_days: 30,
    patterns: [{ source: 'case', agent_id: 'a1', element: null, count: 3, evidence_ids: [], first_seen: '', last_seen: '' }],
  })
  api.getPlaybook.mockResolvedValue({ id: 'pb1', name: 'Erstattung' })
  api.getPersona.mockResolvedValue({ id: 'p1', name: 'Kundenservice' })
  withData()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('AgentEvolutionTab — editor', () => {
  it('zeigt Anleitung und die vier Schritte als Liste mit Stand', async () => {
    renderTab()

    const guide = screen.getByTestId('evolution-guide')
    expect(guide.tagName).toBe('DETAILS')
    expect(guide).not.toHaveAttribute('open')
    expect(within(guide).getByText('So entwickelst du einen Agenten weiter')).toBeInTheDocument()

    const steps = screen.getByRole('list', { name: 'Schritte der Weiterentwicklung' })
    expect(steps.tagName).toBe('OL')
    expect(
      within(steps)
        .getAllByRole('heading', { level: 3 })
        .map((node) => node.textContent),
    ).toEqual(['① Sammeln', '② Besprechen', '③ Umsetzen', '④ Prüfen'])

    // ① aus countCases + listPatterns, „wartet auf dich“ aus /inbox/counts.
    const collect = screen.getByTestId('evolution-step-collect')
    await waitFor(() =>
      expect(within(collect).getByTestId('evolution-step-collect-head')).toHaveTextContent(
        '4 Rückmeldungen offen',
      ),
    )
    await waitFor(() =>
      expect(collect).toHaveTextContent('2 eingeordnet · 1 wieder offen · 1 Muster'),
    )
    expect(within(collect).getByTestId('evolution-step-collect-waiting')).toHaveTextContent(
      '2 warten auf dich',
    )
    expect(within(collect).getByRole('link', { name: 'Ansehen' })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback?tab=cases&agent=a1',
    )
    expect(within(collect).getByRole('button', { name: 'Rückmeldung geben' })).toBeInTheDocument()

    // ② letztes Review und bereite Rueckmeldungen.
    const discuss = screen.getByTestId('evolution-step-discuss')
    await waitFor(() => expect(discuss).toHaveTextContent('Letztes Review 25.09.2026'))
    expect(discuss).toHaveTextContent('2 eingeordnete Rückmeldungen sind bereit')
    expect(within(discuss).getByRole('link', { name: 'Review vorbereiten' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/prepare',
    )

    // ③ nur nicht aktivierte Aenderungen.
    const implement = screen.getByTestId('evolution-step-implement')
    await waitFor(() => expect(implement).toHaveTextContent('1 Änderung offen'))
    expect(implement).toHaveTextContent('Entwurf verknüpft, noch nicht aktiviert')

    // ④ Zahl vom Server, Ziel = erste faellige Aenderung im faelligen Review.
    const check = screen.getByTestId('evolution-step-check')
    expect(check).toHaveTextContent('1 Nachkontrolle fällig')
    expect(within(check).getByTestId('evolution-check-since')).toHaveTextContent('seit 1 Tag fällig')
    expect(within(check).getByTestId('evolution-step-check-waiting')).toHaveTextContent(
      '1 wartet auf dich',
    )
    await waitFor(() =>
      expect(within(check).getByRole('link', { name: 'Nachkontrolle öffnen' })).toHaveAttribute(
        'href',
        '/w/ws-1/agents/a1/reviews/s1?change=m1',
      ),
    )
  })

  it('„Änderungen“: nur offene, fällige zuerst, mit Aktion je Zeile', async () => {
    renderTab()

    const section = await screen.findByTestId('evolution-changes')
    expect(within(section).getByRole('heading', { level: 2, name: 'Änderungen' })).toBeInTheDocument()
    const rows = within(section).getAllByTestId('evolution-change')
    expect(rows).toHaveLength(2)

    await waitFor(() => expect(rows[0]).toHaveTextContent('Playbook Erstattung'))
    expect(within(rows[0]).getByTestId('evolution-change-due')).toHaveTextContent('Nachkontrolle fällig')
    expect(rows[0]).toHaveTextContent('aktiv seit 26.09.2026')
    expect(rows[0]).toHaveTextContent('aus dem Review vom 25.09.2026')
    expect(rows[0]).toHaveTextContent('3 Rückmeldungen')
    expect(
      within(rows[0]).getByRole('link', { name: 'Nachkontrolle öffnen: Playbook Erstattung' }),
    ).toHaveAttribute('href', '/w/ws-1/agents/a1/reviews/s1?change=m1')

    await waitFor(() => expect(rows[1]).toHaveTextContent('Persona Kundenservice'))
    expect(within(rows[1]).getByTestId('evolution-change-state')).toHaveTextContent('Entwurf verknüpft')
    expect(rows[1]).toHaveTextContent('Nachkontrolle am 24.10.2026')
    expect(rows[1]).not.toHaveTextContent('aktiv seit')
    expect(
      within(rows[1]).getByRole('link', { name: 'Ansehen: Persona Kundenservice' }),
    ).toHaveAttribute('href', '/w/ws-1/agents/a1/reviews/s1?change=m2')

    expect(section).not.toHaveTextContent('Ältere Änderungen')
    // Hoechstens 10 Reviews: ein listSessions mit limit 10, je Review ein getSession.
    expect(api.listSessions).toHaveBeenCalledTimes(1)
    expect(api.listSessions).toHaveBeenCalledWith({ agent_id: 'a1' }, { limit: 10 })
    expect(api.getSession).toHaveBeenCalledTimes(2)

    // ③ „Ansehen ↓“ springt zum Abschnitt.
    section.scrollIntoView = vi.fn()
    fireEvent.click(
      within(screen.getByTestId('evolution-step-implement')).getByRole('button', { name: /Ansehen/ }),
    )
    expect(section.scrollIntoView).toHaveBeenCalled()
    expect(section).toHaveFocus()
  })

  it('„Reviews“: Zeilen als Link mit genau einer Markierung, „Weitere laden“ per Cursor', async () => {
    api.listSessions
      .mockResolvedValueOnce({
        items: [
          review(),
          review({ id: 's2', due_measure_count: 0, superseded_by_id: 's9', next_follow_up_at: null }),
          review({ id: 's3', due_measure_count: 0, supersedes_id: 's2', next_follow_up_at: '2026-11-01' }),
        ],
        next_cursor: 'c-1',
      })
      .mockResolvedValueOnce({
        items: [review({ id: 's4', due_measure_count: 0, next_follow_up_at: '2026-11-02', created_at: '2026-08-01T10:00:00Z' })],
        next_cursor: null,
      })
    renderTab()

    const section = screen.getByTestId('evolution-reviews')
    const rows = await within(section).findAllByTestId('evolution-review')
    expect(rows).toHaveLength(3)
    expect(within(rows[0]).getByRole('link', { name: 'Review vom 25.09.2026' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/s1',
    )
    expect(rows[0]).toHaveTextContent('Manuell')
    expect(rows[0]).toHaveTextContent('3 Rückmeldungen · 2 Änderungen · vom Client übermittelt')
    expect(rows[0]).toHaveTextContent('Nachkontrolle fällig')
    expect(rows[1]).toHaveTextContent('Ersetzt')
    expect(rows[1]).not.toHaveTextContent('Nachkontrolle')
    expect(rows[2]).toHaveTextContent('Korrigiert')
    expect(rows[2]).not.toHaveTextContent('Nachkontrolle am')
    // Mehr als 10 Reviews moeglich: Hinweis unter „Aenderungen“.
    expect(await screen.findByTestId('evolution-changes')).toHaveTextContent(
      'Ältere Änderungen findest du in den Reviews.',
    )

    fireEvent.click(within(section).getByRole('button', { name: 'Weitere laden' }))
    await waitFor(() => expect(within(section).getAllByTestId('evolution-review')).toHaveLength(4))
    expect(api.listSessions).toHaveBeenLastCalledWith({ agent_id: 'a1' }, { cursor: 'c-1', limit: 10 })
    expect(within(section).queryByRole('button', { name: 'Weitere laden' })).toBeNull()
    expect(within(section).getAllByTestId('evolution-review')[3]).toHaveTextContent(
      'Nachkontrolle am 02.11.2026',
    )
    // Weitere Reviews laden keine weiteren Aenderungen (§3.4: hoechstens 10).
    expect(api.getSession).toHaveBeenCalledTimes(3)
  })

  it('leer: kein Abschnitt „Änderungen“, Leer-Zustand mit „Review vorbereiten“', async () => {
    empty()
    renderTab(inboxCounts({ follow_ups_due: 0, cases_open: 0 }))

    const emptyState = await screen.findByTestId('evolution-reviews-empty')
    expect(emptyState).toHaveTextContent('Mit Support-Assistent gab es noch kein Review.')
    expect(within(emptyState).getByRole('link', { name: 'Review vorbereiten' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/prepare',
    )
    await waitFor(() =>
      expect(screen.getByTestId('evolution-step-implement')).toHaveTextContent('Keine offenen Änderungen'),
    )
    expect(screen.queryByTestId('evolution-changes')).toBeNull()
    expect(screen.getByTestId('evolution-step-discuss')).toHaveTextContent('Noch kein Review')
    expect(screen.getByTestId('evolution-step-check')).toHaveTextContent('Keine geplant')
    await waitFor(() =>
      expect(screen.getByTestId('evolution-step-collect')).toHaveTextContent('0 Rückmeldungen offen'),
    )
    // Nichts wartet: kein „wartet auf dich“, keine Aktion in ④.
    expect(screen.queryByTestId('evolution-step-collect-waiting')).toBeNull()
    expect(screen.queryByTestId('evolution-step-check-waiting')).toBeNull()
    expect(
      within(screen.getByTestId('evolution-step-check')).queryByRole('link', { name: 'Nachkontrolle öffnen' }),
    ).toBeNull()
  })

  it('④ ohne fällige: nächster Termin aus der Liste', async () => {
    api.listSessions.mockResolvedValue({
      items: [review({ due_measure_count: 0, next_follow_up_at: '2026-10-24' })],
      next_cursor: null,
    })
    renderTab(inboxCounts({ follow_ups_due: 0 }))
    await waitFor(() =>
      expect(screen.getByTestId('evolution-step-check')).toHaveTextContent('Nächste am 24.10.2026'),
    )
  })

  // Eine Quelle je Wert (PM 2026-10-14): Server und lokale Rechnung laufen
  // hier bewusst auseinander, damit ein lokales Nachrechnen auffaellt.
  it('④ zeigt follow_ups_due vom Server, nicht die lokal fälligen Änderungen', async () => {
    renderTab(inboxCounts({ follow_ups_due: 5 }))

    // Lokal ist genau eine geladene Aenderung faellig (m1).
    const section = await screen.findByTestId('evolution-changes')
    await waitFor(() => expect(within(section).getAllByTestId('evolution-change-due')).toHaveLength(1))

    const check = screen.getByTestId('evolution-step-check')
    expect(within(check).getByTestId('evolution-step-check-head')).toHaveTextContent(
      '5 Nachkontrollen fällig',
    )
    expect(within(check).getByTestId('evolution-step-check-waiting')).toHaveTextContent(
      '5 warten auf dich',
    )
  })

  it('Review-Markierung „Nachkontrolle fällig“ nur aus due_measure_count, nicht aus dem Datum', async () => {
    api.listSessions.mockResolvedValue({
      items: [
        // Datum vorbei, Server sagt: nichts faellig.
        review({ id: 's1', due_measure_count: 0, next_follow_up_at: '2026-10-01' }),
        // Datum in der Zukunft, Server sagt: faellig.
        review({
          id: 's2',
          due_measure_count: 2,
          next_follow_up_at: '2026-11-20',
          created_at: '2026-09-20T10:00:00Z',
        }),
      ],
      next_cursor: null,
    })
    renderTab()

    const section = screen.getByTestId('evolution-reviews')
    const rows = await within(section).findAllByTestId('evolution-review')
    expect(rows).toHaveLength(2)
    expect(rows[0]).not.toHaveTextContent('Nachkontrolle fällig')
    expect(rows[0]).toHaveTextContent('Nachkontrolle am 01.10.2026')
    expect(rows[1]).toHaveTextContent('Nachkontrolle fällig')
    expect(rows[1]).not.toHaveTextContent('Nachkontrolle am')
  })

  it('„Weitere laden“ verwirft eine Seite, die nach einem Agentwechsel ankommt', async () => {
    let resolveOld: (page: { items: SessionListItem[]; next_cursor: string | null }) => void = () => {}
    api.listSessions.mockImplementation(
      (filter: { agent_id: string }, opts: { cursor?: string }) => {
        if (filter.agent_id === 'a1' && opts.cursor === undefined) {
          return Promise.resolve({ items: [review()], next_cursor: 'c-1' })
        }
        if (filter.agent_id === 'a1') {
          return new Promise((resolve) => {
            resolveOld = resolve
          })
        }
        return Promise.resolve({
          items: [review({ id: 'b1', agent_id: 'a2', created_at: '2026-09-10T10:00:00Z', due_measure_count: 0 })],
          next_cursor: null,
        })
      },
    )

    function Switcher() {
      const [agent, setAgent] = useState(AGENT)
      return (
        <>
          <button type="button" onClick={() => setAgent({ id: 'a2', name: 'Zweiter' })}>
            Agent wechseln
          </button>
          <AgentEvolutionTab agent={agent} inbox={{ counts: inboxCounts(), failed: false }} />
        </>
      )
    }
    renderInRoutes(<Switcher />, {
      path: '/w/:workspaceId/agents/:id',
      initialEntries: ['/w/ws-1/agents/a1?tab=evolution'],
    })

    const section = screen.getByTestId('evolution-reviews')
    await within(section).findByRole('link', { name: 'Review vom 25.09.2026' })
    fireEvent.click(within(section).getByRole('button', { name: 'Weitere laden' }))
    expect(api.listSessions).toHaveBeenLastCalledWith({ agent_id: 'a1' }, { cursor: 'c-1', limit: 10 })

    fireEvent.click(screen.getByRole('button', { name: 'Agent wechseln' }))
    await within(screen.getByTestId('evolution-reviews')).findByRole('link', {
      name: 'Review vom 10.09.2026',
    })

    // Die alte Seite von a1 kommt erst jetzt an und darf nicht angehaengt werden.
    await act(async () => {
      resolveOld({
        items: [review({ id: 's-old', created_at: '2026-07-01T10:00:00Z' })],
        next_cursor: null,
      })
    })
    const rows = within(screen.getByTestId('evolution-reviews')).getAllByTestId('evolution-review')
    expect(rows).toHaveLength(1)
    expect(rows[0]).toHaveTextContent('Review vom 10.09.2026')
    expect(screen.queryByText('Review vom 01.07.2026')).toBeNull()
  })

  it('Fehler je Karte: „–“ und „Nicht verfügbar“, die anderen bleiben', async () => {
    api.countCases.mockRejectedValue(new Error('kaputt'))
    api.listSessions.mockRejectedValue(new Error('kaputt'))
    renderTab(null, true)

    const collect = screen.getByTestId('evolution-step-collect')
    await waitFor(() => expect(collect).toHaveTextContent('Nicht verfügbar'))
    expect(within(collect).getByTestId('evolution-step-collect-head')).toHaveTextContent('–')
    await waitFor(() =>
      expect(screen.getByTestId('evolution-step-discuss')).toHaveTextContent('Nicht verfügbar'),
    )
    expect(screen.getByTestId('evolution-step-check')).toHaveTextContent('Nicht verfügbar')
    expect(screen.getByRole('alert')).toHaveTextContent('Die Reviews konnten nicht geladen werden.')
    // Aktionen bleiben (Muster Kacheln W2-b).
    expect(within(collect).getByRole('link', { name: 'Ansehen' })).toBeInTheDocument()
  })
})

describe('AgentEvolutionTab — Rechte', () => {
  it('viewer: nur ① mit eigenen Rückmeldungen und Erklärsatz, ohne Reviews-Requests', async () => {
    role = 'viewer'
    api.countCases.mockResolvedValue(
      counts({ open: 0, reopened: 0, triaged: 0, in_progress: 1, addressed: 1 }),
    )
    renderTab()

    const viewer = await screen.findByTestId('agent-evolution-viewer')
    const steps = within(viewer).getByRole('list', { name: 'Schritte der Weiterentwicklung' })
    expect(within(steps).getAllByRole('listitem')).toHaveLength(1)
    await waitFor(() =>
      expect(screen.getByTestId('evolution-step-collect-head')).toHaveTextContent(
        '2 deiner Rückmeldungen',
      ),
    )
    expect(screen.getByTestId('evolution-step-collect')).toHaveTextContent('1 in Arbeit · 1 geändert')
    expect(screen.getByRole('link', { name: 'Meine Rückmeldungen' })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback',
    )
    expect(screen.getByRole('button', { name: 'Rückmeldung geben' })).toBeInTheDocument()
    expect(screen.getByTestId('evolution-viewer-explain')).toHaveTextContent(
      'Reviews, Änderungen und Nachkontrollen führen Editoren.',
    )
    expect(screen.queryByTestId('evolution-guide')).toBeNull()
    expect(screen.queryByTestId('evolution-reviews')).toBeNull()
    expect(screen.queryByText('② Besprechen')).toBeNull()

    for (const name of EDITOR_ONLY) expect(api[name]).not.toHaveBeenCalled()
    expect(api.countCases).toHaveBeenCalledWith('a1')
  })

  it('role === null: rendert nichts und fragt nichts an', () => {
    role = null
    renderTab()
    expect(screen.queryByTestId('agent-evolution')).toBeNull()
    expect(screen.queryByTestId('agent-evolution-viewer')).toBeNull()
    for (const name of [...EDITOR_ONLY, 'countCases'] as const) expect(api[name]).not.toHaveBeenCalled()
  })

  it('admin sieht die editor-Ansicht', async () => {
    role = 'admin'
    renderTab()
    expect(await screen.findByTestId('agent-evolution')).toBeInTheDocument()
    expect(api.listSessions).toHaveBeenCalled()
  })
})

describe('EvolutionTabCount', () => {
  it('zeigt cases_open + follow_ups_due mit zugänglichem Namen, ohne Muster', () => {
    renderInRoutes(<EvolutionTabCount counts={inboxCounts({ patterns: 9 })} />, {
      path: '/w/:workspaceId',
      initialEntries: ['/w/ws-1'],
    })
    const pill = screen.getByTestId('evolution-tab-count')
    expect(pill).toHaveTextContent('3, 3 warten auf dich')
  })

  it('bei 0 oder ohne Zahlen kein Zähler', () => {
    const { rerender } = renderInRoutes(
      <EvolutionTabCount counts={inboxCounts({ cases_open: 0, follow_ups_due: 0 })} />,
      { path: '/w/:workspaceId', initialEntries: ['/w/ws-1'] },
    )
    expect(screen.queryByTestId('evolution-tab-count')).toBeNull()
    rerender(<EvolutionTabCount counts={null} />)
    expect(screen.queryByTestId('evolution-tab-count')).toBeNull()
  })
})

describe('AgentEvolutionTab (a11y)', () => {
  it('a11y: editor mit Daten ohne axe-Violations', async () => {
    const { container } = renderTab()
    await screen.findByTestId('evolution-changes')
    await waitFor(() => expect(screen.getAllByTestId('evolution-change')[1]).toHaveTextContent('Kundenservice'))
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)

  it('a11y: editor leer ohne axe-Violations', async () => {
    empty()
    const { container } = renderTab(inboxCounts({ follow_ups_due: 0, cases_open: 0 }))
    await screen.findByTestId('evolution-reviews-empty')
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)

  it('a11y: viewer ohne axe-Violations', async () => {
    role = 'viewer'
    const { container } = renderTab()
    await waitFor(() =>
      expect(screen.getByTestId('evolution-step-collect-head')).toHaveTextContent('deiner Rückmeldungen'),
    )
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)
})
