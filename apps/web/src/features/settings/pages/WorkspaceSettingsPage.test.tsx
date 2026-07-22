import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { WorkspaceSettingsPage } from './WorkspaceSettingsPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// Radix Dialog nutzt PointerCapture-APIs, die jsdom nicht implementiert.
beforeAll(() => {
  for (const method of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ]) {
    Object.defineProperty(window.HTMLElement.prototype, method, {
      value: () => undefined,
      configurable: true,
    })
  }
})

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(role: WorkspaceRole, workspaceCount: number): Me {
  const workspaces = [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role }]
  if (workspaceCount > 1) {
    workspaces.push({ id: 'ws-2', name: 'Engineering', slug: 'eng', role: 'admin' })
  }
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      { id: 'org-1', name: 'Acme', slug: 'acme', kind: 'company', workspaces },
    ],
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), { status })
}

// Admin-Renders zeigen die Memory-Wächter-Sektion, die beim Mount ihre
// Konfiguration laedt (GET .../memory-guard) — Tests, die die restlichen
// Workspace-Aktionen pruefen, brauchen dafuer einen Stub-Treffer.
function memoryGuardResponse(): Response {
  return jsonResponse({ mode: 'standard', allow_phrases: [], block_phrases: [] })
}

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

function renderPage(
  role: WorkspaceRole = 'admin',
  workspaceCount = 2,
  refreshMe = vi.fn().mockResolvedValue(undefined),
) {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me: buildMe(role, workspaceCount),
        sessionLoaded: true, signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe,
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/settings/workspace']}>
          <Routes>
            <Route
              path="/w/:workspaceId/settings/workspace"
              element={
                <>
                  <WorkspaceSettingsPage />
                  <LocationProbe />
                </>
              }
            />
            <Route
              path="/w/:workspaceId/dashboard"
              element={<LocationProbe />}
            />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('WorkspaceSettingsPage', () => {
  it('benennt den Workspace via PATCH um', async () => {
    const bodies: unknown[] = []
    let patchUrl = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if ((init?.method ?? 'GET') === 'PATCH') {
          patchUrl = url
          bodies.push(JSON.parse(init?.body as string))
          return jsonResponse({
            id: 'ws-1',
            org_id: 'org-1',
            name: 'Marketing & Sales',
            slug: 'marketing',
            created_at: '2026-06-02T10:00:00Z',
          })
        }
        if (url.includes('/memory-guard')) {
          return memoryGuardResponse()
        }
        return jsonResponse([])
      }),
    )

    renderPage('admin')

    const input = screen.getByLabelText('Name')
    fireEvent.change(input, { target: { value: 'Marketing & Sales' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(patchUrl).toContain('/v1/workspaces/ws-1')
    expect(bodies[0]).toEqual({ name: 'Marketing & Sales' })
  })

  it('sperrt das Löschen, wenn es der letzte Workspace ist', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes('/memory-guard')) {
          return memoryGuardResponse()
        }
        return jsonResponse([])
      }),
    )
    renderPage('admin', 1)
    expect(screen.getByRole('button', { name: 'Workspace löschen' })).toBeDisabled()
  })

  it('löscht nach Namensbestätigung und navigiert zum Fallback-Workspace', async () => {
    let deleteUrl = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if ((init?.method ?? 'GET') === 'DELETE') {
          deleteUrl = url
          return jsonResponse(null, 204)
        }
        if (url.includes('/memory-guard')) {
          return memoryGuardResponse()
        }
        return jsonResponse([])
      }),
    )

    renderPage('admin', 2)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace löschen' }))

    const confirmInput = await screen.findByLabelText('Workspace-Name')
    const confirmButton = screen.getByRole('button', { name: 'Endgültig löschen' })
    expect(confirmButton).toBeDisabled()

    fireEvent.change(confirmInput, { target: { value: 'Marketing' } })
    expect(confirmButton).toBeEnabled()
    fireEvent.click(confirmButton)

    await waitFor(() => expect(deleteUrl).toContain('/v1/workspaces/ws-1'))
    await waitFor(() =>
      expect(screen.getByTestId('location').textContent).toBe('/w/ws-2/dashboard'),
    )
  })

  it('versteckt die Danger-Zone für Nicht-Admins', () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse([])))
    renderPage('editor', 2)
    expect(screen.queryByRole('button', { name: 'Workspace löschen' })).toBeNull()
    expect(
      screen.getByText('Nur Admins können diesen Workspace umbenennen.'),
    ).toBeInTheDocument()
  })

  it('versteckt den Memory-Wächter für Nicht-Admins', () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse([])))
    renderPage('editor', 2)
    expect(screen.queryByText('Memory-Wächter')).toBeNull()
  })
})
