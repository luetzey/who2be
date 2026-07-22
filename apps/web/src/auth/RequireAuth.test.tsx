import type { Session } from '@supabase/supabase-js'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { RequireAuth } from './RequireAuth'
import { SessionContext, type SessionValue } from './session-context'

function LoginProbe() {
  const location = useLocation()
  return <div data-testid="login">{`${location.pathname}${location.search}`}</div>
}

function renderAt(path: string, overrides: Partial<SessionValue>) {
  const value: SessionValue = {
    session: null,
    sessionLoaded: true,
    me: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    refreshMe: vi.fn(),
    ...overrides,
  }
  return render(
    <SessionContext.Provider value={value}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route element={<RequireAuth />}>
            <Route path="*" element={<div data-testid="protected" />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

describe('RequireAuth', () => {
  it('wartet den Session-Bootstrap ab, statt sofort zu redirecten (Reload-Bug)', () => {
    // Reload auf einer tiefen URL: Session ist noch nicht resolved. Ein
    // sofortiger Redirect wuerde die URL verwerfen und den User nach dem
    // Bootstrap immer auf dem Dashboard abladen.
    renderAt('/w/ws-1/personas/p-1', { sessionLoaded: false })

    expect(screen.queryByTestId('login')).not.toBeInTheDocument()
    expect(screen.queryByTestId('protected')).not.toBeInTheDocument()
    expect(screen.getByText('Wird geladen…')).toBeInTheDocument()
  })

  it('redirected ausgeloggt nach /login und nimmt die Ziel-URL als next mit', () => {
    renderAt('/w/ws-1/personas/p-1?tab=versions', { session: null })

    expect(screen.getByTestId('login').textContent).toBe(
      `/login?next=${encodeURIComponent('/w/ws-1/personas/p-1?tab=versions')}`,
    )
  })

  it('redirected von der Root ohne next-Parameter', () => {
    renderAt('/', { session: null })

    expect(screen.getByTestId('login').textContent).toBe('/login')
  })

  it('rendert das Outlet bei aktiver Session', () => {
    const session = { access_token: 'tok' } as unknown as Session
    renderAt('/w/ws-1/personas/p-1', { session })

    expect(screen.getByTestId('protected')).toBeInTheDocument()
  })
})
