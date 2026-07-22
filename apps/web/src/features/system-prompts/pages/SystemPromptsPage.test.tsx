import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, SystemPromptTemplate } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { SystemPromptsPage } from './SystemPromptsPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

function template(overrides: Partial<SystemPromptTemplate> = {}): SystemPromptTemplate {
  return {
    id: 'sp1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Support-Template',
    slug: 'support-template',
    current_version: 2,
    current_status: 'active',
    has_pending_draft: false,
    content: { description: 'd', body: '[]' },
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  }
}

function renderPage() {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/system-prompts']}>
          <Routes>
            <Route path="/w/:workspaceId/system-prompts" element={<SystemPromptsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SystemPromptsPage', () => {
  it('listet Templates mit Slug-/Versions-Badge und zeigt die Filterleiste', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify([template()]), { status: 200 }),
        ),
    )

    renderPage()

    expect(await screen.findByText('Support-Template')).toBeInTheDocument()
    expect(screen.getByText('support-template')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
    // Filterleiste erscheint nur bei nicht-leerer Liste.
    expect(screen.getByLabelText('Suche')).toBeInTheDocument()
  })

  it('zeigt den Empty-State ohne Filterleiste, wenn keine Templates existieren', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })),
    )

    renderPage()

    expect(await screen.findByText('Noch keine Templates')).toBeInTheDocument()
    expect(
      screen.getByText('Lege dein erstes System-Prompt-Template an.'),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Suche')).not.toBeInTheDocument()
    // CTA sowohl im Header als auch im Empty-State.
    expect(
      screen.getAllByRole('link', { name: /Neues Template/ }).length,
    ).toBeGreaterThanOrEqual(2)
  })

  it('zeigt einen ErrorAlert, wenn die Liste nicht geladen werden kann', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('kaputt', { status: 500 })),
    )

    renderPage()

    expect(await screen.findByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
    expect(screen.queryByText('Support-Template')).not.toBeInTheDocument()
  })

  it('zeigt den Filter-Empty-State bei erfolgloser Suche und setzt via Reset zurueck', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify([template()]), { status: 200 }),
        ),
    )

    renderPage()

    expect(await screen.findByText('Support-Template')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Suche'), {
      target: { value: 'gibt-es-nicht' },
    })
    expect(await screen.findByText('Keine Treffer')).toBeInTheDocument()
    expect(screen.queryByText('Support-Template')).not.toBeInTheDocument()

    // Reset-Button im Filter-Empty-State stellt die Liste wieder her.
    fireEvent.click(screen.getAllByRole('button', { name: 'Filter zurücksetzen' })[0])
    expect(await screen.findByText('Support-Template')).toBeInTheDocument()
  })
})
