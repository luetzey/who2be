import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ExternalTool, Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { ToolsPage } from './ToolsPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

function tool(overrides: Partial<ExternalTool> = {}): ExternalTool {
  return {
    id: 't1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Todoist',
    alias: 'todo',
    current_version: 1,
    current_status: 'active',
    has_pending_draft: false,
    content: {
      display_name: 'Todoist App',
      mcp_server_name: 'Todoist MCP',
      tool_names: ['add_task'],
      usage_notes: '[]',
      fallback_note: null,
      tags: ['produktivitaet'],
    },
    created_at: '2026-07-18T11:00:00Z',
    updated_at: '2026-07-18T11:00:00Z',
    ...overrides,
  }
}

function renderPage() {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/tools']}>
          <Routes>
            <Route path="/w/:workspaceId/tools" element={<ToolsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ToolsPage', () => {
  it('listet externe Tools mit Alias-/Versions-Badge und zeigt die Filterleiste', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([tool()]), { status: 200 })),
    )

    renderPage()

    expect(await screen.findByText('Todoist')).toBeInTheDocument()
    expect(screen.getByText('todo')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    // Filterleiste erscheint nur bei nicht-leerer Liste.
    expect(screen.getByLabelText('Suche')).toBeInTheDocument()
  })

  it('zeigt den Empty-State ohne Filterleiste, wenn keine Tools existieren', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })),
    )

    renderPage()

    expect(await screen.findByText('Noch keine externen Tools')).toBeInTheDocument()
    expect(screen.queryByLabelText('Suche')).not.toBeInTheDocument()
    // CTA sowohl im Header als auch im Empty-State.
    expect(screen.getAllByRole('link', { name: /Neues Tool/ }).length).toBeGreaterThanOrEqual(2)
  })

  it('zeigt einen ErrorAlert, wenn die Liste nicht geladen werden kann', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('kaputt', { status: 500 })))

    renderPage()

    expect(await screen.findByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
    expect(screen.queryByText('Todoist')).not.toBeInTheDocument()
  })

  it('zeigt den Filter-Empty-State bei erfolgloser Suche und setzt via Reset zurueck', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([tool()]), { status: 200 })),
    )

    renderPage()

    expect(await screen.findByText('Todoist')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'gibt-es-nicht' } })
    expect(await screen.findByText('Keine Treffer')).toBeInTheDocument()
    expect(screen.queryByText('Todoist')).not.toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: 'Filter zurücksetzen' })[0])
    expect(await screen.findByText('Todoist')).toBeInTheDocument()
  })

  it('filtert per Tag-Select und zeigt die Tool-Namen-Anzahl in der Meta-Zeile', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            tool(),
            tool({
              id: 't2',
              name: 'Things 3',
              alias: 'todo2',
              content: {
                display_name: 'Things 3 App',
                mcp_server_name: 'Things MCP',
                tool_names: [],
                usage_notes: '[]',
                fallback_note: null,
                tags: [],
              },
            }),
          ]),
          { status: 200 },
        ),
      ),
    )

    renderPage()

    expect(await screen.findByText('Todoist')).toBeInTheDocument()
    expect(screen.getByText('1 Tool-Name')).toBeInTheDocument()
    expect(screen.getByText('Keine Tool-Namen hinterlegt')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Tag'), { target: { value: 'produktivitaet' } })
    expect(await screen.findByText('Todoist')).toBeInTheDocument()
    expect(screen.queryByText('Things 3')).not.toBeInTheDocument()
  })
})
