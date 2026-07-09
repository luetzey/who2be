import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { SystemPromptNewPage } from './SystemPromptNewPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// BlockNote-Insel mocken — ProseMirror kann in jsdom nicht mounten.
vi.mock('@/components/editor/system-prompt/SystemPromptEditor', () => ({
  SystemPromptEditor: () => <div data-testid="system-prompt-editor" />,
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

const WS_PREFIX = '/v1/workspaces/ws-1'

function renderPage() {
  return render(
    <SessionContext.Provider
      value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/system-prompts/new']}>
          <Routes>
            <Route
              path="/w/:workspaceId/system-prompts/new"
              element={<SystemPromptNewPage />}
            />
            <Route
              path="/w/:workspaceId/system-prompts/:id"
              element={<div>Detail von sp42</div>}
            />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

function submitForm() {
  const submitButton = screen.getByRole('button', { name: 'Anlegen' })
  fireEvent.click(submitButton)
  // jsdom loest die implizite Form-Submission nicht zuverlaessig aus —
  // zusaetzlich direkt submitten (Muster aus PersonaNewPage.test.tsx).
  const form = submitButton.closest('form')
  if (form !== null) {
    fireEvent.submit(form)
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('SystemPromptNewPage', () => {
  it('validiert den Pflicht-Namen und schickt ohne Namen keinen Request', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    submitForm()

    // Die Schema-Message wird beim Modul-Import aufgeloest — Sprache kann
    // de oder en sein, daher beide Varianten zulassen.
    expect(
      await screen.findByText(/Name (erforderlich\.|is required\.)/),
    ).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('legt das Template an und leitet auf die Detailseite weiter', async () => {
    const postCalls: Array<{ body: unknown }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        const pathname = new URL(String(input)).pathname
        if (method === 'POST' && pathname === `${WS_PREFIX}/system-prompts`) {
          postCalls.push({ body: JSON.parse(init?.body as string) })
          return new Response(
            JSON.stringify({
              id: 'sp42',
              workspace_id: 'ws-1',
              owner_id: 'o1',
              name: 'Mein Template',
              slug: 'mein-template',
              current_version: 1,
              content: { description: '', body: '[]' },
              created_at: '2026-07-01T00:00:00Z',
              updated_at: '2026-07-01T00:00:00Z',
            }),
            { status: 200 },
          )
        }
        throw new Error(`Unmocked ${method} ${pathname}`)
      }),
    )

    renderPage()

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Mein Template' },
    })
    submitForm()

    await waitFor(() => {
      expect(screen.getByText('Detail von sp42')).toBeInTheDocument()
    })
    expect(notify.success).toHaveBeenCalledWith('Template angelegt.')
    // submitForm feuert click + submit (jsdom-Fallback) — je nach Umgebung
    // kommen 1–2 POSTs an; entscheidend ist der Payload.
    expect(postCalls.length).toBeGreaterThanOrEqual(1)
    // Leeres BlockNote-Dokument serialisiert zu "[]" (Pydantic min_length=1).
    expect(postCalls[0].body).toEqual({
      name: 'Mein Template',
      content: { description: '', body: '[]' },
    })
  })

  it('zeigt den Server-Fehler als ErrorAlert und bleibt auf der Seite', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: 'Slug bereits vergeben.' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    renderPage()

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Mein Template' },
    })
    submitForm()

    expect(await screen.findByText('Slug bereits vergeben.')).toBeInTheDocument()
    expect(screen.queryByText('Detail von sp42')).not.toBeInTheDocument()
    expect(notify.success).not.toHaveBeenCalled()
  })
})
