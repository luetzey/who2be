import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'
import { PersonaDetailPage } from './PersonaDetailPage'

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

interface PersonaShape {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  current_version: number
  content: { description: string; system_prompt: string; traits: string[] }
  created_at: string
  updated_at: string
}

function persona(version: number, systemPrompt: string): PersonaShape {
  return {
    id: 'p1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Coach',
    current_version: version,
    content: { description: 'd', system_prompt: systemPrompt, traits: [] },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

function route(method: string, url: string): string {
  return `${method} ${url}`
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('PersonaDetailPage', () => {
  it('zeigt eine neue Version, nachdem der Editor gespeichert wurde', async () => {
    const v1 = { version: 1, content: persona(1, 's1').content, created_by: 'o1', created_at: 't1' }
    const v2 = { version: 2, content: persona(2, 's2').content, created_by: 'o1', created_at: 't2' }

    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(persona(1, 's1')),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([v1]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([]),
    }

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      if (method === 'PUT' && url.endsWith(`${WS_PREFIX}/personas/p1`)) {
        handlers[route('GET', `${WS_PREFIX}/personas/p1`)] = () => jsonResponse(persona(2, 's2'))
        handlers[route('GET', `${WS_PREFIX}/personas/p1/versions`)] = () => jsonResponse([v1, v2])
        return jsonResponse(persona(2, 's2'))
      }
      const key = route(method, new URL(url).pathname)
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
          <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('Aktuelle Version: 1')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('System-Prompt'), { target: { value: 's2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Neue Version speichern' }))

    await waitFor(() => {
      expect(screen.getByText('Aktuelle Version: 2')).toBeInTheDocument()
    })
    expect(screen.getByText(/v2 —/)).toBeInTheDocument()
    expect(notify.success).toHaveBeenCalledWith('Gespeichert — neue Version erstellt.')
  })

  it('verknuepft Playbooks via PUT auf /personas/:id/playbooks', async () => {
    const pb1 = {
      id: 'pb1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Coaching',
      current_version: 1,
      type: 'workflow',
      tags: [],
      triggers: null,
      content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
      created_at: 't',
      updated_at: 't',
    }
    const pb2 = { ...pb1, id: 'pb2', name: 'Brainstorming' }

    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(persona(1, 's1')),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([pb1]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([pb1, pb2]),
    }

    const putCalls: Array<{ url: string; body: unknown }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      if (method === 'PUT' && url.endsWith(`${WS_PREFIX}/personas/p1/playbooks`)) {
        putCalls.push({ url, body: JSON.parse(init?.body as string) })
        return jsonResponse([pb1, pb2])
      }
      const key = route(method, new URL(url).pathname)
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
          <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    const checkbox2 = await screen.findByLabelText('Brainstorming')
    fireEvent.click(checkbox2)
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen speichern' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Verknüpfungen gespeichert.')
    })
    expect(putCalls).toHaveLength(1)
    expect(putCalls[0].body).toEqual({ playbook_ids: ['pb1', 'pb2'] })
  })
})
