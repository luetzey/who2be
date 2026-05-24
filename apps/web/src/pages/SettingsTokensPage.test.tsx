import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthTokenProvider } from '../auth/AuthTokenProvider'
import { SessionContext } from '../auth/session-context'
import { SettingsTokensPage } from './SettingsTokensPage'

const session = { access_token: 'jwt' } as unknown as Session

function renderPage() {
  return render(
    <SessionContext.Provider value={{ session, signIn: vi.fn(), signOut: vi.fn() }}>
      <AuthTokenProvider>
        <BrowserRouter>
          <SettingsTokensPage />
        </BrowserRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SettingsTokensPage', () => {
  it('listet die vom Backend gelieferten Tokens', async () => {
    const existing = [
      {
        id: 't1',
        name: 'CLI-Agent',
        created_at: '2026-05-24T10:00:00Z',
        last_used_at: null,
        revoked_at: null,
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(existing), { status: 200 })),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('CLI-Agent')).toBeInTheDocument()
    })
  })

  it('legt einen neuen Token an und zeigt den Klartext genau einmal', async () => {
    const created = {
      id: 't2',
      name: 'Brainstormer',
      created_at: '2026-05-24T10:05:00Z',
      last_used_at: null,
      revoked_at: null,
      token: 'w2b_secret-plaintext',
    }
    const fetchMock = vi
      .fn()
      // initial list
      .mockResolvedValueOnce(new Response('[]', { status: 200 }))
      // POST /v1/tokens
      .mockResolvedValueOnce(new Response(JSON.stringify(created), { status: 201 }))
      // reload after create
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([{ ...created, token: undefined }]),
          { status: 200 },
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Neuen Token anlegen' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Brainstormer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Anlegen' }))

    await waitFor(() => {
      expect(screen.getByLabelText('Klartext-Token')).toHaveValue('w2b_secret-plaintext')
    })

    const postCall = fetchMock.mock.calls[1]
    expect(postCall[0]).toContain('/v1/tokens')
    const init = postCall[1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ name: 'Brainstormer' })
  })
})
