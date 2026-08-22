import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_TOOL_POLICY,
  type Agent,
  type Me,
  type Persona,
  type Playbook,
  type SystemPromptTemplate,
} from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { AgentDetailPage } from './AgentDetailPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

const WS_PREFIX = '/v1/workspaces/ws-1'

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'a1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Carla Bot',
    description: 'Support-Agent',
    persona_id: 'p1',
    system_prompt_template_id: 'sp1',
    status: 'enabled',
    tool_policy: DEFAULT_TOOL_POLICY,
    persona_active: true,
    activatable: true,
    missing: [],
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  }
}

const personaFixture: Persona = {
  id: 'p1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Coach',
  current_version: 3,
  content: { description: 'd', system_prompt: 's', traits: [] },
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
} as unknown as Persona

const templateFixture: SystemPromptTemplate = {
  id: 'sp1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Support-Template',
  slug: 'support-template',
  current_version: 2,
  current_status: 'active',
  has_pending_draft: false,
  content: { description: 'd', body: '[]' },
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

const playbookFixture: Playbook = {
  id: 'pb1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Coaching',
  current_version: 1,
  type: 'workflow',
  tags: [],
  triggers: null,
  content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
} as unknown as Playbook

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

// Handler fuer einen vollstaendig verknuepften Agent (Persona + Template +
// Playbooks + Listen fuer die Selects + Tokens-Sektion).
function fullHandlers(loadedAgent: Agent): Record<string, () => Response> {
  return {
    [`GET ${WS_PREFIX}/agents/${loadedAgent.id}`]: () => jsonResponse(loadedAgent),
    [`GET ${WS_PREFIX}/personas/p1`]: () => jsonResponse(personaFixture),
    [`GET ${WS_PREFIX}/personas/p1/playbooks`]: () => jsonResponse([playbookFixture]),
    [`GET ${WS_PREFIX}/system-prompts/sp1`]: () => jsonResponse(templateFixture),
    [`GET ${WS_PREFIX}/personas`]: () => jsonResponse([personaFixture]),
    [`GET ${WS_PREFIX}/system-prompts`]: () => jsonResponse([templateFixture]),
    [`GET ${WS_PREFIX}/tokens`]: () => jsonResponse([]),
    [`GET ${WS_PREFIX}/agents/${loadedAgent.id}/memories`]: () => jsonResponse([]),
  }
}

function stubFetchRoutes(handlers: Record<string, () => Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const key = `${method} ${new URL(String(input)).pathname}`
    const handler = handlers[key]
    if (!handler) {
      throw new Error(`Unmocked ${key}`)
    }
    return handler()
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPage() {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents/a1']}>
          <Routes>
            <Route path="/w/:workspaceId/agents/:id" element={<AgentDetailPage />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('AgentDetailPage', () => {
  it('aktivierbarer Agent: Hierarchie, Aktionen, Connector- und Token-Sektion', async () => {
    stubFetchRoutes(fullHandlers(agent()))

    renderPage()

    // level 1 = PageHeader (die Hierarchie-Card wiederholt den Namen als Card-Titel).
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Carla Bot' }),
    ).toBeInTheDocument()

    // Hierarchie-Tree: Template + Persona + verknuepftes Playbook.
    const hierarchy = await screen.findByTestId('agent-hierarchy')
    expect(within(hierarchy).getByText('Support-Template')).toBeInTheDocument()
    expect(within(hierarchy).getByText('Coach')).toBeInTheDocument()
    expect(within(hierarchy).getByText('Coaching')).toBeInTheDocument()
    expect(
      within(hierarchy).queryByText('— nicht geladen —'),
    ).not.toBeInTheDocument()

    // Aktivierbar: kein Missing-Hinweis, Duplizieren + Copy-Prompt aktiv.
    expect(screen.queryByTestId('agent-missing-notice')).not.toBeInTheDocument()
    expect(screen.getByTestId('duplicate-agent')).toBeEnabled()
    expect(screen.getByTestId('copy-prompt-primary')).toBeEnabled()
    // Nicht managed: Loeschen vorhanden, keine Notice.
    expect(screen.getByTestId('delete-agent-trigger')).toBeInTheDocument()
    expect(screen.queryByTestId('managed-notice')).not.toBeInTheDocument()

    // Connector- + Token-Sektion liegen im Tab „Verbindung".
    fireEvent.click(screen.getByRole('tab', { name: 'Verbindung' }))

    // Connector-Sektion mit agent-eindeutiger URL (Agent im Pfad, Issue #404).
    expect(screen.getByText('Claude-Connector')).toBeInTheDocument()
    const urlInput = screen.getByLabelText<HTMLInputElement>('Server-URL')
    expect(urlInput.value).toContain('/a/a1')

    // Token-Sektion gerendert.
    expect(screen.getByText('API-Tokens')).toBeInTheDocument()
  })

  it('leere Huelle: Missing-Zweige, gesperrtes Aktiv-Setzen und Duplizieren', async () => {
    const hollow = agent({
      persona_id: null,
      system_prompt_template_id: null,
      status: 'disabled',
      persona_active: false,
      activatable: false,
      missing: ['persona', 'template'],
    })
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1`]: () => jsonResponse(hollow),
      // Keine Persona/Template-Refs — nur die Listen + Tokens werden geladen.
      [`GET ${WS_PREFIX}/personas`]: () => jsonResponse([personaFixture]),
      [`GET ${WS_PREFIX}/system-prompts`]: () => jsonResponse([templateFixture]),
      [`GET ${WS_PREFIX}/tokens`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/agents/a1/memories`]: () => jsonResponse([]),
    })

    renderPage()

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Carla Bot' }),
    ).toBeInTheDocument()

    // Hierarchie zeigt die Nicht-geladen-Zweige.
    const hierarchy = screen.getByTestId('agent-hierarchy')
    expect(within(hierarchy).getAllByText('— nicht geladen —')).toHaveLength(2)
    expect(within(hierarchy).getByText('Keine Playbooks verknüpft.')).toBeInTheDocument()

    // Missing-Hinweis nennt die konkreten Luecken.
    const missingNotice = await screen.findByTestId('agent-missing-notice')
    expect(missingNotice).toHaveTextContent('Persona verknüpfen')
    expect(missingNotice).toHaveTextContent('Systemprompt verknüpfen')

    // "Aktiv" ist im Status-Select gesperrt, Duplizieren ausgegraut.
    expect(screen.getByRole('option', { name: 'Aktiv' })).toBeDisabled()
    expect(screen.getByTestId('duplicate-agent')).toBeDisabled()
  })

  it('managed Agent: Notice, read-only Editor, kein Loeschen — Duplizieren funktioniert', async () => {
    const managed = agent({ is_managed: true, name: 'Builder' })
    const copy = agent({ id: 'a2', name: 'Builder (Kopie)' })
    const copyCalls: unknown[] = []
    stubFetchRoutes({
      ...fullHandlers(managed),
      ...fullHandlers(copy),
      [`POST ${WS_PREFIX}/agents/a1/copy`]: () => {
        copyCalls.push(true)
        return jsonResponse(copy)
      },
    })

    renderPage()

    expect(await screen.findByTestId('managed-notice')).toBeInTheDocument()
    // Duplicate-Hinweis der Notice (nur auf der Agent-Detail-Page).
    expect(
      screen.getByText(
        'Dupliziere den Agenten, um eine eigene, frei anpassbare Kopie zu erhalten.',
      ),
    ).toBeInTheDocument()
    // Kein Loesch-Button, Editor gesperrt. ("Name" ist doppelt gelabelt —
    // Editor-Formular + Token-Formular — daher ueber den Wert selektieren.)
    expect(screen.queryByTestId('delete-agent-trigger')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByDisplayValue('Builder')).toBeInTheDocument()
    })
    expect(screen.getByDisplayValue('Builder')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled()

    // Duplizieren bleibt erlaubt und navigiert zur Kopie.
    const duplicate = screen.getByTestId('duplicate-agent')
    expect(duplicate).toBeEnabled()
    fireEvent.click(duplicate)

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Agent dupliziert.')
    })
    expect(copyCalls).toHaveLength(1)
    // Kopie ist nicht managed: Loeschen wieder verfuegbar.
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: 'Builder (Kopie)' }),
      ).toBeInTheDocument()
    })
    expect(screen.queryByTestId('managed-notice')).not.toBeInTheDocument()
    expect(screen.getByTestId('delete-agent-trigger')).toBeInTheDocument()
  })

  it('zeigt einen ErrorAlert, wenn der Agent nicht geladen werden kann', async () => {
    stubFetchRoutes({
      [`GET ${WS_PREFIX}/agents/a1`]: () => new Response('kaputt', { status: 500 }),
      [`GET ${WS_PREFIX}/personas`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/system-prompts`]: () => jsonResponse([]),
      [`GET ${WS_PREFIX}/tokens`]: () => jsonResponse([]),
    })

    renderPage()

    expect(await screen.findByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
    expect(screen.queryByTestId('agent-hierarchy')).not.toBeInTheDocument()
  })

  it('zeigt den Save-Fehler des Editors als ErrorAlert', async () => {
    stubFetchRoutes({
      ...fullHandlers(agent()),
      [`PUT ${WS_PREFIX}/agents/a1`]: () =>
        new Response(JSON.stringify({ detail: 'Name bereits vergeben.' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }),
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByDisplayValue('Carla Bot')).toBeInTheDocument()
    })

    const submitButton = screen.getByRole('button', { name: 'Speichern' })
    fireEvent.click(submitButton)
    const form = submitButton.closest('form')
    if (form !== null) {
      fireEvent.submit(form)
    }

    expect(await screen.findByText('Name bereits vergeben.')).toBeInTheDocument()
    expect(notify.success).not.toHaveBeenCalled()
  })
})
