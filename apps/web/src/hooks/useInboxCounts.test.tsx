import { act, renderHook, waitFor } from '@testing-library/react'
import type { Session } from '@supabase/supabase-js'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createApi } from '@/api/client'
import type { InboxCounts } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { INBOX_MUTATION_DEBOUNCE_MS, useInboxCounts } from './useInboxCounts'

const session = { access_token: 'jwt' } as unknown as Session

// Navigation W1 (Spec §2.3, Weiche N5 a): ein Zaehl-Request beim Laden, bei
// Workspace-Wechsel, bei Tab-Rueckkehr und nach eigenen Schreibanfragen —
// kein Polling. Gemockt wird `fetch`, damit der echte API-Client (inkl. der
// Schreib-Meldung) mitlaeuft.

function counts(total: number, extra: Partial<InboxCounts> = {}): InboxCounts {
  return {
    follow_ups_due: 0,
    memory_approval: total,
    versions_review: 0,
    system_prompts_review: 0,
    cases_open: 0,
    patterns: 0,
    total,
    ...extra,
  }
}

const fetchMock = vi.fn()

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function inboxCalls(): string[] {
  return fetchMock.mock.calls
    .map(([url]) => String(url).replace(/^https?:\/\/[^/]+/, ''))
    .filter((url) => url.includes('/inbox/counts'))
}

function wrapperFor(path: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <SessionContext.Provider
        value={{
          session,
          me: null,
          sessionLoaded: true,
          signIn: vi.fn(),
          signOut: vi.fn(),
          refreshMe: vi.fn(),
        }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path="/w/:workspaceId/*" element={children} />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>
    )
  }
}

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  document.dispatchEvent(new Event('visibilitychange'))
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => 'visible',
  })
})

describe('useInboxCounts', () => {
  it('laedt die Zaehler einmal beim Mount und liefert sie', async () => {
    fetchMock.mockImplementation(async () => json(counts(7)))
    const { result } = renderHook(() => useInboxCounts(), { wrapper: wrapperFor('/w/ws-1/x') })

    expect(result.current.counts).toBeNull()
    await waitFor(() => expect(result.current.counts?.total).toBe(7))
    expect(inboxCalls()).toEqual(['/v1/workspaces/ws-1/inbox/counts'])
    expect(result.current.failed).toBe(false)
  })

  it('reicht agent_id als Query durch', async () => {
    fetchMock.mockImplementation(async () => json(counts(2)))
    const { result } = renderHook(() => useInboxCounts('agent-9'), {
      wrapper: wrapperFor('/w/ws-1/x'),
    })
    await waitFor(() => expect(result.current.counts?.total).toBe(2))
    expect(inboxCalls()).toEqual(['/v1/workspaces/ws-1/inbox/counts?agent_id=agent-9'])
  })

  it('liefert bei einem Fehler null statt einer behaupteten 0', async () => {
    fetchMock.mockImplementation(async () => json({ detail: 'kaputt' }, 500))
    const { result } = renderHook(() => useInboxCounts(), { wrapper: wrapperFor('/w/ws-1/x') })
    await waitFor(() => expect(result.current.failed).toBe(true))
    expect(result.current.counts).toBeNull()
  })

  it('zaehlt bei Rueckkehr in den Tab neu, nicht beim Verlassen', async () => {
    fetchMock.mockResolvedValueOnce(json(counts(1))).mockResolvedValueOnce(json(counts(4)))
    const { result } = renderHook(() => useInboxCounts(), { wrapper: wrapperFor('/w/ws-1/x') })
    await waitFor(() => expect(result.current.counts?.total).toBe(1))

    act(() => setVisibility('hidden'))
    expect(inboxCalls()).toHaveLength(1)

    act(() => setVisibility('visible'))
    await waitFor(() => expect(result.current.counts?.total).toBe(4))
    expect(inboxCalls()).toHaveLength(2)
  })

  it('zaehlt nach eigenen Schreibanfragen entprellt einmal neu, nach Lesen nicht', async () => {
    fetchMock.mockImplementation(async (url: string) =>
      String(url).includes('/inbox/counts') ? json(counts(inboxCalls().length)) : json({}),
    )
    const { result } = renderHook(() => useInboxCounts(), { wrapper: wrapperFor('/w/ws-1/x') })
    await waitFor(() => expect(result.current.counts).not.toBeNull())
    expect(inboxCalls()).toHaveLength(1)

    const api = createApi('jwt', 'ws-1')
    // Lesen loest nichts aus.
    await act(async () => {
      await api.listCases()
    })
    // Zwei Schreibanfragen kurz hintereinander: eine Zaehlung.
    await act(async () => {
      await api.transitionCase('c1', { to: 'triaged' } as never)
      await api.deleteCase('c2')
    })
    await waitFor(() => expect(inboxCalls()).toHaveLength(2), {
      timeout: INBOX_MUTATION_DEBOUNCE_MS * 10,
    })
    await new Promise((resolve) => setTimeout(resolve, INBOX_MUTATION_DEBOUNCE_MS * 2))
    expect(inboxCalls()).toHaveLength(2)
  })

  it('zaehlt nach einer gescheiterten Schreibanfrage nicht neu', async () => {
    fetchMock.mockImplementation(async (url: string) =>
      String(url).includes('/inbox/counts') ? json(counts(3)) : json({ detail: 'nein' }, 409),
    )
    const { result } = renderHook(() => useInboxCounts(), { wrapper: wrapperFor('/w/ws-1/x') })
    await waitFor(() => expect(result.current.counts).not.toBeNull())

    const api = createApi('jwt', 'ws-1')
    await act(async () => {
      await api.deleteCase('c2').catch(() => undefined)
    })
    await new Promise((resolve) => setTimeout(resolve, INBOX_MUTATION_DEBOUNCE_MS * 2))
    expect(inboxCalls()).toHaveLength(1)
  })

  it('pollt nicht', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetchMock.mockImplementation(async () => json(counts(1)))
    const { result } = renderHook(() => useInboxCounts(), { wrapper: wrapperFor('/w/ws-1/x') })
    await waitFor(() => expect(result.current.counts?.total).toBe(1))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10 * 60_000)
    })
    expect(inboxCalls()).toHaveLength(1)
  })

  it('verwirft eine spaete Antwort fuer den vorigen Agenten', async () => {
    let resolveFirst: (r: Response) => void = () => undefined
    fetchMock
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveFirst = resolve
          }),
      )
      .mockResolvedValueOnce(json(counts(5)))
    const { result, rerender } = renderHook(({ agent }) => useInboxCounts(agent), {
      wrapper: wrapperFor('/w/ws-1/x'),
      initialProps: { agent: 'a1' as string | undefined },
    })
    rerender({ agent: 'a2' })
    await waitFor(() => expect(result.current.counts?.total).toBe(5))
    // Die spaete Antwort der ersten Anfrage ueberschreibt nichts.
    await act(async () => {
      resolveFirst(json(counts(99)))
      await Promise.resolve()
    })
    expect(result.current.counts?.total).toBe(5)
  })

  it('meldet sich beim Abbau ab', async () => {
    fetchMock.mockImplementation(async () => json(counts(1)))
    const { result, unmount } = renderHook(() => useInboxCounts(), {
      wrapper: wrapperFor('/w/ws-1/x'),
    })
    await waitFor(() => expect(result.current.counts).not.toBeNull())
    unmount()
    act(() => setVisibility('visible'))
    const api = createApi('jwt', 'ws-1')
    await api.deleteCase('c1')
    await new Promise((resolve) => setTimeout(resolve, INBOX_MUTATION_DEBOUNCE_MS * 2))
    expect(inboxCalls()).toHaveLength(1)
  })
})
