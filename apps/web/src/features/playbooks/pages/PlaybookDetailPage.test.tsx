import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, VersionStatus, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'
import { PlaybookDetailPage } from './PlaybookDetailPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel mocken — sie ist in jsdom nicht mountfaehig. PlaybookEditorForm
// importiert PlaybookBodyEditor statisch → beim Modul-Load baut PlaceholderBlock
// das Schema via createReactInlineContentSpec/BlockNoteSchema.create, daher diese
// Exports mit-mocken (Muster aus PlaybookBodyEditor.test.tsx).
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
  SuggestionMenuController: () => null,
  getDefaultReactSlashMenuItems: () => [],
  createReactInlineContentSpec: (_config: unknown, _impl: unknown) => ({
    config: _config,
    implementation: _impl,
  }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@blocknote/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@blocknote/core')>()
  return {
    ...actual,
    BlockNoteSchema: {
      create: vi.fn().mockReturnValue({
        blockSchema: {},
        inlineContentSchema: {
          placeholder: { type: 'placeholder', propSchema: {}, content: 'none' },
          text: { config: 'text' },
          link: { config: 'link' },
        },
        styleSchema: {},
      }),
    },
    defaultInlineContentSpecs: { text: {}, link: {} },
  }
})
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}
const WS_PREFIX = '/v1/workspaces/ws-1'

interface PlaybookShape {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  current_version: number
  type: string
  tags: string[]
  triggers: string | null
  content: {
    description: string
    body: string
    type: string
    tags: string[]
    triggers: string | null
  }
  created_at: string
  updated_at: string
}

function playbook(version: number, body: string): PlaybookShape {
  return {
    id: 'pb1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Coach',
    current_version: version,
    type: 'workflow',
    tags: ['coaching'],
    triggers: null,
    content: {
      description: 'd',
      body,
      type: 'workflow',
      tags: ['coaching'],
      triggers: null,
    },
    created_at: '2026-05-24T12:00:00Z',
    updated_at: '2026-05-24T12:00:00Z',
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

describe('PlaybookDetailPage', () => {
  it('Auto-Save: aendert man Felder, geht ein PATCH-Draft raus und kein PUT', async () => {
    const v1 = {
      version: 1,
      status: 'draft',
      content: playbook(1, 'b1').content,
      created_by: 'o1',
      created_at: 't1',
    }
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbook(1, 'b1')),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () => jsonResponse([v1]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/usages`]: () => jsonResponse([]),
      // Track A8 — Composite-Endpoints (leere Listen).
      [`GET ${WS_PREFIX}/playbooks/pb1/composes`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/composed_by`]: () => jsonResponse([]),
    }

    const patchCalls: Array<{ url: string; body: unknown }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      const pathname = new URL(url).pathname
      if (method === 'PATCH' && pathname.endsWith('/playbooks/pb1/draft')) {
        patchCalls.push({ url, body: JSON.parse(init?.body as string) })
        return jsonResponse(playbook(1, 'b1'))
      }
      const key = `${method} ${pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // WICHTIG: warten bis form.reset(playbook) durchgelaufen ist und das
    // Name-Feld den geladenen Wert "Coach" enthaelt. Sonst feuert
    // fireEvent.change gegen ein noch leeres Default-Input und der spaeter
    // eintreffende reset ueberschreibt die Aenderung — PATCH wird nie
    // ausgeloest (CI-Flake beobachtet in PR #79, analog Persona-Test).
    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toHaveValue('Coach')
    })
    // Save-Button gibt es nicht mehr.
    expect(
      screen.queryByRole('button', { name: 'Neue Version speichern' }),
    ).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Coach v2' } })
    // Auto-Save-Debounce ist 1500 ms — Real-Timer warten ist robuster als
    // FakeTimers (die unter Vitest in Kombination mit dem React-Concurrent-
    // Renderer manchmal pending Promises blockieren). CI-Runner haben
    // mehrfach 3s und 5s gerissen (PR #79); 8s ist grosszuegig, das
    // it()-Timeout unten ist auf 15s gehoben.
    await waitFor(
      () => {
        expect(patchCalls.length).toBeGreaterThanOrEqual(1)
      },
      { timeout: 8000 },
    )
    expect(
      (patchCalls[patchCalls.length - 1].body as { name: string }).name,
    ).toBe('Coach v2')
    const putCalls = fetchMock.mock.calls.filter(
      (call) => (call[1] as RequestInit | undefined)?.method === 'PUT',
    )
    expect(putCalls).toHaveLength(0)
  }, 15_000)

  it('zeigt im "Verwendet in"-Block die Personas aus /usages und faellt auf EmptyState zurueck, wenn keine vorhanden sind', async () => {
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbook(1, 'b1')),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () =>
        jsonResponse([
          { version: 1, content: playbook(1, 'b1').content, created_by: 'o1', created_at: 't1' },
        ]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/usages`]: () =>
        jsonResponse([
          { persona_id: 'per1', persona_name: 'Coach Persona' },
          { persona_id: 'per2', persona_name: 'Onboarding Persona' },
        ]),
      [`GET ${WS_PREFIX}/playbooks/pb1/composes`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/composed_by`]: () => jsonResponse([]),
    }
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

    render(
      <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('Verwendet in')).toBeInTheDocument()
    })
    expect(screen.getByText('Coach Persona')).toBeInTheDocument()
    expect(screen.getByText('Onboarding Persona')).toBeInTheDocument()
  })

  it('rendert vorhandene Komma-Trigger als Pills statt als Komma-Text', async () => {
    const playbookWithTriggers = {
      ...playbook(1, 'b1'),
      triggers: '"passwort vergessen", "reset link"',
      content: {
        ...playbook(1, 'b1').content,
        triggers: '"passwort vergessen", "reset link"',
      },
    }
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbookWithTriggers),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () =>
        jsonResponse([
          {
            version: 1,
            content: playbookWithTriggers.content,
            created_by: 'o1',
            created_at: 't1',
          },
        ]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/usages`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/composes`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/composed_by`]: () => jsonResponse([]),
    }
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

    render(
      <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // Trigger leben jetzt ausschliesslich im Formular (TagInput-Chips) —
    // Anfuehrungszeichen sind geschluckt, jeder Trigger eine eigene Pill.
    expect(await screen.findByText('passwort vergessen')).toBeInTheDocument()
    expect(screen.getByText('reset link')).toBeInTheDocument()
    expect(screen.queryByText(/"passwort/)).not.toBeInTheDocument()
  })

  it('zeigt einen EmptyState wenn /usages ein 404 zurueckgibt', async () => {
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/playbooks/pb1`]: () => jsonResponse(playbook(1, 'b1')),
      [`GET ${WS_PREFIX}/playbooks/pb1/versions`]: () =>
        jsonResponse([
          { version: 1, content: playbook(1, 'b1').content, created_by: 'o1', created_at: 't1' },
        ]),
      [`GET ${WS_PREFIX}/playbooks/pb1/resource_links`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/composes`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/playbooks/pb1/composed_by`]: () => jsonResponse([]),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      const pathname = new URL(url).pathname
      if (pathname.endsWith('/usages')) {
        return new Response('', { status: 404 })
      }
      const key = `${method} ${pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('Noch in keiner Persona verwendet')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Branch-Coverage-Ergaenzungen (WP-1/TST-1): Lade-/Fehler-Zustaende, Status-
// Transitions (draft/review/active/inactive), Managed-Lock, Composite-/Tag-/
// Trigger-Zweige, Resource-Links, Backlinks, Delete-Flow inkl. 409.
// Bestandstests oben bleiben unangetastet.
// ---------------------------------------------------------------------------

// Radix-Primitives (Dialog) brauchen Pointer-Capture-Stubs in jsdom
// (Muster aus DeletePlaybookButton.test.tsx).
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

function playbookWith(
  overrides: Partial<PlaybookShape> & Record<string, unknown> = {},
): PlaybookShape & Record<string, unknown> {
  return { ...playbook(1, 'b1'), ...overrides }
}

function pbVersion(v: number, status: VersionStatus) {
  return {
    version: v,
    status,
    content: playbook(v, 'b1').content,
    created_by: 'o1',
    created_at: 't1',
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

interface PlaybookHandlerOptions {
  playbook?: Record<string, unknown>
  versions?: unknown[]
  resourceLinks?: unknown[]
  usages?: unknown[]
  composes?: unknown[]
  composedBy?: unknown[]
}

function playbookHandlers(opts: PlaybookHandlerOptions = {}): FetchHandler {
  return (path, method) => {
    if (method === 'GET') {
      if (path === `${WS_PREFIX}/playbooks/pb1`)
        return jsonResponse(opts.playbook ?? playbook(1, 'b1'))
      if (path === `${WS_PREFIX}/playbooks/pb1/versions`)
        return jsonResponse(opts.versions ?? [pbVersion(1, 'draft')])
      if (path === `${WS_PREFIX}/playbooks/pb1/resource_links`)
        return jsonResponse(opts.resourceLinks ?? [])
      if (path === `${WS_PREFIX}/playbooks/pb1/usages`)
        return jsonResponse(opts.usages ?? [])
      if (path === `${WS_PREFIX}/playbooks/pb1/composes`)
        return jsonResponse(opts.composes ?? [])
      if (path === `${WS_PREFIX}/playbooks/pb1/composed_by`)
        return jsonResponse(opts.composedBy ?? [])
      if (path === `${WS_PREFIX}/feedback/playbook/pb1`)
        return jsonResponse({
          entity_type: 'playbook',
          entity_id: 'pb1',
          usage_count: 0,
          by_outcome: {},
          by_signal: {},
          recent_notes: [],
        })
    }
    throw new Error(`Unmocked ${method} ${path}`)
  }
}

function renderPlaybookDetail(handler: FetchHandler, options: { me?: Me } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(new URL(String(input)).pathname, init?.method ?? 'GET', init),
  )
  vi.stubGlobal('fetch', fetchMock)
  render(
    <SessionContext.Provider
      value={{
        session,
        me: options.me ?? me,
        sessionLoaded: true, signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/playbooks/pb1']}>
          <Routes>
            <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
            <Route path="/w/:workspaceId/playbooks" element={<div>PLAYBOOKS-LISTE</div>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
  return fetchMock
}

describe('PlaybookDetailPage — Lade-/Fehler-Zustaende', () => {
  it('zeigt den Ladezustand, solange das Playbook noch nicht geladen ist', () => {
    renderPlaybookDetail(() => new Promise<Response>(() => {}))

    expect(screen.getAllByText('Lädt…').length).toBeGreaterThan(0)
    expect(screen.queryByText('Coach')).not.toBeInTheDocument()
  })

  it('zeigt die Fehlermeldung aus dem Error-Detail, wenn der Load 500 liefert', async () => {
    const base = playbookHandlers()
    renderPlaybookDetail((path, method, init) => {
      if (method === 'GET' && path === `${WS_PREFIX}/playbooks/pb1`) {
        return errorResponse(500, 'Playbook kaputt')
      }
      return base(path, method, init)
    })

    expect(await screen.findByText('Playbook kaputt')).toBeInTheDocument()
    expect(screen.queryByText('Coach')).not.toBeInTheDocument()
  })

  it('leitet ohne :id-Routenparameter zur Playbook-Liste um', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse([])),
    )
    render(
      <SessionContext.Provider
        value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbook-detail']}>
            <Routes>
              <Route path="/w/:workspaceId/playbook-detail" element={<PlaybookDetailPage />} />
              <Route path="/w/:workspaceId/playbooks" element={<div>PLAYBOOKS-LISTE</div>} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    expect(await screen.findByText('PLAYBOOKS-LISTE')).toBeInTheDocument()
  })
})

describe('PlaybookDetailPage — Status-Transitions', () => {
  it('Draft: "Draft abschliessen" reicht die Version zur Review ein', async () => {
    const transitionBodies: string[] = []
    const base = playbookHandlers()
    renderPlaybookDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/playbooks/pb1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(pbVersion(1, 'review'))
      }
      return base(path, method, init)
    })

    // Review-Banner zeigt den offenen Entwurf als Branch-Knoten.
    expect(await screen.findByTestId('review-banner')).toBeInTheDocument()
    expect(screen.getByText('Entwurf: v1')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Draft abschliessen' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Zur Review eingereicht.')
    })
    expect(transitionBodies[0]).toContain('"to":"review"')
  })

  it('Review (Admin): "Veroeffentlichen" aktiviert die Version', async () => {
    const transitionBodies: string[] = []
    const base = playbookHandlers({ versions: [pbVersion(1, 'review')] })
    renderPlaybookDetail(
      (path, method, init) => {
        if (method === 'POST' && path === `${WS_PREFIX}/playbooks/pb1/versions/1/transition`) {
          transitionBodies.push(String(init?.body))
          return jsonResponse(pbVersion(1, 'active'))
        }
        return base(path, method, init)
      },
      { me: meWithRole('admin') },
    )

    const publish = await screen.findByRole('button', { name: 'Veroeffentlichen' })
    expect(publish).toBeEnabled()

    fireEvent.click(publish)

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Version aktiviert.')
    })
    expect(transitionBodies[0]).toContain('"to":"active"')
  })

  it('Review (kein Admin): Publish ist gesperrt, "Zurueck zu Draft" lehnt ab', async () => {
    const transitionBodies: string[] = []
    const base = playbookHandlers({ versions: [pbVersion(1, 'review')] })
    renderPlaybookDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/playbooks/pb1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(pbVersion(1, 'draft'))
      }
      return base(path, method, init)
    })

    const publish = await screen.findByRole('button', { name: 'Veroeffentlichen' })
    expect(publish).toBeDisabled()
    expect(publish).toHaveAttribute('title', 'Nur Admins können aktivieren')

    fireEvent.click(screen.getByRole('button', { name: 'Zurueck zu Draft' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Review abgelehnt.')
    })
    expect(transitionBodies[0]).toContain('"to":"draft"')
  })

  it('Inactive: "Reaktivieren als Draft" reaktiviert die aktuelle Version', async () => {
    const transitionBodies: string[] = []
    const base = playbookHandlers({
      playbook: playbookWith({ current_status: 'inactive' }),
      versions: [pbVersion(1, 'inactive')],
    })
    renderPlaybookDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/playbooks/pb1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(pbVersion(1, 'draft'))
      }
      return base(path, method, init)
    })

    expect(await screen.findByText('Inaktiv: v1')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reaktivieren als Draft' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Reaktiviert als Entwurf.')
    })
    expect(transitionBodies[0]).toContain('"to":"draft"')
  })

  it('meldet den Fehler per Toast, wenn die Transition fehlschlaegt', async () => {
    const base = playbookHandlers()
    renderPlaybookDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/playbooks/pb1/versions/1/transition`) {
        return errorResponse(500, 'Transition kaputt')
      }
      return base(path, method, init)
    })

    fireEvent.click(
      await screen.findByRole('button', { name: 'Draft abschliessen' }),
    )

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Transition kaputt')
    })
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('Active + Draft: Banner nennt beide Versionen, Submit-Action bleibt sichtbar', async () => {
    renderPlaybookDetail(
      playbookHandlers({
        playbook: playbookWith({ current_version: 2 }),
        versions: [pbVersion(1, 'active'), pbVersion(2, 'draft')],
      }),
    )

    expect(await screen.findByText('Aktiv: v1')).toBeInTheDocument()
    expect(screen.getByText('Entwurf: v2')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Draft abschliessen' }),
    ).toBeInTheDocument()
  })

  it('Active + Review: Banner nennt die Review-Version, Publish + Reject sichtbar', async () => {
    renderPlaybookDetail(
      playbookHandlers({
        playbook: playbookWith({ current_version: 2 }),
        versions: [pbVersion(1, 'active'), pbVersion(2, 'review')],
      }),
    )

    expect(await screen.findByText('Aktiv: v1')).toBeInTheDocument()
    expect(screen.getByText('v2 wartet auf Review')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Veroeffentlichen' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Zurueck zu Draft' })).toBeInTheDocument()
  })

  it('nur Active (ohne Draft/Review): Hero-Chip statt Banner, keine Branch-Aktionen', async () => {
    renderPlaybookDetail(
      playbookHandlers({
        playbook: playbookWith({ current_status: 'active' }),
        versions: [pbVersion(1, 'active')],
      }),
    )

    expect(await screen.findByText('Aktiv · v1')).toBeInTheDocument()
    expect(screen.queryByTestId('review-banner')).not.toBeInTheDocument()
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
  })
})

describe('PlaybookDetailPage — Versions-Insel & Feedback', () => {
  it('Restore stellt die Version als Draft wieder her, Diff/Provenance laden lazy', async () => {
    const calledPaths: string[] = []
    const base = playbookHandlers({
      playbook: playbookWith({ current_status: 'inactive' }),
      versions: [pbVersion(1, 'inactive')],
    })
    renderPlaybookDetail(
      (path, method, init) => {
        if (method === 'GET' && path === `${WS_PREFIX}/playbooks/pb1/versions/1/diff`) {
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
          path === `${WS_PREFIX}/playbooks/pb1/versions/1/provenance`
        ) {
          calledPaths.push(path)
          return jsonResponse([])
        }
        if (
          method === 'POST' &&
          path === `${WS_PREFIX}/playbooks/pb1/versions/1/restore`
        ) {
          calledPaths.push(path)
          return jsonResponse(playbook(1, 'b1'))
        }
        return base(path, method, init)
      },
      { me: meWithRole('editor') },
    )

    // Versions-Insel lebt im Tab „Versionen" — erst umschalten.
    fireEvent.click(await screen.findByRole('tab', { name: 'Versionen' }))

    fireEvent.click(screen.getByRole('button', { name: 'Diff' }))
    await waitFor(() => {
      expect(calledPaths).toContain(`${WS_PREFIX}/playbooks/pb1/versions/1/diff`)
    })

    fireEvent.click(screen.getByRole('button', { name: 'Verlauf' }))
    await waitFor(() => {
      expect(calledPaths).toContain(
        `${WS_PREFIX}/playbooks/pb1/versions/1/provenance`,
      )
    })

    fireEvent.click(screen.getByRole('button', { name: 'Wiederherstellen' }))
    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith(
        'v1 als Entwurf wiederhergestellt.',
      )
    })
    expect(calledPaths).toContain(`${WS_PREFIX}/playbooks/pb1/versions/1/restore`)
  })
})

describe('PlaybookDetailPage — Managed-Lock & Rollen', () => {
  it('is_managed: zeigt die Managed-Notice und blendet Aktionen + Danger-Zone aus', async () => {
    renderPlaybookDetail(
      playbookHandlers({ playbook: playbookWith({ is_managed: true }) }),
    )

    expect(await screen.findByTestId('managed-notice')).toBeInTheDocument()
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
    expect(screen.queryByTestId('delete-playbook-trigger')).not.toBeInTheDocument()
  })

  it('ohne Managed-Flag: keine Notice, Branch-Aktionen und Danger-Zone sichtbar', async () => {
    renderPlaybookDetail(playbookHandlers())

    // Danger-Zone ist als dezente Zeile kollabiert — erst aufklappen.
    const dangerToggle = await screen.findByRole('button', { name: 'Playbook löschen' })
    expect(screen.queryByTestId('delete-playbook-trigger')).not.toBeInTheDocument()
    fireEvent.click(dangerToggle)

    expect(await screen.findByTestId('delete-playbook-trigger')).toBeInTheDocument()
    expect(screen.queryByTestId('managed-notice')).not.toBeInTheDocument()
    expect(
      screen.getByRole('toolbar', { name: 'Branch-Aktionen' }),
    ).toBeInTheDocument()
  })

  it('Viewer: sieht weder Danger-Zone noch Feedback-Panel', async () => {
    renderPlaybookDetail(playbookHandlers(), { me: meWithRole('viewer') })

    await screen.findByText('Verwendet in')
    expect(screen.queryByTestId('delete-playbook-trigger')).not.toBeInTheDocument()
    expect(screen.queryByText('Feedback & Nutzung')).not.toBeInTheDocument()
    // Der „Feedback geben"-Trigger ist auf Editor+ beschränkt.
    expect(
      screen.queryByRole('button', { name: 'Feedback geben' }),
    ).not.toBeInTheDocument()
  })

  it('Editor: zeigt den „Feedback geben"-Trigger in den Header-Aktionen', async () => {
    renderPlaybookDetail(playbookHandlers(), { me: meWithRole('editor') })

    expect(
      await screen.findByRole('button', { name: 'Feedback geben' }),
    ).toBeInTheDocument()
  })
})

describe('PlaybookDetailPage — Composite-, Tag- und Link-Zweige', () => {
  it('Composite: zeigt den Ausfuehrungs-Flow und Composed-by-Backlinks im Beziehungen-Tab', async () => {
    renderPlaybookDetail(
      playbookHandlers({
        playbook: playbookWith({ is_composite: true }),
        composes: [
          { id: 'c1', name: 'Schritt Eins', is_composite: false },
          { id: 'c2', name: 'Verschachtelt', is_composite: true },
        ],
        composedBy: [{ id: 'p9', name: 'Eltern-Composite' }],
      }),
    )

    fireEvent.click(await screen.findByRole('tab', { name: 'Beziehungen' }))
    await screen.findByText('Sub-Playbooks (Composes)')

    const list = screen.getByRole('list', { name: 'Sub-Playbooks' })
    const items = within(list).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Schritt Eins')
    expect(items[1]).toHaveTextContent('Verschachtelt')
    // Kinder sind Links auf ihre Detail-Seite.
    expect(within(list).getByRole('link', { name: /Schritt Eins/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/playbooks/c1'),
    )

    expect(screen.getByText('Eltern-Composite')).toBeInTheDocument()
  })

  it('Leer-Zweige: kein Composite-Badge, keine Tags/Trigger, Empty-Hinweise', async () => {
    renderPlaybookDetail(
      playbookHandlers({
        playbook: playbookWith({
          tags: [],
          content: { ...playbook(1, 'b1').content, tags: [] },
        }),
      }),
    )

    expect(
      await screen.findByText(
        'Keine Sub-Playbooks verknüpft. Dieses Playbook ist atomar.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Kein Composite-Playbook referenziert dieses Playbook.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Composite')).not.toBeInTheDocument()
    // Kein Header-Tag-Cluster (das TagInput-Formularfeld traegt weiterhin
    // sein eigenes "Tags"-Label und bleibt bewusst unberuehrt).
    expect(
      screen.queryAllByLabelText('Tags').filter((el) => el.tagName === 'DIV'),
    ).toHaveLength(0)
    expect(
      screen.queryByRole('list', { name: 'Trigger-Liste' }),
    ).not.toBeInTheDocument()
  })

  it('Resource-Links: rendert verlinkte Bloecke read-only mit Body-Hinweis', async () => {
    renderPlaybookDetail(
      playbookHandlers({
        resourceLinks: [
          {
            resource_id: 'r1',
            resource_name: 'Glossar',
            block_id: 'b1',
            position: 0,
            available: true,
            preview: 'Abschnitt A',
          },
        ],
      }),
    )

    expect(await screen.findByText('Glossar')).toBeInTheDocument()
    expect(screen.getByText('Abschnitt A')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Resource-Verknüpfungen werden im BlockNote-Body als Pills gepflegt — bearbeite sie dort.',
      ),
    ).toBeInTheDocument()
    // Track B: Pills im Body sind die Quelle — kein Entfernen-Button.
    expect(
      screen.queryByRole('button', { name: 'Entfernen' }),
    ).not.toBeInTheDocument()
  })
})

describe('PlaybookDetailPage — Delete-Flow', () => {
  it('loescht nach Bestaetigung und navigiert zurueck zur Liste', async () => {
    const base = playbookHandlers()
    renderPlaybookDetail((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/playbooks/pb1`) {
        return new Response(null, { status: 204 })
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Playbook löschen' }))
    fireEvent.click(await screen.findByTestId('delete-playbook-trigger'))
    fireEvent.click(await screen.findByTestId('delete-playbook-confirm'))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Playbook gelöscht.')
    })
    expect(await screen.findByText('PLAYBOOKS-LISTE')).toBeInTheDocument()
  })

  it('409 DeleteBlocked: listet die Verwender und sperrt den Confirm-Button', async () => {
    const base = playbookHandlers()
    renderPlaybookDetail((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/playbooks/pb1`) {
        return new Response(
          JSON.stringify({
            detail: {
              message: 'Wird noch verwendet',
              blocked_by: {
                personas: [{ persona_id: 'per1', persona_name: 'Blocker Persona' }],
              },
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return base(path, method, init)
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Playbook löschen' }))
    fireEvent.click(await screen.findByTestId('delete-playbook-trigger'))
    fireEvent.click(await screen.findByTestId('delete-playbook-confirm'))

    expect(await screen.findByText('Löschen blockiert')).toBeInTheDocument()
    expect(screen.getByText(/Blocker Persona/)).toBeInTheDocument()
    expect(screen.getByTestId('delete-playbook-confirm')).toBeDisabled()
    expect(notify.success).not.toHaveBeenCalled()
  })
})
