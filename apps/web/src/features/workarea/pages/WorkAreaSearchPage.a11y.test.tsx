import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { area, stubFetch } from '../test-utils'

import { WorkAreaSearchPage } from './WorkAreaSearchPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('WorkAreaSearchPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    stubFetch([
      [
        '/workarea-search',
        [
          {
            anchor: 'art-1#bbbbbbbb',
            artifact_id: 'art-1',
            block_id: 'bbbbbbbb',
            title: 'Preisliste 2026',
            snippet: 'Der Preis stieg um 8 %.',
            score: 0.9,
            area_id: 'area-1',
          },
        ],
      ],
      ['/work-areas', [area()]],
    ])

    const { container } = renderInRoutes(<WorkAreaSearchPage />, {
      path: '/w/:workspaceId/workarea/search',
      initialEntries: ['/w/ws-1/workarea/search?q=preis'],
    })

    await waitFor(() => {
      expect(screen.getByText('Der Preis stieg um 8 %.')).toBeInTheDocument()
    })

    expect(await axe(container)).toHaveNoViolations()
  })
})
