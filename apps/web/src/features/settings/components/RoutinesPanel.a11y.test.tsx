import type { Session } from '@supabase/supabase-js'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { RoutinesOverview } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { axe } from '@/test/a11y'

import { RoutinesPanel } from './RoutinesPanel'

const overview: RoutinesOverview = {
  worker_last_seen_at: '2026-10-10T19:58:00Z',
  routines: [
    {
      name: 'audit-retention',
      schedule: '0 4 * * *',
      enabled: true,
      source: 'env',
      last_run: {
        status: 'failed',
        trigger: 'schedule',
        started_at: '2026-10-10T04:00:00Z',
        duration_ms: 1500,
        result: { deleted: 3 },
        error_class: 'Abandoned',
      },
      next_run_at: '2026-10-11T04:00:00Z',
      last_success_at: null,
      external_schedule_detected: true,
    },
    {
      name: 'usage-rollup',
      schedule: '@every 15m',
      enabled: false,
      source: 'code',
      last_run: null,
      next_run_at: null,
      last_success_at: null,
      external_schedule_detected: false,
    },
  ],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('RoutinesPanel (a11y)', () => {
  it('hat keine axe-Violations mit Fehlerlauf und externem Zeitplan', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(overview), { status: 200 })),
    )

    const { container } = render(
      <SessionContext.Provider
        value={{
          session: { access_token: 'jwt' } as unknown as Session,
          me: null,
          sessionLoaded: true,
          signIn: vi.fn(),
          signOut: vi.fn(),
          refreshMe: vi.fn(),
        }}
      >
        <AuthTokenProvider>
          <MemoryRouter>
            <main>
              <h1>Konto</h1>
              <RoutinesPanel />
            </main>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )
    await screen.findByRole('region', { name: 'Hintergrund-Routinen' })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
