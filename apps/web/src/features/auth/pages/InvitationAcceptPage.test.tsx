import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useParams, useSearchParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { InvitationAcceptPage } from './InvitationAcceptPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }
const authedSession = { access_token: 'jwt' } as unknown as Session

function DashboardMarker() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  return <div>DASHBOARD {workspaceId}</div>
}

function LoginMarker() {
  const [params] = useSearchParams()
  return <div>LOGIN next={params.get('next')}</div>
}

function renderAccept(session: Session | null) {
  return render(
    <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/invitations/abc123/accept']}>
          <Routes>
            <Route path="/invitations/:token/accept" element={<InvitationAcceptPage />} />
            <Route path="/w/:workspaceId/dashboard" element={<DashboardMarker />} />
            <Route path="/login" element={<LoginMarker />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
})

describe('InvitationAcceptPage', () => {
  it('nimmt die Einladung an und leitet ins neue Workspace-Dashboard', async () => {
    const calls: Array<{ url: string; method: string }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({ url: String(input), method: init?.method ?? 'GET' })
        return new Response(JSON.stringify({ workspace_id: 'ws-9' }), { status: 200 })
      }),
    )

    renderAccept(authedSession)

    fireEvent.click(screen.getByRole('button', { name: 'Einladung annehmen' }))

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-9')).toBeInTheDocument()
    })
    expect(calls[0].url).toContain('/v1/invitations/abc123/accept')
    expect(calls[0].method).toBe('POST')
    expect(notify.success).toHaveBeenCalledWith('Einladung angenommen.')
  })

  it('zeigt eine klare Meldung bei abgelaufener Einladung (410)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{}', { status: 410 })),
    )

    renderAccept(authedSession)

    fireEvent.click(screen.getByRole('button', { name: 'Einladung annehmen' }))

    await waitFor(() => {
      expect(screen.getByText(/abgelaufen/i)).toBeInTheDocument()
    })
  })

  it('schickt nicht authentifizierte Nutzer zum Login mit next-Parameter', () => {
    renderAccept(null)

    expect(
      screen.getByText('LOGIN next=/invitations/abc123/accept'),
    ).toBeInTheDocument()
  })
})
