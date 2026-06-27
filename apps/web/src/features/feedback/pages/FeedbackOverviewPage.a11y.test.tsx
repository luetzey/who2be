import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { FeedbackOverview } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { FeedbackOverviewPage } from './FeedbackOverviewPage'

const { getFeedbackOverview, getFeedbackUnused } = vi.hoisted(() => ({
  getFeedbackOverview: vi.fn(),
  getFeedbackUnused: vi.fn(),
}))

vi.mock('@/api/useApi', () => {
  const api = { getFeedbackOverview, getFeedbackUnused }
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
    getFeedbackUnused.mockResolvedValue({
      items: [{ entity_type: 'resource', entity_id: 'r9', name: 'Altes Doku' }],
    })
    const { container } = renderInRoutes(<FeedbackOverviewPage />, {
      path: '/w/:workspaceId/feedback',
      initialEntries: ['/w/ws-1/feedback'],
    })

    await waitFor(() => expect(screen.getByRole('link', { name: 'Onboarding' })).toBeInTheDocument())
    expect(await axe(container)).toHaveNoViolations()
  })
})
