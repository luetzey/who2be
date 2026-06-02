import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { OrgSettingsPage } from './OrgSettingsPage'

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
        id: 'org-1',
        name: 'Acme GmbH',
        slug: 'acme',
        kind: 'company',
        workspaces: [
          { id: 'ws-1', name: 'Marketing', slug: 'marketing', role },
          { id: 'ws-2', name: 'Engineering', slug: 'eng', role: 'viewer' },
        ],
      },
    ],
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

function renderPage(role: WorkspaceRole = 'admin', refreshMe = vi.fn()) {
  return render(
    <SessionContext.Provider
      value={{ session, me: buildMe(role), signIn: vi.fn(), signOut: vi.fn(), refreshMe }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/settings/org']}>
          <Routes>
            <Route path="/w/:workspaceId/settings/org" element={<OrgSettingsPage />} />
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

describe('OrgSettingsPage', () => {
  it('listet die Workspaces der Organisation und zeigt den Billing-Slot', () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse([])))
    renderPage('admin')
    expect(screen.getByText('Marketing')).toBeInTheDocument()
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByTestId('billing-slot')).toBeInTheDocument()
  })

  it('legt als Admin einen Workspace via POST an', async () => {
    const refreshMe = vi.fn().mockResolvedValue(undefined)
    const bodies: unknown[] = []
    let postUrl = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if ((init?.method ?? 'GET') === 'POST') {
          postUrl = url
          bodies.push(JSON.parse(init?.body as string))
          return jsonResponse(
            {
              id: 'ws-3',
              org_id: 'org-1',
              name: 'Sales',
              slug: 'sales',
              created_at: '2026-06-02T10:00:00Z',
            },
            201,
          )
        }
        return jsonResponse([])
      }),
    )

    renderPage('admin', refreshMe)

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Sales' } })
    fireEvent.change(screen.getByLabelText('Slug'), { target: { value: 'sales' } })
    fireEvent.click(screen.getByRole('button', { name: 'Workspace anlegen' }))

    await waitFor(() => {
      expect(bodies).toHaveLength(1)
    })
    expect(postUrl).toContain('/v1/organizations/org-1/workspaces')
    expect(bodies[0]).toEqual({ name: 'Sales', slug: 'sales' })
    expect(refreshMe).toHaveBeenCalled()
  })

  it('blendet das Anlage-Formular für Nicht-Admins aus', () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse([])))
    renderPage('viewer')
    expect(
      screen.queryByRole('button', { name: 'Workspace anlegen' }),
    ).toBeNull()
    expect(
      screen.getByText('Nur Admins können in dieser Organisation Workspaces anlegen.'),
    ).toBeInTheDocument()
  })
})
