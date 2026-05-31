import type { Session } from '@supabase/supabase-js'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { AgentNewPage } from './AgentNewPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

function renderPage() {
  return render(
    <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents/new']}>
          <Routes>
            <Route path="/w/:workspaceId/agents/new" element={<AgentNewPage />} />
            <Route path="/w/:workspaceId/personas/new" element={<div>Persona anlegen</div>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AgentNewPage', () => {
  it('rendert EmptyState bei leerer Persona-Liste', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (String(url).includes('/personas')) {
          return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
        }
        if (String(url).includes('/system-prompts')) {
          return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
        }
        return Promise.resolve(new Response('{}', { status: 200 }))
      }),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Keine Persona vorhanden.')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Du brauchst zuerst eine Persona, um einen Agent anzulegen.'),
    ).toBeInTheDocument()

    const cta = screen.getByRole('link', { name: 'Persona anlegen' })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute('href', '/w/ws-1/personas/new')
  })

  it('rendert Ladeindikator während Personas geladen werden', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        () => new Promise(() => undefined), // never resolves
      ),
    )

    renderPage()

    // LoadingState rendert aria-busy="true" als Ladeanzeige.
    expect(screen.getByRole('generic', { hidden: true, busy: true })).toBeInTheDocument()
  })

  it('rendert Fehlermeldung wenn Laden fehlschlägt', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('Network error')),
    )

    renderPage()

    // Die API wraps alle Netzwerkfehler als "Who2Be-API nicht erreichbar."
    await waitFor(() => {
      expect(screen.getByText(/API nicht erreichbar/i)).toBeInTheDocument()
    })
  })
})
