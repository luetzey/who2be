import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { KbSearchHit } from '@/api/types'

import { renderAt, stubFetch } from '../test-utils'

import { KbSearchPage } from './KbSearchPage'

const PATH = '/w/:workspaceId/workarea/kb'

function hit(overrides: Partial<KbSearchHit> = {}): KbSearchHit {
  return {
    node_id: 'node-1',
    anchor: 'node:node-1',
    snippet: 'Der Listenpreis stieg 2026 um 8 Prozent.',
    tier: 'derived',
    status: 'live',
    score: 0.8,
    ...overrides,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('KbSearchPage', () => {
  it('zeigt Treffer mit Vertrauensstufe und verlinkt auf die Aussage', async () => {
    stubFetch([['/kb-search', [hit()]]])
    renderAt(<KbSearchPage />, PATH, ['/w/ws-1/workarea/kb?q=preis'])

    await waitFor(() => {
      expect(screen.getByText('Der Listenpreis stieg 2026 um 8 Prozent.')).toBeInTheDocument()
    })
    expect(screen.getByText('Abgeleitet')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Der Listenpreis stieg 2026 um 8 Prozent.' }),
    ).toHaveAttribute('href', '/w/ws-1/workarea/kb/node-1')
  })

  it('zeichnet nur ueberholte Aussagen aus', async () => {
    stubFetch([['/kb-search', [hit({ status: 'stale' })]]])
    renderAt(<KbSearchPage />, PATH, ['/w/ws-1/workarea/kb?q=preis'])

    await waitFor(() => {
      expect(screen.getByText('Überholt')).toBeInTheDocument()
    })
  })

  it('fragt ohne Suchbegriff nicht an', async () => {
    const fetchMock = vi.fn(
      async () => new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAt(<KbSearchPage />, PATH, ['/w/ws-1/workarea/kb'])

    await waitFor(() => {
      expect(screen.getByText('Gib einen Suchbegriff ein')).toBeInTheDocument()
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

// Responsive-Vertrag #572 (AK 5). jsdom hat kein Layout — Klassen-Vertrag zu
// den gerenderten Messungen in
// .claude/plan/2026-09-23-1100_572-w3-workarea-responsive-audit.md.
describe('KbSearchPage — Responsive (#572)', () => {
  it('laesst den Treffer-Text umbrechen statt abschneiden', async () => {
    // KB-Snippets tragen Belege ohne Trennstelle (`sha256:…`). Gemessen schnitt
    // der Link bei 320 px ab (297 px Inhalt in 238 px sichtbar).
    stubFetch([
      ['/kb-search', [hit({ snippet: 'Beleg sha256:9f86d081884c7d659a2feaa0c55ad015' })]],
    ])
    renderAt(<KbSearchPage />, PATH, ['/w/ws-1/workarea/kb?q=preis'])

    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: 'Beleg sha256:9f86d081884c7d659a2feaa0c55ad015' }),
      ).toHaveClass('break-words')
    })
  })
})
