import type { Session } from '@supabase/supabase-js'
import { type ReactElement } from 'react'
import { render, type RenderResult } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import type { Me } from '@/api/types'
import { AppLayout } from '@/app/AppLayout'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

interface RenderInRoutesOptions {
  path: string
  initialEntries?: string[]
  session?: Session | null
  me?: Me | null
}

const defaultSession = { access_token: 'tok' } as unknown as Session
const defaultMe: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

/**
 * Rendert ein Page-Element in dem Route-Layout-Setup, das die Produktion
 * benutzt: SessionContext + AuthTokenProvider + MemoryRouter + AppLayout
 * (mit Outlet). Gedacht fuer A11y-Tests und neue Page-Tests, die das
 * tatsaechliche DOM-Setup brauchen.
 *
 * Bestehende Tests (Phase < 2) wrappen Pages direkt — die brauchen das
 * hier nicht, weil sie auf reines Page-DOM testen.
 */
export function renderInRoutes(
  element: ReactElement,
  options: RenderInRoutesOptions,
): RenderResult {
  const {
    path,
    session = defaultSession,
    me = defaultMe,
    initialEntries = [path],
  } = options
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path={path} element={element} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}
