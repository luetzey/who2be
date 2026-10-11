import { fireEvent, screen, within } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FeedbackItems } from '@/api/types'
import { axe } from '@/test/a11y'
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

// Zeigt die aktuelle Query, damit die Tests die URL-Pflege pruefen koennen.
function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.search}</output>
}

function renderInbox(entry = '/w/ws-1/feedback?tab=signals') {
  return renderInRoutes(
    <>
      <FeedbackInbox />
      <LocationProbe />
    </>,
    { path: '/w/:workspaceId/feedback', initialEntries: [entry] },
  )
}

function statusGroup() {
  return screen.getByRole('group', { name: 'Nach Status filtern' })
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
    expect(within(statusGroup()).getByRole('button', { name: 'Offen 1' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    // Keine Inline-Triage/Notiz mehr im Posteingang — die liegen im Detail.
    expect(screen.queryByText('Schritt 4 ist veraltet')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Erledigt — Onboarding/ })).not.toBeInTheDocument()
  })

  it('blendet Status-Chips mit 0 aus, außer „Alle“ und den Standard „Offen“', async () => {
    getFeedbackItems.mockResolvedValue({
      items: [data.items[1]],
      counts: { open: 0, in_progress: 0, addressed: 1, dismissed: 0 },
    })
    renderInbox()

    const group = await screen.findByRole('group', { name: 'Nach Status filtern' })
    expect(within(group).getByRole('button', { name: 'Alle 1' })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: 'Offen 0' })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: 'Erledigt 1' })).toBeInTheDocument()
    expect(within(group).queryByRole('button', { name: /In Arbeit/ })).not.toBeInTheDocument()
    expect(within(group).queryByRole('button', { name: /Ignoriert/ })).not.toBeInTheDocument()
    // Standard „Offen“ ohne Treffer: „Alles erledigt“, kein Zuruecksetzen.
    expect(screen.getByText('Kein offenes Feedback')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Filter zurücksetzen' })).not.toBeInTheDocument()
  })

  it('schreibt den Status per replace in die URL und lässt „tab“ stehen', async () => {
    renderInbox()
    await screen.findByRole('link', { name: 'Onboarding' })

    fireEvent.click(within(statusGroup()).getByRole('button', { name: 'Alle 2' }))
    expect(await screen.findByRole('link', { name: 'API-Doku' })).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('?tab=signals&status=all')

    // Zurück auf den Standard: der Parameter verschwindet.
    fireEvent.click(within(statusGroup()).getByRole('button', { name: 'Offen 1' }))
    expect(screen.getByTestId('location')).toHaveTextContent(/^\?tab=signals$/)
  })

  it('liest Filter aus der URL und zeigt Chips je Facette', async () => {
    renderInbox('/w/ws-1/feedback?tab=signals&status=all&signal=helpful')

    expect(await screen.findByRole('link', { name: 'API-Doku' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Onboarding' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Signal')).toHaveValue('helpful')
    const chips = screen.getByRole('list', { name: 'Aktive Filter' })
    expect(within(chips).getByRole('button', { name: /Signal: Hilfreich/ })).toBeInTheDocument()
  })

  it('filtert per Suche und Typ; die Chip-Zahlen folgen der Auswahl', async () => {
    renderInbox('/w/ws-1/feedback?tab=signals&status=all')
    await screen.findByRole('link', { name: 'Onboarding' })

    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'api' } })
    expect(screen.queryByRole('link', { name: 'Onboarding' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'API-Doku' })).toBeInTheDocument()
    expect(within(statusGroup()).getByRole('button', { name: 'Alle 1' })).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('q=api')

    fireEvent.change(screen.getByLabelText('Typ'), { target: { value: 'playbook' } })
    expect(screen.getByTestId('location')).toHaveTextContent('type=playbook')
    // Suche „api“ + Typ Playbook → keine Treffer, Standard-Leerzustand gefiltert.
    expect(screen.getByText('Keine Treffer')).toBeInTheDocument()
  })

  it('setzt im gefilterten Leerzustand alle Filter zurück', async () => {
    renderInbox('/w/ws-1/feedback?tab=signals&type=system')

    expect(await screen.findByText('Keine Treffer')).toBeInTheDocument()
    const resets = screen.getAllByRole('button', { name: 'Filter zurücksetzen' })
    // Leiste (ghost) und Leerzustand (outline).
    expect(resets).toHaveLength(2)
    fireEvent.click(resets[1])

    expect(await screen.findByRole('link', { name: 'Onboarding' })).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent(/^\?tab=signals$/)
  })

  it('zeigt ohne jedes Feedback den Seiten-Leerzustand ohne Filterleiste', async () => {
    getFeedbackItems.mockResolvedValue({
      items: [],
      counts: { open: 0, in_progress: 0, addressed: 0, dismissed: 0 },
    })
    renderInbox()

    expect(await screen.findByText('Noch kein Feedback in diesem Workspace.')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Nach Status filtern' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Suche')).not.toBeInTheDocument()
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

  it('a11y: keine axe-Violations mit Daten und aktivem Filter', async () => {
    const { container } = renderInbox('/w/ws-1/feedback?tab=signals&status=all&signal=helpful')
    await screen.findByRole('link', { name: 'API-Doku' })
    expect(await axe(container)).toHaveNoViolations()
  })
})
