import type { Session } from '@supabase/supabase-js'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { SessionContext } from '@/auth/session-context'

import { SettingsNav } from './SettingsNav'

const session = { access_token: 'jwt' } as unknown as Session

const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'o1',
      name: 'Org',
      slug: 'org',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'admin' }],
    },
  ],
}

function renderNav() {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me,
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <MemoryRouter initialEntries={['/w/ws-1/settings/account']}>
        <Routes>
          <Route path="/w/:workspaceId/settings/*" element={<SettingsNav />} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

// Responsive-Vertrag #568 (AK 2): die Nav-Eintraege halten unterhalb `md` den
// 40-px-Hit-Target aus design-language.md §11. Gemessen liegen sie mit
// `px-3 py-2` bei `text-sm` auf 36 px — `min-h-10` hebt sie unterhalb `md` auf
// 40 px, ab `md` faellt die Polsterung auf die Desktop-Dichte zurueck.
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-0830_568-w3-settings-responsive-audit.md gerendert
// belegt (36 px -> 40 px bei 320 px Viewport).
describe('SettingsNav — Responsive (#568)', () => {
  it('haelt den 40-px-Hit-Target unterhalb md und gibt ihn ab md wieder frei', () => {
    renderNav()

    const link = screen.getByRole('link', { name: 'Konto' })
    const classes = link.className.split(/\s+/)

    expect(classes).toContain('min-h-10')
    expect(classes).toContain('md:min-h-0')
  })

  it('setzt den Hit-Target-Vertrag auf jedem Eintrag, nicht nur auf dem ersten', () => {
    renderNav()

    for (const name of ['Konto', 'Organisation', 'Workspace', 'Mitglieder']) {
      const classes = screen.getByRole('link', { name }).className.split(/\s+/)
      expect(classes).toContain('min-h-10')
    }
  })

  it('laesst die Tab-Leiste umbrechen, statt sie zu scrollen', () => {
    renderNav()

    const nav = screen.getByRole('navigation')
    expect(nav.className.split(/\s+/)).toContain('flex-wrap')
  })
})
