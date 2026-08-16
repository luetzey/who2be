import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { agent, area, artifact, grant, stubFetch } from '../test-utils'

import { AreaDetailPage } from './AreaDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AreaDetailPage (a11y)', () => {
  it('hat keine axe-Violations — Inhalte wie Zugriffe', async () => {
    stubFetch([
      ['/work-areas/area-1/grants', [grant()]],
      ['/work-areas/area-1/artifacts', [artifact()]],
      ['/work-areas', [area()]],
      ['/agents', [agent(), agent({ id: 'agent-2', name: 'Zweiter Agent' })]],
    ])

    const { container } = renderInRoutes(<AreaDetailPage />, {
      path: '/w/:workspaceId/workarea/areas/:areaId',
      initialEntries: ['/w/ws-1/workarea/areas/area-1'],
    })

    await waitFor(() => {
      expect(screen.getByText('Preisliste 2026')).toBeInTheDocument()
    })
    expect(await axe(container)).toHaveNoViolations()

    // Der Grants-Tab traegt Select + Tabelle — die eigene Pruefung ist noetig,
    // TabsContent rendert nur den aktiven Tab.
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Recht' })).toBeInTheDocument()
    })
    expect(await axe(container)).toHaveNoViolations()
  })
})
