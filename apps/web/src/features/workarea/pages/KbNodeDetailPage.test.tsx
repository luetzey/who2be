import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { KbNeighbor } from '@/api/types'

import { kbNode, renderAt, stubFetch } from '../test-utils'

import { KbNodeDetailPage } from './KbNodeDetailPage'

const PATH = '/w/:workspaceId/workarea/kb/:nodeId'
const ENTRY = ['/w/ws-1/workarea/kb/node-1']

function neighbor(overrides: Partial<KbNeighbor> = {}): KbNeighbor {
  return {
    node: kbNode({ id: 'node-2', content: 'Die Nachfrage blieb konstant.' }),
    edge_type: 'supports',
    direction: 'out',
    co_n: null,
    ...overrides,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('KbNodeDetailPage', () => {
  it('zeigt Aussage und Beleg', async () => {
    stubFetch([
      ['/kb/neighbors', []],
      ['/kb/nodes/node-1', kbNode()],
    ])
    renderAt(<KbNodeDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Der Listenpreis stieg 2026 um 8 Prozent.')).toBeInTheDocument()
    })
    expect(screen.getByText('artifact:art-1#aaaaaaaa')).toBeInTheDocument()
  })

  it('verlinkt einen Artifact-Beleg zurueck in den Arbeitsbereich', async () => {
    stubFetch([
      ['/kb/neighbors', []],
      ['/kb/nodes/node-1', kbNode()],
    ])
    renderAt(<KbNodeDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Beleg öffnen' })).toBeInTheDocument()
    })
    expect(screen.getByRole('link', { name: 'Beleg öffnen' })).toHaveAttribute(
      'href',
      '/w/ws-1/workarea/artifacts/art-1#aaaaaaaa',
    )
  })

  it('macht einen URL-Beleg NICHT klickbar', async () => {
    // Bewusste Entscheidung: die Referenz stammt von einem Agenten bzw. aus
    // einem Ingest — ein Ein-Klick-Weg auf eine fremdbestimmte Adresse waere
    // aus der Verwaltungsoberflaeche heraus falsch. Sichtbar bleibt sie.
    stubFetch([
      ['/kb/neighbors', []],
      [
        '/kb/nodes/node-1',
        kbNode({ source_ref: 'url:https://example.invalid/preise', source_ref_kind: 'url' }),
      ],
    ])
    renderAt(<KbNodeDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('url:https://example.invalid/preise')).toBeInTheDocument()
    })
    expect(screen.queryByRole('link', { name: 'Beleg öffnen' })).not.toBeInTheDocument()
  })

  it('zeigt bei co_occurs_with immer die Fallzahl', async () => {
    stubFetch([
      ['/kb/neighbors', [neighbor({ edge_type: 'co_occurs_with', co_n: 42 })]],
      ['/kb/nodes/node-1', kbNode()],
    ])
    renderAt(<KbNodeDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('tritt gemeinsam auf mit')).toBeInTheDocument()
    })
    expect(screen.getByText('n = 42')).toBeInTheDocument()
  })

  it('zeigt die Aussage auch dann, wenn die Nachbar-Abfrage scheitert', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.includes('/kb/neighbors')
          ? new Response('{}', { status: 500, headers: { 'content-type': 'application/json' } })
          : new Response(JSON.stringify(kbNode()), {
              status: 200,
              headers: { 'content-type': 'application/json' },
            }),
      ),
    )
    renderAt(<KbNodeDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Der Listenpreis stieg 2026 um 8 Prozent.')).toBeInTheDocument()
    })
    expect(screen.getByText('Diese Aussage ist mit keiner anderen verknüpft.')).toBeInTheDocument()
  })
})
