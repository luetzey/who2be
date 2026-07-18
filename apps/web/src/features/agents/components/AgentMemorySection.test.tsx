import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryRead } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { AgentMemorySection } from './AgentMemorySection'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

const WS_PREFIX = '/v1/workspaces/ws-1'

function memory(overrides: Partial<MemoryRead> = {}): MemoryRead {
  return {
    id: 'm1',
    agent_id: 'a1',
    status: 'pending',
    fact: 'Nutzer bevorzugt kurze Antworten.',
    context: 'Nutzer hat das in der letzten Session mehrfach betont.',
    category: 'preference',
    importance: 6,
    source: 'agent',
    triage_note: null,
    retrieval_count: 0,
    last_retrieved_at: null,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetchRoutes(handlers: Record<string, (init?: RequestInit) => Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const key = `${method} ${new URL(String(input)).pathname}`
    const handler = handlers[key]
    if (!handler) {
      throw new Error(`Unmocked ${key}`)
    }
    return handler(init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderSection() {
  return render(
    <SessionContext.Provider
      value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents/a1']}>
          <Routes>
            <Route
              path="/w/:workspaceId/agents/:id"
              element={<AgentMemorySection agentId="a1" />}
            />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('AgentMemorySection', () => {
  it('pending-Vorschlag rendert mit context + Freigeben ruft POST triage und reloadet', async () => {
    const pending = memory()
    let listCalls = 0
    const triageBodies: unknown[] = []
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => {
        listCalls += 1
        return jsonResponse(listCalls === 1 ? [pending] : [{ ...pending, status: 'active' }])
      },
      [`POST ${WS_PREFIX}/agents/a1/memories/m1/triage`]: (init) => {
        triageBodies.push(JSON.parse(String(init?.body)))
        return jsonResponse({ ...pending, status: 'active' })
      },
    })

    renderSection()

    const row = await screen.findByTestId('memory-pending-row')
    // Begruendung (context) ist nur Triage-Hilfe — sichtbar in der Zeile.
    expect(row.textContent).toContain('Begründung des Agenten')
    expect(row.textContent).toContain(pending.context)

    fireEvent.click(within(row).getByRole('button', { name: 'Freigeben' }))

    await waitFor(() => {
      expect(triageBodies).toEqual([{ action: 'approve', fact: pending.fact }])
    })
    await waitFor(() => {
      expect(listCalls).toBeGreaterThanOrEqual(2)
    })
    expect(notify.success).toHaveBeenCalledWith('Erinnerung freigegeben.')
  })

  it('Ablehnen mit Notiz ruft POST triage mit reject + Notiz', async () => {
    const pending = memory({ id: 'm2', context: null })
    let listCalls = 0
    const triageBodies: unknown[] = []
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => {
        listCalls += 1
        return jsonResponse(listCalls === 1 ? [pending] : [{ ...pending, status: 'rejected' }])
      },
      [`POST ${WS_PREFIX}/agents/a1/memories/m2/triage`]: (init) => {
        triageBodies.push(JSON.parse(String(init?.body)))
        return jsonResponse({ ...pending, status: 'rejected', triage_note: 'Nicht relevant.' })
      },
    })

    renderSection()

    const row = await screen.findByTestId('memory-pending-row')
    fireEvent.click(within(row).getByRole('button', { name: 'Ablehnen' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Notiz (optional)'), {
      target: { value: 'Nicht relevant.' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Ablehnen' }))

    await waitFor(() => {
      expect(triageBodies).toEqual([{ action: 'reject', note: 'Nicht relevant.' }])
    })
    expect(notify.success).toHaveBeenCalledWith('Vorschlag abgelehnt.')
  })

  it('aktive Liste zeigt das Nutzungs-Log', async () => {
    const active = memory({
      id: 'm3',
      status: 'active',
      context: null,
      retrieval_count: 4,
      last_retrieved_at: '2026-07-10T12:00:00Z',
    })
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => jsonResponse([active]),
    })

    renderSection()

    expect(await screen.findByText(active.fact)).toBeInTheDocument()
    expect(screen.getByText('4× abgerufen, zuletzt 2026-07-10T12:00:00Z')).toBeInTheDocument()
  })

  it('zeigt "noch nie abgerufen" ohne Retrieval-Historie', async () => {
    const active = memory({ id: 'm3b', status: 'active', context: null })
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => jsonResponse([active]),
    })

    renderSection()

    expect(await screen.findByText('noch nie abgerufen')).toBeInTheDocument()
  })

  it('Einzel-Löschen mit Confirm feuert DELETE', async () => {
    const active = memory({ id: 'm4', status: 'active', context: null })
    let listCalls = 0
    let deleteCalls = 0
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => {
        listCalls += 1
        return jsonResponse(listCalls === 1 ? [active] : [])
      },
      [`DELETE ${WS_PREFIX}/agents/a1/memories/m4`]: () => {
        deleteCalls += 1
        return new Response(null, { status: 204 })
      },
    })

    renderSection()

    expect(await screen.findByText(active.fact)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Erinnerung löschen' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Endgültig löschen' }))

    await waitFor(() => {
      expect(deleteCalls).toBe(1)
    })
    await waitFor(() => {
      expect(listCalls).toBeGreaterThanOrEqual(2)
    })
    expect(notify.success).toHaveBeenCalledWith('Erinnerung gelöscht.')
  })

  it('zeigt den Leerzustand ohne Erinnerungen', async () => {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => jsonResponse([]),
    })

    renderSection()

    expect(await screen.findByText('Noch keine Erinnerungen')).toBeInTheDocument()
    expect(
      screen.getByText('Dieser Agent hat bisher nichts gespeichert.'),
    ).toBeInTheDocument()
  })

  it('eingeklappte Rejected-Liste zeigt Notiz und ist einzeln endgültig löschbar', async () => {
    const rejected = memory({
      id: 'm5',
      status: 'rejected',
      context: null,
      triage_note: 'Nicht relevant fuer diesen Agenten.',
    })
    let listCalls = 0
    let deleteCalls = 0
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => {
        listCalls += 1
        return jsonResponse(listCalls === 1 ? [rejected] : [])
      },
      [`DELETE ${WS_PREFIX}/agents/a1/memories/m5`]: () => {
        deleteCalls += 1
        return new Response(null, { status: 204 })
      },
    })

    renderSection()

    const toggle = await screen.findByRole('button', { name: '1 abgelehnte Erinnerung' })
    expect(screen.queryByText('Nicht relevant fuer diesen Agenten.')).not.toBeInTheDocument()

    fireEvent.click(toggle)

    expect(
      screen.getByText('Nicht relevant fuer diesen Agenten.', { exact: false }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Erinnerung löschen' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Endgültig löschen' }))

    await waitFor(() => {
      expect(deleteCalls).toBe(1)
    })
  })
})
