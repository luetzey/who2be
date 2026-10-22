import type { Session } from '@supabase/supabase-js'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { StrictMode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Tutorial } from '@/api/client'
import type { Me, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { buildHelpIndex } from '@/help/helpIndex'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { HelpArticlePage, HelpHomePage, HelpMarkdown, HelpNewsPage, HelpTutorialPage } from './HelpPages'

afterEach(() => {
  vi.unstubAllGlobals()
})

// Eigene Testdaten: ein Tutorial und zwei Seiten (eine nur fuer admin).
const tutorialMd = (lang: string) =>
  [
    '---',
    'tutorial: demo',
    `title: Demo-Tutorial ${lang}`,
    'description: Zum Testen.',
    'duration: 4',
    '---',
    '',
    'Einleitung.',
    '',
    '## Automatisch [#auto]',
    '',
    'Hakt sich selbst ab.',
    '',
    '## Seite lesen [#visit]',
    '',
    'Lies [Persona](/help/persona#felder).',
    '',
    '## Von Hand [#manual]',
    '',
    'Hake das selbst ab.',
  ].join('\n')

const pageMd = (lang: string, title: string, audience: string, order: number, body: string) =>
  [
    '---',
    `title: ${title} ${lang}`,
    'description: Beschreibung.',
    'section: bausteine',
    `order: ${order}`,
    'updated: 2026-10-21',
    `audience: ${audience}`,
    '---',
    '',
    'Einleitung der Seite.',
    '',
    '## Felder [#felder]',
    '',
    body,
    '',
    '## Mehr [#mehr]',
    '',
    'Siehe [extern](https://who2be.de).',
  ].join('\n')

/** News-Eintrag in beiden Sprachen (`./news/<slug>.<lang>.md`). */
function newsMd(slug: string, type: string, title: string, extra = ''): Record<string, string> {
  const md = (lang: string) =>
    ['---', `date: ${slug.slice(0, 10)}`, `type: ${type}`, `title: ${title} ${lang}`, extra, '---', '', `Text ${lang}.`]
      .filter((line) => line !== '')
      .join('\n')
  return { [`./news/${slug}.de.md`]: md('de'), [`./news/${slug}.en.md`]: md('en') }
}

const index = buildHelpIndex({
  './tutorials/demo.de.md': tutorialMd('de'),
  './tutorials/demo.en.md': tutorialMd('en'),
  './bausteine/persona.de.md': pageMd('de', 'Persona', 'all', 1, 'Identität und `Ton`.'),
  './bausteine/persona.en.md': pageMd('en', 'Persona', 'all', 1, 'Identity and `tone`.'),
  './bausteine/admin-only.de.md': pageMd('de', 'Abrechnung', 'admin', 2, 'Nur für Admins.'),
  './bausteine/admin-only.en.md': pageMd('en', 'Billing', 'admin', 2, 'Admins only.'),
  ...newsMd('2026-11-13-hilfe', 'new', 'Hilfe-Menü', 'link: /help/persona'),
  ...newsMd('2026-11-02-suche', 'improved', 'Bessere Suche'),
  ...newsMd('2026-10-20-start', 'changed', 'Neuer Start'),
})

function tutorial(overrides: Partial<Tutorial> = {}): Tutorial {
  return {
    id: 'demo',
    audience: 'everyone',
    welcome: false,
    welcome_seen_at: null,
    restarted_at: null,
    completed: false,
    steps: [
      { id: 'auto', type: 'first_mcp_call', page: null, automatic: true, state: 'done', completed_at: null },
      { id: 'visit', type: 'page_visited', page: '/help/persona', automatic: false, state: 'open', completed_at: null },
      { id: 'manual', type: 'manual', page: null, automatic: false, state: 'open', completed_at: null },
    ],
    ...overrides,
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
  body: unknown
}

/** Fetch-Stub: Tutorial-Liste, PATCH/restart antworten mit `afterChange`. */
function stubApi(list: Tutorial[], afterChange?: Tutorial) {
  const calls: Call[] = []
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : null })
    if (url.includes('/v1/me/tutorials')) {
      const payload = method === 'GET' ? list : (afterChange ?? list[0])
      return Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }))
    }
    if (url.endsWith('/v1/me/news-seen') && method === 'PATCH') {
      return Promise.resolve(new Response('{"news_seen_at":"2026-10-22T10:00:00Z"}', { status: 200 }))
    }
    return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

describe('Testdaten', () => {
  it('sind ein gültiger Hilfe-Index', () => {
    expect(index.errors).toEqual([])
  })
})

describe('HelpHomePage', () => {
  it('zeigt Tutorials mit Fortschritt, Nachschlagen nach Rolle und besteht axe', async () => {
    stubApi([tutorial()])
    const { container } = renderInRoutes(<HelpHomePage index={index} />, {
      path: '/w/:workspaceId/help',
      initialEntries: ['/w/ws-1/help'],
      me: meWithRole('editor'),
    })
    const card = await screen.findByTestId('tutorial-card-demo')
    expect(within(card).getByText('Demo-Tutorial de')).toBeInTheDocument()
    expect(within(card).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1')
    // Ein automatisch erkannter Schritt ist echter Fortschritt → „Fortsetzen“.
    expect(within(card).getByRole('link', { name: 'Fortsetzen' })).toHaveAttribute(
      'href',
      '/w/ws-1/help/tutorials/demo',
    )
    expect(screen.getByRole('link', { name: 'Persona de' })).toBeInTheDocument()
    expect(screen.queryByText('Abrechnung de')).not.toBeInTheDocument()
    // Gliederung: Abschnitte h2, Karten- und Gruppentitel h3, keine Überschrift in einer Überschrift.
    expect(screen.getByRole('heading', { level: 2, name: 'Tutorials' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Nachschlagen' })).toBeInTheDocument()
    expect(within(card).getByRole('heading', { level: 3, name: 'Demo-Tutorial de' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Bausteine' })).toBeInTheDocument()
    expect(container.querySelector(':is(h1,h2,h3,h4,h5,h6) :is(h1,h2,h3,h4,h5,h6)')).toBeNull()
    expect(await axe(container)).toHaveNoViolations()
  })

  it('zeigt admin-Seiten nur für admin', async () => {
    const fresh = tutorial()
    fresh.steps[0] = { ...fresh.steps[0], type: 'head_start' }
    stubApi([fresh])
    renderInRoutes(<HelpHomePage index={index} />, {
      path: '/w/:workspaceId/help',
      initialEntries: ['/w/ws-1/help'],
      me: meWithRole('admin'),
    })
    expect(await screen.findByRole('link', { name: 'Abrechnung de' })).toBeInTheDocument()
    // Nur der Startvorsprung ist erledigt → noch nicht begonnen.
    expect(await screen.findByRole('link', { name: 'Starten' })).toBeInTheDocument()
  })

  it('sucht live ab zwei Zeichen und meldet die Trefferzahl', async () => {
    stubApi([tutorial()])
    renderInRoutes(<HelpHomePage index={index} />, {
      path: '/w/:workspaceId/help',
      initialEntries: ['/w/ws-1/help'],
      me: meWithRole('editor'),
    })
    const input = screen.getByLabelText('Hilfe durchsuchen')
    fireEvent.change(input, { target: { value: 'identität' } })
    expect(screen.getByRole('status')).toHaveTextContent('1 Treffer für „identität“')
    expect(screen.getByRole('link', { name: 'Persona de' })).toHaveAttribute('href', '/w/ws-1/help/persona')
    fireEvent.change(input, { target: { value: 'nur für admins' } })
    expect(screen.getByRole('status')).toHaveTextContent('Nichts gefunden.')
  })

  it('startet ein abgeschlossenes Tutorial nach Rückfrage neu', async () => {
    const done = tutorial({
      completed: true,
      steps: tutorial().steps.map((step) => ({ ...step, state: 'done' as const })),
    })
    const calls = stubApi([done], tutorial())
    renderInRoutes(<HelpHomePage index={index} />, {
      path: '/w/:workspaceId/help',
      initialEntries: ['/w/ws-1/help'],
      me: meWithRole('editor'),
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Neu starten' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('„Demo-Tutorial de“ neu starten?')
    const confirm = within(dialog).getByRole('button', { name: 'Neu starten' })
    fireEvent.click(confirm)
    fireEvent.click(confirm)
    await waitFor(() =>
      expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1),
    )
    expect(calls.find((c) => c.method === 'POST')?.url).toContain(
      '/v1/me/tutorials/demo/restart?workspace_id=ws-1',
    )
  })

  it('zeigt die letzten zwei Neuigkeiten mit Link auf „Was ist neu“', async () => {
    stubApi([tutorial()])
    renderInRoutes(<HelpHomePage index={index} />, {
      path: '/w/:workspaceId/help',
      initialEntries: ['/w/ws-1/help'],
      me: meWithRole('editor'),
    })
    const section = await screen.findByRole('region', { name: 'Was ist neu' })
    expect(within(section).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'Hilfe-Menü de',
      'Bessere Suche de',
    ])
    expect(within(section).getByRole('link', { name: 'Alle Neuigkeiten' })).toHaveAttribute(
      'href',
      '/w/ws-1/help/neu',
    )
  })

  it.each([
    ['search', () => screen.getByLabelText('Hilfe durchsuchen')],
    ['tutorials', () => screen.getByRole('heading', { level: 2, name: 'Tutorials' })],
  ] as const)('setzt nach dem Sprung aus dem Menü den Fokus (%s)', async (helpFocus, target) => {
    stubApi([tutorial()])
    renderInRoutes(<HelpHomePage index={index} />, {
      path: '/w/:workspaceId/help',
      initialEntries: [{ pathname: '/w/ws-1/help', state: { helpFocus } }],
      me: meWithRole('editor'),
    })
    await waitFor(() => expect(target()).toHaveFocus())
  })
})

describe('HelpNewsPage', () => {
  beforeEach(() => {
    stubApi([])
  })

  it('gruppiert nach Monat, neueste zuerst, mit Typ und Link, besteht axe', async () => {
    const { container } = renderInRoutes(<HelpNewsPage index={index} />, {
      path: '/w/:workspaceId/help/neu',
      initialEntries: ['/w/ws-1/help/neu'],
      me: meWithRole('editor'),
    })
    expect(screen.getByRole('heading', { level: 1, name: 'Was ist neu' })).toBeInTheDocument()
    const main = screen.getByRole('main')
    expect(within(main).getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'November 2026',
      'Oktober 2026',
    ])
    const november = screen.getByRole('region', { name: 'November 2026' })
    const first = within(november).getByTestId('news-2026-11-13-hilfe')
    expect(within(first).getByText('Neu')).toBeInTheDocument()
    expect(within(first).getByText('Text de.')).toBeInTheDocument()
    expect(within(first).getByRole('link', { name: /Mehr erfahren/ })).toHaveAttribute(
      'href',
      '/w/ws-1/help/persona',
    )
    expect(within(november).getByText('Verbessert')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Oktober 2026' })).getByText('Geändert')).toBeInTheDocument()
    expect(await axe(container)).toHaveNoViolations()
  })

  it('zeigt einen leeren Zustand ohne Einträge', () => {
    renderInRoutes(<HelpNewsPage index={buildHelpIndex({})} />, {
      path: '/w/:workspaceId/help/neu',
      initialEntries: ['/w/ws-1/help/neu'],
      me: meWithRole('editor'),
    })
    expect(screen.getByText(/Noch keine Neuigkeiten/)).toBeInTheDocument()
  })

  it('setzt beim Öffnen „gesehen“ genau einmal und lädt danach /v1/me neu (Spec §5.4)', async () => {
    const calls = stubApi([])
    const refreshMe = vi.fn().mockResolvedValue(undefined)
    const me = meWithRole('editor')
    const page = (
      <SessionContext.Provider
        value={{
          session: { access_token: 'tok' } as unknown as Session,
          me,
          sessionLoaded: true,
          signIn: vi.fn(),
          signOut: vi.fn(),
          refreshMe,
        }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/help/neu']}>
            <Routes>
              <Route path="/w/:workspaceId/help/neu" element={<HelpNewsPage index={index} />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>
    )
    const { rerender } = render(<StrictMode>{page}</StrictMode>)
    await waitFor(() => expect(refreshMe).toHaveBeenCalledTimes(1))
    // Neues `me` nach dem Reload (bzw. jedes weitere Rendern) loest keinen
    // zweiten PATCH aus; der doppelte Effekt im StrictMode auch nicht.
    rerender(<StrictMode>{page}</StrictMode>)
    await act(async () => {})
    const patches = calls.filter((c) => c.method === 'PATCH')
    expect(patches).toHaveLength(1)
    expect(patches[0].url).toMatch(/\/v1\/me\/news-seen$/)
    expect(refreshMe).toHaveBeenCalledTimes(1)
  })

  it('lädt /v1/me nicht neu, wenn das Setzen scheitert', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"detail":"nein"}', { status: 403 }))
    vi.stubGlobal('fetch', fetchMock)
    const refreshMe = vi.fn()
    render(
      <SessionContext.Provider
        value={{
          session: { access_token: 'tok' } as unknown as Session,
          me: meWithRole('editor'),
          sessionLoaded: true,
          signIn: vi.fn(),
          signOut: vi.fn(),
          refreshMe,
        }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/help/neu']}>
            <Routes>
              <Route path="/w/:workspaceId/help/neu" element={<HelpNewsPage index={index} />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await act(async () => {})
    expect(refreshMe).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { level: 1, name: 'Was ist neu' })).toBeInTheDocument()
  })
})

describe('HelpArticlePage', () => {
  it('rendert Markdown ohne HTML, Anker, Navigation und meldet den Seitenbesuch', async () => {
    const calls = stubApi([tutorial()])
    const { container } = renderInRoutes(<HelpArticlePage index={index} />, {
      path: '/w/:workspaceId/help/:slug',
      initialEntries: ['/w/ws-1/help/persona'],
      me: meWithRole('editor'),
    })
    expect(screen.getByRole('heading', { level: 1, name: 'Persona de' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Felder' })).toHaveAttribute('id', 'felder')
    expect(screen.getByText(/Aktualisiert am .* · 1 Min\. Lesezeit/)).toBeInTheDocument()
    const external = screen.getByRole('link', { name: 'extern' })
    expect(external).toHaveAttribute('href', 'https://who2be.de')
    expect(external).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getAllByRole('link', { name: 'Persona de' })[0]).toHaveAttribute('aria-current', 'page')
    await waitFor(() => expect(calls.filter((c) => c.method === 'PATCH')).toHaveLength(1))
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ step_id: 'visit', state: 'done' })
    expect(await axe(container)).toHaveNoViolations()
  })

  it('löst unbekannte und nicht freigegebene Slugs nicht auf', () => {
    stubApi([])
    renderInRoutes(<HelpArticlePage index={index} />, {
      path: '/w/:workspaceId/help/:slug',
      initialEntries: ['/w/ws-1/help/admin-only'],
      me: meWithRole('editor'),
    })
    expect(screen.getByText('Diese Hilfe-Seite gibt es nicht.')).toBeInTheDocument()
  })
})

describe('HelpMarkdown', () => {
  it('rendert Raw-HTML als Text und lässt unsichere Links fallen', () => {
    stubApi([])
    const { container } = renderInRoutes(
      <HelpMarkdown>
        {'Text <b>fett</b> <img src=x onerror=alert(1)>\n\n[böse](javascript:alert(1)) [gut](/help/persona)'}
      </HelpMarkdown>,
      { path: '/w/:workspaceId/help', initialEntries: ['/w/ws-1/help'] },
    )
    const main = container.querySelector('main') ?? container
    expect(main.querySelector('b, img, script')).toBeNull()
    expect(main).toHaveTextContent('<b>fett</b>')
    expect(screen.queryByRole('link', { name: 'böse' })).toBeNull()
    expect(screen.getByText('böse')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'gut' })).toHaveAttribute('href', '/w/ws-1/help/persona')
  })
})

describe('HelpTutorialPage', () => {
  it('zeigt Schritte aus dem Server mit Text je Sprache und besteht axe', async () => {
    stubApi([tutorial()])
    const { container } = renderInRoutes(<HelpTutorialPage index={index} />, {
      path: '/w/:workspaceId/help/tutorials/:tutorialId',
      initialEntries: ['/w/ws-1/help/tutorials/demo'],
      me: meWithRole('editor'),
    })
    expect(await screen.findByRole('heading', { level: 1, name: 'Demo-Tutorial de' })).toBeInTheDocument()
    const steps = screen.getAllByRole('listitem').filter((li) => li.querySelector('h2'))
    expect(steps.map((li) => li.querySelector('h2')?.id)).toEqual(['auto', 'visit', 'manual'])
    expect(screen.getByText('Hake das selbst ab.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Seite öffnen' })).toHaveAttribute('href', '/w/ws-1/help/persona')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hakt einen manuellen Schritt einmal ab, auch bei Doppelklick', async () => {
    const after = tutorial()
    after.steps[2] = { ...after.steps[2], state: 'done' }
    const calls = stubApi([tutorial()], after)
    renderInRoutes(<HelpTutorialPage index={index} />, {
      path: '/w/:workspaceId/help/tutorials/:tutorialId',
      initialEntries: ['/w/ws-1/help/tutorials/demo'],
      me: meWithRole('editor'),
    })
    const button = await screen.findByRole('button', { name: 'Erledigt' })
    fireEvent.click(button)
    fireEvent.click(button)
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Erledigt' })).toBeNull())
    expect(calls.filter((c) => c.method === 'PATCH')).toEqual([
      {
        url: expect.stringContaining('/v1/me/tutorials/demo?workspace_id=ws-1') as string,
        method: 'PATCH',
        body: { step_id: 'manual', state: 'done' },
      },
    ])
  })

  it('setzt eine unbekannte Tutorial-ID aus der URL nie in einen API-Pfad', async () => {
    const calls = stubApi([tutorial()])
    renderInRoutes(<HelpTutorialPage index={index} />, {
      path: '/w/:workspaceId/help/tutorials/:tutorialId',
      initialEntries: ['/w/ws-1/help/tutorials/..%2Fadmin'],
      me: meWithRole('editor'),
    })
    expect(await screen.findByText('Dieses Tutorial gibt es nicht.')).toBeInTheDocument()
    const tutorialCalls = calls.filter((c) => c.url.includes('/v1/me/'))
    expect(tutorialCalls.map((c) => `${c.method} ${new URL(c.url).pathname}`)).toEqual([
      'GET /v1/me/tutorials',
    ])
  })
})
