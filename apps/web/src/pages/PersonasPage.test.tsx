import type { Session } from '@supabase/supabase-js'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SessionContext } from '../auth/session-context'
import { PersonasPage } from './PersonasPage'

const fakeSession = { access_token: 'tok' } as unknown as Session

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PersonasPage', () => {
  it('listet die von der API gelieferten Personae', async () => {
    const persona = {
      id: 'p1',
      owner_id: 'o1',
      name: 'QA-Bot',
      current_version: 1,
      content: { description: 'd', system_prompt: 's', traits: [] },
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([persona]), { status: 200 }),
      ),
    )

    render(
      <SessionContext.Provider
        value={{ session: fakeSession, signIn: vi.fn(), signOut: vi.fn() }}
      >
        <BrowserRouter>
          <PersonasPage />
        </BrowserRouter>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('QA-Bot')).toBeInTheDocument()
    })
  })
})
