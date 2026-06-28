import { fireEvent, screen, waitFor } from '@testing-library/react'
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
  setFeedbackResolution.mockResolvedValue({ ...data.items[0], resolution: 'addressed' })
  deleteFeedback.mockResolvedValue(undefined)
})

describe('FeedbackInbox', () => {
  it('zeigt die KPI-Zähler und standardmäßig nur offene Feedbacks', async () => {
    renderInbox()

    // Default-Filter „Offen" → nur das untriagierte Feedback ist sichtbar.
    expect(await screen.findByRole('link', { name: 'Onboarding' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'API-Doku' })).not.toBeInTheDocument()
    // KPI-Karte „Offen" als eigene Button-Kachel (Zaehler + Label).
    expect(screen.getByRole('button', { name: /Offen/ })).toBeInTheDocument()
  })

  it('blendet erledigte Feedbacks ein, wenn der Status-Filter „Alle" ist', async () => {
    renderInbox()
    await screen.findByRole('link', { name: 'Onboarding' })

    const statusSelect = screen.getByLabelText('Status')
    fireEvent.change(statusSelect, { target: { value: 'all' } })
    expect(await screen.findByRole('link', { name: 'API-Doku' })).toBeInTheDocument()
  })

  it('triagiert ein Feedback inline und lädt die Liste neu', async () => {
    renderInbox()
    await screen.findByRole('link', { name: 'Onboarding' })
    const before = getFeedbackItems.mock.calls.length

    const triage = screen.getByLabelText(/Triage — Onboarding/)
    fireEvent.change(triage, { target: { value: 'addressed' } })
    await waitFor(() =>
      expect(setFeedbackResolution).toHaveBeenCalledWith('fb-open', { resolution: 'addressed' }),
    )
    // Reload nach der Triage (mindestens ein weiterer Items-Fetch).
    await waitFor(() =>
      expect(getFeedbackItems.mock.calls.length).toBeGreaterThan(before),
    )
  })

  it('löscht ein Feedback nach Bestätigung und lädt die Liste neu', async () => {
    renderInbox()
    await screen.findByRole('link', { name: 'Onboarding' })
    const before = getFeedbackItems.mock.calls.length

    // Öffnet den Bestätigungs-Dialog und bestätigt den Hard-Delete.
    fireEvent.click(screen.getByRole('button', { name: 'Feedback löschen' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Endgültig löschen' }))

    await waitFor(() => expect(deleteFeedback).toHaveBeenCalledWith('fb-open'))
    // Reload nach dem Löschen (mindestens ein weiterer Items-Fetch).
    await waitFor(() => expect(getFeedbackItems.mock.calls.length).toBeGreaterThan(before))
  })

  it('zeigt System-Feedback mit Kategorie statt Element-Link', async () => {
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

    // Kategorie-Badge (statt Inhalts-Signal) + Beschreibung sichtbar.
    expect(await screen.findByText('MCP')).toBeInTheDocument()
    expect(screen.getByText('fetch_playbook liefert 500')).toBeInTheDocument()
    // Kein Detail-Link — System-Feedback hat kein Element.
    expect(screen.queryByRole('link', { name: 'System' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Element öffnen' })).not.toBeInTheDocument()
  })
})
