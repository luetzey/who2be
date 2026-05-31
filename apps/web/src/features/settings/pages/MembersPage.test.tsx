import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { MembersPage } from './MembersPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(role: WorkspaceRole): Me {
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
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

function renderMembers(role: WorkspaceRole = 'admin') {
  return render(
    <SessionContext.Provider
      value={{ session, me: buildMe(role), signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/settings/members']}>
          <Routes>
            <Route path="/w/:workspaceId/settings/members" element={<MembersPage />} />
            <Route path="/w/:workspaceId/dashboard" element={<div>DASHBOARD</div>} />
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

describe('MembersPage', () => {
  it('listet die Mitglieder des Workspace', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/members')) {
          return jsonResponse([
            {
              user_id: 'm1',
              email: 'coder@who2be.dev',
              role: 'editor',
              joined_at: '2026-05-01T10:00:00Z',
            },
          ])
        }
        return jsonResponse([])
      }),
    )

    renderMembers('admin')

    await waitFor(() => {
      expect(screen.getByText('coder@who2be.dev')).toBeInTheDocument()
    })
  })

  it('verschickt eine Einladung via POST /invitations', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'
        if (method === 'POST' && url.includes('/invitations')) {
          bodies.push(JSON.parse(init?.body as string))
          return jsonResponse(
            {
              id: 'i1',
              email: 'neu@who2be.dev',
              role: 'editor',
              expires_at: '2026-06-01T10:00:00Z',
              created_at: '2026-05-29T10:00:00Z',
              token: 'inv-token',
            },
            201,
          )
        }
        return jsonResponse([])
      }),
    )

    renderMembers('admin')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Einladen' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Einladen' }))

    await waitFor(() => {
      expect(bodies).toHaveLength(1)
    })
    expect(bodies[0]).toEqual({ email: 'neu@who2be.dev', role: 'editor' })
    expect(notify.success).toHaveBeenCalledWith('Einladung an neu@who2be.dev verschickt.')
  })

  it('wirft Editoren aufs Dashboard zurück', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse([])))

    renderMembers('editor')

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: 'Mitglieder' })).toBeNull()
    expect(notify.error).toHaveBeenCalledWith('Diese Seite ist nur für Admins.')
  })
})
