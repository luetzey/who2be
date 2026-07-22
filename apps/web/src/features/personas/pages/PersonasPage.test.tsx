
import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PersonasPage } from './PersonasPage'

const fakeSession = { access_token: 'tok' } as unknown as Session
const fakeMe: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PersonasPage', () => {
  it('listet die von der API gelieferten Personae', async () => {
    const persona = {
      id: 'p1',
      workspace_id: 'ws-1',
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
        value={{ session: fakeSession, me: fakeMe, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <BrowserRouter>
            <PersonasPage />
          </BrowserRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('QA-Bot')).toBeInTheDocument()
    })
  })

  it('reicht die Agent-Facette (?agent=) serverseitig durch und zeigt den Chip', async () => {
    const persona = {
      id: 'p1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'QA-Bot',
      current_version: 1,
      content: { description: 'd', system_prompt: 's', traits: [] },
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
    }
    const agent = {
      id: 'a1',
      workspace_id: 'ws-1',
      name: 'Support-Bot',
      description: null,
      persona_id: 'p1',
      system_prompt_template_id: null,
      status: 'enabled',
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
    }
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      const body = url.includes('/agents') ? [agent] : [persona]
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider
        value={{ session: fakeSession, me: fakeMe, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/?agent=a1']}>
            <PersonasPage />
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText('QA-Bot')).toBeInTheDocument()
    })

    // Der Listen-Fetch traegt den serverseitigen Filter-Param.
    const personaCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/personas'))
    expect(personaCalls.some((url) => url.includes('/personas?agent=a1'))).toBe(true)

    // Aktiver Filter als entfernbarer Chip mit Agent-Name; Entfernen loest
    // einen Refetch ohne den Param aus.
    const chip = screen.getByRole('button', { name: /Agent-Filter entfernen \(Support-Bot\)/ })
    expect(chip).toHaveTextContent('Agent: Support-Bot')
    fireEvent.click(chip)
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((url) => url.endsWith('/personas'))).toBe(true)
    })
  })
})
