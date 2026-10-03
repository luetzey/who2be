import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryEventRead, MemoryRead, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { MemoryList } from '@/components/memory/MemoryList'
import { entryFiltersFrom, type MemoryEntriesData } from '@/features/memory/hooks/useMemoryApi'
import { MemoryPage } from '@/features/memory/pages/MemoryPage'
import { axe } from '@/test/a11y'

// Detail-Sheet (C5c-1, Gedaechtnisverwaltung §7/§16): Rollback mit
// `event_id`, Loeschtext mit Verlauf, „Wieder aktivieren“ nur bei `expired`,
// fremdes Nutzergedaechtnis nie sichtbar, Chevron nur mit `detailLinks`.
// Deep-Link ueber den Einzelabruf: nur 404 ist „nicht gefunden“, ein
// Netz-/Serverfehler ist eine Fehlermeldung mit Retry (t_b6bfcb87).

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

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

function buildMe(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Acme',
        slug: 'acme',
        kind: 'company',
        workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role }],
      },
    ],
  }
}

function memory(overrides: Partial<MemoryRead> = {}): MemoryRead {
  return {
    id: 'm1',
    agent_id: 'a1',
    status: 'active',
    fact: 'Nutzt uv statt pip.',
    context: 'Nutzer sagte: nimm uv',
    category: 'preference',
    importance: 6,
    source: 'agent',
    triage_note: null,
    retrieval_count: 7,
    last_retrieved_at: '2026-10-02T14:02:00Z',
    created_at: '2026-10-01T09:12:00Z',
    updated_at: '2026-10-01T09:12:00Z',
    kind: 'agent_note',
    scope: 'agent',
    subject_user_id: null,
    origin: 'user_stated',
    created_by_agent_id: 'a1',
    confirmed_at: '2026-10-01T10:00:00Z',
    expires_at: null,
    ...overrides,
  }
}

function event(overrides: Partial<MemoryEventRead>): MemoryEventRead {
  return {
    id: 'e1',
    memory_id: 'm1',
    event: 'created',
    actor_kind: 'agent',
    actor_id: null,
    agent_id: 'a1',
    before: null,
    after: { fact: 'Nutzt pip.', status: 'pending', kind: 'agent_note', origin: 'user_stated' },
    reason: null,
    created_at: '2026-09-12T08:00:00Z',
    ...overrides,
  }
}

// Aelteste zuerst (wie die API): angelegt → freigegeben → bearbeitet.
const HISTORY: MemoryEventRead[] = [
  event({ id: 'e1' }),
  event({
    id: 'e2',
    event: 'approved',
    actor_kind: 'human',
    actor_id: 'u2',
    agent_id: null,
    before: { fact: 'Nutzt pip.', status: 'pending' },
    after: { fact: 'Nutzt pip.', status: 'active' },
    created_at: '2026-09-12T09:00:00Z',
  }),
  event({
    id: 'e3',
    event: 'edited',
    actor_kind: 'human',
    actor_id: 'u1',
    agent_id: null,
    before: { fact: 'Nutzt pip.', status: 'active', category: 'preference', importance: 6 },
    after: { fact: 'Nutzt uv statt pip.', status: 'active', category: 'preference', importance: 6 },
    created_at: '2026-09-13T09:00:00Z',
  }),
]

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

interface Call {
  method: string
  path: string
  body: Record<string, unknown> | null
}

// Antwort des Einzelabrufs `GET /memories/{id}`: Response, Funktion (je Aufruf)
// oder `undefined` = Eintrag aus `items` bzw. 404 `memory_not_found`.
type DetailStub = Response | ((attempt: number) => Response | Promise<Response>)

function notFound(): Response {
  return jsonResponse({ detail: 'Memory nicht gefunden.', reason: 'memory_not_found' }, 404)
}

function stubApi({
  items = [memory()],
  history = HISTORY,
  detail,
}: { items?: MemoryRead[]; history?: MemoryEventRead[] | Response; detail?: DetailStub } = {}) {
  const calls: Call[] = []
  let detailAttempts = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const parsed = new URL(String(input), 'http://x')
      const path = parsed.pathname
      const method = init?.method ?? 'GET'
      const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : null
      calls.push({ method, path, body })
      if (method === 'DELETE') return new Response(null, { status: 204 })
      if (path.endsWith('/history')) {
        return history instanceof Response ? history : jsonResponse(history)
      }
      if (path.endsWith('/rollback')) {
        return jsonResponse(memory({ fact: 'Nutzt pip.' }))
      }
      if (path.endsWith('/reactivate')) return jsonResponse(memory({ status: 'active' }))
      if (method === 'PUT') return jsonResponse(memory({ fact: String(body?.fact) }))
      if (path.endsWith('/memories/counts')) return jsonResponse({ total: items.length })
      const single = /^\/v1\/workspaces\/[^/]+\/memories\/([^/]+)$/.exec(path)
      if (single !== null) {
        detailAttempts += 1
        if (detail instanceof Response) return detail
        if (detail !== undefined) return detail(detailAttempts)
        const hit = items.find((item) => item.id === single[1])
        return hit !== undefined ? jsonResponse(hit) : notFound()
      }
      if (path.endsWith('/memories')) return jsonResponse({ items, next_cursor: null })
      if (path.endsWith('/members')) {
        return jsonResponse([
          { user_id: 'u2', email: 'lutz@example.com', role: 'admin', joined_at: '' },
        ])
      }
      if (path.endsWith('/agents')) {
        return jsonResponse([{ id: 'a1', name: 'researcher', tool_policy: {} }])
      }
      return jsonResponse([])
    }),
  )
  return { calls }
}

function renderPage(entry: string, role: WorkspaceRole = 'editor') {
  return render(
    <Providers role={role}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/w/:workspaceId/memory" element={<MemoryPage />} />
        </Routes>
      </MemoryRouter>
    </Providers>,
  )
}

function Providers({ role = 'editor', children }: { role?: WorkspaceRole; children: ReactNode }) {
  return (
    <SessionContext.Provider
      value={{
        session,
        me: buildMe(role),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn().mockResolvedValue(undefined),
      }}
    >
      <AuthTokenProvider>{children}</AuthTokenProvider>
    </SessionContext.Provider>
  )
}

const ENTRY = '/w/ws-1/memory?tab=entries&entry=m1'
const DETAIL_PATH = '/v1/workspaces/ws-1/memories/m1'

async function openSheet(entry = ENTRY) {
  renderPage(entry)
  const sheet = await screen.findByTestId('memory-detail-sheet')
  await within(sheet).findByTestId('detail-fact')
  return sheet
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

describe('MemoryDetailSheet (C5c-1)', () => {
  it('zeigt Herkunft getrennt nach Kanal und „Laut Agent“, Auslieferung und Verlauf neueste zuerst', async () => {
    stubApi()
    const sheet = await openSheet()
    expect(within(sheet).getByTestId('detail-fact')).toHaveTextContent('Nutzt uv statt pip.')
    expect(within(sheet).getByText('Agent researcher (vom Server)')).toBeInTheDocument()
    expect(within(sheet).getByTestId('detail-origin')).toHaveTextContent('Von dir gesagt')
    expect(within(sheet).getByTestId('detail-delivery')).toHaveTextContent('7× ausgeliefert')
    const items = await within(sheet).findAllByTestId('history-item')
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining('Bearbeitet'),
      expect.stringContaining('Freigegeben'),
      expect.stringContaining('Vorgeschlagen'),
    ])
    expect(items[0]).toHaveTextContent('von dir')
    expect(await within(items[1]).findByText('von lutz@example.com')).toBeInTheDocument()
    expect(within(items[2]).getByText('von researcher')).toBeInTheDocument()
  })

  it('lässt lange Werte ohne Leerzeichen in der Herkunft umbrechen statt überlaufen', async () => {
    // jsdom rechnet kein Layout: geprüft werden die Klassen, die den
    // Overflow im Browser verhindern (Messung 1280: dd lief bis x=1627).
    stubApi()
    const sheet = await openSheet()
    const dl = within(sheet).getByTestId('detail-provenance')
    expect(dl.className).toContain('sm:grid-cols-[auto_minmax(0,1fr)]')
    for (const dd of Array.from(dl.querySelectorAll('dd'))) {
      expect(dd).toHaveClass('min-w-0')
    }
    expect(within(sheet).getByText('Nutzer sagte: nimm uv')).toHaveClass('wrap-anywhere')
  })

  it('sendet beim Rollback die gewählte event_id und zeigt den Diff „jetzt → danach“', async () => {
    const { calls } = stubApi()
    const sheet = await openSheet()
    const items = await within(sheet).findAllByTestId('history-item')
    // Kein Knopf ohne Vorzustand (`created`): nur e3 (Fakt) und e2 (Status).
    expect(within(items[2]).queryByTestId('restore-before')).toBeNull()
    expect(within(sheet).getAllByTestId('restore-before')).toHaveLength(2)
    fireEvent.click(within(items[0]).getByTestId('restore-before'))
    const dialog = await screen.findByRole('dialog', { name: /Stand vor dieser Änderung/ })
    expect(within(dialog).getByTestId('restore-preview')).toHaveTextContent(
      'Vorher: Nutzt uv statt pip.. Nachher: Nutzt pip..',
    )
    fireEvent.click(within(dialog).getByRole('button', { name: 'Wiederherstellen' }))
    await waitFor(() => {
      const rollback = calls.find((call) => call.path.endsWith('/rollback'))
      expect(rollback?.path).toBe('/v1/workspaces/ws-1/agents/a1/memories/m1/rollback')
      expect(rollback?.body).toEqual({ event_id: 'e3' })
    })
  })

  it('zeigt keinen toten Wiederherstellen-Knopf, wenn der Vorzustand dem aktuellen gleicht', async () => {
    stubApi({
      history: [
        event({
          id: 'e5',
          event: 'confirmed',
          actor_kind: 'human',
          actor_id: 'u1',
          before: { fact: 'Nutzt uv statt pip.', status: 'active' },
          after: { fact: 'Nutzt uv statt pip.', status: 'active' },
        }),
      ],
    })
    const sheet = await openSheet()
    await within(sheet).findAllByTestId('history-item')
    expect(within(sheet).queryByTestId('restore-before')).toBeNull()
  })

  it('zeigt einen Statuswechsel im Rollback-Dialog', async () => {
    stubApi({
      history: [
        event({
          id: 'e9',
          event: 'approved',
          actor_kind: 'human',
          actor_id: 'u1',
          before: { fact: 'Nutzt uv statt pip.', status: 'pending' },
          after: { fact: 'Nutzt uv statt pip.', status: 'active' },
        }),
      ],
    })
    const sheet = await openSheet()
    fireEvent.click(await within(sheet).findByTestId('restore-before'))
    const dialog = await screen.findByRole('dialog', { name: /Stand vor dieser Änderung/ })
    expect(within(dialog).getByTestId('restore-status')).toHaveTextContent(
      'Status: Aktiv → Zur Freigabe',
    )
  })

  it('nennt im Löschdialog den Verlauf und löscht über den Besitzer-Pfad', async () => {
    const { calls } = stubApi()
    const sheet = await openSheet()
    fireEvent.pointerDown(within(sheet).getByTestId('detail-more'), { button: 0, ctrlKey: false })
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Löschen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Eintrag endgültig löschen?' })
    expect(dialog).toHaveTextContent(
      'Eintrag und sein Verlauf werden dauerhaft entfernt. Das lässt sich nicht rückgängig machen.',
    )
    fireEvent.click(within(dialog).getByTestId('detail-delete-submit'))
    await waitFor(() =>
      expect(calls.some((call) => call.method === 'DELETE')).toBe(true),
    )
    expect(calls.find((call) => call.method === 'DELETE')?.path).toBe(
      '/v1/workspaces/ws-1/agents/a1/memories/m1',
    )
  })

  it('bietet „Wieder aktivieren“ nur bei abgelaufenen Einträgen', async () => {
    stubApi({ items: [memory({ status: 'expired' })] })
    const sheet = await openSheet()
    expect(within(sheet).getByRole('button', { name: 'Wieder aktivieren' })).toBeInTheDocument()
  })

  it.each([
    ['active', { status: 'active' as const }],
    ['pending', { status: 'pending' as const }],
    ['rejected', { status: 'rejected' as const }],
  ])('zeigt bei %s kein „Wieder aktivieren“', async (_label, overrides) => {
    stubApi({ items: [memory(overrides)] })
    const sheet = await openSheet()
    expect(within(sheet).queryByRole('button', { name: 'Wieder aktivieren' })).toBeNull()
  })

  it('bearbeitet über PUT auf das eigene Nutzergedächtnis (/me)', async () => {
    const { calls } = stubApi({
      items: [memory({ scope: 'user', agent_id: null, subject_user_id: 'u1' })],
    })
    const sheet = await openSheet()
    fireEvent.click(within(sheet).getByTestId('detail-edit'))
    fireEvent.change(within(sheet).getByLabelText('Fakt'), { target: { value: 'Nutzt uv.' } })
    fireEvent.click(within(sheet).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => {
      const put = calls.find((call) => call.method === 'PUT')
      expect(put?.path).toBe('/v1/workspaces/ws-1/me/memories/m1')
      expect(put?.body).toEqual({ fact: 'Nutzt uv.' })
    })
  })

  it('zeigt fremdes Nutzergedächtnis per Deep-Link nie an', async () => {
    const { calls } = stubApi({
      items: [memory({ scope: 'user', agent_id: null, subject_user_id: 'u-other' })],
    })
    renderPage(ENTRY)
    const sheet = await screen.findByTestId('memory-detail-sheet')
    expect(
      await within(sheet).findByText(
        'Diesen Eintrag gibt es nicht mehr oder du darfst ihn nicht sehen.',
      ),
    ).toBeInTheDocument()
    expect(within(sheet).queryByText('Nutzt uv statt pip.')).toBeNull()
    expect(calls.some((call) => call.path.endsWith('/history'))).toBe(false)
  })

  it('meldet einen Deep-Link ins Leere', async () => {
    stubApi({ items: [] })
    renderPage('/w/ws-1/memory?tab=entries&entry=gone')
    expect(
      await screen.findByText('Diesen Eintrag gibt es nicht mehr oder du darfst ihn nicht sehen.'),
    ).toBeInTheDocument()
  })

  it('löst einen Deep-Link über den Einzelabruf auf, ohne die Liste zu durchsuchen', async () => {
    const { calls } = stubApi()
    await openSheet()
    const single = calls.filter((call) => call.path === DETAIL_PATH)
    expect(single).toHaveLength(1)
    // Die Liste dahinter laedt ihre erste Seite; ein Suchlauf blaettert nicht.
    expect(
      calls.some((call) => call.path.endsWith('/memories') && call.path.includes('cursor')),
    ).toBe(false)
  })

  it('zeigt bei 404 memory_not_found „nicht gefunden“ ohne Fehlermeldung', async () => {
    stubApi({ detail: notFound() })
    renderPage(ENTRY)
    const sheet = await screen.findByTestId('memory-detail-sheet')
    expect(
      await within(sheet).findByText(
        'Diesen Eintrag gibt es nicht mehr oder du darfst ihn nicht sehen.',
      ),
    ).toBeInTheDocument()
    expect(within(sheet).queryByTestId('error-alert')).toBeNull()
    expect(within(sheet).queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
  })

  it('zeigt einen Netzfehler als Fehlermeldung mit Retry und lädt danach den Eintrag', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const { calls } = stubApi({
      detail: (attempt) => {
        if (attempt === 1) throw new TypeError('Failed to fetch')
        return jsonResponse(memory())
      },
    })
    renderPage(ENTRY)
    const sheet = await screen.findByTestId('memory-detail-sheet')
    const alert = await within(sheet).findByTestId('error-alert')
    expect(alert).toHaveTextContent('Der Eintrag ließ sich nicht laden.')
    expect(
      within(sheet).queryByText('Diesen Eintrag gibt es nicht mehr oder du darfst ihn nicht sehen.'),
    ).toBeNull()
    fireEvent.click(within(sheet).getByRole('button', { name: 'Erneut versuchen' }))
    expect(await within(sheet).findByTestId('detail-fact')).toHaveTextContent(
      'Nutzt uv statt pip.',
    )
    expect(within(sheet).queryByTestId('error-alert')).toBeNull()
    expect(calls.filter((call) => call.path === DETAIL_PATH)).toHaveLength(2)
  })

  it('behandelt einen Serverfehler (500) nicht als „nicht gefunden“', async () => {
    stubApi({ detail: jsonResponse({ detail: 'kaputt' }, 500) })
    renderPage(ENTRY)
    const sheet = await screen.findByTestId('memory-detail-sheet')
    expect(await within(sheet).findByTestId('error-alert')).toBeInTheDocument()
    expect(within(sheet).getByRole('button', { name: 'Erneut versuchen' })).toBeInTheDocument()
    expect(
      within(sheet).queryByText('Diesen Eintrag gibt es nicht mehr oder du darfst ihn nicht sehen.'),
    ).toBeNull()
  })

  it('zeigt einen Verlaufsfehler nur im Verlaufsabschnitt', async () => {
    stubApi({ history: jsonResponse({ detail: 'kaputt' }, 500) })
    const sheet = await openSheet()
    expect(await within(sheet).findByText('Der Verlauf ließ sich nicht laden.')).toBeInTheDocument()
    expect(within(sheet).getByTestId('detail-actions')).toBeInTheDocument()
  })

  it('öffnet das Sheet über den Chevron der Zeile mit dem Eintrag aus der Liste', async () => {
    const { calls } = stubApi()
    renderPage('/w/ws-1/memory?tab=entries')
    const chevron = await screen.findByRole('link', {
      name: 'Details zu „Nutzt uv statt pip.“ öffnen',
    })
    const listCalls = calls.filter((call) => call.path.endsWith('/memories')).length
    fireEvent.click(chevron)
    const sheet = await screen.findByTestId('memory-detail-sheet')
    expect(within(sheet).getByTestId('detail-fact')).toHaveTextContent('Nutzt uv statt pip.')
    // Kein Suchlauf: der Eintrag kam im Router-State mit.
    await within(sheet).findAllByTestId('history-item')
    expect(calls.filter((call) => call.path.endsWith('/memories')).length).toBe(listCalls)
    expect(calls.some((call) => call.path === DETAIL_PATH)).toBe(false)
  })

  it('rendert ohne detailLinks keinen Chevron', () => {
    const data: MemoryEntriesData = {
      items: [memory()],
      counts: { total: 1 },
      countsError: false,
      agents: [],
      hasMore: false,
      loadingMore: false,
      loadMore: vi.fn(),
      loading: false,
      error: null,
      reload: vi.fn(),
    }
    const props = {
      data,
      filters: entryFiltersFrom(new URLSearchParams()),
      onFilter: vi.fn(),
      onResetFilters: vi.fn(),
      fixedAgentId: 'a1',
    }
    const { rerender } = render(
      <Providers>
        <MemoryRouter>
          <MemoryList {...props} />
        </MemoryRouter>
      </Providers>,
    )
    expect(screen.getByTestId('entry-row')).toBeInTheDocument()
    expect(screen.queryByTestId('open-detail')).toBeNull()
    // Gegenprobe: mit `detailLinks` steht er da.
    rerender(
      <Providers>
        <MemoryRouter>
          <MemoryList {...props} detailLinks />
        </MemoryRouter>
      </Providers>,
    )
    expect(screen.getByTestId('open-detail')).toBeInTheDocument()
  })

  it('hat keine axe-Violations', async () => {
    stubApi()
    const sheet = await openSheet()
    await within(sheet).findAllByTestId('history-item')
    expect(await axe(sheet)).toHaveNoViolations()
  })
})
