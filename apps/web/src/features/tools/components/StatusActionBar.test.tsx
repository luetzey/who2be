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
      value={{ session, me: buildMe(role), signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/tools/t1']}>
          <Routes>
            <Route
              path="/w/:workspaceId/tools/:id"
              element={
                <StatusActionBar
                  toolId="t1"
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

describe('StatusActionBar (tools)', () => {
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

  it('aktiviert ist für Admins klickbar, für Viewer gesperrt', () => {
    const { unmount } = renderBar('review', vi.fn(), 'admin')
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    unmount()

    renderBar('review', vi.fn(), 'viewer')
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
    expect(screen.getByRole('button', { name: 'Reaktivieren als Draft' })).toBeInTheDocument()
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
    expect(calls[0].url).toContain('/v1/workspaces/ws-1/external_tools/t1/versions/2/transition')
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({ to: 'active' })
  })

  it('meldet den Fehler per Toast bei einem generischen Transition-Fehler', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'Kaputt' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )

    renderBar('draft')
    fireEvent.click(screen.getByRole('button', { name: 'Zur Review einreichen' }))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Kaputt')
    })
  })

  it('zeigt Inline-Fehler mit Feldnamen bei 409 Promote-Validation-Fail', async () => {
    const problemBody = {
      type: 'https://who2be.dev/errors/promote-validation-failed',
      missing: ['name'],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify(problemBody), {
          status: 409,
          headers: { 'Content-Type': 'application/problem+json' },
        }),
      ),
    )

    renderBar('review')
    fireEvent.click(screen.getByRole('button', { name: 'Aktivieren' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    })
    expect(await screen.findByText(/Name/)).toBeInTheDocument()
    expect(notify.error).not.toHaveBeenCalled()
  })
})
