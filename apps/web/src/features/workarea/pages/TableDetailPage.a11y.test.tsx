import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { stubFetch, tableDescription, tableQueryResult, waTable } from '../test-utils'

import { TableDetailPage } from './TableDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('TableDetailPage (a11y)', () => {
  it('hat keine axe-Violations — Schema, Konventionen und Vorschau', async () => {
    stubFetch([
      // Spezifischer Pfad zuerst: `/wa-tables/tbl-1` ist Praefix von `.../query`.
      ['/wa-tables/tbl-1/query', tableQueryResult()],
      [
        '/wa-tables/tbl-1',
        tableDescription({
          conventions: [
            {
              id: 'conv-1',
              area_id: 'area-1',
              source_name: 'Lieferantenliste',
              convention: { waehrung: 'EUR' },
              created_by: 'u1',
              created_at: '2026-08-01T10:00:00Z',
              updated_at: '2026-08-01T10:00:00Z',
            },
          ],
        }),
      ],
      ['/work-areas/area-1/tables', [waTable()]],
    ])

    const { container } = renderInRoutes(<TableDetailPage />, {
      path: '/w/:workspaceId/workarea/areas/:areaId/tables/:tableId',
      initialEntries: ['/w/ws-1/workarea/areas/area-1/tables/tbl-1'],
    })

    await waitFor(() => {
      expect(screen.getByText('Basis-Lizenz')).toBeInTheDocument()
    })
    expect(await axe(container)).toHaveNoViolations()
  })
})
