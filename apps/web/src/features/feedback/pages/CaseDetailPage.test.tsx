import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type {
  Agent,
  CaseDetail,
  CaseEvent,
  MeasureRead,
  SessionDetail,
  SessionListItem,
  WorkspaceRole,
} from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { CaseDetailPage } from './CaseDetailPage'

const api = vi.hoisted(() => ({
  getCase: vi.fn(),
  deleteCase: vi.fn(),
  listAgents: vi.fn(),
  getPlaybook: vi.fn(),
  listPlaybookVersions: vi.fn(),
  getPersona: vi.fn(),
  getResource: vi.fn(),
  getExternalTool: vi.fn(),
  getSystemPromptTemplate: vi.fn(),
  listTestCases: vi.fn(),
  transitionCase: vi.fn(),
  putCaseElements: vi.fn(),
  listPlaybooks: vi.fn(),
  listResources: vi.fn(),
  listExternalTools: vi.fn(),
  listAgentMemories: vi.fn(),
  createTestCase: vi.fn(),
  listSessions: vi.fn(),
  getSession: vi.fn(),
}))

vi.mock('@/api/useApi', () => ({ useApi: () => api }))

let role: WorkspaceRole | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const { notifySuccess, notifyError } = vi.hoisted(() => ({
  notifySuccess: vi.fn(),
  notifyError: vi.fn(),
}))
vi.mock('@/lib/feedback', () => ({
  notify: { success: notifySuccess, error: notifyError, info: vi.fn() },
}))

let mobile = false
vi.mock('@/hooks/useMediaQuery', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/useMediaQuery')>()
  return { ...actual, useIsMobile: () => mobile }
})

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateSpy }
})

const agents = [
  { id: 'a1', name: 'coder', persona_id: null, system_prompt_template_id: null },
] as unknown as Agent[]

function event(overrides: Partial<CaseEvent>): CaseEvent {
  return {
    id: 'e',
    case_id: 'case-1',
    event: 'reported',
    actor_kind: 'human',
    actor_id: 'u1',
    note: null,
    version_entity_type: null,
    version_id: null,
    measure_id: null,
    element_target: null,
    element_entity_id: null,
    created_at: '2026-10-08T10:00:00Z',
    ...overrides,
  }
}

function caseDetail(overrides: Partial<CaseDetail['case']> = {}): CaseDetail {
  return {
    case: {
      id: 'case-1',
      workspace_id: 'ws-1',
      agent_id: 'a1',
      reporter_kind: 'human',
      reporter_user_id: 'u1',
      reporter_agent_id: null,
      situation: 'Fix für #512 gepusht, CI rot.',
      behavior: 'Direkt gepusht.',
      impact: null,
      expected_behavior: 'Tests vor dem Push lokal laufen lassen.',
      severity: 'medium',
      signal: 'incorrect',
      source_ref: null,
      source_feedback_id: null,
      source_memory_id: null,
      status: 'addressed',
      created_at: '2026-10-08T10:00:00Z',
      ...overrides,
    },
    events: [
      event({ id: 'e1', event: 'reported' }),
      event({
        id: 'e2',
        event: 'element_assigned',
        element_target: 'playbook',
        element_entity_id: 'pb1',
        created_at: '2026-10-08T11:00:00Z',
      }),
      event({ id: 'e3', event: 'triaged', actor_id: 'u2', created_at: '2026-10-08T12:00:00Z' }),
      event({
        id: 'e4',
        event: 'addressed',
        version_entity_type: 'playbook',
        version_id: 'pbv3',
        created_at: '2026-10-08T13:00:00Z',
      }),
      // Ein Wert, den diese UI nicht kennt, faellt auf „Änderung“ zurueck.
      event({
        id: 'e5',
        event: 'future_event' as CaseEvent['event'],
        created_at: '2026-10-08T14:00:00Z',
      }),
    ],
    elements: [
      {
        id: 'el1',
        case_id: 'case-1',
        target: 'playbook',
        entity_id: 'pb1',
        assigned_by_kind: 'human',
        assigned_by: 'u1',
        created_at: '2026-10-08T11:00:00Z',
      },
    ],
    statements: [
      {
        id: 's1',
        case_id: 'case-1',
        agent_id: 'a1',
        followed_instruction: 'Ich bin dem Release-Playbook gefolgt.',
        missing_information: 'Dass Tests vorher laufen müssen.',
        conflict: '',
        created_at: '2026-10-08T12:30:00Z',
      },
    ],
  }
}

function renderPage(search = '') {
  return renderInRoutes(<CaseDetailPage />, {
    path: '/w/:workspaceId/feedback/cases/:caseId',
    initialEntries: [`/w/ws-1/feedback/cases/case-1${search}`],
  })
}

function openOverflow() {
  fireEvent.pointerDown(screen.getByTestId('case-overflow'), { button: 0, ctrlKey: false })
}

beforeEach(() => {
  vi.clearAllMocks()
  role = 'editor'
  mobile = false
  api.getCase.mockResolvedValue(caseDetail())
  api.deleteCase.mockResolvedValue(undefined)
  api.listAgents.mockResolvedValue(agents)
  api.getPlaybook.mockResolvedValue({ id: 'pb1', name: 'Release' })
  api.listPlaybookVersions.mockResolvedValue([
    { id: 'pbv2', version: 2 },
    { id: 'pbv3', version: 3, status: 'active' },
  ])
  api.listTestCases.mockResolvedValue([])
  api.transitionCase.mockResolvedValue({})
  api.putCaseElements.mockResolvedValue([])
  api.listPlaybooks.mockResolvedValue([{ id: 'pb1', name: 'Release' }])
  api.listResources.mockResolvedValue([])
  api.listExternalTools.mockResolvedValue([])
  api.listAgentMemories.mockResolvedValue([])
  api.listSessions.mockResolvedValue({ items: [], next_cursor: null })
})

describe('CaseDetailPage', () => {
  it('zeigt Kopf, Status mit Version, nicht-leere SBI-Blöcke, Schilderung und Zuordnung (editor)', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Rückmeldung · coder' })).toBeInTheDocument()
    expect(screen.getByText(/^gemeldet am /)).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByTestId('case-status')).toHaveTextContent('Geändert → Release v3'),
    )
    // „Folge“ ist leer und entfaellt.
    expect(screen.getByTestId('case-block-situation')).toHaveTextContent('Fix für #512 gepusht')
    expect(screen.getByTestId('case-block-behavior')).toBeInTheDocument()
    expect(screen.getByTestId('case-block-expected')).toBeInTheDocument()
    expect(screen.queryByTestId('case-block-impact')).not.toBeInTheDocument()
    expect(screen.getByText(/Der Inhalt einer Rückmeldung bleibt, wie er gemeldet wurde/)).toBeInTheDocument()

    const statement = screen.getByTestId('case-statement')
    expect(within(statement).getByText('Selbstauskunft, keine Bewertung')).toBeInTheDocument()
    expect(within(statement).getByText('Dass Tests vorher laufen müssen.')).toBeInTheDocument()
    // Leere Zeile („Widerspruch“) entfaellt.
    expect(within(statement).queryByText('Widerspruch')).not.toBeInTheDocument()

    const assignment = screen.getByTestId('case-assignment')
    await waitFor(() => expect(within(assignment).getByText('Playbook: Release')).toBeInTheDocument())
  })

  it('zeigt den Verlauf neueste zuerst, mit Versions-Link und Fallback für unbekannte Ereignisse', async () => {
    renderPage()

    const items = await screen.findAllByTestId('case-history-item')
    expect(items).toHaveLength(5)
    expect(items[0]).toHaveTextContent('Änderung')
    expect(items[0]).not.toHaveTextContent('future_event')
    await waitFor(() =>
      expect(within(items[1]).getByRole('link', { name: 'Geändert mit Release v3' })).toHaveAttribute(
        'href',
        '/w/ws-1/playbooks/pb1?tab=versions',
      ),
    )
    expect(items[2]).toHaveTextContent('Eingeordnet')
    expect(items[2]).toHaveTextContent('von einem Mitglied')
    await waitFor(() => expect(items[3]).toHaveTextContent('Zugeordnet: Playbook: Release'))
    expect(items[4]).toHaveTextContent('Gemeldet')
    expect(items[4]).toHaveTextContent('von dir')
  })

  it('führt mit den Filtern der Liste zurück', async () => {
    renderPage('?status=all&agent=a1')

    const back = await screen.findByRole('link', { name: 'Rückmeldungen' })
    expect(back).toHaveAttribute('href', '/w/ws-1/feedback?tab=cases&status=all&agent=a1')
  })

  it('viewer: eigener Fall lesend, ohne Zuordnung und ohne Löschen', async () => {
    role = 'viewer'
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Rückmeldung · coder' })).toBeInTheDocument()
    expect(screen.getByTestId('case-statement')).toBeInTheDocument()
    expect(screen.getAllByTestId('case-history-item').length).toBeGreaterThan(0)
    expect(screen.queryByTestId('case-assignment')).not.toBeInTheDocument()
    expect(screen.queryByText('Zuordnung')).not.toBeInTheDocument()

    openOverflow()
    expect(await screen.findByRole('menuitem', { name: 'ID kopieren' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Rückmeldung löschen…' })).not.toBeInTheDocument()
  })

  it('viewer: fremder Fall (404) zeigt die Nicht-gefunden-Darstellung', async () => {
    role = 'viewer'
    api.getCase.mockRejectedValue(new ApiError(404, 'Not Found', { reason: 'case_not_found' }))
    renderPage('?status=all')

    expect(await screen.findByText('Diese Rückmeldung gibt es nicht (mehr).')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Zu den Rückmeldungen' })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback?tab=cases&status=all',
    )
    expect(screen.queryByRole('heading', { name: /Rückmeldung ·/ })).not.toBeInTheDocument()
  })

  it('zeigt Skeletons, solange der Fall lädt', () => {
    api.getCase.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getAllByTestId('case-detail-skeleton')).toHaveLength(4)
  })

  it('editor: „Fall löschen…“ fragt nach, löscht und kehrt mit Toast zur Liste zurück', async () => {
    renderPage('?status=triaged')
    await screen.findByRole('heading', { name: 'Rückmeldung · coder' })

    openOverflow()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Rückmeldung löschen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung löschen?' })
    expect(within(dialog).getByText(/mit Inhalt, Verlauf, Zuordnung/)).toBeInTheDocument()
    expect(api.deleteCase).not.toHaveBeenCalled()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Endgültig löschen' }))

    await waitFor(() => expect(api.deleteCase).toHaveBeenCalledWith('case-1'))
    await waitFor(() =>
      expect(navigateSpy).toHaveBeenCalledWith('/w/ws-1/feedback?tab=cases&status=triaged'),
    )
    expect(notifySuccess).toHaveBeenCalledWith('Rückmeldung gelöscht.')
  })

  it('nennt im Löschdialog den Lernvorschlag nur, wenn der Fall daraus entstand', async () => {
    api.getCase.mockResolvedValue(caseDetail({ source_memory_id: 'm1' }))
    renderPage()
    await screen.findByRole('heading', { name: 'Rückmeldung · coder' })

    openOverflow()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Rückmeldung löschen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung löschen?' })
    expect(within(dialog).getByText(/Lernvorschlag, aus dem diese Rückmeldung entstanden ist/)).toBeInTheDocument()
  })

  it('a11y: Detail ohne Violations', async () => {
    const { container } = renderPage()
    await screen.findByRole('heading', { name: 'Rückmeldung · coder' })
    await waitFor(() => expect(screen.getByTestId('case-status')).toHaveTextContent('Release v3'))

    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: Löschdialog ohne Violations', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Rückmeldung · coder' })
    openOverflow()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Rückmeldung löschen…' }))
    await screen.findByRole('dialog', { name: 'Rückmeldung löschen?' })

    expect(await axe(document.body)).toHaveNoViolations()
  })
})

const playbookElement = caseDetail().elements[0]

function nextStep() {
  return screen.findByTestId('case-next-step')
}

function openStatusMenu() {
  fireEvent.pointerDown(screen.getByTestId('case-status-menu'), { button: 0, ctrlKey: false })
}

describe('CaseDetailPage – Triage (D6d)', () => {
  it('open ohne Zuordnung: „Zuordnen…“ ist Hauptaktion, Zuordnen speichert und ordnet ein', async () => {
    api.getCase.mockResolvedValue({ ...caseDetail({ status: 'open' }), elements: [] })
    renderPage()

    const bar = await nextStep()
    fireEvent.click(within(bar).getByRole('button', { name: 'Zuordnen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung zuordnen' })
    fireEvent.click(await within(dialog).findByLabelText('Release'))
    expect(within(dialog).getByLabelText('Danach als eingeordnet markieren')).toBeChecked()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zuordnung speichern' }))

    await waitFor(() =>
      expect(api.putCaseElements).toHaveBeenCalledWith('case-1', [{ target: 'playbook', entity_id: 'pb1' }]),
    )
    await waitFor(() => expect(api.transitionCase).toHaveBeenCalledWith('case-1', { to: 'triaged' }))
    await waitFor(() => expect(api.getCase).toHaveBeenCalledTimes(2))
  })

  it('Zuordnen mit „eingeordnet“ ohne Auswahl zeigt den Fehler und sendet nichts', async () => {
    api.getCase.mockResolvedValue({ ...caseDetail({ status: 'open' }), elements: [] })
    renderPage()

    fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Zuordnen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung zuordnen' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zuordnung speichern' }))

    expect(await within(dialog).findByText(/mindestens einem Baustein/)).toBeInTheDocument()
    expect(api.putCaseElements).not.toHaveBeenCalled()
  })

  describe('zweistufiges Zuordnen: zweiter Aufruf scheitert', () => {
    async function assignAndFail(error: unknown) {
      // Erster Laden: ohne Zuordnung; nach dem Neuladen ist sie gespeichert.
      api.getCase.mockResolvedValueOnce({ ...caseDetail({ status: 'open' }), elements: [] })
      api.getCase.mockResolvedValue({ ...caseDetail({ status: 'open' }), elements: [playbookElement] })
      api.transitionCase.mockRejectedValue(error)
      renderPage()

      fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Zuordnen…' }))
      const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung zuordnen' })
      fireEvent.click(await within(dialog).findByLabelText('Release'))
      fireEvent.click(within(dialog).getByRole('button', { name: 'Zuordnung speichern' }))

      await waitFor(() =>
        expect(api.putCaseElements).toHaveBeenCalledWith('case-1', [{ target: 'playbook', entity_id: 'pb1' }]),
      )
      await waitFor(() => expect(api.transitionCase).toHaveBeenCalledWith('case-1', { to: 'triaged' }))
      return dialog
    }

    async function expectSavedAndReloadedOnce(dialog: HTMLElement) {
      // Dialog bleibt offen, Seite laedt genau einmal neu, die Zuordnung ist sichtbar.
      await waitFor(() => expect(api.getCase).toHaveBeenCalledTimes(2))
      expect(dialog).toBeInTheDocument()
      expect(screen.getByRole('dialog', { name: 'Rückmeldung zuordnen' })).toBe(dialog)
      await waitFor(() =>
        expect(within(screen.getByTestId('case-assignment')).getByText('Playbook: Release')).toBeInTheDocument(),
      )
      expect(notifyError).not.toHaveBeenCalled()
      // Kein zweites Neuladen hinterher.
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(api.getCase).toHaveBeenCalledTimes(2)
    }

    it('case_transition_forbidden: Spec-Text im Dialog, Zuordnung bleibt', async () => {
      const dialog = await assignAndFail(
        new ApiError(409, 'Conflict', { reason: 'case_transition_forbidden', params: {} }),
      )
      expect(
        await within(dialog).findByText(
          'Dieser Schritt passt nicht zum aktuellen Stand. Die Seite wurde neu geladen.',
        ),
      ).toBeInTheDocument()
      await expectSavedAndReloadedOnce(dialog)
    })

    it('case_transition_forbidden mit missing=element: Pflicht-Hinweis im Dialog', async () => {
      const dialog = await assignAndFail(
        new ApiError(409, 'Conflict', {
          reason: 'case_transition_forbidden',
          params: { missing: 'element' },
        }),
      )
      expect(await within(dialog).findByText(/mindestens einem Baustein/)).toBeInTheDocument()
      await expectSavedAndReloadedOnce(dialog)
    })

    it('anderer Fehler: Meldung im Dialog, Zuordnung bleibt', async () => {
      const dialog = await assignAndFail(new Error('Netz weg'))
      expect(await within(dialog).findByText('Netz weg')).toBeInTheDocument()
      await expectSavedAndReloadedOnce(dialog)
    })
  })

  it('open mit Zuordnung: „Als eingeordnet markieren“ wechselt direkt und fokussiert den Status', async () => {
    api.getCase.mockResolvedValueOnce(caseDetail({ status: 'open' }))
    api.getCase.mockResolvedValue(caseDetail({ status: 'triaged' }))
    renderPage()

    fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Als eingeordnet markieren' }))

    await waitFor(() => expect(api.transitionCase).toHaveBeenCalledWith('case-1', { to: 'triaged' }))
    await waitFor(() => expect(screen.getByTestId('case-status')).toHaveTextContent('Eingeordnet'))
    await waitFor(() => expect(screen.getByTestId('case-status')).toHaveFocus())
  })

  it('case_transition_forbidden: Hinweis und Neuladen', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'open' }))
    api.transitionCase.mockRejectedValue(
      new ApiError(409, 'Conflict', { reason: 'case_transition_forbidden', params: {} }),
    )
    renderPage()

    fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Als eingeordnet markieren' }))

    await waitFor(() =>
      expect(notifyError).toHaveBeenCalledWith(
        'Dieser Schritt passt nicht zum aktuellen Stand. Die Seite wurde neu geladen.',
      ),
    )
    expect(api.getCase).toHaveBeenCalledTimes(2)
  })

  it('triaged ohne Prüffall: „Prüffall daraus anlegen“ füllt Eingabe, Erwartung und Herkunft vor', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'triaged' }))
    api.createTestCase.mockResolvedValue({ id: 'tc1', title: 'Push-Regel' })
    renderPage()

    fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Prüffall daraus anlegen' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByDisplayValue('Fix für #512 gepusht, CI rot.')).toBeInTheDocument()
    expect(within(dialog).getByDisplayValue('Tests vor dem Push lokal laufen lassen.')).toBeInTheDocument()
    fireEvent.change(within(dialog).getByLabelText('Kurzname'), { target: { value: 'Push-Regel' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Prüffall anlegen' }))

    await waitFor(() =>
      expect(api.createTestCase).toHaveBeenCalledWith(
        expect.objectContaining({
          agent_id: 'a1',
          entity_type: 'playbook',
          entity_id: 'pb1',
          input: 'Fix für #512 gepusht, CI rot.',
          expected_behavior: 'Tests vor dem Push lokal laufen lassen.',
          origin_case_id: 'case-1',
          supersedes_id: null,
        }),
      ),
    )
    // „Verknüpft“ laedt neu.
    await waitFor(() => expect(api.listTestCases).toHaveBeenCalledTimes(2))
  })

  it('triaged mit Prüffall: „Als umgesetzt markieren…“ ist Hauptaktion, verlangt Version und sendet sie', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'triaged' }))
    api.listTestCases.mockResolvedValue([{ id: 'tc1', title: 'Push-Regel', agent_id: 'a1' }])
    renderPage()

    const linked = await screen.findByTestId('case-linked')
    expect(within(linked).getByRole('link', { name: 'Prüffall: Push-Regel' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1#tests',
    )
    fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Als geändert markieren…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Als geändert markieren' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Als geändert markieren' }))
    expect(await within(dialog).findAllByText('Pflichtfeld.')).not.toHaveLength(0)
    expect(api.transitionCase).not.toHaveBeenCalled()

    await within(dialog).findByRole('option', { name: 'v3 · aktiv' })
    fireEvent.change(within(dialog).getByLabelText('Version'), { target: { value: 'pbv3' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Als geändert markieren' }))

    await waitFor(() =>
      expect(api.transitionCase).toHaveBeenCalledWith('case-1', {
        to: 'addressed',
        version_entity_type: 'playbook',
        version_id: 'pbv3',
        note: null,
      }),
    )
  })

  it('triaged ohne versionierten Baustein: Hinweis statt „Als umgesetzt markieren…“', async () => {
    api.getCase.mockResolvedValue({
      ...caseDetail({ status: 'triaged' }),
      elements: [{ ...playbookElement, target: 'tool_policy', entity_id: null }],
    })
    renderPage()

    await nextStep()
    openStatusMenu()
    expect(await screen.findByTestId('case-address-unavailable')).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Als geändert markieren…' })).not.toBeInTheDocument()
  })

  it('Verwerfen verlangt eine Begründung mit mindestens 10 Zeichen', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'open' }))
    renderPage()

    await nextStep()
    openStatusMenu()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Verwerfen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung verwerfen' })
    const reason = within(dialog).getByLabelText('Warum wird nichts geändert?')
    fireEvent.change(reason, { target: { value: 'zu kurz' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Verwerfen' }))
    expect(await within(dialog).findByText('Bitte mindestens 10 Zeichen angeben.')).toBeInTheDocument()
    expect(reason).toHaveAttribute('aria-invalid', 'true')
    expect(api.transitionCase).not.toHaveBeenCalled()

    fireEvent.change(reason, { target: { value: 'Kein Fehler des Agenten.' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Verwerfen' }))
    await waitFor(() =>
      expect(api.transitionCase).toHaveBeenCalledWith('case-1', {
        to: 'dismissed',
        note: 'Kein Fehler des Agenten.',
      }),
    )
  })

  it('Modellgrenze: „Verwerfen…“ ist Hauptaktion mit vorbelegter Begründung', async () => {
    api.getCase.mockResolvedValue({
      ...caseDetail({ status: 'open' }),
      elements: [{ ...playbookElement, target: 'model_limit', entity_id: null }],
    })
    renderPage()

    fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Verwerfen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung verwerfen' })
    expect(within(dialog).getByLabelText('Warum wird nichts geändert?')).toHaveValue(
      'Modellgrenze – keine Änderung sinnvoll.',
    )
  })

  it('addressed: „Zur Version“ führt zur Version, „Wieder öffnen…“ im Menü', async () => {
    renderPage()

    const bar = await nextStep()
    await waitFor(() =>
      expect(within(bar).getByRole('link', { name: 'Zur Version' })).toHaveAttribute(
        'href',
        '/w/ws-1/playbooks/pb1?tab=versions',
      ),
    )
    openStatusMenu()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Wieder öffnen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung wieder öffnen' })
    fireEvent.change(within(dialog).getByLabelText('Warum wird die Rückmeldung wieder geöffnet?'), {
      target: { value: 'Tritt mit v3 wieder auf.' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Wieder öffnen' }))
    await waitFor(() =>
      expect(api.transitionCase).toHaveBeenCalledWith('case-1', {
        to: 'reopened',
        note: 'Tritt mit v3 wieder auf.',
      }),
    )
  })

  it('dismissed: keine Aktion (Endzustand)', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'dismissed' }))
    renderPage()

    await screen.findByRole('heading', { name: 'Rückmeldung · coder' })
    await waitFor(() => expect(api.listTestCases).toHaveBeenCalled())
    expect(screen.queryByTestId('case-next-step')).not.toBeInTheDocument()
  })

  it('viewer: keine Aktionen und kein „Verknüpft“', async () => {
    role = 'viewer'
    api.getCase.mockResolvedValue(caseDetail({ status: 'open', source_memory_id: 'm1' }))
    renderPage()

    await screen.findByRole('heading', { name: 'Rückmeldung · coder' })
    expect(screen.queryByTestId('case-next-step')).not.toBeInTheDocument()
    expect(screen.queryByTestId('case-linked')).not.toBeInTheDocument()
    expect(api.listTestCases).not.toHaveBeenCalled()
  })

  it('„Verknüpft“: Lernvorschlag, Alt-Feedback und Lauf-Link nur bei http(s)', async () => {
    api.getCase.mockResolvedValue(
      caseDetail({
        source_memory_id: 'm1',
        source_feedback_id: 'f1',
        source_ref: 'https://ci.example.org/run/7',
      }),
    )
    const { unmount } = renderPage()

    const linked = await screen.findByTestId('case-linked')
    expect(within(linked).getByRole('link', { name: 'Aus Lernvorschlag' })).toHaveAttribute(
      'href',
      '/w/ws-1/memory?entry=m1',
    )
    expect(within(linked).getByRole('link', { name: 'Aus altem Feedback' })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback/item/f1',
    )
    const run = within(linked).getByRole('link', { name: /ci\.example\.org/ })
    expect(run).toHaveAttribute('href', 'https://ci.example.org/run/7')
    expect(run).toHaveAttribute('rel', 'noopener noreferrer')
    unmount()

    api.getCase.mockResolvedValue(caseDetail({ source_ref: 'javascript:alert(1)' }))
    renderPage()
    const ref = await screen.findByTestId('case-source-ref')
    expect(within(ref).queryByRole('link')).not.toBeInTheDocument()
    expect(ref).toHaveTextContent('javascript:alert(1)')
  })

  it('390 px: Zuordnen als Bottom-Sheet mit Akkordeon-Gruppen', async () => {
    mobile = true
    api.getCase.mockResolvedValue({ ...caseDetail({ status: 'open' }), elements: [] })
    renderPage()

    fireEvent.click(within(await nextStep()).getByRole('button', { name: 'Zuordnen…' }))
    const sheet = await screen.findByTestId('case-assign-dialog')
    const toggle = await within(sheet).findByRole('button', { name: 'Playbooks' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(within(sheet).getByLabelText('Release')).toBeVisible()
  })

  it('a11y: Zuordnen-Dialog ohne Violations', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'open' }))
    renderPage()
    await nextStep()
    openStatusMenu()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Zuordnung ändern…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Rückmeldung zuordnen' })
    await within(dialog).findByLabelText('Release')

    expect(await axe(document.body)).toHaveNoViolations()
  })

  it('a11y: Verwerfen-Dialog ohne Violations', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'open' }))
    renderPage()
    await nextStep()
    openStatusMenu()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Verwerfen…' }))
    await screen.findByRole('dialog', { name: 'Rückmeldung verwerfen' })

    expect(await axe(document.body)).toHaveNoViolations()
  })
})

describe('CaseDetailPage – Status aus Phase E (E5a)', () => {
  function systemEvent(overrides: Partial<CaseEvent>): CaseEvent {
    return event({ actor_kind: 'system', actor_id: null, ...overrides })
  }

  function phaseEDetail(status: CaseDetail['case']['status']): CaseDetail {
    const base = caseDetail({ status })
    return {
      ...base,
      events: [
        event({ id: 'e1', event: 'reported' }),
        event({ id: 'e2', event: 'triaged', created_at: '2026-10-08T11:00:00Z' }),
        systemEvent({
          id: 'e3',
          event: 'in_progress',
          measure_id: 'm1',
          created_at: '2026-10-08T12:00:00Z',
        }),
        systemEvent({
          id: 'e4',
          event: 'addressed',
          version_entity_type: 'playbook',
          version_id: 'pbv3',
          measure_id: 'm1',
          created_at: '2026-10-08T13:00:00Z',
        }),
        systemEvent({
          id: 'e5',
          event: 'reopened',
          measure_id: 'm1',
          note: 'Fallrate unverändert',
          created_at: '2026-10-08T14:00:00Z',
        }),
        systemEvent({
          id: 'e6',
          event: 'verified',
          measure_id: 'm2',
          created_at: '2026-10-08T15:00:00Z',
        }),
      ],
    }
  }

  it('In Arbeit: Ring-Punkt, Wort und Erklärsatz unter dem Status', async () => {
    api.getCase.mockResolvedValue(caseDetail({ status: 'in_progress' }))
    renderPage()

    const status = await screen.findByTestId('case-status')
    expect(status).toHaveTextContent('In Arbeit')
    const dot = within(status).getByTestId('case-status-dot')
    expect(dot).toHaveAttribute('data-shape', 'ring')
    expect(dot).toHaveClass('ring-2', 'ring-offset-1')
    expect(dot).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByTestId('case-status-explain')).toHaveTextContent(
      'Wird gerade über eine Änderung umgesetzt.',
    )
    // Kein Link im Erklaersatz (der kommt mit E5h).
    expect(within(screen.getByTestId('case-status-explain')).queryByRole('link')).toBeNull()
  })

  it('Hat gewirkt: gefüllter Punkt und Erklärsatz, auch für viewer', async () => {
    role = 'viewer'
    api.getCase.mockResolvedValue(caseDetail({ status: 'verified' }))
    renderPage()

    const status = await screen.findByTestId('case-status')
    expect(status).toHaveTextContent('Hat gewirkt')
    const dot = within(status).getByTestId('case-status-dot')
    expect(dot).toHaveAttribute('data-shape', 'filled')
    expect(dot).not.toHaveClass('border-2')
    expect(dot).not.toHaveClass('ring-2')
    expect(screen.getByTestId('case-status-explain')).toHaveTextContent(
      'Die Änderung hat in der Nachkontrolle gewirkt.',
    )
  })

  it('Geändert bleibt hohl und hat keinen Erklärsatz', async () => {
    renderPage()
    const status = await screen.findByTestId('case-status')
    await waitFor(() => expect(status).toHaveTextContent('Geändert → Release v3'))
    expect(within(status).getByTestId('case-status-dot')).toHaveAttribute('data-shape', 'hollow')
    expect(within(status).getByTestId('case-status-dot')).toHaveClass('border-2')
    expect(screen.queryByTestId('case-status-explain')).not.toBeInTheDocument()
  })

  it('Verlauf: vier neue Ereignistexte statt „Änderung“, Aktivierung mit Element und Version', async () => {
    api.getCase.mockResolvedValue(phaseEDetail('verified'))
    renderPage()

    const items = await screen.findAllByTestId('case-history-item')
    expect(items).toHaveLength(6)
    expect(items[0]).toHaveTextContent('Hat gewirkt laut Nachkontrolle')
    expect(items[1]).toHaveTextContent(
      'Wieder geöffnet nach Nachkontrolle „Hat nicht gewirkt“: Fallrate unverändert',
    )
    await waitFor(() =>
      expect(
        within(items[2]).getByRole('link', {
          name: 'Geändert mit Release v3 (bei Aktivierung)',
        }),
      ).toHaveAttribute('href', '/w/ws-1/playbooks/pb1?tab=versions'),
    )
    expect(items[3]).toHaveTextContent('In Arbeit: Änderung aus einem Review')
    // Kein Eintrag faellt mehr auf das Ersatzwort zurueck.
    expect(screen.queryByText('Änderung')).not.toBeInTheDocument()
    // Die Notiz steht im Wort, nicht doppelt darunter.
    expect(screen.getAllByText(/Fallrate unverändert/)).toHaveLength(1)
    // Ohne geladenes Review kein Link „Zur Änderung“ (E5h verlinkt nur Aufloesbares).
    expect(screen.queryByRole('link', { name: /Zur Maßnahme|Zur Änderung/ })).toBeNull()
  })

  it('Wieder geöffnet durch einen Menschen behält den alten Text', async () => {
    api.getCase.mockResolvedValue({
      ...caseDetail({ status: 'reopened' }),
      events: [event({ id: 'e1', event: 'reopened', note: 'Doch nicht behoben' })],
    })
    renderPage()
    const items = await screen.findAllByTestId('case-history-item')
    expect(items[0]).toHaveTextContent('Wieder geöffnet: Doch nicht behoben')
    expect(items[0]).not.toHaveTextContent('Nachkontrolle')
  })

  it.each(['open', 'triaged', 'in_progress', 'addressed', 'verified'] as const)(
    'kein Knopf und kein Menüpunkt setzt In Arbeit oder Hat gewirkt (%s)',
    async (status) => {
      api.getCase.mockResolvedValue(phaseEDetail(status))
      api.listTestCases.mockResolvedValue([{ id: 't1', title: 'Push erst nach Tests' }])
      renderPage()
      await screen.findByRole('heading', { name: 'Rückmeldung · coder' })
      await waitFor(() => expect(api.listTestCases).toHaveBeenCalled())

      const forbidden = /In Arbeit|Hat gewirkt|Bestätig|verified|in_progress/
      expect(screen.queryByRole('button', { name: forbidden })).toBeNull()
      if (screen.queryByTestId('case-status-menu') !== null) {
        openStatusMenu()
        await screen.findAllByRole('menuitem')
        expect(screen.queryByRole('menuitem', { name: forbidden })).toBeNull()
        fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' })
      }
      openOverflow()
      await screen.findByRole('menuitem', { name: 'ID kopieren' })
      expect(screen.queryByRole('menuitem', { name: forbidden })).toBeNull()
      expect(api.transitionCase).not.toHaveBeenCalled()
      // In Arbeit und Hat gewirkt haben keine eigene Aktion (E5i bringt Links).
      if (status === 'in_progress' || status === 'verified') {
        expect(screen.queryByTestId('case-next-step')).not.toBeInTheDocument()
      }
    },
  )

  it('a11y: In Arbeit mit Verlauf ohne Violations (editor)', async () => {
    api.getCase.mockResolvedValue(phaseEDetail('in_progress'))
    const { container } = renderPage()
    await screen.findByTestId('case-status-explain')
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /bei Aktivierung/ })).toBeInTheDocument(),
    )
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Hat gewirkt mit Verlauf ohne Violations (viewer)', async () => {
    role = 'viewer'
    api.getCase.mockResolvedValue(phaseEDetail('verified'))
    const { container } = renderPage()
    await screen.findByTestId('case-status-explain')
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)
})

describe('CaseDetailPage – Verknüpft, Nachkontrolle, Verlauf-Links (E5h)', () => {
  // Vergangen bzw. weit in der Zukunft: unabhaengig vom Testdatum.
  const PAST = '2020-01-01'
  const FUTURE = '2099-01-01'

  function sessionRow(overrides: Partial<SessionListItem>): SessionListItem {
    return {
      id: 's1',
      workspace_id: 'ws-1',
      agent_id: 'a1',
      trigger: 'manual',
      participants: [],
      summary: 'Review',
      decisions: [],
      dissent: [],
      follow_up_at: PAST,
      supersedes_id: null,
      submitted_by_kind: 'agent',
      submitted_by: 'b1',
      case_ids: ['case-1'],
      created_at: '2026-09-25T10:00:00Z',
      case_count: 1,
      measure_count: 1,
      next_follow_up_at: null,
      due_measure_count: 0,
      superseded_by_id: null,
      ...overrides,
    }
  }

  function measure(overrides: Partial<MeasureRead>): MeasureRead {
    return {
      id: 'm1',
      workspace_id: 'ws-1',
      agent_id: 'a1',
      session_id: 's1',
      case_ids: ['case-1'],
      target: 'playbook',
      entity_id: 'pb1',
      change_summary: 'Tests vor dem Push',
      test_case_id: 't1',
      success_criterion: 'Kein roter Push',
      counterposition: '',
      follow_up_at: null,
      state: 'activated',
      // Absichtlich leer: lokal abgeleitet waere das „Vereinbart“. Die
      // Ansicht muss den Server-Zustand zeigen (eine Quelle je Ansicht).
      events: [],
      created_at: '2026-09-25T10:00:00Z',
      ...overrides,
    }
  }

  function detailOf(row: SessionListItem, measures: MeasureRead[]): SessionDetail {
    const { case_count, measure_count, next_follow_up_at, due_measure_count, superseded_by_id, ...session } = row
    void case_count
    void measure_count
    void next_follow_up_at
    void due_measure_count
    return { session, measures, superseded_by_id }
  }

  // Zwei Reviews, zwei Aenderungen am Fall: m1 faellig (Review s1, Termin
  // vorbei), m2 geplant (Review s2, Termin in der Zukunft). Dazu Rauschen,
  // das nicht erscheinen darf: eine Aenderung zu einem anderen Fall und eine
  // mit fremder `session_id`.
  const s1 = sessionRow({ id: 's1', follow_up_at: PAST })
  const s2 = sessionRow({ id: 's2', follow_up_at: FUTURE, created_at: '2026-10-10T10:00:00Z' })
  const details: Record<string, SessionDetail> = {
    s1: detailOf(s1, [
      measure({ id: 'm1', session_id: 's1' }),
      measure({ id: 'm-other-case', session_id: 's1', case_ids: ['case-9'] }),
    ]),
    s2: detailOf(s2, [
      measure({ id: 'm2', session_id: 's2', state: 'draft_linked' }),
      measure({ id: 'm-foreign', session_id: 's-foreign' }),
    ]),
  }

  function withHistory(): CaseDetail {
    const base = caseDetail({ status: 'in_progress' })
    return {
      ...base,
      events: [
        event({ id: 'e1', event: 'reported' }),
        event({
          id: 'e2',
          event: 'in_progress',
          actor_kind: 'system',
          actor_id: null,
          measure_id: 'm1',
          created_at: '2026-10-08T12:00:00Z',
        }),
        // Aenderung, die in keinem geladenen Review steckt: kein Link.
        event({
          id: 'e3',
          event: 'reopened',
          actor_kind: 'system',
          actor_id: null,
          measure_id: 'm-unknown',
          note: 'Fallrate unverändert',
          created_at: '2026-10-08T13:00:00Z',
        }),
      ],
    }
  }

  beforeEach(() => {
    api.getCase.mockResolvedValue(withHistory())
    api.listSessions.mockResolvedValue({ items: [s2, s1], next_cursor: null })
    api.getSession.mockImplementation((id: string) => Promise.resolve(details[id]))
  })

  it('editor: zwei Zeilen je Änderung mit Server-Zustand, Fällig-Pill bzw. Termin', async () => {
    renderPage()

    const linked = await screen.findByTestId('case-linked')
    await waitFor(() => expect(within(linked).getAllByTestId('case-linked-change')).toHaveLength(2))
    const reviews = within(linked).getAllByTestId('case-linked-review')
    const changes = within(linked).getAllByTestId('case-linked-change')

    // Reihenfolge wie die Liste vom Server (neueste zuerst): s2/m2, dann s1/m1.
    expect(within(reviews[0]).getByRole('link', { name: 'Review vom 10.10.2026' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/s2',
    )
    expect(within(reviews[1]).getByRole('link', { name: 'Review vom 25.09.2026' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/s1',
    )
    await waitFor(() =>
      expect(
        within(changes[1]).getByRole('link', {
          name: 'Änderung: Playbook „Release“ · Aktiviert',
        }),
      ).toHaveAttribute('href', '/w/ws-1/agents/a1/reviews/s1?change=m1'),
    )
    expect(
      within(changes[0]).getByRole('link', { name: 'Änderung: Playbook „Release“ · Entwurf verknüpft' }),
    ).toHaveAttribute('href', '/w/ws-1/agents/a1/reviews/s2?change=m2')

    // m1 faellig und laut Server aktiviert: „Nachkontrolle fällig“, nicht
    // „… noch nicht aktiv“ (das ergaebe die lokale Ableitung aus `events: []`).
    expect(within(changes[1]).getByTestId('measure-due')).toHaveTextContent(/^Nachkontrolle fällig$/)
    expect(within(changes[0]).queryByTestId('measure-due')).toBeNull()
    expect(changes[0]).toHaveTextContent('Nachkontrolle am 01.01.2099')

    // Rauschen erscheint nicht: kein Link auf m-other-case oder m-foreign.
    expect(linked.querySelector('a[href*="m-other-case"]')).toBeNull()
    expect(linked.querySelector('a[href*="m-foreign"]')).toBeNull()

    // Kopf: Pill neben dem Status, Rueckweg zum Agenten.
    expect(await screen.findByTestId('case-follow-up-due')).toHaveTextContent('Nachkontrolle fällig')
    expect(screen.getByRole('link', { name: 'Zu coder → Weiterentwicklung' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1?tab=evolution',
    )
  })

  it('editor: Verlauf verlinkt nur Ereignisse, deren Änderung in einem geladenen Review steckt', async () => {
    renderPage()

    await screen.findAllByTestId('case-linked-change')
    const items = screen.getAllByTestId('case-history-item')
    // Neueste zuerst: e3 (m-unknown), e2 (m1), e1.
    await waitFor(() =>
      expect(within(items[1]).getByRole('link', { name: 'Zur Änderung' })).toHaveAttribute(
        'href',
        '/w/ws-1/agents/a1/reviews/s1?change=m1',
      ),
    )
    expect(within(items[0]).queryByRole('link', { name: 'Zur Änderung' })).toBeNull()
    expect(within(items[2]).queryByRole('link', { name: 'Zur Änderung' })).toBeNull()
    expect(screen.getAllByTestId('case-history-to-change')).toHaveLength(1)
  })

  it('editor: ohne fällige Änderung keine Pill im Kopf', async () => {
    api.listSessions.mockResolvedValue({ items: [s2], next_cursor: null })
    renderPage()

    await screen.findAllByTestId('case-linked-change')
    expect(screen.queryByTestId('case-follow-up-due')).toBeNull()
  })

  it('editor: ein Listen-Request mit Grenze, höchstens 10 Details, nichts je Ereignis', async () => {
    const many = Array.from({ length: 12 }, (_, index) => sessionRow({ id: `s${index + 1}` }))
    api.listSessions.mockResolvedValue({ items: many, next_cursor: 'c' })
    api.getSession.mockImplementation((id: string) =>
      Promise.resolve(detailOf(sessionRow({ id }), [measure({ id: `m-${id}`, session_id: id })])),
    )
    renderPage()

    await waitFor(() => expect(screen.getAllByTestId('case-linked-change')).toHaveLength(10))
    expect(api.listSessions).toHaveBeenCalledTimes(1)
    expect(api.listSessions).toHaveBeenCalledWith({ case_id: 'case-1' }, { limit: 10 })
    expect(api.getSession).toHaveBeenCalledTimes(10)
  })

  it('editor: Reviews fremder Agenten oder ohne diesen Fall werden nicht geladen', async () => {
    api.listSessions.mockResolvedValue({
      items: [
        s1,
        sessionRow({ id: 's-other-agent', agent_id: 'a2' }),
        sessionRow({ id: 's-other-case', case_ids: ['case-9'] }),
      ],
      next_cursor: null,
    })
    renderPage()

    await waitFor(() => expect(screen.getAllByTestId('case-linked-change')).toHaveLength(1))
    expect(api.getSession).toHaveBeenCalledTimes(1)
    expect(api.getSession).toHaveBeenCalledWith('s1')
  })

  it('editor: Fehler beim Laden der Reviews lässt Verknüpft und Verlauf ohne Links', async () => {
    api.listSessions.mockRejectedValue(new Error('boom'))
    renderPage()

    await screen.findAllByTestId('case-history-item')
    await waitFor(() => expect(api.listSessions).toHaveBeenCalled())
    expect(screen.queryByTestId('case-linked-change')).toBeNull()
    expect(screen.queryByTestId('case-history-to-change')).toBeNull()
    expect(screen.queryByTestId('case-follow-up-due')).toBeNull()
  })

  it('viewer: kein Review-Request, keine Links, keine Pill; Rückweg zum Agenten bleibt', async () => {
    role = 'viewer'
    renderPage()

    await screen.findAllByTestId('case-history-item')
    expect(screen.getByRole('link', { name: 'Zu coder → Weiterentwicklung' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1?tab=evolution',
    )
    // Warten, bis die uebrigen Effekte gelaufen sind, dann zaehlen.
    await waitFor(() => expect(api.listAgents).toHaveBeenCalled())
    expect(api.listSessions).not.toHaveBeenCalled()
    expect(api.getSession).not.toHaveBeenCalled()
    expect(screen.queryByTestId('case-linked')).toBeNull()
    expect(screen.queryByTestId('case-history-to-change')).toBeNull()
    expect(screen.queryByTestId('case-follow-up-due')).toBeNull()
  })

  it('Rollenwechsel editor → viewer: geladene Änderungen, Pill und Links verschwinden', async () => {
    renderPage()
    await screen.findByTestId('case-follow-up-due')
    await screen.findByTestId('case-history-to-change')

    role = 'viewer'
    // Irgendein Re-Render der Seite liest die Rolle neu.
    fireEvent.click(screen.getByRole('button', { name: 'Mehr anzeigen' }))

    await waitFor(() => expect(screen.queryByTestId('case-follow-up-due')).toBeNull())
    expect(screen.queryByTestId('case-history-to-change')).toBeNull()
    expect(screen.queryByTestId('case-linked')).toBeNull()
  })

  it('a11y: editor mit Verknüpft, Pill und Verlauf-Link ohne Violations', async () => {
    const { container } = renderPage()
    await screen.findByTestId('case-follow-up-due')
    await screen.findByTestId('case-history-to-change')
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)

  it('a11y: viewer mit Rückweg ohne Violations', async () => {
    role = 'viewer'
    const { container } = renderPage()
    await screen.findByTestId('case-to-evolution')
    expect(await axe(container)).toHaveNoViolations()
  }, 15_000)
})
