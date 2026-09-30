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
    id: 'v1',
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

function emptyReport(versionId: string) {
  return {
    entity_type: 'system_prompt_template',
    entity_id: 'sp1',
    version_id: versionId,
    affected_agent_count: 0,
    scope_note: null,
    counts: { total: 0, passed: 0, failed: 0, error: 0, missing: 0 },
    agents: [],
  }
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

function renderPage(activeMe: Me = me, initialEntry = '/w/ws-1/system-prompts/sp1') {
  return render(
    <SessionContext.Provider
      value={{ session, me: activeMe, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
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
      // Spec S11: ohne Pruefaelle bleibt Aktivieren ein Klick.
      [`GET ${WS_PREFIX}/versions/system_prompt_template/v1/test-report`]: () =>
        jsonResponse(emptyReport('v1')),
    })

    renderPage(meAdmin)

    // Die Leiste laedt zuerst den Pruefbericht (Knopf im Ladezustand gesperrt).
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    })
    const activate = screen.getByRole('button', { name: 'Aktivieren' })
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

// Audit E1 = A: `?tab=versions&diff=<n>` oeffnet den Versions-Tab mit
// aufgeklapptem Diff; die Statusleiste verlinkt im Review genau dorthin.
describe('SystemPromptDetailPage — Deep-Link in die Pruefansicht (E1 = A)', () => {
  const reviewVersions: SystemPromptTemplateVersion[] = [
    { ...version('review'), version: 2, created_at: '2026-07-02T00:00:00Z' },
    { ...version('active'), version: 1 },
  ]
  const diffBody = {
    version: 2,
    against: 'active',
    against_version: 1,
    identical: false,
    changes: [{ path: 'description', op: 'changed', before: 'alt', after: 'neu' }],
  }

  function stubReview() {
    const diffCalls: string[] = []
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        jsonResponse(template({ current_status: 'review', current_version: 2 })),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () => jsonResponse(reviewVersions),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions/2/diff`]: () => {
        diffCalls.push('v2')
        return jsonResponse(diffBody)
      },
    })
    return diffCalls
  }

  it('oeffnet per Deep-Link den Versions-Tab mit aufgeklapptem Diff', async () => {
    const diffCalls = stubReview()

    renderPage(meAdmin, '/w/ws-1/system-prompts/sp1?tab=versions&diff=2')

    expect(await screen.findByRole('list', { name: 'Änderungen' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Versionen' })).toHaveAttribute('aria-selected', 'true')
    expect(diffCalls).toEqual(['v2'])
  })

  it('der Link in der Review-Leiste fuehrt mit einem Klick in den Diff', async () => {
    stubReview()
    renderPage(meAdmin)

    const link = await screen.findByRole('link', { name: 'Änderungen und Prüffälle ansehen' })
    expect(screen.getByRole('tab', { name: 'Bearbeiten' })).toHaveAttribute('aria-selected', 'true')

    fireEvent.click(link)

    expect(await screen.findByRole('list', { name: 'Änderungen' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Versionen' })).toHaveAttribute('aria-selected', 'true')
  })

  it('ignoriert einen unbekannten Tab und einen ungueltigen Diff-Wert', async () => {
    const diffCalls = stubReview()

    renderPage(meAdmin, '/w/ws-1/system-prompts/sp1?tab=evil&diff=2')

    await screen.findByRole('link', { name: 'Änderungen und Prüffälle ansehen' })
    expect(screen.getByRole('tab', { name: 'Bearbeiten' })).toHaveAttribute('aria-selected', 'true')
    expect(diffCalls).toEqual([])
  })
})

// Responsive-Audit #566 (W3, Epic #431). jsdom hat kein Layout — geprueft wird
// der Klassen-Vertrag. Die Layout-Aussagen sind am gerenderten Baum belegt
// (Plandatei .claude/plan/2026-09-23-0700_566-…): bei 320px Viewport misst der
// Slug-Badge 497px (body.scrollWidth 577), und die Label-Zeile ueber dem Editor
// bricht ohne `flex-wrap` nicht um — mit einem laengeren Label schiebt sie den
// Trigger auf right 335 bei 320px Viewport.
describe('SystemPromptDetailPage — Umbruch bei 320px (#566)', () => {
  const LONG_SLUG = 'kundenonboarding_systemprompt_vertriebsteam_langbezeichner_q4_2026'

  function renderWithSlug() {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        jsonResponse(template({ slug: LONG_SLUG })),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        jsonResponse([version('draft')]),
    })
    renderPage()
  }

  it('laesst den umbruchfeindlichen Slug mitten im Wort brechen', async () => {
    renderWithSlug()

    const classes = (await screen.findByText(LONG_SLUG)).className.split(/\s+/)
    expect(classes).toContain('break-all')
    expect(classes).toContain('max-w-full')
  })

  // AK 3: die `justify-between`-Zeile ueber dem Editor (Label links,
  // Placeholder-Hilfe rechts) muss umbrechen duerfen statt ueberzulaufen.
  it('laesst die Label-Zeile ueber dem Editor umbrechen', async () => {
    renderWithSlug()

    const trigger = await screen.findByTestId('placeholder-help-trigger')
    const row = trigger.parentElement
    expect(row?.className.split(/\s+/)).toContain('flex-wrap')
  })
})

// Lernschleife B5-Web C (Spec S11): der Versions-Tab klappt die Review-
// Version auf und laedt deren Pruefbericht ueber Elementart + Versions-UUID;
// die Review-Leiste nutzt dieselbe UUID fuer den Aktivierungsdialog.
describe('SystemPromptDetailPage — Pruefbericht im Versions-Tab (S11)', () => {
  const REVIEW_ID = 'eeeeeeee-0000-4000-8000-000000000002'
  const REPORT_PATH = `${WS_PREFIX}/versions/system_prompt_template/${REVIEW_ID}/test-report`

  function stubS11(reportCalls: string[]) {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        jsonResponse(template({ current_status: 'review', current_version: 2 })),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        jsonResponse([
          { ...version('review'), id: REVIEW_ID, version: 2 },
          { ...version('active'), id: 'v1', version: 1 },
        ]),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions/2/diff`]: () =>
        jsonResponse({ version: 2, against: 'active', against_version: 1, identical: true, changes: [] }),
      [`GET ${REPORT_PATH}`]: () => {
        reportCalls.push(REPORT_PATH)
        return jsonResponse(emptyReport(REVIEW_ID))
      },
    })
  }

  it('der Diff der Review-Version laedt den Bericht mit system_prompt_template und UUID', async () => {
    const reportCalls: string[] = []
    stubS11(reportCalls)

    // Nicht-Admin: die Leiste laedt keinen Bericht, der Request kommt vom Diff.
    renderPage(me, '/w/ws-1/system-prompts/sp1?tab=versions')

    const create = await screen.findByRole('link', { name: 'Prüffall anlegen' })
    expect(create).toHaveAttribute('href', '/w/ws-1/system-prompts/sp1?tab=tests')
    expect(reportCalls).toEqual([REPORT_PATH])
  })

  it('Admin: die Review-Leiste laedt den Bericht derselben Version', async () => {
    const reportCalls: string[] = []
    stubS11(reportCalls)

    renderPage(meAdmin)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    })
    expect(reportCalls).toEqual([REPORT_PATH])
  })
})
