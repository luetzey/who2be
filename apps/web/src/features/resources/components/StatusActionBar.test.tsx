import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, VersionStatus } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { StatusActionBar } from './StatusActionBar'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

function renderBar(status: VersionStatus, onTransitioned = vi.fn()) {
  return render(
    <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/resources/r1']}>
          <Routes>
            <Route
              path="/w/:workspaceId/resources/:id"
              element={
                <StatusActionBar
                  resourceId="r1"
                  version={2}
                  status={status}
                  onTransitioned={onTransitioned}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('StatusActionBar (resource)', () => {
  it('zeigt im Draft nur den Submit-Button', () => {
    renderBar('draft')
    expect(screen.getByRole('button', { name: 'Zur Review einreichen' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aktivieren' })).toBeNull()
  })

  it('zeigt im Review Aktivieren und Ablehnen', () => {
    renderBar('review')
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ablehnen' })).toBeInTheDocument()
  })

  it('rendert nichts im Status active', () => {
    const { container } = renderBar('active')
    expect(container).toBeEmptyDOMElement()
  })

  it('ruft den Transition-Endpoint und onTransitioned bei Aktivieren auf', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({ url: String(input), init })
        return new Response('{}', { status: 200 })
      }),
    )
    const onTransitioned = vi.fn()

    renderBar('review', onTransitioned)
    fireEvent.click(screen.getByRole('button', { name: 'Aktivieren' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Version aktiviert.')
    })
    expect(onTransitioned).toHaveBeenCalledTimes(1)
    expect(calls[0].url).toContain('/v1/workspaces/ws-1/resources/r1/versions/2/transition')
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({ to: 'active' })
  })
})
