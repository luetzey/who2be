import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { ExternalTool, Me, VersionStatus, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel braucht im jsdom nicht real zu mounten — Page-Test prueft
// nur den Wrapper-Vertrag (Muster ResourceDetailPage.test.tsx).
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

import { ToolDetailPage } from './ToolDetailPage'

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

function tool(overrides: Partial<ExternalTool> = {}): ExternalTool {
  return {
    id: 't1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Todoist',
    alias: 'todo',
    current_version: 1,
    content: {
      display_name: 'Todoist App',
      mcp_server_name: 'Todoist MCP',
      tool_names: ['add_task'],
      usage_notes: '[]',
      fallback_note: null,
      tags: [],
    },
    created_at: 't',
    updated_at: 't',
    ...overrides,
  }
}

function version(v: number, status: VersionStatus) {
  return {
    version: v,
    status,
    content: tool().content,
    created_by: 'o1',
    created_at: 't',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

function errorResponse(status: number, detail?: string): Response {
  if (detail === undefined) {
    return new Response('', { status })
  }
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
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

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

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

interface DetailHandlerOptions {
  tool?: ExternalTool
  versions?: unknown[]
}

function detailHandlers(opts: DetailHandlerOptions = {}): FetchHandler {
  return (path, method) => {
    if (method === 'GET') {
      if (path === `${WS_PREFIX}/external_tools/t1`) return jsonResponse(opts.tool ?? tool())
      if (path === `${WS_PREFIX}/external_tools/t1/versions`)
        return jsonResponse(opts.versions ?? [version(1, 'draft')])
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
        <MemoryRouter initialEntries={['/w/ws-1/tools/t1']}>
          <Routes>
            <Route path="/w/:workspaceId/tools/:id" element={<ToolDetailPage />} />
            <Route path="/w/:workspaceId/tools" element={<div>TOOLS-LISTE</div>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
  return fetchMock
}

describe('ToolDetailPage — Lade-/Fehler-Zustaende', () => {
  it('zeigt den Ladezustand, solange das Tool noch nicht geladen ist', () => {
    renderDetailPage(() => new Promise<Response>(() => {}))

    expect(screen.getAllByText('Lädt…').length).toBeGreaterThan(0)
    expect(screen.queryByText('Todoist')).not.toBeInTheDocument()
  })

  it('zeigt die Fehlermeldung aus dem Error-Detail, wenn der Load 500 liefert', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/external_tools/t1`) {
        return errorResponse(500, 'Interner Serverfehler')
      }
      return base(path, method, init)
    })

    expect(await screen.findByText('Interner Serverfehler')).toBeInTheDocument()
    expect(screen.queryByText('Todoist')).not.toBeInTheDocument()
  })

  it('leitet ohne :id-Routenparameter zur Tool-Liste um', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse([])))
    render(
      <SessionContext.Provider
        value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/tool-detail']}>
            <Routes>
              <Route path="/w/:workspaceId/tool-detail" element={<ToolDetailPage />} />
              <Route path="/w/:workspaceId/tools" element={<div>TOOLS-LISTE</div>} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    expect(await screen.findByText('TOOLS-LISTE')).toBeInTheDocument()
  })
})

describe('ToolDetailPage — Formular + Alias', () => {
  it('rendert Name, Alias (read-only), Anzeigename, MCP-Server-Name und Tool-Namen', async () => {
    renderDetailPage(detailHandlers())

    expect(await screen.findByDisplayValue('Todoist')).toBeInTheDocument()
    const aliasInput = screen.getByLabelText('Alias')
    expect(aliasInput).toHaveValue('todo')
    expect(aliasInput).toBeDisabled()
    expect(screen.getByDisplayValue('Todoist MCP')).toBeInTheDocument()
    expect(screen.getByText('add_task')).toBeInTheDocument()
  })
})

describe('ToolDetailPage — Status-Action-Bar', () => {
  it('Draft: reicht per Klick zur Review ein', async () => {
    const transitionBodies: string[] = []
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/external_tools/t1/versions/1/transition`) {
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
      tool: tool({ current_status: 'review' }),
      versions: [version(1, 'review')],
    })
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/external_tools/t1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(version(1, 'active'))
      }
      return base(path, method, init)
    })

    const activate = await screen.findByRole('button', { name: 'Aktivieren' })
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
        if (method === 'POST' && path === `${WS_PREFIX}/external_tools/t1/versions/1/transition`) {
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
      tool: tool({ current_status: 'inactive' }),
      versions: [version(1, 'inactive')],
    })
    renderDetailPage((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/external_tools/t1/versions/1/transition`) {
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
      if (method === 'POST' && path === `${WS_PREFIX}/external_tools/t1/versions/1/transition`) {
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
})

describe('ToolDetailPage — Managed-Lock & Rollen', () => {
  it('is_managed: zeigt die Managed-Notice und blendet Status-/Danger-Zone-Aktionen aus', async () => {
    renderDetailPage(detailHandlers({ tool: tool({ is_managed: true }) }))

    expect(await screen.findByTestId('managed-notice')).toBeInTheDocument()
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Externes Tool löschen' }),
    ).not.toBeInTheDocument()
  })

  it('ohne Managed-Flag: keine Notice, Status-Bar und Danger-Zone-Toggle sind sichtbar', async () => {
    renderDetailPage(detailHandlers())

    expect(
      await screen.findByRole('button', { name: 'Externes Tool löschen' }),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('managed-notice')).not.toBeInTheDocument()
    expect(screen.getByRole('toolbar', { name: 'Status-Aktionen' })).toBeInTheDocument()
  })

  it('Viewer: sieht keine Danger-Zone, Export bleibt sichtbar (Lesen)', async () => {
    renderDetailPage(detailHandlers(), { me: meWithRole('viewer') })

    await screen.findByDisplayValue('Todoist')
    expect(
      screen.queryByRole('button', { name: 'Externes Tool löschen' }),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('export-tool-trigger')).toBeInTheDocument()
  })
})

describe('ToolDetailPage — Versions-Insel (ohne Diff-Endpoint)', () => {
  it('zeigt keinen Diff-Button, laedt Provenance lazy und stellt per Restore wieder her', async () => {
    const calledPaths: string[] = []
    const base = detailHandlers({
      tool: tool({ current_status: 'inactive' }),
      versions: [version(1, 'inactive')],
    })
    renderDetailPage((path, method, init) => {
      if (
        method === 'GET' &&
        path === `${WS_PREFIX}/external_tools/t1/versions/1/provenance`
      ) {
        calledPaths.push(path)
        return jsonResponse([])
      }
      if (
        method === 'POST' &&
        path === `${WS_PREFIX}/external_tools/t1/versions/1/restore`
      ) {
        calledPaths.push(path)
        return jsonResponse(tool())
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByRole('tab', { name: 'Versionen' }))

    // Kein `/diff`-Endpoint in der Backend-Surface (WP-1) — der Button entfaellt.
    expect(screen.queryByRole('button', { name: 'Diff' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Verlauf' }))
    await waitFor(() => {
      expect(calledPaths).toContain(
        `${WS_PREFIX}/external_tools/t1/versions/1/provenance`,
      )
    })

    fireEvent.click(screen.getByRole('button', { name: 'Wiederherstellen' }))
    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith(
        'v1 als Entwurf wiederhergestellt.',
      )
    })
    expect(calledPaths).toContain(`${WS_PREFIX}/external_tools/t1/versions/1/restore`)
  })
})

describe('ToolDetailPage — Delete-Flow (Danger-Zone)', () => {
  it('loescht nach Bestaetigung ueber die aufgeklappte Danger-Zone und navigiert zurueck', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/external_tools/t1`) {
        return new Response(null, { status: 204 })
      }
      return base(path, method, init)
    })

    const dangerToggle = await screen.findByRole('button', { name: 'Externes Tool löschen' })
    expect(screen.queryByTestId('delete-tool-trigger')).not.toBeInTheDocument()
    fireEvent.click(dangerToggle)

    fireEvent.click(await screen.findByTestId('delete-tool-trigger'))
    fireEvent.click(await screen.findByTestId('delete-tool-confirm'))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Externes Tool gelöscht.')
    })
    expect(await screen.findByText('TOOLS-LISTE')).toBeInTheDocument()
  })

  it('409 DeleteBlocked: listet die Verwender und sperrt den Confirm-Button', async () => {
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/external_tools/t1`) {
        return new Response(
          JSON.stringify({
            detail: {
              message: 'Wird noch verwendet',
              blocked_by: { playbooks: [{ playbook_id: 'pb9', playbook_name: 'Coach-Playbook' }] },
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Externes Tool löschen' }))
    fireEvent.click(await screen.findByTestId('delete-tool-trigger'))
    fireEvent.click(await screen.findByTestId('delete-tool-confirm'))

    expect(await screen.findByText('Löschen blockiert')).toBeInTheDocument()
    expect(screen.getByText(/Coach-Playbook/)).toBeInTheDocument()
    expect(screen.getByTestId('delete-tool-confirm')).toBeDisabled()
    expect(notify.success).not.toHaveBeenCalled()
  })
})

describe('ToolDetailPage — Export-Aktionen', () => {
  it('exportiert als JSON und meldet den Download-Erfolg', async () => {
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    const exportPaths: string[] = []
    const base = detailHandlers()
    renderDetailPage((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/external_tools/t1/export`) {
        exportPaths.push(path)
        return jsonResponse({ id: 't1', name: 'Todoist' })
      }
      return base(path, method, init)
    })

    fireEvent.keyDown(await screen.findByTestId('export-tool-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-tool-json'))

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
      if (method === 'GET' && path === `${WS_PREFIX}/external_tools/t1/export`) {
        return errorResponse(500, 'Export kaputt')
      }
      return base(path, method, init)
    })

    fireEvent.keyDown(await screen.findByTestId('export-tool-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-tool-markdown'))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Export kaputt')
    })
    expect(notify.success).not.toHaveBeenCalled()
  })
})
