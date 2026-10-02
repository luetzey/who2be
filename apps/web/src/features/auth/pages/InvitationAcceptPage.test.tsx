import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import i18n from '@/i18n'
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

interface RecordedCall {
  url: string
  method: string
  body: unknown
}

function recordFetch(
  calls: RecordedCall[],
  respond: () => Response = () =>
    new Response(JSON.stringify({ workspace_id: 'ws-9' }), { status: 200 }),
) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({
        url: String(input),
        method: init?.method ?? 'GET',
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : null,
      })
      return respond()
    }),
  )
}

function problem(status: number, reason: string, detail: string) {
  return () =>
    new Response(JSON.stringify({ detail, reason }), {
      status,
      headers: { 'content-type': 'application/problem+json' },
    })
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

// Zeigt die aktuelle Router-Adresse, damit Tests pruefen koennen, dass das
// Token-Fragment nach dem Lesen aus der Adresszeile verschwunden ist.
function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}${location.hash}`}</div>
}

function renderAccept(
  session: Session | null,
  initialEntry = '/invitations/abc123/accept',
  meValue: Me | null = me,
) {
  return render(
    <SessionContext.Provider
      value={{ session, me: meValue, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <LocationProbe />
          <Routes>
            <Route path="/invitations/accept" element={<InvitationAcceptPage />} />
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

/** Kein aufgezeichneter Request darf den Token in Pfad oder Query tragen. */
function expectTokenNotInAnyUrl(calls: RecordedCall[], token: string) {
  for (const call of calls) {
    expect(call.url).not.toContain(token)
  }
}

afterEach(async () => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  window.sessionStorage.clear()
  await i18n.changeLanguage('de')
})

describe('InvitationAcceptPage', () => {
  it('nimmt einen geteilten Link per Fragment an: ein POST, Token nur im Body, Fragment entfernt', async () => {
    const calls: RecordedCall[] = []
    recordFetch(calls)

    renderAccept(authedSession, '/invitations/accept#token=frag-tok-42')

    // Fragment ist nach dem Lesen aus der Adresse verschwunden.
    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent(/^\/invitations\/accept$/)
    })

    fireEvent.click(screen.getByRole('button', { name: 'Einladung annehmen' }))

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-9')).toBeInTheDocument()
    })
    expect(calls).toHaveLength(1)
    expect(calls[0].method).toBe('POST')
    expect(new URL(calls[0].url, 'http://x').pathname).toBe('/v1/invitations/accept')
    expect(calls[0].body).toEqual({ token: 'frag-tok-42' })
    expectTokenNotInAnyUrl(calls, 'frag-tok-42')
    // Nach erfolgreicher Annahme bleibt nichts zwischengespeichert.
    expect(JSON.stringify({ ...window.sessionStorage })).not.toContain('frag-tok-42')
  })

  it('nimmt die Einladung ueber die Legacy-Route per Body an und leitet ins Dashboard', async () => {
    const calls: RecordedCall[] = []
    recordFetch(calls)

    renderAccept(authedSession)

    fireEvent.click(screen.getByRole('button', { name: 'Einladung annehmen' }))

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-9')).toBeInTheDocument()
    })
    expect(calls).toHaveLength(1)
    expect(calls[0].method).toBe('POST')
    expect(new URL(calls[0].url, 'http://x').pathname).toBe('/v1/invitations/accept')
    expect(calls[0].body).toEqual({ token: 'abc123' })
    expectTokenNotInAnyUrl(calls, 'abc123')
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

  it('schickt nicht authentifizierte Nutzer zum Login, ohne den Token in next', () => {
    renderAccept(null)

    expect(screen.getByText('LOGIN next=/invitations/accept')).toBeInTheDocument()
    expect(screen.getByTestId('location')).not.toHaveTextContent('abc123')
  })

  it('traegt einen Fragment-Token ueber den Login, ohne ihn in eine Query zu legen', async () => {
    // Erster Besuch ohne Session: Token wird gelesen, Login-Redirect ohne Token.
    const first = renderAccept(null, '/invitations/accept#token=frag-login')
    expect(screen.getByText('LOGIN next=/invitations/accept')).toBeInTheDocument()
    expect(screen.getByTestId('location')).not.toHaveTextContent('frag-login')
    first.unmount()

    // Ruecksprung nach dem Login: `next` fuehrt tokenfrei zurueck, die Seite
    // nimmt den zwischengespeicherten Token per Body an.
    const calls: RecordedCall[] = []
    recordFetch(calls)
    renderAccept(authedSession, '/invitations/accept')

    fireEvent.click(screen.getByRole('button', { name: 'Einladung annehmen' }))

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-9')).toBeInTheDocument()
    })
    expect(calls).toHaveLength(1)
    expect(calls[0].body).toEqual({ token: 'frag-login' })
    expectTokenNotInAnyUrl(calls, 'frag-login')
  })

  it('leitet ohne Token auf der neuen Route zur Startseite', () => {
    renderAccept(authedSession, '/invitations/accept')

    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/)
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
    const calls: RecordedCall[] = []
    recordFetch(calls, () =>
      new Response(JSON.stringify({ workspace_id: 'ws-7' }), { status: 200 }),
    )

    renderAccept(authedSession, '/invitations/magic-tok/accept?via=magic')

    // Microcopy signalisiert den automatischen Flow — kein „Annehmen"-Button.
    expect(screen.getByText('Login wird abgeschlossen…')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Einladung annehmen' })).toBeNull()

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD ws-7')).toBeInTheDocument()
    })
    expect(calls).toHaveLength(1)
    expect(new URL(calls[0].url, 'http://x').pathname).toBe('/v1/invitations/accept')
    expect(calls[0].method).toBe('POST')
    expect(calls[0].body).toEqual({ token: 'magic-tok' })
  })

  it('leitet Magic-Link-User ohne Passwort auf Set-Password um, ohne Token in next', () => {
    renderAccept(authedSession, '/invitations/magic-tok/accept?via=magic', meNoPassword)

    expect(
      screen.getByText('SETPW next=/invitations/accept?via=magic'),
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

  describe.each([
    {
      lang: 'de',
      reason: 'invitation_email_required',
      text: 'Diese Einladung lässt sich nur mit einem Konto annehmen, das eine bestätigte E-Mail-Adresse trägt.',
    },
    {
      lang: 'en',
      reason: 'invitation_email_required',
      text: 'This invitation can only be accepted with an account that has a confirmed email address.',
    },
    {
      lang: 'de',
      reason: 'invitation_email_unconfirmed',
      text: 'Bestätige zuerst die E-Mail-Adresse deines Kontos, dann kannst du die Einladung annehmen.',
    },
    {
      lang: 'en',
      reason: 'invitation_email_unconfirmed',
      text: "Confirm your account's email address first, then you can accept the invitation.",
    },
  ])('403 $reason ($lang)', ({ lang, reason, text }) => {
    it('zeigt den uebersetzten Text statt des Servertexts', async () => {
      await i18n.changeLanguage(lang)
      const serverDetail = 'SERVERTEXT-NICHT-ANZEIGEN'
      vi.stubGlobal('fetch', vi.fn(async () => problem(403, reason, serverDetail)()))

      renderAccept(authedSession, '/invitations/accept#token=t-403')

      fireEvent.click(await screen.findByTestId('invitation-accept-submit'))

      await waitFor(() => {
        expect(screen.getByText(text)).toBeInTheDocument()
      })
      expect(screen.queryByText(serverDetail)).toBeNull()
    })
  })

  // Responsive-Audit (#569): Workspace-Name und Einladender-E-Mail sind
  // fremdbestimmt und koennen ungebrochene Tokens enthalten. Beide
  // §10.2-Karten der Seite (Ladezustand und Annahme) tragen den Umbruch.
  it('laesst fremdbestimmte Bezeichner in beiden Karten umbrechen (#569)', () => {
    renderAccept(authedSession)

    const mains = document.querySelectorAll('main')
    expect(mains.length).toBeGreaterThan(0)
    for (const main of mains) {
      expect(main.className).toContain('break-words')
    }
  })
})
