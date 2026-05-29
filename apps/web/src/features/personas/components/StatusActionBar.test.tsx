import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, VersionStatus, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { StatusActionBar } from './StatusActionBar'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'o1',
        name: 'Org',
        slug: 'org',
        kind: 'personal',
        workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role }],
      },
    ],
  }
}

function renderBar(
  status: VersionStatus,
  onTransitioned = vi.fn(),
  role: WorkspaceRole = 'admin',
) {
  return render(
    <SessionContext.Provider
      value={{ session, me: buildMe(role), signIn: vi.fn(), signOut: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
          <Routes>
            <Route
              path="/w/:workspaceId/personas/:id"
              element={
                <StatusActionBar
                  personaId="p1"
                  version={3}
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

describe('StatusActionBar (persona)', () => {
  it('zeigt im Draft nur den Submit-Button', () => {
    renderBar('draft')
    expect(
      screen.getByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aktivieren' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Ablehnen' })).toBeNull()
  })

  it('zeigt im Review Aktivieren und Ablehnen', () => {
    renderBar('review')
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ablehnen' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeNull()
  })

  it('aktiviert ist für Admins klickbar, für Editoren gesperrt', () => {
    const { unmount } = renderBar('review', vi.fn(), 'admin')
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    unmount()

    renderBar('review', vi.fn(), 'editor')
    const promote = screen.getByRole('button', { name: 'Aktivieren' })
    expect(promote).toBeDisabled()
    expect(promote).toHaveAttribute('title', 'Nur Admins können aktivieren')
  })

  it('rendert nichts im Status active', () => {
    const { container } = renderBar('active')
    expect(container).toBeEmptyDOMElement()
  })

  it('zeigt im Status inactive den Reactivate-Button', () => {
    renderBar('inactive')
    expect(
      screen.getByRole('button', { name: 'Reaktivieren als Draft' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aktivieren' })).toBeNull()
    expect(
      screen.queryByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeNull()
  })

  it('reaktiviert die Version per inactive→draft-Transition', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({ url: String(input), init })
        return new Response('{}', { status: 200 })
      }),
    )
    const onTransitioned = vi.fn()

    renderBar('inactive', onTransitioned)
    fireEvent.click(screen.getByRole('button', { name: 'Reaktivieren als Draft' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Reaktiviert als Entwurf.')
    })
    expect(onTransitioned).toHaveBeenCalledTimes(1)
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({ to: 'draft' })
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
    const call = calls[0]
    expect(call.url).toContain(
      '/v1/workspaces/ws-1/personas/p1/versions/3/transition',
    )
    expect(call.init?.method).toBe('POST')
    expect(JSON.parse(call.init?.body as string)).toEqual({ to: 'active' })
  })
})
