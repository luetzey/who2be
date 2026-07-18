import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

// BlockNote-Insel mocken — in jsdom nicht mountfaehig (Muster aus
// ResourceDetailPage.a11y.test.tsx). ThemeProvider kommt real ueber das
// AppLayout von renderInRoutes, daher kein theme-context-Mock noetig.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))

import { ToolDetailPage } from './ToolDetailPage'

const WS_PREFIX = '/v1/workspaces/ws-1'

const adminMe: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'o1',
      name: 'Org',
      slug: 'org',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'admin' }],
    },
  ],
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ToolDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout (voll bestueckte Detail-Sicht)', async () => {
    const tool = {
      id: 't1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Todoist',
      alias: 'todo',
      current_version: 2,
      current_status: 'draft',
      content: {
        display_name: 'Todoist',
        mcp_server_name: 'Todoist MCP',
        tool_names: ['add_task', 'list_tasks'],
        usage_notes: '[]',
        fallback_note: 'Kein Fallback definiert.',
        tags: ['produktivitaet'],
      },
      created_at: '2026-07-18T12:00:00Z',
      updated_at: '2026-07-18T12:00:00Z',
    }
    const versionContent = tool.content
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = new URL(String(input)).pathname
        if (path === `${WS_PREFIX}/external_tools/t1`) return jsonResponse(tool)
        if (path === `${WS_PREFIX}/external_tools/t1/versions`)
          return jsonResponse([
            { version: 1, status: 'active', content: versionContent, created_by: 'o1', created_at: 't' },
            { version: 2, status: 'draft', content: versionContent, created_by: 'o1', created_at: 't' },
          ])
        // AppShell-/Layout-Nebenfetches tolerant beantworten.
        return jsonResponse([])
      }),
    )

    const { container } = renderInRoutes(<ToolDetailPage />, {
      path: '/w/:workspaceId/tools/:id',
      initialEntries: ['/w/ws-1/tools/t1'],
      me: adminMe,
    })

    await waitFor(() => {
      expect(screen.getByText('Todoist')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
