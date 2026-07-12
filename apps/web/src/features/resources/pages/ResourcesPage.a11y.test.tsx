import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { ResourcesPage } from './ResourcesPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ResourcesPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const resources = [
      {
        id: 'r1',
        workspace_id: 'ws-1',
        owner_id: 'o1',
        name: 'Runbook',
        slug: 'runbook',
        current_version: 1,
        current_status: 'active',
        has_pending_draft: false,
        content: { description: '', blocks: [] },
        created_at: '2026-05-24T11:00:00Z',
        updated_at: '2026-05-24T11:00:00Z',
        playbook_link_count: 2,
        sub_resources: [
          { id: 'r2', name: 'Glossar', status: 'active', version: 1 },
          { id: 'r3', name: 'Anhang', status: 'draft', version: 2 },
        ],
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(resources), { status: 200 })),
    )

    const { container } = renderInRoutes(<ResourcesPage />, {
      path: '/w/:workspaceId/resources',
      initialEntries: ['/w/ws-1/resources'],
    })

    await waitFor(() => {
      expect(screen.getByText('Runbook')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
