import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { artifact, stubFetch } from '../test-utils'

import { ArtifactDetailPage } from './ArtifactDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ArtifactDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    stubFetch([
      [
        '/wa-artifacts/art-1',
        {
          artifact_id: 'art-1',
          title: 'Preisliste 2026',
          rev: 2,
          markdown: '# Preisliste [#aaaaaaaa]\n\nDer Preis stieg um 8 %. [#bbbbbbbb]',
        },
      ],
      ['/work-areas/area-1/artifacts', [artifact()]],
    ])

    const { container } = renderInRoutes(<ArtifactDetailPage />, {
      path: '/w/:workspaceId/workarea/areas/:areaId/artifacts/:artifactId',
      initialEntries: ['/w/ws-1/workarea/areas/area-1/artifacts/art-1'],
    })

    await waitFor(() => {
      expect(screen.getByText('# Preisliste')).toBeInTheDocument()
    })

    expect(await axe(container)).toHaveNoViolations()
  })
})
