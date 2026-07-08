import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_TOOL_POLICY,
  type Agent,
  type Persona,
  type Playbook,
  type SystemPromptTemplate,
} from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { AgentDetailPage } from './AgentDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const WS_PREFIX = '/v1/workspaces/ws-1'

const agentFixture: Agent = {
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
}

const personaFixture = {
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

const playbookFixture = {
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

describe('AgentDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/agents/a1`]: () =>
        new Response(JSON.stringify(agentFixture), { status: 200 }),
      [`GET ${WS_PREFIX}/personas/p1`]: () =>
        new Response(JSON.stringify(personaFixture), { status: 200 }),
      [`GET ${WS_PREFIX}/personas/p1/playbooks`]: () =>
        new Response(JSON.stringify([playbookFixture]), { status: 200 }),
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        new Response(JSON.stringify(templateFixture), { status: 200 }),
      [`GET ${WS_PREFIX}/personas`]: () =>
        new Response(JSON.stringify([personaFixture]), { status: 200 }),
      [`GET ${WS_PREFIX}/system-prompts`]: () =>
        new Response(JSON.stringify([templateFixture]), { status: 200 }),
      [`GET ${WS_PREFIX}/tokens`]: () =>
        new Response(JSON.stringify([]), { status: 200 }),
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        const key = `${method} ${new URL(String(input)).pathname}`
        const handler = handlers[key]
        if (!handler) {
          throw new Error(`Unmocked ${key}`)
        }
        return handler()
      }),
    )

    const { container } = renderInRoutes(<AgentDetailPage />, {
      path: '/w/:workspaceId/agents/:id',
      initialEntries: ['/w/ws-1/agents/a1'],
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: 'Carla Bot' }),
      ).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByTestId('agent-hierarchy')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
