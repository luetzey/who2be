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

// Filter-Sheet unter `md`: jsdom kennt keine Breakpoints, `useIsMobile` ist
// gemockt (Standard: Desktop), `useMediaQuery` bleibt echt.
const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/hooks/useMediaQuery')>()),
  useIsMobile: () => viewport.mobile,
}))
afterEach(() => {
  viewport.mobile = false
})

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
  // Erste /agents-Seite; Default: coder (a1) und researcher (a2).
  agents?: { id: string; name: string }[]
  // Antwort auf GET /agents/{id} (gezieltes Nachladen); Default 404.
  agentLookup?: (id: string) => Response
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
  agents = [
    { id: 'a1', name: 'coder' },
    { id: 'a2', name: 'researcher' },
  ],
  agentLookup = () => jsonResponse({ detail: 'not found' }, 404),
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
      return jsonResponse(
        agents.map((agent) => ({ ...agent, tool_policy: { memory_mode: 'manual' } })),
      )
    }
    const single = /\/agents\/([^/]+)$/.exec(path)
    if (single !== null) return agentLookup(decodeURIComponent(single[1]))
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
    expect(calls.some((c) => /\/agents\/[^/]+$/.test(new URL(c.url, 'http://x').pathname))).toBe(false)
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

// Filter-Standard M3 (§3.1): Suche + genau eine Facette (Agent, nur editor+)
// in der ListFilterBar; eine Facette steht auch unter `md` inline.
describe('MemoryPage · Zur Freigabe · Filterleiste (Filter-Standard M3)', () => {
  it('setzt den Agenten in die URL, zeigt den Chip und setzt per „Filter zurücksetzen“ zurück', async () => {
    const { calls } = stubApi({ items: [memory({ id: 'm1' })], agentCounts: { a1: 1 } })
    renderPage()
    const select = await screen.findByLabelText('Agent')
    await within(select).findByRole('option', { name: 'researcher' })
    expect(within(select).getAllByRole('option')[0]).toHaveTextContent('Alle Agenten')
    expect(screen.queryByRole('button', { name: 'Filter zurücksetzen' })).toBeNull()

    fireEvent.change(select, { target: { value: 'a2' } })
    const chips = await screen.findByRole('list', { name: 'Aktive Filter' })
    expect(
      within(chips).getByRole('button', { name: 'Agent-Filter entfernen (researcher)' }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(calls.some((c) => /\/memories\?/.test(c.url) && c.url.includes('agent_id=a2'))).toBe(
        true,
      ),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Filter zurücksetzen' }))
    await waitFor(() => expect(screen.queryByRole('list', { name: 'Aktive Filter' })).toBeNull())
    expect(screen.getByLabelText('Agent')).toHaveValue('')
  })

  it('zählt die Suche als aktiv: „Filter zurücksetzen“ leert sie, ohne Chip', async () => {
    stubApi()
    renderPage()
    const search = await screen.findByLabelText('Suche')
    expect(search).toHaveAttribute('placeholder', 'In Vorschlägen suchen…')
    fireEvent.change(search, { target: { value: 'Podman' } })
    expect(screen.queryByRole('list', { name: 'Aktive Filter' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Filter zurücksetzen' }))
    expect(search).toHaveValue('')
  })

  it('lässt unter md die eine Facette inline – kein „Filter“-Knopf, kein Sheet', async () => {
    viewport.mobile = true
    stubApi()
    renderPage()
    const select = await screen.findByLabelText('Agent')
    expect(select).toBeVisible()
    expect(screen.queryByTestId('list-filter-facets-toggle')).toBeNull()
    expect(screen.queryByRole('button', { name: /^Filter( \(|$)/ })).toBeNull()
  })

  it('zeigt Viewern nur die Suche, auch unter md', async () => {
    viewport.mobile = true
    stubApi()
    renderPage('viewer')
    expect(await screen.findByLabelText('Suche')).toBeInTheDocument()
    expect(screen.queryByLabelText('Agent')).toBeNull()
    expect(screen.queryByTestId('list-filter-facets-toggle')).toBeNull()
  })

  it('hat keine axe-Violations mit gesetztem Agent-Filter (mobil)', async () => {
    viewport.mobile = true
    stubApi({ items: [memory({ id: 'm1' })], agentCounts: { a1: 1 } })
    const { container } = renderPage('editor', '/w/ws-1/memory?tab=approval&agent=a1&q=CI')
    await screen.findByRole('list', { name: 'Aktive Filter' })
    expect(await axe(container)).toHaveNoViolations()
  })
})

// Agenten ausserhalb der ersten /agents-Seite (hoechstens 100): nie die rohe
// Agent-ID zeigen, fehlende Namen gezielt per GET /agents/{id} nachladen.
describe('MemoryPage · Zur Freigabe · unbekannte Agenten (t_3cd92765)', () => {
  const UNKNOWN = '7f3c2a10-9b4e-4d21-8c55-0e6f1a2b3c4d'
  const UNKNOWN_2 = '0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d'

  /** Sichtbarer Text und alle zugaenglichen Namen/Beschreibungen. */
  function exposedText(): string {
    const labelled = [...document.body.querySelectorAll('[aria-label], [title], [aria-description]')]
      .flatMap((node) => [
        node.getAttribute('aria-label') ?? '',
        node.getAttribute('title') ?? '',
        node.getAttribute('aria-description') ?? '',
      ])
    return [document.body.textContent ?? '', ...labelled].join('\n')
  }

  function lookupCalls(calls: Call[]): string[] {
    return calls
      .map((c) => new URL(c.url, 'http://x').pathname)
      .filter((path) => /\/agents\/[^/]+$/.test(path))
  }

  it('zeigt „Unbekannter Agent“ in Kopf und allen Gruppenaktionen, wenn getAgent fehlschlägt – nie die UUID', async () => {
    const { calls } = stubApi({
      items: [
        memory({ id: 'u1', agent_id: UNKNOWN, created_by_agent_id: UNKNOWN, fact: 'Fremder Agent merkt sich A.' }),
      ],
      // 3 auf dem Server, 1 geladen: „weitere von …“ und „Nur … zeigen“ erscheinen.
      agentCounts: { [UNKNOWN]: 3 },
      agentLookup: () => jsonResponse({ detail: 'forbidden', reason: 'forbidden' }, 403),
    })
    renderPage()
    const row = await screen.findByText('Fremder Agent merkt sich A.')
    const section = row.closest('section')!
    await waitFor(() => expect(lookupCalls(calls)).toEqual([`/v1/workspaces/ws-1/agents/${UNKNOWN}`]))

    expect(within(section).getByRole('heading', { level: 3 })).toHaveTextContent('Unbekannter Agent (3)')
    const approve = within(section).getByRole('button', { name: 'Alle 3 Einträge von Unbekannter Agent freigeben' })
    expect(approve).toHaveTextContent('Alle 3 von Unbekannter Agent freigeben')
    expect(within(section).getByText(/2 weitere von Unbekannter Agent/)).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Nur Unbekannter Agent zeigen' })).toBeInTheDocument()

    fireEvent.click(approve)
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('heading')).toHaveTextContent('3 Einträge von Unbekannter Agent freigeben?')

    expect(exposedText()).not.toContain(UNKNOWN)
    expect(exposedText()).not.toContain(UNKNOWN.slice(0, 8))
    // Kein Fehler-Toast fuer den stillen Rueckfall.
    const { notify } = await import('@/lib/feedback')
    expect(notify.error).not.toHaveBeenCalled()
  })

  it('zeigt den Namen, wenn der Agent nicht in der Liste steht, getAgent ihn aber liefert', async () => {
    const { calls } = stubApi({
      items: [memory({ id: 'u1', agent_id: UNKNOWN, created_by_agent_id: UNKNOWN, fact: 'Agent 101 merkt sich B.' })],
      agentCounts: { [UNKNOWN]: 1 },
      agentLookup: (id) =>
        jsonResponse({ id, name: 'archivar', tool_policy: { memory_mode: 'manual' } }),
    })
    renderPage()
    const row = await screen.findByText('Agent 101 merkt sich B.')
    const section = row.closest('section')!
    await waitFor(() =>
      expect(within(section).getByRole('heading', { level: 3 })).toHaveTextContent('archivar (1)'),
    )
    expect(within(section).getByRole('button', { name: 'Alle 1 Einträge von archivar freigeben' })).toBeInTheDocument()
    expect(exposedText()).not.toContain(UNKNOWN)
    expect(lookupCalls(calls)).toHaveLength(1)
  })

  it('hält zwei unbekannte Agenten in zwei getrennten Gruppen und fragt jeden genau einmal an', async () => {
    const { calls } = stubApi({
      items: [
        memory({ id: 'u1', agent_id: UNKNOWN, created_by_agent_id: UNKNOWN, fact: 'Erster Unbekannter.' }),
        memory({ id: 'u2', agent_id: UNKNOWN, created_by_agent_id: UNKNOWN, fact: 'Erster Unbekannter, zweiter Eintrag.' }),
        memory({ id: 'u3', agent_id: UNKNOWN_2, created_by_agent_id: UNKNOWN_2, fact: 'Zweiter Unbekannter.' }),
      ],
      agentCounts: { [UNKNOWN]: 2, [UNKNOWN_2]: 1 },
    })
    renderPage()
    const first = (await screen.findByText('Erster Unbekannter.')).closest('section')!
    const second = screen.getByText('Zweiter Unbekannter.').closest('section')!
    expect(first).not.toBe(second)
    expect(within(first).getByRole('heading', { level: 3 })).toHaveTextContent('Unbekannter Agent (2)')
    expect(within(second).getByRole('heading', { level: 3 })).toHaveTextContent('Unbekannter Agent (1)')
    expect(within(first).getByText('Erster Unbekannter, zweiter Eintrag.')).toBeInTheDocument()
    await waitFor(() => expect(lookupCalls(calls).sort()).toEqual(
      [`/v1/workspaces/ws-1/agents/${UNKNOWN_2}`, `/v1/workspaces/ws-1/agents/${UNKNOWN}`].sort(),
    ))
    expect(exposedText()).not.toContain(UNKNOWN)
    expect(exposedText()).not.toContain(UNKNOWN_2)
  })

  it('fragt bekannte Agenten nie einzeln an und lädt nach einem Reload nicht erneut', async () => {
    let lookups = 0
    stubApi({
      items: [
        memory({ id: 'k1', fact: 'Bekannter Agent.' }),
        memory({ id: 'u1', agent_id: UNKNOWN, created_by_agent_id: UNKNOWN, fact: 'Unbekannter Agent C.' }),
      ],
      agentCounts: { a1: 1, [UNKNOWN]: 1 },
      agentLookup: () => {
        lookups += 1
        return jsonResponse({ detail: 'not found' }, 404)
      },
      batch: () => jsonResponse({ results: [{ id: 'k1', ok: true }] }),
    })
    renderPage()
    await screen.findByText('Unbekannter Agent C.')
    await waitFor(() => expect(lookups).toBe(1))
    // Reload ueber eine Aktion (Stapel freigeben) -> gecachter 404, kein zweiter Abruf.
    fireEvent.click(screen.getByRole('checkbox', { name: /Bekannter Agent/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Auswahl freigeben (1)' }))
    const { notify } = await import('@/lib/feedback')
    await waitFor(() => expect(notify.success).toHaveBeenCalled())
    await screen.findByText('Unbekannter Agent C.')
    expect(lookups).toBe(1)
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
    fireEvent.change(screen.getByLabelText('Herkunft laut Agent'), {
      target: { value: 'inferred' },
    })
    await waitFor(() =>
      expect(calls.some((c) => /\/memories\?.*origin=inferred/.test(c.url))).toBe(true),
    )
    const chip = screen.getByRole('button', {
      name: 'Filter „Herkunft laut Agent: Vom Agenten geschlossen“ entfernen',
    })
    expect(screen.getByRole('list', { name: 'Aktive Filter' })).toContainElement(chip)
    expect(screen.getByRole('button', { name: 'Filter zurücksetzen' })).toBeInTheDocument()
  })

  it('setzt den Status über die Chips; 0er-Chips entfallen, Zahlen aus counts.groups.status', async () => {
    const { calls } = stubEntries({
      rows: [memory({ id: 'm1', status: 'active' })],
      counts: () =>
        jsonResponse({ total: 7, groups: { agent: { a1: 7 }, status: { active: 5, expired: 2 } } }),
    })
    renderPage('editor', ENTRIES)
    await screen.findByTestId('entries-list')
    const group = await screen.findByRole('group', { name: 'Nach Status filtern' })
    await waitFor(() =>
      expect(within(group).getByRole('button', { name: 'Alle 7' })).toHaveAttribute(
        'aria-pressed',
        'true',
      ),
    )
    expect(within(group).queryByRole('button', { name: /^Zur Freigabe/ })).toBeNull()
    expect(within(group).queryByRole('button', { name: /^Abgelehnt/ })).toBeNull()
    fireEvent.click(within(group).getByRole('button', { name: 'Abgelaufen 2' }))
    await waitFor(() =>
      expect(calls.some((c) => /\/memories\?.*status=expired/.test(c.url))).toBe(true),
    )
    // Status bekommt keinen Chip „Aktive Filter“, das Zuruecksetzen steht aber da.
    expect(screen.queryByRole('list', { name: 'Aktive Filter' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Filter zurücksetzen' })).toBeInTheDocument()
  })

  it('zeigt Facettenwerte mit Serverzahl, Agenten alphabetisch und den Hinweis zum gewählten Zustand', async () => {
    stubEntries({
      rows: [memory({ id: 'm1', status: 'active' })],
      counts: () =>
        jsonResponse({
          total: 3,
          groups: { agent: { a1: 3, a0: 1 }, health: { unconfirmed: 2 }, status: { active: 3 } },
        }),
    })
    renderPage('editor', `${ENTRIES}&health=unconfirmed`)
    await screen.findByTestId('entries-list')
    const health = screen.getByLabelText('Zustand')
    await waitFor(() =>
      expect(within(health).getByRole('option', { name: /^Unbestätigt \(2\)$/ })).toBeInTheDocument(),
    )
    // Werte mit 0 bleiben wählbar.
    expect(within(health).getAllByRole('option', { name: /\(0\)$/ }).length).toBe(4)
    // Alphabetisch, nicht nach Zahl: „a0“ (1) steht vor „coder“ (3).
    const agentOptions = within(screen.getByLabelText('Agent'))
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(agentOptions).toEqual(['Alle Agenten', 'a0 (1)', 'coder (3)'])
    const hintId = health.getAttribute('aria-describedby')
    expect(hintId).toBeTruthy()
    expect(document.getElementById(hintId!)?.textContent).not.toBe('')
  })

  it('zeigt gefiltert leer den Standard „Keine Treffer“ und setzt zurück', async () => {
    stubEntries({ rows: [], counts: () => jsonResponse({ total: 0, groups: {} }) })
    renderPage('editor', `${ENTRIES}&kind=lesson`)
    expect(await screen.findByText('Keine Treffer')).toBeInTheDocument()
    const resets = screen.getAllByRole('button', { name: 'Filter zurücksetzen' })
    expect(resets.length).toBe(2)
    fireEvent.click(resets[resets.length - 1])
    await waitFor(() => expect(screen.queryByText('Keine Treffer')).toBeNull())
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

  it('lädt die Liste auch ohne Zähler und sagt das klein in der Filterleiste', async () => {
    stubEntries({
      rows: [memory({ id: 'm1', status: 'active', fact: 'Bleibt sichtbar.' })],
      counts: () => jsonResponse({ detail: 'kaputt' }, 500),
    })
    renderPage('editor', ENTRIES)
    expect(await screen.findByText('Bleibt sichtbar.')).toBeInTheDocument()
    expect(await screen.findByText('Zahlen gerade nicht verfügbar.')).toBeInTheDocument()
    // Ohne Zahlen: Chips und Werte nur mit Wort.
    expect(
      within(screen.getByRole('group', { name: 'Nach Status filtern' })).getByRole('button', {
        name: 'Alle',
      }),
    ).toBeInTheDocument()
    expect(within(screen.getByLabelText('Agent')).getByRole('option', { name: 'coder' })).toBeInTheDocument()
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

  it('legt unter md die Facetten in das Sheet: „Filter (n)“, Fuß „n Treffer zeigen“, Fokus zurück', async () => {
    viewport.mobile = true
    stubEntries({
      rows: [memory({ id: 'm1', status: 'active' })],
      counts: () => jsonResponse({ total: 12, groups: { agent: { a1: 12 }, status: { active: 12 } } }),
    })
    renderPage('editor', `${ENTRIES}&kind=lesson`)
    await screen.findByTestId('entries-list')
    // Inline gibt es keine Selects; der Knopf zählt nur gesetzte Facetten.
    expect(screen.queryByLabelText('Zustand')).toBeNull()
    const button = screen.getByRole('button', { name: 'Filter (1)' })
    fireEvent.click(button)
    const sheet = await screen.findByRole('dialog', { name: 'Filter' })
    expect(within(sheet).getByLabelText('Art')).toHaveValue('lesson')
    expect(within(sheet).getByLabelText('Sortierung')).toBeInTheDocument()
    fireEvent.click(await within(sheet).findByRole('button', { name: '12 Treffer zeigen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(button).toHaveFocus()
  })

  it('hat keine axe-Violations mit offenem Filter-Sheet', async () => {
    viewport.mobile = true
    stubEntries({ rows: [memory({ id: 'm1', status: 'active' })] })
    renderPage('editor', ENTRIES)
    await screen.findByTestId('entries-list')
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
    await screen.findByRole('dialog', { name: 'Filter' })
    expect(await axe(document.body)).toHaveNoViolations()
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
    const search = screen.getByLabelText('Suche')
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
