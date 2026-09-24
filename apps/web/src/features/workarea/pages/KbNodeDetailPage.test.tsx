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

// Responsive-Vertrag #572 (AK 5): umbruchfeindliche Bezeichner (`node:<id>`,
// `sha256:<hash>`, Anker) brechen um oder kuerzen kontrolliert. jsdom hat kein
// Layout — Klassen-Vertrag zu den gerenderten Messungen in
// .claude/plan/2026-09-23-1100_572-w3-workarea-responsive-audit.md. Gemessen
// schnitten Inhalt, Inhalts-Referenz und Nachbar-Link bei 320 UND 375 px ab.
// `:122` `source_ref` trug `break-all` bereits — das Muster existierte in der
// Datei, es fehlte nur an den drei Geschwistern.
describe('KbNodeDetailPage — Responsive (#572)', () => {
  it('laesst Aussage und Nachbar-Link umbrechen', async () => {
    const belegter = 'Beleg sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b'
    stubFetch([
      ['/kb/neighbors', [neighbor({ node: kbNode({ id: 'node-2', content: belegter }) })]],
      ['/kb/nodes/node-1', kbNode({ content: belegter })],
    ])
    renderAt(<KbNodeDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getAllByText(belegter).length).toBeGreaterThan(0)
    })
    for (const el of screen.getAllByText(belegter)) {
      expect(el).toHaveClass('break-words')
    }
  })

  it('bricht die Inhalts-Referenz hart, weil sie keine Trennstelle hat', async () => {
    // `sha256:<64 Hex>` enthaelt keine Stelle, an der `break-words` umbrechen
    // duerfte — dieselbe Wahl wie am `source_ref` direkt daneben.
    stubFetch([
      ['/kb/neighbors', []],
      ['/kb/nodes/node-1', kbNode({ content_ref: 'sha256:9f86d081884c7d659a2feaa0c55ad015' })],
    ])
    renderAt(<KbNodeDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(
        screen.getByText(/sha256:9f86d081884c7d659a2feaa0c55ad015/),
      ).toHaveClass('break-all')
    })
  })
})
