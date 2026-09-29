import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '@/api/types'
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
    pending_memories: 2,
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
    // Neue Aufmerksamkeits-Signale: pending Memories + System-Prompt-Reviews,
    // jeweils mit Deep-Link in die Triage-Fläche.
    expect(
      screen.getByText('2 neue Gedächtniseinträge warten auf Freigabe'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Agenten öffnen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/agents',
    )
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
    // Ohne Reviews, pending Memories und System-Prompt-Reviews (Felder fehlen
    // im Payload → Fallback 0) zeigt das Band den Alles-erledigt-Zustand.
    expect(screen.getByText('Alles erledigt')).toBeInTheDocument()
    expect(screen.queryByText(/Gedächtniseint/)).not.toBeInTheDocument()
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

  // Antwortet je Pfad: Dashboard-Aggregat bzw. die jeweilige Liste.
  function routedFetch(dashboard: DashboardData, lists: Record<string, unknown[]>) {
    return vi.fn().mockImplementation((url: string) => {
      const path = new URL(String(url), 'http://x').pathname
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
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  // Wartet, bis die Listen-Requests beantwortet und verarbeitet sind — sonst
  // saehe ein fehlender Direktlink auch vor dem Laden gruen aus.
  async function settleLists(fetchMock: ReturnType<typeof vi.fn>, count: number) {
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1 + count))
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
