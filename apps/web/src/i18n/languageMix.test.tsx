/**
 * Guard gegen Sprachmix (Audit A9): Stellen, die frueher fest verdrahtet
 * deutsch waren, muessen in der englischen Oberflaeche englisch erscheinen.
 *
 * Jede Zusicherung rendert die echte Komponente mit `en` und prueft den Text,
 * den eine Nutzerin (oder ein Screenreader) wahrnimmt. Wird eine der Stellen
 * auf ein deutsches Literal zurueckgebaut, schlaegt genau ihr Fall rot an.
 * Der Seiten-Setup folgt `SystemPromptDetailPage.test.tsx` und
 * `ToolDetailPage.test.tsx` (gemockte BlockNote-Insel, Fetch-Stub).
 */
import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DashboardActivity, Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { ActivityRow } from '@/features/dashboard/components/ActivityRow'
import { SystemPromptDetailPage } from '@/features/system-prompts/pages/SystemPromptDetailPage'
import { ToolDetailPage } from '@/features/tools/pages/ToolDetailPage'
import i18n, { DEFAULT_LOCALE } from '@/i18n'
import { notify } from '@/lib/feedback'

import en from './locales/en.json'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))
vi.mock('@/components/editor/system-prompt/SystemPromptEditor', () => ({
  SystemPromptEditor: () => <div data-testid="system-prompt-editor" />,
}))
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

const WS = '/v1/workspaces/ws-1'
const session = { access_token: 'jwt' } as unknown as Session
const admin: Me = {
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
}

function stubFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${new URL(String(input)).pathname}`
      if (!(key in routes)) throw new Error(`Unmocked ${key}`)
      return new Response(JSON.stringify(routes[key]), { status: 200 })
    }),
  )
}

function renderRoute(path: string, entry: string, element: ReactElement) {
  return render(
    <SessionContext.Provider
      value={{ session, me: admin, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route path={path} element={element} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

beforeAll(() => {
  for (const fn of ['hasPointerCapture', 'releasePointerCapture', 'setPointerCapture', 'scrollIntoView'] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
})

beforeEach(async () => {
  await i18n.changeLanguage('en')
})

afterEach(async () => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  await i18n.changeLanguage(DEFAULT_LOCALE)
})

describe('Sprachmix-Guard (Audit A9) — englische Oberflaeche', () => {
  describe('ActivityRow', () => {
    const base: DashboardActivity = {
      ts: '2026-05-28T10:00:00Z',
      entity_type: 'persona',
      entity_id: 'p1',
      entity_name: 'Coach',
      event: 'submitted_for_review',
    }

    it('uebersetzt Event, Entity-Typ und den unbekannten Akteur', () => {
      render(<ActivityRow activity={base} />)
      const row = screen.getByText('Coach').parentElement
      expect(row).toHaveTextContent('Unknown submitted for review Persona Coach')
    })

    it('uebersetzt das Ersatz-Verb, wenn das Event fehlt', () => {
      render(
        <ActivityRow
          activity={{ ...base, event: '', actor: { user_id: 'u1', display_name: 'Alice' } }}
        />,
      )
      expect(screen.getByText('Coach').parentElement).toHaveTextContent('Alice changed Persona Coach')
    })

    it('laesst ein unbekanntes Event lesbar roh stehen', () => {
      render(<ActivityRow activity={{ ...base, event: 'moved_to_archive' }} />)
      expect(screen.getByText('Coach').parentElement).toHaveTextContent('moved to archive')
    })
  })

  describe('SystemPromptDetailPage', () => {
    const template = {
      id: 'sp1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Support template',
      slug: 'support-template',
      current_version: 2,
      current_status: 'review',
      has_pending_draft: false,
      content: { description: 'Support', body: '[]' },
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    }
    const versions = [
      { version: 2, status: 'review', content: template.content, created_by: 'o1', created_at: 't' },
      { version: 1, status: 'inactive', content: template.content, created_by: 'o1', created_at: 't' },
    ]

    function renderPage() {
      stubFetch({
        [`GET ${WS}/system-prompts/sp1`]: template,
        [`GET ${WS}/system-prompts/sp1/versions`]: versions,
        [`POST ${WS}/system-prompts/sp1/versions/1/restore`]: template,
      })
      renderRoute('/w/:workspaceId/system-prompts/:id', '/w/ws-1/system-prompts/sp1', <SystemPromptDetailPage />)
    }

    it('Review-Banner, Tab-Leiste und Versions-Tab sind englisch', async () => {
      renderPage()
      expect(await screen.findByText('Version v2 is in review')).toBeInTheDocument()
      expect(screen.getByRole('tablist', { name: 'Detail view' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: 'Versions' })).toBeInTheDocument()
    })

    it('der Restore-Toast ist englisch', async () => {
      renderPage()
      fireEvent.click(await screen.findByRole('tab', { name: 'Versions' }))
      // Zwei Versionen, zwei Restore-Knoepfe; der zweite gehoert zu v1.
      const restoreButtons = screen.getAllByRole('button', { name: 'Restore' })
      fireEvent.click(restoreButtons[restoreButtons.length - 1])
      await waitFor(() => {
        expect(notify.success).toHaveBeenCalledWith('v1 restored as draft.')
      })
    })
  })

  describe('ToolDetailPage', () => {
    it('die Tab-Leiste traegt ein englisches Label', async () => {
      stubFetch({
        [`GET ${WS}/external_tools/t1`]: {
          id: 't1',
          workspace_id: 'ws-1',
          owner_id: 'o1',
          name: 'Todoist',
          alias: 'todo',
          current_version: 1,
          content: {
            display_name: 'Todoist App',
            mcp_server_name: 'Todoist MCP',
            tool_names: ['add_task'],
            usage_notes: '[]',
            fallback_note: null,
            tags: [],
          },
          created_at: 't',
          updated_at: 't',
        },
        [`GET ${WS}/external_tools/t1/versions`]: [],
      })
      renderRoute('/w/:workspaceId/tools/:id', '/w/ws-1/tools/t1', <ToolDetailPage />)
      expect(await screen.findByRole('tablist', { name: 'Detail view' })).toBeInTheDocument()
    })
  })

  describe('en.json', () => {
    it('das Typ-Feld im Playbook-Formular heisst englisch', () => {
      expect(en.playbooks.form.typeLabel).toBe('Type')
    })

    it('enthaelt keine deutschen Sonderzeichen', () => {
      const offenders: string[] = []
      const walk = (node: unknown, path: string) => {
        if (typeof node === 'string') {
          if (/[äöüÄÖÜß]/.test(node)) offenders.push(`${path}: ${node}`)
        } else if (node !== null && typeof node === 'object') {
          for (const [key, value] of Object.entries(node)) walk(value, path ? `${path}.${key}` : key)
        }
      }
      walk(en, '')
      expect(offenders).toEqual([])
    })
  })
})
