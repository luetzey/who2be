import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData, InboxCounts, Me, WorkspaceRole } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { DashboardPage } from './DashboardPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const sampleData: DashboardData = {
  kpis: {
    active_personas: 12,
    active_playbooks: 34,
    active_resources: 7,
    pending_reviews: 3,
    pending_system_prompts: 1,
  },
  activity: [
    {
      ts: '2026-05-28T10:00:00Z',
      actor: { user_id: 'u1', display_name: 'Alice' },
      entity_type: 'playbook',
      entity_id: 'pb1',
      entity_name: 'Coaching',
      event: 'promoted_to_active',
      from_version: 3,
      to_version: 4,
    },
  ],
  status_distribution: {
    persona: { draft: 2, review: 1, active: 12, inactive: 8 },
    playbook: { draft: 1, review: 0, active: 34, inactive: 5 },
    resource: { draft: 1, review: 0, active: 7, inactive: 1 },
  },
}

// Antwortet jedem Request mit `payload` — ausser dem Aufgaben-Zaehler
// (`/inbox/counts`, Glocke und Dashboard-Zeile): der scheitert, damit die
// Zeile hier entfaellt und die Tests nur das uebrige Dashboard pruefen.
function jsonFetch(payload: unknown, status = 200) {
  return vi.fn().mockImplementation((input: RequestInfo | URL) => {
    if (String(input).includes('/inbox/counts')) {
      return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
    }
    return Promise.resolve(new Response(JSON.stringify(payload), { status }))
  })
}

function meWithRole(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Acme',
        slug: 'acme',
        kind: 'company',
        workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role }],
      },
    ],
  }
}

describe('DashboardPage', () => {
  it('rendert KPIs, Activity-Eintraege und Status-Bars', async () => {
    vi.stubGlobal('fetch', jsonFetch(sampleData))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText(/Alice/)).toBeInTheDocument()
    })
    // KPI-Zahlen im Kennzahlen-Bereich pruefen (die bloßen Zahlen tauchen sonst
    // auch in der Balken-Ablesung auf).
    const kpis = screen.getByRole('region', { name: 'Kennzahlen' })
    expect(within(kpis).getByText('12')).toBeInTheDocument()
    expect(within(kpis).getByText('34')).toBeInTheDocument()
    // Aktive-Resources-KPI (aus kpis.active_resources).
    expect(within(kpis).getByText('7')).toBeInTheDocument()
    // Das Band „Braucht jetzt deine Aufmerksamkeit“ gibt es nicht mehr
    // (Navigation W1-c); Versionen zur Freigabe stehen auf „Zu erledigen“.
    expect(screen.queryByText(/Braucht jetzt deine Aufmerksamkeit/)).not.toBeInTheDocument()
    expect(screen.queryByText(/liegt zur Review|liegen zur Review/)).not.toBeInTheDocument()
    expect(screen.getByText(/Alice/)).toBeInTheDocument()
    expect(screen.getByText(/Coaching/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Personas:/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Playbooks:/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Resources:/ })).toBeInTheDocument()
  })

  it('zeigt einen Empty-State, wenn der Endpoint 404 liefert', async () => {
    vi.stubGlobal('fetch', jsonFetch({ detail: 'not found' }, 404))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(
        screen.getByText('Dashboard noch nicht verfügbar.'),
      ).toBeInTheDocument()
    })
  })

  it('rendert auch ohne actor (Legacy-Payload) ohne Crash', async () => {
    // Regression: vor Phase-3 Fix Track 1 lieferte das Backend die
    // `status_history`-Rohzeilen — kein `actor`. `ActivityRow` darf das
    // nicht abstuerzen lassen.
    const legacy = {
      kpis: { active_personas: 1, active_playbooks: 1, pending_reviews: 0 },
      activity: [
        {
          ts: '2026-05-28T10:00:00Z',
          entity_type: 'persona' as const,
          entity_id: 'p1',
          event: 'submitted_for_review',
        },
      ],
      status_distribution: {
        persona: { draft: 0, review: 1, active: 1, inactive: 0 },
        playbook: { draft: 0, review: 0, active: 1, inactive: 0 },
      },
    }
    vi.stubGlobal('fetch', jsonFetch(legacy))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('Unbekannt')).toBeInTheDocument()
    })
    expect(screen.getByText(/reichte zur Review ein/)).toBeInTheDocument()
  })

  it('blaettert die Activity seitenbasiert und fragt page=2 an', async () => {
    const paged: DashboardData = {
      kpis: { active_personas: 1, active_playbooks: 1, pending_reviews: 0 },
      activity: [
        {
          ts: '2026-05-28T10:00:00Z',
          actor: { user_id: 'u1', display_name: 'Alice' },
          entity_type: 'playbook',
          entity_id: 'pb1',
          entity_name: 'Coaching',
          event: 'promoted_to_active',
        },
      ],
      activity_pagination: { page: 1, page_size: 20, total: 25, total_pages: 2 },
      status_distribution: {
        persona: { draft: 0, review: 0, active: 1, inactive: 0 },
        playbook: { draft: 0, review: 0, active: 1, inactive: 0 },
      },
    }
    const fetchMock = jsonFetch(paged)
    vi.stubGlobal('fetch', fetchMock)

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('Seite 1 von 2')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Weiter/ }))

    await waitFor(() => {
      const calledWithPage2 = fetchMock.mock.calls.some(([url]) =>
        String(url).includes('page=2'),
      )
      expect(calledWithPage2).toBe(true)
    })
  })

  it('feuert keinen Request und zeigt Preparing-State ohne Workspace-ID', async () => {
    // Kein `:workspaceId`-Param in der Route UND `me.default_workspace_id`
    // leer ⇒ `useWorkspaceId()` liefert ''. Der Hook darf dann NICHT
    // `/v1/workspaces//dashboard` feuern (sonst 404 oder „nicht erreichbar"),
    // sondern einen Preparing-State zeigen.
    const fetchMock = jsonFetch(sampleData)
    vi.stubGlobal('fetch', fetchMock)

    renderInRoutes(<DashboardPage />, {
      path: '/dashboard',
      initialEntries: ['/dashboard'],
      me: { user_id: 'u1', default_workspace_id: null, organizations: [] },
    })

    await waitFor(() => {
      expect(screen.getByText('Workspace wird vorbereitet …')).toBeInTheDocument()
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('zeigt eine Empty-Hint, wenn keine Aktivitaeten vorliegen', async () => {
    const empty: DashboardData = {
      kpis: { active_personas: 0, active_playbooks: 0, pending_reviews: 0 },
      activity: [],
      status_distribution: {
        persona: { draft: 0, review: 0, active: 0, inactive: 0 },
        playbook: { draft: 0, review: 0, active: 0, inactive: 0 },
      },
    }
    vi.stubGlobal('fetch', jsonFetch(empty))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText('Noch keine Aktivitäten.')).toBeInTheDocument()
    })
  })

  // §4.4 Checklistenpunkt 5: Flex-Kinder mit Textinhalt tragen `min-w-0`,
  // damit lange Statuslabels auf 320px nicht aus der Legende laufen.
  it('haelt die Legenden-Eintraege der Statusverteilung schrumpffaehig', async () => {
    vi.stubGlobal('fetch', jsonFetch(sampleData))

    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
    })

    await waitFor(() => {
      expect(screen.getByText(/Alice/)).toBeInTheDocument()
    })
    // Nur die Legende der Statusverteilung, nicht jede `<li>` der Seite: die
    // Legende haengt im CardHeader neben dem Titel.
    const legendItems = screen
      .getByRole('heading', { name: 'Status-Verteilung' })
      .parentElement!.querySelectorAll('li')
    expect(legendItems.length).toBeGreaterThan(0)
    for (const item of legendItems) {
      expect(item).toHaveClass('min-w-0')
    }
  })
})

// Navigation W1-c (Spec §2.5): Statt des Bands „Braucht jetzt deine
// Aufmerksamkeit“ steht eine Zeile `InboxSummary`. Sie zaehlt aus derselben
// Quelle wie Glocke und Seite „Zu erledigen“ (`GET /inbox/counts`); die
// frueheren Einzelquellen des Bands werden nicht mehr angefragt.
describe('DashboardPage — Zeile „Zu erledigen“ (W1-c)', () => {
  const quiet: DashboardData = {
    kpis: {
      active_personas: 1,
      active_playbooks: 1,
      pending_reviews: 2,
      pending_system_prompts: 1,
    },
    activity: [],
    status_distribution: {
      persona: { draft: 0, review: 2, active: 1, inactive: 0 },
      playbook: { draft: 0, review: 0, active: 1, inactive: 0 },
    },
  }

  function inboxCounts(extra: Partial<InboxCounts> = {}): InboxCounts {
    return {
      follow_ups_due: 0,
      memory_approval: 0,
      versions_review: 0,
      system_prompts_review: 0,
      cases_open: 0,
      patterns: 0,
      total: 0,
      ...extra,
    }
  }

  type InboxAnswer = InboxCounts | 'fail' | 'pending'

  function routedFetch(answer: InboxAnswer) {
    return vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://x')
      const json = (body: unknown, status = 200) =>
        Promise.resolve(new Response(JSON.stringify(body), { status }))
      if (url.pathname.endsWith('/dashboard')) return json(quiet)
      if (url.pathname.endsWith('/inbox/counts')) {
        if (answer === 'pending') return new Promise<Response>(() => {})
        if (answer === 'fail') return json({ detail: 'boom' }, 500)
        return json(answer)
      }
      return json({ detail: 'nope' }, 500)
    })
  }

  function renderAs(role: WorkspaceRole | null) {
    renderInRoutes(<DashboardPage />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: ['/w/ws-1/dashboard'],
      ...(role !== null ? { me: meWithRole(role) } : {}),
    })
  }

  async function settle() {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
  }

  function summary() {
    return screen.getByRole('region', { name: 'Zu erledigen' })
  }

  it('zeigt Titel, Arten mit Zahl und „Alle ansehen“ auf /inbox', async () => {
    vi.stubGlobal(
      'fetch',
      routedFetch(inboxCounts({ follow_ups_due: 1, memory_approval: 2, cases_open: 4, total: 7 })),
    )
    renderAs('editor')

    expect(await screen.findByText('7 Aufgaben warten auf dich')).toBeInTheDocument()
    const row = summary()
    expect(within(row).getByText('1 Nachkontrolle fällig')).toBeInTheDocument()
    expect(within(row).getByText('2 Gedächtnis-Einträge')).toBeInTheDocument()
    expect(within(row).getByText('4 Rückmeldungen')).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: /Alle ansehen/ })).toHaveAttribute(
      'href',
      '/w/ws-1/inbox',
    )
  })

  it('Singular: „1 Aufgabe wartet auf dich“', async () => {
    vi.stubGlobal('fetch', routedFetch(inboxCounts({ cases_open: 1, total: 1 })))
    renderAs('editor')

    expect(await screen.findByText('1 Aufgabe wartet auf dich')).toBeInTheDocument()
    expect(within(summary()).getByText('1 Rückmeldung')).toBeInTheDocument()
  })

  it('admin: Versionen zählen als Art, höchstens drei Arten, Rest „+ n weitere“', async () => {
    vi.stubGlobal(
      'fetch',
      routedFetch(
        inboxCounts({
          follow_ups_due: 1,
          memory_approval: 2,
          versions_review: 2,
          system_prompts_review: 1,
          cases_open: 4,
          patterns: 5,
          total: 10,
        }),
      ),
    )
    renderAs('admin')

    expect(await screen.findByText('10 Aufgaben warten auf dich')).toBeInTheDocument()
    const row = summary()
    expect(within(row).getByText('1 Nachkontrolle fällig')).toBeInTheDocument()
    expect(within(row).getByText('2 Gedächtnis-Einträge')).toBeInTheDocument()
    // Versionen und System-Prompts zusammen (wie auf „Zu erledigen“).
    expect(within(row).getByText('3 Versionen zur Freigabe')).toBeInTheDocument()
    expect(within(row).queryByText(/Rückmeldung/)).not.toBeInTheDocument()
    expect(within(row).getByText('+ 1 weitere')).toBeInTheDocument()
    // Muster zaehlen nie (ADR 3.7).
    expect(within(row).queryByText(/Muster/)).not.toBeInTheDocument()
  })

  it('editor: Versionen und Muster stehen nicht in der Zeile', async () => {
    vi.stubGlobal(
      'fetch',
      routedFetch(inboxCounts({ memory_approval: 1, versions_review: 3, patterns: 2, total: 1 })),
    )
    renderAs('editor')

    expect(await screen.findByText('1 Aufgabe wartet auf dich')).toBeInTheDocument()
    const row = summary()
    expect(within(row).getByText('1 Gedächtnis-Eintrag')).toBeInTheDocument()
    expect(within(row).queryByText(/Version/)).not.toBeInTheDocument()
    expect(within(row).queryByText(/Muster/)).not.toBeInTheDocument()
    expect(within(row).queryByText(/weitere/)).not.toBeInTheDocument()
  })

  it.each(['viewer', 'editor', 'admin'] as const)(
    '%s bei 0: „Nichts zu erledigen.“ ohne Knopf',
    async (role) => {
      vi.stubGlobal('fetch', routedFetch(inboxCounts({ patterns: 3 })))
      renderAs(role)

      expect(await screen.findByText('Nichts zu erledigen.')).toBeInTheDocument()
      expect(within(summary()).queryByRole('link')).not.toBeInTheDocument()
    },
  )

  it('Laden: Skeleton statt einer behaupteten „0“', async () => {
    vi.stubGlobal('fetch', routedFetch('pending'))
    renderAs('editor')

    expect(await screen.findByText('Letzte Aktivitäten')).toBeInTheDocument()
    expect(screen.getByTestId('inbox-summary-loading')).toBeInTheDocument()
    expect(screen.queryByText('Nichts zu erledigen.')).not.toBeInTheDocument()
    expect(screen.queryByText(/Aufgaben? warte/)).not.toBeInTheDocument()
  })

  it('Fehler: Zeile entfällt, restliches Dashboard bleibt stehen', async () => {
    vi.stubGlobal('fetch', routedFetch('fail'))
    renderAs('editor')

    expect(await screen.findByText('Letzte Aktivitäten')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.queryByTestId('inbox-summary-loading')).not.toBeInTheDocument(),
    )
    expect(screen.queryByRole('region', { name: 'Zu erledigen' })).not.toBeInTheDocument()
    expect(screen.queryByText('Nichts zu erledigen.')).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Kennzahlen' })).toBeInTheDocument()
  })

  it.each(['viewer', 'editor', 'admin', null] as const)(
    'Rolle %s: nur noch /inbox/counts, keine Einzelzähler und keine Review-Listen',
    async (role) => {
      const fetchMock = routedFetch(inboxCounts({ memory_approval: 1, total: 1 }))
      vi.stubGlobal('fetch', fetchMock)
      renderAs(role)

      expect(await screen.findByText('Letzte Aktivitäten')).toBeInTheDocument()
      await settle()
      const paths = fetchMock.mock.calls.map(
        ([input]) => new URL(String(input), 'http://x').pathname,
      )
      expect(paths.some((p) => p.endsWith('/inbox/counts'))).toBe(true)
      for (const gone of [
        /\/patterns$/,
        /\/cases\/counts$/,
        /\/memories\/counts$/,
        /\/memory-proposals$/,
        /\/(personas|playbooks|resources)$/,
      ]) {
        expect(paths.filter((p) => gone.test(p))).toHaveLength(0)
      }
    },
  )
})
