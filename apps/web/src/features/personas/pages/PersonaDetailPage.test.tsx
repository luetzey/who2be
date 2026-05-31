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

// BlockNote-Insel mocken — sie kann nicht in jsdom mounten (ProseMirror).
// Damit der Persona-Editor (BlockNote-Profil) in diesem Page-Test sauber
// rendert, stuben wir die Insel-Module + den Theme-Context, der die
// Insel hochzieht.
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
  it('Auto-Save: Aenderungen feuern einen PATCH-Draft, kein PUT mehr', async () => {
    const v1 = {
      version: 1,
      status: 'draft',
      content: persona(1, 's1').content,
      created_by: 'o1',
      created_at: 't1',
    }
    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(persona(1, 's1')),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([v1]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([]),
    }

    const patchCalls: Array<{ url: string; body: unknown }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      const pathname = new URL(url).pathname
      if (method === 'PATCH' && pathname.endsWith('/personas/p1/draft')) {
        patchCalls.push({ url, body: JSON.parse(init?.body as string) })
        return jsonResponse(persona(1, 's1'))
      }
      const key = route(method, pathname)
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
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('button', { name: 'Neue Version speichern' }),
    ).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Coach v2' } })
    await waitFor(
      () => {
        expect(patchCalls.length).toBeGreaterThanOrEqual(1)
      },
      { timeout: 3000 },
    )
    expect((patchCalls[patchCalls.length - 1].body as { name: string }).name).toBe(
      'Coach v2',
    )
    const putCalls = fetchMock.mock.calls.filter(
      (call) =>
        (call[1] as RequestInit | undefined)?.method === 'PUT' &&
        String(call[0]).endsWith('/personas/p1'),
    )
    expect(putCalls).toHaveLength(0)
  }, 10_000)

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
