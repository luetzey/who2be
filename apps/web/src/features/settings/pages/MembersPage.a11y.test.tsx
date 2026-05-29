import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { MembersPage } from './MembersPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

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

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MembersPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/members')) {
          return new Response(
            JSON.stringify([
              {
                user_id: 'm1',
                email: 'coder@who2be.dev',
                role: 'editor',
                joined_at: '2026-05-01T10:00:00Z',
              },
            ]),
            { status: 200 },
          )
        }
        return new Response('[]', { status: 200 })
      }),
    )

    const { container } = renderInRoutes(<MembersPage />, {
      path: '/w/:workspaceId/settings/members',
      initialEntries: ['/w/ws-1/settings/members'],
      me: adminMe,
    })

    await waitFor(() => {
      expect(screen.getByText('coder@who2be.dev')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
