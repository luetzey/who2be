import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryGuardConfig } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { MemoryGuardSection } from './MemoryGuardSection'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Acme',
        slug: 'acme',
        kind: 'company',
        workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role: 'admin' }],
      },
    ],
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), { status })
}

const standardConfig: MemoryGuardConfig = {
  mode: 'standard',
  allow_phrases: [],
  block_phrases: [],
}

function renderSection() {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me: buildMe(),
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn().mockResolvedValue(undefined),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/settings/workspace']}>
          <Routes>
            <Route path="/w/:workspaceId/settings/workspace" element={<MemoryGuardSection />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('MemoryGuardSection', () => {
  it('lädt die Konfiguration per GET und zeigt den Standard-Modus vorausgewählt', async () => {
    let getUrl = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        getUrl = String(input)
        return jsonResponse(standardConfig)
      }),
    )

    renderSection()

    expect(await screen.findByRole('radio', { name: 'Standard' })).toBeChecked()
    expect(getUrl).toContain('/v1/workspaces/ws-1/memory-guard')
    // Im Standard-Modus weder Warnung noch Phrasen-Editoren.
    expect(screen.queryByText(/Automatisch-Modus/)).toBeNull()
    expect(screen.queryByLabelText('Ausnahme-Phrasen')).toBeNull()
  })

  it('zeigt bei Modus "Aus" die Warnung und sendet mode "off" per PUT', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        if (method === 'PUT') {
          bodies.push(JSON.parse(init?.body as string))
          return jsonResponse({ mode: 'off', allow_phrases: [], block_phrases: [] })
        }
        return jsonResponse(standardConfig)
      }),
    )

    renderSection()
    await screen.findByRole('radio', { name: 'Standard' })

    fireEvent.click(screen.getByRole('radio', { name: 'Aus' }))
    expect(screen.getByText(/Automatisch-Modus/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toEqual({ mode: 'off', allow_phrases: [], block_phrases: [] })
  })

  it('fügt im Modus "Angepasst" eine Ausnahme-Phrase hinzu, entfernt sie wieder und sendet die Listen per PUT', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        if (method === 'PUT') {
          bodies.push(JSON.parse(init?.body as string))
          return jsonResponse({
            mode: 'custom',
            allow_phrases: ['Jailbreak-Detection'],
            block_phrases: [],
          })
        }
        return jsonResponse(standardConfig)
      }),
    )

    renderSection()
    await screen.findByRole('radio', { name: 'Standard' })

    fireEvent.click(screen.getByRole('radio', { name: 'Angepasst' }))

    const allowInput = screen.getByLabelText('Ausnahme-Phrasen')
    fireEvent.change(allowInput, { target: { value: 'Jailbreak-Detection' } })
    fireEvent.keyDown(allowInput, { key: 'Enter' })
    expect(screen.getByText('Jailbreak-Detection')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toEqual({
      mode: 'custom',
      allow_phrases: ['Jailbreak-Detection'],
      block_phrases: [],
    })

    fireEvent.click(screen.getByRole('button', { name: 'Tag Jailbreak-Detection entfernen' }))
    expect(screen.queryByText('Jailbreak-Detection')).toBeNull()
  })

  it('lehnt zu kurze Phrasen client-seitig ab', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(standardConfig)))

    renderSection()
    await screen.findByRole('radio', { name: 'Standard' })
    fireEvent.click(screen.getByRole('radio', { name: 'Angepasst' }))

    const allowInput = screen.getByLabelText('Ausnahme-Phrasen')
    fireEvent.change(allowInput, { target: { value: 'x' } })
    fireEvent.keyDown(allowInput, { key: 'Enter' })

    expect(screen.getByText('Eine Phrase muss 2–100 Zeichen lang sein.')).toBeInTheDocument()
    expect(screen.queryByText('x')).toBeNull()
  })

  it('zeigt einen Fehler, wenn das Laden fehlschlägt', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'nope' }, 403)))

    renderSection()

    expect(await screen.findByText('Fehler')).toBeInTheDocument()
  })
})
