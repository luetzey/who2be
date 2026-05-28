import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PersonaNewPage } from './PersonaNewPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PersonaNewPage', () => {
  it('legt eine Persona an und leitet auf die Detailseite weiter', async () => {
    const created = {
      id: 'p42',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'QA-Bot',
      current_version: 1,
      content: { description: 'd', system_prompt: 's', traits: ['careful'] },
      created_at: '2026-05-24T11:00:00Z',
      updated_at: '2026-05-24T11:00:00Z',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn() }}>
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

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'QA-Bot' } })
    fireEvent.change(screen.getByLabelText('Beschreibung'), { target: { value: 'd' } })
    fireEvent.change(screen.getByLabelText('System-Prompt'), { target: { value: 's' } })
    fireEvent.change(screen.getByLabelText('Eigenschaften (kommagetrennt)'), {
      target: { value: 'careful' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Anlegen' }))

    await waitFor(() => {
      expect(screen.getByText('Detail von p42')).toBeInTheDocument()
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/v1/workspaces/ws-1/personas')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      name: 'QA-Bot',
      content: { description: 'd', system_prompt: 's', traits: ['careful'] },
    })
  })
})
