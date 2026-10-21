import type { Session } from '@supabase/supabase-js'
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { RoutinesOverview } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { renderInRoutes } from '@/test/render'

import { RoutinesPanel } from './RoutinesPanel'
import { SettingsNav } from './SettingsNav'

const session = { access_token: 'jwt' } as unknown as Session

// ADR-0057 §7 (P5): nur lesender Betreiber-Abschnitt. Die API entscheidet ueber
// die Sichtbarkeit; bei 403 darf vom Abschnitt nichts uebrig bleiben (PM-W7).

const ROUTINES_PATH = '/v1/system/routines'

const overview: RoutinesOverview = {
  worker_last_seen_at: '2026-10-10T19:58:00Z',
  routines: [
    {
      name: 'audit-retention',
      schedule: '0 4 * * *',
      enabled: true,
      source: 'code',
      last_run: {
        status: 'failed',
        trigger: 'schedule',
        started_at: '2026-10-10T04:00:00Z',
        duration_ms: 83_500,
        result: { deleted: 1200 },
        error_class: 'UndefinedTableError',
      },
      next_run_at: '2026-10-11T04:00:00Z',
      last_success_at: '2026-10-09T04:00:12Z',
      external_schedule_detected: true,
    },
    {
      name: 'usage-rollup',
      schedule: '@every 15m',
      enabled: false,
      source: 'env',
      last_run: null,
      next_run_at: null,
      last_success_at: null,
      external_schedule_detected: false,
    },
    {
      name: 'quick',
      schedule: '*/5 * * * *',
      enabled: true,
      source: 'code',
      last_run: {
        status: 'running',
        trigger: 'cli',
        started_at: '2026-10-10T19:55:00Z',
        duration_ms: null,
        result: null,
        error_class: null,
      },
      next_run_at: '2026-10-10T20:00:00Z',
      last_success_at: null,
      external_schedule_detected: false,
    },
    {
      name: 'short',
      schedule: '*/5 * * * *',
      enabled: true,
      source: 'code',
      last_run: {
        status: 'succeeded',
        trigger: 'manual',
        started_at: '2026-10-10T19:50:00Z',
        duration_ms: 420,
        result: {},
        error_class: null,
      },
      next_run_at: '2026-10-10T19:55:00Z',
      last_success_at: '2026-10-10T19:50:01Z',
      external_schedule_detected: false,
    },
    {
      name: 'medium',
      schedule: '*/5 * * * *',
      enabled: true,
      source: 'code',
      last_run: {
        status: 'skipped',
        trigger: 'schedule',
        started_at: '2026-10-10T19:45:00Z',
        duration_ms: 12_300,
        result: null,
        error_class: null,
      },
      next_run_at: '2026-10-10T19:50:00Z',
      last_success_at: null,
      external_schedule_detected: false,
    },
  ],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

/** Routinen-Antwort steuerbar, alles andere (Glocke usw.) leer und 200. */
function stubFetch(routines: () => Response) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      calls.push(url)
      if (url.endsWith(ROUTINES_PATH)) return routines()
      return jsonResponse({})
    }),
  )
  return calls
}

function renderPanel() {
  return render(
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
        <MemoryRouter>
          <Routes>
            <Route path="*" element={<RoutinesPanel />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('RoutinesPanel', () => {
  it('zeigt fuer Betreiber jede Routine mit Zeitplan, Status, Quelle und Laufdaten', async () => {
    stubFetch(() => jsonResponse(overview))
    renderPanel()

    const panel = await screen.findByRole('region', { name: 'Hintergrund-Routinen' })
    expect(within(panel).getByText('Worker zuletzt gesehen:')).toBeInTheDocument()

    const items = within(panel).getAllByTestId('routine-item')
    expect(items).toHaveLength(5)

    const audit = items[0]
    expect(within(audit).getByRole('heading', { name: 'audit-retention' })).toBeInTheDocument()
    expect(within(audit).getByText('0 4 * * *')).toBeInTheDocument()
    expect(within(audit).getByText('An')).toBeInTheDocument()
    expect(within(audit).getByText('Quelle: Code')).toBeInTheDocument()
    expect(within(audit).getByText('Fehlgeschlagen')).toBeInTheDocument()
    expect(within(audit).getByText(/1 min 24 s/)).toBeInTheDocument()
    expect(within(audit).getByText(/deleted: 1\.200/)).toBeInTheDocument()
    expect(within(audit).getByText('UndefinedTableError')).toBeInTheDocument()
    expect(within(audit).getByText('Externer Zeitplan erkannt (Crontab/Dokploy).')).toBeInTheDocument()
    expect(within(audit).getByText('Kann entfernt werden.')).toBeInTheDocument()
    // Zeiten in Ortszeit, UTC sichtbar dahinter; maschinenlesbar im `dateTime`.
    const next = audit.querySelector('time[datetime="2026-10-11T04:00:00Z"]')
    expect(next?.textContent).toMatch(/UTC\)$/)

    const usage = items[1]
    expect(within(usage).getByText('Aus')).toBeInTheDocument()
    expect(within(usage).getByText('Quelle: Umgebung')).toBeInTheDocument()
    expect(within(usage).getByText('Noch kein Lauf')).toBeInTheDocument()
    expect(within(usage).queryByText(/Externer Zeitplan/)).toBeNull()

    expect(within(items[2]).getByText('Läuft')).toBeInTheDocument()
    expect(within(items[2]).getByText('per CLI')).toBeInTheDocument()
    expect(within(items[3]).getByText(/manuell · 420 ms/)).toBeInTheDocument()
    expect(within(items[4]).getByText(/nach Zeitplan · 12,3 s/)).toBeInTheDocument()

    // Nur lesend (W3): keine Knoepfe, keine Eingaben.
    expect(within(panel).queryByRole('button')).toBeNull()
    expect(within(panel).queryByRole('textbox')).toBeNull()
  })

  it('zeigt einen leeren Stand ohne Worker-Heartbeat', async () => {
    stubFetch(() => jsonResponse({ routines: [], worker_last_seen_at: null }))
    renderPanel()

    const panel = await screen.findByRole('region', { name: 'Hintergrund-Routinen' })
    expect(within(panel).getByText('Keine Routinen registriert.')).toBeInTheDocument()
    expect(within(panel).getByText('—')).toBeInTheDocument()
  })

  it('zeigt Betreibern die 503 bei ungueltigem Override als Fehler', async () => {
    stubFetch(() =>
      jsonResponse({ detail: 'Ungueltige Routinen-Konfiguration (ADR-0057): WHO2BE_ROUTINE_X' }, 503),
    )
    renderPanel()

    const panel = await screen.findByRole('region', { name: 'Hintergrund-Routinen' })
    expect(within(panel).getByRole('alert')).toBeInTheDocument()
    expect(within(panel).queryByTestId('routine-item')).toBeNull()
  })

  it.each([403, 401, 500, 0])(
    'rendert bei Status %i nichts, ohne Fehlermeldung',
    async (status) => {
      const calls = stubFetch(() =>
        status === 0 ? Promise.reject(new TypeError('offline')) as never : jsonResponse({ detail: 'nein' }, status),
      )
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const { container } = renderPanel()

      await waitFor(() => expect(calls.some((url) => url.endsWith(ROUTINES_PATH))).toBe(true))
      // Einen Tick warten, damit der abgelehnte Request verarbeitet ist.
      await new Promise((resolve) => setTimeout(resolve, 0))
      expect(container).toBeEmptyDOMElement()
      expect(screen.queryByRole('alert')).toBeNull()
      errorSpy.mockRestore()
    },
  )

  it('bei 403 erscheint weder Abschnitt noch Navigationseintrag noch Fehler (PM-W7)', async () => {
    const calls = stubFetch(() => jsonResponse({ detail: 'Nur fuer Betreiber.' }, 403))

    const { container } = renderInRoutes(
      <>
        <SettingsNav />
        <RoutinesPanel />
      </>,
      {
        path: '/w/:workspaceId/settings/account',
        initialEntries: ['/w/ws-1/settings/account'],
        me: {
          user_id: 'u1',
          default_workspace_id: 'ws-1',
          organizations: [
            {
              id: 'o1',
              name: 'Org',
              slug: 'org',
              kind: 'personal',
              workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'admin' }],
            },
          ],
        },
      },
    )

    await waitFor(() => expect(calls.some((url) => url.endsWith(ROUTINES_PATH))).toBe(true))
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(screen.queryByTestId('routines-panel')).toBeNull()
    expect(container.textContent).not.toMatch(/Routine|Worker/)
    expect(screen.queryByRole('alert')).toBeNull()
    // Keine Navigation fuehrt zum Abschnitt: die Settings-Nav bleibt bei ihren
    // vier Eintraegen, und kein Link im ganzen Layout nennt die Routinen.
    const settingsNav = screen.getByRole('navigation', { name: 'Einstellungen-Navigation' })
    expect(within(settingsNav).getAllByRole('link')).toHaveLength(4)
    for (const link of screen.getAllByRole('link')) {
      expect(link.textContent ?? '').not.toMatch(/Routine/)
      expect(link.getAttribute('href') ?? '').not.toMatch(/routine/i)
    }
  })
})
