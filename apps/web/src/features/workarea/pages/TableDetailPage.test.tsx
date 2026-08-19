import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SourceConvention } from '@/api/types'

import { renderAt, stubFetch, tableDescription, tableQueryResult, waTable } from '../test-utils'

import { TableDetailPage } from './TableDetailPage'

const PATH = '/w/:workspaceId/workarea/areas/:areaId/tables/:tableId'
const ENTRY = ['/w/ws-1/workarea/areas/area-1/tables/tbl-1']

const notifySuccess = vi.fn()
const notifyError = vi.fn()

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

/**
 * Der Query-Pfad muss VOR dem describe-Pfad stehen: `stubFetch` matcht per
 * Teilstring, und `/wa-tables/tbl-1` ist Praefix von `/wa-tables/tbl-1/query`.
 * Ohne die Reihenfolge bekaeme die Query die describe-Antwort.
 */
function stubTableRoutes(): void {
  stubFetch([
    ['/wa-tables/tbl-1/query', tableQueryResult()],
    ['/wa-tables/tbl-1', tableDescription()],
    ['/work-areas/area-1/tables', [waTable()]],
  ])
}

let anchorClick: ReturnType<typeof vi.fn>
let createdAnchors: HTMLAnchorElement[]

beforeAll(() => {
  // Radix-Dropdown braucht Pointer-Capture + scrollIntoView, JSDOM hat beides
  // nicht (Muster `EntityExportButton.test.tsx`).
  for (const fn of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

beforeEach(() => {
  notifySuccess.mockReset()
  notifyError.mockReset()
  createdAnchors = []
  anchorClick = vi.fn()
  const realCreate = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = realCreate(tag)
    if (tag === 'a') {
      el.click = anchorClick as () => void
      createdAnchors.push(el as HTMLAnchorElement)
    }
    return el
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

// Der createElement-Spy sammelt AUCH die Anchor von `<Link>` — gesucht ist die
// eine mit `download`-Attribut, die `downloadFile` erzeugt.
function downloadName(): string | undefined {
  return createdAnchors.find((anchor) => anchor.download !== '')?.download
}

describe('TableDetailPage', () => {
  it('zeigt Schema und Kategorisierungs-Spalten', async () => {
    stubTableRoutes()
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'preisliste' })).toBeInTheDocument()
    })
    expect(screen.getByRole('table', { name: 'Schema' })).toBeInTheDocument()
    expect(screen.getByText('numeric')).toBeInTheDocument()
    expect(screen.getByText('128 Zeilen')).toBeInTheDocument()
    expect(screen.getByText('Kategorisierung liest: produkt')).toBeInTheDocument()
    expect(screen.getByText('Kategorisierung schreibt: kategorie')).toBeInTheDocument()
  })

  it('rendert die Daten-Vorschau aus dem Query-Ergebnis', async () => {
    stubTableRoutes()
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Basis-Lizenz')).toBeInTheDocument()
    })
    expect(screen.getByText('Zeigt die neuesten 50 Zeilen von 128.')).toBeInTheDocument()
    expect(screen.getByText('Team-Lizenz')).toBeInTheDocument()
    // NULL-Zelle wird als Platzhalter gezeigt, nicht als leere Zelle.
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('fragt die Vorschau mit explizit quotierten Spalten ab (kein SELECT *)', async () => {
    stubTableRoutes()
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Basis-Lizenz')).toBeInTheDocument()
    })
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>
    const queryCall = fetchMock.mock.calls.find(
      (call: unknown[]) => typeof call[0] === 'string' && call[0].includes('/query'),
    )
    expect(queryCall).toBeDefined()
    const body = JSON.parse((queryCall?.[1] as RequestInit).body as string) as {
      sql: string
      format: string
      limit: number
    }
    expect(body.sql).toBe(
      'SELECT "occurred_at", "produkt", "preis" FROM "preisliste" ORDER BY "occurred_at" DESC',
    )
    expect(body.format).toBe('json')
    expect(body.limit).toBe(50)
  })

  it('zeigt Quell-Konventionen, wenn welche hinterlegt sind', async () => {
    const convention: SourceConvention = {
      id: 'conv-1',
      area_id: 'area-1',
      source_name: 'Lieferantenliste',
      convention: { waehrung: 'EUR', dezimaltrenner: ',' },
      created_by: 'u1',
      created_at: '2026-08-01T10:00:00Z',
      updated_at: '2026-08-01T10:00:00Z',
    }
    stubFetch([
      ['/wa-tables/tbl-1/query', tableQueryResult()],
      ['/wa-tables/tbl-1', tableDescription({ conventions: [convention] })],
      ['/work-areas/area-1/tables', [waTable()]],
    ])
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Quell-Konventionen')).toBeInTheDocument()
    })
    expect(screen.getByText('Lieferantenliste')).toBeInTheDocument()
    expect(screen.getByText('waehrung: EUR')).toBeInTheDocument()
  })

  it('weist auf ein beschnittenes Ergebnis hin', async () => {
    stubFetch([
      ['/wa-tables/tbl-1/query', tableQueryResult({ truncated: true })],
      ['/wa-tables/tbl-1', tableDescription()],
      ['/work-areas/area-1/tables', [waTable()]],
    ])
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(
        screen.getByText(
          'Das Ergebnis wurde beschnitten — die Tabelle enthält mehr Zeilen als hier stehen.',
        ),
      ).toBeInTheDocument()
    })
  })

  it('exportiert als CSV und löst einen Download aus', async () => {
    stubTableRoutes()
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByTestId('export-table-trigger')).toBeInTheDocument()
    })
    // Radix oeffnet auf pointerdown+up; in JSDOM kommen wir per Enter ans Ziel.
    fireEvent.keyDown(screen.getByTestId('export-table-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-table-csv'))

    await waitFor(() => {
      expect(anchorClick).toHaveBeenCalled()
    })
    expect(downloadName()).toBe('who2be-table-preisliste.csv')
    expect(notifySuccess).toHaveBeenCalledWith('Export gestartet.')
  })

  it('exportiert als Excel unter der xlsx-Endung', async () => {
    stubTableRoutes()
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByTestId('export-table-trigger')).toBeInTheDocument()
    })
    fireEvent.keyDown(screen.getByTestId('export-table-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-table-xlsx'))

    await waitFor(() => {
      expect(anchorClick).toHaveBeenCalled()
    })
    expect(downloadName()).toBe('who2be-table-preisliste.xlsx')
  })

  it('zeigt die Server-Meldung, wenn die Vorschau am Ergebnis-Budget scheitert', async () => {
    // 413 kommt aus dem Result-Budget des Tablestores — Schema und Header
    // muessen trotzdem lesbar bleiben, nur die Vorschau traegt den Hinweis.
    const detail = 'Ergebnis zu gross (max. 5 MiB). Bitte die Query einschränken.'
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/wa-tables/tbl-1/query')) {
          return new Response(JSON.stringify({ detail }), {
            status: 413,
            headers: { 'content-type': 'application/json' },
          })
        }
        if (url.includes('/work-areas/area-1/tables')) {
          return new Response(JSON.stringify([waTable()]), {
            status: 200,
            headers: { 'content-type': 'application/json' },
          })
        }
        if (url.includes('/wa-tables/tbl-1')) {
          return new Response(JSON.stringify(tableDescription()), {
            status: 200,
            headers: { 'content-type': 'application/json' },
          })
        }
        return new Response('[]', {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      }),
    )
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText(detail)).toBeInTheDocument()
    })
    expect(screen.getByRole('table', { name: 'Schema' })).toBeInTheDocument()
  })

  it('meldet eine nicht sichtbare Tabelle als nicht gefunden', async () => {
    stubFetch([
      ['/wa-tables/tbl-1/query', tableQueryResult()],
      ['/wa-tables/tbl-1', tableDescription()],
      ['/work-areas/area-1/tables', []],
    ])
    renderAt(<TableDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(
        screen.getByText('Diese Tabelle existiert nicht oder ist für dich nicht sichtbar.'),
      ).toBeInTheDocument()
    })
  })
})
