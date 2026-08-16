import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { kbNode, stubFetch } from '../test-utils'

import { KbNodeDetailPage } from './KbNodeDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('KbNodeDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    stubFetch([
      [
        '/kb/neighbors',
        [
          {
            node: kbNode({ id: 'node-2', content: 'Die Nachfrage blieb konstant.' }),
            edge_type: 'co_occurs_with',
            direction: 'out',
            co_n: 42,
          },
        ],
      ],
      ['/kb/nodes/node-1', kbNode()],
    ])

    const { container } = renderInRoutes(<KbNodeDetailPage />, {
      path: '/w/:workspaceId/workarea/kb/:nodeId',
      initialEntries: ['/w/ws-1/workarea/kb/node-1'],
    })

    await waitFor(() => {
      expect(screen.getByText('Die Nachfrage blieb konstant.')).toBeInTheDocument()
    })

    expect(await axe(container)).toHaveNoViolations()
  })
})
