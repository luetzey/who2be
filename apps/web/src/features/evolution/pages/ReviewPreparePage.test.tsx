import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Agent, CaseRead, Dossier, WorkspaceRole } from '@/api/types'
import { RouterRoot } from '@/app/routes'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { ReviewPreparePage } from './ReviewPreparePage'

// E5f: Review vorbereiten (Neuschnitt §2, §4; E5-Delta §3).

const api = vi.hoisted(() => ({
  getAgent: vi.fn(),
  listCases: vi.fn(),
  getDossier: vi.fn(),
}))
vi.mock('@/api/useApi', () => ({ useApi: () => api }))

let role: WorkspaceRole | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', () => ({ useIsMobile: () => viewport.mobile }))

const { notifySuccess, notifyError } = vi.hoisted(() => ({
  notifySuccess: vi.fn(),
  notifyError: vi.fn(),
}))
vi.mock('@/lib/feedback', () => ({
  notify: { success: notifySuccess, error: notifyError, info: vi.fn() },
}))

const { copySpy } = vi.hoisted(() => ({ copySpy: vi.fn() }))
vi.mock('@/lib/clipboard', () => ({ copyToClipboard: copySpy }))

const AGENT_ID = '11111111-1111-4111-8111-111111111111'
const C1 = 'c0000000-0000-4000-8000-000000000001'
const C2 = 'c0000000-0000-4000-8000-000000000002'
const C3 = 'c0000000-0000-4000-8000-000000000003'
const C4 = 'c0000000-0000-4000-8000-000000000004'
const C5 = 'c0000000-0000-4000-8000-000000000005'
// Gueltige UUIDs, die der Server fuer diesen Agenten nicht liefert.
const FOREIGN = 'f0000000-0000-4000-8000-0000000000ff'
const FOREIGN_2 = 'f0000000-0000-4000-8000-0000000000fe'
const FOREIGN_3 = 'f0000000-0000-4000-8000-0000000000fd'
// Freitext, der nie in die Zwischenablage darf (D-Delta S5).
const SECRET = 'Kunde Müller wurde falsch beraten'

const agent = { id: AGENT_ID, name: 'coder' } as unknown as Agent

function caseRead(id: string, overrides: Partial<CaseRead>): CaseRead {
  return {
    id,
    workspace_id: 'ws-1',
    agent_id: AGENT_ID,
    reporter_kind: 'human',
    reporter_user_id: 'u1',
    reporter_agent_id: null,
    situation: SECRET,
    behavior: SECRET,
    impact: null,
    expected_behavior: `Erwartung ${id.slice(-1)}`,
    severity: 'medium',
    signal: null,
    source_ref: null,
    source_feedback_id: null,
    source_memory_id: null,
    status: 'open',
    created_at: '2026-10-01T10:00:00Z',
    ...overrides,
  }
}

const firstPage = [
  caseRead(C1, { status: 'triaged', severity: 'low', created_at: '2026-10-05T10:00:00Z' }),
  caseRead(C2, { status: 'triaged', severity: 'high', created_at: '2026-10-01T10:00:00Z' }),
  caseRead(C3, { status: 'open', severity: 'medium' }),
  caseRead(C4, { status: 'reopened', severity: 'high' }),
]

function dossier(overrides: Partial<Dossier> = {}): Dossier {
  return {
    agent_id: AGENT_ID,
    agent_name: 'coder',
    generated_at: '2026-10-14T10:00:00Z',
    min_uses: 50,
    open_cases: {
      // Bewusst nicht die Laenge der Auswahl-Liste: die Zahl kommt vom Server.
      counts: { open: 7, reopened: 1, triaged: 2, in_progress: 3 },
      total: 13,
      items: [],
    },
    elements: [
      {
        entity_type: 'playbook',
        entity_id: 'p1',
        name: 'Code-Task-Flow',
        versions: [
          {
            version: 3,
            active: true,
            activated_at: '2026-09-01T00:00:00Z',
            uses: 400,
            outcomes: {},
            signals: { outdated: 2 },
            cases: 6,
            insufficient: false,
          },
          {
            version: 2,
            active: false,
            activated_at: '2026-08-01T00:00:00Z',
            uses: 10,
            outcomes: {},
            signals: {},
            cases: 1,
            insufficient: true,
          },
        ],
      },
    ],
    elements_total: 1,
    access: {
      since: '2026-09-14T00:00:00Z',
      window_days: 30,
      total: 42,
      rows: [
        {
          ref_kind: 'memory',
          operation: 'read',
          sensitivity: 'normal',
          entries: 42,
          refs: 5,
          last_on: '2026-10-13',
        },
      ],
    },
    measures: Array.from({ length: 6 }, (_, index) => ({
      id: `m${index}`,
      session_id: `s${index}`,
      target: 'playbook' as const,
      entity_id: 'p1',
      change_summary: SECRET,
      state: 'activated' as const,
      verdict: null,
      reviewed_at: null,
      follow_up_at: '2026-10-30',
      case_count: 1,
      created_at: `2026-09-1${index}T10:00:00Z`,
    })),
    measures_total: 9,
    generations: [],
    generations_next_cursor: null,
    ...overrides,
  }
}

function renderPage(query = '') {
  return renderInRoutes(<ReviewPreparePage />, {
    path: '/w/:workspaceId/agents/:agentId/reviews/prepare',
    initialEntries: [`/w/ws-1/agents/${AGENT_ID}/reviews/prepare${query}`],
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  role = 'editor'
  viewport.mobile = false
  // Nicht verbrauchte Once-Antworten eines roten Tests duerfen nicht in den naechsten laufen.
  api.listCases.mockReset()
  api.getAgent.mockResolvedValue(agent)
  api.listCases.mockResolvedValue({ items: firstPage, next_cursor: null })
  api.getDossier.mockResolvedValue(dossier())
  copySpy.mockResolvedValue(undefined)
})

afterEach(() => {
  document.documentElement.style.scrollPaddingBottom = ''
})

function textarea(): HTMLTextAreaElement {
  return within(screen.getByTestId('prepare-copy')).getByRole('textbox') as HTMLTextAreaElement
}

describe('Route', () => {
  it('stellt `prepare` vor `:sessionId`, damit es nie als Review-ID matcht', () => {
    const paths: string[] = []
    const walk = (node: unknown) => {
      if (node === null || typeof node !== 'object') return
      const element = node as { props?: { path?: string; children?: unknown } }
      if (typeof element.props?.path === 'string') paths.push(element.props.path)
      const children = element.props?.children
      if (Array.isArray(children)) children.forEach(walk)
      else walk(children)
    }
    // RouterRoot nutzt keine Hooks: der Elementbaum laesst sich ohne Rendern lesen.
    walk(RouterRoot())
    const prepare = paths.indexOf('/w/:workspaceId/agents/:agentId/reviews/prepare')
    const detail = paths.indexOf('/w/:workspaceId/agents/:agentId/reviews/:sessionId')
    expect(prepare).toBeGreaterThanOrEqual(0)
    expect(detail).toBeGreaterThan(prepare)
  })
})

describe('Rechte', () => {
  it('leitet einen viewer per replace auf den Tab, ohne einen Request', async () => {
    role = 'viewer'
    renderInRoutes(<ReviewPreparePage />, {
      path: '/w/:workspaceId/agents/:agentId/reviews/prepare',
      initialEntries: [`/w/ws-1/agents/${AGENT_ID}/reviews/prepare`],
    })
    await waitFor(() => expect(screen.queryByText('Review vorbereiten')).not.toBeInTheDocument())
    expect(api.getAgent).not.toHaveBeenCalled()
    expect(api.listCases).not.toHaveBeenCalled()
    expect(api.getDossier).not.toHaveBeenCalled()
  })

  it('laedt nichts, solange die Rolle unbekannt ist', () => {
    role = null
    renderPage()
    expect(api.getAgent).not.toHaveBeenCalled()
    expect(api.listCases).not.toHaveBeenCalled()
    expect(api.getDossier).not.toHaveBeenCalled()
  })

  it('zeigt bei unbekanntem Agenten „gibt es nicht mehr“', async () => {
    api.getAgent.mockRejectedValue(new ApiError(404, 'agent_not_found'))
    renderPage()
    expect(await screen.findByText(/Diesen Agenten gibt es nicht mehr/)).toBeInTheDocument()
  })
})

describe('① Rückmeldungen', () => {
  it('fragt nur auswaehlbare Status des Agenten ab, 20 je Seite', async () => {
    renderPage()
    await screen.findByTestId('prepare-group-triaged')
    expect(api.listCases).toHaveBeenCalledTimes(1)
    expect(api.listCases).toHaveBeenCalledWith(
      { agent_id: AGENT_ID, status: ['triaged', 'open', 'reopened'] },
      { limit: 20 },
    )
  })

  it('gruppiert in Eingeordnet / Noch nicht eingeordnet, Schwere vor Datum', async () => {
    renderPage()
    const triaged = await screen.findByTestId('prepare-group-triaged')
    const untriaged = screen.getByTestId('prepare-group-untriaged')
    expect(within(triaged).getByText('Eingeordnet')).toBeInTheDocument()
    expect(within(untriaged).getByText('Der Builder kann sie im Review zuordnen.')).toBeInTheDocument()
    const order = (group: HTMLElement) =>
      within(group)
        .getAllByRole('checkbox')
        .map((box) => box.getAttribute('data-case-id'))
    // high vor low, obwohl low neuer ist.
    expect(order(triaged)).toEqual([C2, C1])
    expect(order(untriaged)).toEqual([C4, C3])
  })

  it('schreibt die Auswahl in ?cases und baut den Startsatz live', async () => {
    renderPage()
    await screen.findByTestId('prepare-group-triaged')
    expect(textarea().value).not.toContain('Rückmeldungen:')
    fireEvent.click(screen.getByRole('checkbox', { name: /Erwartung 2/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Erwartung 3/ }))
    await waitFor(() => expect(textarea().value).toContain(`Rückmeldungen: ${C2}, ${C3}.`))
    fireEvent.click(screen.getByRole('checkbox', { name: /Erwartung 2/ }))
    await waitFor(() => expect(textarea().value).toContain(`Rückmeldungen: ${C3}.`))
  })

  it('uebernimmt nur UUIDs aus ?cases', async () => {
    renderPage(`?cases=${C1},kaputt,${C1.toUpperCase()},<script>`)
    await screen.findByTestId('prepare-group-triaged')
    await waitFor(() => expect(textarea().value).toContain(`Rückmeldungen: ${C1}.`))
    expect(screen.getByRole('checkbox', { name: /Erwartung 1/ })).toBeChecked()
  })

  it('zeigt ab vier Rückmeldungen einen Hinweis, verbietet aber nichts', async () => {
    renderPage(`?cases=${C1},${C2},${C3}`)
    await screen.findByTestId('prepare-group-triaged')
    expect(screen.queryByTestId('prepare-too-many')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('checkbox', { name: /Erwartung 4/ }))
    const hint = await screen.findByTestId('prepare-too-many')
    expect(hint).toHaveAttribute('role', 'status')
    expect(screen.getByRole('checkbox', { name: /Erwartung 4/ })).toBeChecked()
  })

  it('uebernimmt keine fremden IDs aus ?cases in Startsatz, Leiste und Hinweis', async () => {
    viewport.mobile = true
    // Vier IDs im Link, aber nur C1 hat der Server geliefert: kein Hinweis „ab vier“.
    renderPage(`?cases=${C1},${FOREIGN},${FOREIGN_2},${FOREIGN_3}`)
    await screen.findByTestId('prepare-group-triaged')
    await waitFor(() => expect(textarea().value).toContain(`Rückmeldungen: ${C1}.`))
    expect(textarea().value).not.toContain(FOREIGN)
    expect(
      within(screen.getByTestId('prepare-sticky')).getByRole('button', {
        name: 'Startsatz kopieren (1 Rückmeldung)',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('prepare-too-many')).not.toBeInTheDocument()
    expect(screen.getByTestId('prepare-unresolved')).toHaveTextContent(
      '3 Rückmeldungen aus dem Link sind hier nicht auswählbar',
    )
    // Keine Klaerung je ID (kein N+1): genau die eine Listen-Seite.
    expect(api.listCases).toHaveBeenCalledTimes(1)
  })

  it('zaehlt nur Eintraege dieses Agenten mit auswaehlbarem Status', async () => {
    api.listCases.mockResolvedValue({
      items: [
        ...firstPage,
        caseRead(FOREIGN, { agent_id: 'other-agent', status: 'open' }),
        caseRead(FOREIGN_2, { status: 'in_progress' }),
      ],
      next_cursor: null,
    })
    renderPage(`?cases=${FOREIGN},${FOREIGN_2},${C2}`)
    await screen.findByTestId('prepare-group-triaged')
    await waitFor(() => expect(textarea().value).toContain(`Rückmeldungen: ${C2}.`))
    expect(textarea().value).not.toContain(FOREIGN)
    expect(textarea().value).not.toContain(FOREIGN_2)
  })

  it('entfernt unbekannte IDs beim naechsten Toggle aus der URL', async () => {
    renderPage(`?cases=${FOREIGN},${C1}`)
    await screen.findByTestId('prepare-group-triaged')
    fireEvent.click(screen.getByRole('checkbox', { name: /Erwartung 2/ }))
    await waitFor(() => expect(textarea().value).toContain(`Rückmeldungen: ${C1}, ${C2}.`))
    expect(screen.queryByTestId('prepare-unresolved')).not.toBeInTheDocument()
  })

  it('macht eine vorbelegte ID gueltig, sobald sie per „Weitere laden“ kommt', async () => {
    api.listCases.mockResolvedValueOnce({ items: firstPage, next_cursor: 'cur-2' })
    api.listCases.mockResolvedValueOnce({
      items: [caseRead(C5, { status: 'open' })],
      next_cursor: null,
    })
    renderPage(`?cases=${C5}`)
    await screen.findByTestId('prepare-group-triaged')
    expect(textarea().value).not.toContain(C5)
    expect(screen.getByTestId('prepare-unresolved')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('prepare-load-more'))
    await waitFor(() => expect(textarea().value).toContain(`Rückmeldungen: ${C5}.`))
    expect(screen.getByRole('checkbox', { name: /Erwartung 5/ })).toBeChecked()
    expect(screen.queryByTestId('prepare-unresolved')).not.toBeInTheDocument()
  })

  it('laedt weitere per Cursor und sperrt den Knopf waehrend des Ladens', async () => {
    api.listCases.mockResolvedValueOnce({ items: firstPage, next_cursor: 'cur-2' })
    let resolveMore: (value: unknown) => void = () => undefined
    api.listCases.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveMore = resolve
        }),
    )
    renderPage()
    const more = await screen.findByTestId('prepare-load-more')
    fireEvent.click(more)
    await waitFor(() => expect(more).toBeDisabled())
    fireEvent.click(more)
    expect(api.listCases).toHaveBeenCalledTimes(2)
    expect(api.listCases).toHaveBeenLastCalledWith(
      { agent_id: AGENT_ID, status: ['triaged', 'open', 'reopened'] },
      { cursor: 'cur-2', limit: 20 },
    )
    resolveMore({ items: [caseRead(C5, { status: 'open' })], next_cursor: null })
    expect(await screen.findByRole('checkbox', { name: /Erwartung 5/ })).toBeInTheDocument()
    expect(screen.queryByTestId('prepare-load-more')).not.toBeInTheDocument()
  })

  it('nennt den leeren Zustand mit Agent-Namen', async () => {
    api.listCases.mockResolvedValue({ items: [], next_cursor: null })
    renderPage()
    expect(await screen.findByTestId('prepare-no-cases')).toHaveTextContent(
      'Für coder ist gerade keine Rückmeldung offen.',
    )
  })
})

describe('② Lage', () => {
  it('laedt die Lage mit genau einem Request und nichts je Element nach', async () => {
    renderPage()
    await screen.findByTestId('situation')
    expect(api.getDossier).toHaveBeenCalledTimes(1)
    expect(api.getDossier).toHaveBeenCalledWith(AGENT_ID)
    expect(api.getAgent).toHaveBeenCalledTimes(1)
  })

  it('zeigt Zaehler vom Server, nicht aus der Auswahl-Liste', async () => {
    renderPage()
    await screen.findByTestId('situation')
    expect(screen.getByTestId('situation-total')).toHaveTextContent('13')
    expect(within(screen.getByTestId('situation-count-open')).getByText('7')).toBeInTheDocument()
    expect(
      within(screen.getByTestId('situation-count-in_progress')).getByText('3'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('situation-count-open')).getByRole('link', { name: 'Offen' }),
    ).toHaveAttribute('href', `/w/ws-1/feedback?tab=cases&agent=${AGENT_ID}&status=open`)
  })

  it('rechnet nur „je 100“ und zeigt unter der Mindestnutzung „zu wenig Nutzung“', async () => {
    renderPage()
    const table = await screen.findByTestId('situation-rate-table')
    const values = within(table)
      .getAllByTestId('rate-value')
      .map((cell) => cell.textContent)
    expect(values).toEqual(['1,5', 'zu wenig Nutzung'])
    expect(within(table).getByText('v3 (aktiv)')).toBeInTheDocument()
    expect(within(table).getByText('Veraltet 2')).toBeInTheDocument()
  })

  it('zeigt Zugriffe als Label-Wert-Paare', async () => {
    renderPage()
    const access = await screen.findByTestId('situation-access')
    expect(within(access).getByText('memory · read · normal')).toBeInTheDocument()
    expect(within(access).getByText(/42 Einträge, 5 Inhalte/)).toBeInTheDocument()
  })

  it('zeigt hoechstens fuenf fruehere Aenderungen mit Link ins Sheet', async () => {
    renderPage()
    const measures = await screen.findAllByTestId('situation-measure')
    expect(measures).toHaveLength(5)
    expect(within(measures[0]).getByRole('link')).toHaveAttribute(
      'href',
      `/w/ws-1/agents/${AGENT_ID}/reviews/s0?change=m0`,
    )
    expect(within(measures[0]).getByRole('link')).toHaveTextContent('Playbook „Code-Task-Flow“')
    expect(screen.getByTestId('situation-all-reviews')).toHaveTextContent('Alle Reviews mit coder')
    // Freitext der Aenderung bleibt draussen.
    expect(screen.queryByText(SECRET)).not.toBeInTheDocument()
  })

  it('zeigt „Keine Daten“ fuer leere Karten', async () => {
    api.getDossier.mockResolvedValue(
      dossier({
        open_cases: { counts: {}, total: 0, items: [] },
        elements: [],
        elements_total: 0,
        access: { since: '2026-09-14T00:00:00Z', window_days: 30, total: 0, rows: [] },
        measures: [],
        measures_total: 0,
      }),
    )
    renderPage()
    await screen.findByTestId('situation')
    expect(screen.getAllByTestId('situation-no-data')).toHaveLength(4)
  })

  it('haelt ① und ③ bedienbar, wenn die Lage fehlschlaegt, und laedt erneut', async () => {
    api.getDossier.mockRejectedValueOnce(new Error('boom'))
    renderPage()
    const error = await screen.findByTestId('situation-error')
    expect(within(error).getByText('Die Lage konnte nicht geladen werden.')).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox').length).toBeGreaterThan(0)
    expect(textarea()).toBeInTheDocument()
    fireEvent.click(within(error).getByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByTestId('situation')).toBeInTheDocument()
    expect(api.getDossier).toHaveBeenCalledTimes(2)
  })
})

describe('③ Startsatz', () => {
  it('enthaelt nur Agent, ID, UUIDs und Werkzeugnamen', async () => {
    renderPage(`?cases=${C2}`)
    await screen.findByTestId('situation')
    const value = textarea().value
    expect(value).toBe(
      `Führe mit mir ein Review zu Agent coder (${AGENT_ID}). Lade die Lage mit get_dossier, moderiere, entscheide nichts selbst und reiche am Ende das Ergebnis mit submit_session_protocol ein. Rückmeldungen: ${C2}.`,
    )
    expect(value).not.toContain(SECRET)
    expect(value).not.toContain('Erwartung')
  })

  it('kopiert mit brand-Knopf und zeigt danach den Rueckweg', async () => {
    renderPage()
    await screen.findByTestId('situation')
    const button = within(screen.getByTestId('prepare-copy')).getByRole('button', {
      name: 'Kopieren',
    })
    expect(button.className).toContain('bg-brand')
    expect(screen.queryByTestId('prepare-after-copy')).not.toBeInTheDocument()
    fireEvent.click(button)
    const after = await screen.findByTestId('prepare-after-copy')
    expect(copySpy).toHaveBeenCalledWith(textarea().value)
    expect(notifySuccess).toHaveBeenCalledWith('Kopiert.')
    expect(after).toHaveTextContent('Das Ergebnis erscheint unter coder → Weiterentwicklung.')
    expect(within(after).getByRole('link')).toHaveAttribute(
      'href',
      `/w/ws-1/agents/${AGENT_ID}?tab=evolution`,
    )
  })

  it('zeigt keinen Rueckweg, wenn das Kopieren scheitert', async () => {
    copySpy.mockRejectedValue(new Error('denied'))
    renderPage()
    await screen.findByTestId('situation')
    fireEvent.click(
      within(screen.getByTestId('prepare-copy')).getByRole('button', { name: 'Kopieren' }),
    )
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith('denied'))
    expect(screen.queryByTestId('prepare-after-copy')).not.toBeInTheDocument()
  })
})

describe('390 px', () => {
  beforeEach(() => {
    viewport.mobile = true
  })

  it('zeigt die Lage als Akkordeon, „Offene Rückmeldungen“ offen', async () => {
    renderPage()
    await screen.findByTestId('situation')
    expect(screen.getByTestId('situation-open-cases').tagName).toBe('DETAILS')
    expect(screen.getByTestId('situation-open-cases')).toHaveAttribute('open')
    expect(screen.getByTestId('situation-rates')).not.toHaveAttribute('open')
  })

  it('fixiert „Startsatz kopieren“ mit Anzahl und setzt scroll-padding', async () => {
    const { unmount } = renderPage(`?cases=${C1},${C2}`)
    const sticky = await screen.findByTestId('prepare-sticky')
    const button = within(sticky).getByRole('button', {
      name: 'Startsatz kopieren (2 Rückmeldungen)',
    })
    expect(document.documentElement.style.scrollPaddingBottom).not.toBe('')
    fireEvent.click(button)
    await screen.findByTestId('prepare-after-copy')
    expect(copySpy).toHaveBeenCalledWith(textarea().value)
    unmount()
    expect(document.documentElement.style.scrollPaddingBottom).toBe('')
  })

  it('hat ab md keine fixierte Leiste', async () => {
    viewport.mobile = false
    renderPage()
    await screen.findByTestId('situation')
    expect(screen.queryByTestId('prepare-sticky')).not.toBeInTheDocument()
  })
})

describe('a11y', () => {
  it('ist ohne axe-Verstoss (Desktop)', async () => {
    const { container } = renderPage(`?cases=${C1}`)
    await screen.findByTestId('situation')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('ist ohne axe-Verstoss (390 px)', async () => {
    viewport.mobile = true
    const { container } = renderPage()
    await screen.findByTestId('situation')
    expect(await axe(container)).toHaveNoViolations()
  })
})
