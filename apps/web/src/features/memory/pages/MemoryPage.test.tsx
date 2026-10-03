import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryProposalRead, MemoryRead, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { MemoryRow, wordDiff } from '@/components/memory/MemoryRow'
import { axe } from '@/test/a11y'

import { MemoryPage } from './MemoryPage'

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
    if (path.endsWith('/me/memories')) return jsonResponse({ items: [], next_cursor: null })
    if (/\/agents\/[^/]+\/memories$/.test(path)) {
      return jsonResponse([memory({ id: 'm-old', status: 'active', fact: 'Python 3.13 ist installiert.' })])
    }
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

describe('wordDiff', () => {
  it('markiert nur die geänderten Wörter', () => {
    const tokens = wordDiff('Python 3.13 ist da', 'Python 3.14 ist da')
    expect(tokens.filter((t) => t.op === 'removed').map((t) => t.text)).toEqual(['3.13'])
    expect(tokens.filter((t) => t.op === 'added').map((t) => t.text)).toEqual(['3.14'])
  })
})
