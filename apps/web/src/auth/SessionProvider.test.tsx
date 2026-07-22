import type { AuthChangeEvent, Session, Subscription } from '@supabase/supabase-js'
import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
  getSession,
  signInWithPassword,
  signOut,
  onAuthStateChange,
  unsubscribe,
  fetchMe,
  getAuthenticatorAssuranceLevel,
} = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(),
  unsubscribe: vi.fn(),
  fetchMe: vi.fn(async () => ({
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [],
    has_password: true,
  })),
  // Default: kein Step-up faellig (currentLevel == nextLevel).
  getAuthenticatorAssuranceLevel: vi.fn(async () => ({
    data: { currentLevel: 'aal1', nextLevel: 'aal1' },
    error: null,
  })),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession,
      signInWithPassword,
      signOut,
      onAuthStateChange,
      mfa: { getAuthenticatorAssuranceLevel },
    },
  },
}))

vi.mock('@/api/client', () => ({
  fetchMe,
}))

import { SessionProvider } from './SessionProvider'
import { useSession } from './session-context'

function Probe() {
  const { session, me, sessionLoaded } = useSession()
  return (
    <div>
      <span data-testid="session">{session?.access_token ?? '<none>'}</span>
      <span data-testid="me">{me?.user_id ?? '<none>'}</span>
      <span data-testid="loaded">{sessionLoaded ? 'yes' : 'no'}</span>
    </div>
  )
}

let listener:
  | ((event: AuthChangeEvent, session: Session | null) => void)
  | null = null

beforeEach(() => {
  listener = null
  getSession.mockResolvedValue({ data: { session: null }, error: null })
  onAuthStateChange.mockImplementation(
    (cb: (event: AuthChangeEvent, session: Session | null) => void) => {
      listener = cb
      return {
        data: { subscription: { unsubscribe } as unknown as Subscription },
      }
    },
  )
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('SessionProvider', () => {
  it('registriert onAuthStateChange beim Mount', async () => {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(getSession).toHaveBeenCalled()
    })
    expect(onAuthStateChange).toHaveBeenCalledTimes(1)
  })

  it('uebernimmt Hash-Session aus dem Bootstrap und fetcht me genau einmal', async () => {
    // Magic-Link-Hash: GoTrue parsed den Token und liefert die Session
    // schon beim ersten `getSession()`. `onAuthStateChange` feuert direkt
    // danach mit `INITIAL_SESSION` und identischem Token — der zweite
    // `fetchMe`-Call wuerde Daten doppelt holen und (bei race) den ersten
    // ueberholen.
    const magicSession = { access_token: 'magic-jwt' } as unknown as Session
    getSession.mockResolvedValueOnce({ data: { session: magicSession }, error: null })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('magic-jwt')
      expect(screen.getByTestId('me').textContent).toBe('u1')
    })

    // Listener feuert mit identischem Token — dedupe verhindert Doppel-Fetch.
    await act(async () => {
      listener?.('INITIAL_SESSION', magicSession)
      await Promise.resolve()
    })

    expect(fetchMe).toHaveBeenCalledTimes(1)
  })

  it('synct Session+Me, sobald onAuthStateChange feuert (Magic-Link-Hash)', async () => {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(listener).not.toBeNull()
    })

    const magicSession = { access_token: 'magic-jwt' } as unknown as Session
    await act(async () => {
      listener?.('SIGNED_IN', magicSession)
      // Microtask abwarten, damit das asynchrone fetchMe-Resolved-State setzt.
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('magic-jwt')
      expect(screen.getByTestId('me').textContent).toBe('u1')
    })
  })

  it('haelt eine aal1-Session mit faelligem zweiten Faktor zurueck (kein Commit)', async () => {
    // Passwort ok, aber TOTP-Faktor verlangt Step-up: nextLevel > currentLevel.
    // Die Session darf NICHT committed werden, sonst landet der User mit aal1
    // in der App und jede Admin-Aktion 403t (mfa_required).
    getAuthenticatorAssuranceLevel.mockResolvedValueOnce({
      data: { currentLevel: 'aal1', nextLevel: 'aal2' },
      error: null,
    })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )
    await waitFor(() => {
      expect(listener).not.toBeNull()
    })

    const aal1Session = { access_token: 'aal1-jwt' } as unknown as Session
    await act(async () => {
      listener?.('SIGNED_IN', aal1Session)
      await Promise.resolve()
    })

    // Weder Session noch me committed; fetchMe erst gar nicht aufgerufen.
    expect(screen.getByTestId('session').textContent).toBe('<none>')
    expect(screen.getByTestId('me').textContent).toBe('<none>')
    expect(fetchMe).not.toHaveBeenCalled()
  })

  it('setzt sessionLoaded erst nach abgeschlossenem Bootstrap', async () => {
    // Solange getSession() pending ist, muss sessionLoaded false bleiben —
    // RequireAuth zeigt dann eine Ladeanzeige statt nach /login zu redirecten
    // (sonst gehen Deep-Links beim Reload verloren).
    let resolveGetSession!: (value: { data: { session: Session | null }; error: null }) => void
    getSession.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveGetSession = resolve
        }),
    )

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    expect(screen.getByTestId('loaded').textContent).toBe('no')

    await act(async () => {
      resolveGetSession({ data: { session: null }, error: null })
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(screen.getByTestId('loaded').textContent).toBe('yes')
    })
    // Kein Session-Commit — der User ist tatsaechlich ausgeloggt.
    expect(screen.getByTestId('session').textContent).toBe('<none>')
  })

  it('unsubscribed das onAuthStateChange-Listener beim Unmount', async () => {
    const { unmount } = render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )
    await waitFor(() => {
      expect(onAuthStateChange).toHaveBeenCalled()
    })

    unmount()

    // StrictMode kann den Effect doppelt mounten/unmounten — wichtig ist nur,
    // dass beim finalen Unmount unsubscribed wird (kein Listener-Leak).
    expect(unsubscribe).toHaveBeenCalled()
  })
})
