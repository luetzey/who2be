import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Agent, CaseRead, FeedbackDetail } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { FeedbackItemDetailPage } from './FeedbackItemDetailPage'

const { getFeedbackDetail, setFeedbackResolution, deleteFeedback, listAgents, promoteFeedback } =
  vi.hoisted(() => ({
    getFeedbackDetail: vi.fn(),
    setFeedbackResolution: vi.fn(),
    deleteFeedback: vi.fn(),
    listAgents: vi.fn(),
    promoteFeedback: vi.fn(),
  }))

vi.mock('@/api/useApi', () => {
  const api = { getFeedbackDetail, setFeedbackResolution, deleteFeedback, listAgents, promoteFeedback }
  return { useApi: () => api }
})

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

let role: string | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
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

  // §4.4 Checklistenpunkt 1 (#565): `justify-between` erzwingt Label und Wert
  // auf einer Zeile. Auf 320px bleibt der „Bezug"-Liste nach Page-Padding und
  // Card-Padding kaum Breite — lange Element-Namen und der ausgeschriebene
  // Zeitstempel laufen sonst ineinander. Weiche 3: umbrechen lassen.
  it('laesst die Bezug-Zeilen umbrechen, statt Label und Wert auf eine Zeile zu zwingen', async () => {
    renderPage()
    const elementLink = await screen.findByRole('link', { name: 'Onboarding' })

    // Die `DefRow` um den Element-Link: `<dd>` → `<div>`.
    const defRow = elementLink.closest('dd')!.parentElement!
    expect(defRow).toHaveClass('flex-wrap')
    // Der Wert bleibt schrumpffaehig (Punkt 5) — das war schon erfuellt.
    expect(elementLink.closest('dd')).toHaveClass('min-w-0')
  })

  it('laesst die Signal-Zeile umbrechen', async () => {
    renderPage()
    await screen.findByRole('link', { name: 'Onboarding' })

    // Label „Signal" + Badge in der Karte „Signal & Notiz".
    const signalRow = screen.getByText('Signal', { selector: 'span' }).parentElement!
    expect(signalRow).toHaveClass('flex-wrap')
  })
})

// D6f (Delta-Spec „Alt-Feedback-Anschluss“, ADR-0053 5.2/6.5): „In Fall
// übernehmen“ ab editor, nur fuer offenes Feedback, nie fuer System-Meldungen.
describe('FeedbackItemDetailPage – In Fall übernehmen (D6f)', () => {
  const open: FeedbackDetail = { ...detail, resolution: null, history: [] }
  const created = { id: 'case-9', agent_id: 'a1', status: 'open' } as unknown as CaseRead
  const agents = [
    { id: 'a1', name: 'coder' },
    { id: 'a2', name: 'reviewer' },
  ] as unknown as Agent[]
  const PROMOTE = 'In Fall übernehmen'

  beforeEach(() => {
    role = 'editor'
    getFeedbackDetail.mockResolvedValue(open)
    listAgents.mockResolvedValue(agents)
    promoteFeedback.mockResolvedValue(created)
  })

  async function loaded() {
    renderPage()
    await screen.findByRole('link', { name: 'Onboarding' })
  }

  it.each([
    ['editor', true],
    ['admin', true],
    ['viewer', false],
    [null, false],
  ])('Rolle %s: Aktion sichtbar = %s', async (who, visible) => {
    role = who
    await loaded()
    expect(screen.queryByRole('button', { name: PROMOTE }) !== null).toBe(visible)
    expect(
      screen.queryByText(/Daraus wird ein Fall, dieses Feedback gilt dann als umgesetzt\./) !== null,
    ).toBe(visible)
  })

  it.each(['addressed', 'dismissed', 'in_progress'] as const)(
    'kein Knopf bei Status %s (der Server nimmt nur offenes Feedback)',
    async (resolution) => {
      getFeedbackDetail.mockResolvedValue({ ...open, resolution })
      await loaded()
      expect(screen.queryByRole('button', { name: PROMOTE })).toBeNull()
    },
  )

  it('kein Knopf bei einer System-Meldung (report_problem bleibt)', async () => {
    getFeedbackDetail.mockResolvedValue({
      ...open,
      entity_type: 'system',
      entity_id: null,
      signal: 'bug',
      name: 'System',
    })
    renderPage()
    await screen.findByText('Kein Element (System-Feedback)')
    expect(screen.queryByRole('button', { name: PROMOTE })).toBeNull()
  })

  it('Formular mit Zitat der Notiz und dem Agenten des Feedbacks als Vorschlag', async () => {
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: PROMOTE }))
    const dialog = await screen.findByTestId('report-case-dialog')

    const origin = within(dialog).getByTestId('report-case-origin')
    expect(within(origin).getByText('Schritt 4 ist veraltet')).toBeInTheDocument()
    expect(origin.querySelector('cite')?.textContent).toMatch(/^Altes Feedback zu Onboarding vom /)
    const select = await within(dialog).findByRole('combobox', { name: /^Agent/ })
    await waitFor(() => expect(select).toHaveValue('a1'))
    expect(within(dialog).getByRole('button', { name: 'Fall anlegen' })).toBeInTheDocument()
  })

  it('Erfolg: promote mit den Fall-Feldern, danach „Umgesetzt“ mit Server-Notiz und „Zum Fall“', async () => {
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: PROMOTE }))
    const dialog = await screen.findByTestId('report-case-dialog')
    const select = await within(dialog).findByRole('combobox', { name: /^Agent/ })
    await waitFor(() => expect(select).toHaveValue('a1'))
    fireEvent.change(within(dialog).getByLabelText(/Was war die Lage\?/), {
      target: { value: 'Onboarding lief' },
    })
    fireEvent.change(within(dialog).getByLabelText(/Was hat der Agent getan\?/), {
      target: { value: 'Schritt 4 alt befolgt' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'In „Erwartet“ übernehmen' }))

    // Nach dem Anlegen liefert der Server das Feedback als `addressed` mit Verweis.
    getFeedbackDetail.mockResolvedValue({
      ...open,
      resolution: 'addressed',
      history: [
        { resolution: 'addressed', actor_id: 'u1', note: 'case:case-9', created_at: '2026-10-09T08:00:00Z' },
      ],
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Fall anlegen' }))

    await waitFor(() =>
      expect(promoteFeedback).toHaveBeenCalledWith('fb1', {
        agent_id: 'a1',
        situation: 'Onboarding lief',
        behavior: 'Schritt 4 alt befolgt',
        expected_behavior: 'Schritt 4 ist veraltet',
        impact: undefined,
        severity: 'medium',
        signal: undefined,
        source_ref: undefined,
      }),
    )
    const toCase = await screen.findByTestId('item-to-case')
    expect(toCase).toHaveAttribute('href', '/w/ws-1/feedback/cases/case-9')
    expect(toCase).toHaveTextContent('Zum Fall')
    await waitFor(() => expect(toCase).toHaveFocus())
    expect(await screen.findByText('case:case-9')).toBeInTheDocument()
    expect(screen.getAllByText('Erledigt').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: PROMOTE })).toBeNull()
    expect(screen.queryByTestId('report-case-dialog')).toBeNull()
  })

  it('Fehler: 409 feedback_not_promotable bleibt im Formular sichtbar, kein „Zum Fall“', async () => {
    promoteFeedback.mockRejectedValue(
      new ApiError(409, 'Nur ein offenes Feedback (noch nicht triagiert) wird ein Fall.', {
        reason: 'feedback_not_promotable',
      }),
    )
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: PROMOTE }))
    const dialog = await screen.findByTestId('report-case-dialog')
    const select = await within(dialog).findByRole('combobox', { name: /^Agent/ })
    await waitFor(() => expect(select).toHaveValue('a1'))
    fireEvent.change(within(dialog).getByLabelText(/Was war die Lage\?/), { target: { value: 'L' } })
    fireEvent.change(within(dialog).getByLabelText(/Was hat der Agent getan\?/), {
      target: { value: 'G' },
    })
    fireEvent.change(within(dialog).getByLabelText(/Was hättest du erwartet\?/), {
      target: { value: 'E' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Fall anlegen' }))

    expect(
      await within(dialog).findByText('Nur ein offenes Feedback (noch nicht triagiert) wird ein Fall.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByLabelText(/Was war die Lage\?/)).toHaveValue('L')
    expect(screen.queryByTestId('item-to-case')).toBeNull()
  })

  it('a11y: keine axe-Violations auf der Detailseite mit Aktion', async () => {
    await loaded()
    await screen.findByRole('button', { name: PROMOTE })
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: keine axe-Violations im offenen Formular mit Zitat', async () => {
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: PROMOTE }))
    const dialog = await screen.findByTestId('report-case-dialog')
    await within(dialog).findByRole('combobox', { name: /^Agent/ })
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)
})
