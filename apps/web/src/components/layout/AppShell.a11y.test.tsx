import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { ThemeProvider } from '@/app/ThemeProvider'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { axe } from '@/test/a11y'

import { AppShell } from './AppShell'

// Radix DropdownMenu (Theme-/Language-Switcher, WorkspaceSwitcher) — gleicher
// Stub wie in AppShell.test.tsx / WorkspaceSwitcher.test.tsx.
beforeAll(() => {
  Object.defineProperty(window.HTMLElement.prototype, 'hasPointerCapture', {
    value: () => false,
    configurable: true,
  })
  Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
    value: () => undefined,
    configurable: true,
  })
})

const session = { access_token: 'jwt' } as unknown as Session

const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'org-1',
      name: 'Persoenlich',
      slug: 'personal',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'Mein Workspace', slug: 'mein', role: 'admin' }],
    },
  ],
}

function renderShell(path = '/w/ws-1/dashboard') {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <ThemeProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route
                path="/w/:workspaceId/*"
                element={
                  <AppShell onSignOut={vi.fn()}>
                    <span>Seiteninhalt</span>
                  </AppShell>
                }
              />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

// Glocke (Navigation W1): `GET /inbox/counts` liefert 7 offene Aufgaben.
beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      String(url).includes('/inbox/counts')
        ? new Response(
            JSON.stringify({
              follow_ups_due: 1,
              memory_approval: 2,
              versions_review: 0,
              system_prompts_review: 0,
              cases_open: 4,
              patterns: 0,
              total: 7,
            }),
            { status: 200, headers: { 'content-type': 'application/json' } },
          )
        : new Response('[]', { status: 200 }),
    ),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AppShell (a11y)', () => {
  it('hat keine axe-Violations mit Glocke samt Zaehler in der Kopfleiste', async () => {
    renderShell()
    const header = screen.getByRole('banner')
    await waitFor(() => expect(within(header).getByTestId('inbox-bell-count')).toBeInTheDocument())

    expect(await axe(header)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit aktiver Glocke auf /inbox', async () => {
    renderShell('/w/ws-1/inbox')
    const header = screen.getByRole('banner')
    await waitFor(() =>
      expect(within(header).getByTestId('inbox-bell')).toHaveAttribute('aria-current', 'page'),
    )

    expect(await axe(header)).toHaveNoViolations()
  })

  it('hat keine axe-Violations im Ruhezustand (Sheet geschlossen, Sidebar-Markup)', async () => {
    const { container } = renderShell()

    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations im geoeffneten Sheet', async () => {
    renderShell()
    fireEvent.click(screen.getByRole('button', { name: 'Menü öffnen' }))
    const dialog = await screen.findByRole('dialog')

    // Bewusst nur der Dialog-Teilbaum, nicht `document.body`: die `<aside>`
    // bleibt (wie im echten Browser via `hidden md:flex`) im DOM stehen,
    // waehrend jsdom kein CSS anwendet — ein Scan von `document.body` saehe
    // deshalb testweise zwei "Hauptnavigation"-Landmarks gleichzeitig
    // (landmark-unique-Fehlalarm), obwohl im echten Browser durch
    // `display:none` nur eine davon je Breite in der A11y-Tree steht.
    expect(await axe(dialog)).toHaveNoViolations()
  })

  it('haelt die Gruppen-Semantik axe-sauber: Listen nur mit li-Kindern, benannte Listen, h2-Ueberschriften', async () => {
    renderShell()
    const nav = screen.getByTestId('app-nav-sidebar')
    // Voraussetzung, damit der Scan etwas prueft: die Gruppenstruktur steht.
    expect(within(nav).getAllByRole('list')).toHaveLength(4)
    expect(within(nav).getAllByRole('heading', { level: 2 })).toHaveLength(2)

    expect(
      await axe(nav, {
        rules: {
          list: { enabled: true },
          listitem: { enabled: true },
          'aria-valid-attr-value': { enabled: true },
          'empty-heading': { enabled: true },
        },
      }),
    ).toHaveNoViolations()
  })
})
