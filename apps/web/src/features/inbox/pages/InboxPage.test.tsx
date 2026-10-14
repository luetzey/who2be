import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { InboxCounts, Me, WorkspaceRole } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { formatDay } from '../../evolution/lib/followUp'
import { InboxPage } from './InboxPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

function meWithRole(role: WorkspaceRole): Me {
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

const AGENTS = [
  { id: 'a1', name: 'Support-Assistent' },
  { id: 'a2', name: 'Recherche-Agent' },
]

function memory(id: string, fact: string, agentId: string | null = 'a1') {
  return {
    id,
    agent_id: agentId,
    status: 'pending',
    fact,
    context: null,
    category: 'fact',
    importance: 5,
    source: 'agent',
    triage_note: null,
    retrieval_count: 0,
    last_retrieved_at: null,
    created_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    updated_at: new Date().toISOString(),
    scope: agentId === null ? 'user' : 'agent',
  }
}

function caseRow(id: string, behavior: string, status = 'open', agentId = 'a1') {
  return {
    id,
    workspace_id: 'ws-1',
    agent_id: agentId,
    reporter_kind: 'human',
    reporter_user_id: 'u1',
    reporter_agent_id: null,
    situation: 'Kunde fragt',
    behavior,
    impact: null,
    expected_behavior: 'Richtig antworten',
    severity: 'normal',
    signal: null,
    source_ref: null,
    source_feedback_id: null,
    source_memory_id: null,
    status,
    created_at: new Date(Date.now() - 86400_000).toISOString(),
  }
}

interface Fixture {
  counts: InboxCounts | 'error'
  memories?: unknown[] | 'error'
  cases?: unknown[]
  personas?: unknown[]
  /** Seiten von `/feedback-sessions` je Cursor (`''` = erste Seite). */
  sessions?: Record<string, { items: unknown[]; next?: string }> | 'error'
  /** Haelt die Antwort auf die zweite Seite an, bis `release()` gerufen wird. */
  holdMore?: { promise: Promise<void> }
}

const ADMIN_COUNTS: InboxCounts = {
  follow_ups_due: 1,
  memory_approval: 2,
  versions_review: 1,
  system_prompts_review: 0,
  cases_open: 7,
  patterns: 2,
  total: 11,
}

/** Antwortet je Pfad; merkt sich alle aufgerufenen URLs. */
function stubApi(fixture: Fixture) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    calls.push(url)
    const json = (payload: unknown, status = 200) =>
      new Response(JSON.stringify(payload), { status })
    if (url.includes('/feedback-sessions')) {
      if (fixture.sessions === 'error') return json({ detail: 'boom' }, 500)
      const cursor = new URL(url, 'http://x').searchParams.get('cursor') ?? ''
      if (cursor !== '' && fixture.holdMore) await fixture.holdMore.promise
      const page = fixture.sessions?.[cursor] ?? { items: [] }
      return new Response(JSON.stringify(page.items), {
        status: 200,
        headers: page.next ? { 'X-Next-Cursor': page.next } : {},
      })
    }
    if (url.includes('/inbox/counts')) {
      return fixture.counts === 'error'
        ? json({ detail: 'boom' }, 500)
        : json(fixture.counts)
    }
    if (url.includes('/memories')) {
      return fixture.memories === 'error'
        ? json({ detail: 'boom' }, 500)
        : json({ items: fixture.memories ?? [], next_cursor: null })
    }
    if (url.includes('/cases')) return json(fixture.cases ?? [])
    if (url.includes('/agents')) return json(AGENTS)
    if (url.includes('/personas')) return json(fixture.personas ?? [])
    if (url.includes('/playbooks') || url.includes('/resources') || url.includes('/system-prompt'))
      return json([])
    return json({})
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

function renderPage(role: WorkspaceRole, entry = '/w/ws-1/inbox') {
  return renderInRoutes(<InboxPage />, {
    path: '/w/:workspaceId/inbox',
    initialEntries: [entry],
    me: meWithRole(role),
  })
}

const sectionOrder = () =>
  Array.from(document.querySelectorAll('[data-testid^="inbox-section-"]'))
    .map((node) => node.getAttribute('data-testid'))
    .filter((id) => id !== null && !id.endsWith('-error'))

/** Lokaler Kalendertag `YYYY-MM-DD`, `offset` Tage von heute. */
function day(offset: number): string {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function session(
  id: string,
  opts: { agentId?: string; created?: string; next?: string | null; due?: number; measures?: number } = {},
) {
  return {
    id,
    workspace_id: 'ws-1',
    agent_id: opts.agentId ?? 'a1',
    trigger: 'manual',
    participants: [],
    summary: 'Zusammenfassung',
    decisions: [],
    dissent: [],
    follow_up_at: opts.next ?? day(-1),
    supersedes_id: null,
    submitted_by_kind: 'agent',
    submitted_by: 'b1',
    case_ids: [],
    created_at: `${opts.created ?? '2026-09-25'}T10:00:00Z`,
    case_count: 1,
    measure_count: opts.measures ?? 3,
    next_follow_up_at: opts.next === undefined ? day(-1) : opts.next,
    due_measure_count: opts.due ?? 1,
    superseded_by_id: null,
  }
}

const sessionCalls = (calls: string[]) => calls.filter((url) => url.includes('/feedback-sessions'))

describe('InboxPage', () => {
  it('admin: Arten in der Reihenfolge aus §2.2, Zahl im Namen der Überschrift', async () => {
    stubApi({
      counts: ADMIN_COUNTS,
      memories: [memory('m1', 'Rückgabefrist ist 30 Tage')],
      cases: [caseRow('c1', 'Nannte falsche Frist', 'reopened')],
      personas: [{ id: 'p1', name: 'Erstattung', current_version: 3, current_status: 'review' }],
    })
    renderPage('admin')

    expect(await screen.getByRole('heading', { level: 1, name: 'Zu erledigen' })).toBeInTheDocument()
    await screen.findByRole('heading', { name: 'Nachkontrollen fällig, 1' })
    expect(screen.getByRole('heading', { name: 'Gedächtnis zur Freigabe, 2' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Versionen zur Freigabe, 1' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Rückmeldungen, nicht eingeordnet, 7' })).toBeInTheDocument()
    expect(sectionOrder()).toEqual([
      'inbox-section-followUps',
      'inbox-section-memory',
      'inbox-section-versions',
      'inbox-section-cases',
      'inbox-section-look',
    ])

    // Zeilen springen zur Fachseite (N7 a), eine Aktion je Zeile.
    const memoryLink = await screen.findByRole('link', { name: 'Prüfen: Rückgabefrist ist 30 Tage' })
    expect(memoryLink).toHaveAttribute('href', '/w/ws-1/memory?tab=approval&entry=m1')
    const caseLink = await screen.findByRole('link', { name: 'Einordnen: Nannte falsche Frist' })
    expect(caseLink).toHaveAttribute('href', '/w/ws-1/feedback/cases/c1')
    expect(screen.getByText(/wieder offen/)).toBeInTheDocument()
    const versionLink = await screen.findByRole('link', { name: 'Erstattung Version 3 öffnen' })
    expect(versionLink).toHaveAttribute('href', '/w/ws-1/personas/p1?tab=versions&diff=3')

    // „Alle n ansehen“ nur, wo die Art mehr hat als die Zeilen.
    const cases = screen.getByTestId('inbox-section-cases')
    expect(within(cases).getByRole('link', { name: /Alle 7 ansehen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback?tab=cases',
    )
    // Admin: Versionen sind Aufgabe, unter „Zum Anschauen“ nur Muster.
    const look = screen.getByTestId('inbox-section-look')
    expect(within(look).getByText('2 Muster')).toBeInTheDocument()
    expect(within(look).queryByText(/warten auf Freigabe/)).not.toBeInTheDocument()
  })

  it('lädt je Art höchstens 5 Zeilen (limit=5) und keine Suche', async () => {
    const calls = stubApi({ counts: ADMIN_COUNTS, memories: [], cases: [] })
    renderPage('admin')
    await waitFor(() => {
      expect(calls.some((url) => url.includes('/cases?'))).toBe(true)
      expect(calls.some((url) => url.includes('/memories?'))).toBe(true)
    })
    const caseCall = calls.find((url) => url.includes('/cases?')) ?? ''
    expect(caseCall).toContain('limit=5')
    expect(caseCall).toContain('status=open')
    expect(caseCall).toContain('status=reopened')
    expect(calls.find((url) => url.includes('/memories?'))).toContain('limit=5')
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
  })

  it('editor: Versionen nicht als Aufgabe, sondern unter „Zum Anschauen“', async () => {
    stubApi({
      counts: { ...ADMIN_COUNTS, total: 10 },
      personas: [{ id: 'p1', name: 'Erstattung', current_version: 3, current_status: 'review' }],
    })
    renderPage('editor')
    await screen.findByRole('heading', { name: 'Rückmeldungen, nicht eingeordnet, 7' })
    expect(screen.queryByTestId('inbox-section-versions')).not.toBeInTheDocument()
    const look = screen.getByTestId('inbox-section-look')
    expect(
      await within(look).findByText('1 Version wartet auf Freigabe durch einen Admin'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Freigaben/ })).not.toBeInTheDocument()
  })

  it('viewer: nur Gedächtnis (eigenes Nutzergedächtnis), keine Filterleiste', async () => {
    const calls = stubApi({
      counts: { memory_approval: 1, follow_ups_due: null, versions_review: null, system_prompts_review: null, cases_open: null, patterns: null, total: 1 },
      memories: [memory('m9', 'Ich mag kurze Antworten', null)],
    })
    renderPage('viewer')
    await screen.findByRole('heading', { name: 'Gedächtnis zur Freigabe, 1' })
    expect(sectionOrder()).toEqual(['inbox-section-memory'])
    expect(await screen.findByText(/Dein Nutzergedächtnis/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Alle/ })).not.toBeInTheDocument()
    await waitFor(() => expect(calls.some((url) => url.includes('/memories?'))).toBe(true))
    expect(calls.find((url) => url.includes('/memories?'))).toContain('scope=user')
    expect(calls.some((url) => url.includes('/agents'))).toBe(false)
    expect(calls.some((url) => url.includes('/cases'))).toBe(false)
  })

  it('Leerzustand „Alles erledigt“, wenn nichts offen ist', async () => {
    stubApi({
      counts: { follow_ups_due: 0, memory_approval: 0, versions_review: 0, system_prompts_review: 0, cases_open: 0, patterns: 0, total: 0 },
    })
    renderPage('admin')
    expect(await screen.findByText('Alles erledigt')).toBeInTheDocument()
    expect(screen.getByText('Neue Aufgaben erscheinen hier und an der Glocke.')).toBeInTheDocument()
    expect(sectionOrder()).toEqual([])
  })

  it('?agent= filtert Zähler und Listen und reicht den Agenten an „Alle ansehen“ weiter', async () => {
    const calls = stubApi({
      counts: { ...ADMIN_COUNTS, versions_review: null, system_prompts_review: null, total: 10 },
      memories: [memory('m1', 'A')],
      cases: [caseRow('c1', 'B')],
    })
    renderPage('admin', '/w/ws-1/inbox?agent=a2')
    await screen.findByRole('heading', { name: 'Rückmeldungen, nicht eingeordnet, 7' })
    await waitFor(() => {
      expect(calls.some((url) => url.includes('/inbox/counts?agent_id=a2'))).toBe(true)
      expect(calls.some((url) => url.includes('/cases?') && url.includes('agent_id=a2'))).toBe(true)
      expect(calls.some((url) => url.includes('/memories?') && url.includes('agent_id=a2'))).toBe(true)
    })
    expect(screen.getByRole('link', { name: /Alle 7 ansehen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback?tab=cases&agent=a2',
    )
    // Mit Agent gibt es keine Versionen (eine Version gehoert keinem Agenten).
    expect(screen.queryByTestId('inbox-section-versions')).not.toBeInTheDocument()
  })

  it('?kind= zeigt nur die gewählte Art; Chip-Wechsel schreibt die URL', async () => {
    stubApi({ counts: ADMIN_COUNTS, memories: [memory('m1', 'A')], cases: [] })
    renderPage('admin', '/w/ws-1/inbox?kind=memory')
    await screen.findByRole('heading', { name: 'Gedächtnis zur Freigabe, 2' })
    expect(sectionOrder()).toEqual(['inbox-section-memory'])

    fireEvent.click(screen.getByRole('button', { name: /Rückmeldungen 7/ }))
    await screen.findByRole('heading', { name: 'Rückmeldungen, nicht eingeordnet, 7' })
    expect(screen.queryByTestId('inbox-section-memory')).not.toBeInTheDocument()
  })

  it('Fehler je Abschnitt: andere Abschnitte bleiben stehen, Erneut versuchen lädt neu', async () => {
    const calls = stubApi({ counts: ADMIN_COUNTS, memories: 'error', cases: [caseRow('c1', 'B')] })
    renderPage('admin')
    expect(await screen.findByTestId('inbox-section-memory-error')).toHaveTextContent(
      'Konnte nicht geladen werden.',
    )
    expect(await screen.findByRole('link', { name: 'Einordnen: B' })).toBeInTheDocument()
    const before = calls.filter((url) => url.includes('/memories?')).length
    fireEvent.click(
      within(screen.getByTestId('inbox-section-memory-error')).getByRole('button', {
        name: 'Erneut versuchen',
      }),
    )
    await waitFor(() =>
      expect(calls.filter((url) => url.includes('/memories?')).length).toBe(before + 1),
    )
  })

  it('Zähler nicht ladbar: seitenweiter Fehler mit Erneut versuchen', async () => {
    stubApi({ counts: 'error' })
    renderPage('admin')
    expect(await screen.findByText('Die Aufgaben konnten nicht geladen werden.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Erneut versuchen' })).toBeInTheDocument()
  })

  it('teilt sich je Seite EINE Zähler-Instanz (Glocke + Seite = zwei Abrufe)', async () => {
    const calls = stubApi({ counts: ADMIN_COUNTS, memories: [], cases: [] })
    renderPage('admin')
    await screen.findByRole('heading', { name: 'Rückmeldungen, nicht eingeordnet, 7' })
    await waitFor(() => expect(calls.filter((url) => url.includes('/inbox/counts')).length).toBe(2))
  })
})

describe('InboxPage — Nachkontrollen (E5j, Neuschnitt §5)', () => {
  const FOLLOW_COUNTS: InboxCounts = {
    follow_ups_due: 3,
    memory_approval: 0,
    versions_review: 0,
    system_prompts_review: 0,
    cases_open: 0,
    patterns: 0,
    total: 3,
  }

  it('editor: je Review eine Zeile mit Pill, Server-Zahl und Link auf first-due', async () => {
    const calls = stubApi({
      counts: FOLLOW_COUNTS,
      sessions: {
        '': {
          items: [
            session('s1', { created: '2026-09-25', next: day(-1), due: 1 }),
            session('s2', { agentId: 'a2', created: '2026-09-12', next: day(-2), due: 2 }),
          ],
        },
      },
    })
    renderPage('editor')

    // Abschnittszahl bleibt `follow_ups_due` (Änderungen), Zeilen sind Reviews.
    await screen.findByRole('heading', { name: 'Nachkontrollen fällig, 3' })
    const link = await screen.findByRole('link', {
      name: 'Nachkontrolle öffnen: Review vom 25.09.2026 · Support-Assistent',
    })
    expect(link).toHaveAttribute('href', '/w/ws-1/agents/a1/reviews/s1?change=first-due')
    const section = screen.getByTestId('inbox-section-followUps')
    expect(within(section).getByText('seit 1 Tag fällig')).toBeInTheDocument()
    expect(within(section).getByText('seit 2 Tagen fällig')).toBeInTheDocument()
    expect(
      within(section).getByText(`1 Änderung zur Nachkontrolle · Termin ${formatDay(day(-1))}`),
    ).toBeInTheDocument()
    expect(
      within(section).getByRole('link', {
        name: 'Nachkontrolle öffnen: Review vom 12.09.2026 · Recherche-Agent',
      }),
    ).toHaveAttribute('href', '/w/ws-1/agents/a2/reviews/s2?change=first-due')
    // Ohne Agent-Filter kein Link auf den Tab, ohne Cursor kein „Weitere laden“.
    expect(screen.queryByTestId('inbox-followups-more')).not.toBeInTheDocument()

    // Ein Request, serverseitig gefiltert und begrenzt — kein N+1 auf Details.
    const list = sessionCalls(calls)
    expect(list).toHaveLength(1)
    expect(list[0]).toContain('due=true')
    expect(list[0]).toContain('limit=5')
    expect(calls.some((url) => /\/feedback-sessions\/s\d/.test(url))).toBe(false)
  })

  it('eine Quelle: Zeilen, Zahl und Fälligkeit kommen vom Server, das Web rechnet nicht nach', async () => {
    // Server sagt fällig, obwohl der Termin lokal morgen ist (UTC-Stichtag);
    // `due_measure_count` 2 bei `measure_count` 5; Abschnittszahl 3 ≠ Zeilensumme.
    stubApi({
      counts: FOLLOW_COUNTS,
      sessions: { '': { items: [session('s1', { next: day(1), due: 2, measures: 5 })] } },
    })
    renderPage('admin')
    await screen.findByRole('heading', { name: 'Nachkontrollen fällig, 3' })
    const section = screen.getByTestId('inbox-section-followUps')
    expect(
      await within(section).findByRole('link', { name: /Nachkontrolle öffnen: Review vom/ }),
    ).toBeInTheDocument()
    expect(within(section).getByText('heute fällig')).toBeInTheDocument()
    expect(within(section).getByText(/^2 Änderungen zur Nachkontrolle/)).toBeInTheDocument()
    expect(within(section).queryByText(/5 Änderungen/)).not.toBeInTheDocument()
  })

  it('viewer: kein Request an /feedback-sessions', async () => {
    const calls = stubApi({
      // Selbst wenn der Server (fehlerhaft) eine Zahl liefert, fragt viewer nicht.
      counts: { ...FOLLOW_COUNTS, follow_ups_due: 2 },
      sessions: { '': { items: [session('s1')] } },
    })
    renderPage('viewer')
    await screen.findByRole('heading', { level: 1, name: 'Zu erledigen' })
    await screen.findByTestId('inbox-section-followUps')
    // Kurz warten, damit ein (falscher) Effekt sicher gelaufen wäre.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(sessionCalls(calls)).toHaveLength(0)
    expect(screen.queryByRole('link', { name: /Nachkontrolle öffnen/ })).not.toBeInTheDocument()
  })

  it('Fehler der Liste: nur dieser Abschnitt zeigt den Fehler, die anderen bleiben stehen', async () => {
    const calls = stubApi({
      counts: { ...FOLLOW_COUNTS, cases_open: 1, total: 4 },
      sessions: 'error',
      cases: [caseRow('c1', 'B')],
    })
    renderPage('editor')
    expect(await screen.findByTestId('inbox-section-followUps-error')).toHaveTextContent(
      'Konnte nicht geladen werden.',
    )
    expect(await screen.findByRole('link', { name: 'Einordnen: B' })).toBeInTheDocument()
    expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
    const before = sessionCalls(calls).length
    fireEvent.click(
      within(screen.getByTestId('inbox-section-followUps-error')).getByRole('button', {
        name: 'Erneut versuchen',
      }),
    )
    await waitFor(() => expect(sessionCalls(calls).length).toBe(before + 1))
  })

  it('„Weitere laden“ hängt die nächste Seite an; Doppelklick löst nur einen Request aus', async () => {
    let release: () => void = () => {}
    const hold = new Promise<void>((resolve) => {
      release = resolve
    })
    const first = ['s1', 's2', 's3', 's4', 's5'].map((id) => session(id))
    const calls = stubApi({
      counts: { ...FOLLOW_COUNTS, follow_ups_due: 6, total: 6 },
      sessions: { '': { items: first, next: 'c2' }, c2: { items: [session('s6')] } },
      holdMore: { promise: hold },
    })
    renderPage('editor')
    const more = await screen.findByRole('button', { name: 'Weitere laden' })
    expect(screen.queryByRole('link', { name: /Alle \d+ ansehen/ })).not.toBeInTheDocument()

    // Zwei Klicks ohne Render dazwischen: die Sperre muss vor `disabled` greifen.
    act(() => {
      more.click()
      more.click()
    })
    await waitFor(() =>
      expect(sessionCalls(calls).filter((url) => url.includes('cursor=c2'))).toHaveLength(1),
    )
    expect(screen.getByRole('button', { name: 'Lädt …' })).toBeDisabled()
    release()

    const section = screen.getByTestId('inbox-section-followUps')
    await waitFor(() =>
      expect(within(section).getAllByRole('link', { name: /Nachkontrolle öffnen/ })).toHaveLength(6),
    )
    expect(sessionCalls(calls).filter((url) => url.includes('cursor=c2'))).toHaveLength(1)
    expect(sessionCalls(calls).find((url) => url.includes('cursor=c2'))).toContain('due=true')
    // Ohne weiteren Cursor verschwindet der Knopf.
    expect(screen.queryByRole('button', { name: 'Weitere laden' })).not.toBeInTheDocument()
  })

  it('?agent= filtert die Liste und bietet „Bei {{agent}} ansehen“ auf den Tab', async () => {
    const calls = stubApi({
      counts: { ...FOLLOW_COUNTS, versions_review: null, system_prompts_review: null },
      sessions: { '': { items: [session('s1', { agentId: 'a2' })] } },
    })
    renderPage('editor', '/w/ws-1/inbox?agent=a2&kind=followUps')
    await screen.findByRole('link', { name: /Nachkontrolle öffnen/ })
    expect(sessionCalls(calls)[0]).toContain('agent_id=a2')
    expect(await screen.findByRole('link', { name: 'Bei Recherche-Agent ansehen' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a2?tab=evolution',
    )
  })

  it('ohne fällige Nachkontrolle: kein Abschnitt und kein Request', async () => {
    const calls = stubApi({
      counts: { ...FOLLOW_COUNTS, follow_ups_due: 0, total: 0 },
    })
    renderPage('editor')
    expect(await screen.findByText('Alles erledigt')).toBeInTheDocument()
    expect(sessionCalls(calls)).toHaveLength(0)
  })
})
