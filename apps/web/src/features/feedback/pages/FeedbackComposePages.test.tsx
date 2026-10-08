import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SessionContext } from '@/auth/session-context'
import { ReportCaseDialog } from '@/components/cases/ReportCaseForm'
import { GiveFeedbackDialog } from '@/components/feedback/GiveFeedbackDialog'
import { toast } from '@/components/ui/sonner'
import { axe } from '@/test/a11y'

import { CaseList } from '../components/CaseList'
import { ReportProblemDialog } from '../components/ReportProblemDialog'
import { GiveFeedbackPage, ReportCasePage, ReportProblemPage } from './FeedbackComposePages'

const {
  submitFeedback,
  submitSystemFeedback,
  createCase,
  listAgents,
  listCases,
  countCases,
  mobile,
  notify,
  role,
} = vi.hoisted(() => ({
  submitFeedback: vi.fn(),
  submitSystemFeedback: vi.fn(),
  createCase: vi.fn(),
  listAgents: vi.fn(),
  listCases: vi.fn(),
  countCases: vi.fn(),
  mobile: { value: true },
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  role: { value: 'viewer' as string | null },
}))

vi.mock('@/api/useApi', () => {
  const api = { submitFeedback, submitSystemFeedback, createCase, listAgents, listCases, countCases }
  return { useApi: () => api }
})
vi.mock('@/lib/feedback', () => ({ notify }))
vi.mock('@/hooks/useMediaQuery', () => ({ useIsMobile: () => mobile.value }))
vi.mock('@/components/ui/sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role.value,
}))

/** Zeigt Pfad + Query der aktuellen Route, damit der Zurueck-Fluss pruefbar ist. */
function Where() {
  const location = useLocation()
  return <output data-testid="where">{`${location.pathname}${location.search}`}</output>
}

function Origin() {
  return (
    <>
      <h1>Ausgangsseite</h1>
      <GiveFeedbackDialog entityType="resource" entityId="r1" entityName="Onboarding" version={3} />
      <ReportProblemDialog />
    </>
  )
}

function renderApp(initial: string[]) {
  return render(
    <SessionContext.Provider
      value={{
        session: null,
        me: null,
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <MemoryRouter initialEntries={initial} initialIndex={initial.length - 1}>
        <Routes>
          <Route path="/w/:workspaceId/resources/:id" element={<Origin />} />
          <Route path="/w/:workspaceId/agents/:id" element={<AgentOrigin />} />
          <Route path="/w/:workspaceId/feedback" element={<HubOrigin />} />
          <Route path="/w/:workspaceId/feedback/cases/new" element={<ReportCasePage />} />
          <Route
            path="/w/:workspaceId/feedback/give/:entityType/:entityId"
            element={<GiveFeedbackPage />}
          />
          <Route path="/w/:workspaceId/feedback/report" element={<ReportProblemPage />} />
        </Routes>
        <Where />
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

/** Einstieg Agent-Detail (D6a): Agent fest. */
function AgentOrigin() {
  return (
    <>
      <h1>Agent coder</h1>
      <ReportCaseDialog agent={{ id: 'a1', name: 'coder' }} />
    </>
  )
}

/** Einstieg Hub (D6b): Agent waehlbar, darunter die Fall-Liste. */
function HubOrigin() {
  return (
    <>
      <h1>Übersicht</h1>
      <ReportCaseDialog variant="brand" />
      <CaseList viewer />
    </>
  )
}

const where = () => screen.getByTestId('where').textContent

const AGENTS = [
  { id: 'a1', name: 'coder' },
  { id: 'a2', name: 'reviewer' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mobile.value = true
  role.value = 'viewer'
  submitFeedback.mockResolvedValue(undefined)
  submitSystemFeedback.mockResolvedValue(undefined)
  createCase.mockResolvedValue({ id: 'case-9' })
  listAgents.mockResolvedValue(AGENTS)
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
})

function fillRequired() {
  fireEvent.change(screen.getByLabelText(/Was war die Lage\?/), {
    target: { value: 'Bitte Tests fixen.' },
  })
  fireEvent.change(screen.getByLabelText(/Was hat der Agent getan\?/), {
    target: { value: 'Direkt gepusht.' },
  })
  fireEvent.change(screen.getByLabelText(/Was hättest du erwartet\?/), {
    target: { value: 'Erst lokal testen.' },
  })
}

describe('Fall melden unter md (Delta-Spec S6 „390 px“, D6c′)', () => {
  it('Ausloeser am Agenten ist ein Link auf die Seite mit ?agent, der Agent steht dort fest', async () => {
    const { container } = renderApp(['/w/ws-1/agents/a1'])
    const trigger = screen.getByRole('link', { name: 'Fall melden' })
    expect(trigger).toHaveAttribute('href', '/w/ws-1/feedback/cases/new?agent=a1')
    fireEvent.click(trigger)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Fall melden' })).toBeInTheDocument()
    expect(screen.getByText('coder')).toBeInTheDocument()
    // Fester Agent: keine Auswahl, kein Abruf der Agentenliste.
    expect(screen.queryByRole('combobox', { name: /Agent/ })).not.toBeInTheDocument()
    expect(listAgents).not.toHaveBeenCalled()
    // Wie die anderen Seiten-Tests: `container` statt `body`, das `main`
    // liefert die App-Shell (sonst meldet axe nur fehlende Landmarks).
    expect(await axe(container)).toHaveNoViolations()
  })

  it('Absenden meldet mit dem festen Agenten und fuehrt zur Ausgangsseite zurueck', async () => {
    renderApp(['/w/ws-1/agents/a1'])
    fireEvent.click(screen.getByRole('link', { name: 'Fall melden' }))
    fillRequired()
    fireEvent.click(screen.getByRole('button', { name: 'Fall melden' }))

    await waitFor(() => expect(where()).toBe('/w/ws-1/agents/a1'))
    expect(createCase).toHaveBeenCalledWith(
      expect.objectContaining({
        agent_id: 'a1',
        situation: 'Bitte Tests fixen.',
        behavior: 'Direkt gepusht.',
        expected_behavior: 'Erst lokal testen.',
        severity: 'medium',
      }),
    )
    expect(screen.getByRole('heading', { name: 'Agent coder' })).toBeInTheDocument()
  })

  it('aus der Fall-Liste: nach Erfolg zurueck zur Liste mit Filter, die Liste ist neu geladen', async () => {
    renderApp(['/w/ws-1/feedback?status=all'])
    await waitFor(() => expect(listCases).toHaveBeenCalledTimes(1))
    const trigger = screen.getByRole('link', { name: 'Fall melden' })
    expect(trigger).toHaveAttribute('href', '/w/ws-1/feedback/cases/new')
    fireEvent.click(trigger)

    const select = await screen.findByRole('combobox', { name: /Agent/ })
    fireEvent.change(select, { target: { value: 'a2' } })
    fillRequired()
    fireEvent.click(screen.getByRole('button', { name: 'Fall melden' }))

    await waitFor(() => expect(where()).toBe('/w/ws-1/feedback?status=all'))
    expect(createCase).toHaveBeenCalledWith(expect.objectContaining({ agent_id: 'a2' }))
    await waitFor(() => expect(listCases).toHaveBeenCalledTimes(2))
  })

  it('Pflichtfelder fehlen: Seite bleibt, nichts wird gesendet', async () => {
    renderApp(['/w/ws-1/agents/a1'])
    fireEvent.click(screen.getByRole('link', { name: 'Fall melden' }))
    fireEvent.click(screen.getByRole('button', { name: 'Fall melden' }))

    await waitFor(() => expect(screen.getByLabelText(/Was war die Lage\?/)).toHaveFocus())
    expect(createCase).not.toHaveBeenCalled()
    expect(where()).toBe('/w/ws-1/feedback/cases/new?agent=a1')
  })

  it('Abbrechen ohne Eingaben geht sofort zurueck, mit Eingaben erst nach „Verwerfen“', async () => {
    renderApp(['/w/ws-1/agents/a1'])
    fireEvent.click(screen.getByRole('link', { name: 'Fall melden' }))
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(where()).toBe('/w/ws-1/agents/a1')

    fireEvent.click(screen.getByRole('link', { name: 'Fall melden' }))
    fireEvent.change(screen.getByLabelText(/Was war die Lage\?/), { target: { value: 'Etwas' } })
    // Auch „Zurück“ fragt nach, statt Eingaben still zu verwerfen.
    fireEvent.click(screen.getByTestId('feedback-compose-back'))
    const confirm = await screen.findByTestId('report-case-discard')
    fireEvent.click(within(confirm).getByRole('button', { name: 'Weiter bearbeiten' }))
    await waitFor(() => expect(screen.queryByTestId('report-case-discard')).not.toBeInTheDocument())
    expect(screen.getByLabelText(/Was war die Lage\?/)).toHaveValue('Etwas')

    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    const again = await screen.findByTestId('report-case-discard')
    fireEvent.click(within(again).getByRole('button', { name: 'Verwerfen' }))
    await waitFor(() => expect(where()).toBe('/w/ws-1/agents/a1'))
    expect(createCase).not.toHaveBeenCalled()
  })

  it('Deep-Link mit ?agent: Agent ist vorausgewaehlt, Zurueck ersetzt durch die Fall-Liste', async () => {
    renderApp(['/w/ws-1/feedback/cases/new?agent=a2'])
    await waitFor(() => expect(screen.getByRole('combobox', { name: /Agent/ })).toHaveValue('a2'))
    // Vorauswahl ist keine Eingabe: Zurueck geht ohne Rueckfrage.
    fireEvent.click(screen.getByTestId('feedback-compose-back'))
    expect(where()).toBe('/w/ws-1/feedback?tab=cases')
  })

  it('Deep-Link mit unbekanntem Agenten laesst die Auswahl leer', async () => {
    renderApp(['/w/ws-1/feedback/cases/new?agent=weg'])
    const select = await screen.findByRole('combobox', { name: /Agent/ })
    expect(select).toHaveValue('')
    fillRequired()
    fireEvent.click(screen.getByRole('button', { name: 'Fall melden' }))
    await waitFor(() => expect(select).toHaveFocus())
    expect(createCase).not.toHaveBeenCalled()
  })

  it('Knopfleiste ist unten fixiert', async () => {
    renderApp(['/w/ws-1/feedback/cases/new?agent=a1'])
    expect(await screen.findByTestId('report-case-footer')).toHaveClass('sticky', 'bottom-0')
  })

  it.each([
    ['viewer', 'Fall gemeldet. Du siehst den Stand unter „Meine Fälle“.'],
    ['editor', 'Fall gemeldet. Du findest ihn unter Fälle.'],
  ])('Rechte: %s darf melden, die Bestaetigung passt zur Rolle', async (current, message) => {
    role.value = current
    renderApp(['/w/ws-1/agents/a1'])
    fireEvent.click(screen.getByRole('link', { name: 'Fall melden' }))
    fillRequired()
    fireEvent.click(screen.getByRole('button', { name: 'Fall melden' }))
    await waitFor(() => expect(createCase).toHaveBeenCalledTimes(1))
    expect(toast.success).toHaveBeenCalledWith(message, expect.anything())
  })

  it('ab md bleibt „Fall melden“ ein Dialog, die Route wechselt nicht', async () => {
    mobile.value = false
    renderApp(['/w/ws-1/agents/a1'])
    expect(screen.queryByRole('link', { name: 'Fall melden' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Fall melden' }))
    expect(await screen.findByTestId('report-case-dialog')).toBeInTheDocument()
    expect(where()).toBe('/w/ws-1/agents/a1')
  })
})

describe('Feedback geben unter md (Mobil-Spec W4=b)', () => {
  it('Ausloeser ist ein Link auf die eigene Seite statt eines Dialogs', () => {
    renderApp(['/w/ws-1/resources/r1?tab=versions'])
    const trigger = screen.getByRole('link', { name: 'Feedback geben' })
    expect(trigger).toHaveAttribute('href', '/w/ws-1/feedback/give/resource/r1?version=3')
    fireEvent.click(trigger)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Feedback geben' })).toBeInTheDocument()
    // Elementname kommt ueber den Navigations-State in die Beschreibung.
    expect(screen.getByText(/„Onboarding“/)).toBeInTheDocument()
  })

  it('Absenden schickt Element-ID + Version und fuehrt mit Bestaetigung zur Ausgangsseite (inkl. ?tab)', async () => {
    renderApp(['/w/ws-1/resources/r1?tab=versions'])
    fireEvent.click(screen.getByRole('link', { name: 'Feedback geben' }))
    fireEvent.change(screen.getByLabelText('Signal'), { target: { value: 'outdated' } })
    fireEvent.change(screen.getByLabelText('Notiz (optional)'), {
      target: { value: '  Fristen veraltet  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Absenden' }))

    await waitFor(() => expect(where()).toBe('/w/ws-1/resources/r1?tab=versions'))
    expect(submitFeedback).toHaveBeenCalledWith({
      entity_type: 'resource',
      entity_id: 'r1',
      version: 3,
      signal: 'outdated',
      note: 'Fristen veraltet',
    })
    expect(notify.success).toHaveBeenCalledWith('Danke für dein Feedback!')
    expect(screen.getByRole('heading', { name: 'Ausgangsseite' })).toBeInTheDocument()
  })

  it('Zurueck und Abbrechen fuehren ohne Absenden zur Ausgangsseite', () => {
    renderApp(['/w/ws-1/resources/r1?tab=versions'])
    fireEvent.click(screen.getByRole('link', { name: 'Feedback geben' }))
    fireEvent.click(screen.getByTestId('feedback-compose-back'))
    expect(where()).toBe('/w/ws-1/resources/r1?tab=versions')

    fireEvent.click(screen.getByRole('link', { name: 'Feedback geben' }))
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(where()).toBe('/w/ws-1/resources/r1?tab=versions')
    expect(submitFeedback).not.toHaveBeenCalled()
  })

  it('Fehler beim Absenden: Seite bleibt, Eingabe bleibt erhalten', async () => {
    submitFeedback.mockRejectedValue(new Error('kaputt'))
    renderApp(['/w/ws-1/resources/r1'])
    fireEvent.click(screen.getByRole('link', { name: 'Feedback geben' }))
    fireEvent.change(screen.getByLabelText('Notiz (optional)'), { target: { value: 'Text' } })
    fireEvent.click(screen.getByRole('button', { name: 'Absenden' }))
    await waitFor(() => expect(notify.error).toHaveBeenCalledWith('kaputt'))
    expect(where()).toBe('/w/ws-1/feedback/give/resource/r1?version=3')
    expect(screen.getByLabelText('Notiz (optional)')).toHaveValue('Text')
  })

  it('Deep-Link ohne Herkunft: Zurueck ersetzt durch die Element-Detailseite', () => {
    renderApp(['/w/ws-1/feedback/give/resource/r1'])
    expect(screen.getByRole('heading', { level: 1, name: 'Feedback geben' })).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('feedback-compose-back'))
    expect(where()).toBe('/w/ws-1/resources/r1')
  })

  it('Deep-Link ohne ?version sendet version undefined', async () => {
    renderApp(['/w/ws-1/feedback/give/resource/r1'])
    fireEvent.click(screen.getByRole('button', { name: 'Absenden' }))
    await waitFor(() => expect(submitFeedback).toHaveBeenCalled())
    expect(submitFeedback.mock.calls[0][0]).toMatchObject({ version: undefined })
  })

  it('unbekannter Element-Typ fuehrt auf die Feedback-Uebersicht', () => {
    renderApp(['/w/ws-1/feedback/give/system/x'])
    expect(where()).toBe('/w/ws-1/feedback')
  })
})

describe('Problem melden unter md (Mobil-Spec W4=b)', () => {
  it('oeffnet die eigene Seite, Absenden erst mit Beschreibung, dann zurueck mit Bestaetigung', async () => {
    renderApp(['/w/ws-1/resources/r1?tab=content'])
    const trigger = screen.getByRole('link', { name: 'Problem melden' })
    expect(trigger).toHaveAttribute('href', '/w/ws-1/feedback/report')
    fireEvent.click(trigger)
    expect(
      screen.getByRole('heading', { level: 1, name: 'System-/MCP-Problem melden' }),
    ).toBeInTheDocument()

    const submit = screen.getByRole('button', { name: 'Melden' })
    expect(submit).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Kategorie'), { target: { value: 'mcp' } })
    fireEvent.change(screen.getByLabelText('Beschreibung'), { target: { value: ' Tool hängt ' } })
    fireEvent.click(submit)

    await waitFor(() => expect(where()).toBe('/w/ws-1/resources/r1?tab=content'))
    expect(submitSystemFeedback).toHaveBeenCalledWith({ category: 'mcp', note: 'Tool hängt' })
    expect(notify.success).toHaveBeenCalledWith('Problem gemeldet. Danke!')
  })

  it('Deep-Link ohne Herkunft: Abbrechen fuehrt auf die Feedback-Uebersicht', () => {
    renderApp(['/w/ws-1/feedback/report'])
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(where()).toBe('/w/ws-1/feedback')
  })
})

describe('ab md bleibt der Dialog', () => {
  it('beide Ausloeser sind Buttons und oeffnen einen Dialog, die Route bleibt', async () => {
    mobile.value = false
    renderApp(['/w/ws-1/resources/r1'])
    expect(screen.queryByRole('link', { name: 'Feedback geben' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Feedback geben' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(where()).toBe('/w/ws-1/resources/r1')
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Problem melden' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(where()).toBe('/w/ws-1/resources/r1')
  })
})
