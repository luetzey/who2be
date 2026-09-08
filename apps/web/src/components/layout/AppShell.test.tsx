import type { Session } from '@supabase/supabase-js'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { ThemeProvider } from '@/app/ThemeProvider'
import { SessionContext } from '@/auth/session-context'

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
    </SessionContext.Provider>,
  )
}

const NAV_LABELS = [
  'Dashboard',
  'Agents',
  'System-Prompts',
  'Personae',
  'Playbooks',
  'Resources',
  'Externe Tools',
  'Arbeitsbereich',
  'Feedback',
  'Einstellungen',
]

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
})
