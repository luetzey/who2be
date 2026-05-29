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
  it('zeigt eine neue Version, nachdem der Editor gespeichert wurde', async () => {
    const v1 = {
      version: 1,
      content: playbook(1, 'b1').content,
      created_by: 'o1',
      created_at: 't1',
    }
    const v2 = {
      version: 2,
      content: playbook(2, 'b2').content,
      created_by: 'o1',
      created_at: 't2',
    }

    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbook(1, 'b1')),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () => jsonResponse([v1]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/usages`]: () => jsonResponse([]),
    }

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      if (method === 'PUT' && url.endsWith(`${WS_PREFIX}/playbooks/pb1`)) {
        handlers[`GET ${WS_PREFIX}/playbooks/pb1`] = () => jsonResponse(playbook(2, 'b2'))
        handlers[`GET ${WS_PREFIX}/playbooks/pb1/versions`] = () => jsonResponse([v1, v2])
        return jsonResponse(playbook(2, 'b2'))
      }
      const key = `${method} ${new URL(url).pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
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
      expect(screen.getByText('Aktuelle Version: 1')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Inhalt'), { target: { value: 'b2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Neue Version speichern' }))

    await waitFor(() => {
      expect(screen.getByText('Aktuelle Version: 2')).toBeInTheDocument()
    })
    expect(screen.getByText(/v2 —/)).toBeInTheDocument()
    expect(notify.success).toHaveBeenCalledWith('Gespeichert — neue Version erstellt.')
  })

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
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
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
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
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
