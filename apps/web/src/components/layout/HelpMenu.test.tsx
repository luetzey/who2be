import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Tutorial, TutorialStep } from '@/api/client'
import type { Me, WorkspaceRole } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

// Feste Eintraege „Was ist neu“ statt des ausgelieferten Inhalts, damit die
// Punkt-Regel nicht vom naechsten News-Eintrag abhaengt. Es bleibt derselbe
// Loader (`helpIndex.news`), nur mit anderen Daten.
vi.mock('@/help/helpIndex', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/help/helpIndex')>()
  const md = (date: string, lang: string) =>
    ['---', `date: ${date}`, 'type: new', `title: Neu ${lang}`, '---', '', `Text ${lang}.`].join('\n')
  return {
    ...original,
    helpIndex: original.buildHelpIndex({
      './news/2026-10-20-neu.de.md': md('2026-10-20', 'de'),
      './news/2026-10-20-neu.en.md': md('2026-10-20', 'en'),
      './news/2026-09-01-alt.de.md': md('2026-09-01', 'de'),
      './news/2026-09-01-alt.en.md': md('2026-09-01', 'en'),
    }),
  }
})

// Radix DropdownMenu braucht PointerCapture/scrollIntoView, die jsdom fehlen.
beforeAll(() => {
  for (const name of ['hasPointerCapture', 'releasePointerCapture', 'setPointerCapture', 'scrollIntoView']) {
    Object.defineProperty(window.HTMLElement.prototype, name, {
      value: () => undefined,
      configurable: true,
    })
  }
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function step(id: string, type: TutorialStep['type'], state: TutorialStep['state'] = 'open'): TutorialStep {
  return { id, type, page: null, automatic: type !== 'manual', state, completed_at: null }
}

// Bewusst NICHT „getting-started“: das Menue findet „Erste Schritte“ ueber
// `welcome: true`, nie ueber eine feste ID (Review B3).
const WELCOME_ID = 'start-probe'

function welcome(states: Partial<Record<string, TutorialStep['state']>> = {}): Tutorial {
  return {
    id: WELCOME_ID,
    audience: 'everyone',
    welcome: true,
    welcome_seen_at: null,
    restarted_at: null,
    completed: false,
    steps: [
      step('head', 'head_start', 'done'),
      step('connect', 'first_mcp_call', states.connect ?? 'open'),
      step('create', 'agent_created', states.create ?? 'open'),
      step('manual', 'manual', states.manual ?? 'open'),
    ],
  }
}

/**
 * Zweites Tutorial ohne `welcome`, in der API-Liste VOR dem Willkommens-
 * Tutorial und mit der ID, die eine hart codierte Suche treffen wuerde.
 */
function other(): Tutorial {
  return {
    id: 'getting-started',
    audience: 'everyone',
    welcome: false,
    welcome_seen_at: null,
    restarted_at: null,
    completed: false,
    steps: [step('x', 'manual', 'done'), step('y', 'manual', 'skipped')],
  }
}

interface Call {
  url: string
  method: string
  body: { step_id?: string; state?: string } | null
}

/** Fetch-Stub fuer `/v1/me/tutorials` (GET, PATCH, POST …/restart); alles andere 500. */
function stubApi(initial: Tutorial[]) {
  const calls: Call[] = []
  let current = initial
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      const body = init?.body ? (JSON.parse(String(init.body)) as Call['body']) : null
      const json = (payload: unknown, status = 200) =>
        Promise.resolve(new Response(JSON.stringify(payload), { status }))
      if (!url.includes('/v1/me/tutorials')) return json({ detail: 'nope' }, 500)
      calls.push({ url, method, body })
      if (method === 'GET') return json(current)
      const tutorial = current.find((t) => new RegExp(`/v1/me/tutorials/${t.id}(/|\\?|$)`).test(url))
      if (tutorial === undefined) return json({ detail: 'unbekannt' }, 404)
      const next: Tutorial = url.includes('/restart')
        ? { ...tutorial, steps: tutorial.steps.map((s) => (s.type === 'head_start' ? s : { ...s, state: 'open' })) }
        : {
            ...tutorial,
            steps: tutorial.steps.map((s) =>
              s.id === body?.step_id ? { ...s, state: body.state as TutorialStep['state'] } : s,
            ),
          }
      current = current.map((t) => (t.id === next.id ? next : t))
      return json(next)
    }),
  )
  return calls
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

/** Zeigt Pfad und Router-State, damit der Test die Spruenge pruefen kann. */
function LocationProbe() {
  const location = useLocation()
  return (
    <output data-testid="location">
      {location.pathname}
      {location.state ? ` ${JSON.stringify(location.state)}` : ''}
    </output>
  )
}

function renderShell(role: WorkspaceRole = 'editor', account: Partial<Me> = {}) {
  return renderInRoutes(<LocationProbe />, {
    path: '/w/:workspaceId/*',
    initialEntries: ['/w/ws-1/agents'],
    me: { ...meWithRole(role), ...account },
  })
}

async function openMenu() {
  fireEvent.keyDown(screen.getByRole('button', { name: 'Hilfe und Neuigkeiten' }), { key: 'Enter' })
  return screen.findByTestId('help-menu')
}

function tutorialCalls(calls: Call[], method: string) {
  return calls.filter((c) => c.method === method)
}

describe('HelpMenu', () => {
  describe('Punkt bei ungesehenen Neuigkeiten (Spec §5.4)', () => {
    // Nur `Date` faken: Timer bleiben echt, sonst haengen waitFor und Radix.
    function at(iso: string) {
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date(iso))
    }

    afterEach(() => {
      vi.useRealTimers()
    })

    /** Wartet, bis der nachgeladene Hilfe-Index da ist; danach steht der Punkt fest. */
    async function settled() {
      await act(async () => {
        await vi.dynamicImportSettled()
      })
    }

    const dot = () => screen.queryByTestId('help-menu-news-dot')
    const trigger = () => screen.getByTestId('help-menu-trigger')

    it('zeigt den Punkt bei einem Eintrag nach news_seen_at, mit Screenreader-Text, besteht axe', async () => {
      at('2026-10-22T10:00:00Z')
      stubApi([welcome()])
      const { container } = renderShell('editor', {
        news_seen_at: '2026-10-19T08:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
      })
      expect(await screen.findByTestId('help-menu-news-dot')).toHaveAttribute('aria-hidden', 'true')
      expect(trigger()).toHaveAccessibleName('Hilfe und Neuigkeiten, neue Einträge in „Was ist neu“')
      expect(await axe(container)).toHaveNoViolations()
    })

    it('kein Punkt, wenn news_seen_at nach dem neuesten Eintrag liegt (auch am selben Tag)', async () => {
      at('2026-10-22T10:00:00Z')
      stubApi([welcome()])
      renderShell('editor', { news_seen_at: '2026-10-20T09:30:00Z', created_at: '2026-01-01T00:00:00Z' })
      await settled()
      expect(dot()).toBeNull()
      expect(trigger()).toHaveAccessibleName('Hilfe und Neuigkeiten')
    })

    it('ohne news_seen_at: Punkt bei einem Eintrag nach der Kontoanlage, höchstens 14 Tage alt', async () => {
      at('2026-10-22T10:00:00Z')
      stubApi([welcome()])
      renderShell('editor', { news_seen_at: null, created_at: '2026-08-01T00:00:00Z' })
      expect(await screen.findByTestId('help-menu-news-dot')).toBeInTheDocument()
    })

    it('ohne news_seen_at: kein Punkt, wenn der neueste Eintrag älter als 14 Tage ist', async () => {
      // 2026-10-20 + 14 Tage = 2026-11-03 00:00 UTC; einen Tag danach ist er zu alt.
      at('2026-11-04T00:00:00Z')
      stubApi([welcome()])
      renderShell('editor', { news_seen_at: null, created_at: '2026-08-01T00:00:00Z' })
      await settled()
      expect(dot()).toBeNull()
    })

    it('ohne news_seen_at: kein Punkt für Einträge vor der Kontoanlage', async () => {
      at('2026-10-22T10:00:00Z')
      stubApi([welcome()])
      renderShell('editor', { news_seen_at: null, created_at: '2026-10-21T12:00:00Z' })
      await settled()
      expect(dot()).toBeNull()
    })

    it('kein Punkt, solange das Konto beide Felder nicht kennt (alte API, Token-Pfad)', async () => {
      at('2026-10-22T10:00:00Z')
      stubApi([welcome()])
      renderShell('editor', { news_seen_at: null, created_at: null })
      await settled()
      expect(dot()).toBeNull()
      expect(trigger()).toHaveAccessibleName('Hilfe und Neuigkeiten')
    })
  })

  it('lädt erst beim Öffnen und zeigt die Einträge in fester Reihenfolge, besteht axe', async () => {
    const calls = stubApi([other(), welcome()])
    const { container } = renderShell()
    // Kein Abruf auf jeder Seite.
    await act(async () => {})
    expect(calls).toHaveLength(0)

    const menu = await openMenu()
    await within(menu).findByText('Erste Schritte')
    expect(tutorialCalls(calls, 'GET')).toHaveLength(1)
    expect(within(menu).getAllByRole('menuitem').map((item) => item.textContent)).toEqual([
      'Erste Schritte1 von 4',
      'Tutorials',
      'Hilfe durchsuchen',
      'Was ist neu',
      'Einführung erneut starten',
      'Problem melden',
    ])
    expect(await axe(container)).toHaveNoViolations()
  })

  it('blendet „Erste Schritte“ aus, wenn alles erledigt ist; viewer zählt nur seine Schritte', async () => {
    stubApi([other(), welcome({ connect: 'done', manual: 'done' })])
    renderShell('viewer')
    let menu = await openMenu()
    await waitFor(() =>
      expect(within(menu).getByRole('menuitem', { name: 'Einführung erneut starten' })).not.toHaveAttribute(
        'data-disabled',
      ),
    )
    // viewer: „Agent anlegen“ gehört nicht zu seinen Schritten → alles erledigt.
    expect(within(menu).queryByText('Erste Schritte')).toBeNull()

    fireEvent.keyDown(menu, { key: 'Escape' })
    vi.unstubAllGlobals()
    stubApi([other(), welcome({ manual: 'done' })])
    menu = await openMenu()
    expect(await within(menu).findByText('2 von 3')).toBeInTheDocument()
  })

  it('springt mit Router-State zu Tutorials, Suche, Neuigkeiten und Problem melden', async () => {
    stubApi([other(), welcome()])
    renderShell()
    const cases: Array<[string, string]> = [
      ['Tutorials', '/w/ws-1/help {"helpFocus":"tutorials"}'],
      ['Hilfe durchsuchen', '/w/ws-1/help {"helpFocus":"search"}'],
      ['Was ist neu', '/w/ws-1/help/neu'],
      ['Problem melden', '/w/ws-1/feedback/report'],
    ]
    for (const [label, target] of cases) {
      const menu = await openMenu()
      fireEvent.click(within(menu).getByRole('menuitem', { name: label }))
      await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(target))
    }
  })

  it('„Erste Schritte“ holt eine ausgeblendete Liste zurück und springt ins Dashboard', async () => {
    const calls = stubApi([other(), welcome({ connect: 'skipped', create: 'skipped', manual: 'done' })])
    renderShell()
    const menu = await openMenu()
    fireEvent.click(await within(menu).findByRole('menuitem', { name: /Erste Schritte/ }))
    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/w/ws-1/dashboard {"focusTutorial":"start-probe"}',
      ),
    )
    // Uebersprungenes wird wieder offen, Erledigtes bleibt.
    expect(tutorialCalls(calls, 'PATCH').map((c) => c.body)).toEqual([
      { step_id: 'connect', state: 'open' },
      { step_id: 'create', state: 'open' },
    ])
  })

  it('startet die Einführung ohne Rückfrage neu, solange nichts begonnen ist', async () => {
    const calls = stubApi([other(), welcome()])
    renderShell()
    const menu = await openMenu()
    const replay = await within(menu).findByRole('menuitem', { name: 'Einführung erneut starten' })
    await waitFor(() => expect(replay).not.toHaveAttribute('data-disabled'))
    fireEvent.click(replay)
    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/w/ws-1/dashboard {"replayWelcome":true,"focusTutorial":"start-probe"}',
      ),
    )
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(tutorialCalls(calls, 'POST')).toHaveLength(1)
    expect(tutorialCalls(calls, 'POST')[0].url).toContain('/v1/me/tutorials/start-probe/restart')
  })

  it('fragt vor dem Neustart nach, wenn Fortschritt verloren geht', async () => {
    const calls = stubApi([other(), welcome({ manual: 'done' })])
    renderShell()
    const menu = await openMenu()
    const replay = await within(menu).findByRole('menuitem', { name: 'Einführung erneut starten' })
    await waitFor(() => expect(replay).not.toHaveAttribute('data-disabled'))
    fireEvent.click(replay)
    const dialog = await screen.findByRole('dialog', { name: '„Erste Schritte“ neu starten?' })
    expect(tutorialCalls(calls, 'POST')).toHaveLength(0)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Neu starten' }))
    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent('"replayWelcome":true'),
    )
    expect(tutorialCalls(calls, 'POST')).toHaveLength(1)
    expect(tutorialCalls(calls, 'POST')[0].url).toContain(`/v1/me/tutorials/${WELCOME_ID}/restart`)
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
