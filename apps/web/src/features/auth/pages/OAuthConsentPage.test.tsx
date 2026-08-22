import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { OAuthConsentPreviewAgent } from '@/api/client'
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

// fetch-Stub: /oauth/consent/preview liefert den Lock-Status (Default:
// ungelockt — passt zu Blobs ohne `agent_id`), /agents die Dropdown-Liste
// (oder einen Fehlerstatus), alles andere geht an /oauth/consent.
// Aufgezeichnete Calls fuer Body-Assertions.
function stubApi(options: {
  preview?: { locked: boolean; agent: OAuthConsentPreviewAgent | null } | { status: number }
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
      if (url.includes('/oauth/consent/preview')) {
        const preview = options.preview ?? { locked: false, agent: null }
        if ('status' in preview) {
          return new Response('', { status: preview.status })
        }
        return new Response(JSON.stringify(preview), { status: 200 })
      }
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
        if (url.includes('/oauth/consent/preview')) {
          return new Response(JSON.stringify({ locked: false, agent: null }), { status: 200 })
        }
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
    const consentCall = calls.find(
      (c) => c.url.includes('/oauth/consent') && !c.url.includes('/preview'),
    )
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
        if (url.includes('/oauth/consent/preview')) {
          return new Response(JSON.stringify({ locked: false, agent: null }), { status: 200 })
        }
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

  it('gelockt + aufloesbar: zeigt Name und Workspace des Preview-Agenten und sendet dessen id', async () => {
    const assign = stubAssign()
    const previewAgent: OAuthConsentPreviewAgent = {
      id: 'a2',
      name: 'Writer',
      workspace_id: 'ws-2',
      workspace_name: 'Anderer Workspace',
    }
    const calls = stubApi({
      preview: { locked: true, agent: previewAgent },
      consent: { redirect: 'https://claude.ai/cb?code=abc' },
    })

    renderConsent(
      authedSession,
      `?request=${blobOf({ client_name: 'Claude', agent_id: 'a2' })}`,
    )

    // Gepinnter Agent: readonly Input mit Name + Workspace aus der Preview
    // (nicht aus der — hier gar nicht geladenen — Workspace-Agentenliste).
    const locked = await screen.findByLabelText(/über die Verbindungs-URL festgelegt/)
    expect(locked).toHaveValue('Writer')
    expect(locked).toHaveAttribute('readonly')
    expect(screen.getByText('Workspace: Anderer Workspace')).toBeInTheDocument()
    expect(screen.queryByLabelText('Agent')).toBeNull()
    expect(screen.getByText(/kann hier nicht gewechselt werden/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Verbinden' }))
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=abc')
    })
    const consentCall = calls.find(
      (c) => c.url.includes('/oauth/consent') && !c.url.includes('/preview'),
    )
    expect(consentCall?.body).toMatchObject({ agent_id: 'a2', approve: true })
    // Lock-Fall: die Workspace-Agentenliste wird nicht mehr geladen (Fehler 2).
    expect(calls.some((c) => c.url.includes('/agents'))).toBe(false)
  })

  it('gelockt + nicht aufloesbar: sperrt Approve und nennt den Grund, ohne eine rohe UUID zu zeigen', async () => {
    const calls = stubApi({ preview: { locked: true, agent: null } })

    renderConsent(authedSession, `?request=${blobOf({ agent_id: 'ghost-uuid' })}`)

    expect(await screen.findByText(/Connector-URL verweist auf einen Agenten/)).toBeInTheDocument()
    expect(screen.queryByText('ghost-uuid')).toBeNull()
    expect(screen.queryByLabelText(/über die Verbindungs-URL festgelegt/)).toBeNull()
    expect(screen.queryByLabelText('Agent')).toBeNull()

    // Approve gesperrt, Deny bleibt moeglich (User kann trotzdem ablehnen).
    expect(screen.getByRole('button', { name: 'Verbinden' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Ablehnen' })).toBeEnabled()
    // Lock-Fall: die Workspace-Agentenliste wird nicht geladen.
    expect(calls.some((c) => c.url.includes('/agents'))).toBe(false)
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

  it('bleibt ohne default_workspace_id im Ladezustand, sobald die Preview ungelockt ist', async () => {
    const calls = stubApi({ agents: [builder] })

    renderConsent(authedSession, `?request=${blobWith('Claude')}`, {
      ...me,
      default_workspace_id: null,
    })

    // Die Preview braucht keinen Workspace (sie sucht ueber alle
    // Memberships) und wird deshalb IMMER angefragt. Erst der zweite Effekt
    // (Dropdown-Kandidaten aus dem Default-Workspace) haengt an
    // `default_workspace_id` — ohne den bleibt die Seite im Ladezustand und
    // `listAgents` wird nie aufgerufen.
    await waitFor(() => {
      expect(calls.some((c) => c.url.includes('/oauth/consent/preview'))).toBe(true)
    })
    expect(await screen.findByText('Lädt…')).toBeInTheDocument()
    expect(calls.some((c) => c.url.includes('/agents'))).toBe(false)
  })
})
