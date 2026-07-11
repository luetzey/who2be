import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

// BlockNote-Insel mocken — in jsdom nicht mountfaehig (Muster aus
// ResourceDetailPage.test.tsx). ThemeProvider kommt real ueber das AppLayout
// von renderInRoutes, daher kein theme-context-Mock noetig.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))

import { ResourceDetailPage } from './ResourceDetailPage'

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

describe('ResourceDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout (voll bestueckte Detail-Sicht)', async () => {
    const resource = {
      id: 'r1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Onboarding',
      current_version: 2,
      current_status: 'draft',
      content: { description: 'd', blocks: [] },
      created_at: '2026-05-24T12:00:00Z',
      updated_at: '2026-05-24T12:00:00Z',
    }
    const versionContent = { description: 'd', blocks: [] }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = new URL(String(input)).pathname
        if (path === `${WS_PREFIX}/resources/r1`) return jsonResponse(resource)
        if (path === `${WS_PREFIX}/resources/r1/versions`)
          return jsonResponse([
            { version: 1, status: 'active', content: versionContent, created_by: 'o1', created_at: 't' },
            { version: 2, status: 'draft', content: versionContent, created_by: 'o1', created_at: 't' },
          ])
        if (path === `${WS_PREFIX}/resources/r1/usages`)
          return jsonResponse([
            { playbook_id: 'pb1', playbook_name: 'Coach', block_count: 2 },
          ])
        if (path === `${WS_PREFIX}/resources/r1/sub_resources`)
          return jsonResponse([
            {
              id: 'r2',
              name: 'Glossar',
              link_scope: 'resource',
              block_id: null,
              position: 0,
              fetch_call: "fetch_resource('r2')",
            },
          ])
        if (path === `${WS_PREFIX}/resources/r1/used_by`)
          return jsonResponse([{ id: 'r3', name: 'Handbuch' }])
        if (path === `${WS_PREFIX}/feedback/resource/r1`)
          return jsonResponse({
            entity_type: 'resource',
            entity_id: 'r1',
            usage_count: 3,
            by_outcome: { applied: 2, skipped: 1 },
            by_signal: { helpful: 1 },
            recent_notes: ['Hilfreich im Onboarding.'],
          })
        // AppShell-/Layout-Nebenfetches tolerant beantworten.
        return jsonResponse([])
      }),
    )

    const { container } = renderInRoutes(<ResourceDetailPage />, {
      path: '/w/:workspaceId/resources/:id',
      initialEntries: ['/w/ws-1/resources/r1'],
      me: adminMe,
    })

    await waitFor(() => {
      expect(screen.getByText('Onboarding')).toBeInTheDocument()
    })
    // „Coach" lebt im Verwendung-Tab — erst aktivieren, dann axe pruefen.
    fireEvent.click(await screen.findByRole('tab', { name: 'Verwendung' }))
    await waitFor(() => {
      expect(screen.getByText('Coach')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
