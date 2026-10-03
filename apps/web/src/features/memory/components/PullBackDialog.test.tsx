import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryRead, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { MemoryPage } from '@/features/memory/pages/MemoryPage'
import { notify } from '@/lib/feedback'
import { axe } from '@/test/a11y'

// Not-Aus (C5c-2, Gedaechtnisverwaltung §8/§13.6/§15/§16): erst zaehlen
// (`dry_run`), dann nur mit `expected_count`; bei 409 neu bestaetigen statt
// still wiederholen; editor ohne fremden Umfang; viewer ohne Not-Aus;
// fremdes Nutzergedaechtnis nie als Inhalt.

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

beforeAll(() => {
  for (const method of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ]) {
    Object.defineProperty(window.HTMLElement.prototype, method, {
      value: () => undefined,
      configurable: true,
    })
  }
})

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Acme',
        slug: 'acme',
        kind: 'company',
        workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role }],
      },
    ],
  }
}

function memory(overrides: Partial<MemoryRead> = {}): MemoryRead {
  return {
    id: 'm1',
    agent_id: 'a1',
    status: 'active',
    fact: 'Nutzt uv statt pip.',
    context: null,
    category: 'preference',
    importance: 6,
    source: 'agent',
    triage_note: null,
    retrieval_count: 0,
    last_retrieved_at: null,
    created_at: '2026-10-01T09:12:00Z',
    updated_at: '2026-10-01T09:12:00Z',
    kind: 'agent_note',
    scope: 'agent',
    subject_user_id: null,
    origin: 'user_stated',
    created_by_agent_id: 'a1',
    confirmed_at: null,
    expires_at: null,
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

interface Call {
  method: string
  path: string
  body: Record<string, unknown> | null
}

interface StubOptions {
  // Vorschau-Antworten der Reihe nach; die letzte gilt fuer alle weiteren.
  previews?: { count: number; hidden_count?: number; sample?: MemoryRead[] }[]
  // Antwort der Ausfuehrung: Zahl (Erfolg) oder 409 mit neuer Zahl.
  revoke?: { count: number } | { mismatch: number }
  // Hält die erste Vorschau zurück, bis der Test sie freigibt.
  hold?: Promise<void>
}

function stubApi({ previews = [{ count: 2, sample: [memory()] }], revoke, hold }: StubOptions = {}) {
  const calls: Call[] = []
  let previewIndex = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const parsed = new URL(String(input), 'http://x')
      const path = parsed.pathname
      const method = init?.method ?? 'GET'
      const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : null
      calls.push({ method, path, body })
      if (path.endsWith('/memories/revoke-auto')) {
        if (body?.dry_run === true) {
          if (previewIndex === 0 && hold !== undefined) await hold
          const preview = previews[Math.min(previewIndex, previews.length - 1)]
          previewIndex += 1
          return jsonResponse({
            count: preview.count,
            hidden_count: preview.hidden_count ?? 0,
            sample: preview.sample ?? [],
          })
        }
        const result = revoke ?? { count: Number(body?.expected_count) }
        if ('mismatch' in result) {
          return jsonResponse(
            {
              detail: 'Es gibt andere Zahlen.',
              reason: 'memory_batch_count_mismatch',
              params: { count: result.mismatch },
            },
            409,
          )
        }
        return jsonResponse({ count: result.count, hidden_count: 0, results: [] })
      }
      if (path.endsWith('/memories/counts')) return jsonResponse({ total: 0 })
      if (path.endsWith('/memories')) return jsonResponse({ items: [], next_cursor: null })
      if (path.endsWith('/agents')) {
        return jsonResponse([
          { id: 'a1', name: 'researcher', tool_policy: {} },
          { id: 'a2', name: 'coder', tool_policy: {} },
        ])
      }
      return jsonResponse([])
    }),
  )
  return { calls }
}

const revokeCalls = (calls: Call[]) =>
  calls.filter((call) => call.path.endsWith('/memories/revoke-auto'))
const previewCalls = (calls: Call[]) => revokeCalls(calls).filter((c) => c.body?.dry_run === true)
const executeCalls = (calls: Call[]) => revokeCalls(calls).filter((c) => c.body?.dry_run === false)

function Search() {
  const { search } = useLocation()
  return <output data-testid="location-search">{search}</output>
}

function renderPage(entry = '/w/ws-1/memory?tab=approval', role: WorkspaceRole = 'editor') {
  return render(
    <Providers role={role}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route
            path="/w/:workspaceId/memory"
            element={
              <>
                <MemoryPage />
                <Search />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </Providers>,
  )
}

function Providers({ role, children }: { role: WorkspaceRole; children: ReactNode }) {
  return (
    <SessionContext.Provider
      value={{
        session,
        me: buildMe(role),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn().mockResolvedValue(undefined),
      }}
    >
      <AuthTokenProvider>{children}</AuthTokenProvider>
    </SessionContext.Provider>
  )
}

async function openFromMenu() {
  const trigger = await screen.findByRole('button', { name: 'Weitere Aktionen' })
  fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false })
  fireEvent.click(
    await screen.findByRole('menuitem', { name: 'Automatisch Freigegebenes zurücknehmen…' }),
  )
  return screen.findByRole('dialog', { name: 'Automatisch Freigegebenes zurücknehmen' })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('PullBackDialog (C5c-2, Spec §8)', () => {
  it('zählt zuerst per dry_run und führt erst nach Klick mit expected_count und demselben since aus', async () => {
    let release: () => void = () => undefined
    const hold = new Promise<void>((resolve) => {
      release = resolve
    })
    const { calls } = stubApi({ previews: [{ count: 2, sample: [memory()] }], hold })
    renderPage()
    const dialog = await openFromMenu()

    const submit = within(dialog).getByTestId('pullback-submit')
    // Bis zur Zählung deaktiviert, der Grund steht im aria-describedby.
    expect(await within(dialog).findByText('Wird gezählt…')).toBeInTheDocument()
    expect(submit).toBeDisabled()
    expect(submit).toHaveAccessibleDescription('Erst nach dem Zählen möglich.')
    release()

    expect(await within(dialog).findByText('Betrifft 2 Einträge.')).toBeInTheDocument()
    expect(executeCalls(calls)).toHaveLength(0)
    const [preview] = previewCalls(calls)
    expect(preview.body).toMatchObject({ dry_run: true, include_other_users: false })
    expect(preview.body).not.toHaveProperty('expected_count')
    expect(Date.now() - Date.parse(String(preview.body?.since))).toBeGreaterThan(23 * 3600_000)

    expect(within(dialog).getByTestId('pullback-sample')).toHaveTextContent(
      '„Nutzt uv statt pip.“ · researcher',
    )
    expect(submit).toBeEnabled()
    expect(submit).toHaveTextContent('2 zurücknehmen')
    fireEvent.click(submit)

    await waitFor(() => expect(executeCalls(calls)).toHaveLength(1))
    expect(executeCalls(calls)[0].body).toEqual({
      since: preview.body?.since,
      include_other_users: false,
      expected_count: 2,
      dry_run: false,
    })
    await waitFor(() =>
      expect(notify.success).toHaveBeenCalledWith(
        '2 Einträge zurückgenommen. Sie warten jetzt in „Zur Freigabe“.',
      ),
    )
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByTestId('location-search')).not.toHaveTextContent('pullback')
  })

  it('bei 409 bleibt der Dialog offen, nennt die neue Zahl und wiederholt nicht still', async () => {
    const { calls } = stubApi({
      previews: [{ count: 2, sample: [memory()] }, { count: 3, sample: [memory()] }],
      revoke: { mismatch: 3 },
    })
    renderPage()
    const dialog = await openFromMenu()
    await within(dialog).findByText('Betrifft 2 Einträge.')
    fireEvent.click(within(dialog).getByTestId('pullback-submit'))

    expect(await within(dialog).findByTestId('pullback-count-changed')).toHaveTextContent(
      'Inzwischen sind es 3. Erneut bestätigen?',
    )
    expect(within(dialog).getByText('Betrifft 3 Einträge.')).toBeInTheDocument()
    expect(within(dialog).getByTestId('pullback-submit')).toHaveTextContent('3 zurücknehmen')
    // Genau eine Ausführung — keine stille Wiederholung mit der neuen Zahl.
    expect(executeCalls(calls)).toHaveLength(1)
    expect(executeCalls(calls)[0].body?.expected_count).toBe(2)
    expect(notify.success).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    // Erst der neue Klick sendet die neue Zahl.
    fireEvent.click(within(dialog).getByTestId('pullback-submit'))
    await waitFor(() => expect(executeCalls(calls)).toHaveLength(2))
    expect(executeCalls(calls)[1].body?.expected_count).toBe(3)
  })

  it('editor: kein fremder Umfang, der Satz dazu steht da', async () => {
    const { calls } = stubApi()
    renderPage()
    const dialog = await openFromMenu()
    await within(dialog).findByText('Betrifft 2 Einträge.')
    expect(within(dialog).getByTestId('pullback-editor-note')).toHaveTextContent(
      'Das Nutzergedächtnis anderer Mitglieder kann nur ein Admin zurücknehmen.',
    )
    expect(within(dialog).getByLabelText('Alle Agenten und dein Nutzergedächtnis')).toBeChecked()
    expect(within(dialog).queryByText('Alle Agenten und das Nutzergedächtnis')).toBeNull()
    expect(revokeCalls(calls).every((c) => c.body?.include_other_users === false)).toBe(true)
  })

  it('admin: fremdes Nutzergedächtnis nur als Anzahl, nie als Inhalt', async () => {
    const foreign = memory({
      id: 'm9',
      fact: 'Fremder Nutzerfakt',
      scope: 'user',
      kind: 'user_fact',
      agent_id: null,
      subject_user_id: 'u2',
    })
    const own = memory({
      id: 'm2',
      fact: 'Antwortet gern kurz.',
      scope: 'user',
      kind: 'user_fact',
      agent_id: null,
      subject_user_id: 'u1',
    })
    const { calls } = stubApi({
      previews: [{ count: 8, hidden_count: 6, sample: [memory(), own, foreign] }],
    })
    renderPage('/w/ws-1/memory?tab=approval', 'admin')
    const dialog = await openFromMenu()
    await within(dialog).findByText('Betrifft 8 Einträge.')
    expect(previewCalls(calls)[0].body?.include_other_users).toBe(true)
    expect(within(dialog).getByTestId('pullback-hidden')).toHaveTextContent(
      'und 6 Einträge im Nutzergedächtnis anderer Mitglieder',
    )
    expect(within(dialog).queryByText(/Fremder Nutzerfakt/)).toBeNull()
    expect(within(dialog).getAllByTestId('pullback-sample')).toHaveLength(2)
    expect(within(dialog).queryByTestId('pullback-editor-note')).toBeNull()
    expect(within(dialog).getByLabelText('Alle Agenten und das Nutzergedächtnis')).toBeChecked()
  })

  it('viewer: kein Overflow und ?pullback=1 öffnet nichts und fragt nichts an', async () => {
    const { calls } = stubApi()
    renderPage('/w/ws-1/memory?tab=approval&pullback=1', 'viewer')
    await screen.findByRole('heading', { name: 'Gedächtnis', level: 1 })
    await waitFor(() => expect(calls.some((c) => c.path.endsWith('/memories'))).toBe(true))
    expect(screen.queryByRole('button', { name: 'Weitere Aktionen' })).toBeNull()
    expect(screen.queryByTestId('pullback-dialog')).toBeNull()
    expect(revokeCalls(calls)).toHaveLength(0)
  })

  it('öffnet über ?pullback=1 (Link aus S4) und zählt neu, wenn der Umfang wechselt', async () => {
    const { calls } = stubApi({ previews: [{ count: 2 }, { count: 1 }] })
    renderPage('/w/ws-1/memory?tab=approval&pullback=1')
    const dialog = await screen.findByRole('dialog', {
      name: 'Automatisch Freigegebenes zurücknehmen',
    })
    await within(dialog).findByText('Betrifft 2 Einträge.')
    fireEvent.click(within(dialog).getByLabelText('Nur ein Agent'))
    fireEvent.change(within(dialog).getByTestId('pullback-agent'), { target: { value: 'a2' } })
    expect(await within(dialog).findByText('Betrifft 1 Eintrag.')).toBeInTheDocument()
    expect(previewCalls(calls).at(-1)?.body).toMatchObject({ agent_id: 'a2', dry_run: true })
  })

  it('„Seit“ sendet den Tagesbeginn und lässt kein Datum vor 90 Tagen zu', async () => {
    const { calls } = stubApi()
    renderPage('/w/ws-1/memory?tab=approval&pullback=1')
    const dialog = await screen.findByRole('dialog')
    await within(dialog).findByText('Betrifft 2 Einträge.')
    fireEvent.click(within(dialog).getByLabelText('Seit'))
    const date = within(dialog).getByTestId('pullback-since')
    expect(date).toHaveAttribute('type', 'date')
    fireEvent.change(date, { target: { value: '2001-01-01' } })
    // Ungültig: keine Zählung, Knopf bleibt aus.
    await new Promise((resolve) => setTimeout(resolve, 400))
    expect(within(dialog).getByTestId('pullback-submit')).toBeDisabled()
    const before = previewCalls(calls).length
    const yesterday = new Date(Date.now() - 24 * 3600_000)
    const pad = (n: number) => String(n).padStart(2, '0')
    const value = `${yesterday.getFullYear()}-${pad(yesterday.getMonth() + 1)}-${pad(yesterday.getDate())}`
    fireEvent.change(date, { target: { value } })
    await waitFor(() => expect(previewCalls(calls).length).toBeGreaterThan(before))
    expect(previewCalls(calls).at(-1)?.body?.since).toBe(new Date(`${value}T00:00:00`).toISOString())
  })

  it('bei 0 Treffern heißt der Primärknopf „Schließen“ und führt nichts aus', async () => {
    const { calls } = stubApi({ previews: [{ count: 0 }] })
    renderPage('/w/ws-1/memory?tab=approval&pullback=1')
    const dialog = await screen.findByRole('dialog')
    expect(
      await within(dialog).findByText('Keine automatisch freigegebenen Einträge in diesem Zeitraum.'),
    ).toBeInTheDocument()
    expect(within(dialog).queryByTestId('pullback-submit')).toBeNull()
    fireEvent.click(within(dialog).getByTestId('pullback-close'))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(executeCalls(calls)).toHaveLength(0)
  })

  it('Zählfehler: Hinweis statt Zahl, Ausführen bleibt aus', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = new URL(String(input), 'http://x').pathname
        if (path.endsWith('/memories/revoke-auto')) return jsonResponse({ detail: 'x' }, 500)
        if (path.endsWith('/memories/counts')) return jsonResponse({ total: 0 })
        if (path.endsWith('/memories')) return jsonResponse({ items: [], next_cursor: null })
        return jsonResponse([])
      }),
    )
    renderPage('/w/ws-1/memory?tab=approval&pullback=1')
    const dialog = await screen.findByRole('dialog')
    expect(
      await within(dialog).findByText('Die Zahl ließ sich nicht ermitteln.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByTestId('pullback-submit')).toBeDisabled()
  })

  it('Agent-Auswahl darf schmaler werden als der längste Agentenname (390 px, kein Überlauf)', async () => {
    stubApi()
    renderPage('/w/ws-1/memory?tab=approval&pullback=1')
    const dialog = await screen.findByRole('dialog')
    const select = within(dialog).getByTestId('pullback-agent')
    // Grid- und Flex-Kinder haben sonst `min-width: auto` (Messung: right=403 bei 390).
    expect(select).toHaveClass('min-w-0', 'max-w-full')
    expect(select.parentElement).toHaveClass('min-w-0')
    expect(select.parentElement?.parentElement).toHaveClass('min-w-0')
  })

  it('hat keine axe-Verstöße', async () => {
    stubApi()
    renderPage('/w/ws-1/memory?tab=approval&pullback=1')
    const dialog = await screen.findByRole('dialog')
    await within(dialog).findByText('Betrifft 2 Einträge.')
    expect(await axe(dialog)).toHaveNoViolations()
  })
})
