import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { agent, area, artifact, grant, stubFetch, waTable } from '../test-utils'

import { AreaDetailPage } from './AreaDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

/**
 * Rendert die Seite mit allen drei Tabs und wartet, bis der Default-Tab
 * (Inhalte) seine Daten zeigt. Liefert den Container fuer den axe-Lauf.
 */
async function renderLoaded(): Promise<HTMLElement> {
  stubFetch([
    ['/work-areas/area-1/grants', [grant()]],
    ['/work-areas/area-1/artifacts', [artifact()]],
    ['/work-areas/area-1/tables', [waTable()]],
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
  return container
}

// Jeder Tab braucht einen eigenen axe-Lauf — TabsContent rendert nur den
// aktiven Tab, ein einzelner Check saehe die anderen Panels nie.
//
// Bewusst ein Test pro Tab statt drei Laeufe in einem: ein axe-Lauf ueber die
// ganze Seite kostet in jsdom isoliert ~0,5 s, in der vollen Suite unter
// CPU-Last bis ~0,9 s; dazu kommen die `getByRole(..., { name })`-Abfragen
// (bis ~0,8 s). Alle drei Tabs in EINEM Test summierten sich auf 4,3–5,1 s
// und rissen das 5-s-Default-Timeout (CI-Run 37162917703). Getrennt hat jeder
// Tab sein eigenes Budget — ohne ein Timeout hochzusetzen.
describe('AreaDetailPage (a11y)', () => {
  it('hat keine axe-Violations — Inhalte', async () => {
    const container = await renderLoaded()

    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations — Tabellen', async () => {
    const container = await renderLoaded()

    fireEvent.click(screen.getByRole('tab', { name: 'Tabellen' }))
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'preisliste' })).toBeInTheDocument()
    })
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations — Zugriffe', async () => {
    const container = await renderLoaded()

    // Der Grants-Tab traegt zusaetzlich Select + Aktionsspalte.
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Recht' })).toBeInTheDocument()
    })
    expect(await axe(container)).toHaveNoViolations()
  })
})
