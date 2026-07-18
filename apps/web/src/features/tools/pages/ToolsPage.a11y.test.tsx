import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { ToolsPage } from './ToolsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ToolsPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const tools = [
      {
        id: 't1',
        workspace_id: 'ws-1',
        owner_id: 'o1',
        name: 'Todoist',
        alias: 'todo',
        current_version: 1,
        current_status: 'active',
        has_pending_draft: false,
        content: {
          display_name: 'Todoist App',
          mcp_server_name: 'Todoist MCP',
          tool_names: ['add_task'],
          usage_notes: '[]',
          fallback_note: null,
          tags: ['produktivitaet'],
        },
        created_at: '2026-07-18T11:00:00Z',
        updated_at: '2026-07-18T11:00:00Z',
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(tools), { status: 200 })),
    )

    const { container } = renderInRoutes(<ToolsPage />, {
      path: '/w/:workspaceId/tools',
      initialEntries: ['/w/ws-1/tools'],
    })

    await waitFor(() => {
      expect(screen.getByText('Todoist')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
