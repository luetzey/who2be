import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { WorkAreaSearchHit } from '@/api/types'

import { area, renderAt, stubFetch } from '../test-utils'

import { WorkAreaSearchPage } from './WorkAreaSearchPage'

const PATH = '/w/:workspaceId/workarea/search'

function hit(overrides: Partial<WorkAreaSearchHit> = {}): WorkAreaSearchHit {
  return {
    anchor: 'art-1#bbbbbbbb',
    artifact_id: 'art-1',
    block_id: 'bbbbbbbb',
    title: 'Preisliste 2026',
    snippet: 'Der Preis stieg um 8 %.',
    score: 0.9,
    area_id: 'area-1',
    ...overrides,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('WorkAreaSearchPage', () => {
  it('fragt ohne Suchbegriff nicht an und fordert zur Eingabe auf', async () => {
    // Signatur explizit am Generic: `mock.calls` traegt dann die URL, ohne
    // dass ein ungenutzter Parameter deklariert werden muss.
    const fetchMock = vi.fn<(url: string) => Promise<Response>>(
      async () =>
        new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAt(<WorkAreaSearchPage />, PATH, ['/w/ws-1/workarea/search'])

    await waitFor(() => {
      expect(screen.getByText('Gib einen Suchbegriff ein')).toBeInTheDocument()
    })
    // Die Bereichs-Liste fuer den Filter darf geladen werden, die Suche nicht.
    const searched = fetchMock.mock.calls.some(([url]) =>
      String(url).includes('/workarea-search'),
    )
    expect(searched).toBe(false)
  })

  it('zeigt Treffer mit Anker und verlinkt auf den Block', async () => {
    stubFetch([
      ['/workarea-search', [hit()]],
      ['/work-areas', [area()]],
    ])
    renderAt(<WorkAreaSearchPage />, PATH, ['/w/ws-1/workarea/search?q=preis'])

    await waitFor(() => {
      expect(screen.getByText('Der Preis stieg um 8 %.')).toBeInTheDocument()
    })
    expect(screen.getByText('art-1#bbbbbbbb')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Preisliste 2026' })).toHaveAttribute(
      'href',
      '/w/ws-1/workarea/areas/area-1/artifacts/art-1#bbbbbbbb',
    )
  })

  it('sucht nach dem Tippen entprellt mit dem eingegebenen Begriff', async () => {
    // Signatur explizit am Generic: `mock.calls` traegt dann die URL, ohne
    // dass ein ungenutzter Parameter deklariert werden muss.
    const fetchMock = vi.fn<(url: string) => Promise<Response>>(
      async () =>
        new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAt(<WorkAreaSearchPage />, PATH, ['/w/ws-1/workarea/search'])

    fireEvent.change(screen.getByLabelText('Suchbegriff'), { target: { value: 'preis' } })

    // Der Weg fuehrt ueber die URL (`?q=`) in den Daten-Hook — landet der
    // Begriff am Server, funktioniert die ganze Kette inkl. Entprellung.
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([url]) => String(url))
      expect(calls.some((url) => url.includes('/workarea-search?q=preis'))).toBe(true)
    })
  })

  it('schraenkt auf den gewaehlten Bereich ein', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      new Response(JSON.stringify(url.includes('/work-areas') ? [area()] : []), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAt(<WorkAreaSearchPage />, PATH, ['/w/ws-1/workarea/search?q=preis'])

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Marktrecherche' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Bereich'), { target: { value: 'area-1' } })

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([url]) => String(url))
      expect(calls.some((url) => url.includes('area_id=area-1'))).toBe(true)
    })
  })

  it('meldet Treffer-Losigkeit mit dem gesuchten Begriff', async () => {
    stubFetch([
      ['/workarea-search', []],
      ['/work-areas', [area()]],
    ])
    renderAt(<WorkAreaSearchPage />, PATH, ['/w/ws-1/workarea/search?q=xyz'])

    await waitFor(() => {
      expect(
        screen.getByText('Für „xyz“ gibt es nichts in den sichtbaren Bereichen.'),
      ).toBeInTheDocument()
    })
  })
})
