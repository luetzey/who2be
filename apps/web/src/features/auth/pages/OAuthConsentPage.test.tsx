import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Agent, Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { OAuthConsentPage } from './OAuthConsentPage'

const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
  has_password: true,
}
const authedSession = { access_token: 'jwt' } as unknown as Session

const builder = { id: 'a1', name: 'Builder', workspace_id: 'ws-1' } as unknown as Agent
const writer = { id: 'a2', name: 'Writer', workspace_id: 'ws-1' } as unknown as Agent

// base64url(JSON) + Dummy-Sig — die Page liest NUR den client_name zur Anzeige.
function blobWith(clientName: string): string {
  const body = btoa(JSON.stringify({ client_name: clientName }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
  return `${body}.sig`
}

function LoginMarker() {
  const [params] = useSearchParams()
  return <div>LOGIN next={params.get('next')}</div>
}

function renderConsent(session: Session | null, search: string, meValue: Me | null = me) {
  return render(
    <SessionContext.Provider
      value={{ session, me: meValue, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[`/oauth/consent${search}`]}>
          <Routes>
            <Route path="/oauth/consent" element={<OAuthConsentPage />} />
            <Route path="/login" element={<LoginMarker />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

const ORIGINAL_LOCATION = window.location

// jsdom's `window.location.assign` ist non-configurable → spyOn schlaegt fehl.
// Stattdessen `window.location` durch ein Stub-Objekt ersetzen.
function stubAssign(): ReturnType<typeof vi.fn> {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { assign, pathname: '/oauth/consent', search: '' },
  })
  return assign
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: ORIGINAL_LOCATION,
  })
})

describe('OAuthConsentPage', () => {
  it('zeigt den Agent-Picker und autorisiert mit dem gewaehlten Agenten', async () => {
    const assign = stubAssign()
    const calls: Array<{ url: string; method: string; body: unknown }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        calls.push({
          url,
          method: init?.method ?? 'GET',
          body: init?.body ? JSON.parse(String(init.body)) : null,
        })
        if (url.includes('/agents')) {
          return new Response(JSON.stringify([builder, writer]), { status: 200 })
        }
        return new Response(JSON.stringify({ redirect: 'https://claude.ai/cb?code=xyz' }), {
          status: 200,
        })
      }),
    )

    renderConsent(authedSession, `?request=${blobWith('Claude')}`)

    // Client-Name aus dem Blob steht in der Microcopy.
    await screen.findByText(/Claude/)
    // Zweiten Agenten waehlen, dann verbinden.
    const select = await screen.findByLabelText('Agent')
    fireEvent.change(select, { target: { value: 'a2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Verbinden' }))

    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=xyz')
    })
    const consentCall = calls.find((c) => c.url.includes('/oauth/consent'))
    expect(consentCall?.method).toBe('POST')
    expect(consentCall?.body).toMatchObject({ agent_id: 'a2', approve: true })
  })

  it('schickt ein Deny mit approve:false', async () => {
    const assign = stubAssign()
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/agents')) {
          return new Response(JSON.stringify([builder]), { status: 200 })
        }
        bodies.push(init?.body ? JSON.parse(String(init.body)) : null)
        return new Response(JSON.stringify({ redirect: 'https://claude.ai/cb?error=access_denied' }), {
          status: 200,
        })
      }),
    )

    renderConsent(authedSession, `?request=${blobWith('Claude')}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Ablehnen' }))

    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?error=access_denied')
    })
    expect(bodies[0]).toMatchObject({ approve: false })
  })

  it('schickt nicht eingeloggte Nutzer zum Login mit next-Parameter', () => {
    renderConsent(null, `?request=${blobWith('Claude')}`)
    expect(screen.getByText(/^LOGIN next=\/oauth\/consent/)).toBeInTheDocument()
  })

  it('zeigt einen Fehler, wenn der request-Parameter fehlt', () => {
    renderConsent(authedSession, '')
    expect(screen.getByText(/Verbindungs-Link/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verbinden' })).toBeNull()
  })
})
