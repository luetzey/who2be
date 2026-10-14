import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type {
  Agent,
  CaseRead,
  MeasureRead,
  MeasureEvent,
  Member,
  SessionDetail,
  SessionListItem,
  SessionRead,
  WorkspaceRole,
} from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { ReviewDetailPage } from './ReviewDetailPage'

const api = vi.hoisted(() => ({
  getSession: vi.fn(),
  listSessions: vi.fn(),
  listAgents: vi.fn(),
  listMembers: vi.fn(),
  getCase: vi.fn(),
  getTestCase: vi.fn(),
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

const { notifySuccess, notifyError } = vi.hoisted(() => ({
  notifySuccess: vi.fn(),
  notifyError: vi.fn(),
}))
vi.mock('@/lib/feedback', () => ({
  notify: { success: notifySuccess, error: notifyError, info: vi.fn() },
}))

const { copySpy } = vi.hoisted(() => ({ copySpy: vi.fn() }))
vi.mock('@/lib/clipboard', () => ({ copyToClipboard: copySpy }))

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateSpy }
})

const agents = [
  { id: 'a1', name: 'coder' },
  { id: 'a2', name: 'reviewer' },
] as unknown as Agent[]

const members = [
  { user_id: 'u1', email: 'yannick@example.org', role: 'admin', joined_at: '2026-01-01' },
] as Member[]

const SUMMARY = 'Vertraulich: Kunde Müller hat sich beschwert.'

function sessionRead(overrides: Partial<SessionRead> = {}): SessionRead {
  return {
    id: 's1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    trigger: 'threshold',
    participants: [
      { kind: 'builder', id: 'builder', role: 'Moderation' },
      { kind: 'agent', id: 'a1', role: 'Betroffener' },
      { kind: 'agent', id: 'gone', role: 'Zweitmeinung' },
      { kind: 'human', id: 'u1', role: 'Owner' },
      { kind: 'human', id: 'u-left', role: 'Beobachtung' },
    ],
    summary: SUMMARY,
    decisions: [
      { text: 'Tests vor dem Push.', standard_ref: 'https://example.org/std#tests' },
      { text: '<b>kein HTML</b>', standard_ref: 'javascript:alert(1)' },
      { text: 'Ohne Verweis.', standard_ref: null },
    ],
    dissent: [{ participant_kind: 'agent', participant_id: 'a1', text: 'Zu streng.' }],
    follow_up_at: '2026-10-27',
    supersedes_id: null,
    submitted_by_kind: 'agent',
    submitted_by: 'a2',
    case_ids: ['c1', 'c-deleted'],
    created_at: '2026-09-25T10:00:00Z',
    ...overrides,
  }
}

function ev(
  id: string,
  event: MeasureEvent['event'],
  created_at: string,
  verdict: MeasureEvent['verdict'] = null,
): MeasureEvent {
  return {
    id,
    measure_id: 'm',
    event,
    actor_kind: 'agent',
    actor_id: null,
    version_entity_type: null,
    version_id: null,
    verdict,
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
    case_ids: ['c1'],
    target: 'playbook',
    entity_id: 'pb1',
    change_summary: 'Schritt 4 verlangt Tests.',
    test_case_id: 't1',
    success_criterion: 'Keine roten CI-Läufe.',
    counterposition: '',
    follow_up_at: null,
    state: 'activated',
    events: [ev('ev2', 'activated', '2026-09-26T10:00:00Z')],
    created_at: '2026-09-25T10:00:00Z',
    ...overrides,
  }
}

function detail(
  session: Partial<SessionRead> = {},
  measures?: MeasureRead[],
  superseded_by_id: string | null = null,
): SessionDetail {
  return { session: sessionRead(session), measures: measures ?? [measure()], superseded_by_id }
}

function listItem(session: SessionRead, superseded_by_id: string | null): SessionListItem {
  return {
    ...session,
    case_count: session.case_ids.length,
    measure_count: 1,
    next_follow_up_at: null,
    due_measure_count: 0,
    superseded_by_id,
  }
}

/** s1 ist durch `successorId` (angelegt `createdAt`) ersetzt; das Detail traegt den Verweis. */
function replacedBy(successorId: string, createdAt: string) {
  api.getSession.mockImplementation((id: string) => {
    if (id === 's1') return Promise.resolve(detail({}, undefined, successorId))
    if (id === successorId) {
      return Promise.resolve(detail({ id: successorId, supersedes_id: 's1', created_at: createdAt }))
    }
    return Promise.reject(new ApiError(404, 'session_not_found'))
  })
}

const caseRow = {
  id: 'c1',
  agent_id: 'a1',
  status: 'in_progress',
  expected_behavior: 'Tests vor dem Push lokal laufen lassen.',
} as unknown as CaseRead

function renderPage(path = '/w/ws-1/agents/a1/reviews/s1') {
  return renderInRoutes(<ReviewDetailPage />, {
    path: '/w/:workspaceId/agents/:agentId/reviews/:sessionId',
    initialEntries: [path],
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-14T10:00:00'))
  role = 'editor'
  api.getSession.mockImplementation((id: string) =>
    id === 's1'
      ? Promise.resolve(detail())
      : Promise.reject(new ApiError(404, 'session_not_found')),
  )
  api.listSessions.mockResolvedValue({
    items: [listItem(sessionRead(), null)],
    next_cursor: null,
  })
  api.listAgents.mockResolvedValue(agents)
  api.listMembers.mockResolvedValue(members)
  api.getCase.mockImplementation((id: string) =>
    id === 'c1'
      ? Promise.resolve({ case: caseRow })
      : Promise.reject(new ApiError(404, 'case_not_found')),
  )
  api.getTestCase.mockResolvedValue({ id: 't1', title: 'Push ohne Tests' })
  api.getPlaybook.mockResolvedValue({ id: 'pb1', name: 'Release' })
  copySpy.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('ReviewDetailPage', () => {
  it('zeigt Kopf, Herkunft, Abschnitte und Änderungen (editor)', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { level: 1, name: 'Review vom 25.09.2026' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('coder · Schwelle · vom Client übermittelt')).toBeInTheDocument())
    // Kopf (Meta-Pill) und Aenderung nennen beide den Termin.
    expect(screen.getAllByText('Nachkontrolle am 27.10.2026')).toHaveLength(2)
    expect(screen.getByRole('link', { name: /coder · Weiterentwicklung/ })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1?tab=evolution',
    )
    expect(screen.getByTestId('review-origin')).toHaveTextContent(
      /Vom Client übermittelt \(reviewer\) am .*Unveränderlich\./,
    )

    const headings = within(screen.getByRole('main'))
      .getAllByRole('heading', { level: 2 })
      .map((node) => node.textContent)
    expect(headings).toEqual([
      'Teilnehmende',
      'Zusammenfassung',
      'Entscheidungen',
      'Abweichende Meinungen',
      expect.stringMatching(/^Rückmeldungen/),
      expect.stringMatching(/^Änderungen/),
      'Korrektur einreichen',
    ])

    // Rueckmeldungen: geloeschte fehlen still, Status mit Wort.
    const cases = await screen.findAllByTestId('review-case')
    expect(cases).toHaveLength(1)
    expect(cases[0]).toHaveTextContent('In Arbeit')
    expect(within(cases[0]).getByRole('link')).toHaveAttribute('href', '/w/ws-1/feedback/cases/c1')

    // Aenderung: Label mit Elementname, Server-Zustand, Termin, Prueffall.
    const card = screen.getByTestId('review-measure')
    await waitFor(() => expect(within(card).getByRole('heading', { level: 3 })).toHaveTextContent('M1 · Playbook „Release“'))
    expect(within(card).getByTestId('measure-state')).toHaveTextContent('Aktiviert')
    expect(within(card).getByText('Nachkontrolle am 27.10.2026')).toBeInTheDocument()
    await waitFor(() => expect(card).toHaveTextContent('Prüffall: Push ohne Tests · 1 Rückmeldung'))
    expect(within(card).getByRole('link', { name: 'Änderung öffnen: M1 · Playbook „Release“' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/s1?change=m1',
    )
  })

  it('löst Teilnehmende mit Fallbacks auf (Builder, gelöschter Agent, ehemaliges Mitglied)', async () => {
    renderPage()
    const section = await screen.findByTestId('review-participants')
    await waitFor(() => expect(section).toHaveTextContent('yannick@example.org (Owner)'))
    expect(section).toHaveTextContent('Builder (Moderation)')
    expect(section).toHaveTextContent('coder (Betroffener)')
    expect(section).toHaveTextContent('Gelöschter Agent (Zweitmeinung)')
    expect(section).toHaveTextContent('Ehemaliges Mitglied (Beobachtung)')
    expect(section).not.toHaveTextContent('u-left')
    expect(section).not.toHaveTextContent('gone')
    expect(screen.getByTestId('review-dissent')).toHaveTextContent('coder: Zu streng.')
  })

  it('zeigt einen von einem Menschen eingereichten Review mit Namen', async () => {
    api.getSession.mockResolvedValue(detail({ submitted_by_kind: 'human', submitted_by: 'u1' }))
    renderPage()
    await waitFor(() =>
      expect(screen.getByTestId('review-origin')).toHaveTextContent(/Eingereicht von yannick@example.org am /),
    )
    expect(screen.getByText('coder · Schwelle')).toBeInTheDocument()
  })

  it('rendert Freitext als Text und verlinkt nur http(s)-Verweise', async () => {
    renderPage()
    const decisions = await screen.findByTestId('review-decisions')
    expect(within(decisions).getByText('<b>kein HTML</b>')).toBeInTheDocument()
    expect(decisions.querySelector('b')).toBeNull()
    const refs = within(decisions).getAllByTestId('decision-ref')
    expect(refs).toHaveLength(2)
    expect(within(refs[0]).getByRole('link')).toHaveAttribute('href', 'https://example.org/std#tests')
    expect(within(refs[1]).queryByRole('link')).toBeNull()
    expect(refs[1]).toHaveTextContent('Verweis: javascript:alert(1)')
  })

  it('markiert eine fällige Änderung nach lokalem Kalendertag', async () => {
    api.getSession.mockResolvedValue(
      detail({}, [
        measure({ follow_up_at: '2026-10-14' }),
        measure({
          id: 'm2',
          state: 'agreed',
          follow_up_at: '2026-10-01',
          events: [],
        }),
        measure({
          id: 'm3',
          state: 'effective',
          follow_up_at: '2026-10-01',
          events: [
            ev('f', 'activated', '2026-09-26T10:00:00Z'),
            ev('g', 'reviewed', '2026-10-02T10:00:00Z', 'effective'),
          ],
        }),
      ]),
    )
    renderPage()
    const cards = await screen.findAllByTestId('review-measure')
    expect(within(cards[0]).getByTestId('measure-due')).toHaveTextContent('Nachkontrolle fällig')
    expect(within(cards[1]).getByTestId('measure-due')).toHaveTextContent(
      'Nachkontrolle fällig, Änderung noch nicht aktiv',
    )
    expect(within(cards[2]).queryByTestId('measure-due')).toBeNull()
    expect(within(cards[2]).getByTestId('measure-state')).toHaveTextContent('Hat gewirkt')
  })

  it('Korrektur: Kopiertext enthält Session-ID, Agent-Name und -ID, aber keinen Freitext', async () => {
    renderPage()
    const block = await screen.findByTestId('review-correction')
    const textarea = await within(block).findByLabelText('Im Client einfügen:')
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toContain('zu coder (a1)'))
    const value = (textarea as HTMLTextAreaElement).value
    expect(value).toContain('s1')
    expect(value).toContain('supersedes_id s1')
    expect(value).not.toContain(SUMMARY)
    expect(value).not.toContain('Tests vor dem Push')
    expect(value).not.toContain('Zu streng')

    fireEvent.click(within(block).getByRole('button', { name: 'Kopieren' }))
    await waitFor(() => expect(copySpy).toHaveBeenCalledWith(value))
    expect(notifySuccess).toHaveBeenCalledWith('Kopiert.')
  })

  it('Korrektur vorwärts: ersetztes Ergebnis zeigt Banner, verlinkt den Nachfolger und hat keinen Kopierblock', async () => {
    replacedBy('s2', '2026-10-02T10:00:00Z')
    renderPage()
    const banner = await screen.findByTestId('review-replaced')
    await waitFor(() =>
      expect(banner).toHaveTextContent('Ersetzt durch das Review-Ergebnis vom 02.10.2026'),
    )
    expect(banner).toHaveTextContent('Die Änderungen dieses Review-Ergebnisses gelten weiter')
    expect(within(banner).getByRole('link', { name: 'Zum neuen Review-Ergebnis' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/s2',
    )
    expect(screen.queryByTestId('review-correction')).toBeNull()
    // Der Nachfolger kommt aus dem Detail, nicht aus der Liste.
    expect(api.listSessions).not.toHaveBeenCalled()
  })

  it('Korrektur vorwärts: ein Review hinter 1 000 anderen zeigt das Banner und keinen Kopierblock', async () => {
    // Die Liste des Agenten liefert endlos fremde Zeilen; die eigene Zeile
    // kaeme erst nach mehr als 1 000 Reviews. Das Detail kennt den Nachfolger.
    let page = 0
    api.listSessions.mockImplementation(() => {
      page += 1
      return Promise.resolve({
        items: Array.from({ length: 200 }, (_, i) =>
          listItem(sessionRead({ id: `other-${page}-${i}` }), null),
        ),
        next_cursor: `c${page + 1}`,
      })
    })
    replacedBy('s9', '2026-10-05T10:00:00Z')
    renderPage()
    const banner = await screen.findByTestId('review-replaced')
    await waitFor(() => expect(banner).toHaveTextContent('vom 05.10.2026'))
    expect(within(banner).getByRole('link', { name: 'Zum neuen Review-Ergebnis' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/s9',
    )
    expect(screen.queryByTestId('review-correction')).toBeNull()
  })

  it('Korrektur vorwärts: Banner und kein Kopierblock auch, wenn der Nachfolger nicht ladbar ist', async () => {
    api.getSession.mockImplementation((id: string) =>
      id === 's1'
        ? Promise.resolve(detail({}, undefined, 's2'))
        : Promise.reject(new Error('boom')),
    )
    renderPage()
    const banner = await screen.findByTestId('review-replaced')
    expect(banner).toHaveTextContent('Ersetzt durch das Review-Ergebnis vom …')
    expect(within(banner).getByRole('link', { name: 'Zum neuen Review-Ergebnis' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/s2',
    )
    expect(screen.queryByTestId('review-correction')).toBeNull()
  })

  it('Korrektur rückwärts: Meta-Link auf den Vorgänger mit dessen Datum', async () => {
    api.getSession.mockImplementation((id: string) =>
      id === 's1'
        ? Promise.resolve(detail({ supersedes_id: 's0' }))
        : Promise.resolve(detail({ id: 's0', created_at: '2026-09-01T10:00:00Z' })),
    )
    renderPage()
    const link = await screen.findByTestId('review-corrects')
    expect(link).toHaveAttribute('href', '/w/ws-1/agents/a1/reviews/s0')
    await waitFor(() => expect(link).toHaveTextContent('Korrigiert das Review-Ergebnis vom 01.09.2026'))
    expect(screen.queryByTestId('review-replaced')).toBeNull()
  })

  it('kopiert die ID über das Überlauf-Menü', async () => {
    renderPage()
    await screen.findByRole('heading', { level: 1 })
    fireEvent.pointerDown(screen.getByTestId('review-overflow'), { button: 0, ctrlKey: false })
    fireEvent.click(await screen.findByRole('menuitem', { name: 'ID kopieren' }))
    await waitFor(() => expect(copySpy).toHaveBeenCalledWith('s1'))
    expect(notifySuccess).toHaveBeenCalledWith('ID kopiert.')
  })

  it('ersetzt die URL, wenn die Agent-ID nicht passt (altes Lesezeichen)', async () => {
    renderPage('/w/ws-1/agents/a-old/reviews/s1?change=m1')
    await waitFor(() =>
      expect(navigateSpy).toHaveBeenCalledWith(
        { pathname: '/w/ws-1/agents/a1/reviews/s1', search: '?change=m1' },
        expect.objectContaining({ replace: true }),
      ),
    )
  })

  it('viewer: 404-Darstellung ohne Abruf', async () => {
    role = 'viewer'
    renderPage()
    expect(await screen.findByText('Dieses Review gibt es nicht (mehr).')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Zur Weiterentwicklung' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1?tab=evolution',
    )
    expect(api.getSession).not.toHaveBeenCalled()
    expect(api.listSessions).not.toHaveBeenCalled()
    expect(screen.queryByText(SUMMARY)).toBeNull()
  })

  it('unbekanntes Review: 404-Darstellung', async () => {
    renderPage('/w/ws-1/agents/a1/reviews/nope')
    expect(await screen.findByText('Dieses Review gibt es nicht (mehr).')).toBeInTheDocument()
  })

  it('Ladefehler: Meldung mit erneutem Versuch', async () => {
    api.getSession.mockRejectedValueOnce(new Error('boom'))
    renderPage()
    expect(await screen.findByText('Das Review-Ergebnis konnte nicht geladen werden.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Review vom 25.09.2026' })).toBeInTheDocument()
  })

  it('leere Abschnitte zeigen ihren Hinweis', async () => {
    api.getSession.mockResolvedValue({
      session: sessionRead({ decisions: [], dissent: [], case_ids: [] }),
      measures: [],
      superseded_by_id: null,
    })
    renderPage()
    expect(await screen.findByText('Keine Entscheidungen festgehalten.')).toBeInTheDocument()
    expect(screen.getByText('Keine abweichenden Meinungen festgehalten.')).toBeInTheDocument()
    expect(await screen.findByText('Keine Rückmeldungen mehr verknüpft.')).toBeInTheDocument()
    expect(screen.getByText('In diesem Review wurde keine Änderung vereinbart.')).toBeInTheDocument()
  })

  it('a11y: Review-Ergebnis ohne Violations', async () => {
    const { container } = renderPage()
    await screen.findAllByTestId('review-case')
    await screen.findByTestId('review-correction')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: ersetztes Review-Ergebnis ohne Violations', async () => {
    replacedBy('s2', '2026-10-02T10:00:00Z')
    const { container } = renderPage()
    await screen.findByTestId('review-replaced')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: Korrektur-Block aufgeklappt ohne Violations', async () => {
    const { container } = renderPage()
    const block = await screen.findByTestId('review-correction')
    ;(block as HTMLDetailsElement).open = true
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: 404-Darstellung (viewer) ohne Violations', async () => {
    role = 'viewer'
    const { container } = renderPage()
    await screen.findByText('Dieses Review gibt es nicht (mehr).')
    expect(await axe(container)).toHaveNoViolations()
  })
})
