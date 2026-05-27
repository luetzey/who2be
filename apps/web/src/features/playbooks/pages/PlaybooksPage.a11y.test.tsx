import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { PlaybooksPage } from './PlaybooksPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlaybooksPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const playbooks = [
      {
        id: 'pb1',
        owner_id: 'o1',
        name: 'Coaching',
        current_version: 1,
        type: 'workflow',
        tags: ['coach'],
        triggers: null,
        content: {
          description: '',
          body: '',
          type: 'workflow',
          tags: ['coach'],
          triggers: null,
        },
        created_at: '2026-05-24T11:00:00Z',
        updated_at: '2026-05-24T11:00:00Z',
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(playbooks), { status: 200 })),
    )

    const { container } = renderInRoutes(<PlaybooksPage />, { path: '/playbooks' })

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
