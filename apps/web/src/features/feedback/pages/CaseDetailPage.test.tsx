import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Agent, CaseDetail, CaseEvent, WorkspaceRole } from '@/api/types'
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
}))

vi.mock('@/api/useApi', () => ({ useApi: () => api }))

let role: WorkspaceRole | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const { notifySuccess } = vi.hoisted(() => ({ notifySuccess: vi.fn() }))
vi.mock('@/lib/feedback', () => ({
  notify: { success: notifySuccess, error: vi.fn(), info: vi.fn() },
}))

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateSpy }
})

const agents = [{ id: 'a1', name: 'coder' }] as Agent[]

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
      event({ id: 'e5', event: 'verified', created_at: '2026-10-08T14:00:00Z' }),
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
  api.getCase.mockResolvedValue(caseDetail())
  api.deleteCase.mockResolvedValue(undefined)
  api.listAgents.mockResolvedValue(agents)
  api.getPlaybook.mockResolvedValue({ id: 'pb1', name: 'Release' })
  api.listPlaybookVersions.mockResolvedValue([
    { id: 'pbv2', version: 2 },
    { id: 'pbv3', version: 3 },
  ])
})

describe('CaseDetailPage', () => {
  it('zeigt Kopf, Status mit Version, nicht-leere SBI-Blöcke, Schilderung und Zuordnung (editor)', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Fall · coder' })).toBeInTheDocument()
    expect(screen.getByText(/^gemeldet am /)).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByTestId('case-status')).toHaveTextContent('Umgesetzt → Release v3'),
    )
    // „Folge“ ist leer und entfaellt.
    expect(screen.getByTestId('case-block-situation')).toHaveTextContent('Fix für #512 gepusht')
    expect(screen.getByTestId('case-block-behavior')).toBeInTheDocument()
    expect(screen.getByTestId('case-block-expected')).toBeInTheDocument()
    expect(screen.queryByTestId('case-block-impact')).not.toBeInTheDocument()
    expect(screen.getByText(/Der Inhalt eines Falls bleibt, wie er gemeldet wurde/)).toBeInTheDocument()

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
    expect(items[0]).not.toHaveTextContent('verified')
    await waitFor(() =>
      expect(within(items[1]).getByRole('link', { name: 'Umgesetzt mit Release v3' })).toHaveAttribute(
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

    const back = await screen.findByRole('link', { name: 'Fälle' })
    expect(back).toHaveAttribute('href', '/w/ws-1/feedback?tab=cases&status=all&agent=a1')
  })

  it('viewer: eigener Fall lesend, ohne Zuordnung und ohne Löschen', async () => {
    role = 'viewer'
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Fall · coder' })).toBeInTheDocument()
    expect(screen.getByTestId('case-statement')).toBeInTheDocument()
    expect(screen.getAllByTestId('case-history-item').length).toBeGreaterThan(0)
    expect(screen.queryByTestId('case-assignment')).not.toBeInTheDocument()
    expect(screen.queryByText('Zuordnung')).not.toBeInTheDocument()

    openOverflow()
    expect(await screen.findByRole('menuitem', { name: 'ID kopieren' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Fall löschen…' })).not.toBeInTheDocument()
  })

  it('viewer: fremder Fall (404) zeigt die Nicht-gefunden-Darstellung', async () => {
    role = 'viewer'
    api.getCase.mockRejectedValue(new ApiError(404, 'Not Found', { reason: 'case_not_found' }))
    renderPage('?status=all')

    expect(await screen.findByText('Diesen Fall gibt es nicht (mehr).')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Zu den Fällen' })).toHaveAttribute(
      'href',
      '/w/ws-1/feedback?tab=cases&status=all',
    )
    expect(screen.queryByRole('heading', { name: /Fall ·/ })).not.toBeInTheDocument()
  })

  it('zeigt Skeletons, solange der Fall lädt', () => {
    api.getCase.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getAllByTestId('case-detail-skeleton')).toHaveLength(4)
  })

  it('editor: „Fall löschen…“ fragt nach, löscht und kehrt mit Toast zur Liste zurück', async () => {
    renderPage('?status=triaged')
    await screen.findByRole('heading', { name: 'Fall · coder' })

    openOverflow()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Fall löschen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Fall löschen?' })
    expect(within(dialog).getByText(/mit Inhalt, Verlauf, Zuordnung/)).toBeInTheDocument()
    expect(api.deleteCase).not.toHaveBeenCalled()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Endgültig löschen' }))

    await waitFor(() => expect(api.deleteCase).toHaveBeenCalledWith('case-1'))
    await waitFor(() =>
      expect(navigateSpy).toHaveBeenCalledWith('/w/ws-1/feedback?tab=cases&status=triaged'),
    )
    expect(notifySuccess).toHaveBeenCalledWith('Fall gelöscht.')
  })

  it('nennt im Löschdialog den Lernvorschlag nur, wenn der Fall daraus entstand', async () => {
    api.getCase.mockResolvedValue(caseDetail({ source_memory_id: 'm1' }))
    renderPage()
    await screen.findByRole('heading', { name: 'Fall · coder' })

    openOverflow()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Fall löschen…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Fall löschen?' })
    expect(within(dialog).getByText(/Lernvorschlag, aus dem dieser Fall entstanden ist/)).toBeInTheDocument()
  })

  it('a11y: Detail ohne Violations', async () => {
    const { container } = renderPage()
    await screen.findByRole('heading', { name: 'Fall · coder' })
    await waitFor(() => expect(screen.getByTestId('case-status')).toHaveTextContent('Release v3'))

    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: Löschdialog ohne Violations', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Fall · coder' })
    openOverflow()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Fall löschen…' }))
    await screen.findByRole('dialog', { name: 'Fall löschen?' })

    expect(await axe(document.body)).toHaveNoViolations()
  })
})
