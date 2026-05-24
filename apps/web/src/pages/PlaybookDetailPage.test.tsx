import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthTokenProvider } from '../auth/AuthTokenProvider'
import { SessionContext } from '../auth/session-context'
import { PlaybookDetailPage } from './PlaybookDetailPage'

const session = { access_token: 'jwt' } as unknown as Session

interface PlaybookShape {
  id: string
  owner_id: string
  name: string
  current_version: number
  type: string
  tags: string[]
  triggers: string | null
  content: {
    description: string
    body: string
    type: string
    tags: string[]
    triggers: string | null
  }
  created_at: string
  updated_at: string
}

function playbook(version: number, body: string): PlaybookShape {
  return {
    id: 'pb1',
    owner_id: 'o1',
    name: 'Coach',
    current_version: version,
    type: 'workflow',
    tags: ['coaching'],
    triggers: null,
    content: {
      description: 'd',
      body,
      type: 'workflow',
      tags: ['coaching'],
      triggers: null,
    },
    created_at: '2026-05-24T12:00:00Z',
    updated_at: '2026-05-24T12:00:00Z',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlaybookDetailPage', () => {
  it('zeigt eine neue Version, nachdem der Editor gespeichert wurde', async () => {
    const v1 = {
      version: 1,
      content: playbook(1, 'b1').content,
      created_by: 'o1',
      created_at: 't1',
    }
    const v2 = {
      version: 2,
      content: playbook(2, 'b2').content,
      created_by: 'o1',
      created_at: 't2',
    }

    const handlers: Record<string, () => Response> = {
      'GET /v1/playbooks/pb1': () => jsonResponse(playbook(1, 'b1')),
      'GET /v1/playbooks/pb1/versions': () => jsonResponse([v1]),
    }

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const url = String(input)
      if (method === 'PUT' && url.endsWith('/v1/playbooks/pb1')) {
        handlers['GET /v1/playbooks/pb1'] = () => jsonResponse(playbook(2, 'b2'))
        handlers['GET /v1/playbooks/pb1/versions'] = () => jsonResponse([v1, v2])
        return jsonResponse(playbook(2, 'b2'))
      }
      const key = `${method} ${new URL(url).pathname}`
      const handler = handlers[key]
      if (!handler) {
        throw new Error(`Unmocked ${key}`)
      }
      return handler()
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider value={{ session, signIn: vi.fn(), signOut: vi.fn() }}>
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/playbooks/pb1']}>
            <Routes>
              <Route path="/playbooks/:id" element={<PlaybookDetailPage />} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('Aktuelle Version: 1')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Inhalt'), { target: { value: 'b2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern (neue Version)' }))

    await waitFor(() => {
      expect(screen.getByText('Aktuelle Version: 2')).toBeInTheDocument()
    })
    expect(screen.getByText(/v2 —/)).toBeInTheDocument()
  })
})
