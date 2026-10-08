import type { Session } from '@supabase/supabase-js'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createApi } from '@/api/client'
import type { Agent, CaseRead, Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { toast } from '@/components/ui/sonner'
import { axe } from '@/test/a11y'

import { ReportCaseDialog } from './ReportCaseForm'

vi.mock('@/components/ui/sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

let role: string | null = 'viewer'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }
const WS = '/v1/workspaces/ws-1'
const agent = { id: 'a1', name: 'coder' }

function caseRead(overrides: Partial<CaseRead> = {}): CaseRead {
  return {
    id: 'case-1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    reporter_kind: 'human',
    reporter_user_id: 'u1',
    reporter_agent_id: null,
    situation: 'Bitte Tests fixen.',
    behavior: 'Direkt gepusht.',
    impact: null,
    expected_behavior: 'Erst lokal testen.',
    severity: 'medium',
    signal: null,
    source_ref: null,
    source_feedback_id: null,
    source_memory_id: null,
    status: 'open',
    created_at: '2026-10-08T10:00:00Z',
    ...overrides,
  }
}

function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

type Handler = (url: URL, init?: RequestInit) => Response | Promise<Response>

function stubFetch(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://who2be.test')
    const key = `${init?.method ?? 'GET'} ${url.pathname}`
    const handler = handlers[key]
    if (!handler) throw new Error(`Unmocked ${key}`)
    return handler(url, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderDialog(element: ReactElement = <ReportCaseDialog agent={agent} />) {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents/a1']}>
          <Routes>
            <Route path="/w/:workspaceId/agents/:id" element={element} />
            <Route
              path="/w/:workspaceId/feedback/cases/:caseId"
              element={<p data-testid="case-target">Fall-Ziel</p>}
            />
            <Route path="/w/:workspaceId/agents" element={<p data-testid="agents-target">Agents</p>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

async function openDialog() {
  fireEvent.click(screen.getByRole('button', { name: 'Fall melden' }))
  return screen.findByTestId('report-case-dialog')
}

function fill(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function fillRequired() {
  fill(/Was war die Lage\?/, '  Bitte Tests fixen.  ')
  fill(/Was hat der Agent getan\?/, 'Direkt gepusht.')
  fill(/Was hättest du erwartet\?/, 'Erst lokal testen.')
}

function submitButton(dialog: HTMLElement) {
  return within(dialog).getByRole('button', { name: 'Fall melden' })
}

beforeEach(() => {
  role = 'viewer'
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(toast.success).mockClear()
})

describe('ReportCaseDialog', () => {
  it('zeigt die vier Fragen mit Hilfesatz, den festen Agenten und den Datenschutzhinweis', async () => {
    renderDialog()
    const dialog = await openDialog()

    expect(within(dialog).getByRole('heading', { name: 'Fall melden' })).toBeInTheDocument()
    expect(within(dialog).getByText('coder')).toBeInTheDocument()
    expect(screen.getByLabelText(/Was war die Lage\?/)).toHaveAccessibleDescription(
      'Was hast du gefragt oder was sollte der Agent tun?',
    )
    expect(screen.getByLabelText(/Was hat der Agent getan\?/)).toBeRequired()
    expect(screen.getByLabelText(/Was hättest du erwartet\?/)).toBeRequired()
    expect(screen.getByLabelText(/Was war die Folge\?/)).not.toBeRequired()
    expect(within(dialog).getByText(/Keine Passwörter oder Kundendaten/)).toBeInTheDocument()
    // „Mehr angeben“ ist eingeklappt; Schwere ist mit „Stört“ vorbelegt.
    const more = within(dialog).getByRole('button', { name: 'Mehr angeben' })
    expect(more).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(more)
    expect(screen.getByRole('radio', { name: 'Stört' })).toBeChecked()
    expect(screen.getByLabelText('Link zum Lauf oder Ergebnis')).toBeVisible()
  })

  it('validiert erst beim Absenden und fokussiert das erste Fehlerfeld', async () => {
    const fetchMock = stubFetch({})
    renderDialog()
    const dialog = await openDialog()

    // Vor dem Absenden keine Fehlermeldung.
    fill(/Was hat der Agent getan\?/, 'x')
    expect(within(dialog).queryByText('Pflichtfeld.')).toBeNull()

    fireEvent.click(submitButton(dialog))

    const situation = screen.getByLabelText(/Was war die Lage\?/)
    await waitFor(() => expect(situation).toHaveFocus())
    expect(situation).toHaveAttribute('aria-invalid', 'true')
    expect(within(dialog).getAllByText('Pflichtfeld.')).toHaveLength(2)
    expect(fetchMock).not.toHaveBeenCalled()

    // Danach live: das Feld wird gueltig, sobald es Text hat.
    fill(/Was war die Lage\?/, 'Lage')
    expect(situation).not.toHaveAttribute('aria-invalid')
  })

  it('zeigt den Zähler ab 80 % der Grenze und weist zu langen Text vor dem Senden ab', async () => {
    const fetchMock = stubFetch({})
    renderDialog()
    const dialog = await openDialog()

    // Erwartet: Grenze 2 000 (CaseCreate.expected_behavior), Zaehler ab 1 600.
    fill(/Was hättest du erwartet\?/, 'e'.repeat(1_599))
    expect(within(dialog).queryByText('1599 / 2000')).toBeNull()
    fill(/Was hättest du erwartet\?/, 'e'.repeat(1_600))
    expect(within(dialog).getByText('1600 / 2000')).toBeInTheDocument()

    // Lage: Grenze 4 000 (CaseCreate.situation).
    fill(/Was war die Lage\?/, 's'.repeat(4_001))
    fill(/Was hat der Agent getan\?/, 'b')
    fireEvent.click(submitButton(dialog))

    expect(await within(dialog).findByText('Höchstens 4000 Zeichen.')).toBeInTheDocument()
    expect(screen.getByLabelText(/Was war die Lage\?/)).toHaveFocus()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('„Getan“ hat die Grenze 4000: 4000 Zeichen gehen durch, 4001 nicht (LIMITS.behavior)', async () => {
    const bodies: Array<Record<string, unknown>> = []
    const fetchMock = stubFetch({
      [`POST ${WS}/cases`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        return json(caseRead(), 201)
      },
    })
    renderDialog()
    const dialog = await openDialog()
    fillRequired()

    // Zaehler ab 80 % von 4000 = 3200, nicht erst ab 6400 (alte Spec: 8000).
    fill(/Was hat der Agent getan\?/, 'b'.repeat(3_200))
    expect(within(dialog).getByText('3200 / 4000')).toBeInTheDocument()

    fill(/Was hat der Agent getan\?/, 'b'.repeat(4_001))
    fireEvent.click(submitButton(dialog))
    expect(await within(dialog).findByText('Höchstens 4000 Zeichen.')).toBeInTheDocument()
    expect(screen.getByLabelText(/Was hat der Agent getan\?/)).toHaveFocus()
    expect(fetchMock).not.toHaveBeenCalled()

    fill(/Was hat der Agent getan\?/, 'b'.repeat(4_000))
    expect(within(dialog).queryByText('Höchstens 4000 Zeichen.')).toBeNull()
    fireEvent.click(submitButton(dialog))
    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(String(bodies[0].behavior)).toHaveLength(4_000)
  })

  it('öffnet „Mehr angeben“, wenn der Link zu lang ist (Grenze 500)', async () => {
    stubFetch({})
    renderDialog()
    const dialog = await openDialog()
    fillRequired()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Mehr angeben' }))
    fill('Link zum Lauf oder Ergebnis', 'l'.repeat(501))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Mehr angeben' }))

    fireEvent.click(submitButton(dialog))

    const link = screen.getByLabelText('Link zum Lauf oder Ergebnis')
    await waitFor(() => expect(link).toHaveFocus())
    expect(within(dialog).getByText('Höchstens 500 Zeichen.')).toBeInTheDocument()
  })

  it('sendet getrimmte Felder ohne Zuordnung und meldet Erfolg mit Link „Ansehen“', async () => {
    const bodies: unknown[] = []
    stubFetch({
      [`POST ${WS}/cases`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)))
        return json(caseRead(), 201)
      },
    })
    renderDialog()
    const dialog = await openDialog()
    fillRequired()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Mehr angeben' }))
    fireEvent.click(screen.getByRole('radio', { name: 'Blockiert' }))
    fill('Link zum Lauf oder Ergebnis', ' artifact:42 ')

    fireEvent.click(submitButton(dialog))

    await waitFor(() => expect(screen.queryByTestId('report-case-dialog')).toBeNull())
    expect(bodies).toEqual([
      {
        agent_id: 'a1',
        situation: 'Bitte Tests fixen.',
        behavior: 'Direkt gepusht.',
        expected_behavior: 'Erst lokal testen.',
        severity: 'high',
        source_ref: 'artifact:42',
      },
    ])
    const [message, options] = vi.mocked(toast.success).mock.calls[0]
    expect(message).toBe('Fall gemeldet. Du siehst den Stand unter „Meine Fälle“.')
    const action = options?.action as { label: string; onClick: () => void }
    expect(action.label).toBe('Ansehen')
    act(() => action.onClick())
    expect(await screen.findByTestId('case-target')).toBeInTheDocument()
  })

  it('editor bekommt den Erfolgstext „unter Fälle“', async () => {
    role = 'editor'
    stubFetch({ [`POST ${WS}/cases`]: () => json(caseRead(), 201) })
    renderDialog()
    const dialog = await openDialog()
    fillRequired()
    fireEvent.click(submitButton(dialog))

    await waitFor(() => expect(toast.success).toHaveBeenCalled())
    expect(vi.mocked(toast.success).mock.calls[0][0]).toBe(
      'Fall gemeldet. Du findest ihn unter Fälle.',
    )
  })

  it('Variante „Lief gut – so lassen“: signal=helpful und Label „Was soll so bleiben?“', async () => {
    const bodies: Array<Record<string, unknown>> = []
    stubFetch({
      [`POST ${WS}/cases`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        return json(caseRead({ signal: 'helpful' }), 201)
      },
    })
    renderDialog()
    const dialog = await openDialog()

    const keep = within(dialog).getByRole('button', { name: 'Lief gut – so lassen' })
    fireEvent.click(keep)
    expect(keep).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByLabelText(/Was hättest du erwartet\?/)).toBeNull()
    fill(/Was war die Lage\?/, 'Release-Notes schreiben.')
    fill(/Was hat der Agent getan\?/, 'Kurz und vollständig.')
    fill(/Was soll so bleiben\?/, 'Genau diese Form.')

    fireEvent.click(submitButton(dialog))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].signal).toBe('helpful')
    expect(bodies[0].expected_behavior).toBe('Genau diese Form.')
  })

  it('agent_not_found: eigener Fehlertext, Eingaben bleiben erhalten', async () => {
    stubFetch({
      [`POST ${WS}/cases`]: () =>
        new Response(JSON.stringify({ detail: 'Agent nicht gefunden.', reason: 'agent_not_found' }), {
          status: 404,
          headers: { 'Content-Type': 'application/problem+json' },
        }),
    })
    renderDialog()
    const dialog = await openDialog()
    fillRequired()
    fireEvent.click(submitButton(dialog))

    const alert = await within(dialog).findByTestId('error-alert')
    expect(alert).toHaveTextContent('Diesen Agenten gibt es nicht mehr. Wähle einen anderen.')
    expect(screen.getByLabelText(/Was hat der Agent getan\?/)).toHaveValue('Direkt gepusht.')
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('anderer Fehler: ErrorAlert mit dem Servertext', async () => {
    stubFetch({
      [`POST ${WS}/cases`]: () =>
        new Response(JSON.stringify({ detail: 'Zu viele Anfragen.' }), {
          status: 429,
          headers: { 'Content-Type': 'application/json' },
        }),
    })
    renderDialog()
    const dialog = await openDialog()
    fillRequired()
    fireEvent.click(submitButton(dialog))

    expect(await within(dialog).findByTestId('error-alert')).toHaveTextContent('Zu viele Anfragen.')
  })

  it('beim Senden: Spinner, aria-busy und kein doppeltes Absenden', async () => {
    let release: (response: Response) => void = () => undefined
    const fetchMock = stubFetch({
      [`POST ${WS}/cases`]: () =>
        new Promise<Response>((resolve) => {
          release = resolve
        }),
    })
    renderDialog()
    const dialog = await openDialog()
    fillRequired()

    const button = submitButton(dialog)
    fireEvent.click(button)
    fireEvent.click(button)
    fireEvent.submit(button.closest('form') as HTMLFormElement)

    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    expect(button).toBeDisabled()
    expect(button.querySelector('.animate-spin')).not.toBeNull()
    // Felder bleiben bedienbar.
    expect(screen.getByLabelText(/Was war die Folge\?/)).toBeEnabled()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await act(async () => release(json(caseRead(), 201)))
    await waitFor(() => expect(screen.queryByTestId('report-case-dialog')).toBeNull())
  })

  it('Abbrechen mit Inhalt fragt „Eingaben verwerfen?“, ohne Inhalt schließt es direkt', async () => {
    renderDialog()
    let dialog = await openDialog()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))
    expect(screen.queryByTestId('report-case-dialog')).toBeNull()

    dialog = await openDialog()
    fill(/Was war die Folge\?/, 'Alles neu.')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))
    const confirm = await screen.findByTestId('report-case-discard')
    expect(within(confirm).getByRole('heading', { name: 'Eingaben verwerfen?' })).toBeInTheDocument()

    fireEvent.click(within(confirm).getByRole('button', { name: 'Weiter bearbeiten' }))
    await waitFor(() => expect(screen.queryByTestId('report-case-discard')).toBeNull())
    expect(screen.getByLabelText(/Was war die Folge\?/)).toHaveValue('Alles neu.')

    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))
    fireEvent.click(
      within(await screen.findByTestId('report-case-discard')).getByRole('button', {
        name: 'Verwerfen',
      }),
    )
    await waitFor(() => expect(screen.queryByTestId('report-case-dialog')).toBeNull())

    // Kein Entwurf: neu geoeffnet ist das Formular leer.
    await openDialog()
    expect(screen.getByLabelText(/Was war die Folge\?/)).toHaveValue('')
  })

  it('a11y: keine axe-Violations mit Daten, Fehlern und offenem „Mehr angeben“', async () => {
    stubFetch({})
    renderDialog()
    const dialog = await openDialog()
    fill(/Was hat der Agent getan\?/, 'b'.repeat(3_300))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Mehr angeben' }))
    fireEvent.click(submitButton(dialog))
    await within(dialog).findAllByText('Pflichtfeld.')

    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)
})

function agentRow(id: string, name: string): Agent {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'u1',
    name,
    description: '',
    persona_id: null,
    system_prompt_template_id: null,
    status: 'enabled',
    tool_policy: {},
    persona_active: true,
    activatable: true,
  } as unknown as Agent
}

describe('ReportCaseDialog ohne festen Agenten (D6b0)', () => {
  const agents = [agentRow('a1', 'coder'), agentRow('a2', 'reviewer')]

  it('Ausloeser: Default-Variante outline, Hub-Variante brand', () => {
    const { unmount } = renderDialog()
    expect(screen.getByRole('button', { name: 'Fall melden' })).toHaveClass('border-input')
    expect(screen.getByRole('button', { name: 'Fall melden' })).not.toHaveClass('bg-brand')
    unmount()

    renderDialog(<ReportCaseDialog variant="brand" />)
    expect(screen.getByRole('button', { name: 'Fall melden' })).toHaveClass('bg-brand')
  })

  it('mit festem Agenten: Lesewert, kein Select und kein GET /agents', async () => {
    const fetchMock = stubFetch({})
    renderDialog()
    const dialog = await openDialog()
    expect(within(dialog).queryByRole('combobox', { name: /Agent/ })).toBeNull()
    expect(within(dialog).getByText('coder')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('lädt die Agenten über GET /agents und sendet den gewählten', async () => {
    const bodies: Array<Record<string, unknown>> = []
    stubFetch({
      [`GET ${WS}/agents`]: () => json(agents),
      [`POST ${WS}/cases`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        return json(caseRead({ agent_id: 'a2' }), 201)
      },
    })
    renderDialog(<ReportCaseDialog variant="brand" />)
    const dialog = await openDialog()

    const select = await within(dialog).findByRole('combobox', { name: /Agent/ })
    expect(select).toHaveValue('')
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Agent wählen …',
      'coder',
      'reviewer',
    ])
    fireEvent.change(select, { target: { value: 'a2' } })
    fillRequired()
    fireEvent.click(submitButton(dialog))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].agent_id).toBe('a2')
  })

  it('Pflicht „Agent“: ohne Auswahl Fehler, Fokus auf dem Select, kein POST', async () => {
    const fetchMock = stubFetch({ [`GET ${WS}/agents`]: () => json(agents) })
    renderDialog(<ReportCaseDialog />)
    const dialog = await openDialog()
    const select = await within(dialog).findByRole('combobox', { name: /Agent/ })
    fillRequired()

    fireEvent.click(submitButton(dialog))

    await waitFor(() => expect(select).toHaveFocus())
    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(select).toHaveAccessibleDescription('Bitte einen Agenten wählen.')
    expect(fetchMock).toHaveBeenCalledTimes(1) // nur GET /agents

    // Danach live: mit Auswahl verschwindet der Fehler.
    fireEvent.change(select, { target: { value: 'a1' } })
    expect(select).not.toHaveAttribute('aria-invalid')
    expect(within(dialog).queryByText('Bitte einen Agenten wählen.')).toBeNull()
  })

  it('Auswahl allein zählt als Eingabe: Abbrechen fragt „Eingaben verwerfen?“', async () => {
    stubFetch({ [`GET ${WS}/agents`]: () => json(agents) })
    renderDialog(<ReportCaseDialog />)
    const dialog = await openDialog()
    fireEvent.change(await within(dialog).findByRole('combobox', { name: /Agent/ }), {
      target: { value: 'a1' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))
    expect(await screen.findByTestId('report-case-discard')).toBeInTheDocument()
  })

  it('Leerzustand: ohne Agenten kein Formular, Hinweis noAgents mit Link zu den Agents', async () => {
    stubFetch({ [`GET ${WS}/agents`]: () => json([]) })
    renderDialog(<ReportCaseDialog />)
    const dialog = await openDialog()

    expect(
      await within(dialog).findByText(
        'Noch kein Agent im Workspace. Ein Fall gehört immer zu einem Agenten.',
      ),
    ).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Fall melden' })).toBeNull()
    expect(screen.queryByLabelText(/Was war die Lage\?/)).toBeNull()
    fireEvent.click(within(dialog).getByRole('link', { name: 'Zu den Agents' }))
    expect(await screen.findByTestId('agents-target')).toBeInTheDocument()
  })

  it('Ladefehler bei GET /agents: ErrorAlert statt Formular', async () => {
    stubFetch({
      [`GET ${WS}/agents`]: () =>
        new Response(JSON.stringify({ detail: 'Kein Zugriff.' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }),
    })
    renderDialog(<ReportCaseDialog />)
    const dialog = await openDialog()
    expect(await within(dialog).findByTestId('error-alert')).toHaveTextContent('Kein Zugriff.')
    expect(screen.queryByLabelText(/Was war die Lage\?/)).toBeNull()
  })

  it('a11y: keine axe-Violations mit Agent-Select im Fehlerzustand', async () => {
    stubFetch({ [`GET ${WS}/agents`]: () => json(agents) })
    renderDialog(<ReportCaseDialog variant="brand" />)
    const dialog = await openDialog()
    await within(dialog).findByRole('combobox', { name: /Agent/ })
    fireEvent.click(submitButton(dialog))
    await within(dialog).findByText('Bitte einen Agenten wählen.')

    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)
})

describe('Fall-Client (createApi)', () => {
  it('listCases liest X-Next-Cursor und setzt je Status einen Query-Parameter', async () => {
    const urls: URL[] = []
    stubFetch({
      [`GET ${WS}/cases`]: (url) => {
        urls.push(url)
        return json([caseRead()], 200, { 'X-Next-Cursor': 'c-2' })
      },
    })
    const api = createApi('jwt', 'ws-1')

    const page = await api.listCases(
      { agent_id: 'a1', status: ['open', 'reopened'], target: 'playbook' },
      { cursor: 'c-1', limit: 20 },
    )

    expect(page).toEqual({ items: [caseRead()], next_cursor: 'c-2' })
    expect(urls[0].searchParams.getAll('status')).toEqual(['open', 'reopened'])
    expect(urls[0].searchParams.get('agent_id')).toBe('a1')
    expect(urls[0].searchParams.get('target')).toBe('playbook')
    expect(urls[0].searchParams.get('cursor')).toBe('c-1')
    expect(urls[0].searchParams.get('limit')).toBe('20')
  })

  it('listCases ohne Header ist die letzte Seite; ein einzelner Status bleibt ein Parameter', async () => {
    const urls: URL[] = []
    stubFetch({
      [`GET ${WS}/cases`]: (url) => {
        urls.push(url)
        return json([])
      },
    })
    const page = await createApi('jwt', 'ws-1').listCases({ status: 'triaged' })

    expect(page).toEqual({ items: [], next_cursor: null })
    expect(urls[0].search).toBe('?status=triaged')
  })

  it('listCases wirft bei HTTP-Fehler den uebersetzten ApiError', async () => {
    stubFetch({
      [`GET ${WS}/cases`]: () =>
        new Response(JSON.stringify({ detail: 'Kein Zugriff.' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }),
    })
    await expect(createApi('jwt', 'ws-1').listCases()).rejects.toMatchObject({
      status: 403,
      message: 'Kein Zugriff.',
    })
  })

  it('übrige Fall-Methoden treffen die Pfade aus cases.py', async () => {
    const calls: string[] = []
    const record: Handler = (url, init) => {
      calls.push(`${init?.method ?? 'GET'} ${url.pathname}${url.search}`)
      return init?.method === 'DELETE' ? new Response(null, { status: 204 }) : json({})
    }
    stubFetch({
      [`GET ${WS}/cases/counts`]: record,
      [`GET ${WS}/cases/case-1`]: record,
      [`DELETE ${WS}/cases/case-1`]: record,
      [`POST ${WS}/cases/case-1/transition`]: record,
      [`PUT ${WS}/cases/case-1/elements`]: record,
    })
    const api = createApi('jwt', 'ws-1')

    await api.countCases('a1')
    await api.getCase('case-1')
    await api.deleteCase('case-1')
    await api.transitionCase('case-1', { to: 'dismissed', note: 'Doppelt.' })
    await api.putCaseElements('case-1', [{ target: 'model_limit' }])

    expect(calls).toEqual([
      `GET ${WS}/cases/counts?agent_id=a1`,
      `GET ${WS}/cases/case-1`,
      `DELETE ${WS}/cases/case-1`,
      `POST ${WS}/cases/case-1/transition`,
      `PUT ${WS}/cases/case-1/elements`,
    ])
  })
})
