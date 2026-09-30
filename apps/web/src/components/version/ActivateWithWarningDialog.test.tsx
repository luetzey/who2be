import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  Me,
  TestCaseRead,
  TestReport,
  TestReportEntry,
  TestRunRead,
  VersionStatus,
  WorkspaceRole,
} from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { SystemPromptStatusActionBar } from '@/features/system-prompts/components/SystemPromptStatusActionBar'
import i18n from '@/i18n'
import { notify } from '@/lib/feedback'
import { axe } from '@/test/a11y'

import { StatusActionBar } from './StatusActionBar'

// Aktivieren mit Warnung (Lernschleife B5, Spec S11, ADR-0053 6.3). Die Tests
// laufen ueber einen `fetch`-Stub durch die echte Kette Leiste -> Api-Client,
// damit der Request-Body selbst geprueft wird (beide Felder des Vertrags).

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const WS = '/v1/workspaces/ws-1'
const VERSION_ID = '11111111-2222-3333-4444-555555555555'
const REPORT_PATH = `${WS}/versions/system_prompt_template/${VERSION_ID}/test-report`
const PERSONA_REPORT_PATH = `${WS}/versions/persona/${VERSION_ID}/test-report`
const SP_TRANSITION = `${WS}/system-prompts/sp1/versions/3/transition`

function buildMe(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'o1',
        name: 'Org',
        slug: 'org',
        kind: 'personal',
        workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role }],
      },
    ],
  }
}

// JWT-Attrappe ohne `aal`-Claim: keine MFA-Vorankuendigung.
const session = {
  access_token: `h.${btoa(JSON.stringify({ sub: 'u1' })).replace(/=+$/, '')}.s`,
} as unknown as Session

function testCase(overrides: Partial<TestCaseRead> = {}): TestCaseRead {
  return {
    id: 'c1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    entity_type: 'system_prompt_template',
    entity_id: 'sp1',
    title: 'Kurze PR-Beschreibung',
    input: 'Schreib die PR-Beschreibung.',
    expected_behavior: 'Höchstens fünf Zeilen.',
    check_kind: 'must_contain',
    check_pattern: 'x',
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
    subject_entity_type: 'system_prompt_template',
    subject_version_id: VERSION_ID,
    runs_total: 3,
    runs_passed: 3,
    verdict: 'pass',
    output_excerpt: null,
    attestation: 'client_self_report',
    model_provider: null,
    model_name: null,
    reported_by_agent_id: 'a1',
    reported_by_user_id: null,
    created_at: '2026-09-30T09:00:00Z',
    ...overrides,
  }
}

function entry(
  state: TestReportEntry['state'],
  caseOverrides: Partial<TestCaseRead>,
  result: TestRunRead | null = null,
): TestReportEntry {
  return { test_case: testCase(caseOverrides), direct: true, state, result }
}

function report(entries: TestReportEntry[]): TestReport {
  const count = (state: TestReportEntry['state']) => entries.filter((e) => e.state === state).length
  return {
    entity_type: 'system_prompt_template',
    entity_id: 'sp1',
    version_id: VERSION_ID,
    affected_agent_count: 1,
    scope_note: null,
    counts: {
      total: entries.length,
      passed: count('pass'),
      failed: count('fail'),
      error: count('error'),
      missing: count('missing'),
    },
    agents: [{ agent_id: 'a1', agent_name: 'coder', via: ['direct'], entries }],
  }
}

const RED_REPORT = report([
  entry('fail', { id: 'c40', title: 'T-40 Kurze PR-Beschreibung' }, run({ runs_passed: 1, verdict: 'fail' })),
  entry('missing', { id: 'c12', title: 'T-12 Changelog-Fragment' }),
  entry('pass', { id: 'c1', title: 'T-1 Tests laufen' }, run()),
])

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

function calls(fetchMock: ReturnType<typeof stubFetch>, method: string, path: string) {
  return fetchMock.mock.calls.filter(([input, init]) => {
    return (init?.method ?? 'GET') === method && new URL(String(input)).pathname === path
  })
}

function wrap(element: React.ReactNode, role: WorkspaceRole = 'admin') {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me: buildMe(role),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/system-prompts/sp1']}>{element}</MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

function renderSpBar(options: { role?: WorkspaceRole; onTransitioned?: () => void } = {}) {
  return wrap(
    <SystemPromptStatusActionBar
      templateId="sp1"
      version={3}
      status="review"
      onTransitioned={options.onTransitioned ?? vi.fn()}
      testReportEntityType="system_prompt_template"
      versionId={VERSION_ID}
    />,
    options.role,
  )
}

function renderCentralBar(
  onTransition: (to: VersionStatus, options?: unknown) => Promise<unknown>,
  role: WorkspaceRole = 'admin',
) {
  return wrap(
    <StatusActionBar
      status="review"
      onTransition={onTransition}
      onTransitioned={vi.fn()}
      testReportEntityType="persona"
      versionId={VERSION_ID}
    />,
    role,
  )
}

async function openDialog() {
  fireEvent.click(await screen.findByRole('button', { name: 'Aktivieren…' }))
  return screen.findByRole('dialog', { name: 'Trotz offener Prüffälle aktivieren?' })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('ActivateWithWarningDialog', () => {
  it('fuehrt bei roten/fehlenden Faellen ueber den Dialog und listet sie mit Wort, Titel und k/n', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json(RED_REPORT) })
    renderSpBar()

    const dialog = await openDialog()
    // DialogDescription ist verdrahtet (aria-describedby).
    expect(dialog).toHaveAccessibleDescription(
      '1 nicht bestanden, 1 ohne Ergebnis von 3 Prüffällen. Aktivieren geht nur mit Begründung.',
    )
    const rows = within(dialog).getAllByTestId('activate-warning-case')
    expect(rows.map((row) => row.textContent)).toEqual([
      'Nicht bestanden: T-40 Kurze PR-Beschreibung (1/3)',
      'Kein Ergebnis: T-12 Changelog-Fragment',
    ])
    // Rot laeuft ueber `text-destructive` (Audit A6).
    expect(within(rows[0]).getByText('Nicht bestanden')).toHaveClass('text-destructive')
    // Bestandene Faelle stehen nicht in der Liste.
    expect(dialog).not.toHaveTextContent('T-1 Tests laufen')
    const confirm = within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' })
    expect(confirm.className).toMatch(/bg-destructive/)
  })

  it('schickt ohne Grund nichts ab – auch nicht bei reinen Leerzeichen', async () => {
    const fetchMock = stubFetch({ [`GET ${REPORT_PATH}`]: () => json(RED_REPORT) })
    renderSpBar()

    const dialog = await openDialog()
    const confirm = within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' })
    expect(confirm).toBeDisabled()

    fireEvent.change(within(dialog).getByLabelText(/Warum trotzdem\?/), {
      target: { value: '   \n\t ' },
    })
    expect(confirm).toBeDisabled()
    fireEvent.click(confirm)

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(calls(fetchMock, 'POST', SP_TRANSITION)).toHaveLength(0)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('schickt mit Grund die Transition mit acknowledge_test_report und override_reason', async () => {
    const onTransitioned = vi.fn()
    const fetchMock = stubFetch({
      [`GET ${REPORT_PATH}`]: () => json(RED_REPORT),
      [`POST ${SP_TRANSITION}`]: () => json({}),
    })
    renderSpBar({ onTransitioned })

    const dialog = await openDialog()
    fireEvent.change(within(dialog).getByLabelText(/Warum trotzdem\?/), {
      target: { value: '  Hotfix, T-40 ist bekannt flaky.  ' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' }))

    await waitFor(() => expect(onTransitioned).toHaveBeenCalledTimes(1))
    const posts = calls(fetchMock, 'POST', SP_TRANSITION)
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({
      to: 'active',
      acknowledge_test_report: true,
      override_reason: 'Hotfix, T-40 ist bekannt flaky.',
    })
    expect(notify.success).toHaveBeenCalledWith('Version aktiviert.')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it.each([
    [
      'test_override_reason_required',
      'Begründung fehlt',
      'Der Server braucht eine Begründung, warum trotz offener Prüffälle aktiviert wird. Trag sie oben ein.',
    ],
    [
      'test_results_incomplete',
      'Prüfbericht nicht bestätigt',
      'Der Server hat die Aktivierung abgelehnt, weil rote oder fehlende Prüffälle nicht bestätigt wurden. Lade die Seite neu und versuche es noch einmal.',
    ],
  ])('zeigt eine 409 %s verständlich im Dialog, nicht als Toast', async (reason, title, body) => {
    const onTransitioned = vi.fn()
    stubFetch({
      [`GET ${REPORT_PATH}`]: () => json(RED_REPORT),
      [`POST ${SP_TRANSITION}`]: () =>
        json({ detail: 'Server-Detail', reason, params: {} }, 409),
    })
    renderSpBar({ onTransitioned })

    const dialog = await openDialog()
    fireEvent.change(within(dialog).getByLabelText(/Warum trotzdem\?/), {
      target: { value: 'Grund' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' }))

    const alert = await within(dialog).findByRole('alert')
    expect(alert).toHaveTextContent(title)
    expect(alert).toHaveTextContent(body)
    expect(notify.error).not.toHaveBeenCalled()
    expect(onTransitioned).not.toHaveBeenCalled()
    // Dialog bleibt offen, der Grund bleibt stehen.
    expect(within(dialog).getByLabelText(/Warum trotzdem\?/)).toHaveValue('Grund')
  })

  it('zeigt andere Fehler ebenfalls im Dialog', async () => {
    stubFetch({
      [`GET ${REPORT_PATH}`]: () => json(RED_REPORT),
      [`POST ${SP_TRANSITION}`]: () => json({ detail: 'Kaputt' }, 500),
    })
    renderSpBar()

    const dialog = await openDialog()
    fireEvent.change(within(dialog).getByLabelText(/Warum trotzdem\?/), {
      target: { value: 'Grund' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Aktivieren fehlgeschlagen')
  })

  it('sperrt Gründe über 1 000 Zeichen (nach Trimmen) und nimmt genau 1 000 an', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json(RED_REPORT) })
    renderSpBar()

    const dialog = await openDialog()
    const field = within(dialog).getByLabelText(/Warum trotzdem\?/)
    const confirm = within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' })

    fireEvent.change(field, { target: { value: `  ${'x'.repeat(1000)}  ` } })
    expect(confirm).toBeEnabled()
    fireEvent.change(field, { target: { value: 'x'.repeat(1001) } })
    expect(confirm).toBeDisabled()
    expect(within(dialog).getByTestId('activate-warning-too-long')).toHaveClass('text-destructive')
  })

  it('nimmt bei nicht ladbarem Bericht alle Fälle als „fehlt“ und verlangt trotzdem den Grund', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json({ detail: 'weg' }, 500) })
    renderSpBar()

    const dialog = await openDialog()
    expect(dialog).toHaveTextContent('Ergebnisse konnten nicht geladen werden – alle Prüffälle gelten als „fehlt“.')
    expect(within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' })).toBeDisabled()
  })

  it('gibt den Fokus nach dem Schließen an den Auslöser zurück', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json(RED_REPORT) })
    renderSpBar()

    const trigger = await screen.findByRole('button', { name: 'Aktivieren…' })
    trigger.focus()
    const dialog = await openDialog()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(trigger).toHaveFocus()
  })

  it('hat keine axe-Verstöße im offenen Dialog', async () => {
    stubFetch({ [`GET ${REPORT_PATH}`]: () => json(RED_REPORT) })
    renderSpBar()

    const dialog = await openDialog()
    expect(await axe(dialog)).toHaveNoViolations()
  })

  it('zeigt die Texte in der englischen Oberfläche auf Englisch', async () => {
    await i18n.changeLanguage('en')
    try {
      stubFetch({ [`GET ${REPORT_PATH}`]: () => json(RED_REPORT) })
      renderSpBar()
      fireEvent.click(await screen.findByRole('button', { name: 'Activate…' }))
      const dialog = await screen.findByRole('dialog', { name: 'Activate despite open test cases?' })
      expect(within(dialog).getByLabelText(/Why anyway\?/)).toBeInTheDocument()
      expect(within(dialog).getByRole('button', { name: 'Activate anyway' })).toBeDisabled()
    } finally {
      await i18n.changeLanguage('de')
    }
  })
})

describe('StatusActionBar mit Prüfbericht', () => {
  it('aktiviert bei allem bestanden ohne Dialog und nennt die Zahl der Prüffälle', async () => {
    stubFetch({
      [`GET ${PERSONA_REPORT_PATH}`]: () =>
        json(report([entry('pass', { id: 'c1' }, run()), entry('pass', { id: 'c2' }, run())])),
    })
    const onTransition = vi.fn().mockResolvedValue(undefined)
    renderCentralBar(onTransition)

    expect(await screen.findByTestId('activate-all-passed')).toHaveTextContent(
      'Alle 2 Prüffälle bestanden. Aktivieren entscheidest trotzdem du.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Aktivieren' }))

    await waitFor(() => expect(onTransition).toHaveBeenCalledTimes(1))
    // Ein Klick wie bisher: keine Zusatzfelder, kein Dialog.
    expect(onTransition).toHaveBeenCalledWith('active')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('aktiviert bei leerer Prüffall-Menge ohne Dialog und ohne Satz', async () => {
    stubFetch({ [`GET ${PERSONA_REPORT_PATH}`]: () => json(report([])) })
    renderCentralBar(vi.fn().mockResolvedValue(undefined))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Aktivieren' })).not.toHaveAttribute('aria-busy'),
    )
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    expect(screen.queryByTestId('activate-all-passed')).toBeNull()
  })

  it('reicht die Vertragsfelder an onTransition durch', async () => {
    stubFetch({ [`GET ${PERSONA_REPORT_PATH}`]: () => json(RED_REPORT) })
    const onTransition = vi.fn().mockResolvedValue(undefined)
    renderCentralBar(onTransition)

    const dialog = await openDialog()
    expect(screen.getByTestId('branch-action-publish')).toHaveTextContent('Aktivieren…')
    fireEvent.change(within(dialog).getByLabelText(/Warum trotzdem\?/), {
      target: { value: 'Weil.' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Trotzdem aktivieren' }))

    await waitFor(() => expect(onTransition).toHaveBeenCalledTimes(1))
    expect(onTransition).toHaveBeenCalledWith('active', {
      acknowledge_test_report: true,
      override_reason: 'Weil.',
    })
  })

  it('zeigt Nicht-Admins den gesperrten Knopf mit sichtbarem Grund und lädt keinen Bericht', () => {
    const fetchMock = stubFetch({})
    renderCentralBar(vi.fn(), 'editor')

    expect(screen.getByTestId('branch-action-publish')).toBeDisabled()
    expect(screen.getByTestId('activate-admin-only')).toHaveTextContent('Nur Admins können aktivieren.')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('zeigt Nicht-Admins auch in der System-Prompt-Leiste den sichtbaren Grund', () => {
    const fetchMock = stubFetch({})
    renderSpBar({ role: 'editor' })

    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeDisabled()
    expect(screen.getByTestId('activate-admin-only')).toBeVisible()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('bleibt ohne testReportEntityType/versionId beim bisherigen Ein-Klick-Knopf', () => {
    const fetchMock = stubFetch({})
    wrap(<StatusActionBar status="review" onTransition={vi.fn()} onTransitioned={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
