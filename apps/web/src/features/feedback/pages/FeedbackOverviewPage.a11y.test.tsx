import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { FeedbackOverview } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { FeedbackOverviewPage } from './FeedbackOverviewPage'

const { getFeedbackOverview, getFeedbackItems } = vi.hoisted(() => ({
  getFeedbackOverview: vi.fn(),
  getFeedbackItems: vi.fn(),
}))

vi.mock('@/api/useApi', () => {
  const api = { getFeedbackOverview, getFeedbackItems }
  return { useApi: () => api }
})

describe('FeedbackOverviewPage (a11y)', () => {
  it('hat keine axe-Violations mit Daten', async () => {
    const overview: FeedbackOverview = {
      items: [
        {
          entity_type: 'playbook',
          entity_id: 'pb1',
          name: 'Onboarding',
          usage_count: 12,
          feedback_count: 3,
          negative_count: 2,
          helpful_count: 1,
          last_activity_at: '2026-06-20T10:00:00Z',
        },
      ],
    }
    getFeedbackOverview.mockResolvedValue(overview)
    getFeedbackItems.mockResolvedValue({
      items: [
        {
          id: 'fb1',
          entity_type: 'persona',
          entity_id: 'pe1',
          name: 'Coach-Persona',
          version: 2,
          signal: 'outdated',
          note: 'Schritt 4 veraltet',
          agent_id: 'a1',
          created_at: '2026-06-20T10:00:00Z',
          resolution: null,
        },
      ],
      counts: { open: 1, in_progress: 0, addressed: 0, dismissed: 0 },
    })
    const { container } = renderInRoutes(<FeedbackOverviewPage />, {
      path: '/w/:workspaceId/feedback',
      initialEntries: ['/w/ws-1/feedback'],
    })

    // Posteingang-Tab (Default) axe-prüfen …
    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Coach-Persona' })).toBeInTheDocument(),
    )
    expect(await axe(container)).toHaveNoViolations()
    // … dann in den Kurations-Tab wechseln und dort ebenfalls prüfen.
    fireEvent.click(screen.getByRole('tab', { name: /Kuration/ }))
    await waitFor(() => expect(screen.getByRole('link', { name: 'Onboarding' })).toBeInTheDocument())
    expect(await axe(container)).toHaveNoViolations()
  })
})
