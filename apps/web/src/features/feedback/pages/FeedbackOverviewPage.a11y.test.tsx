import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { FeedbackOverview } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { FeedbackOverviewPage } from './FeedbackOverviewPage'

const {
  getFeedbackOverview,
  getFeedbackItems,
  listCases,
  countCases,
  listAgents,
  listPatterns,
  countMemories,
} = vi.hoisted(() => ({
  getFeedbackOverview: vi.fn(),
  getFeedbackItems: vi.fn(),
  listCases: vi.fn(),
  countCases: vi.fn(),
  listAgents: vi.fn(),
  listPatterns: vi.fn(),
  countMemories: vi.fn(),
}))

vi.mock('@/api/useApi', () => {
  const api = {
    getFeedbackOverview,
    getFeedbackItems,
    listCases,
    countCases,
    listAgents,
    listPatterns,
    countMemories,
  }
  return { useApi: () => api }
})

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

/**
 * Setzt die API-Mocks frisch und rendert die Seite auf dem angegebenen Tab.
 * Liefert den Container fuer den axe-Lauf.
 */
function renderTab(tab: 'cases' | 'patterns' | 'signals' | 'curation'): HTMLElement {
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
  listAgents.mockResolvedValue([{ id: 'a1', name: 'coder' }])
  countCases.mockResolvedValue({
    open: 1,
    reopened: 0,
    triaged: 0,
    in_progress: 0,
    addressed: 0,
    verified: 0,
    dismissed: 0,
  })
  listCases.mockResolvedValue({
    items: [
      {
        id: 'case-1',
        workspace_id: 'ws-1',
        agent_id: 'a1',
        reporter_kind: 'human',
        reporter_user_id: 'u1',
        reporter_agent_id: null,
        situation: 'Fix gepusht, CI rot.',
        behavior: 'Direkt gepusht.',
        impact: null,
        expected_behavior: 'Tests vorher lokal laufen lassen.',
        severity: 'high',
        signal: 'incorrect',
        source_ref: null,
        source_feedback_id: null,
        source_memory_id: null,
        status: 'open',
        created_at: '2026-10-08T10:00:00Z',
      },
    ],
    next_cursor: null,
  })
  countMemories.mockResolvedValue({ total: 1 })
  listPatterns.mockResolvedValue({
    threshold: 3,
    window_days: 30,
    patterns: [
      {
        source: 'lesson',
        agent_id: 'a1',
        element: null,
        count: 3,
        evidence_ids: ['m1'],
        first_seen: '2026-10-01T10:00:00Z',
        last_seen: '2026-10-05T10:00:00Z',
      },
    ],
  })

  const { container } = renderInRoutes(<FeedbackOverviewPage />, {
    path: '/w/:workspaceId/feedback',
    initialEntries: [`/w/ws-1/feedback?tab=${tab}`],
  })
  return container
}

// Jeder Tab braucht einen eigenen axe-Lauf — TabsContent rendert nur den
// aktiven Tab, ein einzelner Check saehe die anderen Panels nie.
//
// Bewusst ein Test pro Tab statt mehrerer Laeufe in einem (Muster aus #814):
// mehrere axe-Laeufe ueber die ganze Seite in EINEM Test rissen im
// Coverage-Lauf unter Last das 15-s-Timeout des a11y-Projekts (Review von
// PR #819). Getrennt hat jeder Tab sein eigenes Budget.
describe('FeedbackOverviewPage (a11y)', () => {
  it('hat keine axe-Violations mit Daten — Fälle', async () => {
    const container = renderTab('cases')
    await waitFor(() => expect(screen.getByRole('link', { name: 'coder' })).toBeInTheDocument())
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit Daten — Muster', async () => {
    const container = renderTab('patterns')
    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Dieselbe Korrektur 3×' })).toBeInTheDocument(),
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit Daten — Bausteine', async () => {
    const container = renderTab('signals')
    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Coach-Persona' })).toBeInTheDocument(),
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit Daten — Kuration', async () => {
    const container = renderTab('curation')
    await waitFor(() => expect(screen.getByRole('link', { name: 'Onboarding' })).toBeInTheDocument())
    expect(await axe(container)).toHaveNoViolations()
  })
})
