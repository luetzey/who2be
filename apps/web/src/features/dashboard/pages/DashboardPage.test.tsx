import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData, Me, WorkspaceRole } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { DashboardPage } from './DashboardPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const sampleData: DashboardData = {
  kpis: {
    active_personas: 12,
    active_playbooks: 34,
    active_resources: 7,
    pending_reviews: 3,
    pending_system_prompts: 1,
  },
  activity: [
    {
      ts: '2026-05-28T10:00:00Z',
      actor: { user_id: 'u1', display_name: 'Alice' },
      entity_type: 'playbook',
      entity_id: 'pb1',
      entity_name: 'Coaching',
      event: 'promoted_to_active',
      from_version: 3,
      to_version: 4,
    },
  ],
  status_distribution: {
    persona: { draft: 2, review: 1, active: 12, inactive: 8 },
    playbook: { draft: 1, review: 0, active: 34, inactive: 5 },
    resource: { draft: 1, review: 0, active: 7, inactive: 1 },
  },
}

function jsonFetch(payload: unknown, status = 200) {
  return vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(payload), { status }))
}

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

describe('DashboardPage', () => {
  it('rendert KPIs, Attention-Band, Activity-Eintraege und Status-Bars', async () => {
    vi.stubGlobal('fetch', jsonFetch(sampleData))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText(/Alice/)).toBeInTheDocument()
    })
    // KPI-Zahlen im Kennzahlen-Bereich pruefen (die bloßen Zahlen tauchen sonst
    // auch in der Balken-Ablesung auf).
    const kpis = screen.getByRole('region', { name: 'Kennzahlen' })
    expect(within(kpis).getByText('12')).toBeInTheDocument()
    expect(within(kpis).getByText('34')).toBeInTheDocument()
    // Aktive-Resources-KPI (aus kpis.active_resources).
    expect(within(kpis).getByText('7')).toBeInTheDocument()
    // Pending-Reviews steckt jetzt im Aufmerksamkeits-Band statt in einer KPI.
    expect(screen.getByText('3 Versionen liegen zur Review')).toBeInTheDocument()
    // Der Gedaechtnis-Banner zaehlt aus `/memories/counts` (rollengerecht).
    // Ohne Rolle (Default-`me` ohne Mitgliedschaft) fragt er nichts an und
    // zeigt nichts.
    expect(screen.queryByText(/zur Freigabe/)).not.toBeInTheDocument()
    expect(screen.getByText('1 System-Prompt liegt zur Review')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Zur Review/ })).toHaveAttribute(
      'href',
      '/w/ws-1/system-prompts?status=review',
    )
    // Solange etwas ansteht, gibt es kein „Alles erledigt".
    expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
    expect(screen.getByText(/Alice/)).toBeInTheDocument()
    expect(screen.getByText(/Coaching/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Personas:/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Playbooks:/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Resources:/ })).toBeInTheDocument()
  })

  it('zeigt einen Empty-State, wenn der Endpoint 404 liefert', async () => {
    vi.stubGlobal('fetch', jsonFetch({ detail: 'not found' }, 404))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(
        screen.getByText('Dashboard noch nicht verfügbar.'),
      ).toBeInTheDocument()
    })
  })

  it('rendert auch ohne actor (Legacy-Payload) ohne Crash', async () => {
    // Regression: vor Phase-3 Fix Track 1 lieferte das Backend die
    // `status_history`-Rohzeilen — kein `actor`. `ActivityRow` darf das
    // nicht abstuerzen lassen.
    const legacy = {
      kpis: { active_personas: 1, active_playbooks: 1, pending_reviews: 0 },
      activity: [
        {
          ts: '2026-05-28T10:00:00Z',
          entity_type: 'persona' as const,
          entity_id: 'p1',
          event: 'submitted_for_review',
        },
      ],
      status_distribution: {
        persona: { draft: 0, review: 1, active: 1, inactive: 0 },
        playbook: { draft: 0, review: 0, active: 1, inactive: 0 },
      },
    }
    vi.stubGlobal('fetch', jsonFetch(legacy))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('Unbekannt')).toBeInTheDocument()
    })
    expect(screen.getByText(/reichte zur Review ein/)).toBeInTheDocument()
  })

  it('blaettert die Activity seitenbasiert und fragt page=2 an', async () => {
    const paged: DashboardData = {
      kpis: { active_personas: 1, active_playbooks: 1, pending_reviews: 0 },
      activity: [
        {
          ts: '2026-05-28T10:00:00Z',
          actor: { user_id: 'u1', display_name: 'Alice' },
          entity_type: 'playbook',
          entity_id: 'pb1',
          entity_name: 'Coaching',
          event: 'promoted_to_active',
        },
      ],
      activity_pagination: { page: 1, page_size: 20, total: 25, total_pages: 2 },
      status_distribution: {
        persona: { draft: 0, review: 0, active: 1, inactive: 0 },
        playbook: { draft: 0, review: 0, active: 1, inactive: 0 },
      },
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(paged), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('Seite 1 von 2')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Weiter/ }))

    await waitFor(() => {
      const calledWithPage2 = fetchMock.mock.calls.some(([url]) =>
        String(url).includes('page=2'),
      )
      expect(calledWithPage2).toBe(true)
    })
  })

  it('feuert keinen Request und zeigt Preparing-State ohne Workspace-ID', async () => {
    // Kein `:workspaceId`-Param in der Route UND `me.default_workspace_id`
    // leer ⇒ `useWorkspaceId()` liefert ''. Der Hook darf dann NICHT
    // `/v1/workspaces//dashboard` feuern (sonst 404 oder „nicht erreichbar"),
    // sondern einen Preparing-State zeigen.
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(sampleData), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    renderInRoutes(<DashboardPage />, {
      path: '/dashboard',
      initialEntries: ['/dashboard'],
      me: { user_id: 'u1', default_workspace_id: null, organizations: [] },
    })

    await waitFor(() => {
      expect(screen.getByText('Workspace wird vorbereitet …')).toBeInTheDocument()
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('zeigt eine Empty-Hint, wenn keine Aktivitaeten vorliegen', async () => {
    const empty: DashboardData = {
      kpis: { active_personas: 0, active_playbooks: 0, pending_reviews: 0 },
      activity: [],
      status_distribution: {
        persona: { draft: 0, review: 0, active: 0, inactive: 0 },
        playbook: { draft: 0, review: 0, active: 0, inactive: 0 },
      },
    }
    vi.stubGlobal('fetch', jsonFetch(empty))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('Noch keine Aktivitäten.')).toBeInTheDocument()
    })
    // Ohne Rolle gibt es keine belegte Gedaechtnis-Zahl — dann behauptet das
    // Band auch kein „Alles erledigt“ (der Fall mit Rolle und 0 steht unten).
    expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
    expect(screen.queryByText(/zur Freigabe/)).not.toBeInTheDocument()
    expect(screen.queryByText(/liegt zur Review|liegen zur Review/)).not.toBeInTheDocument()
  })

  // §4.4 Checklistenpunkt 5: Flex-Kinder mit Textinhalt tragen `min-w-0`,
  // damit lange Statuslabels auf 320px nicht aus der Legende laufen.
  it('haelt die Legenden-Eintraege der Statusverteilung schrumpffaehig', async () => {
    vi.stubGlobal('fetch', jsonFetch(sampleData))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText(/Alice/)).toBeInTheDocument()
    })
    // Nur die Legende der Statusverteilung, nicht jede `<li>` der Seite: die
    // Legende haengt im CardHeader neben dem Titel.
    const legendItems = screen
      .getByRole('heading', { name: 'Status-Verteilung' })
      .parentElement!.querySelectorAll('li')
    expect(legendItems.length).toBeGreaterThan(0)
    for (const item of legendItems) {
      expect(item).toHaveClass('min-w-0')
    }
  })
})

// Audit A4: Der Review-Banner fuehrt zur Pruefung — bis drei offene Versionen
// direkt in die Pruefansicht (ein Klick), darueber auf die gefilterte Liste.
describe('DashboardPage — Review-Banner (Audit A4)', () => {
  const dist = (review: number) => ({ draft: 0, review, active: 1, inactive: 0 })

  function reviewData(pending: number, persona: number, playbook: number, resource: number) {
    return {
      kpis: { active_personas: 1, active_playbooks: 1, pending_reviews: pending },
      activity: [],
      status_distribution: {
        persona: dist(persona),
        playbook: dist(playbook),
        resource: dist(resource),
      },
    } satisfies DashboardData
  }

  const item = (id: string, name: string, version: number, status: string) => ({
    id,
    name,
    current_version: version,
    current_status: status,
  })

  // Antwortet je Pfad: Dashboard-Aggregat bzw. die jeweilige Liste. Die
  // Glocke in der Kopfleiste (Navigation W1) zaehlt nebenher; ihr Request
  // geht in `pageCalls` nicht mit ein.
  function routedFetch(dashboard: DashboardData, lists: Record<string, unknown[]>) {
    return vi.fn().mockImplementation((url: string) => {
      const path = new URL(String(url), 'http://x').pathname
      if (path.endsWith('/inbox/counts')) {
        return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
      }
      if (path.endsWith('/dashboard')) {
        return Promise.resolve(new Response(JSON.stringify(dashboard), { status: 200 }))
      }
      const type = path.split('/').pop() ?? ''
      if (type in lists) {
        return Promise.resolve(new Response(JSON.stringify(lists[type]), { status: 200 }))
      }
      return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
    })
  }

  function renderDashboard() {
    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })
  }

  // Requests der Seite selbst, ohne den Zaehler der Glocke.
  function pageCalls(fetchMock: ReturnType<typeof vi.fn>): number {
    return fetchMock.mock.calls.filter(([url]) => !String(url).includes('/inbox/counts')).length
  }

  it('Singular: eine Version, Direktlink auf die Pruefansicht', async () => {
    const fetchMock = routedFetch(reviewData(1, 1, 0, 0), {
      personas: [item('p1', 'Builder (Kopie)', 2, 'review'), item('p2', 'Coach', 1, 'active')],
    })
    vi.stubGlobal('fetch', fetchMock)
    renderDashboard()

    const link = await screen.findByRole('link', { name: /Builder \(Kopie\) v2 prüfen/ })
    expect(link).toHaveAttribute('href', '/w/ws-1/personas/p1?tab=versions&diff=2')
    expect(screen.getByText('1 Version liegt zur Review')).toBeInTheDocument()
    // Nur die Liste mit offenen Reviews wird geladen, Playbooks/Resources nicht.
    const paths = fetchMock.mock.calls.map(([url]) => new URL(String(url), 'http://x').pathname)
    expect(paths.some((p) => p.endsWith('/personas'))).toBe(true)
    expect(paths.some((p) => p.endsWith('/playbooks') || p.endsWith('/resources'))).toBe(false)
  })

  it('bis drei Versionen: je ein Direktlink, ueber alle Typen', async () => {
    vi.stubGlobal(
      'fetch',
      routedFetch(reviewData(3, 1, 1, 1), {
        personas: [item('p1', 'Builder', 2, 'review')],
        playbooks: [item('pb1', 'Onboarding call', 3, 'review')],
        resources: [item('r1', 'Pricing sheet', 4, 'review')],
      }),
    )
    renderDashboard()

    expect(await screen.findByRole('link', { name: /Onboarding call v3 prüfen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks/pb1?tab=versions&diff=3',
    )
    expect(screen.getByRole('link', { name: /Builder v2 prüfen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/personas/p1?tab=versions&diff=2',
    )
    expect(screen.getByRole('link', { name: /Pricing sheet v4 prüfen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/resources/r1?tab=versions&diff=4',
    )
    expect(screen.getByText('3 Versionen liegen zur Review')).toBeInTheDocument()
  })

  it('mehr als drei Versionen: Link auf die gefilterte Liste je Typ, keine Listen-Requests', async () => {
    const fetchMock = routedFetch(reviewData(4, 3, 1, 0), {})
    vi.stubGlobal('fetch', fetchMock)
    renderDashboard()

    expect(await screen.findByRole('link', { name: /3 Personas prüfen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/personas?status=review',
    )
    expect(screen.getByRole('link', { name: /1 Playbook prüfen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks?status=review',
    )
    expect(screen.queryByRole('link', { name: /Resources? prüfen/ })).not.toBeInTheDocument()
    expect(screen.getByText('4 Versionen liegen zur Review')).toBeInTheDocument()
    expect(pageCalls(fetchMock)).toBe(1)
  })

  // Wartet, bis die Listen-Requests beantwortet und verarbeitet sind — sonst
  // saehe ein fehlender Direktlink auch vor dem Laden gruen aus.
  async function settleLists(fetchMock: ReturnType<typeof vi.fn>, count: number) {
    await waitFor(() => expect(pageCalls(fetchMock)).toBe(1 + count))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
  }

  it('faellt auf die Liste zurueck, wenn die Listen nicht alle Versionen liefern', async () => {
    const fetchMock = routedFetch(reviewData(2, 2, 0, 0), {
      personas: [item('p1', 'Builder', 2, 'review')],
    })
    vi.stubGlobal('fetch', fetchMock)
    renderDashboard()

    await settleLists(fetchMock, 1)
    expect(screen.getByRole('link', { name: /2 Personas prüfen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/personas?status=review',
    )
    expect(screen.queryByRole('link', { name: /Builder v2 prüfen/ })).not.toBeInTheDocument()
  })

  it('faellt auf die Liste zurueck, wenn eine Liste nicht laedt', async () => {
    const fetchMock = routedFetch(reviewData(1, 0, 1, 0), {})
    vi.stubGlobal('fetch', fetchMock)
    renderDashboard()

    await settleLists(fetchMock, 1)
    expect(screen.getByRole('link', { name: /1 Playbook prüfen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks?status=review',
    )
  })
})

// Lernschleife C5a-2: Der Gedaechtnis-Banner zaehlt aus derselben Quelle wie
// der Tab „Zur Freigabe“ (`/memories/counts?status=pending` + offene
// Vorschlaege) und verlinkt auf `/memory?tab=approval`.
describe('DashboardPage — Banner „Einträge zur Freigabe“ (C5a-2)', () => {
  const quiet: DashboardData = {
    kpis: { active_personas: 1, active_playbooks: 1, pending_reviews: 0 },
    activity: [],
    status_distribution: {
      persona: { draft: 0, review: 0, active: 1, inactive: 0 },
      playbook: { draft: 0, review: 0, active: 1, inactive: 0 },
    },
  }

  function memoryFetch({
    pending,
    proposals = 0,
    failCounts = false,
  }: {
    pending: number
    proposals?: number
    failCounts?: boolean
  }) {
    return vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://x')
      const json = (body: unknown, status = 200) =>
        Promise.resolve(new Response(JSON.stringify(body), { status }))
      if (url.pathname.endsWith('/dashboard')) return json(quiet)
      if (url.pathname.endsWith('/memories/counts')) {
        return failCounts ? json({ detail: 'boom' }, 500) : json({ total: pending })
      }
      if (url.pathname.endsWith('/memory-proposals')) {
        return json(
          Array.from({ length: proposals }, (_, i) => ({ id: `p${i}`, status: 'pending' })),
        )
      }
      // D6h: editor+ fragen zusaetzlich Muster und Fall-Zaehler an; leer.
      if (url.pathname.endsWith('/patterns')) {
        return json({ threshold: 3, window_days: 30, patterns: [] })
      }
      if (url.pathname.endsWith('/cases/counts')) return json({ open: 0, reopened: 0 })
      return json({ detail: 'nope' }, 500)
    })
  }

  function memoryUrls(fetchMock: ReturnType<typeof vi.fn>): URL[] {
    return fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://x'))
      .filter((url) => /\/(memories|memory-proposals)/.test(url.pathname))
  }

  function renderAs(role: WorkspaceRole) {
    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
      me: meWithRole(role),
    })
  }

  it('editor: zählt pending plus offene Vorschläge und verlinkt auf /memory?tab=approval', async () => {
    const fetchMock = memoryFetch({ pending: 2, proposals: 1 })
    vi.stubGlobal('fetch', fetchMock)
    renderAs('editor')

    expect(await screen.findByText('3 Einträge zur Freigabe')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Freigeben/ })).toHaveAttribute(
      'href',
      '/w/ws-1/memory?tab=approval',
    )
    const counts = memoryUrls(fetchMock).filter((u) => u.pathname.endsWith('/memories/counts'))
    expect(counts).toHaveLength(1)
    expect(counts[0].searchParams.get('status')).toBe('pending')
    // editor+: Agentengedaechtnis und eigenes Nutzergedaechtnis — der Server
    // filtert fremdes Nutzergedaechtnis; der Client grenzt nicht auf `user` ein.
    expect(counts[0].searchParams.has('scope')).toBe(false)
    expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
  })

  it('viewer: fragt nur scope=user an', async () => {
    const fetchMock = memoryFetch({ pending: 1 })
    vi.stubGlobal('fetch', fetchMock)
    renderAs('viewer')

    expect(await screen.findByText('1 Eintrag zur Freigabe')).toBeInTheDocument()
    const counts = memoryUrls(fetchMock).filter((u) => u.pathname.endsWith('/memories/counts'))
    expect(counts.length).toBeGreaterThan(0)
    for (const url of counts) {
      expect(url.searchParams.get('scope')).toBe('user')
    }
  })

  it.each(['viewer', 'editor', 'admin'] as const)(
    '%s: kein Request mit subject_user_id (auch nicht als Zahl)',
    async (role) => {
      const fetchMock = memoryFetch({ pending: 1 })
      vi.stubGlobal('fetch', fetchMock)
      renderAs(role)

      await screen.findByText('1 Eintrag zur Freigabe')
      const urls = memoryUrls(fetchMock)
      expect(urls.length).toBeGreaterThan(0)
      for (const url of urls) {
        expect(url.search).not.toContain('subject_user_id')
      }
    },
  )

  it('bei 0: kein Banner, „Alles erledigt“', async () => {
    vi.stubGlobal('fetch', memoryFetch({ pending: 0 }))
    renderAs('editor')

    expect(await screen.findByText('Alles erledigt')).toBeInTheDocument()
    expect(screen.queryByText(/zur Freigabe/)).not.toBeInTheDocument()
  })

  it('Zählerfehler: kein Banner und kein „Alles erledigt“', async () => {
    const fetchMock = memoryFetch({ pending: 0, failCounts: true })
    vi.stubGlobal('fetch', fetchMock)
    renderAs('editor')

    await waitFor(() => {
      expect(memoryUrls(fetchMock).length).toBeGreaterThan(0)
    })
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
    expect(screen.queryByText(/zur Freigabe/)).not.toBeInTheDocument()
    expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
  })
})

// Lernschleife D6h (Delta-Spec „Dashboard“, Spec §10): „{{count}} Muster“ aus
// `GET /patterns` und „{{count}} offene Fälle“ (open + reopened) aus
// `GET /cases/counts`, nur fuer editor+. viewer fragen nichts davon an.
describe('DashboardPage — Muster und offene Fälle (D6h)', () => {
  const quiet: DashboardData = {
    kpis: { active_personas: 1, active_playbooks: 1, pending_reviews: 0 },
    activity: [],
    status_distribution: {
      persona: { draft: 0, review: 0, active: 1, inactive: 0 },
      playbook: { draft: 0, review: 0, active: 1, inactive: 0 },
    },
  }

  const pattern = (i: number) => ({
    source: 'lesson',
    agent_id: 'a1',
    element: null,
    count: 3,
    evidence_ids: [`m${i}`],
    first_seen: '2026-10-01T00:00:00Z',
    last_seen: '2026-10-08T00:00:00Z',
  })

  const counts = (open: number, reopened: number) => ({
    open,
    triaged: 4,
    in_progress: 0,
    addressed: 2,
    verified: 0,
    reopened,
    dismissed: 1,
  })

  function triageFetch({
    patterns = 0,
    open = 0,
    reopened = 0,
    failPatterns = false,
    failCounts = false,
  }: {
    patterns?: number
    open?: number
    reopened?: number
    failPatterns?: boolean
    failCounts?: boolean
  }) {
    return vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://x')
      const json = (body: unknown, status = 200) =>
        Promise.resolve(new Response(JSON.stringify(body), { status }))
      if (url.pathname.endsWith('/dashboard')) return json(quiet)
      if (url.pathname.endsWith('/memories/counts')) return json({ total: 0 })
      if (url.pathname.endsWith('/memory-proposals')) return json([])
      if (url.pathname.endsWith('/patterns')) {
        if (failPatterns) return json({ detail: 'boom' }, 500)
        return json({
          threshold: 3,
          window_days: 30,
          patterns: Array.from({ length: patterns }, (_, i) => pattern(i)),
        })
      }
      if (url.pathname.endsWith('/cases/counts')) {
        return failCounts ? json({ detail: 'boom' }, 500) : json(counts(open, reopened))
      }
      return json({ detail: 'nope' }, 500)
    })
  }

  // Alle Aufrufe gegen Muster und Faelle (Liste wie Zaehler).
  function triageUrls(fetchMock: ReturnType<typeof vi.fn>): URL[] {
    return fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://x'))
      .filter((url) => /\/(patterns|cases)(\/|$)/.test(url.pathname))
  }

  function renderAs(role: WorkspaceRole) {
    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
      me: meWithRole(role),
    })
  }

  async function settle() {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
  }

  it.each(['editor', 'admin'] as const)(
    '%s: zeigt beide Einträge mit Aktion und Ziel',
    async (role) => {
      const fetchMock = triageFetch({ patterns: 2, open: 3, reopened: 2 })
      vi.stubGlobal('fetch', fetchMock)
      renderAs(role)

      expect(await screen.findByText('2 Muster')).toBeInTheDocument()
      expect(screen.getByText('Lernvorschläge oder Fälle, die sich wiederholen.')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Ansehen/ })).toHaveAttribute(
        'href',
        '/w/ws-1/feedback?tab=patterns',
      )
      // open + reopened, nicht triaged/addressed/dismissed.
      expect(await screen.findByText('5 offene Fälle')).toBeInTheDocument()
      expect(
        screen.getByText('Gemeldete Situationen, die noch niemand eingeordnet hat.'),
      ).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Einordnen/ })).toHaveAttribute(
        'href',
        '/w/ws-1/feedback?tab=cases',
      )
      expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
      // Gezaehlt wird ueber den Zaehler-Endpunkt; die Fall-Liste wird nie geladen.
      const paths = triageUrls(fetchMock).map((url) => url.pathname)
      expect(paths.filter((p) => p.endsWith('/cases/counts'))).toHaveLength(1)
      expect(paths.filter((p) => p.endsWith('/patterns'))).toHaveLength(1)
      expect(paths.some((p) => p.endsWith('/cases'))).toBe(false)
    },
  )

  it('Singular: „1 Muster“ und „1 offener Fall“', async () => {
    vi.stubGlobal('fetch', triageFetch({ patterns: 1, open: 0, reopened: 1 }))
    renderAs('editor')

    expect(await screen.findByText('1 Muster')).toBeInTheDocument()
    expect(await screen.findByText('1 offener Fall')).toBeInTheDocument()
  })

  it('editor ohne Daten: keine Einträge, „Alles erledigt“', async () => {
    const fetchMock = triageFetch({})
    vi.stubGlobal('fetch', fetchMock)
    renderAs('editor')

    expect(await screen.findByText('Alles erledigt')).toBeInTheDocument()
    expect(triageUrls(fetchMock)).toHaveLength(2)
    expect(screen.queryByText(/Muster$/)).not.toBeInTheDocument()
    expect(screen.queryByText(/offene[rn]? F(a|ä)ll/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Ansehen|Einordnen/ })).not.toBeInTheDocument()
  })

  it('viewer: keine Aufrufe gegen Muster oder Fälle, keine Einträge', async () => {
    const fetchMock = triageFetch({ patterns: 2, open: 3 })
    vi.stubGlobal('fetch', fetchMock)
    renderAs('viewer')

    // Das restliche Band laedt (Gedaechtnis-Zaehler mit 0) ...
    expect(await screen.findByText('Alles erledigt')).toBeInTheDocument()
    await settle()
    // ... aber Muster und Faelle werden nie angefragt.
    expect(fetchMock).toHaveBeenCalled()
    expect(triageUrls(fetchMock)).toHaveLength(0)
    expect(screen.queryByText('2 Muster')).not.toBeInTheDocument()
    expect(screen.queryByText(/offene Fälle/)).not.toBeInTheDocument()
  })

  it('Rolle unbekannt: keine Aufrufe gegen Muster oder Fälle', async () => {
    const fetchMock = triageFetch({ patterns: 2, open: 3 })
    vi.stubGlobal('fetch', fetchMock)
    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    expect(await screen.findByText('Letzte Aktivitäten')).toBeInTheDocument()
    await settle()
    expect(triageUrls(fetchMock)).toHaveLength(0)
  })

  it('Muster-Fehler: Fall-Eintrag und restliches Dashboard bleiben stehen', async () => {
    vi.stubGlobal('fetch', triageFetch({ failPatterns: true, open: 2 }))
    renderAs('editor')

    expect(await screen.findByText('2 offene Fälle')).toBeInTheDocument()
    await settle()
    expect(screen.queryByRole('link', { name: /Ansehen/ })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Kennzahlen' })).toBeInTheDocument()
    expect(screen.getByText('Letzte Aktivitäten')).toBeInTheDocument()
    // Eine unbelegte Zahl behauptet kein „Alles erledigt“.
    expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
  })

  it('Zähler-Fehler: Muster-Eintrag und restliches Dashboard bleiben stehen', async () => {
    vi.stubGlobal('fetch', triageFetch({ patterns: 3, failCounts: true }))
    renderAs('editor')

    expect(await screen.findByText('3 Muster')).toBeInTheDocument()
    await settle()
    expect(screen.queryByRole('link', { name: /Einordnen/ })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Kennzahlen' })).toBeInTheDocument()
    expect(screen.getByText('Letzte Aktivitäten')).toBeInTheDocument()
    expect(screen.queryByText('Alles erledigt')).not.toBeInTheDocument()
  })
})
