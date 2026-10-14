import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Dossier, DossierGeneration, DossierMeasure } from '@/api/types'
import { Button } from '@/components/ui/button'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { EvolutionTimeline } from './EvolutionTimeline'

const api = vi.hoisted(() => ({ getDossier: vi.fn() }))
vi.mock('@/api/useApi', () => ({ useApi: () => api }))

const M1 = '6f1c2a3b-0000-4000-8000-000000000001'
const S1 = '6f1c2a3b-0000-4000-8000-0000000000a1'

function measure(overrides: Partial<DossierMeasure> = {}): DossierMeasure {
  return {
    id: M1,
    session_id: S1,
    target: 'playbook',
    entity_id: 'pb1',
    change_summary: 'Frist aus Resource lesen',
    state: 'activated',
    verdict: null,
    reviewed_at: null,
    follow_up_at: '2026-10-24',
    case_count: 3,
    created_at: '2026-09-25T10:00:00Z',
    ...overrides,
  }
}

function generation(overrides: Partial<DossierGeneration> = {}): DossierGeneration {
  return {
    entity_type: 'playbook',
    entity_id: 'pb1',
    name: 'Erstattung',
    from_version: 3,
    to_version: 4,
    activated_at: '2026-09-26T10:00:00Z',
    measure_ids: [M1],
    verdict: null,
    shared_agent_count: 0,
    ...overrides,
  }
}

function dossier(overrides: Partial<Dossier> = {}): Dossier {
  return {
    agent_id: 'a1',
    agent_name: 'Support-Assistent',
    generated_at: '2026-10-14T10:00:00Z',
    min_uses: 20,
    open_cases: { counts: {}, total: 0, items: [] },
    elements: [],
    elements_total: 0,
    access: { since: '2026-07-16', window_days: 90, total: 0, rows: [] },
    measures: [measure()],
    measures_total: 1,
    generations: [generation()],
    generations_next_cursor: null,
    ...overrides,
  }
}

/** `n` Generationen, Tag absteigend (neueste zuerst wie der Server). */
function many(n: number, offset = 0): DossierGeneration[] {
  return Array.from({ length: n }, (_, index) => {
    const day = String(28 - ((index + offset) % 28)).padStart(2, '0')
    return generation({
      entity_id: `pb${index + offset}`,
      name: `Baustein ${index + offset + 1}`,
      activated_at: `2026-08-${day}T10:00:00Z`,
      measure_ids: [],
    })
  })
}

const changeHref = (sessionId: string, measureId: string) =>
  `/w/ws-1/agents/a1/reviews/${encodeURIComponent(sessionId)}?change=${encodeURIComponent(measureId)}`

function renderTimeline(reviewDates: Record<string, string> = {}) {
  return renderInRoutes(
    <EvolutionTimeline agentId="a1" changeHref={changeHref} reviewDates={reviewDates} />,
    { path: '/w/:workspaceId/agents/:id', initialEntries: ['/w/ws-1/agents/a1?tab=evolution'] },
  )
}

async function items() {
  return within(await screen.findByTestId('evolution-timeline')).findAllByTestId('evolution-generation')
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-14T10:00:00'))
  api.getDossier.mockResolvedValue(dossier())
})

afterEach(() => {
  vi.useRealTimers()
})

describe('EvolutionTimeline', () => {
  it('Eintrag: Datum, Baustein, Versionen, Pill, Warum mit Review-Datum, Link auf die Änderung', async () => {
    api.getDossier.mockResolvedValue(
      dossier({ generations: [generation({ shared_agent_count: 2 })] }),
    )
    renderTimeline({ [S1]: '2026-09-25T10:00:00Z' })

    expect(screen.getByRole('heading', { level: 2, name: 'Verlauf' })).toBeInTheDocument()
    expect(
      screen.getByText('Jede aktivierte Version eines Bausteins ist eine neue Generation des Agenten.'),
    ).toBeInTheDocument()
    const [row] = await items()
    expect(within(row).getByTestId('evolution-generation-title')).toHaveTextContent(
      'Generation vom 26.09.2026 · Playbook Erstattung v3 → v4',
    )
    expect(within(row).getByTestId('evolution-generation-result')).toHaveTextContent(
      'Nachkontrolle am 24.10.2026',
    )
    expect(within(row).getByTestId('evolution-generation-meta')).toHaveTextContent(
      'Warum: 3 Rückmeldungen (Review vom 25.09.2026) · betrifft auch: 2 weitere Agenten',
    )
    expect(within(row).getByRole('link', { name: 'Änderung ansehen: Playbook Erstattung' })).toHaveAttribute(
      'href',
      `/w/ws-1/agents/a1/reviews/${S1}?change=${M1}`,
    )
    expect(within(row).getByTestId('evolution-generation-dot')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Generationen, neueste zuerst' }).tagName).toBe('OL')
    expect(api.getDossier).toHaveBeenCalledTimes(1)
    expect(api.getDossier).toHaveBeenCalledWith('a1', undefined)
  })

  it('erste Version ohne Vorgänger: nur „v1“; ohne Review-Datum „Warum: n Rückmeldungen“', async () => {
    api.getDossier.mockResolvedValue(
      dossier({ generations: [generation({ from_version: null, to_version: 1, shared_agent_count: null })] }),
    )
    renderTimeline()
    const [row] = await items()
    expect(within(row).getByTestId('evolution-generation-title')).toHaveTextContent(
      'Generation vom 26.09.2026 · Playbook Erstattung v1',
    )
    expect(within(row).getByTestId('evolution-generation-title')).not.toHaveTextContent('→')
    expect(within(row).getByTestId('evolution-generation-meta')).toHaveTextContent('Warum: 3 Rückmeldungen')
    expect(within(row).getByTestId('evolution-generation-meta')).not.toHaveTextContent('betrifft auch')
  })

  it('direkte Aktivierung (measure_ids leer): gestrichelter Punkt, Pill, „Keine Nachkontrolle“, kein Link', async () => {
    api.getDossier.mockResolvedValue(dossier({ generations: [generation({ measure_ids: [] })] }))
    renderTimeline()
    const [row] = await items()
    expect(within(row).getByTestId('evolution-generation-result')).toHaveTextContent(
      'Direkt geändert, ohne Review',
    )
    expect(within(row).getByTestId('evolution-generation-meta')).toHaveTextContent('Keine Nachkontrolle')
    expect(within(row).getByTestId('evolution-generation-dot-direct')).toBeInTheDocument()
    expect(within(row).queryByRole('link')).toBeNull()
  })

  it('fällige Nachkontrolle: Pill „Nachkontrolle fällig“ aus Server-Zustand und Termin', async () => {
    api.getDossier.mockResolvedValue(dossier({ measures: [measure({ follow_up_at: '2026-10-13' })] }))
    renderTimeline()
    const [row] = await items()
    expect(within(row).getByTestId('evolution-generation-result')).toHaveTextContent('Nachkontrolle fällig')
  })
})

// Leitplanke „eine Quelle pro Ansicht“: Server und lokale Rechnung laufen
// auseinander, die Ansicht folgt dem Server.
describe('EvolutionTimeline — eine Quelle (Server)', () => {
  it('Reihenfolge wie geliefert, auch wenn sie nicht nach Datum sortiert ist', async () => {
    api.getDossier.mockResolvedValue(
      dossier({
        generations: [
          generation({ name: 'Alt', activated_at: '2026-08-01T10:00:00Z', measure_ids: [] }),
          generation({ name: 'Neu', activated_at: '2026-10-01T10:00:00Z', measure_ids: [] }),
        ],
      }),
    )
    renderTimeline()
    const rows = await items()
    expect(rows.map((row) => within(row).getByTestId('evolution-generation-title').textContent)).toEqual([
      'Generation vom 01.08.2026 · Playbook Alt v3 → v4',
      'Generation vom 01.10.2026 · Playbook Neu v3 → v4',
    ])
  })

  it('Einstufung vom Server (verdict) schlägt den Zustand der Änderung', async () => {
    api.getDossier.mockResolvedValue(
      dossier({
        generations: [generation({ verdict: 'effective' })],
        measures: [measure({ state: 'ineffective', follow_up_at: '2026-10-01' })],
      }),
    )
    renderTimeline()
    const [row] = await items()
    expect(within(row).getByTestId('evolution-generation-result')).toHaveTextContent('Hat gewirkt')
  })

  it('Zustand vom Server (state), nicht aus dem Termin: abgeschlossene Änderung ist nie fällig', async () => {
    api.getDossier.mockResolvedValue(
      dossier({ measures: [measure({ state: 'withdrawn', follow_up_at: '2026-10-01' })] }),
    )
    renderTimeline()
    const [row] = await items()
    expect(within(row).getByTestId('evolution-generation-result')).toHaveTextContent('Zurückgezogen')
    expect(row).not.toHaveTextContent('fällig')
  })

  it('keine Verknüpfung über den Baustein: ohne measure_ids „direkt“, obwohl eine Änderung am Baustein existiert', async () => {
    api.getDossier.mockResolvedValue(
      dossier({ generations: [generation({ measure_ids: [] })], measures: [measure()] }),
    )
    renderTimeline()
    const [row] = await items()
    expect(within(row).getByTestId('evolution-generation-result')).toHaveTextContent(
      'Direkt geändert, ohne Review',
    )
    expect(within(row).queryByRole('link')).toBeNull()
  })
})

describe('EvolutionTimeline — IDs', () => {
  it('Änderung mit Nicht-UUID-ID bekommt keinen Link', async () => {
    api.getDossier.mockResolvedValue(
      dossier({
        generations: [generation({ measure_ids: ['../../x'] })],
        measures: [measure({ id: '../../x' })],
      }),
    )
    renderTimeline()
    const [row] = await items()
    expect(within(row).queryByRole('link')).toBeNull()
    expect(within(row).getByTestId('evolution-generation-meta')).toHaveTextContent('Aus einem Review')
  })

  it('Änderung mit Nicht-UUID-Review bekommt keinen Link', async () => {
    api.getDossier.mockResolvedValue(dossier({ measures: [measure({ session_id: 's1?x=1' })] }))
    renderTimeline()
    const [row] = await items()
    expect(within(row).queryByRole('link')).toBeNull()
  })

  it('Dossier eines anderen Agenten wird verworfen', async () => {
    api.getDossier.mockResolvedValue(dossier({ agent_id: 'a2' }))
    renderTimeline()
    expect(await screen.findByRole('alert')).toHaveTextContent('Der Verlauf konnte nicht geladen werden.')
    expect(screen.queryByTestId('evolution-generation')).toBeNull()
  })
})

describe('EvolutionTimeline — Grenze', () => {
  it('5 sichtbar, +10 aus den geladenen ohne Anfrage, danach eine Anfrage mit Cursor', async () => {
    api.getDossier
      .mockResolvedValueOnce(dossier({ generations: many(15), measures: [], generations_next_cursor: 'c-1' }))
      .mockResolvedValueOnce(dossier({ generations: many(3, 15), measures: [], generations_next_cursor: null }))
    renderTimeline()

    expect(await items()).toHaveLength(5)
    const more = screen.getByRole('button', { name: 'Ältere Generationen zeigen' })
    fireEvent.click(more)
    expect(await items()).toHaveLength(15)
    expect(api.getDossier).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Ältere Generationen zeigen' }))
    await waitFor(async () => expect(await items()).toHaveLength(18))
    expect(api.getDossier).toHaveBeenCalledTimes(2)
    expect(api.getDossier).toHaveBeenLastCalledWith('a1', { cursor: 'c-1' })
    expect(screen.queryByRole('button', { name: 'Ältere Generationen zeigen' })).toBeNull()
  })

  it('ohne weitere Generationen kein Knopf', async () => {
    api.getDossier.mockResolvedValue(dossier({ generations: many(5), generations_next_cursor: null }))
    renderTimeline()
    expect(await items()).toHaveLength(5)
    expect(screen.queryByRole('button', { name: 'Ältere Generationen zeigen' })).toBeNull()
  })

  it('Fehler beim Nachladen: Hinweis, die geladenen bleiben', async () => {
    api.getDossier
      .mockResolvedValueOnce(dossier({ generations: many(5), measures: [], generations_next_cursor: 'c-1' }))
      .mockRejectedValueOnce(new Error('boom'))
    renderTimeline()
    expect(await items()).toHaveLength(5)
    fireEvent.click(screen.getByRole('button', { name: 'Ältere Generationen zeigen' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ältere Generationen konnten nicht geladen werden.',
    )
    expect(await items()).toHaveLength(5)
  })
})

describe('EvolutionTimeline — Zustände', () => {
  it('Agentwechsel: eine alte Seite wird verworfen, die Anzeige beginnt wieder bei 5', async () => {
    let resolveOld: (value: Dossier) => void = () => {}
    api.getDossier.mockImplementation((agentId: string, options?: { cursor?: string }) => {
      if (agentId === 'a1' && options === undefined) {
        return Promise.resolve(dossier({ generations: many(5), measures: [], generations_next_cursor: 'c-1' }))
      }
      if (agentId === 'a1') {
        return new Promise((resolve) => {
          resolveOld = resolve
        })
      }
      return Promise.resolve(
        dossier({ agent_id: 'a2', generations: many(7, 40), measures: [], generations_next_cursor: null }),
      )
    })

    function Switcher() {
      const [agentId, setAgentId] = useState('a1')
      return (
        <>
          <Button type="button" onClick={() => setAgentId('a2')}>
            Agent wechseln
          </Button>
          <EvolutionTimeline agentId={agentId} changeHref={changeHref} reviewDates={{}} />
        </>
      )
    }
    renderInRoutes(<Switcher />, {
      path: '/w/:workspaceId/agents/:id',
      initialEntries: ['/w/ws-1/agents/a1?tab=evolution'],
    })

    expect(await items()).toHaveLength(5)
    fireEvent.click(screen.getByRole('button', { name: 'Ältere Generationen zeigen' }))
    await waitFor(() => expect(api.getDossier).toHaveBeenLastCalledWith('a1', { cursor: 'c-1' }))

    fireEvent.click(screen.getByRole('button', { name: 'Agent wechseln' }))
    await waitFor(async () => expect((await items())[0]).toHaveTextContent('Baustein 41'))
    expect(await items()).toHaveLength(5)

    await act(async () => {
      resolveOld(dossier({ generations: many(3, 90), measures: [], generations_next_cursor: null }))
    })
    expect(screen.queryByText(/Baustein 91/)).toBeNull()
    expect(await items()).toHaveLength(5)
  })

  it('leer: Satz aus der Spec', async () => {
    api.getDossier.mockResolvedValue(dossier({ generations: [] }))
    renderTimeline()
    expect(await screen.findByTestId('evolution-timeline-empty')).toHaveTextContent(
      'Noch keine Generation. Sobald du eine Änderung aktivierst, erscheint sie hier.',
    )
  })

  it('Fehler: Hinweis statt Liste', async () => {
    api.getDossier.mockRejectedValue(new Error('500'))
    renderTimeline()
    expect(await screen.findByRole('alert')).toHaveTextContent('Der Verlauf konnte nicht geladen werden.')
  })
})

describe('EvolutionTimeline (a11y)', () => {
  it('a11y: laden ohne axe-Violations', async () => {
    api.getDossier.mockReturnValue(new Promise(() => {}))
    const { container } = renderTimeline()
    expect(screen.getByTestId('evolution-timeline-loading')).toBeInTheDocument()
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: leer ohne axe-Violations', async () => {
    api.getDossier.mockResolvedValue(dossier({ generations: [] }))
    const { container } = renderTimeline()
    await screen.findByTestId('evolution-timeline-empty')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: Fehler ohne axe-Violations', async () => {
    api.getDossier.mockRejectedValue(new Error('500'))
    const { container } = renderTimeline()
    await screen.findByRole('alert')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: Liste mit Review- und direkter Generation ohne axe-Violations', async () => {
    api.getDossier.mockResolvedValue(
      dossier({
        generations: [generation(), generation({ measure_ids: [], entity_id: 'p1', entity_type: 'persona' })],
        generations_next_cursor: 'c-1',
      }),
    )
    const { container } = renderTimeline({ [S1]: '2026-09-25T10:00:00Z' })
    expect(await items()).toHaveLength(2)
    expect(await axe(container)).toHaveNoViolations()
  })
})
