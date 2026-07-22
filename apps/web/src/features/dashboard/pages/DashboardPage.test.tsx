import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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
    expect(screen.getByText(/warten auf Review/)).toBeInTheDocument()
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
    expect(screen.getByRole('img', { name: /Personae:/ })).toBeInTheDocument()
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
})
