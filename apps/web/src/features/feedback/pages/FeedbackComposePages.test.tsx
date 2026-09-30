import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SessionContext } from '@/auth/session-context'
import { GiveFeedbackDialog } from '@/components/feedback/GiveFeedbackDialog'

import { ReportProblemDialog } from '../components/ReportProblemDialog'
import { GiveFeedbackPage, ReportProblemPage } from './FeedbackComposePages'

const { submitFeedback, submitSystemFeedback, mobile, notify } = vi.hoisted(() => ({
  submitFeedback: vi.fn(),
  submitSystemFeedback: vi.fn(),
  mobile: { value: true },
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/useApi', () => {
  const api = { submitFeedback, submitSystemFeedback }
  return { useApi: () => api }
})
vi.mock('@/lib/feedback', () => ({ notify }))
vi.mock('@/hooks/useMediaQuery', () => ({ useIsMobile: () => mobile.value }))

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
          <Route path="/w/:workspaceId/feedback" element={<h1>Übersicht</h1>} />
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

const where = () => screen.getByTestId('where').textContent

beforeEach(() => {
  vi.clearAllMocks()
  mobile.value = true
  submitFeedback.mockResolvedValue(undefined)
  submitSystemFeedback.mockResolvedValue(undefined)
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
