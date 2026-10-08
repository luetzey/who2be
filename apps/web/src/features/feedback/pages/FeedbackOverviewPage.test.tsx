import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FeedbackOverview, WorkspaceRole } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { FeedbackOverviewPage } from './FeedbackOverviewPage'

const {
  getFeedbackOverview,
  getFeedbackItems,
  listCases,
  countCases,
  listAgents,
  createCase,
} = vi.hoisted(() => ({
  getFeedbackOverview: vi.fn(),
  getFeedbackItems: vi.fn(),
  listCases: vi.fn(),
  countCases: vi.fn(),
  listAgents: vi.fn(),
  createCase: vi.fn(),
}))

// Stabile API-Referenz (wie der echte `useMemo`-basierte `useApi`) — sonst
// feuert der `useEffect(load,[load])` des Hooks in einer Schleife.
vi.mock('@/api/useApi', () => {
  const api = {
    getFeedbackOverview,
    getFeedbackItems,
    listCases,
    countCases,
    listAgents,
    createCase,
  }
  return { useApi: () => api }
})

let role: WorkspaceRole | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const EMPTY_ITEMS = {
  items: [],
  counts: { open: 0, in_progress: 0, addressed: 0, dismissed: 0 },
}

const OVERVIEW: FeedbackOverview = {
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

beforeEach(() => {
  role = 'editor'
  getFeedbackOverview.mockReset()
  getFeedbackItems.mockReset()
  listCases.mockReset()
  countCases.mockReset()
  listAgents.mockReset()
  // Bausteine (FeedbackInbox) und Faelle laden eigenstaendig; leer reicht hier.
  getFeedbackItems.mockResolvedValue(EMPTY_ITEMS)
  getFeedbackOverview.mockResolvedValue(OVERVIEW)
  listCases.mockResolvedValue({ items: [], next_cursor: null })
  countCases.mockResolvedValue({
    open: 0,
    reopened: 0,
    triaged: 0,
    in_progress: 0,
    addressed: 0,
    verified: 0,
    dismissed: 0,
  })
  listAgents.mockResolvedValue([])
})

function SearchProbe() {
  return <output data-testid="search">{useLocation().search}</output>
}

const currentSearch = () => screen.getByTestId('search').textContent

function renderPage(search = '') {
  return renderInRoutes(
    <>
      <FeedbackOverviewPage />
      <SearchProbe />
    </>,
    { path: '/w/:workspaceId/feedback', initialEntries: [`/w/ws-1/feedback${search}`] },
  )
}

describe('FeedbackOverviewPage — Hub-Tabs', () => {
  it('oeffnet standardmaessig „Fälle“ mit drei Tabs fuer editor', async () => {
    renderPage()

    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['Fälle', 'Bausteine', 'Kuration'])
    expect(screen.getByRole('tab', { name: /Fälle/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tablist', { name: 'Bereiche des Feedbacks' })).toBeInTheDocument()
    expect(await screen.findByText('Keine offenen Fälle')).toBeInTheDocument()
    // Kuration laedt erst, wenn der Tab offen ist.
    expect(getFeedbackOverview).not.toHaveBeenCalled()
  })

  it('schreibt den Tab in die URL und verwirft dabei Filter des alten Tabs', async () => {
    renderPage('?tab=cases&status=triaged')
    await waitFor(() => expect(listCases).toHaveBeenCalled())

    fireEvent.mouseDown(screen.getByRole('tab', { name: /Bausteine/ }))
    fireEvent.click(screen.getByRole('tab', { name: /Bausteine/ }))
    await waitFor(() => expect(currentSearch()).toBe('?tab=signals'))
    expect(screen.getByRole('tab', { name: /Bausteine/ })).toHaveAttribute('aria-selected', 'true')
    expect(getFeedbackItems).toHaveBeenCalled()
  })

  it('oeffnet einen Deep-Link auf „Kuration“ direkt', async () => {
    renderPage('?tab=curation')
    expect(await screen.findByRole('link', { name: 'Onboarding' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Kuration/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('korrigiert einen unbekannten Tab still auf „Fälle“', async () => {
    renderPage('?tab=quatsch')
    await waitFor(() => expect(currentSearch()).toBe('?tab=cases'))
    expect(screen.getByRole('tab', { name: /Fälle/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('zeigt viewer nur „Meine Fälle“ ohne Tab-Leiste und ohne Kuration', async () => {
    role = 'viewer'
    renderPage('?tab=curation')

    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Meine Fälle' })).toBeInTheDocument()
    expect(await screen.findByText('Du hast noch keinen Fall gemeldet')).toBeInTheDocument()
    await waitFor(() => expect(currentSearch()).toBe('?tab=cases'))
    expect(getFeedbackOverview).not.toHaveBeenCalled()
    expect(getFeedbackItems).not.toHaveBeenCalled()
  })

  it('bietet „Fall melden“ und „Problem melden“ im Seitenkopf', () => {
    renderPage()
    expect(screen.getAllByRole('button', { name: 'Fall melden' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /Problem melden/ })).toBeInTheDocument()
  })

  // D6b-Review Nit d (Seitenkopf): solange die Rolle laedt, weder „Meine
  // Fälle“ noch die viewer-Beschreibung zeigen und keine Faelle abrufen.
  it('zeigt waehrend die Rolle laedt nur Kopf und Platzhalter, ohne viewer-Variante', () => {
    role = null
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Feedback' })).toBeInTheDocument()
    expect(screen.getByTestId('feedback-hub-loading')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Meine Fälle' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(listCases).not.toHaveBeenCalled()
  })

  // D6b-Review Nit b: nach „Fall melden“ im Dialog laedt die Fall-Liste neu.
  it('laedt die Fall-Liste nach erfolgreichem „Fall melden“ neu, Filter bleiben', async () => {
    listAgents.mockResolvedValue([{ id: 'a1', name: 'coder' }])
    createCase.mockResolvedValue({ id: 'case-9' })
    renderPage('?tab=cases&status=all')
    await waitFor(() => expect(listCases).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getAllByRole('button', { name: 'Fall melden' })[0])
    const dialog = await screen.findByTestId('report-case-dialog')
    fireEvent.change(await within(dialog).findByRole('combobox', { name: /Agent/ }), {
      target: { value: 'a1' },
    })
    fireEvent.change(within(dialog).getByLabelText(/Was war die Lage\?/), {
      target: { value: 'Lage' },
    })
    fireEvent.change(within(dialog).getByLabelText(/Was hat der Agent getan\?/), {
      target: { value: 'Getan' },
    })
    fireEvent.change(within(dialog).getByLabelText(/Was hättest du erwartet\?/), {
      target: { value: 'Erwartet' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Fall melden' }))

    await waitFor(() => expect(createCase).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(listCases).toHaveBeenCalledTimes(2))
    expect(listCases.mock.calls[1][0]).toEqual(listCases.mock.calls[0][0])
    expect(currentSearch()).toBe('?tab=cases&status=all')
  })
})

describe('FeedbackOverviewPage — Kuration', () => {
  it('listet Elemente mit Kennzahlen und verlinkt auf die Detailseite', async () => {
    renderPage('?tab=curation')

    const link = await screen.findByRole('link', { name: 'Onboarding' })
    expect(link).toHaveAttribute('href', '/w/ws-1/feedback/playbook/pb1')
    expect(screen.getByText(/12 Nutzungen/)).toBeInTheDocument()
    // Negativ-Zähler in der Meter-Zeile.
    expect(screen.getByText('2 negativ')).toBeInTheDocument()
  })

  it('zeigt einen Empty-State, wenn kein Feedback vorliegt', async () => {
    getFeedbackOverview.mockResolvedValue({ items: [] } satisfies FeedbackOverview)
    renderPage('?tab=curation')

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
    renderPage('?tab=curation')

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
