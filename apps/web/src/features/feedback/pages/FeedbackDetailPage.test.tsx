import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FeedbackSummary } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { FeedbackDetailPage } from './FeedbackDetailPage'

const { getFeedback, getFeedbackEvents, setFeedbackResolution, deleteFeedback } = vi.hoisted(
  () => ({
    getFeedback: vi.fn(),
    getFeedbackEvents: vi.fn(),
    setFeedbackResolution: vi.fn(),
    deleteFeedback: vi.fn(),
  }),
)

// Stabile API-Referenz (wie der echte `useMemo`-basierte `useApi`) — sonst
// feuert der `useEffect(load,[load])` des Hooks in einer Schleife.
vi.mock('@/api/useApi', () => {
  const api = { getFeedback, getFeedbackEvents, setFeedbackResolution, deleteFeedback }
  return { useApi: () => api }
})

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const summary: FeedbackSummary = {
  entity_type: 'playbook',
  entity_id: 'pb1',
  usage_count: 12,
  by_outcome: { applied: 8, skipped: 3, error: 1 },
  by_signal: { helpful: 4, outdated: 2, incorrect: 1, unclear: 0 },
  recent_notes: [],
  recent_feedback: [],
}

function renderPage() {
  return renderInRoutes(<FeedbackDetailPage />, {
    path: '/w/:workspaceId/feedback/:entityType/:entityId',
    initialEntries: ['/w/ws-1/feedback/playbook/pb1'],
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  getFeedback.mockResolvedValue(summary)
  getFeedbackEvents.mockResolvedValue({ feedback: [] })
})

describe('FeedbackDetailPage', () => {
  it('zeigt Nutzung, Erfolgsquote und die Signal-Verteilung', async () => {
    renderPage()

    expect(await screen.findByText('12')).toBeInTheDocument()
    // 8 von 12 angewendet → 67 %.
    expect(screen.getByText('67%')).toBeInTheDocument()
    expect(screen.getByText('7 gesamt')).toBeInTheDocument()
  })

  // §4.4 Checklistenpunkt 1 (#565): `justify-between` ohne `flex-wrap` zwingt
  // Label und Wert auf eine Zeile. In der `md:grid-cols-2`-Spalte bleibt auf
  // 320px zu wenig Breite. Weiche 3: umbrechen lassen, keine zweite,
  // breakpoint-abhaengige Render-Variante (Repo-Muster `PageHeader`).
  it('laesst die Erfolgsquoten-Zeile umbrechen', async () => {
    renderPage()
    const label = await screen.findByText('Erfolgsquote')
    expect(label.parentElement).toHaveClass('flex-wrap')
  })

  it('laesst die Kartenkoepfe mit Zweitinhalt umbrechen', async () => {
    renderPage()

    // „Signale" + Gesamtzahl im selben CardHeader.
    const signalsHeader = (await screen.findByText('Signale')).parentElement!
    expect(signalsHeader).toHaveClass('flex-wrap')

    // „Einzel-Ereignisse" + Ausklapp-Button im selben CardHeader.
    const eventsHeader = screen.getByText('Einzel-Ereignisse').parentElement!
    expect(eventsHeader).toHaveClass('flex-wrap')
  })

  // Weiche 4 aus #565: die festen Label-Breiten der Meter-Zeilen werden nur
  // angefasst, wenn die Messung einen Ueberlauf zeigt. Auf 320px bleiben dem
  // Balken nach Label (96px) + 2x gap-3 (24px) + Zahl (32px) noch ~90px — kein
  // Ueberlauf, also bleibt das Prop unveraendert und `MeterRow`/`DataList`
  // unberuehrt. Der Test haelt fest, dass hier bewusst nichts geaendert wurde.
  it('laesst die Meter-Label-Breiten unveraendert (kein gemessener Ueberlauf)', async () => {
    renderPage()
    expect(await screen.findByText('Angewendet')).toHaveClass('w-24')
    expect(screen.getByText('Hilfreich')).toHaveClass('w-20')
  })
})
