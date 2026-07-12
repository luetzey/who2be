import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FeedbackDetail } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { FeedbackItemDetailPage } from './FeedbackItemDetailPage'

const { getFeedbackDetail, setFeedbackResolution, deleteFeedback } = vi.hoisted(() => ({
  getFeedbackDetail: vi.fn(),
  setFeedbackResolution: vi.fn(),
  deleteFeedback: vi.fn(),
}))

vi.mock('@/api/useApi', () => {
  const api = { getFeedbackDetail, setFeedbackResolution, deleteFeedback }
  return { useApi: () => api }
})

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const detail: FeedbackDetail = {
  id: 'fb1',
  entity_type: 'playbook',
  entity_id: 'pb1',
  name: 'Onboarding',
  version: 2,
  signal: 'outdated',
  note: 'Schritt 4 ist veraltet',
  agent_id: 'a1',
  actor_id: null,
  created_at: '2026-06-20T10:00:00Z',
  resolution: 'in_progress',
  history: [
    {
      resolution: 'in_progress',
      actor_id: 'u1',
      note: 'Ich kümmere mich darum',
      created_at: '2026-06-21T09:00:00Z',
    },
    {
      resolution: 'addressed',
      actor_id: 'u1',
      note: null,
      created_at: '2026-06-22T09:00:00Z',
    },
  ],
}

function renderPage() {
  return renderInRoutes(<FeedbackItemDetailPage />, {
    path: '/w/:workspaceId/feedback/item/:feedbackId',
    initialEntries: ['/w/ws-1/feedback/item/fb1'],
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  getFeedbackDetail.mockResolvedValue(detail)
  setFeedbackResolution.mockResolvedValue({ ...detail, resolution: 'addressed' })
  deleteFeedback.mockResolvedValue(undefined)
})

describe('FeedbackItemDetailPage', () => {
  it('lädt das Feedback und zeigt Bezug, Signal und Verlauf', async () => {
    renderPage()

    // Bezug: Element-Link auf das Element (nicht die Feedback-Detailseite).
    const elementLink = await screen.findByRole('link', { name: 'Onboarding' })
    expect(elementLink).toHaveAttribute('href', '/w/ws-1/playbooks/pb1')
    // Version + Quelle (Agent, weil agent_id gesetzt).
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('Agent')).toBeInTheDocument()

    // Signal & Notiz: übersetztes Signal + Absender-Notiz.
    expect(screen.getAllByText('Veraltet').length).toBeGreaterThan(0)
    expect(screen.getByText('Schritt 4 ist veraltet')).toBeInTheDocument()

    // Verlauf: beide Triage-Ereignisse (Notiz des ersten sichtbar).
    expect(screen.getByText('Ich kümmere mich darum')).toBeInTheDocument()
    expect(screen.getByText('Verlauf')).toBeInTheDocument()
  })

  it('setzt den Status über die Triage-Segmente und lädt das Detail neu', async () => {
    renderPage()
    await screen.findByRole('link', { name: 'Onboarding' })
    const before = getFeedbackDetail.mock.calls.length

    fireEvent.click(screen.getByRole('button', { name: 'Erledigt — Onboarding' }))

    await waitFor(() =>
      expect(setFeedbackResolution).toHaveBeenCalledWith('fb1', { resolution: 'addressed' }),
    )
    // Refetch nach der Triage, damit der Verlauf das neue Ereignis spiegelt.
    await waitFor(() =>
      expect(getFeedbackDetail.mock.calls.length).toBeGreaterThan(before),
    )
  })

  it('zeigt den leeren Verlauf-Hinweis, wenn noch nicht triagiert wurde', async () => {
    getFeedbackDetail.mockResolvedValue({ ...detail, resolution: null, history: [] })
    renderPage()

    expect(await screen.findByText('Noch nicht bearbeitet.')).toBeInTheDocument()
  })
})
