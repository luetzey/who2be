import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { agent, area, renderAt, stubFetch } from '../test-utils'

import { AreasPage } from './AreasPage'

const PATH = '/w/:workspaceId/workarea'
const ENTRY = ['/w/ws-1/workarea']

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AreasPage', () => {
  it('listet sichtbare Bereiche mit Sichtbarkeits-Badge', async () => {
    stubFetch([
      ['/agents', [agent()]],
      ['/work-areas', [area(), area({ id: 'area-2', scope: 'private', owner_agent_id: 'agent-1', name: 'Privat von Recherche-Agent' })]],
    ])
    renderAt(<AreasPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Marktrecherche')).toBeInTheDocument()
    })
    expect(screen.getByText('Geteilt')).toBeInTheDocument()
    expect(screen.getByText('Privat')).toBeInTheDocument()
  })

  it('loest den Besitzer einer privaten Area zum Agenten-Namen auf', async () => {
    stubFetch([
      ['/agents', [agent()]],
      ['/work-areas', [area({ id: 'area-2', scope: 'private', owner_agent_id: 'agent-1' })]],
    ])
    renderAt(<AreasPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Agent: Recherche-Agent')).toBeInTheDocument()
    })
  })

  it('zeigt einen Leerzustand ohne Bereiche', async () => {
    stubFetch([['/work-areas', []]])
    renderAt(<AreasPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Noch keine Bereiche')).toBeInTheDocument()
    })
  })

  it('meldet einen Ladefehler statt einer leeren Liste', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.includes('/work-areas')
          ? new Response('{}', { status: 500, headers: { 'content-type': 'application/json' } })
          : new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }),
      ),
    )
    renderAt(<AreasPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
    })
  })
})

// Responsive-Vertrag #572 (AK 5). jsdom hat kein Layout — Klassen-Vertrag zu
// den gerenderten Messungen in
// .claude/plan/2026-09-23-1100_572-w3-workarea-responsive-audit.md.
describe('AreasPage — Responsive (#572)', () => {
  it('laesst den Besitzer-Namen in der Meta-Pille hart umbrechen', async () => {
    // Gemessen: ein langer Agentenname lief bei 320 px um 49 px ueber die
    // Innenkante der Meta-Zeile — eine `inline-flex`-Pille bietet keine
    // Trennstelle. `break-all`, weil Agentennamen zusammengeschrieben sein
    // koennen (Muster `ResourcesPage` aus #564).
    stubFetch([
      ['/agents', [agent({ name: 'Unternehmensberatungsgesellschaftsrechercheagent' })]],
      ['/work-areas', [area({ scope: 'private', owner_agent_id: 'agent-1' })]],
    ])
    renderAt(<AreasPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(
        screen.getByText('Agent: Unternehmensberatungsgesellschaftsrechercheagent'),
      ).toHaveClass('break-all')
    })
  })
})
