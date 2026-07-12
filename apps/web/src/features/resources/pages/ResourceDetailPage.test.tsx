import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, Resource, VersionStatus, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel braucht im jsdom nicht real zu mounten — Page-Test
// pruegt nur den Wrapper-Vertrag (Card, Usages-Block, EmptyState).
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

import { ResourceDetailPage } from './ResourceDetailPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'o1',
      name: 'Org',
      slug: 'org',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'admin' }],
    },
  ],
}
const WS_PREFIX = '/v1/workspaces/ws-1'

function resource() {
  return {
    id: 'r1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Onboarding',
    slug: 'onboarding',
    current_version: 1,
    content: { description: 'd', blocks: [] },
    created_at: 't',
    updated_at: 't',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

function renderPage(handler: (url: string, method: string) => Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(new URL(String(input)).pathname, init?.method ?? 'GET'),
    ),
  )
  render(
    <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/resources/r1']}>
          <Routes>
            <Route path="/w/:workspaceId/resources/:id" element={<ResourceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

describe('ResourceDetailPage', () => {
  it('zeigt den "Verlinkt in"-Block mit Playbook-Namen und Block-Count', async () => {
    renderPage((path) => {
      if (path === `${WS_PREFIX}/resources/r1`) return jsonResponse(resource())
      if (path === `${WS_PREFIX}/resources/r1/versions`)
        return jsonResponse([
          { version: 1, content: { description: 'd', blocks: [] }, created_by: 'o1', created_at: 't' },
        ])
      if (path === `${WS_PREFIX}/resources/r1/usages`)
        return jsonResponse([
          { playbook_id: 'pb1', playbook_name: 'Coach', block_count: 1 },
          { playbook_id: 'pb2', playbook_name: 'Onboarding-Flow', block_count: 3 },
        ])
      if (path === `${WS_PREFIX}/resources/r1/sub_resources`) return jsonResponse([])
      if (path === `${WS_PREFIX}/resources/r1/used_by`) return jsonResponse([])
      throw new Error(`Unmocked ${path}`)
    })

    // „Verlinkt in" lebt jetzt im Verwendung-Tab.
    fireEvent.click(await screen.findByRole('tab', { name: 'Verwendung' }))
    await waitFor(() => {
      expect(screen.getByText('Verlinkt in')).toBeInTheDocument()
    })
    expect(screen.getByText('Coach')).toBeInTheDocument()
    expect(screen.getByText('Onboarding-Flow')).toBeInTheDocument()
    expect(screen.getByText('1 Block')).toBeInTheDocument()
    expect(screen.getByText('3 Blöcke')).toBeInTheDocument()
  })

  it('zeigt einen EmptyState, wenn /usages 404 zurueckgibt', async () => {
    renderPage((path) => {
      if (path === `${WS_PREFIX}/resources/r1`) return jsonResponse(resource())
      if (path === `${WS_PREFIX}/resources/r1/versions`)
        return jsonResponse([
          { version: 1, content: { description: 'd', blocks: [] }, created_by: 'o1', created_at: 't' },
        ])
      if (path === `${WS_PREFIX}/resources/r1/usages`)
        return new Response('', { status: 404 })
      if (path === `${WS_PREFIX}/resources/r1/sub_resources`)
        return new Response('', { status: 404 })
      if (path === `${WS_PREFIX}/resources/r1/used_by`)
        return new Response('', { status: 404 })
      throw new Error(`Unmocked ${path}`)
    })

    fireEvent.click(await screen.findByRole('tab', { name: 'Verwendung' }))
    await waitFor(() => {
      expect(screen.getByText('Noch in keinem Playbook verwendet')).toBeInTheDocument()
    })
  })

  it('zeigt die direkten Sub-Resources mit Scope-Badge', async () => {
    renderPage((path) => {
      if (path === `${WS_PREFIX}/resources/r1`) return jsonResponse(resource())
      if (path === `${WS_PREFIX}/resources/r1/versions`)
        return jsonResponse([
          { version: 1, content: { description: 'd', blocks: [] }, created_by: 'o1', created_at: 't' },
        ])
      if (path === `${WS_PREFIX}/resources/r1/usages`) return jsonResponse([])
      if (path === `${WS_PREFIX}/resources/r1/sub_resources`)
        return jsonResponse([
          {
            id: 'r2',
            name: 'Glossar',
            link_scope: 'resource',
            block_id: null,
            position: 0,
            fetch_call: "fetch_resource('r2')",
          },
        ])
      if (path === `${WS_PREFIX}/resources/r1/used_by`)
        return jsonResponse([{ id: 'r3', name: 'Handbuch' }])
      // Der inline Sub-Resource-Picker laedt die Workspace-Resources.
      if (path === `${WS_PREFIX}/resources`) return jsonResponse([])
      throw new Error(`Unmocked ${path}`)
    })

    // Direkte Sub-Resources liegen im Sub-Resources-Tab.
    fireEvent.click(await screen.findByRole('tab', { name: 'Sub-Resources' }))
    await waitFor(() => {
      expect(screen.getByText('Glossar')).toBeInTheDocument()
    })
    // Resource-Links tragen den Lazy/Inline-Toggle (statt eines Scope-Badges) —
    // ohne embedding_mode ist „Lazy" aktiv.
    expect(screen.getByRole('button', { name: 'Lazy' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    // Used-By-Backlink liegt im Verwendung-Tab.
    fireEvent.click(screen.getByRole('tab', { name: 'Verwendung' }))
    await waitFor(() => {
      expect(screen.getByText('Handbuch')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Branch-Coverage-Ergaenzungen (WP-1/TST-1): Lade-/Fehler-/NotFound-Zustaende,
// Status-Action-Bar-Zweige, Managed-Lock, Backlinks, Delete-Flow (inkl. 409),
// Export-Aktionen. Bestandstests oben bleiben unangetastet.
// ---------------------------------------------------------------------------

// Radix-Primitives (Dialog/DropdownMenu) brauchen Pointer-Capture-Stubs in
// jsdom (Muster aus DeleteResourceButton.test.tsx / ExportResourceButton.test.tsx).
beforeAll(() => {
  for (const fn of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

type FetchHandler = (
  path: string,
  method: string,
  init?: RequestInit,
) => Response | Promise<Response>

function errorResponse(status: number, detail?: string): Response {
  if (detail === undefined) {
    return new Response('', { status })
  }
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function resourceWith(overrides: Partial<Resource> = {}): Resource {
  return { ...(resource() as Resource), ...overrides }
}

function version(v: number, status: VersionStatus) {
  return {
    version: v,
    status,
    content: { description: 'd', blocks: [] },
    created_by: 'o1',
    created_at: 't',
  }
}

function feedbackSummary() {
  return {
    entity_type: 'resource',
    entity_id: 'r1',
    usage_count: 0,
    by_outcome: {},
    by_signal: {},
    recent_notes: [],
  }
}

function meWithRole(role: WorkspaceRole): Me {
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

interface DetailHandlerOptions {
  resource?: Resource
  versions?: unknown[]
  usages?: unknown[]
  subResources?: unknown[]
  allResources?: unknown[]
  usedBy?: unknown[]
}

function detailHandlers(opts: DetailHandlerOptions = {}): FetchHandler {
  return (path, method) => {
    if (method === 'GET') {
      if (path === `${WS_PREFIX}/resources/r1`)
        return jsonResponse(opts.resource ?? resource())
      if (path === `${WS_PREFIX}/resources/r1/versions`)
        return jsonResponse(opts.versions ?? [version(1, 'draft')])
      if (path === `${WS_PREFIX}/resources/r1/usages`)
        return jsonResponse(opts.usages ?? [])
      if (path === `${WS_PREFIX}/resources/r1/sub_resources`)
        return jsonResponse(opts.subResources ?? [])
      // Der inline Sub-Resource-Picker laedt die Workspace-Resources.
      if (path === `${WS_PREFIX}/resources`)
        return jsonResponse(opts.allResources ?? [])
      if (path === `${WS_PREFIX}/resources/r1/used_by`)
        return jsonResponse(opts.usedBy ?? [])
      if (path === `${WS_PREFIX}/feedback/resource/r1`)
        return jsonResponse(feedbackSummary())
    }
    throw new Error(`Unmocked ${method} ${path}`)
  }
}

function renderDetailPage(handler: FetchHandler, options: { me?: Me } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(new URL(String(input)).pathname, init?.method ?? 'GET', init),
  )
  vi.stubGlobal('fetch', fetchMock)
  render(
    <SessionContext.Provider
      value={{
        session,
        me: options.me ?? me,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/resources/r1']}>
          <Routes>
            <Route path="/w/:workspaceId/resources/:id" element={<ResourceDetailPage />} />
            <Route path="/w/:workspaceId/resources" element={<div>RESOURCES-LISTE</div>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
  return fetchMock
}

describe('ResourceDetailPage — Lade-/Fehler-Zustaende', () => {
  it('zeigt den Ladezustand, solange die Resource noch nicht geladen ist', () => {
    renderDetailPage(() => new Promise<Response>(() => {}))

    expect(screen.getAllByText('Lädt…').length).toBeGreaterThan(0)
    expect(screen.queryByText('Onboarding')).not.toBeInTheDocument()
  })

  it('zeigt die Fehlermeldung aus dem Error-Detail, wenn der Load 500 liefert', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/resources/r1`) {
        return errorResponse(500, 'Interner Serverfehler')
      }
      return base(path, method, init)
    })

    expect(await screen.findByText('Interner Serverfehler')).toBeInTheDocument()
    expect(screen.queryByText('Onboarding')).not.toBeInTheDocument()
  })

  it('zeigt bei 404 (NotFound) die generische API-Fehlermeldung', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/resources/r1`) {
        return errorResponse(404)
      }
      return base(path, method, init)
    })

    expect(
      await screen.findByText('Who2Be-API-Fehler (404).'),
    ).toBeInTheDocument()
  })

  it('leitet ohne :id-Routenparameter zur Resource-Liste um', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse([])),
    )
    render(
      <SessionContext.Provider
        value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/resource-detail']}>
            <Routes>
              <Route path="/w/:workspaceId/resource-detail" element={<ResourceDetailPage />} />
              <Route path="/w/:workspaceId/resources" element={<div>RESOURCES-LISTE</div>} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    expect(await screen.findByText('RESOURCES-LISTE')).toBeInTheDocument()
  })
})

describe('ResourceDetailPage — Status-Action-Bar', () => {
  it('Draft: zeigt die Draft-Beschreibung und reicht per Klick zur Review ein', async () => {
    const transitionBodies: string[] = []
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/resources/r1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(version(1, 'review'))
      }
      return base(path, method, init)
    })

    expect(
      await screen.findByText('Aktuelle Version: v1 (Entwurf)'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aktivieren' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Zur Review einreichen' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Zur Review eingereicht.')
    })
    expect(transitionBodies[0]).toContain('"to":"review"')
  })

  it('Review (Admin): aktiviert die Version ueber den Promote-Button', async () => {
    const transitionBodies: string[] = []
    const base = detailHandlers({
      resource: resourceWith({ current_status: 'review' }),
      versions: [version(1, 'review')],
    })
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/resources/r1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(version(1, 'active'))
      }
      return base(path, method, init)
    })

    expect(
      await screen.findByText('Aktuelle Version: v1 (In Review)'),
    ).toBeInTheDocument()
    const activate = screen.getByRole('button', { name: 'Aktivieren' })
    expect(activate).toBeEnabled()

    fireEvent.click(activate)

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Version aktiviert.')
    })
    expect(transitionBodies[0]).toContain('"to":"active"')
  })

  it('Review (Editor): Promote ist gesperrt, Ablehnen setzt zurueck auf Draft', async () => {
    const transitionBodies: string[] = []
    const base = detailHandlers({ versions: [version(1, 'review')] })
    renderDetailPage(
      (path, method, init) => {
        if (method === 'POST' && path === `${WS_PREFIX}/resources/r1/versions/1/transition`) {
          transitionBodies.push(String(init?.body))
          return jsonResponse(version(1, 'draft'))
        }
        return base(path, method, init)
      },
      { me: meWithRole('editor') },
    )

    const activate = await screen.findByRole('button', { name: 'Aktivieren' })
    expect(activate).toBeDisabled()
    expect(activate).toHaveAttribute('title', 'Nur Admins können aktivieren')

    fireEvent.click(screen.getByRole('button', { name: 'Ablehnen' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Review abgelehnt.')
    })
    expect(transitionBodies[0]).toContain('"to":"draft"')
  })

  it('Inactive: zeigt die Reaktivieren-Bar und reaktiviert als Draft', async () => {
    const transitionBodies: string[] = []
    const base = detailHandlers({
      resource: resourceWith({ current_status: 'inactive' }),
      versions: [version(1, 'inactive')],
    })
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/resources/r1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(version(1, 'draft'))
      }
      return base(path, method, init)
    })

    expect(
      await screen.findByText('Aktuelle Version: v1 (Inaktiv)'),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reaktivieren als Draft' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Reaktiviert als Entwurf.')
    })
    expect(transitionBodies[0]).toContain('"to":"draft"')
  })

  it('meldet den Fehler per Toast, wenn die Transition fehlschlaegt', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/resources/r1/versions/1/transition`) {
        return errorResponse(500, 'Transition kaputt')
      }
      return base(path, method, init)
    })

    fireEvent.click(
      await screen.findByRole('button', { name: 'Zur Review einreichen' }),
    )

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Transition kaputt')
    })
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('Active + Draft: Header nennt beide Versionen, die Draft-Bar bleibt sichtbar', async () => {
    renderDetailPage(
      detailHandlers({
        resource: resourceWith({ current_version: 3, current_status: 'draft' }),
        versions: [version(2, 'active'), version(3, 'draft')],
      }),
    )

    expect(
      await screen.findByText(/Active: v2 · Du arbeitest auf Draft v3/),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeInTheDocument()
  })

  it('Active + Review: Header nennt die Review-Version, Promote ist sichtbar', async () => {
    renderDetailPage(
      detailHandlers({
        resource: resourceWith({ current_version: 3, current_status: 'review' }),
        versions: [version(2, 'active'), version(3, 'review')],
      }),
    )

    expect(await screen.findByText(/Active: v2 · In Review: v3/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeInTheDocument()
  })

  it('nur Active (ohne Draft/Review): Header ohne Suffix, keine Status-Bar', async () => {
    renderDetailPage(
      detailHandlers({
        // `content` ohne `blocks` — der Editor faellt auf `?? []` zurueck.
        resource: resourceWith({
          current_version: 2,
          current_status: 'active',
          content: { description: 'd' } as Resource['content'],
        }),
        versions: [version(2, 'active')],
      }),
    )

    expect(await screen.findByText('Active: v2')).toBeInTheDocument()
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
  })
})

describe('ResourceDetailPage — Managed-Lock & Rollen', () => {
  it('is_managed: zeigt die Managed-Notice und blendet alle Mutations-Aktionen aus', async () => {
    renderDetailPage(
      detailHandlers({ resource: resourceWith({ is_managed: true }) }),
    )

    expect(await screen.findByTestId('managed-notice')).toBeInTheDocument()
    // Keine Status-Action-Bar, kein Danger-Zone-Delete, kein Sub-Resource-Picker.
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
    expect(screen.queryByTestId('delete-resource-trigger')).not.toBeInTheDocument()
    expect(screen.queryByText('Sub-Resources bearbeiten')).not.toBeInTheDocument()
  })

  it('ohne Managed-Flag: keine Notice, Status-Bar und Danger-Zone sind sichtbar', async () => {
    renderDetailPage(detailHandlers())

    expect(await screen.findByTestId('delete-resource-trigger')).toBeInTheDocument()
    expect(screen.queryByTestId('managed-notice')).not.toBeInTheDocument()
    expect(screen.getByRole('toolbar', { name: 'Status-Aktionen' })).toBeInTheDocument()
  })

  it('Viewer: sieht weder Danger-Zone noch Feedback-Panel noch Sub-Resource-Picker', async () => {
    renderDetailPage(detailHandlers(), { me: meWithRole('viewer') })

    await screen.findByText('Onboarding')
    expect(screen.queryByTestId('delete-resource-trigger')).not.toBeInTheDocument()
    expect(screen.queryByText('Feedback & Nutzung')).not.toBeInTheDocument()
    expect(screen.queryByText('Sub-Resources bearbeiten')).not.toBeInTheDocument()
    // Export ist Lesen — bleibt auch fuer Viewer sichtbar.
    expect(screen.getByTestId('export-resource-trigger')).toBeInTheDocument()
  })
})

describe('ResourceDetailPage — Backlinks & Scope-Zweige', () => {
  it('zeigt den Leer-Hinweis, wenn keine Resource diese als Sub-Resource nutzt', async () => {
    renderDetailPage(detailHandlers({ usedBy: [] }))

    fireEvent.click(await screen.findByRole('tab', { name: 'Verwendung' }))
    expect(
      await screen.findByText(
        'Keine Resource referenziert diese Resource als Sub-Resource.',
      ),
    ).toBeInTheDocument()
  })

  it('rendert Block-Scope- und Inline-Dokument-Badges der Sub-Resources', async () => {
    renderDetailPage(
      detailHandlers({
        subResources: [
          {
            id: 'r2',
            name: 'Abschnitt',
            link_scope: 'block',
            block_id: 'b-1',
            position: 0,
            fetch_call: "fetch_resource('r2')",
          },
          {
            id: 'r3',
            name: 'Anhang',
            link_scope: 'resource',
            block_id: null,
            position: 1,
            fetch_call: "fetch_resource('r3')",
            embedding_mode: 'inline',
          },
          {
            id: 'r4',
            name: 'Ohne Anker',
            link_scope: 'block',
            block_id: null,
            position: 2,
            fetch_call: "fetch_resource('r4')",
          },
        ],
      }),
    )

    fireEvent.click(await screen.findByRole('tab', { name: 'Sub-Resources' }))
    // Block-Anker sind read-only mit „Im Text"-Badge; ohne Anker ohne Block-Suffix.
    expect(await screen.findByText('Im Text (Block b-1)')).toBeInTheDocument()
    expect(screen.getByText('Im Text')).toBeInTheDocument()
    // Resource-Link mit inline-Modus: der Inline-Toggle ist aktiv.
    expect(screen.getByRole('button', { name: 'Inline' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})

describe('ResourceDetailPage — Versions-Insel', () => {
  it('Restore stellt die Version als Draft wieder her, Diff/Provenance laden lazy', async () => {
    const calledPaths: string[] = []
    const base = detailHandlers({
      resource: resourceWith({ current_status: 'inactive' }),
      versions: [version(1, 'inactive')],
    })
    renderDetailPage((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/resources/r1/versions/1/diff`) {
        calledPaths.push(path)
        return jsonResponse({
          version: 1,
          against: 'active',
          against_version: null,
          changes: [],
          identical: true,
        })
      }
      if (
        method === 'GET' &&
        path === `${WS_PREFIX}/resources/r1/versions/1/provenance`
      ) {
        calledPaths.push(path)
        return jsonResponse([])
      }
      if (
        method === 'POST' &&
        path === `${WS_PREFIX}/resources/r1/versions/1/restore`
      ) {
        calledPaths.push(path)
        return jsonResponse(resource())
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByRole('tab', { name: 'Versionen' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Diff' }))
    await waitFor(() => {
      expect(calledPaths).toContain(`${WS_PREFIX}/resources/r1/versions/1/diff`)
    })

    fireEvent.click(screen.getByRole('button', { name: 'Verlauf' }))
    await waitFor(() => {
      expect(calledPaths).toContain(
        `${WS_PREFIX}/resources/r1/versions/1/provenance`,
      )
    })

    fireEvent.click(screen.getByRole('button', { name: 'Wiederherstellen' }))
    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith(
        'v1 als Entwurf wiederhergestellt.',
      )
    })
    expect(calledPaths).toContain(`${WS_PREFIX}/resources/r1/versions/1/restore`)
  })
})

describe('ResourceDetailPage — Header-Aktionen (Slug/Duplizieren/Feedback)', () => {
  it('zeigt den Slug als Badge und einen Feedback-Link auf die Kuratierungs-Route', async () => {
    renderDetailPage(detailHandlers())

    expect(await screen.findByText('onboarding')).toBeInTheDocument()
    const feedback = screen.getByRole('link', { name: 'Feedback' })
    expect(feedback).toHaveAttribute('href', '/w/ws-1/feedback/resource/r1')
  })

  it('dupliziert die Resource und meldet den Erfolg', async () => {
    const duplicatePaths: string[] = []
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/resources/r1/duplicate`) {
        duplicatePaths.push(path)
        return jsonResponse(resourceWith({ id: 'r2', name: 'Onboarding (Kopie)' }))
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByTestId('duplicate-resource'))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Resource dupliziert.')
    })
    expect(duplicatePaths).toContain(`${WS_PREFIX}/resources/r1/duplicate`)
  })

  it('Viewer: Duplizieren-Button ist ausgegraut', async () => {
    renderDetailPage(detailHandlers(), { me: meWithRole('viewer') })

    expect(await screen.findByTestId('duplicate-resource')).toBeDisabled()
  })
})

describe('ResourceDetailPage — Delete-Flow', () => {
  it('loescht nach Bestaetigung und navigiert zurueck zur Liste', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/resources/r1`) {
        return new Response(null, { status: 204 })
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByTestId('delete-resource-trigger'))
    fireEvent.click(await screen.findByTestId('delete-resource-confirm'))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Resource gelöscht.')
    })
    expect(await screen.findByText('RESOURCES-LISTE')).toBeInTheDocument()
  })

  it('409 DeleteBlocked: listet die Verwender und sperrt den Confirm-Button', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/resources/r1`) {
        return new Response(
          JSON.stringify({
            detail: {
              message: 'Wird noch verwendet',
              blocked_by: {
                playbooks: [{ playbook_id: 'pb9', playbook_name: 'Coach-Playbook' }],
              },
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByTestId('delete-resource-trigger'))
    fireEvent.click(await screen.findByTestId('delete-resource-confirm'))

    expect(await screen.findByText('Löschen blockiert')).toBeInTheDocument()
    expect(screen.getByText(/Coach-Playbook/)).toBeInTheDocument()
    expect(screen.getByTestId('delete-resource-confirm')).toBeDisabled()
    expect(notify.success).not.toHaveBeenCalled()
  })
})

describe('ResourceDetailPage — Export-Aktionen', () => {
  it('exportiert als JSON und meldet den Download-Erfolg', async () => {
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    const exportPaths: string[] = []
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/resources/r1/export`) {
        exportPaths.push(path)
        return jsonResponse({ id: 'r1', name: 'Onboarding' })
      }
      return base(path, method, init)
    })

    fireEvent.keyDown(await screen.findByTestId('export-resource-trigger'), {
      key: 'Enter',
    })
    fireEvent.click(await screen.findByTestId('export-resource-json'))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Export heruntergeladen.')
    })
    expect(exportPaths).toHaveLength(1)
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('meldet den Fehler per Toast, wenn der Markdown-Export fehlschlaegt', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/resources/r1/export`) {
        return errorResponse(500, 'Export kaputt')
      }
      return base(path, method, init)
    })

    fireEvent.keyDown(await screen.findByTestId('export-resource-trigger'), {
      key: 'Enter',
    })
    fireEvent.click(await screen.findByTestId('export-resource-markdown'))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Export kaputt')
    })
    expect(notify.success).not.toHaveBeenCalled()
  })
})
