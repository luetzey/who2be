import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent, type Me, type WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { AgentOverview, FEEDBACK_WINDOW_DAYS } from './AgentOverview'

const session = { access_token: 'jwt' } as unknown as Session
const WS = '/v1/workspaces/ws-1'

const agent: Agent = {
  id: 'a1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Carla Bot',
  description: '',
  persona_id: 'p1',
  system_prompt_template_id: 'sp1',
  status: 'enabled',
  tool_policy: DEFAULT_TOOL_POLICY,
  persona_active: true,
  activatable: true,
  missing: [],
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

function meWithRole(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'o1',
        name: 'Org',
        slug: 'org',
        kind: 'personal',
        workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role }],
      },
    ],
  } as Me
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

const caseCounts = {
  open: 2,
  reopened: 1,
  triaged: 0,
  in_progress: 1,
  addressed: 5,
  verified: 0,
  dismissed: 3,
}

type Handlers = Record<string, () => Response>

function agentUsage(overrides: Record<string, unknown> = {}) {
  return {
    agent_id: 'a1',
    uses_7d: 12,
    uses_30d: 42,
    uses_by_type_30d: { persona: 10, playbook: 30, resource: 2 },
    active_days_30d: 9,
    last_used_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    last_active_at: null,
    daily: [],
    work_areas: [],
    counting_since: '2026-10-08',
    ...overrides,
  }
}

function defaultHandlers(): Handlers {
  return {
    [`${WS}/inbox/counts`]: () =>
      json({
        follow_ups_due: 1,
        memory_approval: 2,
        versions_review: null,
        system_prompts_review: null,
        cases_open: 0,
        patterns: 1,
        total: 3,
      }),
    [`${WS}/cases/counts`]: () => json(caseCounts),
    [`${WS}/feedback-overview`]: () =>
      json({
        items: [
          { entity_type: 'persona', entity_id: 'p1', name: 'P', usage_count: 9, feedback_count: 4, negative_count: 2, helpful_count: 2, last_activity_at: null },
          { entity_type: 'playbook', entity_id: 'pb1', name: 'B', usage_count: 3, feedback_count: 1, negative_count: 1, helpful_count: 0, last_activity_at: null },
        ],
      }),
    [`${WS}/memories/counts`]: () =>
      json({ total: 7, groups: { status: { pending: 2 }, health: { expiring_soon: 1 } } }),
    [`${WS}/patterns`]: () =>
      json({
        threshold: 3,
        window_days: 30,
        patterns: [
          { source: 'case', agent_id: 'a1', element: { target: 'playbook', entity_id: 'pb1' }, count: 3, evidence_ids: [], first_seen: '', last_seen: '' },
          { source: 'lesson', agent_id: 'a1', element: null, count: 5, evidence_ids: [], first_seen: '', last_seen: '' },
        ],
      }),
    [`${WS}/test-cases`]: () => json([{ id: 't1' }, { id: 't2' }]),
    [`${WS}/agents/a1/usage`]: () => json(agentUsage()),
    [`${WS}/agents/a1/work-areas`]: () =>
      json([
        { id: 'w1', name: 'Privat', scope: 'private', level: 'write', owner: true, agent_count: 1 },
        { id: 'w2', name: 'Team-Notizen', scope: 'shared', level: 'read', owner: false, agent_count: 4 },
        { id: 'w3', name: 'Allein geteilt', scope: 'shared', level: 'write', owner: false, agent_count: 1 },
      ]),
  }
}

function stub(overrides: Handlers = {}) {
  const handlers = { ...defaultHandlers(), ...overrides }
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname
    const handler = handlers[path]
    if (!handler) throw new Error(`Unmocked ${path}`)
    return handler()
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function requestedUrls(fetchMock: ReturnType<typeof stub>): URL[] {
  return fetchMock.mock.calls.map(([input]) => new URL(String(input)))
}

function renderOverview(role: WorkspaceRole = 'editor') {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me: meWithRole(role),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents/a1']}>
          <Routes>
            <Route
              path="/w/:workspaceId/agents/:id"
              element={<AgentOverview agent={agent} composition={<div data-testid="composition" />} />}
            />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AgentOverview (Navigation W2-b, Spec §3.2)', () => {
  it('editor: Aufgaben-Zeile mit Agent-Filter, fünf Kacheln mit Zahl, Untertitel und Ziel', async () => {
    const fetchMock = stub()
    renderOverview('editor')

    const summary = await screen.findByTestId('inbox-summary')
    expect(within(summary).getByText('3 Aufgaben warten auf dich')).toBeInTheDocument()
    expect(within(summary).getByRole('link', { name: /Alle ansehen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/inbox?agent=a1',
    )

    const cases = await screen.findByRole('link', { name: 'Rückmeldungen offen: 4' })
    expect(cases).toHaveAttribute('href', '/w/ws-1/feedback?tab=cases&agent=a1')
    expect(cases).toHaveAccessibleDescription('1 wieder offen · 1 in Arbeit')

    const feedback = await screen.findByRole('link', { name: 'Feedback zu seinen Bausteinen: 5' })
    expect(feedback).toHaveAttribute('href', '/w/ws-1/feedback?tab=signals&agent=a1')
    expect(feedback).toHaveAccessibleDescription('3 negativ · 30 Tage')

    const memory = await screen.findByRole('link', { name: 'Gedächtnis: 7' })
    expect(memory).toHaveAttribute('href', '/w/ws-1/agents/a1?tab=memory')
    expect(memory).toHaveAccessibleDescription('2 zur Freigabe · 1 läuft bald ab')

    const patterns = await screen.findByRole('link', { name: 'Muster: 2' })
    expect(patterns).toHaveAttribute('href', '/w/ws-1/feedback?tab=patterns&agent=a1')
    // Stärkstes Muster: der Lernvorschlag mit 5×.
    expect(patterns).toHaveAccessibleDescription('Lernvorschlag · 5×')

    const tests = await screen.findByRole('link', { name: 'Prüffälle: 2' })
    expect(tests).toHaveAttribute('href', '/w/ws-1/agents/a1?tab=tests')

    // Anfragen tragen den Agenten (und das Feedback-Fenster).
    const urls = requestedUrls(fetchMock)
    const byPath = (path: string) => urls.find((url) => url.pathname === `${WS}${path}`)
    expect(byPath('/inbox/counts')?.searchParams.get('agent_id')).toBe('a1')
    expect(byPath('/cases/counts')?.searchParams.get('agent_id')).toBe('a1')
    expect(byPath('/feedback-overview')?.searchParams.get('agent_id')).toBe('a1')
    expect(byPath('/feedback-overview')?.searchParams.get('days')).toBe(String(FEEDBACK_WINDOW_DAYS))
    expect(byPath('/memories/counts')?.searchParams.get('agent_id')).toBe('a1')
    expect(byPath('/memories/counts')?.searchParams.get('status')).toBe('active')
    expect(byPath('/patterns')?.searchParams.get('agent_id')).toBe('a1')
    expect(byPath('/test-cases')?.searchParams.get('agent_id')).toBe('a1')
    expect(byPath('/test-cases')?.searchParams.get('status')).toBe('active')
  })

  it('viewer: nur die Kachel Rückmeldungen, keine Anfragen an editor-Endpunkte', async () => {
    const fetchMock = stub({
      [`${WS}/inbox/counts`]: () =>
        json({
          follow_ups_due: null,
          memory_approval: 0,
          versions_review: null,
          system_prompts_review: null,
          cases_open: null,
          patterns: null,
          total: 0,
        }),
    })
    renderOverview('viewer')

    expect(await screen.findByRole('link', { name: 'Rückmeldungen offen: 4' })).toBeInTheDocument()
    expect(await screen.findAllByTestId('agent-work-area')).toHaveLength(3)
    for (const id of ['feedback', 'memory', 'patterns', 'tests']) {
      expect(screen.queryByTestId(`agent-kpi-${id}`)).toBeNull()
    }
    const paths = requestedUrls(fetchMock).map((url) => url.pathname)
    for (const path of ['/feedback-overview', '/memories/counts', '/patterns', '/test-cases']) {
      expect(paths).not.toContain(`${WS}${path}`)
    }
    // Aufgaben-Zeile bei 0: entfällt am Agenten ganz.
    await waitFor(() => expect(paths).toContain(`${WS}/inbox/counts`))
    expect(screen.queryByTestId('inbox-summary')).toBeNull()
    expect(screen.queryByTestId('inbox-summary-loading')).toBeNull()
    // Nutzung steht auch für viewer.
    expect(await screen.findByRole('group', { name: 'Nutzung: 42' })).toBeInTheDocument()
  })

  it('Nutzung: uses_30d, „zuletzt vor …“, kein Link; Anfrage an den Agent-Zähler', async () => {
    const fetchMock = stub()
    renderOverview('editor')

    const usage = await screen.findByRole('group', { name: 'Nutzung: 42' })
    expect(usage).toHaveAccessibleDescription('zuletzt vor 2 Stunden · 30 Tage')
    expect(usage.tagName).toBe('DIV')
    expect(screen.queryByRole('link', { name: /Nutzung/ })).toBeNull()
    expect(requestedUrls(fetchMock).map((url) => url.pathname)).toContain(`${WS}/agents/a1/usage`)
  })

  it('Nutzung ohne Auslieferung nennt den Zählbeginn; Fehler zeigt „–“', async () => {
    stub({
      [`${WS}/agents/a1/usage`]: () =>
        json(agentUsage({ uses_7d: 0, uses_30d: 0, last_used_at: null })),
    })
    const { unmount } = renderOverview('viewer')
    const usage = await screen.findByRole('group', { name: 'Nutzung: 0' })
    expect(usage).toHaveAccessibleDescription('Noch keine · gezählt seit 08.10.2026')
    unmount()
    vi.unstubAllGlobals()

    stub({ [`${WS}/agents/a1/usage`]: () => json({ detail: 'x' }, 500) })
    renderOverview('viewer')
    const failed = await screen.findByRole('group', { name: 'Nutzung: –' })
    expect(failed).toHaveAccessibleDescription('Nicht verfügbar')
    expect(await screen.findByRole('link', { name: 'Rückmeldungen offen: 4' })).toBeInTheDocument()
  })

  it('Zahl 0 zeigt „0“ und „Noch keine“; Fehler einer Kachel zeigt „–“, die anderen bleiben', async () => {
    stub({
      [`${WS}/cases/counts`]: () =>
        json({ open: 0, reopened: 0, triaged: 0, in_progress: 0, addressed: 0, verified: 0, dismissed: 0 }),
      [`${WS}/patterns`]: () => json({ detail: 'boom' }, 500),
      [`${WS}/test-cases`]: () => json([]),
    })
    renderOverview('editor')

    const cases = await screen.findByRole('link', { name: 'Rückmeldungen offen: 0' })
    expect(cases).toHaveAccessibleDescription('Noch keine')
    const tests = await screen.findByRole('link', { name: 'Prüffälle: 0' })
    expect(tests).toHaveAccessibleDescription('Noch keine')

    const patterns = await screen.findByRole('link', { name: 'Muster: –' })
    expect(patterns).toHaveAccessibleDescription('Nicht verfügbar')
    expect(screen.queryByTestId('error-alert')).toBeNull()
    expect(await screen.findByRole('link', { name: 'Gedächtnis: 7' })).toBeInTheDocument()
  })

  it('Arbeitsbereiche: eigener, geteilt mit Stufe und +n Agenten, Links auf den Bereich', async () => {
    stub()
    renderOverview('editor')

    const card = await screen.findByTestId('agent-work-areas')
    expect(within(card).getByRole('heading', { name: 'Arbeitsbereiche' })).toBeInTheDocument()
    const rows = await within(card).findAllByTestId('agent-work-area')
    expect(rows).toHaveLength(3)
    expect(within(rows[0]).getByRole('link', { name: 'Privat' })).toHaveAttribute(
      'href',
      '/w/ws-1/workarea/areas/w1',
    )
    expect(rows[0]).toHaveTextContent('eigener')
    expect(rows[1]).toHaveTextContent('geteilt · lesen · +3 Agenten')
    // Nur dieser Agent hat Zugriff: kein „+0“.
    expect(rows[2]).toHaveTextContent(/geteilt · lesen\/schreiben$/)
    expect(within(card).getByText('Zugriff vergibst du am Arbeitsbereich unter „Zugriff“.')).toBeInTheDocument()
    // Zusammensetzung steht im selben Raster (ab lg nebeneinander).
    expect(screen.getByTestId('composition').parentElement).toBe(card.parentElement)
  })

  it('Arbeitsbereiche leer und Fehler mit „Erneut versuchen“', async () => {
    let fail = true
    stub({
      [`${WS}/agents/a1/work-areas`]: () => (fail ? json({ detail: 'x' }, 500) : json([])),
    })
    renderOverview('editor')

    const card = await screen.findByTestId('agent-work-areas')
    expect(await within(card).findByText('Die Arbeitsbereiche konnten nicht geladen werden.')).toBeInTheDocument()
    fail = false
    fireEvent.click(within(card).getByRole('button', { name: 'Erneut versuchen' }))
    expect(await within(card).findByTestId('agent-work-areas-empty')).toHaveTextContent(
      'Dieser Agent hat noch keinen Arbeitsbereich. Der private entsteht beim ersten Zugriff.',
    )
  })

  it('Aufgaben-Zeile entfällt bei Fehler der Zählung', async () => {
    stub({ [`${WS}/inbox/counts`]: () => json({ detail: 'x' }, 500) })
    renderOverview('admin')
    expect(await screen.findByRole('link', { name: 'Rückmeldungen offen: 4' })).toBeInTheDocument()
    expect(screen.queryByTestId('inbox-summary')).toBeNull()
  })
})
