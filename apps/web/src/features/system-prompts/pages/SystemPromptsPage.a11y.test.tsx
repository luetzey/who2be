import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SystemPromptTemplate } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { SystemPromptsPage } from './SystemPromptsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SystemPromptsPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const templates: SystemPromptTemplate[] = [
      {
        id: 'sp1',
        workspace_id: 'ws-1',
        owner_id: 'o1',
        name: 'Support-Template',
        slug: 'support-template',
        current_version: 1,
        current_status: 'active',
        has_pending_draft: false,
        content: { description: 'd', body: '[]' },
        created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify(templates), { status: 200 })),
    )

    const { container } = renderInRoutes(<SystemPromptsPage />, {
      path: '/w/:workspaceId/system-prompts',
      initialEntries: ['/w/ws-1/system-prompts'],
    })

    await waitFor(() => {
      expect(screen.getByText('Support-Template')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
