import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FeedbackItems } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { FeedbackInbox } from './FeedbackInbox'

const { getFeedbackItems, setFeedbackResolution, deleteFeedback, submitSystemFeedback } =
  vi.hoisted(() => ({
    getFeedbackItems: vi.fn(),
    setFeedbackResolution: vi.fn(),
    deleteFeedback: vi.fn(),
    submitSystemFeedback: vi.fn(),
  }))

vi.mock('@/api/useApi', () => {
  const api = { getFeedbackItems, setFeedbackResolution, deleteFeedback, submitSystemFeedback }
  return { useApi: () => api }
})

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const data: FeedbackItems = {
  items: [
    {
      id: 'fb-open',
      entity_type: 'playbook',
      entity_id: 'pb1',
      name: 'Onboarding',
      version: 2,
      signal: 'outdated',
      note: 'Schritt 4 ist veraltet',
      agent_id: 'a1',
      created_at: '2026-06-20T10:00:00Z',
      resolution: null,
    },
    {
      id: 'fb-done',
      entity_type: 'resource',
      entity_id: 'r1',
      name: 'API-Doku',
      version: null,
      signal: 'helpful',
      note: null,
      agent_id: null,
      created_at: '2026-06-19T10:00:00Z',
      resolution: 'addressed',
    },
  ],
  counts: { open: 1, in_progress: 0, addressed: 1, dismissed: 0 },
}

function renderInbox() {
  return renderInRoutes(<FeedbackInbox />, {
    path: '/w/:workspaceId/feedback',
    initialEntries: ['/w/ws-1/feedback'],
  })
}

beforeEach(() => {
  getFeedbackItems.mockResolvedValue(data)
})

describe('FeedbackInbox', () => {
  it('zeigt Status-Chips und standardmäßig nur offene Feedbacks kompakt', async () => {
    renderInbox()

    // Default-Filter „Offen" → nur das untriagierte Feedback ist sichtbar.
    expect(await screen.findByRole('link', { name: 'Onboarding' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'API-Doku' })).not.toBeInTheDocument()
    // Status-Filter-Chip „Offen" mit Zaehler (Button, nicht das Zeilen-Status-Pill).
    expect(screen.getByRole('button', { name: /Offen/ })).toBeInTheDocument()
    // Keine Inline-Triage/Notiz mehr im Posteingang — die liegen im Detail.
    expect(screen.queryByText('Schritt 4 ist veraltet')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Erledigt — Onboarding/ })).not.toBeInTheDocument()
  })

  it('blendet erledigte Feedbacks ein, wenn der Status-Filter „Alle" ist', async () => {
    renderInbox()
    await screen.findByRole('link', { name: 'Onboarding' })

    fireEvent.click(screen.getByRole('button', { name: /Alle/ }))
    expect(await screen.findByRole('link', { name: 'API-Doku' })).toBeInTheDocument()
  })

  it('verlinkt jede Karte auf die Einzel-Feedback-Detailseite', async () => {
    renderInbox()
    const titleLink = await screen.findByRole('link', { name: 'Onboarding' })
    expect(titleLink).toHaveAttribute('href', '/w/ws-1/feedback/item/fb-open')
  })

  it('zeigt System-Feedback mit Kategorie und Detail-Link (kein Element-Link)', async () => {
    getFeedbackItems.mockResolvedValue({
      items: [
        {
          id: 'sys1',
          entity_type: 'system',
          entity_id: null,
          name: 'System',
          version: null,
          signal: 'mcp',
          note: 'fetch_playbook liefert 500',
          agent_id: null,
          created_at: '2026-06-28T10:00:00Z',
          resolution: null,
        },
      ],
      counts: { open: 1, in_progress: 0, addressed: 0, dismissed: 0 },
    })
    renderInbox()

    // Kategorie-Badge (statt Inhalts-Signal) sichtbar; der Titel verlinkt auf die
    // Einzel-Feedback-Detailseite (auch System-Feedback hat eine id).
    expect(await screen.findByText('MCP')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'System' })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback/item/sys1',
    )
    // Keine „Element öffnen"-Aktion mehr im Posteingang.
    expect(screen.queryByRole('link', { name: 'Element öffnen' })).not.toBeInTheDocument()
    // Die Notiz erscheint erst in der Detailansicht, nicht im Posteingang.
    expect(screen.queryByText('fetch_playbook liefert 500')).not.toBeInTheDocument()
  })
})
