import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { ThemeProvider } from '@/app/ThemeProvider'
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

function renderShell() {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <ThemeProvider>
        <MemoryRouter initialEntries={['/w/ws-1/dashboard']}>
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
    </SessionContext.Provider>,
  )
}

describe('AppShell (a11y)', () => {
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
})
