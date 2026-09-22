import { fireEvent, screen, waitFor } from '@testing-library/react'
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

    // Die Kurations-Aggregat-Liste liegt jetzt im „Kuration"-Tab.
    fireEvent.click(screen.getByRole('tab', { name: /Kuration/ }))
    const link = await screen.findByRole('link', { name: 'Onboarding' })
    expect(link).toHaveAttribute('href', '/w/ws-1/feedback/playbook/pb1')
    expect(screen.getByText(/12 Nutzungen/)).toBeInTheDocument()
    // Negativ-Zähler in der Meter-Zeile.
    expect(screen.getByText('2 negativ')).toBeInTheDocument()
  })

  it('zeigt einen Empty-State, wenn kein Feedback vorliegt', async () => {
    getFeedbackOverview.mockResolvedValue({ items: [] } satisfies FeedbackOverview)
    renderPage()

    fireEvent.click(screen.getByRole('tab', { name: /Kuration/ }))
    await waitFor(() =>
      expect(screen.getByText('Noch kein Feedback in diesem Workspace.')).toBeInTheDocument(),
    )
  })

  // §4.4 Checklistenpunkt 2/3 (#565): die Kurations-Zeile trug drei feste
  // Anteile nebeneinander — 208px (`w-52`) + 120px (`min-w-[7.5rem]`) + 96px
  // (`w-24`) plus Gaps. Das passt auf 320px rechnerisch nicht. Weiche 1:
  // unterhalb der Mobile-Schwelle `md` stapeln, die Breiten gelten nur
  // darueber. Weiche 2: `min-w-[7.5rem]` wird praefixiert, nicht entfernt.
  it('stapelt die Kurations-Zeile unterhalb md, statt drei feste Breiten zu erzwingen', async () => {
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

    fireEvent.click(screen.getByRole('tab', { name: /Kuration/ }))
    const link = await screen.findByRole('link', { name: 'Onboarding' })

    // Die Zeile selbst: Phone-Fall ist die Spalte, `md:` schaltet die Reihe an.
    const row = link.closest('div')!
    expect(row).toHaveClass('flex-col', 'md:flex-row')

    // Spalte 1 (Element): 208px erst ab `md`, kein nacktes `w-52`/`flex-none`.
    const nameColumn = link.parentElement!.parentElement!
    expect(nameColumn).toHaveClass('md:w-52', 'md:flex-none')
    expect(nameColumn.className).not.toMatch(/(^|\s)w-52(\s|$)/)
    expect(nameColumn.className).not.toMatch(/(^|\s)flex-none(\s|$)/)

    // Spalte 2 (Signal-Balken): die funktionale Mindestbreite bleibt, aber
    // nur oberhalb der Schwelle — im gestapelten Fall ist sie gegenstandslos.
    const meterColumn = screen.getByText('2 negativ').closest('span.flex.w-full')!
    expect(meterColumn).toHaveClass('md:min-w-[7.5rem]', 'md:flex-1')
    expect(meterColumn.className).not.toMatch(/(^|\s)min-w-\[7\.5rem\](\s|$)/)

    // Spalte 3 (Datum): rechtsbuendig erst ab `md`, sonst im Textfluss.
    const dateColumn = screen.getByText(new Date('2026-06-20T10:00:00Z').toLocaleDateString())
    expect(dateColumn).toHaveClass('md:w-24', 'md:flex-none', 'md:text-right')
    expect(dateColumn.className).not.toMatch(/(^|\s)w-24(\s|$)/)
  })
})
