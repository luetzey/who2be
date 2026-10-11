import type { Session } from '@supabase/supabase-js'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { ThemeProvider } from '@/app/ThemeProvider'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import i18n from '@/i18n'

import { AppShell } from './AppShell'

// Issue #500 (W1 von #431): Off-Canvas-Navigation. Unterhalb `md` ersetzt ein
// Sheet, das ueber einen Hamburger-Trigger im Header oeffnet, die Sidebar;
// ab `md` bleibt die Sidebar sichtbar. Sichtbarkeit selbst laeuft rein ueber
// CSS-Klassen (`hidden md:flex` / `md:hidden`) — echtes Viewport-Rendering
// ist Sache von Playwright/W4, hier pruefen wir Struktur + Verhalten.

// Radix DropdownMenu (Theme-/Language-Switcher, WorkspaceSwitcher) nutzt
// PointerCapture- und scrollIntoView-APIs, die jsdom nicht implementiert —
// gleicher Stub wie in WorkspaceSwitcher.test.tsx.
beforeAll(() => {
  Object.defineProperty(window.HTMLElement.prototype, 'hasPointerCapture', {
    value: () => false,
    configurable: true,
  })
  Object.defineProperty(window.HTMLElement.prototype, 'releasePointerCapture', {
    value: () => undefined,
    configurable: true,
  })
  Object.defineProperty(window.HTMLElement.prototype, 'setPointerCapture', {
    value: () => undefined,
    configurable: true,
  })
  Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
    value: () => undefined,
    configurable: true,
  })
})

const MOBILE_QUERY = '(max-width: 767px)'

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Persoenlich',
        slug: 'personal',
        kind: 'personal',
        workspaces: [
          { id: 'ws-1', name: 'Mein Workspace', slug: 'mein', role: 'admin' },
        ],
      },
    ],
  }
}

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

function renderShell(options?: { onSignOut?: () => void; initialPath?: string }) {
  const onSignOut = options?.onSignOut ?? vi.fn()
  const initialPath = options?.initialPath ?? '/w/ws-1/dashboard'
  return render(
    <SessionContext.Provider
      value={{
        session,
        me: buildMe(),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <AuthTokenProvider>
        <ThemeProvider>
          <MemoryRouter initialEntries={[initialPath]}>
            <Routes>
              <Route
                path="/w/:workspaceId/*"
                element={
                  <>
                    <AppShell onSignOut={onSignOut}>
                      <span>Seiteninhalt</span>
                    </AppShell>
                    <LocationProbe />
                  </>
                }
              />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

// Die Glocke zaehlt ueber `GET /inbox/counts` (Navigation W1). Standard:
// Antwort mit `total`; einzelne Tests stellen den Wert oder einen Fehler ein.
const fetchMock = vi.fn()
let inboxTotal: number | 'error' | 'pending' = 0

function inboxResponse(): Promise<Response> {
  if (inboxTotal === 'pending') return new Promise<Response>(() => undefined)
  if (inboxTotal === 'error') {
    return Promise.resolve(
      new Response(JSON.stringify({ detail: 'kaputt' }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      }),
    )
  }
  return Promise.resolve(
    new Response(
      JSON.stringify({
        follow_ups_due: 0,
        memory_approval: inboxTotal,
        versions_review: 0,
        system_prompts_review: 0,
        cases_open: 0,
        patterns: 3,
        total: inboxTotal,
      }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    ),
  )
}

beforeEach(() => {
  inboxTotal = 0
  fetchMock.mockReset()
  fetchMock.mockImplementation((url: string) =>
    String(url).includes('/inbox/counts')
      ? inboxResponse()
      : Promise.resolve(new Response('[]', { status: 200 })),
  )
  vi.stubGlobal('fetch', fetchMock)
})

const NAV_LABELS = [
  'Dashboard',
  'Agents',
  'System-Prompts',
  'Personas',
  'Playbooks',
  'Resources',
  'Externe Tools',
  'Arbeitsbereich',
  'Feedback',
  'Gedächtnis',
  'Einstellungen',
]

// Audit E2-B: Gruppen in fester Reihenfolge. `heading: null` = Gruppe ohne
// Ueberschrift (Einstieg oben, Settings unten).
const NAV_GROUPS_DE: { heading: string | null; links: string[] }[] = [
  { heading: null, links: ['Dashboard', 'Agents'] },
  {
    heading: 'Bausteine',
    links: ['System-Prompts', 'Personas', 'Playbooks', 'Resources', 'Externe Tools'],
  },
  { heading: 'Betrieb', links: ['Arbeitsbereich', 'Feedback', 'Gedächtnis'] },
  { heading: null, links: ['Einstellungen'] },
]

/**
 * Prueft die Screenreader-Struktur einer Nav-Flaeche: genau vier Listen in
 * fester Reihenfolge, je Liste die erwarteten Links in Reihenfolge, betitelte
 * Listen per h2 benannt (`aria-labelledby`), keine weiteren Ueberschriften.
 */
function expectGroupedNav(nav: HTMLElement, groups = NAV_GROUPS_DE) {
  const lists = within(nav).getAllByRole('list')
  expect(lists).toHaveLength(groups.length)
  groups.forEach((group, index) => {
    const list = lists[index]
    const links = within(list).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(group.links)
    // Jeder Link steckt in einem eigenen Listeneintrag.
    expect(within(list).getAllByRole('listitem')).toHaveLength(group.links.length)
    if (group.heading) {
      expect(list).toHaveAccessibleName(group.heading)
    } else {
      expect(list).not.toHaveAttribute('aria-labelledby')
    }
  })
  const headings = within(nav).getAllByRole('heading', { level: 2 })
  expect(headings.map((h) => h.textContent)).toEqual(
    groups.flatMap((g) => (g.heading ? [g.heading] : [])),
  )
  // Tastaturreihenfolge = DOM-Reihenfolge: kein Link verschiebt sich per
  // positivem tabIndex aus der Gruppenfolge.
  const allLinks = within(nav).getAllByRole('link')
  expect(allLinks.map((link) => link.textContent)).toEqual(groups.flatMap((g) => g.links))
  for (const link of allLinks) {
    expect(link.tabIndex).toBe(0)
  }
}

interface MatchMediaControls {
  setMatches: (query: string, matches: boolean) => void
}

/**
 * Query-bewusster `matchMedia`-Mock: haelt pro Query-String einen eigenen
 * Match- und Listener-Zustand, weil AppShell (`useIsMobile`, `(max-width:
 * 767px)`) und `ThemeProvider` (`(prefers-color-scheme: dark)`) beide
 * gleichzeitig `window.matchMedia` mit unterschiedlichen Queries aufrufen —
 * ein einzelner globaler Zustand (wie in useMediaQuery.test.tsx, das nur
 * eine Query pro Test kennt) wuerde die beiden Faelle vermischen.
 */
function installMatchMedia(): MatchMediaControls {
  const matchesByQuery = new Map<string, boolean>()
  const listenersByQuery = new Map<string, Array<(event: MediaQueryListEvent) => void>>()

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      get matches() {
        return matchesByQuery.get(query) ?? false
      },
      media: query,
      onchange: null,
      addEventListener: (_event: string, cb: (event: MediaQueryListEvent) => void) => {
        const listeners = listenersByQuery.get(query) ?? []
        listeners.push(cb)
        listenersByQuery.set(query, listeners)
      },
      removeEventListener: (_event: string, cb: (event: MediaQueryListEvent) => void) => {
        const listeners = listenersByQuery.get(query) ?? []
        listenersByQuery.set(
          query,
          listeners.filter((listener) => listener !== cb),
        )
      },
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })

  return {
    setMatches(query: string, matches: boolean) {
      matchesByQuery.set(query, matches)
      for (const listener of listenersByQuery.get(query) ?? []) {
        listener({ matches } as MediaQueryListEvent)
      }
    },
  }
}

function uninstallMatchMedia() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: undefined,
  })
}

afterEach(() => {
  uninstallMatchMedia()
  vi.unstubAllGlobals()
})

function openSheet() {
  fireEvent.click(screen.getByRole('button', { name: 'Menü öffnen' }))
  return screen.findByRole('dialog')
}

describe('AppShell', () => {
  describe('Sidebar (ab md)', () => {
    it('rendert die Sidebar mit WorkspaceSwitcher und allen zehn Nav-Zielen', () => {
      renderShell()
      const aside = screen.getByRole('complementary')
      expect(within(aside).getByRole('button', { name: 'Workspace wechseln' })).toBeInTheDocument()
      const nav = within(aside).getByRole('navigation', { name: 'Hauptnavigation' })
      for (const label of NAV_LABELS) {
        expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
      }
      expect(within(nav).getAllByRole('link')).toHaveLength(NAV_LABELS.length)
    })

    it('ist per CSS erst ab md sichtbar (hidden md:flex, nicht mehr sm:flex)', () => {
      renderShell()
      const aside = screen.getByRole('complementary')
      expect(aside).toHaveClass('hidden', 'md:flex')
      expect(aside).not.toHaveClass('sm:flex')
    })

    it('gruppiert die Ziele: Einstieg, Bausteine, Betrieb, Einstellungen (Audit E2-B)', () => {
      renderShell()
      const aside = screen.getByRole('complementary')
      expectGroupedNav(within(aside).getByRole('navigation', { name: 'Hauptnavigation' }))
    })

    it('setzt die Gruppenueberschriften als Eyebrow (design-language §3.3)', () => {
      renderShell()
      const aside = screen.getByRole('complementary')
      for (const heading of within(aside).getAllByRole('heading', { level: 2 })) {
        expect(heading).toHaveClass(
          'text-xs',
          'font-medium',
          'uppercase',
          'tracking-wide',
          'text-muted-foreground',
        )
      }
    })

    it('zeigt die Gruppenueberschriften auf Englisch, wenn die UI Englisch ist', async () => {
      await act(async () => {
        await i18n.changeLanguage('en')
      })
      renderShell()
      const nav = within(screen.getByRole('complementary')).getByRole('navigation', {
        name: 'Main navigation',
      })
      expectGroupedNav(nav, [
        { heading: null, links: ['Dashboard', 'Agents'] },
        {
          heading: 'Building blocks',
          links: ['System prompts', 'Personas', 'Playbooks', 'Resources', 'External tools'],
        },
        { heading: 'Operations', links: ['Work area', 'Feedback', 'Memory'] },
        { heading: null, links: ['Settings'] },
      ])
    })
  })

  describe('Sheet-Navigation (unterhalb md)', () => {
    it('rendert den Hamburger-Trigger mit aria-label, aria-expanded und md:hidden', () => {
      renderShell()
      const trigger = screen.getByRole('button', { name: 'Menü öffnen' })
      expect(trigger).toHaveAttribute('aria-label', 'Menü öffnen')
      expect(trigger).toHaveAttribute('aria-expanded', 'false')
      expect(trigger).toHaveClass('md:hidden')
    })

    it('oeffnet per Trigger-Klick das Sheet mit WorkspaceSwitcher und allen zehn Nav-Zielen', async () => {
      renderShell()
      const trigger = screen.getByRole('button', { name: 'Menü öffnen' })

      const dialog = await openSheet()

      expect(trigger).toHaveAttribute('aria-expanded', 'true')
      expect(within(dialog).getByRole('button', { name: 'Workspace wechseln' })).toBeInTheDocument()
      const nav = within(dialog).getByRole('navigation', { name: 'Hauptnavigation' })
      for (const label of NAV_LABELS) {
        expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
      }
      expect(within(nav).getAllByRole('link')).toHaveLength(NAV_LABELS.length)
    })

    it('zeigt im Sheet dieselbe Gruppierung wie die Sidebar, mit eigenen Ueberschrift-IDs', async () => {
      renderShell()
      const dialog = await openSheet()
      const sheetNav = within(dialog).getByRole('navigation', { name: 'Hauptnavigation' })
      expectGroupedNav(sheetNav)

      // Beide Flaechen stehen gleichzeitig im DOM — die aria-labelledby-IDs
      // duerfen deshalb nicht kollidieren, sonst benennt die Sidebar-
      // Ueberschrift die Sheet-Liste.
      const ids = Array.from(document.querySelectorAll('nav h2')).map((h) => h.id)
      expect(ids).toHaveLength(4)
      expect(new Set(ids).size).toBe(4)
    })

    it('schliesst das Sheet bei Klick auf ein Nav-Ziel und navigiert dorthin', async () => {
      renderShell()
      const dialog = await openSheet()

      fireEvent.click(within(dialog).getByRole('link', { name: 'Playbooks' }))

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
      expect(screen.getByTestId('location').textContent).toBe('/w/ws-1/playbooks')
    })

    it('schliesst per Escape', async () => {
      renderShell()
      const dialog = await openSheet()

      fireEvent.keyDown(dialog, { key: 'Escape' })

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('faengt den Fokus im Panel und gibt ihn beim Schliessen an den Hamburger-Trigger zurueck', async () => {
      renderShell()
      const trigger = screen.getByRole('button', { name: 'Menü öffnen' })
      const dialog = await openSheet()

      await waitFor(() => {
        expect(dialog.contains(document.activeElement)).toBe(true)
      })

      fireEvent.keyDown(dialog, { key: 'Escape' })

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
      expect(document.activeElement).toBe(trigger)
    })

    it('schliesst automatisch, wenn das Viewport waehrend offenem Sheet ueber die md-Schwelle waechst', async () => {
      const media = installMatchMedia()
      media.setMatches(MOBILE_QUERY, true)
      renderShell()

      await openSheet()

      act(() => {
        media.setMatches(MOBILE_QUERY, false)
      })

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })
  })

  it('rendert Sprache, Theme und Abmelden im Header unabhaengig vom Breakpoint', () => {
    const onSignOut = vi.fn()
    renderShell({ onSignOut })
    expect(screen.getByRole('button', { name: 'Sprache umstellen' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Theme umstellen' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Abmelden' }))
    expect(onSignOut).toHaveBeenCalledTimes(1)
  })

  describe('Glocke „Zu erledigen“ (Navigation W1, Spec §2.3)', () => {
    function bell() {
      return screen.getByTestId('inbox-bell')
    }

    it('ist ein Link auf /w/:ws/inbox in der Kopfleiste vor der Sprache, nicht in der Nav', async () => {
      inboxTotal = 7
      renderShell()
      const link = await screen.findByRole('link', { name: 'Zu erledigen: 7 offen' })
      expect(link).toHaveAttribute('href', '/w/ws-1/inbox')
      const header = screen.getByRole('banner')
      expect(header).toContainElement(link)
      // Vor Sprache/Theme/Abmelden (DOM-Reihenfolge = Tab-Reihenfolge).
      const language = within(header).getByRole('button', { name: 'Sprache umstellen' })
      expect(link.compareDocumentPosition(language) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      // Kein zusaetzlicher Nav-Eintrag (Spec §2.3 „Navigation“).
      for (const nav of screen.getAllByRole('navigation', { hidden: true })) {
        expect(within(nav).queryByRole('link', { name: /Zu erledigen/ })).toBeNull()
      }
    })

    it('zeigt den Zaehler aria-hidden; vorgelesen wird nur das aria-label', async () => {
      inboxTotal = 7
      renderShell()
      await waitFor(() => expect(screen.getByTestId('inbox-bell-count')).toHaveTextContent('7'))
      const count = screen.getByTestId('inbox-bell-count')
      expect(count).toHaveAttribute('aria-hidden', 'true')
      expect(count).toHaveClass('bg-brand', 'text-brand-foreground', 'tabular-nums')
      expect(bell()).toHaveAccessibleName('Zu erledigen: 7 offen')
    })

    it('zeigt bei 0 keinen Zaehler, die Glocke bleibt', async () => {
      inboxTotal = 0
      renderShell()
      await waitFor(() => expect(bell()).toHaveAccessibleName('Zu erledigen: nichts offen'))
      expect(screen.queryByTestId('inbox-bell-count')).toBeNull()
    })

    it('zeigt ab 100 „99+“, das aria-label nennt die echte Zahl', async () => {
      inboxTotal = 100
      renderShell()
      await waitFor(() => expect(screen.getByTestId('inbox-bell-count')).toHaveTextContent('99+'))
      expect(bell()).toHaveAccessibleName('Zu erledigen: 100 offen')
    })

    it('zeigt bei genau 99 die Zahl', async () => {
      inboxTotal = 99
      renderShell()
      await waitFor(() => expect(screen.getByTestId('inbox-bell-count')).toHaveTextContent(/^99$/))
    })

    it('behauptet beim Laden keine 0: kein Zaehler, Name ohne Zahl', () => {
      inboxTotal = 'pending'
      renderShell()
      expect(bell()).toHaveAccessibleName('Zu erledigen')
      expect(screen.queryByTestId('inbox-bell-count')).toBeNull()
    })

    it('bleibt bei einem Fehler ein Link, ohne Zaehler und ohne Fehlerbanner', async () => {
      inboxTotal = 'error'
      renderShell()
      await waitFor(() =>
        expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/inbox/counts'))).toBe(
          true,
        ),
      )
      expect(bell()).toHaveAttribute('href', '/w/ws-1/inbox')
      expect(bell()).toHaveAccessibleName('Zu erledigen')
      expect(screen.queryByTestId('inbox-bell-count')).toBeNull()
      expect(screen.queryByRole('alert')).toBeNull()
    })

    it('markiert sich auf /inbox als aktuelle Seite (aria-current, bg-accent)', async () => {
      renderShell({ initialPath: '/w/ws-1/inbox' })
      await waitFor(() => expect(bell()).toHaveAttribute('aria-current', 'page'))
      expect(bell()).toHaveClass('bg-accent')
    })

    it('ist auf anderen Seiten nicht aktuell', () => {
      renderShell()
      expect(bell()).not.toHaveAttribute('aria-current')
      expect(bell()).not.toHaveClass('bg-accent')
    })

    it('hat unter md eine Trefferflaeche von 44 px und steht nicht im Nav-Sheet', () => {
      renderShell()
      expect(bell()).toHaveClass('h-11', 'w-11', 'md:h-9', 'md:w-9')
      expect(bell()).not.toHaveClass('md:hidden')
      expect(bell()).not.toHaveClass('hidden')
    })

    it('navigiert per Klick auf die Seite „Zu erledigen“', async () => {
      renderShell()
      fireEvent.click(bell())
      await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/w/ws-1/inbox'))
    })

    it('zeigt das aria-label auf Englisch', async () => {
      await act(async () => {
        await i18n.changeLanguage('en')
      })
      inboxTotal = 1
      renderShell()
      await waitFor(() => expect(bell()).toHaveAccessibleName('To do: 1 open'))
    })
  })
})
