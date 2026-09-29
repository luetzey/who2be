import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Agent, Me, TestCaseRead } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'
import { axe } from '@/test/a11y'

import { TestCaseList } from './TestCaseList'

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
    check_kind: 'human_rule',
    check_pattern: null,
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

const agents = [{ id: 'a1', name: 'coder' }] as unknown as Agent[]

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

function renderList(props: Parameters<typeof TestCaseList>[0]) {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/playbooks/p1']}>
          <Routes>
            <Route path="/w/:workspaceId/playbooks/:id" element={<TestCaseList {...props} />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

const entity = { type: 'playbook' as const, id: 'p1' }

beforeEach(() => {
  role = 'editor'
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('TestCaseList', () => {
  it('laedt am Element mit entity-Filter und zeigt die aktiven Prueffaelle', async () => {
    const urls: URL[] = []
    stubFetch({
      [`GET ${WS}/test-cases`]: (url) => {
        urls.push(url)
        return json([testCase(), testCase({ id: 'c2', title: 'Alt', status: 'retired' })])
      },
    })
    renderList({ entity, agents, subjectLabel: 'Playbook „Implement“' })

    const rows = await screen.findAllByTestId('test-case-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].textContent).toContain('Push nach Fix')
    expect(rows[0].textContent).toContain('Mensch bewertet')
    expect(urls[0].searchParams.get('entity_type')).toBe('playbook')
    expect(urls[0].searchParams.get('entity_id')).toBe('p1')
    expect(urls[0].searchParams.has('agent_id')).toBe(false)
    expect(screen.getByRole('heading', { name: 'Prüffälle · Playbook „Implement“' })).toBeInTheDocument()
    expect(screen.getByText(/1 Prüffall · läuft bei jeder neuen Version/)).toBeInTheDocument()
  })

  it('blendet archivierte Prueffaelle auf Wunsch ein, mit sichtbarem Status', async () => {
    stubFetch({
      [`GET ${WS}/test-cases`]: () =>
        json([testCase(), testCase({ id: 'c2', title: 'Alt', status: 'retired' })]),
    })
    renderList({ entity, agents })

    const toggle = await screen.findByRole('button', { name: '1 archivierten Prüffall anzeigen' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(toggle)

    const rows = screen.getAllByTestId('test-case-row')
    expect(rows).toHaveLength(2)
    const retired = rows.find((row) => row.dataset.status === 'retired')
    expect(retired?.textContent).toContain('Archiviert')
    // Archivierte Zeilen haben keine Aktionen mehr.
    expect(within(retired as HTMLElement).queryByRole('button')).toBeNull()
    expect(screen.getByRole('button', { name: 'Archivierte ausblenden' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('Leerzustand mit Spec-Text und Anlage-Aktion', async () => {
    stubFetch({ [`GET ${WS}/test-cases`]: () => json([]) })
    renderList({ agentId: 'a1', agents })

    expect(await screen.findByText('Noch keine Prüffälle')).toBeInTheDocument()
    expect(screen.getByText(/Jede neue Version wird gegen alle geprüft/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Prüffall anlegen' })).toBeInTheDocument()
  })

  it('Fehler mit Erneut versuchen laedt neu', async () => {
    let calls = 0
    stubFetch({
      [`GET ${WS}/test-cases`]: () => {
        calls += 1
        return calls === 1 ? json({ detail: 'Kaputt' }, 500) : json([testCase()])
      },
    })
    renderList({ agentId: 'a1', agents })

    fireEvent.click(await screen.findByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByTestId('test-case-row')).toBeInTheDocument()
    expect(calls).toBe(2)
  })

  it('403 zeigt den Rechte-Text statt der Rohmeldung', async () => {
    stubFetch({ [`GET ${WS}/test-cases`]: () => json({ detail: 'raw forbidden' }, 403) })
    renderList({ agentId: 'a1', agents })

    expect(await screen.findByText('Dafür fehlen dir die Rechte (ab Rolle Editor).')).toBeInTheDocument()
    expect(screen.queryByText('raw forbidden')).toBeNull()
  })

  it('viewer bekommt den Rechte-Hinweis ohne Request', async () => {
    role = 'viewer'
    const fetchMock = stubFetch({})
    renderList({ agentId: 'a1', agents })

    expect(screen.getByText('Dafür fehlen dir die Rechte (ab Rolle Editor).')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Prüffall anlegen' })).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('am Agenten: gruppiert nach Bezug und legt einen Prueffall an', async () => {
    const bodies: unknown[] = []
    let listCalls = 0
    stubFetch({
      [`GET ${WS}/test-cases`]: (url) => {
        listCalls += 1
        expect(url.searchParams.get('agent_id')).toBe('a1')
        return json([testCase(), testCase({ id: 'c3', title: 'Direkt', entity_type: null, entity_id: null })])
      },
      [`POST ${WS}/test-cases`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)))
        return json(testCase({ id: 'c9' }), 201)
      },
    })
    renderList({ agentId: 'a1', agents })

    expect(await screen.findByRole('region', { name: 'Direkt am Agenten' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Playbook p1' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Prüffall anlegen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Prüffall anlegen' })
    // Agent ist vom Aufrufort fest — keine Auswahl.
    expect(within(dialog).queryByLabelText('Gilt für Agent')).toBeNull()

    fireEvent.change(within(dialog).getByLabelText('Kurzname'), { target: { value: ' Kurze PR ' } })
    fireEvent.change(within(dialog).getByLabelText('Eingabe'), { target: { value: 'Schreib die PR.' } })
    fireEvent.change(within(dialog).getByLabelText('Erwartetes Verhalten'), {
      target: { value: 'Höchstens fünf Zeilen.' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Prüffall anlegen' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toEqual({
      agent_id: 'a1',
      entity_type: null,
      entity_id: null,
      title: 'Kurze PR',
      input: 'Schreib die PR.',
      expected_behavior: 'Höchstens fünf Zeilen.',
      check_kind: 'human_rule',
      check_pattern: null,
      origin_case_id: null,
      origin_measure_id: null,
      supersedes_id: null,
    })
    expect(notify.success).toHaveBeenCalledWith('Prüffall angelegt.')
    await waitFor(() => expect(listCalls).toBe(2))
  })

  it('Formular prueft Pflichtfelder und verlangt das Muster bei Enthaelt', async () => {
    const post = vi.fn()
    stubFetch({
      [`GET ${WS}/test-cases`]: () => json([]),
      [`POST ${WS}/test-cases`]: () => {
        post()
        return json(testCase(), 201)
      },
    })
    renderList({ entity, agents })

    fireEvent.click(await screen.findByRole('button', { name: 'Prüffall anlegen' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Wie wird geprüft?'), {
      target: { value: 'must_contain' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Prüffall anlegen' }))

    expect(within(dialog).getByText('Bitte einen Agenten wählen.')).toBeInTheDocument()
    expect(within(dialog).getAllByText('Pflichtfeld.')).toHaveLength(4)
    expect(within(dialog).getByLabelText('Gesuchter Text')).toHaveAttribute('aria-invalid', 'true')
    expect(post).not.toHaveBeenCalled()
  })

  it('am Element: Agent waehlbar, Bezug vorbelegt, Muster wird mitgeschickt', async () => {
    const bodies: Record<string, unknown>[] = []
    stubFetch({
      [`GET ${WS}/test-cases`]: () => json([]),
      [`POST ${WS}/test-cases`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        return json(testCase(), 201)
      },
    })
    renderList({ entity, agents })

    fireEvent.click(await screen.findByRole('button', { name: 'Prüffall anlegen' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Gilt für Agent'), { target: { value: 'a1' } })
    fireEvent.change(within(dialog).getByLabelText('Kurzname'), { target: { value: 'T' } })
    fireEvent.change(within(dialog).getByLabelText('Eingabe'), { target: { value: 'E' } })
    fireEvent.change(within(dialog).getByLabelText('Erwartetes Verhalten'), { target: { value: 'X' } })
    fireEvent.change(within(dialog).getByLabelText('Wie wird geprüft?'), {
      target: { value: 'must_not_contain' },
    })
    fireEvent.change(within(dialog).getByLabelText('Gesuchter Text'), { target: { value: 'force' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Prüffall anlegen' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toMatchObject({
      agent_id: 'a1',
      entity_type: 'playbook',
      entity_id: 'p1',
      check_kind: 'must_not_contain',
      check_pattern: 'force',
    })
  })

  it('Neue Fassung: vorbelegt, schickt supersedes_id und behaelt den Bezug', async () => {
    const bodies: Record<string, unknown>[] = []
    stubFetch({
      [`GET ${WS}/test-cases`]: () => json([testCase({ origin_case_id: 'case-218' })]),
      [`POST ${WS}/test-cases`]: (_url, init) => {
        bodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        return json(testCase({ id: 'c2', supersedes_id: 'c1' }), 201)
      },
    })
    renderList({ entity, agents })

    fireEvent.pointerDown(
      await screen.findByRole('button', { name: 'Aktionen für Prüffall „Push nach Fix“' }),
      { button: 0, ctrlKey: false },
    )
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Neue Fassung anlegen' }))

    const dialog = await screen.findByRole('dialog', { name: 'Neue Fassung anlegen' })
    expect(within(dialog).getByLabelText('Kurzname')).toHaveValue('Push nach Fix')
    fireEvent.change(within(dialog).getByLabelText('Erwartetes Verhalten'), {
      target: { value: 'Führt Tests und Lint lokal aus.' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Neue Fassung anlegen' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toMatchObject({
      agent_id: 'a1',
      entity_type: 'playbook',
      entity_id: 'p1',
      expected_behavior: 'Führt Tests und Lint lokal aus.',
      origin_case_id: 'case-218',
      supersedes_id: 'c1',
    })
    expect(notify.success).toHaveBeenCalledWith('Neue Fassung angelegt, die bisherige ist archiviert.')
  })

  it('Archivieren fragt nach und ruft retire', async () => {
    const retired: string[] = []
    stubFetch({
      [`GET ${WS}/test-cases`]: () => json([testCase()]),
      [`POST ${WS}/test-cases/c1/retire`]: () => {
        retired.push('c1')
        return json(testCase({ status: 'retired' }))
      },
    })
    renderList({ entity, agents })

    fireEvent.pointerDown(
      await screen.findByRole('button', { name: 'Aktionen für Prüffall „Push nach Fix“' }),
      { button: 0, ctrlKey: false },
    )
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Archivieren' }))

    const dialog = await screen.findByRole('dialog', { name: 'Prüffall archivieren?' })
    expect(
      within(dialog).getByText(
        'Archivierte Prüffälle laufen nicht mehr mit. Gilt dieser Fall wirklich nicht mehr?',
      ),
    ).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Archivieren' }))

    await waitFor(() => expect(retired).toEqual(['c1']))
    expect(notify.success).toHaveBeenCalledWith('Prüffall archiviert.')
  })
})

describe('TestCaseList a11y', () => {
  it('Liste ohne axe-Verstoesse', async () => {
    stubFetch({
      [`GET ${WS}/test-cases`]: () =>
        json([testCase(), testCase({ id: 'c2', title: 'Alt', status: 'retired' })]),
    })
    const { container } = renderList({ agentId: 'a1', agents })
    await screen.findAllByTestId('test-case-row')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('Leerzustand ohne axe-Verstoesse', async () => {
    stubFetch({ [`GET ${WS}/test-cases`]: () => json([]) })
    const { container } = renderList({ entity, agents })
    await screen.findByText('Noch keine Prüffälle')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('Formular-Dialog ohne axe-Verstoesse', async () => {
    stubFetch({ [`GET ${WS}/test-cases`]: () => json([]) })
    renderList({ entity, agents })
    fireEvent.click(await screen.findByRole('button', { name: 'Prüffall anlegen' }))
    const dialog = await screen.findByRole('dialog')
    expect(await axe(dialog)).toHaveNoViolations()
  })
})
