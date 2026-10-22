import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Tutorial, TutorialStep } from '@/api/client'
import type { Me, WorkspaceRole } from '@/api/types'
import { buildHelpIndex } from '@/help/helpIndex'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { TutorialChecklist } from './TutorialChecklist'

afterEach(() => {
  vi.unstubAllGlobals()
})

// Test-Tutorial mit allen Schritt-Typen des Katalogs (ADR-0060 §3): die
// Komponente kennt keinen Schritt beim Namen, alles kommt aus API + Markdown.
const tutorialMd = (lang: string) =>
  [
    '---',
    'tutorial: probe',
    `title: Probe-Liste ${lang}`,
    'description: Zum Testen.',
    'duration: 7',
    '---',
    '',
    'Einleitung.',
    '',
    '## Schon da [#head]',
    '',
    'Gibt es von Anfang an.',
    '',
    '## Verbinden [#connect]',
    '',
    'Verbinde den Agenten.',
    '',
    '## Agent anlegen [#create]',
    '',
    'Leg einen Agenten an.',
    '',
    '## Eigener Abruf [#own]',
    '',
    'Dein Agent ruft ab.',
    '',
    '## Seite lesen [#visit]',
    '',
    'Lies die Seite.',
    '',
    '## Von Hand [#manual]',
    '',
    'Hake das selbst ab.',
  ].join('\n')

const otherMd = (lang: string) =>
  ['---', 'tutorial: other', `title: Andere ${lang}`, 'description: x', 'duration: 2', '---', '', '## A [#a]', '', 'a'].join(
    '\n',
  )

const index = buildHelpIndex({
  './tutorials/probe.de.md': tutorialMd('de'),
  './tutorials/probe.en.md': tutorialMd('en'),
  './tutorials/other.de.md': otherMd('de'),
  './tutorials/other.en.md': otherMd('en'),
})

const NOW = Date.parse('2026-10-22T12:00:00Z')

function step(id: string, type: TutorialStep['type'], extra: Partial<TutorialStep> = {}): TutorialStep {
  const automatic = ['first_mcp_call', 'agent_created', 'own_agent_mcp_call'].includes(type)
  return {
    id,
    type,
    page: null,
    automatic,
    state: type === 'head_start' ? 'done' : 'open',
    completed_at: null,
    ...extra,
  }
}

function probe(overrides: Partial<Tutorial> = {}): Tutorial {
  return {
    id: 'probe',
    audience: 'everyone',
    welcome: true,
    welcome_seen_at: null,
    restarted_at: null,
    completed: false,
    steps: [
      step('head', 'head_start', { completed_at: '2026-10-22T10:00:00Z' }),
      step('connect', 'first_mcp_call'),
      step('create', 'agent_created'),
      step('own', 'own_agent_mcp_call'),
      step('visit', 'page_visited', { page: '/help/feedback-and-cases' }),
      step('manual', 'manual'),
    ],
    ...overrides,
  }
}

function allDone(at: string): Tutorial {
  const base = probe()
  return {
    ...base,
    completed: true,
    steps: base.steps.map((s) => ({ ...s, state: 'done' as const, completed_at: at })),
  }
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

interface Call {
  url: string
  method: string
  body: { step_id?: string; state?: string } | null
}

/**
 * Fetch-Stub: GET liefert `lists` der Reihe nach, danach den Stand nach den
 * Aenderungen (wie der Server). PATCH
 * antwortet mit dem Tutorial, in dem der Schritt umgestellt ist — ausser der
 * Schritt steht in `failOn`.
 */
function stubApi(lists: Array<Tutorial[] | 'fail'>, failOn: string[] = []) {
  const calls: Call[] = []
  let current = lists[0] === 'fail' ? [] : lists[0]
  let gets = 0
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const body = init?.body ? (JSON.parse(String(init.body)) as Call['body']) : null
    calls.push({ url, method, body })
    const json = (payload: unknown, status = 200) =>
      Promise.resolve(new Response(JSON.stringify(payload), { status }))
    if (!url.includes('/v1/me/tutorials')) return json({ detail: 'nope' }, 500)
    if (method === 'GET') {
      const answer = gets < lists.length ? lists[gets] : current
      gets += 1
      if (answer === 'fail') return json({ detail: 'kaputt' }, 500)
      current = answer
      return json(answer)
    }
    if (body?.step_id !== undefined && failOn.includes(body.step_id)) {
      return json({ detail: 'nein' }, 500)
    }
    const tutorial = current.find((t) => url.includes(`/v1/me/tutorials/${t.id}`)) ?? current[0]
    const next: Tutorial = {
      ...tutorial,
      steps: tutorial.steps.map((s) =>
        s.id === body?.step_id ? { ...s, state: body.state as TutorialStep['state'] } : s,
      ),
    }
    current = current.map((t) => (t.id === next.id ? next : t))
    return json(next)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

function renderChecklist(role: WorkspaceRole = 'editor', now = NOW) {
  return renderInRoutes(<TutorialChecklist index={index} now={now} />, {
    path: '/w/:workspaceId/dashboard',
    initialEntries: ['/w/ws-1/dashboard'],
    me: meWithRole(role),
  })
}

describe('TutorialChecklist', () => {
  it('rendert das Test-Tutorial aus API und Markdown, nächster Schritt offen, besteht axe', async () => {
    stubApi([[probe()]])
    const { container } = renderChecklist()

    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })
    expect(within(card).getByText('1 von 6 erledigt · etwa 7 Minuten')).toBeInTheDocument()
    expect(within(card).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1')
    expect(within(card).getByRole('progressbar')).toHaveAttribute('aria-valuemax', '6')

    const rows = within(card).getAllByRole('button', { expanded: false })
    expect(rows.map((r) => r.textContent)).toContain('Schon da (erledigt)')
    // Der erste offene Schritt ist aufgeklappt und als „als Nächstes“ benannt.
    const next = within(card).getByRole('button', { name: 'Verbinden (als Nächstes)' })
    expect(next).toHaveAttribute('aria-expanded', 'true')
    expect(within(card).getByText('Verbinde den Agenten.')).toBeVisible()
    expect(within(card).getByRole('link', { name: 'Zu den Agents' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents',
    )
    const panel = document.getElementById(next.getAttribute('aria-controls') ?? '')
    expect(panel).not.toBeNull()
    expect(within(panel as HTMLElement).getByText(/hakt Who2Be selbst ab/)).toBeVisible()
    // Andere Schritte sind zu, ihr Text ist nicht sichtbar.
    expect(within(card).getByText('Hake das selbst ab.')).not.toBeVisible()

    expect(await axe(container)).toHaveNoViolations()
  })

  it('zeigt je Schritt-Typ die passende Aktion', async () => {
    stubApi([[probe()]])
    renderChecklist()
    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })

    fireEvent.click(within(card).getByRole('button', { name: 'Seite lesen' }))
    expect(within(card).getByRole('link', { name: 'Seite öffnen' })).toHaveAttribute(
      'href',
      '/w/ws-1/help/feedback-and-cases',
    )
    // Nur ein Schritt ist aufgeklappt.
    expect(within(card).getByText('Verbinde den Agenten.')).not.toBeVisible()

    fireEvent.click(within(card).getByRole('button', { name: 'Von Hand' }))
    expect(within(card).getByRole('button', { name: 'Erledigt' })).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: 'Überspringen' })).toBeInTheDocument()
  })

  it('hakt einen manuellen Schritt ab, ohne Doppel-Submit', async () => {
    const calls = stubApi([[probe()]])
    renderChecklist()
    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })
    fireEvent.click(within(card).getByRole('button', { name: 'Von Hand' }))
    const done = within(card).getByRole('button', { name: 'Erledigt' })
    fireEvent.click(done)
    fireEvent.click(done)
    await waitFor(() => expect(within(card).getByText('2 von 6 erledigt · etwa 7 Minuten')).toBeInTheDocument())
    const patches = calls.filter((c) => c.method === 'PATCH')
    expect(patches).toHaveLength(1)
    expect(patches[0].body).toEqual({ step_id: 'manual', state: 'done' })
    expect(patches[0].url).toContain('/v1/me/tutorials/probe?workspace_id=ws-1')
  })

  it('Ausblenden überspringt alle offenen Schritte nacheinander und verschwindet', async () => {
    const calls = stubApi([[probe()]])
    renderChecklist()
    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })
    const hide = within(card).getByRole('button', { name: 'Ausblenden' })
    fireEvent.click(hide)
    fireEvent.click(hide)
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: 'Probe-Liste de' })).not.toBeInTheDocument(),
    )
    const patches = calls.filter((c) => c.method === 'PATCH').map((c) => c.body)
    expect(patches).toEqual([
      { step_id: 'connect', state: 'skipped' },
      { step_id: 'create', state: 'skipped' },
      { step_id: 'own', state: 'skipped' },
      { step_id: 'visit', state: 'skipped' },
      { step_id: 'manual', state: 'skipped' },
    ])
    expect(await screen.findByText(/Ausgeblendet\. Du findest „Probe-Liste de“/)).toBeInTheDocument()
  })

  it('Ausblenden mit Teilfehler: Fehler sichtbar, Liste neu geladen, bleibt stehen', async () => {
    const calls = stubApi([[probe()]], ['own'])
    renderChecklist()
    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })
    fireEvent.click(within(card).getByRole('button', { name: 'Ausblenden' }))
    expect(await screen.findByText(/Ausblenden hat nicht ganz geklappt/)).toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'PATCH').map((c) => c.body?.step_id)).toEqual([
      'connect',
      'create',
      'own',
    ])
    await waitFor(() => expect(calls.filter((c) => c.method === 'GET' && c.url.includes('/v1/me/tutorials'))).toHaveLength(2))
    // Die ersten beiden sind wirklich übersprungen; die Liste bleibt mit dem Rest.
    const region = await screen.findByRole('region', { name: 'Probe-Liste de' })
    expect(within(region).getByRole('button', { name: 'Eigener Abruf (als Nächstes)' })).toBeInTheDocument()
  })

  it('viewer: Liste ohne Agent-Schritte', async () => {
    stubApi([[probe()]])
    renderChecklist('viewer')
    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })
    expect(within(card).getByText('1 von 4 erledigt · etwa 7 Minuten')).toBeInTheDocument()
    expect(within(card).queryByText('Agent anlegen')).not.toBeInTheDocument()
    expect(within(card).queryByText('Eigener Abruf')).not.toBeInTheDocument()
  })

  it('zeigt nur Tutorials mit welcome und Text in der Sprache', async () => {
    stubApi([
      [
        probe(),
        { ...probe({ id: 'other', welcome: false }), steps: [step('a', 'manual')] },
        { ...probe({ id: 'ohne-text' }) },
      ],
    ])
    renderChecklist()
    await screen.findByRole('region', { name: 'Probe-Liste de' })
    expect(screen.queryByText('Andere de')).not.toBeInTheDocument()
    expect(screen.getAllByTestId(/^tutorial-checklist-/)).toHaveLength(1)
  })

  it('„Du bist startklar“ bis 7 Tage nach dem letzten Haken, danach nichts', async () => {
    // Genau 7 Tage her: steht noch.
    stubApi([[allDone('2026-10-15T12:00:00Z')]])
    const { unmount } = renderChecklist()
    const card = await screen.findByRole('region', { name: 'Du bist startklar' })
    expect(within(card).getByRole('link', { name: 'Zur Hilfe' })).toHaveAttribute('href', '/w/ws-1/help')
    expect(within(card).queryByRole('button', { name: 'Ausblenden' })).not.toBeInTheDocument()
    unmount()

    // Letzter Haken 7 Tage und 1 Minute her: abgelaufen.
    stubApi([[allDone('2026-10-15T11:59:00Z')]])
    const { container } = renderChecklist()
    await waitFor(() => expect(container.querySelector('[aria-busy="true"]')).toBeNull())
    expect(screen.queryByTestId(/^tutorial-checklist-/)).not.toBeInTheDocument()
    expect(screen.queryByText('Erste Schritte')).not.toBeInTheDocument()
  })

  it('übersprungene Schritte zählen nicht als „startklar“: dann keine Karte', async () => {
    const skipped = allDone('2026-10-22T11:00:00Z')
    skipped.steps[2] = { ...skipped.steps[2], state: 'skipped' }
    stubApi([[skipped]])
    const { container } = renderChecklist()
    await waitFor(() => expect(container.querySelector('[aria-busy="true"]')).toBeNull())
    expect(screen.queryByText('Du bist startklar')).not.toBeInTheDocument()
    expect(screen.queryByTestId(/^tutorial-checklist-/)).not.toBeInTheDocument()
  })

  it('Laden: Skeleton; Fehler: Meldung mit „Erneut versuchen“', async () => {
    stubApi(['fail', [probe()]])
    renderChecklist()
    expect(screen.getByRole('region', { name: 'Erste Schritte' })).toHaveTextContent('Lädt')
    expect(await screen.findByText('Erste Schritte konnten nicht geladen werden.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByRole('region', { name: 'Probe-Liste de' })).toBeInTheDocument()
  })

  it('lädt neu, wenn der Tab zurückkommt, ohne den Stand wegzunehmen', async () => {
    const connected = probe()
    connected.steps[1] = { ...connected.steps[1], state: 'done', completed_at: '2026-10-22T11:00:00Z' }
    const calls = stubApi([[probe()], [connected]])
    renderChecklist()
    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })
    expect(within(card).getByText('1 von 6 erledigt · etwa 7 Minuten')).toBeInTheDocument()

    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    // Waehrend des Neu-Ladens bleibt die Karte stehen (kein Skeleton).
    expect(screen.getByRole('region', { name: 'Probe-Liste de' })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByText('2 von 6 erledigt · etwa 7 Minuten')).toBeInTheDocument(),
    )
    expect(calls.filter((c) => c.method === 'GET' && c.url.includes('/v1/me/tutorials'))).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Agent anlegen (als Nächstes)' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it('setzt beim Sprung aus dem „?“-Menü den Fokus auf die Überschrift', async () => {
    stubApi([[probe()]])
    renderInRoutes(<TutorialChecklist index={index} now={NOW} />, {
      path: '/w/:workspaceId/dashboard',
      initialEntries: [{ pathname: '/w/ws-1/dashboard', state: { focusTutorial: 'probe' } }],
      me: meWithRole('editor'),
    })
    const card = await screen.findByRole('region', { name: 'Probe-Liste de' })
    await waitFor(() => expect(within(card).getByText('Probe-Liste de')).toHaveFocus())
  })
})
