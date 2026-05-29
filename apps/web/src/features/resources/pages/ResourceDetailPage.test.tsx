import type { Session } from '@supabase/supabase-js'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel braucht im jsdom nicht real zu mounten — Page-Test
// pruegt nur den Wrapper-Vertrag (Card, Usages-Block, EmptyState).
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

import { ResourceDetailPage } from './ResourceDetailPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'o1',
      name: 'Org',
      slug: 'org',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'admin' }],
    },
  ],
}
const WS_PREFIX = '/v1/workspaces/ws-1'

function resource() {
  return {
    id: 'r1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Onboarding',
    current_version: 1,
    content: { description: 'd', blocks: [] },
    created_at: 't',
    updated_at: 't',
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

function renderPage(handler: (url: string, method: string) => Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(new URL(String(input)).pathname, init?.method ?? 'GET'),
    ),
  )
  render(
    <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/resources/r1']}>
          <Routes>
            <Route path="/w/:workspaceId/resources/:id" element={<ResourceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

describe('ResourceDetailPage', () => {
  it('zeigt den "Verlinkt in"-Block mit Playbook-Namen und Block-Count', async () => {
    renderPage((path) => {
      if (path === `${WS_PREFIX}/resources/r1`) return jsonResponse(resource())
      if (path === `${WS_PREFIX}/resources/r1/versions`)
        return jsonResponse([
          { version: 1, content: { description: 'd', blocks: [] }, created_by: 'o1', created_at: 't' },
        ])
      if (path === `${WS_PREFIX}/resources/r1/usages`)
        return jsonResponse([
          { playbook_id: 'pb1', playbook_name: 'Coach', block_count: 1 },
          { playbook_id: 'pb2', playbook_name: 'Onboarding-Flow', block_count: 3 },
        ])
      throw new Error(`Unmocked ${path}`)
    })

    await waitFor(() => {
      expect(screen.getByText('Verlinkt in')).toBeInTheDocument()
    })
    expect(screen.getByText('Coach')).toBeInTheDocument()
    expect(screen.getByText('Onboarding-Flow')).toBeInTheDocument()
    expect(screen.getByText('1 Block')).toBeInTheDocument()
    expect(screen.getByText('3 Bloecke')).toBeInTheDocument()
  })

  it('zeigt einen EmptyState, wenn /usages 404 zurueckgibt', async () => {
    renderPage((path) => {
      if (path === `${WS_PREFIX}/resources/r1`) return jsonResponse(resource())
      if (path === `${WS_PREFIX}/resources/r1/versions`)
        return jsonResponse([
          { version: 1, content: { description: 'd', blocks: [] }, created_by: 'o1', created_at: 't' },
        ])
      if (path === `${WS_PREFIX}/resources/r1/usages`)
        return new Response('', { status: 404 })
      throw new Error(`Unmocked ${path}`)
    })

    await waitFor(() => {
      expect(screen.getByText('Noch in keinem Playbook verwendet')).toBeInTheDocument()
    })
  })
})
