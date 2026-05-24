import type { Session } from '@supabase/supabase-js'
import { act, render, screen } from '@testing-library/react'
import { type ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { AuthTokenProvider } from './AuthTokenProvider'
import { useAuthTokenContext } from './auth-token-context'
import { SessionContext } from './session-context'
import { useAuthToken } from './useAuthToken'

function wrap(children: ReactNode, session: Session | null) {
  return (
    <SessionContext.Provider value={{ session, signIn: vi.fn(), signOut: vi.fn() }}>
      <AuthTokenProvider>{children}</AuthTokenProvider>
    </SessionContext.Provider>
  )
}

function TokenProbe() {
  const token = useAuthToken()
  return <span data-testid="token">{token === '' ? '<none>' : token}</span>
}

function OverrideProbe({ value }: { value: string | null }) {
  const { setOverrideToken } = useAuthTokenContext()
  return (
    <button type="button" onClick={() => setOverrideToken(value)}>
      set
    </button>
  )
}

describe('useAuthToken', () => {
  it('liefert leeren Token, wenn weder Session noch Override gesetzt sind', () => {
    render(wrap(<TokenProbe />, null))
    expect(screen.getByTestId('token').textContent).toBe('<none>')
  })

  it('greift auf das Supabase-JWT zurueck, wenn kein Override gesetzt ist', () => {
    const session = { access_token: 'jwt-from-supabase' } as unknown as Session
    render(wrap(<TokenProbe />, session))
    expect(screen.getByTestId('token').textContent).toBe('jwt-from-supabase')
  })

  it('bevorzugt den w2b_-Override gegenueber der Session', () => {
    const session = { access_token: 'jwt-from-supabase' } as unknown as Session
    render(
      wrap(
        <>
          <TokenProbe />
          <OverrideProbe value="w2b_abc" />
        </>,
        session,
      ),
    )
    act(() => {
      screen.getByRole('button', { name: 'set' }).click()
    })
    expect(screen.getByTestId('token').textContent).toBe('w2b_abc')
  })

  it('faellt nach Override-Reset wieder auf die Session zurueck', () => {
    const session = { access_token: 'jwt-from-supabase' } as unknown as Session
    const { rerender } = render(
      wrap(
        <>
          <TokenProbe />
          <OverrideProbe value="w2b_abc" />
        </>,
        session,
      ),
    )
    act(() => {
      screen.getByRole('button', { name: 'set' }).click()
    })
    expect(screen.getByTestId('token').textContent).toBe('w2b_abc')

    rerender(
      wrap(
        <>
          <TokenProbe />
          <OverrideProbe value={null} />
        </>,
        session,
      ),
    )
    act(() => {
      screen.getByRole('button', { name: 'set' }).click()
    })
    expect(screen.getByTestId('token').textContent).toBe('jwt-from-supabase')
  })
})
