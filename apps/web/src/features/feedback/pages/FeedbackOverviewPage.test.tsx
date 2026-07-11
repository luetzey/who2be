import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FeedbackOverview } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { FeedbackOverviewPage } from './FeedbackOverviewPage'

const { getFeedbackOverview, getFeedbackItems } = vi.hoisted(() => ({
  getFeedbackOverview: vi.fn(),
  getFeedbackItems: vi.fn(),
}))

// Stabile API-Referenz (wie der echte `useMemo`-basierte `useApi`) — sonst
// feuert der `useEffect(load,[load])` des Hooks in einer Schleife.
vi.mock('@/api/useApi', () => {
  const api = { getFeedbackOverview, getFeedbackItems }
  return { useApi: () => api }
})

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
    renderPage()

    const link = await screen.findByRole('link', { name: 'Onboarding' })
    expect(link).toHaveAttribute('href', '/w/ws-1/feedback/playbook/pb1')
    expect(screen.getByText(/12 Nutzungen/)).toBeInTheDocument()
    // Negativ-Zähler in der Meter-Zeile.
    expect(screen.getByText('2 negativ')).toBeInTheDocument()
  })

  it('zeigt einen Empty-State, wenn kein Feedback vorliegt', async () => {
    getFeedbackOverview.mockResolvedValue({ items: [] } satisfies FeedbackOverview)
    renderPage()

    await waitFor(() =>
      expect(screen.getByText('Noch kein Feedback in diesem Workspace.')).toBeInTheDocument(),
    )
  })
})
