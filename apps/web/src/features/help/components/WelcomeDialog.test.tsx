import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Tutorial, TutorialStep } from '@/api/client'
import type { Me } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { connectStepDone, WELCOME_CONFIRM_AFTER_MS, WELCOME_POLL_INTERVAL_MS } from '../welcome'
import { DashboardWelcome } from './WelcomeDialog'

// Schluessel des Cookie-Hinweises (features/legal); als Literal, weil der
// Feature-Schnitt den tiefen Import verbietet.
const CONSENT_STORAGE_KEY = 'who2be:cookie-consent'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

function step(id: string, type: TutorialStep['type'], state: TutorialStep['state'] = 'open'): TutorialStep {
  return { id, type, page: null, automatic: type !== 'manual', state, completed_at: null }
}

function welcomeTutorial(overrides: Partial<Tutorial> = {}, connected = false): Tutorial {
  return {
    id: 'erste-schritte',
    audience: 'everyone',
    welcome: true,
    welcome_seen_at: null,
    restarted_at: null,
    completed: false,
    steps: [step('head', 'head_start', 'done'), step('connect', 'first_mcp_call', connected ? 'done' : 'open')],
    ...overrides,
  }
}

const builder = {
  id: 'agent-builder',
  name: 'Builder',
  is_managed: true,
  status: 'enabled',
  activatable: true,
}

function me(kind: 'personal' | 'company', role: 'admin' | 'editor' = 'admin'): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Ich',
        slug: 'ich',
        kind,
        workspaces: [{ id: 'ws-1', name: 'Privat', slug: 'privat', role }],
      },
    ],
  }
}

interface Call {
  url: string
  method: string
  body: unknown
}

/** GET-Tutorials liefert `lists` der Reihe nach (letzte bleibt stehen). */
function stubApi(lists: Tutorial[][]) {
  const calls: Call[] = []
  let gets = 0
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : null })
      const json = (payload: unknown) => Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }))
      if (url.includes('/agents')) return json([builder])
      if (url.includes('/v1/me/tutorials') && method === 'GET') {
        const answer = lists[Math.min(gets, lists.length - 1)]
        gets += 1
        return json(answer)
      }
      if (url.includes('/v1/me/tutorials') && method === 'PATCH') {
        return json({ ...lists[0][0], welcome_seen_at: '2026-10-22T12:00:00Z' })
      }
      return Promise.resolve(new Response('{}', { status: 500 }))
    }),
  )
  return calls
}

function acknowledgeCookies() {
  window.localStorage.setItem(CONSENT_STORAGE_KEY, 'acknowledged')
}

function renderWelcome(options: { kind?: 'personal' | 'company'; state?: unknown } = {}) {
  return renderInRoutes(<DashboardWelcome />, {
    path: '/w/:workspaceId/dashboard',
    initialEntries: [{ pathname: '/w/ws-1/dashboard', state: options.state }],
    me: me(options.kind ?? 'personal'),
  })
}

const patches = (calls: Call[]) => calls.filter((c) => c.method === 'PATCH')

describe('connectStepDone', () => {
  it('ist nur wahr, wenn der Verbinden-Schritt erledigt ist', () => {
    expect(connectStepDone(undefined)).toBe(false)
    expect(connectStepDone(welcomeTutorial())).toBe(false)
    expect(connectStepDone(welcomeTutorial({}, true))).toBe(true)
  })
})

describe('DashboardWelcome', () => {
  it('geht im eigenen persoenlichen Workspace einmal auf, setzt welcome_seen genau einmal und besteht axe', async () => {
    acknowledgeCookies()
    const calls = stubApi([[welcomeTutorial()]])
    const { baseElement } = renderWelcome()

    const dialog = await screen.findByRole('dialog', { name: 'Willkommen bei Who2Be' })
    expect(await within(dialog).findByRole('link', { name: /Mit Claude verbinden/ })).toBeInTheDocument()
    await waitFor(() => expect(patches(calls)).toHaveLength(1))
    expect(patches(calls)[0].body).toEqual({ welcome_seen: true })
    expect(await axe(baseElement)).toHaveNoViolations()
  })

  it('bleibt zu, wenn welcome_seen_at schon gesetzt ist', async () => {
    acknowledgeCookies()
    const calls = stubApi([[welcomeTutorial({ welcome_seen_at: '2026-10-21T10:00:00Z' })]])
    renderWelcome()
    await waitFor(() => expect(calls.some((c) => c.url.includes('/v1/me/tutorials'))).toBe(true))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(patches(calls)).toHaveLength(0)
  })

  it('bleibt in einem Team-Workspace zu (nur Startliste)', async () => {
    acknowledgeCookies()
    const calls = stubApi([[welcomeTutorial()]])
    renderWelcome({ kind: 'company' })
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(calls.filter((c) => c.url.includes('/v1/me/tutorials'))).toHaveLength(0)
  })

  it('wartet auf den Cookie-Hinweis und geht nach dessen Bestaetigung auf', async () => {
    stubApi([[welcomeTutorial()]])
    renderWelcome()
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    act(() => {
      window.localStorage.setItem(CONSENT_STORAGE_KEY, 'acknowledged')
      window.dispatchEvent(new Event('who2be:cookie-consent-acknowledged'))
    })
    expect(await screen.findByRole('dialog', { name: 'Willkommen bei Who2Be' })).toBeInTheDocument()
  })

  it('oeffnet nach „Einführung erneut starten“ trotz welcome_seen_at, auch im Team-Workspace', async () => {
    acknowledgeCookies()
    const calls = stubApi([[welcomeTutorial({ welcome_seen_at: '2026-10-21T10:00:00Z' })]])
    renderWelcome({ kind: 'company', state: { replayWelcome: true } })
    expect(await screen.findByRole('dialog', { name: 'Willkommen bei Who2Be' })).toBeInTheDocument()
    expect(patches(calls)).toHaveLength(0)
  })

  it('Überspringen schliesst den Dialog', async () => {
    acknowledgeCookies()
    stubApi([[welcomeTutorial()]])
    renderWelcome()
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Überspringen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('Escape schliesst wie Überspringen; der Fokus startet auf der Überschrift', async () => {
    acknowledgeCookies()
    stubApi([[welcomeTutorial()]])
    renderWelcome()
    const heading = await screen.findByRole('heading', { name: 'Willkommen bei Who2Be' })
    await waitFor(() => expect(heading).toHaveFocus())
    fireEvent.keyDown(heading, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('stoppt das Nachfragen beim Schliessen und beim Unmount', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    acknowledgeCookies()
    const calls = stubApi([[welcomeTutorial()]])
    const tutorialGets = () => calls.filter((c) => c.method === 'GET' && c.url.includes('/v1/me/tutorials')).length

    // 1) Schliessen waehrend des Wartens.
    const first = renderWelcome()
    let dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Etwas anderes' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Ich habe die Adresse eingetragen' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(WELCOME_POLL_INTERVAL_MS)
    })
    const whileOpen = tutorialGets()
    fireEvent.click(screen.getByRole('button', { name: 'Später' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(WELCOME_POLL_INTERVAL_MS * 4)
    })
    expect(tutorialGets()).toBe(whileOpen)
    first.unmount()

    // 2) Unmount waehrend des Wartens (Seitenwechsel).
    const second = renderWelcome()
    dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Etwas anderes' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Ich habe die Adresse eingetragen' }))
    second.unmount()
    const atUnmount = tutorialGets()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(WELCOME_POLL_INTERVAL_MS * 4)
    })
    expect(tutorialGets()).toBe(atUnmount)
  })

  it('Verbinden: wartet, zeigt nach dem ersten Abruf den Erfolg und kündigt ihn an', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    acknowledgeCookies()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    stubApi([[welcomeTutorial()], [welcomeTutorial()], [welcomeTutorial({}, true)]])
    renderWelcome()
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Claude Code' }))
    expect(await screen.findByRole('dialog', { name: /Verbinde „Builder“ mit Claude Code/ })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Befehl kopieren' }))
    expect(await screen.findByTestId('welcome-waiting')).toBeInTheDocument()
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('/a/agent-builder'))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(WELCOME_POLL_INTERVAL_MS * 2)
    })
    expect(await screen.findByRole('dialog', { name: 'Verbunden!' })).toBeInTheDocument()
    expect(screen.getByTestId('welcome-live')).toHaveTextContent('Verbunden!')
  })

  it('zeigt nach zwei Minuten „Ja, weiter“', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    acknowledgeCookies()
    stubApi([[welcomeTutorial()]])
    renderWelcome()
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Etwas anderes' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Ich habe die Adresse eingetragen' }))
    expect(screen.queryByRole('button', { name: 'Ja, weiter' })).not.toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(WELCOME_CONFIRM_AFTER_MS)
    })
    expect(await screen.findByRole('button', { name: 'Ja, weiter' })).toBeInTheDocument()
  })
})
