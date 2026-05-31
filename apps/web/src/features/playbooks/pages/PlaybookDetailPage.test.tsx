import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'
import { PlaybookDetailPage } from './PlaybookDetailPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel mocken — sie ist in jsdom nicht mountfaehig.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}
const WS_PREFIX = '/v1/workspaces/ws-1'

interface PlaybookShape {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  current_version: number
  type: string
  tags: string[]
  triggers: string | null
  content: {
    description: string
    body: string
    type: string
    tags: string[]
    triggers: string | null
  }
  created_at: string
  updated_at: string
}

function playbook(version: number, body: string): PlaybookShape {
  return {
    id: 'pb1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Coach',
    current_version: version,
    type: 'workflow',
    tags: ['coaching'],
    triggers: null,
    content: {
      description: 'd',
      body,
      type: 'workflow',
      tags: ['coaching'],
      triggers: null,
    },
    created_at: '2026-05-24T12:00:00Z',
    updated_at: '2026-05-24T12:00:00Z',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('PlaybookDetailPage', () => {
  it('Auto-Save: aendert man Felder, geht ein PATCH-Draft raus und kein PUT', async () => {
    const v1 = {
      version: 1,
      status: 'draft',
      content: playbook(1, 'b1').content,
      created_by: 'o1',
      created_at: 't1',
    }
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbook(1, 'b1')),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () => jsonResponse([v1]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/usages`]: () => jsonResponse([]),
    }

    const patchCalls: Array<{ url: string; body: unknown }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      const pathname = new URL(url).pathname
      if (method === 'PATCH' && pathname.endsWith('/playbooks/pb1/draft')) {
        patchCalls.push({ url, body: JSON.parse(init?.body as string) })
        return jsonResponse(playbook(1, 'b1'))
      }
      const key = `${method} ${pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    })
    // Save-Button gibt es nicht mehr.
    expect(
      screen.queryByRole('button', { name: 'Neue Version speichern' }),
    ).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Coach v2' } })
    // Auto-Save-Debounce ist 1500 ms — Real-Timer warten ist robuster als
    // FakeTimers (die unter Vitest in Kombination mit dem React-Concurrent-
    // Renderer manchmal pending Promises blockieren).
    await waitFor(
      () => {
        expect(patchCalls.length).toBeGreaterThanOrEqual(1)
      },
      { timeout: 3000 },
    )
    expect(
      (patchCalls[patchCalls.length - 1].body as { name: string }).name,
    ).toBe('Coach v2')
    const putCalls = fetchMock.mock.calls.filter(
      (call) => (call[1] as RequestInit | undefined)?.method === 'PUT',
    )
    expect(putCalls).toHaveLength(0)
  }, 10_000)

  it('zeigt im "Verwendet in"-Block die Personas aus /usages und faellt auf EmptyState zurueck, wenn keine vorhanden sind', async () => {
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbook(1, 'b1')),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () =>
        jsonResponse([
          { version: 1, content: playbook(1, 'b1').content, created_by: 'o1', created_at: 't1' },
        ]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/usages`]: () =>
        jsonResponse([
          { persona_id: 'per1', persona_name: 'Coach Persona' },
          { persona_id: 'per2', persona_name: 'Onboarding Persona' },
        ]),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const key = `${method} ${new URL(String(input)).pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('Verwendet in')).toBeInTheDocument()
    })
    expect(screen.getByText('Coach Persona')).toBeInTheDocument()
    expect(screen.getByText('Onboarding Persona')).toBeInTheDocument()
  })

  it('rendert vorhandene Komma-Trigger als Pills statt als Komma-Text', async () => {
    const playbookWithTriggers = {
      ...playbook(1, 'b1'),
      triggers: '"passwort vergessen", "reset link"',
      content: {
        ...playbook(1, 'b1').content,
        triggers: '"passwort vergessen", "reset link"',
      },
    }
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbookWithTriggers),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () =>
        jsonResponse([
          {
            version: 1,
            content: playbookWithTriggers.content,
            created_by: 'o1',
            created_at: 't1',
          },
        ]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/usages`]: () => jsonResponse([]),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const key = `${method} ${new URL(String(input)).pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    const cluster = await screen.findByRole('list', { name: 'Trigger-Liste' })
    expect(cluster).toBeInTheDocument()
    // Anfuehrungszeichen sind in der UI komplett geschluckt.
    expect(cluster.textContent ?? '').not.toContain('"')
    // Beide Pills sind als eigene Listitem-Pills da.
    const items = screen.getAllByRole('listitem')
    const itemTexts = items.map((node) => node.textContent ?? '')
    expect(itemTexts).toEqual(
      expect.arrayContaining(['passwort vergessen', 'reset link']),
    )
  })

  it('zeigt einen EmptyState wenn /usages ein 404 zurueckgibt', async () => {
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbook(1, 'b1')),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () =>
        jsonResponse([
          { version: 1, content: playbook(1, 'b1').content, created_by: 'o1', created_at: 't1' },
        ]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      const pathname = new URL(url).pathname
      if (pathname.endsWith('/usages')) {
        return new Response('', { status: 404 })
      }
      const key = `${method} ${pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('Noch in keiner Persona verwendet')).toBeInTheDocument()
    })
  })
})
