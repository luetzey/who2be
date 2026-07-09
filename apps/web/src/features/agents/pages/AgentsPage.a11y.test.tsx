import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { AgentsPage } from './AgentsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AgentsPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const agents: Agent[] = [
      {
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
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify(agents), { status: 200 })),
    )

    const { container } = renderInRoutes(<AgentsPage />, {
      path: '/w/:workspaceId/agents',
      initialEntries: ['/w/ws-1/agents'],
    })

    await waitFor(() => {
      expect(screen.getByText('Carla Bot')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
