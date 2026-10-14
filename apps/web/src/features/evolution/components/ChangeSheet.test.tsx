import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type {
  CaseRead,
  FollowUpReport,
  MeasureEvent,
  MeasureRead,
  MeasureState,
  SessionRead,
  TestCaseRead,
} from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { ChangeSheet, type ChangeSheetData } from './ChangeSheet'

const api = vi.hoisted(() => ({
  getFollowUp: vi.fn(),
  listPersonaVersions: vi.fn(),
  listPlaybookVersions: vi.fn(),
  listResourceVersions: vi.fn(),
  listExternalToolVersions: vi.fn(),
  listSystemPromptTemplateVersions: vi.fn(),
}))
vi.mock('@/api/useApi', () => ({ useApi: () => api }))

const LONG = 'Ein-sehr-langer-Elementname-ohne-Leerzeichen-'.repeat(6)
const LONG_URL = `https://example.org/${'pfad/'.repeat(40)}ende`

function ev(
  id: string,
  event: MeasureEvent['event'],
  created_at: string,
  extra: Partial<MeasureEvent> = {},
): MeasureEvent {
  return {
    id,
    measure_id: 'm1',
    event,
    actor_kind: 'agent',
    actor_id: null,
    version_entity_type: null,
    version_id: null,
    verdict: null,
    metrics: null,
    note: null,
    created_at,
    ...extra,
  }
}

const linked = ev('e1', 'draft_linked', '2026-09-26T09:00:00Z', {
  actor_kind: 'agent',
  actor_id: 'a2',
  version_entity_type: 'playbook',
  version_id: 'v4',
})
const activated = ev('e2', 'activated', '2026-09-28T09:00:00Z', {
  actor_kind: 'system',
  version_entity_type: 'playbook',
  version_id: 'v4',
})

function measure(overrides: Partial<MeasureRead> = {}): MeasureRead {
  return {
    id: 'm1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    session_id: 's1',
    case_ids: ['c1'],
    target: 'playbook',
    entity_id: 'pb1',
    change_summary: 'Schritt 4 verlangt Tests.',
    test_case_id: 't1',
    success_criterion: 'Keine roten CI-Läufe.',
    counterposition: '<b>Zu streng</b>',
    follow_up_at: null,
    state: 'activated',
    events: [linked, activated],
    created_at: '2026-09-25T10:00:00Z',
    ...overrides,
  }
}

const session = {
  id: 's1',
  agent_id: 'a1',
  follow_up_at: '2026-10-27',
  created_at: '2026-09-25T10:00:00Z',
} as unknown as SessionRead

const testCase = {
  id: 't1',
  agent_id: 'a1',
  title: 'Push ohne Tests',
  status: 'active',
} as unknown as TestCaseRead

const caseRow = {
  id: 'c1',
  status: 'in_progress',
  expected_behavior: 'Tests vor dem Push lokal laufen lassen.',
} as unknown as CaseRead

function report(overrides: Partial<FollowUpReport> = {}): FollowUpReport {
  return {
    measure_id: 'm1',
    state: 'activated',
    follow_up_at: '2026-10-27',
    due: false,
    reviewable: true,
    before: {
      version_id: 'v3',
      version: 3,
      test_run: {
        runs_total: 10,
        runs_passed: 6,
        verdict: 'fail',
        attestation: 'human_rating',
        created_at: '2026-09-20T10:00:00Z',
      },
      uses: 120,
      cases: 9,
    },
    after: {
      version_id: 'v4',
      version: 4,
      test_run: {
        runs_total: 10,
        runs_passed: 9,
        verdict: 'pass',
        attestation: 'human_rating',
        created_at: '2026-10-01T10:00:00Z',
      },
      uses: 80,
      cases: 2,
    },
    recurrence: 0,
    min_uses: 30,
    insufficient: false,
    ...overrides,
  }
}

function data(overrides: Partial<ChangeSheetData> = {}): ChangeSheetData {
  return {
    measure: measure(),
    index: 1,
    session,
    agentName: 'coder',
    element: 'Playbook „Release“',
    testCase,
    cases: [caseRow],
    people: {
      agentById: new Map([
        ['a1', 'coder'],
        ['a2', 'reviewer'],
      ]),
      memberById: new Map([['u2', 'kim@example.org']]),
    },
    ...overrides,
  }
}

const onClose = vi.fn()
const onGone = vi.fn()

function renderSheet(value: ChangeSheetData | null = data()) {
  return renderInRoutes(
    <ChangeSheet data={value} onClose={onClose} onGone={onGone} fallbackFocus={() => null} />,
    { path: '/w/:workspaceId/agents/:agentId/reviews/:sessionId' , initialEntries: ['/w/ws-1/agents/a1/reviews/s1'] },
  )
}

function mockMobile(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-14T10:00:00'))
  api.getFollowUp.mockResolvedValue(report())
  api.listPlaybookVersions.mockResolvedValue([
    { id: 'v3', version: 3, status: 'inactive' },
    { id: 'v4', version: 4, status: 'active' },
  ])
})

afterEach(() => {
  vi.useRealTimers()
  Reflect.deleteProperty(window, 'matchMedia')
})

const STATE_WORDS: [MeasureState, string, MeasureEvent[]][] = [
  ['agreed', 'Vereinbart', []],
  ['draft_linked', 'Entwurf verknüpft', [linked]],
  ['activated', 'Aktiviert', [linked, activated]],
  ['follow_up_prepared', 'Kennzahlen bereit', [linked, activated]],
  ['effective', 'Hat gewirkt', [linked, activated]],
  ['ineffective', 'Hat nicht gewirkt', [linked, activated]],
  ['not_measurable', 'Nicht messbar', [linked, activated]],
  ['withdrawn', 'Zurückgezogen', [linked]],
]

describe('ChangeSheet', () => {
  it('zeigt Titel, Herkunft, Felder und Freitext als Text', async () => {
    renderSheet()
    const sheet = await screen.findByTestId('change-sheet')
    expect(within(sheet).getByTestId('change-title')).toHaveTextContent('Änderung M1 · Playbook „Release“')
    expect(sheet).toHaveTextContent('Aus dem Review mit coder vom 25.09.2026')
    const fields = within(sheet).getByTestId('change-fields')
    expect(fields).toHaveTextContent('Kleinste ÄnderungSchritt 4 verlangt Tests.')
    expect(fields).toHaveTextContent('ErfolgskriteriumKeine roten CI-Läufe.')
    // Freitext ist Text, kein HTML.
    expect(within(fields).getByText('<b>Zu streng</b>')).toBeInTheDocument()
    expect(fields.querySelector('b')).toBeNull()
    expect(within(sheet).getByTestId('change-target').querySelector('a')).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks/pb1',
    )
    expect(within(sheet).getByRole('link', { name: 'Push ohne Tests' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1?tab=tests',
    )
    expect(within(sheet).getByTestId('change-follow-up-at')).toHaveTextContent('27.10.2026')
    const cases = within(sheet).getByTestId('change-cases')
    expect(cases).toHaveTextContent('In Arbeit')
    expect(within(cases).getByRole('link')).toHaveAttribute('href', '/w/ws-1/feedback/cases/c1')
    // Entwurf: juengster draft_linked mit Version und Status.
    await waitFor(() =>
      expect(within(sheet).getByTestId('change-draft')).toHaveTextContent(
        'Playbook „Release“ v4 · aktiv seit 28.09.2026',
      ),
    )
    expect(within(sheet).getByTestId('change-draft')).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks/pb1?tab=versions',
    )
  })

  it.each(STATE_WORDS)('Zustand %s zeigt „%s“', async (state, word, events) => {
    renderSheet(data({ measure: measure({ state, events }) }))
    expect(await screen.findByTestId('change-state')).toHaveTextContent(word)
  })

  it.each([
    ['agreed', [] as MeasureEvent[]],
    ['draft_linked', [linked]],
    ['withdrawn', [linked]],
  ] as const)('vor Aktiviert (%s): kein Kennzahlen-Request, Hinweis statt Tabelle', async (state, events) => {
    renderSheet(data({ measure: measure({ state, events: [...events] }) }))
    expect(await screen.findByTestId('follow-up-not-yet')).toHaveTextContent(
      'Kennzahlen gibt es, sobald die verknüpfte Version aktiv ist.',
    )
    expect(api.getFollowUp).not.toHaveBeenCalled()
    expect(screen.queryByTestId('follow-up-figures')).toBeNull()
  })

  it.each(['activated', 'follow_up_prepared', 'effective', 'ineffective', 'not_measurable'] as const)(
    'ab Aktiviert (%s): genau ein Kennzahlen-Request',
    async (state) => {
      renderSheet(data({ measure: measure({ state }) }))
      await screen.findByTestId('follow-up-figures')
      expect(api.getFollowUp).toHaveBeenCalledTimes(1)
      expect(api.getFollowUp).toHaveBeenCalledWith('m1')
    },
  )

  it('zurückgezogen nach Aktivierung: Kennzahlen werden geladen', async () => {
    renderSheet(data({ measure: measure({ state: 'withdrawn', events: [linked, activated] }) }))
    await screen.findByTestId('follow-up-figures')
    expect(api.getFollowUp).toHaveBeenCalledTimes(1)
  })

  it('eine Quelle: der Server-Zustand gilt, auch wenn die Events etwas anderes nahelegen', async () => {
    // Server sagt „Vereinbart“, die Events enthalten ein `activated`: kein Request.
    const { unmount } = renderSheet(data({ measure: measure({ state: 'agreed' }) }))
    expect(await screen.findByTestId('change-state')).toHaveTextContent('Vereinbart')
    expect(screen.getByTestId('follow-up-not-yet')).toBeInTheDocument()
    expect(api.getFollowUp).not.toHaveBeenCalled()
    unmount()

    // Server sagt „Aktiviert“, die Events sind leer: Request und Wort „Aktiviert“.
    renderSheet(data({ measure: measure({ state: 'activated', events: [] }) }))
    expect(await screen.findByTestId('change-state')).toHaveTextContent('Aktiviert')
    await screen.findByTestId('follow-up-figures')
    expect(api.getFollowUp).toHaveBeenCalledTimes(1)
  })

  it('eine Quelle: Fällig-Pill folgt dem Server-Zustand, nicht den Events', async () => {
    renderSheet(
      data({
        measure: measure({ state: 'effective', follow_up_at: '2026-10-01', events: [linked, activated] }),
      }),
    )
    await screen.findByTestId('change-state')
    // Abgeschlossen laut Server: keine Fällig-Markierung.
    expect(screen.queryByTestId('measure-due')).toBeNull()
  })

  it('Tabelle: vorher/nachher, Raten mit einer Nachkommastelle, Richtung als Wort', async () => {
    renderSheet()
    const table = await screen.findByTestId('follow-up-table')
    expect(within(table).getByText('Kennzahlen vor und nach der Änderung')).toHaveClass('sr-only')
    expect(within(table).getByRole('columnheader', { name: 'vorher (v3)' })).toHaveAttribute('scope', 'col')
    expect(within(table).getByRole('columnheader', { name: 'nachher (v4)' })).toBeInTheDocument()
    const pass = within(table).getByTestId('figure-passRate')
    expect(within(pass).getByRole('rowheader')).toHaveTextContent('Prüffall bestanden')
    expect(pass).toHaveTextContent('6 von 10 Läufen')
    expect(pass).toHaveTextContent('9 von 10 Läufen höher')
    const rate = within(table).getByTestId('figure-caseRate')
    // 9/120*100 = 7,5; 2/80*100 = 2,5.
    expect(rate).toHaveTextContent('7,5 (120 Nutzungen)')
    expect(rate).toHaveTextContent('2,5 (80 Nutzungen) niedriger')
    expect(within(table).getByTestId('figure-recurrence')).toHaveTextContent('keine neuen Rückmeldungen')
    expect(screen.queryByTestId('follow-up-too-few')).toBeNull()
    // Keine Farbe als einziges Signal: das Wort steht ohne Farbklasse.
    for (const word of within(table).getAllByTestId('figure-direction')) {
      expect(word.className).not.toMatch(/(green|red|success|danger|destructive)/)
    }
  })

  it('Rate rundet auf eine Nachkommastelle', async () => {
    api.getFollowUp.mockResolvedValue(
      report({
        before: { ...report().before!, uses: 300, cases: 7 },
        after: { ...report().after!, uses: 300, cases: 7 },
      }),
    )
    renderSheet()
    const rate = await screen.findByTestId('figure-caseRate')
    // 7/300*100 = 2,333… → 2,3; gleiche Rate → „gleich“.
    expect(rate).toHaveTextContent('2,3 (300 Nutzungen) gleich')
  })

  it('insufficient: Hinweis „zu wenig Nutzung“ und keine Richtung bei der Rate', async () => {
    api.getFollowUp.mockResolvedValue(
      report({ insufficient: true, after: { ...report().after!, uses: 12, cases: 1 } }),
    )
    renderSheet()
    expect(await screen.findByTestId('follow-up-too-few')).toHaveTextContent(
      'Nur 12 Nutzungen seit Aktivierung – zu wenig für einen Vergleich.',
    )
    const rate = screen.getByTestId('figure-caseRate')
    expect(within(rate).queryByTestId('figure-direction')).toBeNull()
  })

  it('Selbstauskunft: Läufe „laut Client“ und Hinweis', async () => {
    const after = report().after!
    api.getFollowUp.mockResolvedValue(
      report({ after: { ...after, test_run: { ...after.test_run!, attestation: 'client_self_report' } } }),
    )
    renderSheet()
    const pass = await screen.findByTestId('figure-passRate')
    expect(pass).toHaveTextContent('9 von 10 Läufen (laut Client)')
    expect(screen.getByText('Prüffall-Ergebnisse vom Client gemeldet.')).toBeInTheDocument()
  })

  it('unter md: Kennzahlen als drei Karten mit sichtbaren Labels', async () => {
    mockMobile(true)
    renderSheet()
    const cards = await screen.findByTestId('follow-up-cards')
    expect(cards).toHaveClass('md:hidden')
    expect(screen.getByTestId('follow-up-table')).toHaveClass('hidden', 'md:table')
    const items = within(cards).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('Prüffall bestanden')
    expect(within(items[0]).getByText('vorher (v3)')).toBeInTheDocument()
    expect(within(items[0]).getByText('nachher (v4)')).toBeInTheDocument()
  })

  it('Sheet-Seite: rechts ab md, Bottom-Sheet in voller Höhe darunter', async () => {
    mockMobile(false)
    const { unmount } = renderSheet()
    const desktop = await screen.findByTestId('change-sheet')
    expect(desktop.className).toContain('sm:max-w-[40rem]')
    expect(desktop.className).toContain('right-0')
    unmount()
    mockMobile(true)
    renderSheet()
    const mobile = await screen.findByTestId('change-sheet')
    expect(mobile.className).toContain('bottom-0')
    expect(mobile.className).toContain('h-[100svh]')
  })

  it('Kennzahlen-Fehler: Rest bleibt stehen, erneuter Versuch lädt nach', async () => {
    api.getFollowUp.mockRejectedValueOnce(new Error('boom'))
    renderSheet()
    const alert = await screen.findByTestId('follow-up-error')
    expect(alert).toHaveTextContent('Die Kennzahlen konnten nicht geladen werden.')
    expect(screen.getByTestId('change-fields')).toBeInTheDocument()
    expect(screen.getByTestId('change-history')).toBeInTheDocument()
    expect(onGone).not.toHaveBeenCalled()
    fireEvent.click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))
    await screen.findByTestId('follow-up-figures')
    expect(api.getFollowUp).toHaveBeenCalledTimes(2)
  })

  it('measure_not_found beim Kennzahlen-Abruf: meldet „gibt es nicht (mehr)“', async () => {
    api.getFollowUp.mockRejectedValue(new ApiError(404, 'measure_not_found'))
    renderSheet()
    await waitFor(() => expect(onGone).toHaveBeenCalledTimes(1))
  })

  it('Prüffall zurückgezogen bzw. nicht verfügbar, ohne Fehlerbanner', async () => {
    const { unmount } = renderSheet(data({ testCase: { ...testCase, status: 'retired' } }))
    expect(await screen.findByTestId('change-test-case-retired')).toHaveTextContent('zurückgezogen')
    unmount()
    renderSheet(data({ testCase: null }))
    expect(await screen.findByTestId('change-test-case-unavailable')).toHaveTextContent(
      'Prüffall nicht verfügbar',
    )
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('Ziel ohne Versionen: Werkzeugrechte und Gedächtnis mit vorhandenen Wörtern', async () => {
    const { unmount } = renderSheet(
      data({ measure: measure({ target: 'tool_policy', entity_id: null, state: 'agreed', events: [] }) }),
    )
    const target = await screen.findByTestId('change-target')
    expect(target).toHaveTextContent('Werkzeugrechte')
    expect(within(target).getByRole('link')).toHaveAttribute('href', '/w/ws-1/agents/a1?tab=settings')
    expect(screen.getByTestId('change-draft-field')).toHaveTextContent('Noch kein Entwurf verknüpft')
    unmount()
    renderSheet(data({ measure: measure({ target: 'memory', entity_id: null, state: 'agreed', events: [] }) }))
    expect(await screen.findByTestId('change-target')).toHaveTextContent('Gedächtnis')
  })

  it('Verlauf: neueste zuerst, activatedNoCount, unbekanntes Ereignis, Akteur-Wörter', async () => {
    const unknown = { ...ev('e9', 'activated', '2026-10-05T09:00:00Z'), event: 'future_kind' } as unknown as MeasureEvent
    const reviewed = ev('e3', 'reviewed', '2026-10-03T09:00:00Z', {
      actor_kind: 'human',
      actor_id: 'u1',
      verdict: 'effective',
      note: 'Läuft.',
    })
    const byOther = ev('e4', 'follow_up_prepared', '2026-10-02T09:00:00Z', {
      actor_kind: 'human',
      actor_id: 'u2',
    })
    const counted = ev('e5', 'activated', '2026-09-29T09:00:00Z', {
      actor_kind: 'system',
      metrics: { count: 3 },
    })
    renderSheet(
      data({
        measure: measure({ state: 'effective', events: [linked, activated, counted, byOther, reviewed, unknown] }),
      }),
    )
    const items = await screen.findAllByTestId('change-history-item')
    await waitFor(() => expect(items[5]).toHaveTextContent('Entwurf verknüpft: Playbook „Release“ v4'))
    expect(items.map((item) => item.querySelector('p')?.textContent)).toEqual([
      'Ereignis',
      'Eingestuft: Hat gewirkt',
      'Kennzahlen bereitgestellt',
      'Version aktiv geworden, 3 Rückmeldungen geändert',
      'Version aktiv geworden',
      'Entwurf verknüpft: Playbook „Release“ v4',
    ])
    expect(items[1]).toHaveTextContent('Läuft.')
    expect(items[1]).toHaveTextContent('03.10.2026 · von dir')
    expect(items[2]).toHaveTextContent('von kim@example.org')
    expect(items[4]).toHaveTextContent('Automatisch')
    expect(items[5]).toHaveTextContent('von reviewer')
  })

  it('Überlauf: Sheet, Felder und Links brechen lange Namen und URLs um', async () => {
    renderSheet(
      data({
        element: `Playbook „${LONG}“`,
        measure: measure({ change_summary: LONG_URL, success_criterion: LONG }),
        testCase: { ...testCase, title: LONG },
      }),
    )
    const sheet = await screen.findByTestId('change-sheet')
    // Das scrollende Panel schneidet horizontal ab, die Inhalte brechen um
    // (echte Breiten: measure.json der Abgabe-Fotos, 390/1280).
    expect(sheet).toHaveClass('overflow-x-hidden', 'overflow-y-auto')
    expect(screen.getByTestId('change-title')).toHaveClass('break-words')
    for (const dd of screen.getByTestId('change-fields').querySelectorAll('dd')) {
      expect(dd).toHaveClass('min-w-0', 'break-words')
    }
    expect(screen.getByRole('link', { name: LONG })).toHaveClass('wrap-anywhere')
    const table = await screen.findByTestId('follow-up-table')
    expect(table).toHaveClass('table-fixed', 'w-full')
  })

  it('geschlossen: kein Sheet im DOM', () => {
    renderSheet(null)
    expect(screen.queryByTestId('change-sheet')).toBeNull()
  })

  it('a11y: vor Aktiviert ohne Violations', async () => {
    renderSheet(data({ measure: measure({ state: 'agreed', events: [] }) }))
    await screen.findByTestId('follow-up-not-yet')
    expect(await axe(screen.getByTestId('change-sheet'))).toHaveNoViolations()
  })

  it('a11y: mit Kennzahlen ohne Violations', async () => {
    renderSheet()
    await screen.findByTestId('follow-up-table')
    await screen.findByTestId('change-draft')
    expect(await axe(screen.getByTestId('change-sheet'))).toHaveNoViolations()
  })

  it('a11y: zu wenig Nutzung ohne Violations', async () => {
    api.getFollowUp.mockResolvedValue(report({ insufficient: true }))
    renderSheet()
    await screen.findByTestId('follow-up-too-few')
    expect(await axe(screen.getByTestId('change-sheet'))).toHaveNoViolations()
  })

  it('a11y: Kennzahlen-Fehler ohne Violations', async () => {
    api.getFollowUp.mockRejectedValue(new Error('boom'))
    renderSheet()
    await screen.findByTestId('follow-up-error')
    expect(await axe(screen.getByTestId('change-sheet'))).toHaveNoViolations()
  })

  it('a11y: abgeschlossen (Hat gewirkt) ohne Violations', async () => {
    renderSheet(data({ measure: measure({ state: 'effective' }) }))
    await screen.findByTestId('follow-up-table')
    expect(await axe(screen.getByTestId('change-sheet'))).toHaveNoViolations()
  })

  it('a11y: Bottom-Sheet mit Karten ohne Violations', async () => {
    mockMobile(true)
    renderSheet()
    await screen.findByTestId('follow-up-cards')
    expect(await axe(screen.getByTestId('change-sheet'))).toHaveNoViolations()
  })
})
