import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { agent, area, artifact, grant, renderAt, stubFetch, waTable } from '../test-utils'

import { AreaDetailPage } from './AreaDetailPage'

const PATH = '/w/:workspaceId/workarea/areas/:areaId'
const ENTRY = ['/w/ws-1/workarea/areas/area-1']

let role = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn() },
}))

beforeEach(() => {
  role = 'editor'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AreaDetailPage', () => {
  it('zeigt die Inhalte eines geteilten Bereichs', async () => {
    stubFetch([
      ['/work-areas/area-1/artifacts', [artifact()]],
      ['/work-areas', [area()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Preisliste 2026')).toBeInTheDocument()
    })
    expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
  })

  it('bietet privaten Bereichen keinen Zugriffs-Tab an', async () => {
    // Private Areas sind serverseitig nicht grantbar (403 `area_forbidden`) —
    // ein Tab dorthin waere eine Sackgasse.
    stubFetch([
      ['/work-areas/area-1/artifacts', [artifact()]],
      ['/work-areas', [area({ scope: 'private', owner_agent_id: 'agent-1' })]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Privater Bereich')).toBeInTheDocument()
    })
    expect(screen.queryByRole('tab', { name: 'Zugriffe' })).not.toBeInTheDocument()
  })

  it('listet Freigaben mit aufgeloestem Agenten-Namen', async () => {
    stubFetch([
      ['/work-areas/area-1/grants', [grant({ level: 'write' })]],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area()]],
      ['/agents', [agent()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))

    await waitFor(() => {
      expect(screen.getByText('Recherche-Agent')).toBeInTheDocument()
    })
    expect(screen.getByRole('combobox', { name: 'Recht' })).toHaveValue('write')
  })

  it('sperrt Freigaben fuer Viewer', async () => {
    role = 'viewer'
    stubFetch([
      ['/work-areas/area-1/grants', [grant()]],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area()]],
      ['/agents', [agent()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Recht' })).toBeDisabled()
    })
    expect(screen.getByRole('button', { name: /Entfernen/ })).toBeDisabled()
  })

  it('zeigt den Tabellen-Tab in geteilten Bereichen und listet den Katalog', async () => {
    stubFetch([
      ['/work-areas/area-1/tables', [waTable()]],
      ['/work-areas/area-1/artifacts', [artifact()]],
      ['/work-areas', [area()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Tabellen' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Tabellen' }))

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'preisliste' })).toBeInTheDocument()
    })
    // Spaltenzahl statt Zeilenzahl: `row_count` ist im Katalog-Pfad null.
    expect(screen.getByRole('cell', { name: '3' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'preisliste' })).toHaveAttribute(
      'href',
      '/w/ws-1/workarea/areas/area-1/tables/tbl-1',
    )
  })

  it('bietet auch privaten Bereichen den Tabellen-Tab an', async () => {
    // Gerade private Agent-Bereiche sind der Ort, an dem Tabellen entstehen —
    // anders als Freigaben sind sie dort kein Sonderfall.
    stubFetch([
      ['/work-areas/area-1/tables', [waTable()]],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area({ scope: 'private', owner_agent_id: 'agent-1' })]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Tabellen' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Tabellen' }))

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'preisliste' })).toBeInTheDocument()
    })
    expect(screen.queryByRole('tab', { name: 'Zugriffe' })).not.toBeInTheDocument()
  })

  it('zeigt einen leeren Tabellen-Katalog ohne Anlege-Aufforderung', async () => {
    stubFetch([
      ['/work-areas/area-1/tables', []],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Tabellen' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Tabellen' }))

    await waitFor(() => {
      expect(screen.getByText('Noch keine Tabellen')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: /Tabelle/ })).not.toBeInTheDocument()
  })

  it('meldet einen nicht sichtbaren Bereich als nicht gefunden', async () => {
    stubFetch([['/work-areas', []]])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(
        screen.getByText('Dieser Bereich existiert nicht oder ist für dich nicht sichtbar.'),
      ).toBeInTheDocument()
    })
  })
})

// Responsive-Vertrag #572 (AK 3, 4 und 5) fuer die beiden Komponenten, die
// diese Page komponiert: `AreaGrants` und `ArtifactList`. jsdom hat kein
// Layout — Klassen-Vertrag zu den gerenderten Messungen in
// .claude/plan/2026-09-23-1100_572-w3-workarea-responsive-audit.md.
describe('AreaDetailPage — Responsive (#572)', () => {
  it('haelt das Rollen-Select in der Tabellenzelle bedienbar (AK 4)', async () => {
    // Gemessen: die Tabellenspalte schrumpfte das Control bei 320 px auf 33 px
    // Breite. `min-w-32` sitzt als `className` an der Aufrufstelle — das
    // `Select`-Primitive bleibt unberuehrt. Woertlich die Loesung, die das
    // Schwesterpaket #568 an der Mitgliedertabelle gewaehlt hat.
    stubFetch([
      ['/work-areas/area-1/grants', [grant()]],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area()]],
      ['/agents', [agent()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Recht' })).toHaveClass('min-w-32')
    })
  })

  it('haelt den Entfernen-Knopf auf dem 40-px-Hit-Target aus AK 3', async () => {
    // Die Zahl kommt aus AK 3 dieses Issues, nicht aus der Norm:
    // design-language.md §11 setzt den Floor auf >= 32 px, womit die gemessenen
    // 36 px (`size="sm"`) zulaessig waren; 40 px ist dort die Praeferenz
    // `size="default"`, die dieses Paket unterhalb `md` verbindlich macht. Ab
    // `md` faellt die Zeilen-Aktion auf die Desktop-Dichte zurueck.
    stubFetch([
      ['/work-areas/area-1/grants', [grant()]],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area()]],
      ['/agents', [agent()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Entfernen/ })).toHaveClass('min-h-10')
    })
    expect(screen.getByRole('button', { name: /Entfernen/ })).toHaveClass('md:min-h-0')
  })

  it('laesst die Quell-Angabe eines Artefakts umbrechen (AK 5)', async () => {
    // Gemessen der schwerste Ueberlaeufer der Domaene: eine Quell-URL lief bei
    // 320 px um 344 px und bei 375 px um 289 px ueber die Innenkante. Eine URL
    // ist hier der Regelfall (`source_url` aus dem Ingest), nicht der Ausreisser.
    stubFetch([
      [
        '/work-areas/area-1/artifacts',
        [
          artifact({
            source_url: 'https://www.beispielgesellschaft.example/berichte/2026/q3/analyse.pdf',
          }),
        ],
      ],
      ['/work-areas', [area()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(
        screen.getByText(
          'Quelle: https://www.beispielgesellschaft.example/berichte/2026/q3/analyse.pdf',
        ),
      ).toHaveClass('break-all')
    })
  })
})
