import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent, type Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { AgentsPage } from './AgentsPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

const WS_PREFIX = '/v1/workspaces/ws-1'

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
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
    ...overrides,
  }
}

function renderPage() {
  return render(
    <SessionContext.Provider
      value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents']}>
          <Routes>
            <Route path="/w/:workspaceId/agents" element={<AgentsPage />} />
            <Route
              path="/w/:workspaceId/agents/:id"
              element={<div>Agent-Detail-Route</div>}
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

describe('AgentsPage', () => {
  it('listet Agents mit Status- und Unvollstaendig-Badges', async () => {
    const complete = agent()
    const incomplete = agent({
      id: 'a2',
      name: 'Leere Hülle',
      persona_id: null,
      system_prompt_template_id: null,
      status: 'disabled',
      persona_active: false,
      activatable: false,
      missing: ['persona', 'template'],
    })
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify([complete, incomplete]), { status: 200 }),
        ),
    )

    renderPage()

    expect(await screen.findByText('Carla Bot')).toBeInTheDocument()
    expect(screen.getByText('Leere Hülle')).toBeInTheDocument()
    // Aktivierbarer Agent: Status-Badge "Aktiv", kein "Unvollständig".
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    // Unvollstaendiger Agent: beide Badges.
    expect(screen.getByText('Deaktiviert')).toBeInTheDocument()
    expect(screen.getByText('Unvollständig')).toBeInTheDocument()
  })

  it('zeigt den Empty-State, wenn keine Agents existieren', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })),
    )

    renderPage()

    expect(await screen.findByText('Noch keine Agents')).toBeInTheDocument()
    expect(screen.getByTestId('new-agent-empty')).toBeEnabled()
  })

  it('zeigt einen ErrorAlert, wenn die Liste nicht geladen werden kann', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('kaputt', { status: 500 })),
    )

    renderPage()

    expect(await screen.findByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
  })

  it('legt per Klick einen leeren Agent an und navigiert zur Detailseite', async () => {
    const postCalls: Array<{ body: unknown }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        const pathname = new URL(String(input)).pathname
        if (method === 'GET' && pathname === `${WS_PREFIX}/agents`) {
          return new Response(JSON.stringify([]), { status: 200 })
        }
        if (method === 'POST' && pathname === `${WS_PREFIX}/agents`) {
          postCalls.push({ body: JSON.parse(init?.body as string) })
          return new Response(JSON.stringify(agent({ id: 'a9', name: 'Neuer Agent' })), {
            status: 200,
          })
        }
        throw new Error(`Unmocked ${method} ${pathname}`)
      }),
    )

    renderPage()

    fireEvent.click(await screen.findByTestId('new-agent-empty'))

    await waitFor(() => {
      expect(screen.getByText('Agent-Detail-Route')).toBeInTheDocument()
    })
    expect(postCalls).toHaveLength(1)
    expect(postCalls[0].body).toEqual({ name: 'Neuer Agent' })
    expect(notify.success).toHaveBeenCalledWith(
      'Agent angelegt — jetzt Persona und Systemprompt zuweisen.',
    )
  })

  it('meldet einen Fehler-Toast, wenn das Anlegen fehlschlaegt, und bleibt auf der Liste', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        if (method === 'POST') {
          return new Response(JSON.stringify({ detail: 'Anlegen kaputt.' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        return new Response(JSON.stringify([]), { status: 200 })
      }),
    )

    renderPage()

    fireEvent.click(await screen.findByTestId('new-agent-empty'))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Anlegen kaputt.')
    })
    expect(screen.queryByText('Agent-Detail-Route')).not.toBeInTheDocument()
    // Button wird nach dem Fehler wieder freigegeben.
    expect(screen.getByTestId('new-agent-empty')).toBeEnabled()
  })
})
