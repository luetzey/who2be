import { render, screen } from '@testing-library/react'
import type { Session } from '@supabase/supabase-js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { SessionContext } from '@/auth/session-context'

import { WorkAreaNav } from './WorkAreaNav'

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
      <MemoryRouter initialEntries={['/w/ws-1/workarea']}>
        <Routes>
          <Route path="/w/:workspaceId/workarea/*" element={<WorkAreaNav />} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

// Responsive-Vertrag #572 (AK 3): die Nav-Eintraege halten unterhalb `md`
// 40 px Hit-Target. Die Zahl kommt aus AK 3 dieses Issues, nicht aus der Norm:
// design-language.md §11 ist die einzige Quelle des Floors und setzt ihn auf
// >= 32 px — die gemessenen 36 px waren danach zulaessig, 40 px ist dort die
// Praeferenz `size="default"`, die dieses Paket unterhalb `md` verbindlich
// macht. Gemessen liegen die Eintraege mit `px-3 py-2` bei `text-sm` auf
// 36 px — `min-h-10` hebt sie unterhalb `md` auf 40 px, ab `md` faellt die
// Polsterung auf die Desktop-Dichte zurueck.
//
// Die Klassenfolge ist woertlich die aus `SettingsNav` (#568, PR #604): beide
// Komponenten sind klassengleich, und das Schwesterpaket hat zuerst gemessen.
// Eine zweite Variante desselben Musters waere Pattern Drift.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1100_572-w3-workarea-responsive-audit.md gerendert
// belegt (36 px -> 40 px bei 320 px Viewport).
describe('WorkAreaNav — Responsive (#572)', () => {
  it('haelt den 40-px-Hit-Target aus AK 3 unterhalb md und gibt ihn ab md wieder frei', () => {
    renderNav()

    const entries = screen.getAllByRole('link')
    expect(entries).toHaveLength(3)
    for (const entry of entries) {
      expect(entry).toHaveClass('min-h-10')
      expect(entry).toHaveClass('md:min-h-0')
    }
  })
})
