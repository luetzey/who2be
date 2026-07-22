import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { SessionContext } from '@/auth/session-context'

import { WorkspaceSwitcher } from './WorkspaceSwitcher'

// Radix DropdownMenu nutzt PointerCapture- und scrollIntoView-APIs, die jsdom
// nicht implementiert. Stub-Polyfill, damit Trigger + Items aktivierbar sind.
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
      {
        id: 'org-2',
        name: 'Acme GmbH',
        slug: 'acme',
        kind: 'company',
        workspaces: [
          { id: 'ws-2', name: 'Marketing', slug: 'marketing', role: 'editor' },
          { id: 'ws-3', name: 'Engineering', slug: 'eng', role: 'viewer' },
        ],
      },
    ],
  }
}

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

function renderSwitcher(me: Me | null = buildMe(), initialPath = '/w/ws-1/dashboard') {
  return render(
    <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route
            path="/w/:workspaceId/*"
            element={
              <>
                <WorkspaceSwitcher />
                <LocationProbe />
              </>
            }
          />
          <Route
            path="*"
            element={
              <>
                <WorkspaceSwitcher />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  window.localStorage.clear()
})

function openMenu() {
  const trigger = screen.getByRole('button', { name: 'Workspace wechseln' })
  // Radix oeffnet auf pointerdown+up; in jsdom triggern wir per Enter, das die
  // Trigger-Kompo identisch behandelt.
  fireEvent.keyDown(trigger, { key: 'Enter' })
}

describe('WorkspaceSwitcher', () => {
  it('rendert den aktiven Workspace im Trigger', () => {
    renderSwitcher()
    const trigger = screen.getByRole('button', { name: 'Workspace wechseln' })
    expect(trigger).toHaveTextContent('Mein Workspace')
    expect(trigger).toHaveTextContent('Persoenlich')
  })

  it('zeigt nach Klick alle Organizations und Workspaces als Gruppen', () => {
    renderSwitcher()
    openMenu()
    // Org-Labels (DropdownMenuLabel sind keine semantischen Headings -> Text-Match).
    expect(screen.getAllByText('Persoenlich').length).toBeGreaterThan(0)
    expect(screen.getByText('Acme GmbH')).toBeInTheDocument()
    // Workspaces als MenuItems
    expect(screen.getByRole('menuitem', { name: /Mein Workspace/ })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /Marketing/ })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /Engineering/ })).toBeInTheDocument()
    expect(
      screen.getByRole('menuitem', { name: /Workspace anlegen/ }),
    ).toBeInTheDocument()
  })

  it('navigiert beim Auswahl-Click auf einen anderen Workspace', () => {
    renderSwitcher()
    openMenu()
    fireEvent.click(screen.getByRole('menuitem', { name: /Marketing/ }))
    expect(screen.getByTestId('location').textContent).toBe('/w/ws-2/dashboard')
    expect(window.localStorage.getItem('lastWorkspaceId')).toBe('ws-2')
  })

  it('rendert nichts, wenn me === null', () => {
    renderSwitcher(null)
    expect(
      screen.queryByRole('button', { name: 'Workspace wechseln' }),
    ).toBeNull()
  })
})
