import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PlaybookNewPage } from './PlaybookNewPage'

const session = { access_token: 'jwt' } as unknown as Session

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlaybookNewPage', () => {
  it('legt ein Playbook an und leitet auf die Detailseite weiter', async () => {
    const created = {
      id: 'pb7',
      owner_id: 'o1',
      name: 'Brainstorming',
      current_version: 1,
      type: 'workflow',
      tags: ['ideation'],
      triggers: 'ich brauche Ideen',
      content: {
        description: 'd',
        body: 'b',
        type: 'workflow',
        tags: ['ideation'],
        triggers: 'ich brauche Ideen',
      },
      created_at: '2026-05-24T12:00:00Z',
      updated_at: '2026-05-24T12:00:00Z',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, signIn: vi.fn(), signOut: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/playbooks/new']}>
            <Routes>
              <Route path="/playbooks/new" element={<PlaybookNewPage />} />
              <Route path="/playbooks/:id" element={<div>Detail von {created.id}</div>} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Brainstorming' } })
    fireEvent.change(screen.getByLabelText('Beschreibung'), { target: { value: 'd' } })
    fireEvent.change(screen.getByLabelText('Inhalt'), { target: { value: 'b' } })
    fireEvent.change(screen.getByLabelText('Tags (kommagetrennt)'), {
      target: { value: 'ideation' },
    })
    fireEvent.change(screen.getByLabelText('Trigger'), {
      target: { value: 'ich brauche Ideen' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Anlegen' }))

    await waitFor(() => {
      expect(screen.getByText('Detail von pb7')).toBeInTheDocument()
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/v1/playbooks')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      name: 'Brainstorming',
      content: {
        description: 'd',
        body: 'b',
        type: 'workflow',
        tags: ['ideation'],
        triggers: 'ich brauche Ideen',
      },
    })
  })
})
