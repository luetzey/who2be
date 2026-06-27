import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { FeedbackEvents, FeedbackSummary } from '@/api/types'

import { FeedbackPanel } from './FeedbackPanel'

const { getFeedback, getFeedbackEvents } = vi.hoisted(() => ({
  getFeedback: vi.fn(),
  getFeedbackEvents: vi.fn(),
}))

// Stabile API-Referenz (wie der echte `useMemo`-basierte `useApi`) — sonst
// wechselt die Identitaet pro Render und der `useEffect(load,[load])` der Hooks
// feuert in einer Schleife.
vi.mock('@/api/useApi', () => {
  const api = { getFeedback, getFeedbackEvents }
  return { useApi: () => api }
})

const summary: FeedbackSummary = {
  entity_type: 'playbook',
  entity_id: 'pb1',
  usage_count: 5,
  by_outcome: { applied: 3, skipped: 1, error: 1 },
  by_signal: { helpful: 2, outdated: 1 },
  recent_notes: ['Schritt 4 ist veraltet'],
}

const events: FeedbackEvents = {
  entity_type: 'playbook',
  entity_id: 'pb1',
  feedback: [
    {
      id: 'f1',
      entity_type: 'playbook',
      entity_id: 'pb1',
      version: 2,
      signal: 'outdated',
      note: 'bitte aktualisieren',
      agent_id: 'a1',
      created_at: '2026-06-20T10:00:00Z',
    },
  ],
  usage: [],
}

describe('FeedbackPanel', () => {
  it('zeigt Nutzungszahl, Signale und letzte Notizen', async () => {
    getFeedback.mockResolvedValue(summary)
    render(<FeedbackPanel type="playbook" id="pb1" />)

    await waitFor(() => expect(screen.getByText('5')).toBeInTheDocument())
    // Signal-Labels (deutsche i18n) + Notiz.
    expect(screen.getByText('Hilfreich')).toBeInTheDocument()
    expect(screen.getByText('Veraltet')).toBeInTheDocument()
    expect(screen.getByText('Schritt 4 ist veraltet')).toBeInTheDocument()
  })

  it('bietet „Überarbeiten" nur bei negativen Signalen + Handler', async () => {
    getFeedback.mockResolvedValue(summary)
    const onRevise = vi.fn()
    render(<FeedbackPanel type="playbook" id="pb1" onRevise={onRevise} />)

    const button = await screen.findByRole('button', { name: 'Überarbeiten' })
    fireEvent.click(button)
    expect(onRevise).toHaveBeenCalledTimes(1)
  })

  it('lädt Einzel-Ereignisse erst beim Aufklappen (lazy)', async () => {
    getFeedback.mockResolvedValue(summary)
    getFeedbackEvents.mockResolvedValue(events)
    render(<FeedbackPanel type="playbook" id="pb1" />)

    await waitFor(() => expect(screen.getByText('5')).toBeInTheDocument())
    expect(getFeedbackEvents).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Einzelne Ereignisse anzeigen' }))
    await waitFor(() => expect(getFeedbackEvents).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('bitte aktualisieren')).toBeInTheDocument()
  })

  it('zeigt einen Empty-State ohne Feedback', async () => {
    getFeedback.mockResolvedValue({
      entity_type: 'playbook',
      entity_id: 'pb1',
      usage_count: 0,
      by_outcome: {},
      by_signal: {},
      recent_notes: [],
    } satisfies FeedbackSummary)
    render(<FeedbackPanel type="playbook" id="pb1" />)

    await waitFor(() =>
      expect(
        screen.getByText(/Noch kein Feedback. Agenten melden Nutzung/),
      ).toBeInTheDocument(),
    )
  })
})
