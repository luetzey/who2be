
import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, VersionStatus, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'
import { PersonaDetailPage } from './PersonaDetailPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel mocken — sie kann nicht in jsdom mounten (ProseMirror).
// Damit der Persona-Editor (BlockNote-Profil) in diesem Page-Test sauber
// rendert, stuben wir die Insel-Module + den Theme-Context, der die
// Insel hochzieht.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))
// Track F: der pill-faehige Profil-Editor zieht das volle BlockNote-Custom-
// Schema hoch (createReactInlineContentSpec). Im Page-Test stuben wir ihn,
// damit nur das Page-Verhalten geprueft wird, nicht die BlockNote-Insel.
vi.mock('@/features/personas/components/PersonaProfileEditor', () => ({
  PersonaProfileEditor: () => <div data-testid="blocknote-view" />,
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}
const WS_PREFIX = '/v1/workspaces/ws-1'

interface PersonaShape {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  current_version: number
  content: { description: string; system_prompt: string; traits: string[] }
  created_at: string
  updated_at: string
  is_managed?: boolean
}

function persona(version: number, systemPrompt: string): PersonaShape {
  return {
    id: 'p1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Coach',
    current_version: version,
    content: { description: 'd', system_prompt: systemPrompt, traits: [] },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

function route(method: string, url: string): string {
  return `${method} ${url}`
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('PersonaDetailPage', () => {
  it('Auto-Save: Aenderungen feuern einen PATCH-Draft, kein PUT mehr', async () => {
    const v1 = {
      version: 1,
      status: 'draft',
      content: persona(1, 's1').content,
      created_by: 'o1',
      created_at: 't1',
    }
    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(persona(1, 's1')),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([v1]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([]),
    }

    const patchCalls: Array<{ url: string; body: unknown }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      const pathname = new URL(url).pathname
      if (method === 'PATCH' && pathname.endsWith('/personas/p1/draft')) {
        patchCalls.push({ url, body: JSON.parse(init?.body as string) })
        return jsonResponse(persona(1, 's1'))
      }
      const key = route(method, pathname)
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // WICHTIG: warten bis form.reset(persona) durchgelaufen ist und das Name-
    // Feld den geladenen Wert "Coach" enthaelt. Sonst feuert fireEvent.change
    // gegen ein noch leeres Default-Input und der spaeter eintreffende reset
    // ueberschreibt die Aenderung — PATCH wird nie ausgeloest (CI-Flake
    // beobachtet in PR #79).
    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toHaveValue('Coach')
    })
    expect(
      screen.queryByRole('button', { name: 'Neue Version speichern' }),
    ).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Coach v2' } })
    // Auto-Save-Debounce ist 1500 ms; lokal ~1.6s, aber CI-Runner mit
    // jsdom-Overhead haben sowohl das 3s- als auch das 5s-Limit gerissen
    // (siehe PR #79). 8s ist grosszuegig, der it()-Timeout unten ist auf
    // 15s gehoben.
    await waitFor(
      () => {
        expect(patchCalls.length).toBeGreaterThanOrEqual(1)
      },
      { timeout: 8000 },
    )
    expect((patchCalls[patchCalls.length - 1].body as { name: string }).name).toBe(
      'Coach v2',
    )
    const putCalls = fetchMock.mock.calls.filter(
      (call) =>
        (call[1] as RequestInit | undefined)?.method === 'PUT' &&
        String(call[0]).endsWith('/personas/p1'),
    )
    expect(putCalls).toHaveLength(0)
  }, 15_000)

  it('verknuepft Playbooks via PUT auf /personas/:id/playbooks', async () => {
    const pb1 = {
      id: 'pb1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Coaching',
      current_version: 1,
      type: 'workflow',
      tags: [],
      triggers: null,
      content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
      created_at: 't',
      updated_at: 't',
    }
    const pb2 = { ...pb1, id: 'pb2', name: 'Brainstorming' }

    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(persona(1, 's1')),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([pb1]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([pb1, pb2]),
    }

    const putCalls: Array<{ url: string; body: unknown }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      if (method === 'PUT' && url.endsWith(`${WS_PREFIX}/personas/p1/playbooks`)) {
        putCalls.push({ url, body: JSON.parse(init?.body as string) })
        return jsonResponse([pb1, pb2])
      }
      const key = route(method, new URL(url).pathname)
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // WP-E: Playbooks liegen jetzt im „Playbooks"-Tab; Anzeige-Modus default —
    // verknuepftes Playbook als Link, der Picker liegt hinter „Verknüpfungen
    // bearbeiten".
    fireEvent.click(await screen.findByRole('tab', { name: 'Playbooks' }))
    expect(await screen.findByRole('link', { name: 'Coaching' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))

    const checkbox2 = await screen.findByLabelText('Brainstorming')
    fireEvent.click(checkbox2)
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen speichern' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Verknüpfungen gespeichert.')
    })
    expect(putCalls).toHaveLength(1)
    expect(putCalls[0].body).toEqual({ playbook_ids: ['pb1', 'pb2'] })
    // Nach dem Speichern: zurueck im Anzeige-Modus, beide Playbooks verlinkt.
    expect(await screen.findByRole('link', { name: 'Brainstorming' })).toBeInTheDocument()
  })

  it('Abbrechen verwirft lokale Auswahl-Aenderungen (WP-E)', async () => {
    const pb1 = {
      id: 'pb1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Coaching',
      current_version: 1,
      type: 'workflow',
      tags: [],
      triggers: null,
      content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
      created_at: 't',
      updated_at: 't',
    }
    const pb2 = { ...pb1, id: 'pb2', name: 'Brainstorming' }

    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(persona(1, 's1')),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([pb1]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([pb1, pb2]),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const key = route(method, new URL(String(input)).pathname)
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    fireEvent.click(await screen.findByRole('tab', { name: 'Playbooks' }))
    fireEvent.click(
      await screen.findByRole('button', { name: 'Verknüpfungen bearbeiten' }),
    )
    fireEvent.click(await screen.findByLabelText('Brainstorming'))
    expect(screen.getByLabelText('Brainstorming')).toBeChecked()

    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))

    // Zurueck im Anzeige-Modus: kein PUT gefeuert, nur pb1 verlinkt.
    expect(screen.getByRole('link', { name: 'Coaching' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Brainstorming' })).not.toBeInTheDocument()

    // Erneutes Oeffnen: die verworfene Auswahl ist weg.
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))
    expect(screen.getByLabelText('Brainstorming')).not.toBeChecked()
    expect(screen.getByLabelText('Coaching')).toBeChecked()
    const putCalls = fetchMock.mock.calls.filter(
      (call) => (call[1] as RequestInit | undefined)?.method === 'PUT',
    )
    expect(putCalls).toHaveLength(0)
  })

  it('Modi liegen in einem eigenen Tab und teilen die Form des Bearbeiten-Tabs', async () => {
    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(persona(1, 's1')),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([]),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const key = route(method, new URL(String(input)).pathname)
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // Bearbeiten-Tab (Default): Profil-Felder, kein Modi-Editor.
    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toHaveValue('Coach')
    })
    expect(
      screen.queryByRole('button', { name: 'Ersten Modus anlegen' }),
    ).not.toBeInTheDocument()

    // In den Modi-Tab wechseln: der Modi-Editor erscheint.
    fireEvent.click(screen.getByRole('tab', { name: 'Modi' }))
    expect(
      await screen.findByRole('button', { name: 'Ersten Modus anlegen' }),
    ).toBeInTheDocument()
  })

  it('vom System verwaltet: Notice + read-only, keine Status-/Lösch-Aktionen', async () => {
    const managed: PersonaShape = { ...persona(1, 's1'), is_managed: true }
    // Draft-Version => ohne Lock erschiene der „Draft abschliessen"-Button.
    const v1 = {
      version: 1,
      status: 'draft',
      content: persona(1, 's1').content,
      created_by: 'o1',
      created_at: 't1',
    }
    const handlers: Record<string, () => Response> = {
      [route('GET', `${WS_PREFIX}/personas/p1`)]: () => jsonResponse(managed),
      [route('GET', `${WS_PREFIX}/personas/p1/versions`)]: () => jsonResponse([v1]),
      [route('GET', `${WS_PREFIX}/personas/p1/playbooks`)]: () => jsonResponse([]),
      [route('GET', `${WS_PREFIX}/playbooks`)]: () => jsonResponse([]),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const key = route(method, new URL(String(input)).pathname)
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toHaveValue('Coach')
    })
    // Managed-Notice sichtbar.
    expect(screen.getByTestId('managed-notice')).toBeInTheDocument()
    // Editor read-only: Name-Feld gesperrt.
    expect(screen.getByLabelText('Name')).toBeDisabled()
    // Keine Status-Aktion trotz vorhandener Draft-Version.
    expect(
      screen.queryByRole('button', { name: 'Draft abschliessen' }),
    ).not.toBeInTheDocument()
    // Kein Lösch-Bereich (Danger-Zone liegt im „Versionen"-Tab, fuer managed
    // ohnehin ausgeblendet).
    expect(screen.queryByText('Persona löschen')).not.toBeInTheDocument()
    // Playbook-Verknuepfung: in den „Playbooks"-Tab wechseln — nur Anzeige-
    // Modus, kein Bearbeiten-Button (WP-E).
    fireEvent.click(screen.getByRole('tab', { name: 'Playbooks' }))
    expect(
      screen.queryByRole('button', { name: 'Verknüpfungen bearbeiten' }),
    ).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Branch-Coverage-Ergaenzungen (Coverage-Nachrunde): Redirect ohne :id,
// Status-Transitions (draft/review/active/inactive) inkl. Fehlerpfade,
// Header-Beschreibungs-Zweige, Admin-/Editor-/Viewer-Rollen. Muster analog
// PlaybookDetailPage.test.tsx / ResourceDetailPage.test.tsx.
// Bestandstests oben bleiben unangetastet.
// ---------------------------------------------------------------------------

type FetchHandler = (
  path: string,
  method: string,
  init?: RequestInit,
) => Response | Promise<Response>

function errorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function personaWith(
  overrides: Partial<PersonaShape> & Record<string, unknown> = {},
): PersonaShape & Record<string, unknown> {
  return { ...persona(1, 's1'), ...overrides }
}

function pVersion(v: number, status: VersionStatus) {
  return {
    version: v,
    status,
    content: persona(v, 's1').content,
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

interface PersonaHandlerOptions {
  persona?: Record<string, unknown>
  versions?: unknown[]
}

function personaHandlers(opts: PersonaHandlerOptions = {}): FetchHandler {
  return (path, method) => {
    if (method === 'GET') {
      if (path === `${WS_PREFIX}/personas/p1`)
        return jsonResponse(opts.persona ?? persona(1, 's1'))
      if (path === `${WS_PREFIX}/personas/p1/versions`)
        return jsonResponse(opts.versions ?? [pVersion(1, 'draft')])
      if (path === `${WS_PREFIX}/personas/p1/playbooks`) return jsonResponse([])
      if (path === `${WS_PREFIX}/playbooks`) return jsonResponse([])
      if (path === `${WS_PREFIX}/feedback/persona/p1`)
        return jsonResponse({
          entity_type: 'persona',
          entity_id: 'p1',
          usage_count: 0,
          by_outcome: {},
          by_signal: {},
          recent_notes: [],
        })
    }
    throw new Error(`Unmocked ${method} ${path}`)
  }
}

function renderPersonaDetail(handler: FetchHandler, options: { me?: Me } = {}) {
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
        <MemoryRouter initialEntries={['/w/ws-1/personas/p1']}>
          <Routes>
            <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
            <Route path="/w/:workspaceId/personas" element={<div>PERSONAE-LISTE</div>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
  return fetchMock
}

describe('PersonaDetailPage — Redirect & Status-Transitions', () => {
  it('leitet ohne :id-Routenparameter zur Personae-Liste um', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse([])),
    )
    render(
      <SessionContext.Provider
        value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/persona-detail']}>
            <Routes>
              <Route path="/w/:workspaceId/persona-detail" element={<PersonaDetailPage />} />
              <Route path="/w/:workspaceId/personas" element={<div>PERSONAE-LISTE</div>} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    expect(await screen.findByText('PERSONAE-LISTE')).toBeInTheDocument()
  })

  it('Draft: "Draft abschliessen" reicht die Version zur Review ein', async () => {
    const transitionBodies: string[] = []
    const base = personaHandlers()
    renderPersonaDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/personas/p1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(pVersion(1, 'review'))
      }
      return base(path, method, init)
    })

    expect(
      await screen.findByText('Aktuelle Version: v1 (Entwurf)'),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Draft abschliessen' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Zur Review eingereicht.')
    })
    expect(transitionBodies[0]).toContain('"to":"review"')
  })

  it('Active + Review (Admin): Header nennt beide, "Veroeffentlichen" aktiviert', async () => {
    const transitionBodies: string[] = []
    const base = personaHandlers({
      persona: personaWith({ current_version: 2 }),
      versions: [pVersion(1, 'active'), pVersion(2, 'review')],
    })
    renderPersonaDetail(
      (path, method, init) => {
        if (method === 'POST' && path === `${WS_PREFIX}/personas/p1/versions/2/transition`) {
          transitionBodies.push(String(init?.body))
          return jsonResponse(pVersion(2, 'active'))
        }
        return base(path, method, init)
      },
      { me: meWithRole('admin') },
    )

    expect(await screen.findByText(/Active: v1 · In Review: v2/)).toBeInTheDocument()

    const publish = screen.getByRole('button', { name: 'Veroeffentlichen' })
    expect(publish).toBeEnabled()

    fireEvent.click(publish)

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Version aktiviert.')
    })
    expect(transitionBodies[0]).toContain('"to":"active"')
  })

  it('Review (kein Admin): Publish ist gesperrt, "Zurueck zu Draft" lehnt ab', async () => {
    const transitionBodies: string[] = []
    const base = personaHandlers({ versions: [pVersion(1, 'review')] })
    renderPersonaDetail(
      (path, method, init) => {
        if (method === 'POST' && path === `${WS_PREFIX}/personas/p1/versions/1/transition`) {
          transitionBodies.push(String(init?.body))
          return jsonResponse(pVersion(1, 'draft'))
        }
        return base(path, method, init)
      },
      { me: meWithRole('editor') },
    )

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
    const base = personaHandlers({
      persona: personaWith({ current_status: 'inactive' }),
      versions: [pVersion(1, 'inactive')],
    })
    renderPersonaDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/personas/p1/versions/1/transition`) {
        transitionBodies.push(String(init?.body))
        return jsonResponse(pVersion(1, 'draft'))
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

  it('meldet die Server-Message per Toast, wenn die Transition fehlschlaegt', async () => {
    const base = personaHandlers()
    renderPersonaDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/personas/p1/versions/1/transition`) {
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

  it('faellt bei Nicht-Error-Ursachen auf die generische Fehlermeldung zurueck', async () => {
    const base = personaHandlers()
    renderPersonaDetail((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/personas/p1/versions/1/transition`) {
        return jsonResponse(pVersion(1, 'review'))
      }
      return base(path, method, init)
    })

    // Non-Error-Rejection im try-Block: der Success-Toast wirft einen String.
    vi.mocked(notify.success).mockImplementationOnce(() => {
      throw 'kaputt'
    })

    fireEvent.click(
      await screen.findByRole('button', { name: 'Draft abschliessen' }),
    )

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Aktion fehlgeschlagen.')
    })
  })
})

describe('PersonaDetailPage — Header-Beschreibung & Rollen', () => {
  it('Active + Draft: Header nennt beide Versionen, Submit-Action sichtbar', async () => {
    renderPersonaDetail(
      personaHandlers({
        persona: personaWith({ current_version: 2 }),
        versions: [pVersion(1, 'active'), pVersion(2, 'draft')],
      }),
    )

    expect(
      await screen.findByText(/Active: v1 · Du arbeitest auf Draft v2/),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Draft abschliessen' }),
    ).toBeInTheDocument()
  })

  it('nur Active (ohne Draft/Review): Header ohne Suffix, keine Branch-Aktionen', async () => {
    renderPersonaDetail(
      personaHandlers({
        persona: personaWith({ current_status: 'active' }),
        versions: [pVersion(1, 'active')],
      }),
    )

    // Nur-Active ohne Handlungsbedarf: kein Attention-Banner; der Status steht
    // als Badge im DetailHeader, es gibt keine Branch-Aktionen.
    expect(await screen.findByRole('heading', { name: 'Coach' })).toBeInTheDocument()
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Draft abschliessen' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
  })

  it('Viewer: sieht weder Feedback-Panel noch Danger-Zone', async () => {
    renderPersonaDetail(personaHandlers(), { me: meWithRole('viewer') })

    fireEvent.click(await screen.findByRole('tab', { name: 'Playbooks' }))
    expect(await screen.findByText('Verknüpfte Playbooks')).toBeInTheDocument()
    expect(screen.queryByText('Feedback & Nutzung')).not.toBeInTheDocument()
    expect(screen.queryByText('Persona löschen')).not.toBeInTheDocument()
    // WP-E: Viewer sieht keinen Bearbeiten-Button an der Playbooks-Karte.
    expect(
      screen.queryByRole('button', { name: 'Verknüpfungen bearbeiten' }),
    ).not.toBeInTheDocument()
  })
})
