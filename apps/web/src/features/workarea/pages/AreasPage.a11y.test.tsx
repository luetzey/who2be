import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { agent, area, stubFetch } from '../test-utils'

import { AreasPage } from './AreasPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AreasPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    stubFetch([
      ['/agents', [agent()]],
      [
        '/work-areas',
        [
          area(),
          area({
            id: 'area-2',
            scope: 'private',
            owner_agent_id: 'agent-1',
            name: 'Privat von Recherche-Agent',
          }),
        ],
      ],
    ])

    const { container } = renderInRoutes(<AreasPage />, {
      path: '/w/:workspaceId/workarea',
      initialEntries: ['/w/ws-1/workarea'],
    })

    await waitFor(() => {
      expect(screen.getByText('Marktrecherche')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
