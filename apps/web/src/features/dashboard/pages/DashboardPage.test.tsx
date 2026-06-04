import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { DashboardPage } from './DashboardPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const sampleData: DashboardData = {
  kpis: { active_personas: 12, active_playbooks: 34, pending_reviews: 3 },
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
  },
}

function jsonFetch(payload: unknown, status = 200) {
  return vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(payload), { status }))
}

describe('DashboardPage', () => {
  it('rendert KPIs, Activity-Eintraege und Status-Bars', async () => {
    vi.stubGlobal('fetch', jsonFetch(sampleData))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument()
    })
    expect(screen.getByText('34')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText(/Alice/)).toBeInTheDocument()
    expect(screen.getByText(/Coaching/)).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: /Personae:/ }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: /Playbooks:/ }),
    ).toBeInTheDocument()
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
    expect(screen.getByText(/zur Review eingereicht/)).toBeInTheDocument()
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
  })
})
