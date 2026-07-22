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

// base64url(JSON) + Dummy-Sig — die Page liest client_name/redirect_uri/agent_id
// nur zur Anzeige bzw. UI-Vorauswahl; die Signaturpruefung passiert serverseitig.
function blobOf(payload: Record<string, unknown>): string {
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
  return `${body}.sig`
}

function blobWith(clientName: string): string {
  return blobOf({ client_name: clientName })
}

// fetch-Stub: /agents liefert die Liste (oder einen Fehlerstatus), alles andere
// geht an /oauth/consent. Aufgezeichnete Calls fuer Body-Assertions.
function stubApi(options: {
  agents?: Agent[] | { status: number }
  consent?: { redirect: string } | { status: number }
}): Array<{ url: string; method: string; body: unknown }> {
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
        const agents = options.agents ?? []
        if (!Array.isArray(agents)) {
          return new Response('', { status: agents.status })
        }
        return new Response(JSON.stringify(agents), { status: 200 })
      }
      const consent = options.consent ?? { redirect: 'https://claude.ai/cb' }
      if ('status' in consent) {
        return new Response('', { status: consent.status })
      }
      return new Response(JSON.stringify(consent), { status: 200 })
    }),
  )
  return calls
}

function LoginMarker() {
  const [params] = useSearchParams()
  return <div>LOGIN next={params.get('next')}</div>
}

function renderConsent(session: Session | null, search: string, meValue: Me | null = me) {
  return render(
    <SessionContext.Provider
      value={{ session, me: meValue, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
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

  it('pinnt den Agenten aus dem Blob als readonly Feld und sendet dessen id', async () => {
    const assign = stubAssign()
    const calls = stubApi({
      agents: [builder, writer],
      consent: { redirect: 'https://claude.ai/cb?code=abc' },
    })

    renderConsent(
      authedSession,
      `?request=${blobOf({ client_name: 'Claude', agent_id: 'a2' })}`,
    )

    // Gepinnter Agent: readonly Input mit dem Namen statt Select.
    const locked = await screen.findByLabelText(/über die Verbindungs-URL festgelegt/)
    expect(locked).toHaveValue('Writer')
    expect(locked).toHaveAttribute('readonly')
    expect(screen.queryByLabelText('Agent')).toBeNull()
    expect(screen.getByText(/kann hier nicht gewechselt werden/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Verbinden' }))
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=abc')
    })
    const consentCall = calls.find((c) => c.url.includes('/oauth/consent'))
    expect(consentCall?.body).toMatchObject({ agent_id: 'a2', approve: true })
  })

  it('zeigt die rohe agent_id, wenn der gepinnte Agent nicht in der Liste ist', async () => {
    stubApi({ agents: [builder] })

    renderConsent(authedSession, `?request=${blobOf({ agent_id: 'ghost-uuid' })}`)

    const locked = await screen.findByLabelText(/über die Verbindungs-URL festgelegt/)
    expect(locked).toHaveValue('ghost-uuid')
  })

  it('zeigt den Host der signierten redirect_uri an', async () => {
    stubApi({ agents: [builder] })

    renderConsent(
      authedSession,
      `?request=${blobOf({
        client_name: 'Claude',
        redirect_uri: 'https://claude.ai/api/mcp/auth_callback?state=x',
      })}`,
    )

    await screen.findByText(/zurückgeleitet an/)
    expect(screen.getByText('claude.ai')).toBeInTheDocument()
  })

  it('unterdrueckt den Redirect-Hinweis bei unparsbarer redirect_uri', async () => {
    stubApi({ agents: [builder] })

    renderConsent(
      authedSession,
      `?request=${blobOf({ client_name: 'Claude', redirect_uri: 'kein-absoluter-url' })}`,
    )

    await screen.findByLabelText('Agent')
    expect(screen.queryByText(/zurückgeleitet an/)).toBeNull()
  })

  it('faellt bei unparsbarem Blob auf die generische Beschreibung zurueck', async () => {
    stubApi({ agents: [builder] })

    renderConsent(authedSession, '?request=%25%25nicht-base64.sig')

    expect(
      await screen.findByText(/Eine Anwendung möchte sich mit Who2Be verbinden/),
    ).toBeInTheDocument()
  })

  it('ignoriert nicht-string client_name und leere agent_id im Blob', async () => {
    stubApi({ agents: [builder, writer] })

    renderConsent(
      authedSession,
      `?request=${blobOf({ client_name: 42, agent_id: '', redirect_uri: '' })}`,
    )

    // Generische Beschreibung (client_name kein String) + freie Agent-Auswahl
    // (leere agent_id zaehlt nicht als Pinning), Default = erster Agent.
    expect(
      await screen.findByText(/Eine Anwendung möchte sich mit Who2Be verbinden/),
    ).toBeInTheDocument()
    expect(await screen.findByLabelText('Agent')).toHaveValue('a1')
  })

  it('zeigt einen Fehler, wenn die Agentenliste nicht laedt', async () => {
    stubApi({ agents: { status: 500 } })

    renderConsent(authedSession, `?request=${blobWith('Claude')}`)

    expect(await screen.findByText(/Autorisierung fehlgeschlagen/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verbinden' })).toBeNull()
  })

  it('zeigt den No-Agents-Hinweis bei leerer Agentenliste', async () => {
    stubApi({ agents: [] })

    renderConsent(authedSession, `?request=${blobWith('Claude')}`)

    expect(await screen.findByText(/Keine Agenten in diesem Workspace/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verbinden' })).toBeNull()
  })

  it('zeigt einen Fehler und reaktiviert die Buttons, wenn der Consent fehlschlaegt', async () => {
    const assign = stubAssign()
    stubApi({ agents: [builder], consent: { status: 500 } })

    renderConsent(authedSession, `?request=${blobWith('Claude')}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Verbinden' }))

    expect(await screen.findByText(/Autorisierung fehlgeschlagen/)).toBeInTheDocument()
    expect(assign).not.toHaveBeenCalled()
    // submitting wurde zurueckgesetzt — erneuter Versuch moeglich.
    expect(screen.getByRole('button', { name: 'Verbinden' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Ablehnen' })).toBeEnabled()
  })

  it('bleibt ohne default_workspace_id im Ladezustand und ruft die API nicht', async () => {
    const calls = stubApi({ agents: [builder] })

    renderConsent(authedSession, `?request=${blobWith('Claude')}`, {
      ...me,
      default_workspace_id: null,
    })

    // Effekt bricht ohne Workspace ab: Skeleton bleibt sichtbar, kein fetch.
    expect(await screen.findByText('Lädt…')).toBeInTheDocument()
    expect(calls).toHaveLength(0)
  })
})
