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

const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
  has_password: true,
}
const meNoPassword: Me = { ...me, has_password: false }
const authedSession = { access_token: 'jwt' } as unknown as Session

function DashboardMarker() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  return <div>DASHBOARD {workspaceId}</div>
}

function LoginMarker() {
  const [params] = useSearchParams()
  return <div>LOGIN next={params.get('next')}</div>
}

function SetPasswordMarker() {
  const [params] = useSearchParams()
  return <div>SETPW next={params.get('next')}</div>
}

function renderAccept(
  session: Session | null,
  initialEntry = '/invitations/abc123/accept',
  meValue: Me | null = me,
) {
  return render(
    <SessionContext.Provider
      value={{ session, me: meValue, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/invitations/:token/accept" element={<InvitationAcceptPage />} />
            <Route path="/w/:workspaceId/dashboard" element={<DashboardMarker />} />
            <Route path="/login" element={<LoginMarker />} />
            <Route path="/onboarding/set-password" element={<SetPasswordMarker />} />
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

  it('zeigt Loading-State, solange Session da, me aber noch null ist', () => {
    // Hash-Session ist etabliert, `/v1/me` antwortet noch nicht. Ohne diesen
    // Branch wuerde der `has_password`-Check `me === null` als „kein Passwort"
    // missverstehen oder der Auto-Accept ohne `me`-Daten feuern.
    renderAccept(authedSession, '/invitations/magic-tok/accept?via=magic', null)

    expect(screen.getByText('Login wird abgeschlossen…')).toBeInTheDocument()
    expect(screen.queryByText(/LOGIN next=/)).toBeNull()
    expect(screen.queryByText(/SETPW next=/)).toBeNull()
  })

  it('akzeptiert magic-link automatisch ohne Klick', async () => {
    const calls: Array<{ url: string; method: string }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({ url: String(input), method: init?.method ?? 'GET' })
        return new Response(JSON.stringify({ workspace_id: 'ws-7' }), { status: 200 })
      }),
    )

    renderAccept(authedSession, '/invitations/magic-tok/accept?via=magic')

    // Microcopy signalisiert den automatischen Flow — kein „Annehmen"-Button.
    expect(screen.getByText('Login wird abgeschlossen…')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Einladung annehmen' })).toBeNull()

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-7')).toBeInTheDocument()
    })
    expect(calls[0].url).toContain('/v1/invitations/magic-tok/accept')
    expect(calls[0].method).toBe('POST')
  })

  it('leitet Magic-Link-User ohne Passwort auf Set-Password um', () => {
    renderAccept(authedSession, '/invitations/magic-tok/accept?via=magic', meNoPassword)

    expect(
      screen.getByText('SETPW next=/invitations/magic-tok/accept?via=magic'),
    ).toBeInTheDocument()
  })

  it('akzeptiert Magic-Link automatisch, wenn Passwort bereits gesetzt ist', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ workspace_id: 'ws-3' }), { status: 200 })),
    )

    renderAccept(authedSession, '/invitations/magic-tok/accept?via=magic', me)

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-3')).toBeInTheDocument()
    })
  })

  it('zeigt Email-Mismatch-Microcopy bei 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{}', { status: 403 })),
    )

    renderAccept(authedSession, '/invitations/wrong-acct/accept?via=magic')

    await waitFor(() => {
      expect(screen.getByText(/andere Email-Adresse/i)).toBeInTheDocument()
    })
  })
})
