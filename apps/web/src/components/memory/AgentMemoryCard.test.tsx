import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_TOOL_POLICY,
  type Agent,
  type Me,
  type MemoryCounts,
  type MemoryProposalRead,
  type MemoryRead,
  type WorkspaceRole,
} from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'
import { axe } from '@/test/a11y'

import { AgentMemoryCard } from './AgentMemoryCard'

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
      writable: true,
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

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'a1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'coder',
    description: '',
    persona_id: 'p1',
    system_prompt_template_id: 'sp1',
    status: 'enabled',
    tool_policy: { ...DEFAULT_TOOL_POLICY, memory_mode: 'suggest' },
    persona_active: true,
    activatable: true,
    missing: [],
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  }
}

function memory(overrides: Partial<MemoryRead>): MemoryRead {
  return {
    id: 'm1',
    agent_id: 'a1',
    status: 'active',
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
    confirmed_at: null,
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

interface StubOptions {
  items?: MemoryRead[]
  pending?: number
  proposals?: MemoryProposalRead[]
  total?: number
  notes?: number
}

interface Call {
  method: string
  url: URL
}

function stubApi({
  items = [memory({})],
  pending = 0,
  proposals = [],
  total = items.length,
  notes = items.filter((m) => m.kind === 'agent_note').length,
}: StubOptions = {}) {
  const calls: Call[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const url = new URL(String(input), 'http://x')
    calls.push({ method, url })
    const path = url.pathname
    if (method === 'DELETE' && /\/agents\/a1\/memories$/.test(path)) return jsonResponse(null, 204)
    if (path.endsWith('/memories/counts')) {
      if (url.searchParams.get('status') === 'pending') return jsonResponse({ total: pending })
      const counts: MemoryCounts = {
        total,
        groups: { kind: { agent_note: notes, user_fact: total - notes } },
      }
      return jsonResponse(counts)
    }
    if (path.endsWith('/memories')) return jsonResponse({ items, next_cursor: null })
    // Einzelabruf des Deep-Links (`GET /memories/{id}`, nicht Besitzer-Pfade).
    const single = /^\/v1\/workspaces\/[^/]+\/memories\/([^/]+)$/.exec(path)
    if (single !== null) {
      const hit = items.find((m) => m.id === single[1])
      return hit !== undefined
        ? jsonResponse(hit)
        : jsonResponse({ detail: 'Memory nicht gefunden.', reason: 'memory_not_found' }, 404)
    }
    if (path.endsWith('/memory-proposals')) return jsonResponse(proposals)
    if (path.endsWith('/history')) return jsonResponse([])
    if (path.endsWith('/agents')) return jsonResponse([agent()])
    return jsonResponse([])
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls }
}

function renderCard(loaded: Agent = agent(), role: WorkspaceRole = 'editor', entry = '/w/ws-1/agents/a1') {
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
            <Route path="/w/:workspaceId/agents/:id" element={<AgentMemoryCard agent={loaded} />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  viewport.mobile = false
})

describe('AgentMemoryCard (C5b-2, Spec §6.6)', () => {
  it('fragt die Liste mit fest gesetztem Agenten an und rendert keine Agent-Facette', async () => {
    const { calls } = stubApi()
    renderCard()

    expect(await screen.findByText('CI läuft auf Podman.')).toBeInTheDocument()
    const lists = calls.filter((c) => c.method === 'GET' && c.url.pathname.endsWith('/memories'))
    expect(lists.length).toBeGreaterThan(0)
    for (const call of lists) {
      expect(call.url.searchParams.get('agent_id')).toBe('a1')
      expect(call.url.searchParams.get('scope')).toBe('agent')
    }
    // Kein Aufruf der Legacy-Liste `/agents/{id}/memories`.
    expect(calls.some((c) => /\/agents\/a1\/memories$/.test(c.url.pathname))).toBe(false)

    // Fester Agent als Text ohne ✕; die Leiste (Filter-Standard §3.1) hat
    // ab `md` die Selects im Raster — ohne Agent-Facette und ohne Knopf.
    expect(screen.getByTestId('memory-fixed-agent')).toHaveTextContent('Agent: coder')
    expect(screen.queryByRole('button', { name: /Filter „Agent/ })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Art' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Zustand' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Sortierung' })).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Agent' })).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Nach Status filtern' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Filter \(0\)$/ })).not.toBeInTheDocument()

    // Die Zeile verlinkt nicht auf die Seite, auf der sie steht.
    const row = screen.getAllByTestId('entry-row')[0]
    expect(within(row).queryByRole('link', { name: /coder/ })).not.toBeInTheDocument()
  })

  it('„In der Gedächtnisverwaltung öffnen“ übernimmt Agent und gesetzte Filter', async () => {
    stubApi()
    renderCard()
    await screen.findByText('CI läuft auf Podman.')

    const link = screen.getByTestId('memory-open-central')
    expect(link).toHaveAttribute('href', '/w/ws-1/memory?tab=entries&agent=a1')

    // Erklärsatz-Knopf setzt die Art (Spec §6.2) — der Link nimmt sie mit.
    fireEvent.click(screen.getByRole('button', { name: 'Agentennotiz' }))
    await waitFor(() => {
      expect(screen.getByTestId('memory-open-central')).toHaveAttribute(
        'href',
        '/w/ws-1/memory?tab=entries&agent=a1&kind=agent_note',
      )
    })
  })

  it('Facette als Select: Chip „Art: …“, Zurücksetzen leert Facette und Suche, Sortierung bleibt', async () => {
    const { calls } = stubApi()
    renderCard()
    await screen.findByText('CI läuft auf Podman.')

    fireEvent.change(screen.getByRole('combobox', { name: 'Sortierung' }), {
      target: { value: 'oldest' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Art' }), {
      target: { value: 'agent_note' },
    })
    const chips = await screen.findByRole('list', { name: 'Aktive Filter' })
    expect(within(chips).getByRole('button', { name: 'Filter „Art: Agentennotiz“ entfernen' }))
      .toBeInTheDocument()
    await waitFor(() =>
      expect(
        calls.some(
          (c) =>
            c.url.pathname.endsWith('/memories') && c.url.searchParams.get('kind') === 'agent_note',
        ),
      ).toBe(true),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Filter zurücksetzen' }))
    await waitFor(() =>
      expect(screen.queryByRole('list', { name: 'Aktive Filter' })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('combobox', { name: 'Art' })).toHaveValue('')
    // Anzeige ist kein Filter: die Sortierung bleibt beim Zurücksetzen stehen.
    expect(screen.getByRole('combobox', { name: 'Sortierung' })).toHaveValue('oldest')
  })

  it('unter md: „Filter“ ohne Zahl öffnet das Sheet von unten, ohne Agent-Facette', async () => {
    viewport.mobile = true
    stubApi({ total: 3 })
    renderCard()
    await screen.findByText('CI läuft auf Podman.')

    expect(screen.queryByRole('combobox', { name: 'Art' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
    const sheet = await screen.findByTestId('list-filter-sheet')
    expect(within(sheet).getByRole('combobox', { name: 'Art' })).toBeInTheDocument()
    expect(within(sheet).getByRole('combobox', { name: 'Sortierung' })).toBeInTheDocument()
    expect(within(sheet).queryByRole('combobox', { name: 'Agent' })).not.toBeInTheDocument()

    fireEvent.change(within(sheet).getByRole('combobox', { name: 'Art' }), {
      target: { value: 'lesson' },
    })
    // Fuß „n Treffer zeigen“ schließt nur; der Fokus geht zurück auf „Filter (n)“.
    fireEvent.click(await within(sheet).findByRole('button', { name: '3 Treffer zeigen' }))
    await waitFor(() => expect(screen.queryByTestId('list-filter-sheet')).toBeNull())
    const toggle = screen.getByRole('button', { name: 'Filter (1)' })
    await waitFor(() => expect(toggle).toHaveFocus())
    expect(screen.getByRole('button', { name: 'Filter „Art: Lernvorschlag“ entfernen' }))
      .toBeInTheDocument()
  })

  it('hat mit offenem Filter-Sheet keine axe-Verstöße', async () => {
    viewport.mobile = true
    stubApi()
    const { baseElement } = renderCard()
    await screen.findByTestId('entry-row')
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
    await screen.findByTestId('list-filter-sheet')
    expect(await axe(baseElement)).toHaveNoViolations()
  })

  it('zeigt den Freigabe-Hinweis nur mit offenen Einträgen und verlinkt in die Warteschlange', async () => {
    stubApi({ pending: 3 })
    renderCard()

    const hint = await screen.findByTestId('memory-pending-hint')
    expect(hint).toHaveTextContent('3 Einträge warten auf Freigabe.')
    expect(within(hint).getByRole('link', { name: 'Zur Freigabe' })).toHaveAttribute(
      'href',
      '/w/ws-1/memory?tab=approval&agent=a1',
    )
  })

  it('ohne offene Einträge kein Freigabe-Hinweis', async () => {
    stubApi({ pending: 0 })
    renderCard()
    await screen.findByText('CI läuft auf Podman.')
    expect(screen.queryByTestId('memory-pending-hint')).not.toBeInTheDocument()
  })

  it('viewer: keine Karte und keine Anfrage an das Agentengedächtnis', async () => {
    const { calls } = stubApi()
    const { container } = renderCard(agent(), 'viewer')
    await waitFor(() => expect(container).toBeEmptyDOMElement())
    expect(calls.some((c) => c.url.pathname.includes('/memories'))).toBe(false)
  })

  it('Gedächtnis aus: Hinweis und Liste nur lesend, ohne Auswahl und Zeilenaktion', async () => {
    stubApi({ items: [memory({ confirmed_at: null })] })
    renderCard(agent({ tool_policy: { ...DEFAULT_TOOL_POLICY, memory_mode: 'off' } }))

    expect(
      await screen.findByText('Das Gedächtnis ist für diesen Agenten aus.'),
    ).toBeInTheDocument()
    const row = await screen.findByTestId('entry-row')
    expect(within(row).queryByRole('checkbox')).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: 'Bestätigen' })).not.toBeInTheDocument()
  })

  it('Gedächtnis an: unbestätigter Eintrag hat Checkbox und „Bestätigen“', async () => {
    stubApi({ items: [memory({ confirmed_at: null })] })
    renderCard()
    const row = await screen.findByTestId('entry-row')
    expect(within(row).getByRole('checkbox')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Bestätigen' })).toBeInTheDocument()
    expect(screen.queryByText('Das Gedächtnis ist für diesen Agenten aus.')).not.toBeInTheDocument()
  })

  it('Füllstand aus den Zählern, ab 90 % „fast voll“', async () => {
    stubApi({ total: 190, notes: 185 })
    renderCard()
    const fill = await screen.findByTestId('memory-fill')
    expect(fill).toHaveTextContent('5 von 500 Einträgen')
    expect(fill).toHaveTextContent('185 von 200 Agentennotizen')
    expect(within(fill).getAllByText('fast voll')).toHaveLength(1)
  })

  it('„Alle löschen“ im Overflow nennt die Anzahl und ruft DELETE /agents/{id}/memories', async () => {
    const { calls } = stubApi({ total: 12, notes: 4 })
    renderCard()
    await screen.findByTestId('memory-fill')

    const trigger = screen.getByRole('button', { name: 'Weitere Aktionen zum Gedächtnis von coder' })
    fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false })
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Alle löschen' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Alle 12 Einträge endgültig löschen?')).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: '12 löschen' }))

    await waitFor(() => expect(notify.success).toHaveBeenCalledWith('Alle Erinnerungen gelöscht.'))
    expect(
      calls.some((c) => c.method === 'DELETE' && /\/agents\/a1\/memories$/.test(c.url.pathname)),
    ).toBe(true)
  })

  it('ohne Einträge kein Overflow und der Leerzustand des Agenten', async () => {
    stubApi({ items: [], total: 0, notes: 0 })
    renderCard()
    expect(await screen.findByText('Noch keine Erinnerungen')).toBeInTheDocument()
    expect(screen.queryByTestId('memory-actions')).not.toBeInTheDocument()
  })

  it('Deep-Link #memory hebt die Karte kurz hervor', async () => {
    stubApi()
    renderCard(agent(), 'editor', '/w/ws-1/agents/a1#memory')
    const card = await screen.findByTestId('agent-memory-card')
    expect(card).toHaveAttribute('id', 'memory')
    await waitFor(() => expect(card).toHaveAttribute('data-highlighted', 'true'))
  })

  it('Chevron je Zeile öffnet das Detail-Sheet über ?entry= (kein toter Knopf)', async () => {
    const { calls } = stubApi({ items: [memory({ fact: 'Nutzt uv statt pip.' })] })
    renderCard()
    const chevron = await screen.findByTestId('open-detail')
    expect(chevron).toHaveAccessibleName('Details zu „Nutzt uv statt pip.“ öffnen')
    fireEvent.click(chevron)
    const sheet = await screen.findByTestId('memory-detail-sheet')
    expect(within(sheet).getByTestId('detail-fact')).toHaveTextContent('Nutzt uv statt pip.')
    // Eintrag kam aus der Liste mit: Verlauf geladen, keine Suche nach ihm.
    await waitFor(() =>
      expect(calls.some((c) => /\/agents\/a1\/memories\/m1\/history$/.test(c.url.pathname))).toBe(
        true,
      ),
    )
    fireEvent.keyDown(sheet, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByTestId('memory-detail-sheet')).toBeNull())
  })

  it('Deep-Link ?entry= auf der Agent-Seite öffnet das Sheet', async () => {
    stubApi({ items: [memory({ fact: 'Nutzt uv statt pip.' })] })
    renderCard(agent(), 'editor', '/w/ws-1/agents/a1?entry=m1')
    const sheet = await screen.findByTestId('memory-detail-sheet')
    expect(await within(sheet).findByTestId('detail-fact')).toHaveTextContent('Nutzt uv statt pip.')
  })

  it('hat keine axe-Verstöße', async () => {
    stubApi({ pending: 2, items: [memory({ confirmed_at: null })] })
    const { container } = renderCard()
    await screen.findByTestId('memory-pending-hint')
    await screen.findByTestId('entry-row')
    expect(await axe(container)).toHaveNoViolations()
  })
})
