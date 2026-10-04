import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryProposalRead, MemoryRead, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { MemoryRow, wordDiff } from '@/components/memory/MemoryRow'
import { axe } from '@/test/a11y'

import { isBatchable, resolveCommand } from '../hooks/useQueueShortcuts'
import { MemoryPage } from './MemoryPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// Stapel-Obergrenze: echt 100 (geprueft im Kuerzel-Test). Fuer den Test der
// Grenze per `x` laesst sie sich absenken, statt 100 Zeilen anzuklicken.
const selectionLimit = vi.hoisted(() => ({ override: null as number | null, actual: 0 }))
vi.mock('../hooks/useMemoryApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../hooks/useMemoryApi')>()
  selectionLimit.actual = original.SELECTION_LIMIT
  return {
    ...original,
    get SELECTION_LIMIT() {
      return selectionLimit.override ?? original.SELECTION_LIMIT
    },
  }
})

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

function memory(overrides: Partial<MemoryRead>): MemoryRead {
  return {
    id: 'm1',
    agent_id: 'a1',
    status: 'pending',
    fact: 'CI läuft auf Podman.',
    context: null,
    category: 'fact',
    importance: 3,
    source: 'agent',
    triage_note: null,
    retrieval_count: 0,
    last_retrieved_at: null,
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    kind: 'agent_note',
    scope: 'agent',
    subject_user_id: null,
    origin: 'user_stated',
    created_by_agent_id: 'a1',
    ...overrides,
  }
}

function proposal(overrides: Partial<MemoryProposalRead> = {}): MemoryProposalRead {
  return {
    id: 'p1',
    memory_id: 'm-old',
    agent_id: 'a1',
    action: 'change',
    new_fact: 'Python 3.14 ist installiert.',
    reason: 'neue Version installiert',
    status: 'pending',
    decided_by: null,
    decided_at: null,
    created_at: '2026-10-01T10:00:00Z',
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

interface StubOptions {
  held?: MemoryRead[]
  items?: MemoryRead[]
  proposals?: MemoryProposalRead[]
  agentCounts?: Record<string, number>
  myMemories?: MemoryRead[]
  agentMemories?: MemoryRead[]
  batch?: (body: Record<string, unknown>) => Response
}

interface Call {
  method: string
  url: string
  body: Record<string, unknown> | null
}

function stubApi({
  held = [],
  items = [],
  proposals = [],
  agentCounts = {},
  myMemories = [],
  agentMemories = [memory({ id: 'm-old', status: 'active', fact: 'Python 3.13 ist installiert.' })],
  batch,
}: StubOptions = {}) {
  const calls: Call[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : null
    calls.push({ method, url, body })
    const parsed = new URL(url, 'http://x')
    const path = parsed.pathname
    if (path.endsWith('/memories/batch')) {
      return batch ? batch(body ?? {}) : jsonResponse({ results: [] })
    }
    if (path.endsWith('/memories/counts')) {
      if (parsed.searchParams.get('held') === 'true') return jsonResponse({ total: held.length })
      if (parsed.searchParams.get('scope') === 'user') {
        const mine = items.filter((m) => m.scope === 'user').length
        return jsonResponse({ total: mine })
      }
      return jsonResponse({
        total: Object.values(agentCounts).reduce((a, b) => a + b, 0),
        groups: { agent: agentCounts },
      })
    }
    if (path.endsWith('/me/memories')) return jsonResponse({ items: myMemories, next_cursor: null })
    if (/\/agents\/[^/]+\/memories$/.test(path)) return jsonResponse(agentMemories)
    if (path.endsWith('/memories')) {
      const rows = parsed.searchParams.get('held') === 'true' ? held : items
      return jsonResponse({ items: rows, next_cursor: null })
    }
    if (path.endsWith('/decide')) {
      return jsonResponse({ ...proposals[0], status: 'accepted' })
    }
    if (path.endsWith('/memory-proposals')) return jsonResponse(proposals)
    if (path.endsWith('/agents')) {
      return jsonResponse([
        { id: 'a1', name: 'coder', tool_policy: { memory_mode: 'manual' } },
        { id: 'a2', name: 'researcher', tool_policy: { memory_mode: 'manual' } },
      ])
    }
    return jsonResponse([])
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls }
}

function renderPage(role: WorkspaceRole = 'editor', entry = '/w/ws-1/memory') {
  return render(
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
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route path="/w/:workspaceId/memory" element={<MemoryPage />} />
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

describe('MemoryPage · Zur Freigabe (C5a, Spec S1′)', () => {
  it('zeigt einem Lernvorschlag nie „Freigeben“ – auch nicht als einzelne Zeile', () => {
    render(
      <MemoryRow
        memory={memory({ kind: 'lesson' })}
        agentName={null}
        canAct
        selectable={false}
        selected={false}
        onToggleSelect={vi.fn()}
        failure={null}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /CI läuft auf Podman/ }))
    expect(screen.queryByRole('button', { name: 'Freigeben' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Aktivieren/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Ablehnen' })).toBeInTheDocument()
  })

  it('rendert Lernvorschläge aus der Antwort nicht in der Warteschlange', async () => {
    stubApi({
      items: [
        memory({ id: 'm1', fact: 'Normaler Eintrag.' }),
        memory({ id: 'm2', fact: 'Lektion aus Fall 7.', kind: 'lesson' }),
      ],
      agentCounts: { a1: 1 },
    })
    renderPage()
    expect(await screen.findByText('Normaler Eintrag.')).toBeInTheDocument()
    expect(screen.queryByText('Lektion aus Fall 7.')).toBeNull()
  })

  it('übernimmt einen Änderungsvorschlag über decide mit accept:true und zeigt den Wort-Diff', async () => {
    const { calls } = stubApi({ proposals: [proposal()] })
    renderPage()
    const row = await screen.findByTestId('memory-proposal-row')
    await waitFor(() => expect(within(row).getByTestId('proposal-diff')).toBeInTheDocument())
    expect(row.querySelector('del')).toHaveTextContent('3.13')
    expect(row.querySelector('ins')).toHaveTextContent('3.14')
    // Vorschläge haben keine Checkbox.
    expect(within(row).queryByRole('checkbox')).toBeNull()

    fireEvent.click(within(row).getByRole('button', { name: 'Änderung übernehmen' }))
    await waitFor(() =>
      expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/memory-proposals/p1/decide'))).toBe(true),
    )
    const decide = calls.find((c) => c.url.endsWith('/memory-proposals/p1/decide'))!
    expect(decide.body).toEqual({ accept: true })
  })

  it('ordnet einen Agentenvorschlag aufs eigene Nutzergedächtnis der eigenen Gruppe zu, nicht dem Agenten', async () => {
    stubApi({
      proposals: [proposal({ id: 'p-user', memory_id: 'mine-1', new_fact: 'Ich arbeite mit Neovim.' })],
      agentMemories: [],
      myMemories: [
        memory({ id: 'mine-1', status: 'active', scope: 'user', kind: 'user_fact', agent_id: null, subject_user_id: 'u1', fact: 'Ich arbeite mit Vim.' }),
      ],
    })
    renderPage()
    const row = await screen.findByTestId('memory-proposal-row')
    const section = row.closest('section')!
    expect(within(section).getByRole('heading', { level: 3 })).toHaveTextContent('Dein Nutzergedächtnis')
    await waitFor(() => expect(row.querySelector('del')).toHaveTextContent('Vim.'))
  })

  it('rendert fremdes Nutzergedächtnis nie und fragt nie nach subject_user_id-Gruppen (admin)', async () => {
    const { calls } = stubApi({
      items: [
        memory({ id: 'own', scope: 'user', kind: 'user_fact', agent_id: null, subject_user_id: 'u1', fact: 'Eigener Fakt.' }),
        memory({ id: 'foreign', scope: 'user', kind: 'user_fact', agent_id: null, subject_user_id: 'u2', fact: 'Fremder Fakt.' }),
      ],
    })
    renderPage('admin')
    expect(await screen.findByText('Eigener Fakt.')).toBeInTheDocument()
    expect(screen.queryByText('Fremder Fakt.')).toBeNull()
    expect(calls.some((c) => c.url.includes('subject_user_id'))).toBe(false)
  })

  it('gibt zurückgehaltenen Einträgen keine Checkbox und nennt den Grund', async () => {
    stubApi({
      held: [memory({ id: 'h1', origin: 'external_content', fact: 'Aus README übernommen.' })],
      items: [memory({ id: 'm1' })],
      agentCounts: { a1: 1 },
    })
    renderPage()
    const heldRow = await screen.findByTestId('memory-held-row')
    expect(within(heldRow).queryByRole('checkbox')).toBeNull()
    expect(within(heldRow).getByText('Aus Webseite, Datei oder Werkzeug (laut Agent)')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /CI läuft auf Podman/ })).toBeInTheDocument()
  })

  it('sendet bei „Alle von coder freigeben“ expected_count; bei 409 bleibt der Dialog mit der neuen Zahl', async () => {
    let attempt = 0
    const { calls } = stubApi({
      items: [memory({ id: 'm1' }), memory({ id: 'm2', fact: 'Tests mit uv run pytest.' })],
      agentCounts: { a1: 2 },
      batch: () => {
        attempt += 1
        if (attempt === 1) {
          return jsonResponse(
            { detail: 'x', reason: 'memory_batch_count_mismatch', params: { count: 3 } },
            409,
          )
        }
        return jsonResponse({ results: [{ id: 'm1', ok: true }, { id: 'm2', ok: true }, { id: 'm3', ok: true }] })
      },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Alle 2 Einträge von coder freigeben' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: '2 freigeben' }))

    expect(await within(dialog).findByTestId('count-changed')).toHaveTextContent('Inzwischen sind es 3.')
    const first = calls.find((c) => c.url.endsWith('/memories/batch'))!
    expect(first.body).toMatchObject({
      action: 'approve',
      expected_count: 2,
      filter: { status: 'pending', held: false, scope: 'agent', agent_id: 'a1' },
    })

    fireEvent.click(within(dialog).getByRole('button', { name: '3 freigeben' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const second = calls.filter((c) => c.url.endsWith('/memories/batch'))[1]
    expect(second.body).toMatchObject({ expected_count: 3 })
  })

  it('lässt bei Teilfehler die fehlgeschlagene Zeile ausgewählt und zeigt den Grund dort', async () => {
    stubApi({
      items: [memory({ id: 'm1', fact: 'Erster.' }), memory({ id: 'm2', fact: 'Zweiter.' })],
      agentCounts: { a1: 2 },
      batch: () =>
        jsonResponse({
          results: [
            { id: 'm1', ok: true },
            { id: 'm2', ok: false, reason: 'memory_note_cap_reached' },
          ],
        }),
    })
    renderPage()
    fireEvent.click(await screen.findByRole('checkbox', { name: /Erster/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Zweiter/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Auswahl freigeben (2)' }))

    expect(
      await screen.findByText('1 Eintrag konnte nicht freigegeben werden. Er ist weiter ausgewählt, der Grund steht an der Zeile.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('checkbox', { name: /Zweiter/ })).toBeChecked())
    expect(screen.getByTestId('row-failure')).toHaveTextContent(
      'Die Agentennotizen dieses Agenten sind voll.',
    )
  })

  it('zeigt Viewern nur das eigene Nutzergedächtnis und fragt nur scope=user an', async () => {
    const { calls } = stubApi()
    renderPage('viewer')
    expect(await screen.findByText('Nichts zur Freigabe')).toBeInTheDocument()
    const listCalls = calls.filter((c) => /\/memories(\?|$)/.test(c.url))
    expect(listCalls.length).toBeGreaterThan(0)
    for (const call of listCalls) expect(call.url).toContain('scope=user')
    expect(calls.some((c) => c.url.endsWith('/agents'))).toBe(false)
    expect(screen.queryByLabelText('Agent')).toBeNull()
  })

  it('hat keine axe-Violations mit Gruppen, Zurückgehaltenen und Vorschlag', async () => {
    stubApi({
      held: [memory({ id: 'h1', category: 'instruction', fact: 'Antworte immer knapp.' })],
      items: [memory({ id: 'm1' })],
      proposals: [proposal()],
      agentCounts: { a1: 1 },
    })
    const { container } = renderPage()
    await screen.findByTestId('memory-proposal-row')
    expect(await axe(container)).toHaveNoViolations()
  })
})

// ------------------------------------------------------------ Tab „Einträge“

interface EntriesStub {
  rows?: MemoryRead[]
  // Antwort von `/memories/counts` je Aufruf; Standard: total = rows.length.
  counts?: (params: URLSearchParams) => Response
  batch?: (body: Record<string, unknown>) => Response
  action?: (path: string) => Response
}

function stubEntries({ rows = [], counts, batch, action }: EntriesStub = {}) {
  const calls: Call[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : null
    calls.push({ method, url, body })
    const parsed = new URL(url, 'http://x')
    const path = parsed.pathname
    if (path.endsWith('/memories/batch')) {
      return batch ? batch(body ?? {}) : jsonResponse({ results: [] })
    }
    if (/\/(confirm|reactivate|triage)$/.test(path)) {
      return action ? action(path) : jsonResponse(rows[0])
    }
    if (path.endsWith('/memories/counts')) {
      if (counts) return counts(parsed.searchParams)
      return jsonResponse({
        total: rows.length,
        groups: { agent: { a1: rows.length }, status: { active: rows.length } },
      })
    }
    if (path.endsWith('/memories')) return jsonResponse({ items: rows, next_cursor: null })
    if (path.endsWith('/memory-proposals')) return jsonResponse([])
    if (path.endsWith('/agents')) {
      return jsonResponse([{ id: 'a1', name: 'coder', tool_policy: { memory_mode: 'manual' } }])
    }
    return jsonResponse([])
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls }
}

const ENTRIES = '/w/ws-1/memory?tab=entries'

describe('MemoryPage · Einträge (C5b-1, Spec S2′)', () => {
  it('lädt die Liste mit scope=agent, Facetten aus /memories/counts und zeigt die Serverzahl', async () => {
    const { calls } = stubEntries({
      rows: [memory({ id: 'm1', status: 'active', confirmed_at: '2026-10-02T10:00:00Z' })],
      counts: () =>
        jsonResponse({ total: 1240, groups: { agent: { a1: 1240 }, status: { active: 1240 } } }),
    })
    renderPage('editor', ENTRIES)
    expect(await screen.findByTestId('entries-result-count')).toHaveTextContent('1.240 Einträge')
    const list = calls.find((c) => c.method === 'GET' && /\/memories\?/.test(c.url))!
    expect(list.url).toContain('scope=agent')
    const facetCounts = calls.find(
      (c) => c.url.includes('/memories/counts') && c.url.includes('group_by=health'),
    )!
    for (const group of ['agent', 'kind', 'status', 'health', 'origin', 'source']) {
      expect(facetCounts.url).toContain(`group_by=${group}`)
    }
    expect(screen.getByRole('tab', { name: /^Einträge/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('setzt eine Facette in die URL und fragt mit genau diesem Filter neu an', async () => {
    const { calls } = stubEntries({ rows: [memory({ id: 'm1', status: 'active' })] })
    renderPage('editor', ENTRIES)
    await screen.findByTestId('entries-list')
    fireEvent.click(screen.getByRole('radio', { name: /^Abgelaufen/ }))
    await waitFor(() =>
      expect(calls.some((c) => /\/memories\?.*status=expired/.test(c.url))).toBe(true),
    )
    expect(screen.getByRole('button', { name: 'Filter „Status: Abgelaufen“ entfernen' })).toBeInTheDocument()
  })

  it('bietet „Bestätigen“ für unbestätigte und „Wieder aktivieren“ für abgelaufene Einträge an', async () => {
    const { calls } = stubEntries({
      rows: [
        memory({ id: 'm1', status: 'active', confirmed_at: null, fact: 'Unbestätigt.' }),
        memory({ id: 'm2', status: 'expired', fact: 'Abgelaufen.' }),
        memory({ id: 'm3', status: 'active', confirmed_at: '2026-10-02T10:00:00Z', fact: 'Fertig.' }),
      ],
    })
    renderPage('editor', ENTRIES)
    await screen.findByTestId('entries-list')
    const rows = screen.getAllByTestId('entry-row')
    // Bestätigte aktive Zeile: keine Aktion (keine toten Knöpfe).
    expect(within(rows[2]).queryByRole('button', { name: /Bestätigen|Wieder aktivieren/ })).toBeNull()

    fireEvent.click(within(rows[0]).getByRole('button', { name: 'Bestätigen' }))
    await waitFor(() =>
      expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/agents/a1/memories/m1/confirm'))).toBe(true),
    )
    fireEvent.click(within(rows[1]).getByRole('button', { name: 'Wieder aktivieren' }))
    await waitFor(() =>
      expect(
        calls.some((c) => c.method === 'POST' && c.url.endsWith('/agents/a1/memories/m2/reactivate')),
      ).toBe(true),
    )
  })

  it('gibt zurückgehaltenen Vorschlägen kein „Freigeben“, sondern den Weg in die Warteschlange', async () => {
    const { calls } = stubEntries({
      rows: [
        memory({ id: 'h1', status: 'pending', origin: 'external_content', fact: 'Aus README.' }),
        memory({ id: 'h2', status: 'pending', category: 'instruction', fact: 'Immer so.' }),
        memory({ id: 'p1', status: 'pending', fact: 'Normaler Vorschlag.' }),
      ],
    })
    renderPage('editor', ENTRIES)
    await screen.findByTestId('entries-list')
    const rows = screen.getAllByTestId('entry-row')
    for (const row of [rows[0], rows[1]]) {
      expect(within(row).queryByRole('button', { name: 'Freigeben' })).toBeNull()
      expect(within(row).queryByRole('checkbox')).toBeNull()
      const link = within(row).getByRole('link', { name: 'In der Warteschlange entscheiden' })
      expect(link).toHaveAttribute('href', '/w/ws-1/memory?tab=approval&agent=a1')
    }
    // Nicht zurückgehalten: Einzelfreigabe bleibt, kein Warteschlangen-Link.
    expect(within(rows[2]).getByRole('button', { name: 'Freigeben' })).toBeInTheDocument()
    expect(within(rows[2]).queryByTestId('decide-in-queue')).toBeNull()
    expect(calls.some((c) => c.method === 'POST' && /\/triage$/.test(c.url))).toBe(false)
  })

  it('zählt im Tab dieselbe Menge wie die ungefilterte Liste (inkl. abgelehnter)', async () => {
    stubEntries({
      rows: [memory({ id: 'm1', status: 'active', confirmed_at: '2026-10-02T10:00:00Z' })],
      counts: () =>
        jsonResponse({ total: 7, groups: { agent: { a1: 7 }, status: { active: 5, rejected: 2 } } }),
    })
    renderPage('editor', ENTRIES)
    expect(await screen.findByTestId('entries-result-count')).toHaveTextContent('7 Einträge')
    await waitFor(() => expect(screen.getByTestId('tab-count-entries')).toHaveTextContent('7'))
  })

  it('sendet im Stapel nur passende IDs und zeigt den Grund je Eintrag an der Zeile', async () => {
    const { calls } = stubEntries({
      rows: [
        memory({ id: 'm1', status: 'active', confirmed_at: null, fact: 'Erster.' }),
        memory({ id: 'm2', status: 'active', confirmed_at: null, fact: 'Zweiter.' }),
        memory({ id: 'm3', status: 'expired', fact: 'Dritter.' }),
      ],
      batch: () =>
        jsonResponse({
          results: [
            { id: 'm1', ok: true },
            { id: 'm2', ok: false, reason: 'memory_transition_invalid', params: { status: 'expired' } },
          ],
        }),
    })
    renderPage('editor', ENTRIES)
    fireEvent.click(await screen.findByRole('checkbox', { name: /Erster/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Zweiter/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Dritter/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Bestätigen (2 von 3)' }))

    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/memories/batch'))).toBe(true))
    const call = calls.find((c) => c.url.endsWith('/memories/batch'))!
    expect(call.body).toEqual({ action: 'confirm', ids: ['m1', 'm2'] })
    expect(await screen.findByTestId('row-failure')).toHaveTextContent('Schon entschieden.')
    await waitFor(() => expect(screen.getByRole('checkbox', { name: /Zweiter/ })).toBeChecked())
    expect(screen.getByRole('checkbox', { name: /Erster/ })).not.toBeChecked()
  })

  it('bestätigt per Filter nur mit expected_count und fragt bei 409 neu', async () => {
    let attempt = 0
    const { calls } = stubEntries({
      rows: [memory({ id: 'm1', status: 'active', confirmed_at: null })],
      counts: () => jsonResponse({ total: 2, groups: {} }),
      batch: () => {
        attempt += 1
        if (attempt === 1) {
          return jsonResponse(
            { detail: 'x', reason: 'memory_batch_count_mismatch', params: { count: 3 } },
            409,
          )
        }
        return jsonResponse({ results: [{ id: 'm1', ok: true }] })
      },
    })
    renderPage('editor', `${ENTRIES}&health=unconfirmed&agent=a1`)
    fireEvent.click(await screen.findByRole('button', { name: 'Alle 2 bestätigen' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: '2 bestätigen' }))

    expect(await within(dialog).findByTestId('count-changed')).toHaveTextContent('Inzwischen sind es 3.')
    const first = calls.find((c) => c.url.endsWith('/memories/batch'))!
    expect(first.body).toEqual({
      action: 'confirm',
      filter: { scope: 'agent', agent_id: 'a1', health: 'unconfirmed' },
      expected_count: 2,
    })
    fireEvent.click(within(dialog).getByRole('button', { name: '3 bestätigen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const second = calls.filter((c) => c.url.endsWith('/memories/batch'))[1]
    expect(second.body).toMatchObject({ expected_count: 3 })
  })

  it('zeigt fremdes Nutzergedächtnis nie, auch wenn es in der Antwort steckt', async () => {
    stubEntries({
      rows: [
        memory({ id: 'm1', status: 'active', fact: 'Eigene Notiz.' }),
        memory({
          id: 'x1',
          agent_id: null,
          scope: 'user',
          kind: 'user_fact',
          subject_user_id: 'u2',
          status: 'active',
          fact: 'Fremder Nutzerfakt.',
        }),
      ],
    })
    renderPage('editor', ENTRIES)
    expect(await screen.findByText('Eigene Notiz.')).toBeInTheDocument()
    expect(screen.queryByText('Fremder Nutzerfakt.')).toBeNull()
  })

  it('blendet den Tab für Viewer aus, fällt auf „Zur Freigabe“ zurück und fragt nur scope=user an', async () => {
    const { calls } = stubEntries()
    renderPage('viewer', ENTRIES)
    expect(await screen.findByText('Nichts zur Freigabe')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /^Einträge/ })).toBeNull()
    expect(screen.queryByTestId('entries-list')).toBeNull()
    const listCalls = calls.filter((c) => /\/memories(\/counts)?(\?|$)/.test(c.url))
    expect(listCalls.length).toBeGreaterThan(0)
    for (const call of listCalls) expect(call.url).toContain('scope=user')
  })

  it('lädt die Liste auch ohne Zähler und sagt das klein über den Facetten', async () => {
    stubEntries({
      rows: [memory({ id: 'm1', status: 'active', fact: 'Bleibt sichtbar.' })],
      counts: () => jsonResponse({ detail: 'kaputt' }, 500),
    })
    renderPage('editor', ENTRIES)
    expect(await screen.findByText('Bleibt sichtbar.')).toBeInTheDocument()
    expect((await screen.findAllByTestId('counts-unavailable')).length).toBeGreaterThan(0)
  })

  it('hat keine axe-Violations mit Liste, Facetten und Stapelleiste', async () => {
    stubEntries({
      rows: [
        memory({ id: 'm1', status: 'active', confirmed_at: null, fact: 'Erster.' }),
        memory({ id: 'm2', status: 'expired', fact: 'Zweiter.' }),
      ],
    })
    const { container } = renderPage('editor', ENTRIES)
    fireEvent.click(await screen.findByRole('checkbox', { name: /Erster/ }))
    await screen.findByTestId('entries-bulk-bar')
    expect(await axe(container)).toHaveNoViolations()
  })
})

// ------------------------------------------------- Tastaturkürzel (C5a-3)

describe('MemoryPage · Zur Freigabe · Tastaturkürzel (C5a-3, Spec §5.2)', () => {
  afterEach(() => window.localStorage.clear())

  const twoRows = () =>
    stubApi({
      items: [memory({ id: 'm1', fact: 'Erster.' }), memory({ id: 'm2', fact: 'Zweiter.' })],
      agentCounts: { a1: 2 },
    })

  const toggle = (fact: RegExp) => screen.getByRole('button', { name: fact })
  const press = (key: string, target: Element = document.activeElement ?? document.body) =>
    fireEvent.keyDown(target, { key })

  it('j/k bewegen den Fokus zur nächsten bzw. vorigen Zeile', async () => {
    twoRows()
    renderPage()
    const first = await screen.findByRole('button', { name: /Erster/ })
    first.focus()
    press('j')
    expect(toggle(/Zweiter/)).toHaveFocus()
    press('j')
    expect(toggle(/Zweiter/)).toHaveFocus()
    press('k')
    expect(toggle(/Erster/)).toHaveFocus()
  })

  it('x wählt die Zeile aus und wieder ab', async () => {
    twoRows()
    renderPage()
    ;(await screen.findByRole('button', { name: /Erster/ })).focus()
    press('x')
    expect(screen.getByRole('checkbox', { name: /Erster/ })).toBeChecked()
    expect(screen.getByText('1 ausgewählt')).toBeInTheDocument()
    press('x')
    expect(screen.getByRole('checkbox', { name: /Erster/ })).not.toBeChecked()
  })

  it('x respektiert die Stapel-Obergrenze (100) und zeigt den Hinweis', async () => {
    expect(selectionLimit.actual).toBe(100)
    selectionLimit.override = 2
    try {
      stubApi({
        items: [
          memory({ id: 'm1', fact: 'Erster.' }),
          memory({ id: 'm2', fact: 'Zweiter.' }),
          memory({ id: 'm3', fact: 'Dritter.' }),
        ],
        agentCounts: { a1: 3 },
      })
      renderPage()
      ;(await screen.findByRole('button', { name: /Erster/ })).focus()
      press('x')
      press('j')
      press('x')
      press('j')
      press('x')
      expect(screen.getByRole('checkbox', { name: /Dritter/ })).not.toBeChecked()
      expect(screen.getByText('2 ausgewählt')).toBeInTheDocument()
      expect(screen.getByText('Höchstens 100 auf einmal.')).toBeInTheDocument()
    } finally {
      selectionLimit.override = null
    }
  })

  it('a gibt die fokussierte Zeile über triage frei', async () => {
    const { calls } = twoRows()
    renderPage()
    ;(await screen.findByRole('button', { name: /Zweiter/ })).focus()
    press('a')
    await waitFor(() =>
      expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/agents/a1/memories/m2/triage'))).toBe(true),
    )
    const call = calls.find((c) => c.url.endsWith('/memories/m2/triage'))!
    expect(call.body).toEqual({ action: 'approve' })
  })

  it('a und x wirken bei Zurückgehaltenen nicht und sagen „Einzeln entscheiden“ an', async () => {
    const { notify } = await import('@/lib/feedback')
    const { calls } = stubApi({
      held: [memory({ id: 'h1', origin: 'external_content', fact: 'Aus README übernommen.' })],
    })
    renderPage()
    const heldRow = await screen.findByTestId('memory-held-row')
    heldRow.focus()
    press('a')
    press('x')
    expect(notify.info).toHaveBeenCalledWith('Einzeln entscheiden')
    expect(notify.info).toHaveBeenCalledTimes(2)
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    expect(screen.queryByText(/ausgewählt/)).toBeNull()
  })

  it('a übernimmt keinen Änderungsvorschlag (nur per Knopf)', async () => {
    const { notify } = await import('@/lib/feedback')
    const { calls } = stubApi({ proposals: [proposal()] })
    renderPage()
    const row = await screen.findByTestId('memory-proposal-row')
    row.focus()
    press('a')
    expect(notify.info).toHaveBeenCalledWith('Einzeln entscheiden')
    expect(calls.some((c) => c.url.endsWith('/decide'))).toBe(false)
  })

  it('a gibt nie einen Lernvorschlag frei, x wählt ihn nie aus', () => {
    const lesson = memory({ kind: 'lesson' })
    const row = { type: 'memory', memory: lesson, canAct: true } as const
    expect(isBatchable(lesson)).toBe(false)
    expect(resolveCommand('approve', row)).toBe('refuse')
    expect(resolveCommand('select', row)).toBe('refuse')
    expect(resolveCommand('edit', row)).toBe('ignore')
    // Gegenprobe: ein normaler Eintrag läuft.
    expect(resolveCommand('approve', { ...row, memory: memory({}) })).toBe('run')
  })

  it('r öffnet den Ablehnen-Dialog der Zeile', async () => {
    twoRows()
    renderPage()
    ;(await screen.findByRole('button', { name: /Erster/ })).focus()
    press('r')
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Eintrag ablehnen?')).toBeInTheDocument()
  })

  it('e klappt auf und setzt den Fokus ins Faktfeld; Esc führt zurück zur Zeile', async () => {
    twoRows()
    renderPage()
    const first = await screen.findByRole('button', { name: /Erster/ })
    first.focus()
    press('e')
    expect(first).toHaveAttribute('aria-expanded', 'true')
    const field = screen.getByRole('textbox', { name: 'Fakt' })
    expect(field).toHaveFocus()
    press('Escape', field)
    expect(first).toHaveFocus()
  })

  it('h öffnet den Verlauf (Detail-Sheet) der Zeile', async () => {
    twoRows()
    renderPage()
    ;(await screen.findByRole('button', { name: /Erster/ })).focus()
    press('h')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('? öffnet die Hilfe mit allen Kürzeln', async () => {
    twoRows()
    renderPage()
    ;(await screen.findByRole('button', { name: /Erster/ })).focus()
    press('?')
    const dialog = await screen.findByRole('dialog', { name: 'Tastaturkürzel' })
    for (const key of ['j', 'k', 'x', 'a', 'r', 'e', 'h', '?', 'Esc']) {
      expect(within(dialog).getByText(key, { selector: 'kbd' })).toBeInTheDocument()
    }
    expect(within(dialog).getByText('Verlauf öffnen')).toBeInTheDocument()
  })

  it('wirkt nicht im Suchfeld und nicht im Faktfeld', async () => {
    const { calls } = twoRows()
    renderPage()
    const first = await screen.findByRole('button', { name: /Erster/ })
    const search = screen.getByRole('searchbox')
    search.focus()
    for (const key of ['j', 'x', 'a', 'r', '?']) press(key, search)
    expect(search).toHaveFocus()
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(first)
    const field = screen.getByRole('textbox', { name: 'Fakt' })
    field.focus()
    for (const key of ['a', 'x', 'r', 'j']) press(key, field)
    expect(field).toHaveFocus()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByText(/ausgewählt/)).toBeNull()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('lässt sich in der Hilfe abschalten (WCAG 2.1.4) und bleibt aus', async () => {
    twoRows()
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Tastatur/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Tastaturkürzel' })
    fireEvent.click(within(dialog).getByRole('checkbox', { name: 'Tastaturkürzel verwenden' }))
    fireEvent.keyDown(dialog, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    toggle(/Erster/).focus()
    press('x')
    press('j')
    expect(screen.getByRole('checkbox', { name: /Erster/ })).not.toBeChecked()
    expect(toggle(/Erster/)).toHaveFocus()
    expect(window.localStorage.getItem('who2be:memory-queue-shortcuts')).toBe('off')
  })
})

describe('wordDiff', () => {
  it('markiert nur die geänderten Wörter', () => {
    const tokens = wordDiff('Python 3.13 ist da', 'Python 3.14 ist da')
    expect(tokens.filter((t) => t.op === 'removed').map((t) => t.text)).toEqual(['3.13'])
    expect(tokens.filter((t) => t.op === 'added').map((t) => t.text)).toEqual(['3.14'])
  })

  it('fasst benachbarte Änderungen zu einem entfernten und einem neuen Block zusammen', () => {
    const tokens = wordDiff(
      'Der Ansprechpartner ist Frau Schmidt.',
      'Der Ansprechpartner ist seit Oktober Herr Yilmaz.',
    )
    expect(tokens.filter((t) => t.op === 'removed').map((t) => t.text)).toEqual(['Frau Schmidt.'])
    expect(tokens.filter((t) => t.op === 'added').map((t) => t.text)).toEqual([
      'seit Oktober Herr Yilmaz.',
    ])
    expect(tokens.map((t) => t.text).join('')).toBe(
      'Der Ansprechpartner ist Frau Schmidt. seit Oktober Herr Yilmaz.',
    )
  })
})
