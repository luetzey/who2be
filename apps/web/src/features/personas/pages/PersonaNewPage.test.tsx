import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, ResourceBlock } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PersonaNewPage } from './PersonaNewPage'

// Profil-Insel mocken — PersonaEditorForm beinhaltet den PersonaProfileEditor,
// der BlockNote (ThemeProvider-Abhaengigkeit) benoetigt (Track F).
vi.mock('@/features/personas/components/PersonaProfileEditor', () => ({
  PersonaProfileEditor: ({ initialBlocks }: { initialBlocks: ResourceBlock[] }) => (
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

// Alle useApi-Aufrufe auf der New-Page mocken. `listPersonaTags` liefert []
// (kein echtes Netz). `createPersona` delegiert an den globalen fetch-Stub.
const createPersonaMock = vi.fn()
vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    listPersonaTags: vi.fn().mockResolvedValue([]),
    createPersona: createPersonaMock,
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
  createPersonaMock.mockReset()
})

describe('PersonaNewPage', () => {
  it('legt eine Persona an und leitet auf die Detailseite weiter', async () => {
    const created = {
      id: 'p42',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'QA-Bot',
      current_version: 1,
      content: {
        description: '',
        system_prompt: '',
        traits: [],
        tags: [],
        content: { description: '', blocks: [] },
      },
      created_at: '2026-05-24T11:00:00Z',
      updated_at: '2026-05-24T11:00:00Z',
    }
    createPersonaMock.mockResolvedValueOnce(created)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/personas/new']}>
            <Routes>
              <Route path="/w/:workspaceId/personas/new" element={<PersonaNewPage />} />
              <Route
                path="/w/:workspaceId/personas/:id"
                element={<div>Detail von {created.id}</div>}
              />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    // `name` ist das einzige Pflichtfeld fuer Create (Welle 4).
    const nameInput = screen.getByLabelText('Name')
    fireEvent.change(nameInput, { target: { value: 'QA-Bot' } })
    // Submit via button-click; falls jsdom die Bubble-Chain nicht
    // durchreicht, feuern wir zusaetzlich das submit-Event direkt.
    const submitButton = screen.getByRole('button', { name: 'Anlegen' })
    fireEvent.click(submitButton)
    // Fallback: form direkt submitten
    const form = submitButton.closest('form')
    if (form !== null) {
      fireEvent.submit(form)
    }

    await waitFor(
      () => {
        expect(screen.getByText('Detail von p42')).toBeInTheDocument()
      },
      { timeout: 3000 },
    )

    // POST-Call: createPersona mit korrektem Body aufgerufen (Track C5: modes
    // immer mitgeschickt; PR-A: skills ebenfalls Default []).
    expect(createPersonaMock).toHaveBeenCalledWith({
      name: 'QA-Bot',
      content: {
        description: '',
        system_prompt: '',
        traits: [],
        tags: [],
        content: { description: '', blocks: [] },
        modes: [],
        skills: [],
      },
    })
  })
})
