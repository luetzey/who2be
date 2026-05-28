import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { PersonasPage } from './PersonasPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PersonasPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const personas = [
      {
        id: 'p1',
        workspace_id: 'ws-1',
        owner_id: 'o1',
        name: 'QA-Bot',
        current_version: 1,
        content: { description: 'd', system_prompt: 's', traits: [] },
        created_at: '2026-05-21T00:00:00Z',
        updated_at: '2026-05-21T00:00:00Z',
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(personas), { status: 200 })),
    )

    const { container } = renderInRoutes(<PersonasPage />, {
      path: '/w/:workspaceId/personas',
      initialEntries: ['/w/ws-1/personas'],
    })

    await waitFor(() => {
      expect(screen.getByText('QA-Bot')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
