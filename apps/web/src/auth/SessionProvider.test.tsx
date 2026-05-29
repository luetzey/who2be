import type { AuthChangeEvent, Session, Subscription } from '@supabase/supabase-js'
import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
  getSession,
  signInWithPassword,
  signOut,
  onAuthStateChange,
  unsubscribe,
} = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(),
  unsubscribe: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: { getSession, signInWithPassword, signOut, onAuthStateChange },
  },
}))

vi.mock('@/api/client', () => ({
  fetchMe: vi.fn(async () => ({
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [],
    has_password: true,
  })),
}))

import { SessionProvider } from './SessionProvider'
import { useSession } from './session-context'

function Probe() {
  const { session, me } = useSession()
  return (
    <div>
      <span data-testid="session">{session?.access_token ?? '<none>'}</span>
      <span data-testid="me">{me?.user_id ?? '<none>'}</span>
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
