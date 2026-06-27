import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FeedbackOverview, FeedbackUnused } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { FeedbackOverviewPage } from './FeedbackOverviewPage'

const { getFeedbackOverview, getFeedbackUnused, getFeedbackItems } = vi.hoisted(() => ({
  getFeedbackOverview: vi.fn(),
  getFeedbackUnused: vi.fn(),
  getFeedbackItems: vi.fn(),
}))

// Stabile API-Referenz (wie der echte `useMemo`-basierte `useApi`) — sonst
// feuert der `useEffect(load,[load])` des Hooks in einer Schleife.
vi.mock('@/api/useApi', () => {
  const api = { getFeedbackOverview, getFeedbackUnused, getFeedbackItems }
  return { useApi: () => api }
})

const EMPTY_UNUSED: FeedbackUnused = { items: [] }
const EMPTY_ITEMS = {
  items: [],
  counts: { open: 0, in_progress: 0, addressed: 0, dismissed: 0 },
}

beforeEach(() => {
  // Der Posteingang (FeedbackInbox) laedt eigenstaendig; in den Page-Tests
  // pruefen wir den Ueberblick-Teil, daher der Posteingang hier leer.
  getFeedbackItems.mockResolvedValue(EMPTY_ITEMS)
})

function renderPage() {
  return renderInRoutes(<FeedbackOverviewPage />, {
    path: '/w/:workspaceId/feedback',
    initialEntries: ['/w/ws-1/feedback'],
  })
}

describe('FeedbackOverviewPage', () => {
  it('listet Elemente mit Kennzahlen und verlinkt auf die Detailseite', async () => {
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
    getFeedbackUnused.mockResolvedValue(EMPTY_UNUSED)
    renderPage()

    const link = await screen.findByRole('link', { name: 'Onboarding' })
    expect(link).toHaveAttribute('href', '/w/ws-1/playbooks/pb1')
    expect(screen.getByText('12')).toBeInTheDocument()
    // Negativ-Zähler als destructive Badge.
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('zeigt einen Empty-State, wenn kein Feedback vorliegt', async () => {
    getFeedbackOverview.mockResolvedValue({ items: [] } satisfies FeedbackOverview)
    getFeedbackUnused.mockResolvedValue(EMPTY_UNUSED)
    renderPage()

    await waitFor(() =>
      expect(screen.getByText('Noch kein Feedback in diesem Workspace.')).toBeInTheDocument(),
    )
  })

  it('listet ungenutzte aktive Elemente in der Stale-Sektion', async () => {
    getFeedbackOverview.mockResolvedValue({ items: [] } satisfies FeedbackOverview)
    getFeedbackUnused.mockResolvedValue({
      items: [{ entity_type: 'resource', entity_id: 'r9', name: 'Altes Doku' }],
    } satisfies FeedbackUnused)
    renderPage()

    const link = await screen.findByRole('link', { name: 'Altes Doku' })
    expect(link).toHaveAttribute('href', '/w/ws-1/resources/r9')
  })
})
