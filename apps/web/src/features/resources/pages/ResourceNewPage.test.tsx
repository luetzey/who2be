import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, ResourceBlock } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { ResourceNewPage } from './ResourceNewPage'

// BlockNote-Insel mocken — ResourceEditorForm beinhaltet ResourceEditor, der
// BlockNoteEditor (ThemeProvider-Abhaengigkeit) benoetigt.
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

// `createResource` delegiert via gemocktem useApi — kein echtes Netz.
const createResourceMock = vi.fn()
// Track E3: `listResourceTags` wird vom TagInput-Feld beim Mount aufgerufen.
const listResourceTagsMock = vi.fn().mockResolvedValue([])
vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    createResource: createResourceMock,
    listResourceTags: listResourceTagsMock,
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
  createResourceMock.mockReset()
})

describe('ResourceNewPage', () => {
  it('legt eine Resource an und leitet auf die Detailseite weiter', async () => {
    const created = {
      id: 'res7',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'FAQ',
      current_version: 1,
      content: { description: '', blocks: [] },
      created_at: '2026-05-31T10:00:00Z',
      updated_at: '2026-05-31T10:00:00Z',
    }
    createResourceMock.mockResolvedValueOnce(created)

    render(
      <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/resources/new']}>
            <Routes>
              <Route path="/w/:workspaceId/resources/new" element={<ResourceNewPage />} />
              <Route
                path="/w/:workspaceId/resources/:id"
                element={<div>Detail von {created.id}</div>}
              />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // `name` ist das einzige Pflichtfeld fuer Create (Welle 4).
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'FAQ' } })
    const submitButton = screen.getByRole('button', { name: 'Anlegen' })
    fireEvent.click(submitButton)
    // Fallback: form direkt submitten (jsdom bubbled-submit-Fix).
    const form = submitButton.closest('form')
    if (form !== null) {
      fireEvent.submit(form)
    }

    await waitFor(() => {
      expect(screen.getByText('Detail von res7')).toBeInTheDocument()
    })

    // `createResource` mit korrektem Body aufgerufen (Track E3: tags immer mitgeschickt).
    expect(createResourceMock).toHaveBeenCalledWith({
      name: 'FAQ',
      content: { description: '', blocks: [], tags: [] },
      // Ein Element, eine Sprache (ADR-0045): Default aus der (in `me` nicht
      // aufloesbaren) Workspace-Content-Sprache faellt auf 'de' zurueck.
      locale: 'de',
    })
  })
})
