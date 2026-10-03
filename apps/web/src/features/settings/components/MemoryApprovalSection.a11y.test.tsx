import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { axe } from '@/test/a11y'

import { MemoryApprovalSection } from './MemoryApprovalSection'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', () => ({
  useIsMobile: () => viewport.mobile,
  useMediaQuery: () => viewport.mobile,
}))

beforeAll(() => {
  for (const method of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ]) {
    Object.defineProperty(window.HTMLElement.prototype, method, {
      value: () => undefined,
      configurable: true,
    })
  }
})

const session = { access_token: 'jwt' } as unknown as Session

const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'org-1',
      name: 'Acme',
      slug: 'acme',
      kind: 'company',
      workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role: 'admin' }],
    },
  ],
}

function stub(guardMode: 'standard' | 'off' = 'standard', enabled = false) {
  const cell = { row: 'user_fact', origin: 'user_stated' }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/memory-auto-policy')) {
        return new Response(
          JSON.stringify({ enabled_cells: enabled ? [cell] : [], switchable_cells: [cell] }),
          { status: 200 },
        )
      }
      if (url.includes('/memory-guard')) {
        return new Response(
          JSON.stringify({ mode: guardMode, allow_phrases: [], block_phrases: [] }),
          { status: 200 },
        )
      }
      return new Response('[]', { status: 200 })
    }),
  )
}

function renderSection() {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me,
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn().mockResolvedValue(undefined),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/settings/workspace']}>
          <Routes>
            <Route path="/w/:workspaceId/settings/workspace" element={<MemoryApprovalSection />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  viewport.mobile = false
})

describe('MemoryApprovalSection (a11y)', () => {
  it('hat keine axe-Violations als Matrix (Desktop), auch mit Wächter-Banner', async () => {
    stub('off', true)
    const { container } = renderSection()
    await screen.findByRole('switch')
    await screen.findByText('Der Memory-Wächter ist aus.')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations als Liste je Art (unter md)', async () => {
    viewport.mobile = true
    stub()
    const { container } = renderSection()
    await screen.findByRole('switch')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations im offenen Warnlisten-Dialog', async () => {
    stub()
    renderSection()
    fireEvent.click(await screen.findByRole('switch'))
    const dialog = await screen.findByRole('dialog')
    expect(await axe(dialog)).toHaveNoViolations()
  })

  it('benennt den Schalter aus Zeilen- und Spaltenkopf', async () => {
    stub()
    renderSection()
    expect(await screen.findByRole('switch', { name: 'Nutzerfakt Von dir gesagt' })).toBeInTheDocument()
  })
})
