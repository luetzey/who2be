
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
  it('listet die von der API gelieferten Personas', async () => {
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

  it('zeigt die Element-Sprache als Badge (ADR-0045)', async () => {
    const persona = {
      id: 'p1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'QA-Bot',
      current_version: 1,
      content: { description: 'd', system_prompt: 's', traits: [] },
      locale: 'en',
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([persona]), { status: 200 })),
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
    expect(screen.getByText('EN')).toBeInTheDocument()
  })

  it('reicht die Sprach-Facette (?locale=) serverseitig durch und zeigt den Chip', async () => {
    const persona = {
      id: 'p1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'QA-Bot',
      current_version: 1,
      content: { description: 'd', system_prompt: 's', traits: [] },
      locale: 'en',
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([persona]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider
        value={{ session: fakeSession, me: fakeMe, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/?locale=en']}>
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
    expect(personaCalls.some((url) => url.includes('/personas?locale=en'))).toBe(true)

    // Aktiver Filter als entfernbarer Chip; Entfernen loest einen Refetch
    // ohne den Param aus.
    const chip = screen.getByRole('button', { name: /Sprachfilter entfernen \(English\)/ })
    expect(chip).toHaveTextContent('Sprache: English')
    fireEvent.click(chip)
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((url) => url.endsWith('/personas'))).toBe(true)
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

// Audit A13-Rest (Folge zu #777): drei Tags und „+n“ unter `md`, Knopf im
// Fluss (W3=a); jsdom ohne Layout — geprueft wird die TagList-Verdrahtung.
describe('PersonasPage — Tags „+n“ in der Listen-Karte (A13)', () => {
  it('zeigt drei Tags und „+2“, Klick klappt in der Karte auf', async () => {
    const persona = {
      id: 'p1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'QA-Bot',
      current_version: 1,
      content: {
        description: 'd',
        system_prompt: 's',
        traits: [],
        tags: ['t1', 't2', 't3', 't4', 't5'],
      },
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([persona]), { status: 200 })),
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

    const more = await screen.findByRole('button', { name: '2 weitere anzeigen' })
    const rest = screen.getByTestId('tag-list-rest')
    expect(more).toHaveTextContent('+2')
    expect(rest).toHaveClass('hidden', 'md:contents')
    expect(rest).toHaveTextContent('t4t5')

    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(rest).not.toHaveClass('hidden')
    expect(screen.getByText('QA-Bot')).toBeInTheDocument()
  })
})
