import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { DashboardPage } from './DashboardPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const sampleData: DashboardData = {
  kpis: { active_personas: 2, active_playbooks: 4, pending_reviews: 1 },
  activity: [
    {
      ts: '2026-05-28T10:00:00Z',
      actor: { user_id: 'u1', display_name: 'Alice' },
      entity_type: 'persona',
      entity_id: 'p1',
      entity_name: 'Coach',
      event: 'created',
      from_version: null,
      to_version: 1,
    },
  ],
  status_distribution: {
    persona: { draft: 1, review: 0, active: 2, inactive: 0 },
    playbook: { draft: 0, review: 1, active: 4, inactive: 0 },
  },
}

describe('DashboardPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(sampleData), { status: 200 }),
      ),
    )

    const { container } = renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('Letzte Aktivitäten')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
