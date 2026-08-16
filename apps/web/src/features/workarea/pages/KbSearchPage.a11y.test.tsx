import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { stubFetch } from '../test-utils'

import { KbSearchPage } from './KbSearchPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('KbSearchPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    stubFetch([
      [
        '/kb-search',
        [
          {
            node_id: 'node-1',
            anchor: 'node:node-1',
            snippet: 'Der Listenpreis stieg 2026 um 8 Prozent.',
            tier: 'hypothesis',
            status: 'stale',
            score: 0.8,
          },
        ],
      ],
    ])

    const { container } = renderInRoutes(<KbSearchPage />, {
      path: '/w/:workspaceId/workarea/kb',
      initialEntries: ['/w/ws-1/workarea/kb?q=preis'],
    })

    await waitFor(() => {
      expect(screen.getByText('Der Listenpreis stieg 2026 um 8 Prozent.')).toBeInTheDocument()
    })

    expect(await axe(container)).toHaveNoViolations()
  })
})
