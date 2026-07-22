import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, ResourceBlock } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { ToolNewPage } from './ToolNewPage'

// BlockNote-Insel mocken — ToolEditorForm bindet ResourceEditor ein, der
// BlockNoteEditor (ThemeProvider-Abhaengigkeit) benoetigt (Muster
// ResourceNewPage.test.tsx).
vi.mock('@/components/editor/BlockNoteEditor', () => ({
  BlockNoteEditor: ({ initialBlocks }: { initialBlocks: ResourceBlock[] }) => (
    <div
      data-testid="blocknote-view"
      data-initial-blocks={JSON.stringify(initialBlocks)}
    />
  ),
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'admin',
}))

const createExternalToolMock = vi.fn()
vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    createExternalTool: createExternalToolMock,
  }),
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

afterEach(() => {
  vi.unstubAllGlobals()
  createExternalToolMock.mockReset()
})

describe('ToolNewPage', () => {
  it('legt ein externes Tool an und leitet auf die Detailseite weiter', async () => {
    const created = {
      id: 'tool7',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Todoist',
      alias: 'todoist',
      current_version: 1,
      content: {
        display_name: '',
        mcp_server_name: '',
        tool_names: [],
        usage_notes: '[]',
        fallback_note: null,
        tags: [],
      },
      created_at: '2026-07-18T10:00:00Z',
      updated_at: '2026-07-18T10:00:00Z',
    }
    createExternalToolMock.mockResolvedValueOnce(created)

    render(
      <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/tools/new']}>
            <Routes>
              <Route path="/w/:workspaceId/tools/new" element={<ToolNewPage />} />
              <Route
                path="/w/:workspaceId/tools/:id"
                element={<div>Detail von {created.id}</div>}
              />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // `name` ist das einzige Pflichtfeld fuer Create.
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Todoist' } })
    const submitButton = screen.getByRole('button', { name: 'Anlegen' })
    fireEvent.click(submitButton)
    const form = submitButton.closest('form')
    if (form !== null) {
      fireEvent.submit(form)
    }

    await waitFor(() => {
      expect(screen.getByText('Detail von tool7')).toBeInTheDocument()
    })

    expect(createExternalToolMock).toHaveBeenCalledWith({
      name: 'Todoist',
      content: {
        display_name: '',
        mcp_server_name: '',
        tool_names: [],
        usage_notes: '[]',
        fallback_note: null,
        tags: [],
      },
      locales: ['de'],
    })
  })

  it('meldet einen Fehler, wenn das Anlegen fehlschlaegt', async () => {
    // `mockRejectedValue` (nicht `Once`): der Click-Handler UND der
    // Submit-Fallback (Zeile unten, jsdom-bubbled-submit-Fix) koennen beide
    // feuern — beide Aufrufe sollen konsistent fehlschlagen, damit die
    // Assertion nicht vom Timing einer Doppel-Submission abhaengt.
    createExternalToolMock.mockRejectedValue(new Error('Anlegen kaputt'))

    render(
      <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/tools/new']}>
            <Routes>
              <Route path="/w/:workspaceId/tools/new" element={<ToolNewPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Todoist' } })
    const submitButton = screen.getByRole('button', { name: 'Anlegen' })
    fireEvent.click(submitButton)
    const form = submitButton.closest('form')
    if (form !== null) {
      fireEvent.submit(form)
    }

    expect(await screen.findByText('Anlegen kaputt')).toBeInTheDocument()
  })
})
