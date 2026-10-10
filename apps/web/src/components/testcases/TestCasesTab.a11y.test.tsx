import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent, type Me } from '@/api/types'
import { AgentDetailPage } from '@/features/agents/pages/AgentDetailPage'
import { PersonaDetailPage } from '@/features/personas/pages/PersonaDetailPage'
import { PlaybookDetailPage } from '@/features/playbooks/pages/PlaybookDetailPage'
import { SystemPromptDetailPage } from '@/features/system-prompts/pages/SystemPromptDetailPage'
import i18n from '@/i18n'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

// Lernschleife B4b (Spec S10 / §2.2): Einstieg „Prüffälle" in die Detail-
// seiten. Geprueft wird die Einbindung — Tab, Deep-Link `?tab=tests`, kein
// Zaehler, richtiger Filter, Laden erst bei Bedarf. Die Liste selbst testet
// TestCaseList.a11y.test.tsx.

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Inseln sind in jsdom nicht mountfaehig (Muster aus den a11y-
// Tests der Detailseiten).
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
  SuggestionMenuController: () => null,
  getDefaultReactSlashMenuItems: () => [],
  createReactInlineContentSpec: (config: unknown, implementation: unknown) => ({
    config,
    implementation,
  }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@blocknote/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@blocknote/core')>()
  return {
    ...actual,
    BlockNoteSchema: {
      create: vi.fn().mockReturnValue({
        blockSchema: {},
        inlineContentSchema: {
          placeholder: { type: 'placeholder', propSchema: {}, content: 'none' },
          text: { config: 'text' },
          link: { config: 'link' },
        },
        styleSchema: {},
      }),
    },
    defaultInlineContentSpecs: { text: {}, link: {} },
  }
})
vi.mock('@/features/personas/components/PersonaProfileEditor', () => ({
  PersonaProfileEditor: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/components/editor/system-prompt/SystemPromptEditor', () => ({
  SystemPromptEditor: () => <div data-testid="system-prompt-editor" />,
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

const WS = '/v1/workspaces/ws-1'

const editorMe: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'o1',
      name: 'Org',
      slug: 'org',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'editor' }],
    },
  ],
}

const agent: Agent = {
  id: 'a1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'coder',
  description: 'Implementiert Tickets',
  persona_id: 'p1',
  system_prompt_template_id: 'sp1',
  status: 'enabled',
  tool_policy: DEFAULT_TOOL_POLICY,
  persona_active: true,
  activatable: true,
  missing: [],
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

const persona = {
  id: 'p1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Coach',
  current_version: 1,
  content: { description: 'd', system_prompt: 's', traits: [] },
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

const playbookContent = { description: 'd', body: '', type: 'workflow', tags: [], triggers: null }
const playbook = {
  id: 'pb1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Implement',
  current_version: 1,
  current_status: 'active',
  type: 'workflow',
  tags: [],
  triggers: null,
  content: playbookContent,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

const template = {
  id: 'sp1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Support-Template',
  slug: 'support-template',
  current_version: 1,
  current_status: 'active',
  has_pending_draft: false,
  content: { description: 'Beschreibung', body: '[]' },
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

const testCase = {
  id: 'c1',
  workspace_id: 'ws-1',
  agent_id: 'a1',
  entity_type: null,
  entity_id: null,
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
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

function feedbackSummary(entityType: string, entityId: string) {
  return {
    entity_type: entityType,
    entity_id: entityId,
    usage_count: 0,
    by_outcome: {},
    by_signal: {},
    recent_notes: [],
  }
}

/**
 * Fetch-Stub fuer alle vier Detailseiten. Gibt die Anfragen an
 * `/test-cases` zurueck, damit Filter und Lade-Zeitpunkt pruefbar sind.
 */
function stubApi(cases: unknown[] = [testCase]) {
  const testCaseRequests: URL[] = []
  const bySuffix: Record<string, unknown> = {
    [`${WS}/agents`]: [agent],
    [`${WS}/agents/a1`]: agent,
    [`${WS}/personas`]: [persona],
    [`${WS}/personas/p1`]: persona,
    [`${WS}/personas/p1/versions`]: [
      { version: 1, content: persona.content, created_by: 'o1', created_at: 't' },
    ],
    [`${WS}/feedback/persona/p1`]: feedbackSummary('persona', 'p1'),
    [`${WS}/playbooks/pb1`]: playbook,
    [`${WS}/playbooks/pb1/versions`]: [
      { version: 1, status: 'active', content: playbookContent, created_by: 'o1', created_at: 't' },
    ],
    [`${WS}/feedback/playbook/pb1`]: feedbackSummary('playbook', 'pb1'),
    [`${WS}/system-prompts`]: [template],
    [`${WS}/system-prompts/sp1`]: template,
    [`${WS}/system-prompts/sp1/versions`]: [
      { version: 1, status: 'active', content: template.content, created_by: 'o1', created_at: 't' },
    ],
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input))
      if (url.pathname === `${WS}/test-cases`) {
        testCaseRequests.push(url)
        return json(cases)
      }
      if (url.pathname in bySuffix) return json(bySuffix[url.pathname])
      // Layout-/Nebenfetches (Tokens, Gedaechtnis, Beziehungen) tolerant.
      return json([])
    }),
  )
  return testCaseRequests
}

function renderPage(element: React.ReactElement, path: string, entry: string) {
  return renderInRoutes(element, { path, initialEntries: [entry], me: editorMe })
}

describe('Tab „Prüffälle" an den Element-Detailseiten (B4b)', () => {
  it.each([
    {
      label: 'Persona',
      element: <PersonaDetailPage />,
      path: '/w/:workspaceId/personas/:id',
      entry: '/w/ws-1/personas/p1',
      title: 'Coach',
      entityType: 'persona',
      entityId: 'p1',
      heading: 'Prüffälle · Persona „Coach“',
    },
    {
      label: 'Playbook',
      element: <PlaybookDetailPage />,
      path: '/w/:workspaceId/playbooks/:id',
      entry: '/w/ws-1/playbooks/pb1',
      title: 'Implement',
      entityType: 'playbook',
      entityId: 'pb1',
      heading: 'Prüffälle · Playbook „Implement“',
    },
    {
      label: 'System-Prompt',
      element: <SystemPromptDetailPage />,
      path: '/w/:workspaceId/system-prompts/:id',
      entry: '/w/ws-1/system-prompts/sp1',
      title: 'Support-Template',
      entityType: 'system_prompt_template',
      entityId: 'sp1',
      heading: 'Prüffälle · System-Prompt „Support-Template“',
    },
  ])(
    '$label: ?tab=tests oeffnet den Tab ohne Zaehler und filtert auf das Element',
    async ({ element, path, entry, title, entityType, entityId, heading }) => {
      const requests = stubApi([{ ...testCase, entity_type: entityType, entity_id: entityId }])
      renderPage(element, path, `${entry}?tab=tests`)

      const tab = await screen.findByRole('tab', { name: 'Prüffälle' })
      expect(tab).toHaveAttribute('aria-selected', 'true')
      // Spec §2.3: kein Zaehler am Tab — der Name ist genau das Wort.
      expect(tab.textContent).toBe('Prüffälle')
      expect(screen.getByText(title, { selector: 'h1' })).toBeInTheDocument()

      expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
      expect(await screen.findByTestId('test-case-row')).toHaveTextContent('Push nach Fix')
      expect(requests).toHaveLength(1)
      expect(requests[0].searchParams.get('entity_type')).toBe(entityType)
      expect(requests[0].searchParams.get('entity_id')).toBe(entityId)
      expect(requests[0].searchParams.has('agent_id')).toBe(false)
    },
  )

  it.each([
    {
      label: 'Persona',
      element: <PersonaDetailPage />,
      path: '/w/:workspaceId/personas/:id',
      entry: '/w/ws-1/personas/p1',
      title: 'Coach',
    },
    {
      label: 'Playbook',
      element: <PlaybookDetailPage />,
      path: '/w/:workspaceId/playbooks/:id',
      entry: '/w/ws-1/playbooks/pb1',
      title: 'Implement',
    },
    {
      label: 'System-Prompt',
      element: <SystemPromptDetailPage />,
      path: '/w/:workspaceId/system-prompts/:id',
      entry: '/w/ws-1/system-prompts/sp1',
      title: 'Support-Template',
    },
  ])(
    '$label: laedt Prueffaelle erst, wenn der Tab geoeffnet wird',
    async ({ element, path, entry, title }) => {
      const requests = stubApi()
      renderPage(element, path, entry)

      await screen.findByText(title, { selector: 'h1' })
      const tab = screen.getByRole('tab', { name: 'Prüffälle' })
      expect(tab).toHaveAttribute('aria-selected', 'false')
      expect(screen.queryByTestId('test-case-list')).toBeNull()
      expect(requests).toHaveLength(0)

      fireEvent.click(tab)
      expect(tab).toHaveAttribute('aria-selected', 'true')
      expect(await screen.findByTestId('test-case-row')).toBeInTheDocument()
      expect(requests).toHaveLength(1)
    },
  )

  it('setzt im Kopf die Anfuehrungszeichen der UI-Sprache (EN)', async () => {
    stubApi()
    await i18n.changeLanguage('en')
    try {
      renderPage(
        <PlaybookDetailPage />,
        '/w/:workspaceId/playbooks/:id',
        '/w/ws-1/playbooks/pb1?tab=tests',
      )
      expect(
        await screen.findByRole('heading', { name: 'Test cases · Playbook “Implement”' }),
      ).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: 'Test cases' })).toHaveAttribute(
        'aria-selected',
        'true',
      )
    } finally {
      await i18n.changeLanguage('de')
    }
  })
})

describe('Prüffälle am Agenten (Tab, Navigation §3.1)', () => {
  it('Tab ist nicht gewählt, laedt nichts und laedt beim Öffnen auf den Agenten gefiltert', async () => {
    const requests = stubApi()
    renderPage(<AgentDetailPage />, '/w/:workspaceId/agents/:id', '/w/ws-1/agents/a1')

    await screen.findByRole('heading', { level: 1, name: 'coder' })
    const tab = screen.getByRole('tab', { name: 'Prüffälle' })
    expect(tab).toHaveAttribute('aria-selected', 'false')
    // Wie an den Elementen: kein Zaehler am Tab.
    expect(tab.textContent).toBe('Prüffälle')
    expect(screen.queryByTestId('agent-test-cases')).toBeNull()
    expect(requests).toHaveLength(0)

    fireEvent.click(tab)
    expect(tab).toHaveAttribute('aria-selected', 'true')
    const section = await screen.findByTestId('agent-test-cases')
    expect(await within(section).findByTestId('test-case-row')).toBeInTheDocument()
    expect(requests).toHaveLength(1)
    expect(requests[0].searchParams.get('agent_id')).toBe('a1')
    expect(requests[0].searchParams.has('entity_type')).toBe(false)
  })

  it.each(['#tests', '?tab=tests'])('%s öffnet den Tab direkt', async (suffix) => {
    const requests = stubApi()
    renderPage(<AgentDetailPage />, '/w/:workspaceId/agents/:id', `/w/ws-1/agents/a1${suffix}`)

    const section = await screen.findByTestId('agent-test-cases')
    expect(screen.getByRole('tab', { name: 'Prüffälle' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(
      await within(section).findByRole('heading', { name: 'Prüffälle · coder' }),
    ).toBeInTheDocument()
    await waitFor(() => expect(requests).toHaveLength(1))
  })
})

describe('Prüffälle-Einstieg (a11y)', () => {
  it.each([
    {
      element: <PersonaDetailPage />,
      path: '/w/:workspaceId/personas/:id',
      entry: '/w/ws-1/personas/p1?tab=tests',
    },
    {
      element: <PlaybookDetailPage />,
      path: '/w/:workspaceId/playbooks/:id',
      entry: '/w/ws-1/playbooks/pb1?tab=tests',
    },
    {
      element: <SystemPromptDetailPage />,
      path: '/w/:workspaceId/system-prompts/:id',
      entry: '/w/ws-1/system-prompts/sp1?tab=tests',
    },
  ])('Element-Tab $entry hat keine axe-Violations im AppLayout', async ({ element, path, entry }) => {
    stubApi()
    const { container } = renderPage(element, path, entry)
    await screen.findByTestId('test-case-row')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('Agent-Seite (Standardansicht, Tab Überblick) hat keine axe-Violations', async () => {
    stubApi()
    const { container } = renderPage(
      <AgentDetailPage />,
      '/w/:workspaceId/agents/:id',
      '/w/ws-1/agents/a1',
    )
    await screen.findByTestId('agent-hierarchy')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('Agent-Tab „Prüffälle“ (über alten Anker #tests) hat keine axe-Violations im AppLayout', async () => {
    stubApi()
    const { container } = renderPage(
      <AgentDetailPage />,
      '/w/:workspaceId/agents/:id',
      '/w/ws-1/agents/a1#tests',
    )
    await within(await screen.findByTestId('agent-test-cases')).findByTestId('test-case-row')
    expect(await axe(container)).toHaveNoViolations()
  })
})
