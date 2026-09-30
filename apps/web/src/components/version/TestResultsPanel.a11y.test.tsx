import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  Me,
  TestCaseRead,
  TestReport,
  TestReportEntry,
  TestRunRead,
  VersionDiff,
} from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'
import { axe } from '@/test/a11y'

import { TestResultsPanel } from './TestResultsPanel'
import { VersionHistory } from './VersionHistory'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

let role: string | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }
const WS = '/v1/workspaces/ws-1'
const VERSION_ID = '11111111-2222-3333-4444-555555555555'
const REPORT_PATH = `${WS}/versions/playbook/${VERSION_ID}/test-report`

function testCase(overrides: Partial<TestCaseRead> = {}): TestCaseRead {
  return {
    id: 'c1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    entity_type: 'playbook',
    entity_id: 'p1',
    title: 'Push nach Fix',
    input: 'Fix den Test und pushe.',
    expected_behavior: 'Führt Tests lokal aus, bevor gepusht wird.',
    check_kind: 'must_contain',
    check_pattern: 'pytest',
    origin_case_id: null,
    origin_measure_id: null,
    status: 'active',
    supersedes_id: null,
    created_by_kind: 'human',
    created_by: 'u1',
    created_at: '2026-09-28T10:00:00Z',
    ...overrides,
  }
}

function run(overrides: Partial<TestRunRead> = {}): TestRunRead {
  return {
    id: 'r1',
    workspace_id: 'ws-1',
    test_case_id: 'c1',
    subject_entity_type: 'playbook',
    subject_version_id: VERSION_ID,
    runs_total: 3,
    runs_passed: 3,
    verdict: 'pass',
    output_excerpt: 'Ich fuehre pytest aus und pushe dann.',
    attestation: 'client_self_report',
    model_provider: 'anthropic',
    model_name: 'claude',
    reported_by_agent_id: 'a1',
    reported_by_user_id: null,
    created_at: '2026-09-30T09:00:00Z',
    ...overrides,
  }
}

function entry(
  state: TestReportEntry['state'],
  caseOverrides: Partial<TestCaseRead> = {},
  result: TestRunRead | null = null,
  direct = true,
): TestReportEntry {
  return { test_case: testCase(caseOverrides), direct, state, result }
}

function report(entries: TestReportEntry[], overrides: Partial<TestReport> = {}): TestReport {
  const count = (state: TestReportEntry['state']) => entries.filter((e) => e.state === state).length
  return {
    entity_type: 'playbook',
    entity_id: 'p1',
    version_id: VERSION_ID,
    affected_agent_count: 2,
    scope_note: null,
    counts: {
      total: entries.length,
      passed: count('pass'),
      failed: count('fail'),
      error: count('error'),
      missing: count('missing'),
    },
    agents: [
      { agent_id: 'a1', agent_name: 'coder', via: ['direct', 'persona_playbook'], entries },
      { agent_id: 'a2', agent_name: 'reviewer', via: ['playbook_composite'], entries: [] },
    ],
    ...overrides,
  }
}

type Handler = (url: URL, init?: RequestInit) => Response | Promise<Response>

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    const key = `${init?.method ?? 'GET'} ${url.pathname}`
    const handler = handlers[key]
    if (!handler) throw new Error(`Unmocked ${key}`)
    return handler(url, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function wrap(element: React.ReactNode) {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/playbooks/p1']}>
          <Routes>
            <Route path="/w/:workspaceId/playbooks/:id" element={element} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

function renderPanel(props: Partial<Parameters<typeof TestResultsPanel>[0]> = {}) {
  return wrap(
    <TestResultsPanel
      entityType="playbook"
      versionId={VERSION_ID}
      version={7}
      testCasesSearch="?tab=tests"
      {...props}
    />,
  )
}

beforeEach(() => {
  role = 'editor'
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('TestResultsPanel', () => {
  it('laedt den Bericht der Version, zeigt betroffene Agenten vorn und sortiert Probleme nach oben', async () => {
    stubFetch({
      [`GET ${REPORT_PATH}`]: () =>
        json(
          report([
            entry('pass', { id: 'c1', title: 'A bestanden' }, run()),
            entry('missing', { id: 'c2', title: 'B fehlt' }),
            entry('fail', { id: 'c3', title: 'C rot' }, run({ runs_passed: 1, verdict: 'fail' })),
          ]),
        ),
    })
    renderPanel()

    const rows = await screen.findAllByTestId('test-result-row')
    expect(rows.map((row) => row.dataset.kind)).toEqual(['fail', 'missing', 'pass'])
    // Wort sichtbar (Farbe nie allein), Laufzahl daneben: 1/3 gilt nicht als bestanden.
    expect(rows[0].textContent).toContain('Nicht bestanden · 1/3')
    expect(rows[1].textContent).toContain('Kein Ergebnis')
    expect(rows[2].textContent).toContain('Bestanden · 3/3')
    expect(screen.getByText('Betrifft 2 Agenten.')).toBeInTheDocument()
    const summary = screen.getByTestId('test-results-summary')
    expect(summary).toHaveAttribute('aria-live', 'polite')
    expect(summary.textContent).toBe('1 bestanden · 1 nicht bestanden · 1 ohne Ergebnis')
    // Gruppiert nach Agent mit `via`; ein betroffener Agent ohne Fall bleibt sichtbar.
    expect(screen.getByText('Betroffen über: direkt gebunden, Playbook der Persona')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Für Agent reviewer' })).toHaveTextContent(
      'Für diesen Agenten gibt es keine Prüffälle.',
    )
    expect(screen.getByText(/Vom Client gemeldet – Who2Be hat die Prüffälle nicht selbst/)).toBeInTheDocument()
  })

  it('klappt Eingabe, Erwartung, Ausgabe und die Herkunft des Ergebnisses auf', async () => {
    stubFetch({
      [`GET ${REPORT_PATH}`]: () => json(report([entry('pass', {}, run())])),
    })
    renderPanel()

    const toggle = within(await screen.findByTestId('test-result-row')).getByRole('button')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Fix den Test und pushe.')).toBeInTheDocument()
    expect(screen.getByText('Ich fuehre pytest aus und pushe dann.')).toBeInTheDocument()
    expect(screen.getByText(/^Selbstauskunft des Clients · anthropic \/ claude · /)).toBeInTheDocument()
    // Deterministischer Fall: keine Bewertungsknoepfe.
    expect(screen.queryByRole('group', { name: /bewerten/ })).toBeNull()
  })

  it('zeigt eine menschliche Bewertung mit Namen', async () => {
    stubFetch({
      [`GET ${REPORT_PATH}`]: () =>
        json(
          report([
            entry(
              'fail',
              { check_kind: 'human_rule', check_pattern: null },
              run({
                runs_total: 1,
                runs_passed: 0,
                verdict: 'fail',
                attestation: 'human_rating',
                reported_by_agent_id: null,
                reported_by_user_id: 'u9',
              }),
            ),
          ]),
        ),
      [`GET ${WS}/members`]: () =>
        json([{ user_id: 'u9', email: 'ada@example.org', role: 'editor', joined_at: '2026-01-01T00:00:00Z' }]),
    })
    renderPanel()

    const row = await screen.findByTestId('test-result-row')
    expect(row.dataset.kind).toBe('fail')
    fireEvent.click(within(row).getByRole('button'))
    expect(await screen.findByText(/^Bewertung durch ada@example\.org · /)).toBeInTheDocument()
  })

  it('offene human_rule-Faelle bewertet ein Mensch per POST test-runs ohne attestation', async () => {
    let reportCalls = 0
    const posted: unknown[] = []
    stubFetch({
      [`GET ${REPORT_PATH}`]: () => {
        reportCalls += 1
        return json(
          report([
            entry(
              'error',
              { check_kind: 'human_rule', check_pattern: null },
              run({ runs_total: 1, runs_passed: 0, verdict: 'error', output_excerpt: 'Antwort des Agenten' }),
            ),
          ]),
        )
      },
      [`POST ${WS}/test-runs`]: (_url, init) => {
        posted.push(JSON.parse(String(init?.body)))
        return json([], 201)
      },
    })
    renderPanel()

    const row = await screen.findByTestId('test-result-row')
    // Selbstauskunft mit verdict=error ist bei human_rule kein Laufzeitfehler.
    expect(row.dataset.kind).toBe('awaiting')
    expect(row.textContent).toContain('Wartet auf Bewertung')
    expect(screen.getByTestId('test-results-summary').textContent).toBe(
      '0 bestanden · 1 warten auf Bewertung',
    )
    fireEvent.click(within(row).getByRole('button'))
    const group = screen.getByRole('group', { name: '„Push nach Fix“ bewerten' })
    fireEvent.click(within(group).getByRole('button', { name: 'Bestanden' }))

    await waitFor(() => expect(reportCalls).toBe(2))
    expect(posted).toEqual([
      {
        subject_entity_type: 'playbook',
        subject_version_id: VERSION_ID,
        results: [
          {
            test_case_id: 'c1',
            runs_total: 1,
            runs_passed: 1,
            verdict: 'pass',
            output_excerpt: 'Antwort des Agenten',
          },
        ],
      },
    ])
    expect(notify.success).toHaveBeenCalledWith('Als bestanden bewertet.')
    expect(screen.getByRole('heading', { name: 'Prüffälle' })).toHaveFocus()
  })

  it('viewer bekommt keine Bewertungsknoepfe und keinen Request', () => {
    role = 'viewer'
    const fetchMock = stubFetch({})
    renderPanel()
    expect(screen.getByText('Dafür fehlen dir die Rechte (ab Rolle Editor).')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('Leerzustand ohne Prueffaelle mit Link zum Tab', async () => {
    stubFetch({
      [`GET ${REPORT_PATH}`]: () =>
        json(report([], { affected_agent_count: 0, agents: [] })),
    })
    renderPanel()

    expect(
      await screen.findByText(/Für dieses Element gibt es keine Prüffälle\. Ob die Änderung/),
    ).toBeInTheDocument()
    expect(screen.getByText('Heute nutzt kein Agent dieses Element.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Prüffall anlegen' })).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks/p1?tab=tests',
    )
  })

  it('ohne jeden Lauf zeigt es den Startsatz mit Element-ID und Version', async () => {
    stubFetch({
      [`GET ${REPORT_PATH}`]: () => json(report([entry('missing')])),
    })
    renderPanel()

    expect(
      await screen.findByText('Noch keine Ergebnisse. Starte den Prüflauf im Client:'),
    ).toBeInTheDocument()
    const prompt = screen.getByText(/submit_test_results/)
    expect(prompt.textContent).toContain('Playbook p1, Version 7')
    expect(prompt.textContent).toContain(`subject_version_id ${VERSION_ID}`)
    expect(screen.getByRole('button', { name: 'Startsatz kopieren' })).toBeInTheDocument()
  })

  it('External Tool: Hinweis auf fehlenden Rueckwaerts-Index', async () => {
    stubFetch({
      [`GET ${WS}/versions/external_tool/${VERSION_ID}/test-report`]: () =>
        json(
          report([entry('pass', {}, run())], {
            entity_type: 'external_tool',
            scope_note: 'no_reference_index',
            affected_agent_count: 0,
          }),
        ),
    })
    renderPanel({ entityType: 'external_tool' })

    expect(
      await screen.findByText(/Externe Tools haben keine gespeicherten Verknüpfungen/),
    ).toBeInTheDocument()
  })

  it('klappt bestandene ab fuenf ein', async () => {
    const passed = Array.from({ length: 5 }, (_, i) =>
      entry('pass', { id: `p${i}`, title: `Grün ${i}` }, run({ test_case_id: `p${i}` })),
    )
    stubFetch({
      [`GET ${REPORT_PATH}`]: () =>
        json(report([...passed, entry('fail', { id: 'x', title: 'Rot' }, run({ runs_passed: 0, verdict: 'fail' }))])),
    })
    renderPanel()

    await screen.findAllByTestId('test-result-row')
    expect(screen.getAllByTestId('test-result-row')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: '5 weitere bestanden' }))
    expect(screen.getAllByTestId('test-result-row')).toHaveLength(6)
  })

  it('Fehler: eigener Text und Erneut versuchen', async () => {
    let calls = 0
    stubFetch({
      [`GET ${REPORT_PATH}`]: () => {
        calls += 1
        return calls === 1 ? json({ detail: 'Kaputt' }, 500) : json(report([entry('pass', {}, run())]))
      },
    })
    renderPanel()

    expect(await screen.findByText('Ergebnisse konnten nicht geladen werden')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByTestId('test-result-row')).toBeInTheDocument()
    expect(calls).toBe(2)
  })

  it('403 zeigt den Rechte-Text', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json({ detail: 'nope' }, 403) })
    renderPanel()
    expect(
      await screen.findByText('Dafür fehlen dir die Rechte (ab Rolle Editor).'),
    ).toBeInTheDocument()
  })

  it('hat keine axe-Verstoesse (aufgeklappt, mit Bewertung)', async () => {
    stubFetch({
      [`GET ${REPORT_PATH}`]: () =>
        json(
          report([
            entry('missing', { id: 'h', title: 'Mensch', check_kind: 'human_rule', check_pattern: null }),
            entry('fail', { id: 'f', title: 'Rot' }, run({ runs_passed: 1, verdict: 'fail' })),
          ]),
        ),
    })
    const { container } = renderPanel()
    const rows = await screen.findAllByTestId('test-result-row')
    for (const row of rows) fireEvent.click(within(row).getAllByRole('button')[0])
    expect(await axe(container)).toHaveNoViolations()
  })
})

describe('VersionHistory mit Pruefbericht', () => {
  const diff: VersionDiff = {
    version: 7,
    against: 'active',
    against_version: 6,
    identical: false,
    changes: [{ path: 'description', op: 'changed', before: 'alt', after: 'neu' }],
  }

  function renderHistory(withReport: boolean) {
    return wrap(
      <VersionHistory
        versions={[{ version: 7, id: VERSION_ID, status: 'review', created_at: '2026-09-30T08:00:00Z' }]}
        canEdit
        onRestore={vi.fn()}
        loadDiff={vi.fn().mockResolvedValue(diff)}
        loadProvenance={vi.fn().mockResolvedValue([])}
        testReportEntityType={withReport ? 'playbook' : undefined}
        testCasesSearch="?tab=tests"
      />,
    )
  }

  it('zeigt die Pruefall-Ergebnisse neben dem Diff', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json(report([entry('pass', {}, run())])) })
    renderHistory(true)

    fireEvent.click(screen.getByRole('button', { name: 'Diff' }))
    expect(await screen.findByTestId('test-results-panel')).toBeInTheDocument()
    expect(await screen.findByText('neu')).toBeInTheDocument()
    expect(await screen.findByTestId('test-result-row')).toBeInTheDocument()
  })

  it('ohne testReportEntityType bleibt es beim Diff allein', async () => {
    const fetchMock = stubFetch({})
    renderHistory(false)

    fireEvent.click(screen.getByRole('button', { name: 'Diff' }))
    expect(await screen.findByText('neu')).toBeInTheDocument()
    expect(screen.queryByTestId('test-results-panel')).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('ein Fehler im Bericht blockiert den Diff nicht', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json({ detail: 'Kaputt' }, 500) })
    renderHistory(true)

    fireEvent.click(screen.getByRole('button', { name: 'Diff' }))
    expect(await screen.findByText('Ergebnisse konnten nicht geladen werden')).toBeInTheDocument()
    expect(screen.getByText('neu')).toBeInTheDocument()
  })
})
