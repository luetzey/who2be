import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, SystemPromptTemplate, SystemPromptTemplateVersion, VersionStatus } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { SystemPromptDetailPage } from './SystemPromptDetailPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel mocken — ProseMirror kann in jsdom nicht mounten
// (Standard-Pattern, vgl. PersonaDetailPage.test.tsx).
vi.mock('@/components/editor/system-prompt/SystemPromptEditor', () => ({
  SystemPromptEditor: () => <div data-testid="system-prompt-editor" />,
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}
// Admin-Membership fuer die Promote-Zweige der Status-Action-Bar.
const meAdmin: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'org1',
      name: 'Org',
      slug: 'org',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'admin' }],
    },
  ],
}

const WS_PREFIX = '/v1/workspaces/ws-1'

function template(overrides: Partial<SystemPromptTemplate> = {}): SystemPromptTemplate {
  return {
    id: 'sp1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Support-Template',
    slug: 'support-template',
    current_version: 1,
    current_status: 'draft',
    has_pending_draft: false,
    content: { description: 'Beschreibung', body: '[]' },
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  }
}

function version(status: VersionStatus): SystemPromptTemplateVersion {
  return {
    version: 1,
    status,
    content: { description: 'Beschreibung', body: '[]' },
    created_by: 'o1',
    created_at: '2026-07-01T00:00:00Z',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

function stubFetchRoutes(handlers: Record<string, () => Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const key = `${method} ${new URL(String(input)).pathname}`
    const handler = handlers[key]
    if (!handler) {
      throw new Error(`Unmocked ${key}`)
    }
    return handler()
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPage(activeMe: Me = me) {
  return render(
    <SessionContext.Provider
      value={{ session, me: activeMe, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/system-prompts/sp1']}>
          <Routes>
            <Route
              path="/w/:workspaceId/system-prompts/:id"
              element={<SystemPromptDetailPage />}
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

describe('SystemPromptDetailPage', () => {
  it('laedt das Template und zeigt Draft-Status-Aktion, Formular und Versionshistorie', async () => {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () => jsonResponse(template()),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        jsonResponse([version('draft')]),
    })

    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Support-Template' }),
    ).toBeInTheDocument()
    // Slug- und Versions-Badge im DetailHeader.
    expect(screen.getByText('support-template')).toBeInTheDocument()
    // Draft-Zweig der Status-Action-Bar.
    expect(screen.getByRole('toolbar', { name: 'Status-Aktionen' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeInTheDocument()
    // Formular mit geladenen Werten, editierbar (kein Managed-Lock) — Tab „Bearbeiten".
    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toHaveValue('Support-Template')
    })
    expect(screen.getByLabelText('Name')).toBeEnabled()
    expect(screen.queryByTestId('managed-notice')).not.toBeInTheDocument()
    // Versionshistorie liegt im Tab „Versionen".
    fireEvent.click(screen.getByRole('tab', { name: 'Versionen' }))
    expect(screen.getByRole('heading', { name: 'Versionen' })).toBeInTheDocument()
  })

  it('zeigt einen ErrorAlert, wenn das Template nicht geladen werden kann', async () => {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        new Response('kaputt', { status: 500 }),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () => jsonResponse([]),
    })

    renderPage()

    expect(await screen.findByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Support-Template' }),
    ).not.toBeInTheDocument()
  })

  it('Managed-Lock: Notice sichtbar, Editor read-only, keine Status-Aktionen', async () => {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        jsonResponse(template({ is_managed: true })),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        jsonResponse([version('draft')]),
    })

    renderPage()

    expect(await screen.findByTestId('managed-notice')).toBeInTheDocument()
    // Trotz Draft-Version keine Status-Action-Bar.
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Zur Review einreichen' }),
    ).not.toBeInTheDocument()
    // Editor gesperrt.
    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toHaveValue('Support-Template')
    })
    expect(screen.getByLabelText('Name')).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Neue Version speichern' }),
    ).toBeDisabled()
  })

  it('Review-Status als Admin: Aktivieren feuert die Transition und laedt neu', async () => {
    const transitionCalls: unknown[] = []
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        jsonResponse(template({ current_status: 'review' })),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        jsonResponse([version('review')]),
      [`POST ${WS_PREFIX}/system-prompts/sp1/versions/1/transition`]: () => {
        transitionCalls.push(true)
        return jsonResponse(version('active'))
      },
    })

    renderPage(meAdmin)

    const activate = await screen.findByRole('button', { name: 'Aktivieren' })
    expect(activate).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Zurück zu Draft' })).toBeInTheDocument()

    fireEvent.click(activate)

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Version aktiviert.')
    })
    expect(transitionCalls).toHaveLength(1)
  })

  it('Review-Status ohne Admin-Rolle: Aktivieren ist gesperrt', async () => {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        jsonResponse(template({ current_status: 'review' })),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        jsonResponse([version('review')]),
    })

    renderPage()

    expect(await screen.findByRole('button', { name: 'Aktivieren' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Zurück zu Draft' })).toBeEnabled()
  })

  it('Inactive-Status: bietet die Reaktivierung als Draft an', async () => {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        jsonResponse(template({ current_status: 'inactive' })),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        jsonResponse([version('inactive')]),
    })

    renderPage()

    expect(
      await screen.findByRole('button', { name: 'Als Draft reaktivieren' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Zur Review einreichen' }),
    ).not.toBeInTheDocument()
  })
})
