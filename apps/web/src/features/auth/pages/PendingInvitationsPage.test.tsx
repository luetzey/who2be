import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { MemoryRouter, Route, Routes, useParams, useSearchParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { RequireAuth } from '@/auth/RequireAuth'
import { SessionContext } from '@/auth/session-context'
import i18n from '@/i18n'
import { notify } from '@/lib/feedback'

import { PendingInvitationsPage } from './PendingInvitationsPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-home',
  organizations: [],
  has_password: true,
}
const authedSession = {
  access_token: 'jwt',
  user: { id: 'u1' },
} as unknown as Session
const invitedSession = {
  access_token: 'jwt',
  user: { id: 'u1', invited_at: '2026-10-01T10:00:00Z' },
} as unknown as Session

const PENDING = [
  {
    id: '11111111-1111-4111-8111-111111111111',
    workspace_id: 'ws-acme',
    workspace_name: 'Acme Research',
    role: 'editor',
    expires_at: '2026-10-08T10:00:00Z',
    created_at: '2026-10-01T10:00:00Z',
  },
  {
    id: '22222222-2222-4222-8222-222222222222',
    workspace_id: 'ws-beta',
    workspace_name: 'Beta Lab',
    role: 'viewer',
    expires_at: '2026-10-08T10:00:00Z',
    created_at: '2026-10-01T10:00:00Z',
  },
]

interface RecordedCall {
  url: string
  method: string
  body: unknown
}

function json(status: number, payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function problem(status: number, reason: string, detail = 'SERVERTEXT-NICHT-ANZEIGEN') {
  return new Response(JSON.stringify({ detail, reason }), {
    status,
    headers: { 'content-type': 'application/problem+json' },
  })
}

/** Zeichnet jeden Request auf und antwortet je Methode + Pfad. */
function recordFetch(
  calls: RecordedCall[],
  respond: (method: string, path: string) => Response,
) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      calls.push({ url, method, body: init?.body ?? null })
      return respond(method, new URL(url, 'http://x').pathname)
    }),
  )
}

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

function renderPage(
  session: Session | null,
  meValue: Me | null = me,
  refreshMe: () => Promise<void> = vi.fn(async () => {}),
) {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me: meValue,
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe,
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/invitations']}>
          <Routes>
            {/* Wie in routes.tsx: die Seite haengt hinter RequireAuth. */}
            <Route element={<RequireAuth />}>
              <Route path="/invitations" element={<PendingInvitationsPage />} />
            </Route>
            <Route path="/w/:workspaceId/dashboard" element={<DashboardMarker />} />
            <Route path="/login" element={<LoginMarker />} />
            <Route path="/onboarding/set-password" element={<SetPasswordMarker />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

/** Kein Request darf einen Einladungs-Token tragen — weder in URL noch Body. */
function expectNoInvitationToken(calls: RecordedCall[]) {
  for (const call of calls) {
    expect(call.url).not.toMatch(/token/i)
    expect(new URL(call.url, 'http://x').pathname).not.toBe('/v1/invitations/accept')
    expect(call.body).toBeNull()
  }
}

afterEach(async () => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  await i18n.changeLanguage('de')
})

describe('PendingInvitationsPage', () => {
  it('listet offene Einladungen mit Workspace-Name und Rolle', async () => {
    const calls: RecordedCall[] = []
    recordFetch(calls, () => json(200, PENDING))

    renderPage(authedSession)

    const items = await screen.findAllByTestId('pending-invitation')
    expect(items).toHaveLength(2)
    expect(within(items[0]).getByText('Acme Research')).toBeInTheDocument()
    expect(within(items[0]).getByText(/Rolle: Editor/)).toBeInTheDocument()
    expect(within(items[1]).getByText('Beta Lab')).toBeInTheDocument()
    expect(within(items[1]).getByText(/Rolle: Viewer/)).toBeInTheDocument()

    expect(calls).toHaveLength(1)
    expect(calls[0].method).toBe('GET')
    expect(new URL(calls[0].url, 'http://x').pathname).toBe('/v1/invitations/pending')
    expectNoInvitationToken(calls)
  })

  it('nimmt per Klick genau ueber POST /v1/invitations/pending/{id}/accept an und leitet weiter', async () => {
    const calls: RecordedCall[] = []
    recordFetch(calls, (method) =>
      method === 'POST' ? json(200, { workspace_id: 'ws-acme' }) : json(200, PENDING),
    )
    const refreshMe = vi.fn(async () => {})

    renderPage(authedSession, me, refreshMe)

    fireEvent.click(
      await screen.findByRole('button', { name: 'Einladung in Acme Research annehmen' }),
    )

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-acme')).toBeInTheDocument()
    })
    const posts = calls.filter((call) => call.method === 'POST')
    expect(posts).toHaveLength(1)
    expect(new URL(posts[0].url, 'http://x').pathname).toBe(
      `/v1/invitations/pending/${PENDING[0].id}/accept`,
    )
    expect(notify.success).toHaveBeenCalledWith('Einladung angenommen.')
    // Der Workspace-Umschalter kennt die neue Mitgliedschaft erst nach Re-Fetch.
    expect(refreshMe).toHaveBeenCalled()
    expectNoInvitationToken(calls)
  })

  it('zeigt den Leer-Zustand ohne offene Einladungen', async () => {
    recordFetch([], () => json(200, []))

    renderPage(authedSession)

    expect(await screen.findByText('Keine offenen Einladungen')).toBeInTheDocument()
    expect(screen.queryByTestId('pending-invitation')).toBeNull()
  })

  describe.each([
    {
      lang: 'de',
      title: 'E-Mail-Adresse bestätigen',
      text: 'Bestätige zuerst die E-Mail-Adresse deines Kontos, dann kannst du die Einladung annehmen.',
    },
    {
      lang: 'en',
      title: 'Confirm your email address',
      text: "Confirm your account's email address first, then you can accept the invitation.",
    },
  ])('403 invitation_email_unconfirmed ($lang)', ({ lang, title, text }) => {
    it('zeigt den uebersetzten Hinweis statt des Servertexts', async () => {
      await i18n.changeLanguage(lang)
      recordFetch([], () => problem(403, 'invitation_email_unconfirmed'))

      renderPage(authedSession)

      expect(await screen.findByText(text)).toBeInTheDocument()
      expect(screen.getByText(title)).toBeInTheDocument()
      expect(screen.queryByText('SERVERTEXT-NICHT-ANZEIGEN')).toBeNull()
    })
  })

  it('zeigt bei 410 auf die Annahme die Ablauf-Meldung und laedt die Liste neu', async () => {
    const calls: RecordedCall[] = []
    let gets = 0
    recordFetch(calls, (method) => {
      if (method === 'POST') return problem(410, 'invitation_no_longer_valid')
      gets += 1
      return json(200, gets === 1 ? PENDING : PENDING.slice(1))
    })

    renderPage(authedSession)

    fireEvent.click(
      await screen.findByRole('button', { name: 'Einladung in Acme Research annehmen' }),
    )

    expect(await screen.findByText(/abgelaufen/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getAllByTestId('pending-invitation')).toHaveLength(1)
    })
    expect(screen.queryByText('Acme Research')).toBeNull()
  })

  it('schickt nicht eingeloggte Nutzer zum Login mit Ruecksprung auf /invitations', () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)

    renderPage(null, null)

    expect(screen.getByText('LOGIN next=/invitations')).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('laesst ein Neukonto aus der Einladungsmail zuerst ein Passwort setzen', async () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)

    renderPage(invitedSession, { ...me, has_password: false })

    expect(await screen.findByText('SETPW next=/invitations')).toBeInTheDocument()
    // Keine Einladungsliste, bevor das Konto ein Passwort hat.
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('fuehrt nach dem Passwort-Setzen nicht im Kreis: frisches me zeigt die Liste', async () => {
    recordFetch([], () => json(200, PENDING))

    // Snapshot ist veraltet (`has_password=false`), der Re-Fetch kennt das
    // inzwischen gesetzte Passwort.
    function Harness() {
      const [meValue, setMeValue] = useState<Me>({ ...me, has_password: false })
      const refreshMe = async () => setMeValue({ ...me, has_password: true })
      return (
        <SessionContext.Provider
          value={{
            session: invitedSession,
            me: meValue,
            sessionLoaded: true,
            signIn: vi.fn(),
            signOut: vi.fn(),
            refreshMe,
          }}
        >
          <AuthTokenProvider>
            <MemoryRouter initialEntries={['/invitations']}>
              <Routes>
                <Route path="/invitations" element={<PendingInvitationsPage />} />
                <Route path="/onboarding/set-password" element={<SetPasswordMarker />} />
              </Routes>
            </MemoryRouter>
          </AuthTokenProvider>
        </SessionContext.Provider>
      )
    }
    render(<Harness />)

    expect(await screen.findAllByTestId('pending-invitation')).toHaveLength(2)
    expect(screen.queryByText(/SETPW next=/)).toBeNull()
  })

  it('laesst Konten ohne Passwort, die nicht per Einladung kamen (OAuth), direkt durch', async () => {
    recordFetch([], () => json(200, PENDING))

    renderPage(authedSession, { ...me, has_password: false })

    expect(await screen.findAllByTestId('pending-invitation')).toHaveLength(2)
  })
})
