import type { Session } from '@supabase/supabase-js'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Agent, Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { axe } from '@/test/a11y'

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

// base64url(JSON) + Dummy-Sig, wie im Verhaltens-Test.
function blobOf(payload: Record<string, unknown>): string {
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
  return `${body}.sig`
}

function renderConsent(search: string) {
  return render(
    <SessionContext.Provider
      value={{
        session: authedSession,
        me,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[`/oauth/consent${search}`]}>
          <Routes>
            <Route path="/oauth/consent" element={<OAuthConsentPage />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('OAuthConsentPage (a11y)', () => {
  it('hat keine axe-Violations im Agent-Picker-Zustand', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify([builder, writer]), { status: 200 })),
    )

    const { container } = renderConsent(
      `?request=${blobOf({ client_name: 'Claude', redirect_uri: 'https://claude.ai/cb' })}`,
    )
    await screen.findByLabelText('Agent')

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('hat keine axe-Violations im Fehlerzustand ohne request-Parameter', async () => {
    // fetch auch hier stubben: ungestubbt kann ein (timing-abhaengig)
    // fehlschlagender Hintergrund-Call zusaetzlich einen ErrorAlert rendern —
    // die axe-Snapshot-DOM war dadurch auf langsamen Runnern nichtdeterministisch.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify([]), { status: 200 })),
    )
    const { container } = renderConsent('')
    await screen.findByText(/Verbindungs-Link/)

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
