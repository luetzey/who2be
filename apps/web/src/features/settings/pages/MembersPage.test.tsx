import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Invitation, Me, Member, WorkspaceRole } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'

import { MembersPage } from './MembersPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// Clipboard-Modul mocken — jsdom hat weder navigator.clipboard noch ein
// funktionierendes execCommand('copy'); getestet wird das Page-Verhalten
// (Toast-Pfade), nicht der Browser-Fallback.
vi.mock('@/lib/clipboard', () => ({
  copyToClipboard: vi.fn(async () => undefined),
}))

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'o1',
        name: 'Org',
        slug: 'org',
        kind: 'personal',
        workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role }],
      },
    ],
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

function renderMembers(role: WorkspaceRole = 'admin') {
  return render(
    <SessionContext.Provider
      value={{ session, me: buildMe(role), sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/settings/members']}>
          <Routes>
            <Route path="/w/:workspaceId/settings/members" element={<MembersPage />} />
            <Route path="/w/:workspaceId/dashboard" element={<div>DASHBOARD</div>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
  vi.mocked(notify.info).mockClear()
  vi.mocked(copyToClipboard).mockClear()
})

describe('MembersPage', () => {
  it('listet die Mitglieder des Workspace', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/members')) {
          return jsonResponse([
            {
              user_id: 'm1',
              email: 'coder@who2be.dev',
              role: 'editor',
              joined_at: '2026-05-01T10:00:00Z',
            },
          ])
        }
        return jsonResponse([])
      }),
    )

    renderMembers('admin')

    await waitFor(() => {
      expect(screen.getByText('coder@who2be.dev')).toBeInTheDocument()
    })
  })

  it('verschickt eine Einladung via POST /invitations', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'
        if (method === 'POST' && url.includes('/invitations')) {
          bodies.push(JSON.parse(init?.body as string))
          return jsonResponse(
            {
              id: 'i1',
              email: 'neu@who2be.dev',
              role: 'editor',
              expires_at: '2026-06-01T10:00:00Z',
              created_at: '2026-05-29T10:00:00Z',
              token: 'inv-token',
            },
            201,
          )
        }
        return jsonResponse([])
      }),
    )

    renderMembers('admin')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Einladen' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Einladen' }))

    await waitFor(() => {
      expect(bodies).toHaveLength(1)
    })
    expect(bodies[0]).toEqual({ email: 'neu@who2be.dev', role: 'editor' })
    expect(notify.success).toHaveBeenCalledWith('Einladung an neu@who2be.dev verschickt.')
  })

  it('wirft Editoren aufs Dashboard zurück', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse([])))

    renderMembers('editor')

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: 'Mitglieder' })).toBeNull()
    expect(notify.error).toHaveBeenCalledWith('Diese Seite ist nur für Admins.')
  })
})

// ---------------------------------------------------------------------------
// Branch-Coverage-Ergaenzungen (Coverage-Nachrunde): Rollen-Aenderung
// (Erfolg/Downgrade/No-op/Fehler), Mitglied entfernen, Invitations (Erstellen
// inkl. Validierung + Fehlerpfad, Liste, Copy-Link, Widerruf) und die
// Fallback-Zweige von describeError/tokenFor. Bestandstests oben bleiben
// unangetastet.
// ---------------------------------------------------------------------------

const WS_PREFIX = '/v1/workspaces/ws-1'

type FetchHandler = (
  path: string,
  method: string,
  init?: RequestInit,
) => Response | Promise<Response>

function errorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function member(overrides: Partial<Member> = {}): Member {
  return {
    user_id: 'm1',
    email: 'coder@who2be.dev',
    role: 'editor',
    joined_at: '2026-05-01T10:00:00Z',
    ...overrides,
  }
}

function invitation(overrides: Partial<Invitation> = {}): Invitation {
  return {
    id: 'i1',
    email: 'offen@who2be.dev',
    role: 'editor',
    expires_at: '2026-06-01T10:00:00Z',
    created_at: '2026-05-29T10:00:00Z',
    ...overrides,
  }
}

interface SettingsHandlerOptions {
  members?: () => Member[]
  invitations?: () => Invitation[]
}

function settingsHandlers(opts: SettingsHandlerOptions = {}): FetchHandler {
  return (path, method) => {
    if (method === 'GET') {
      if (path === `${WS_PREFIX}/members`) return jsonResponse(opts.members?.() ?? [member()])
      if (path === `${WS_PREFIX}/invitations`)
        return jsonResponse(opts.invitations?.() ?? [])
    }
    throw new Error(`Unmocked ${method} ${path}`)
  }
}

function stubFetch(handler: FetchHandler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(new URL(String(input)).pathname, init?.method ?? 'GET', init),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('MembersPage — Rollen-Aenderung', () => {
  it('Upgrade (editor → admin): PATCH + Erfolgs-Toast, kein Downgrade-Hinweis', async () => {
    const patchBodies: string[] = []
    const base = settingsHandlers()
    stubFetch((path, method, init) => {
      if (method === 'PATCH' && path === `${WS_PREFIX}/members/m1`) {
        patchBodies.push(String(init?.body))
        return jsonResponse(member({ role: 'admin' }))
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    const select = await screen.findByLabelText('Rolle von coder@who2be.dev')
    fireEvent.change(select, { target: { value: 'admin' } })

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Rolle aktualisiert.')
    })
    expect(patchBodies[0]).toContain('"role":"admin"')
    expect(notify.info).not.toHaveBeenCalled()
  })

  it('Downgrade (editor → viewer): zusaetzlicher Token-Snapshot-Hinweis', async () => {
    const base = settingsHandlers()
    stubFetch((path, method, init) => {
      if (method === 'PATCH' && path === `${WS_PREFIX}/members/m1`) {
        return jsonResponse(member({ role: 'viewer' }))
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    const select = await screen.findByLabelText('Rolle von coder@who2be.dev')
    fireEvent.change(select, { target: { value: 'viewer' } })

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Rolle aktualisiert.')
    })
    expect(notify.info).toHaveBeenCalledWith(
      'Bestehende API-Tokens dieses Mitglieds behalten ihre alte Rolle, bis sie widerrufen werden.',
    )
  })

  it('gleiche Rolle: kein PATCH, kein Toast (No-op-Zweig)', async () => {
    const base = settingsHandlers()
    const fetchMock = stubFetch(base)

    renderMembers('admin')

    const select = await screen.findByLabelText('Rolle von coder@who2be.dev')
    // React feuert bei <select> das onChange fuer jedes native change-Event —
    // gleicher Wert wie die aktuelle Rolle trifft den Early-Return.
    fireEvent.change(select, { target: { value: 'editor' } })

    await waitFor(() => {
      expect(select).toHaveValue('editor')
    })
    const patchCalls = fetchMock.mock.calls.filter(
      (call) => (call[1] as RequestInit | undefined)?.method === 'PATCH',
    )
    expect(patchCalls).toHaveLength(0)
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('meldet die Server-Message per Toast, wenn das PATCH fehlschlaegt', async () => {
    const base = settingsHandlers()
    stubFetch((path, method, init) => {
      if (method === 'PATCH' && path === `${WS_PREFIX}/members/m1`) {
        return errorResponse(500, 'Rolle kaputt')
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    const select = await screen.findByLabelText('Rolle von coder@who2be.dev')
    fireEvent.change(select, { target: { value: 'admin' } })

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Rolle kaputt')
    })
    expect(notify.success).not.toHaveBeenCalled()
  })
})

describe('MembersPage — Mitglied entfernen', () => {
  it('entfernt das Mitglied via DELETE und laedt die Liste neu', async () => {
    let removed = false
    const base = settingsHandlers({
      members: () => (removed ? [] : [member()]),
    })
    stubFetch((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/members/m1`) {
        removed = true
        return new Response(null, { status: 204 })
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    fireEvent.click(await screen.findByRole('button', { name: 'Entfernen' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Mitglied entfernt.')
    })
    await waitFor(() => {
      expect(screen.getByText('Noch keine Mitglieder.')).toBeInTheDocument()
    })
  })

  it('faellt bei Nicht-Error-Ursachen auf die generische Meldung zurueck', async () => {
    const base = settingsHandlers()
    stubFetch((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/members/m1`) {
        return new Response(null, { status: 204 })
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    // Non-Error-Rejection im try-Block: der Success-Toast wirft einen String.
    vi.mocked(notify.success).mockImplementationOnce(() => {
      throw 'kaputt'
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Entfernen' }))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Aktion fehlgeschlagen.')
    })
  })

  it('zeigt die user_id, wenn das Mitglied keine E-Mail hat', async () => {
    stubFetch(settingsHandlers({ members: () => [member({ email: null })] }))

    renderMembers('admin')

    expect(await screen.findByText('m1')).toBeInTheDocument()
  })
})

describe('MembersPage — Invitations', () => {
  it('Validierung: ungueltige E-Mail zeigt die Zod-Meldung, kein POST', async () => {
    const fetchMock = stubFetch(settingsHandlers())

    renderMembers('admin')

    await screen.findByRole('button', { name: 'Einladen' })
    const emailInput = screen.getByLabelText('E-Mail')
    fireEvent.change(emailInput, { target: { value: 'keine-mail' } })
    // jsdom blockt den nativen Submit bei invalider `type="email"`-Eingabe —
    // das submit-Event direkt am Formular feuern, damit der Zod-Resolver laeuft.
    fireEvent.submit(emailInput.closest('form') as HTMLFormElement)

    // Die Zod-Message wird beim Modul-Import aufgeloest (i18n.t im Schema-
    // Literal) — zu dem Zeitpunkt steht der jsdom-Sprachdetektor noch auf
    // Englisch, erst das Test-Setup schaltet danach auf Deutsch um.
    expect(
      await screen.findByText('Please enter a valid email.'),
    ).toBeInTheDocument()
    const postCalls = fetchMock.mock.calls.filter(
      (call) => (call[1] as RequestInit | undefined)?.method === 'POST',
    )
    expect(postCalls).toHaveLength(0)
  })

  it('meldet den Fehler per Toast, wenn das Einladen fehlschlaegt', async () => {
    const base = settingsHandlers()
    stubFetch((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/invitations`) {
        return errorResponse(409, 'Bereits eingeladen')
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    await screen.findByRole('button', { name: 'Einladen' })
    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Einladen' }))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Bereits eingeladen')
    })
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('Erstellen mit Token: Link ist sofort kopierbar (Session-Token-Cache)', async () => {
    let created: Invitation | null = null
    const base = settingsHandlers({
      // Backend liefert den Klartext-Token nur einmal beim POST — die Liste
      // bleibt Hash-only (ADR-0023).
      invitations: () => (created === null ? [] : [{ ...created, token: null }]),
    })
    stubFetch((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/invitations`) {
        created = invitation({ email: 'neu@who2be.dev', token: 'tok-neu' })
        return jsonResponse(created)
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    await screen.findByRole('button', { name: 'Einladen' })
    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Einladen' }))

    const copy = await screen.findByRole('button', { name: 'Link kopieren' })
    expect(copy).toBeEnabled()

    fireEvent.click(copy)

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Einladungs-Link kopiert.')
    })
    expect(copyToClipboard).toHaveBeenCalledWith(
      `${window.location.origin}/invitations/tok-neu/accept`,
    )
  })

  it('Erstellen ohne Token in der Antwort: Copy bleibt gesperrt mit Hinweis', async () => {
    let created: Invitation | null = null
    const base = settingsHandlers({
      invitations: () => (created === null ? [] : [created]),
    })
    stubFetch((path, method, init) => {
      if (method === 'POST' && path === `${WS_PREFIX}/invitations`) {
        created = invitation({ email: 'neu@who2be.dev' })
        return jsonResponse(created)
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    await screen.findByRole('button', { name: 'Einladen' })
    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Einladen' }))

    const copy = await screen.findByRole('button', { name: 'Link kopieren' })
    expect(copy).toBeDisabled()
    expect(copy).toHaveAttribute(
      'title',
      'Link nur direkt nach dem Einladen kopierbar',
    )
    expect(copyToClipboard).not.toHaveBeenCalled()
  })

  it('Listen-Invitation mit Token: kopiert die Accept-URL', async () => {
    stubFetch(
      settingsHandlers({
        invitations: () => [invitation({ token: 'tok-liste' })],
      }),
    )

    renderMembers('admin')

    const copy = await screen.findByRole('button', { name: 'Link kopieren' })
    fireEvent.click(copy)

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Einladungs-Link kopiert.')
    })
    expect(copyToClipboard).toHaveBeenCalledWith(
      `${window.location.origin}/invitations/tok-liste/accept`,
    )
  })

  it('Copy-Fehler mit Error: zeigt die Fehlermeldung des Clipboards', async () => {
    stubFetch(
      settingsHandlers({
        invitations: () => [invitation({ token: 'tok-liste' })],
      }),
    )
    vi.mocked(copyToClipboard).mockRejectedValueOnce(
      new Error('Clipboard nicht verfuegbar.'),
    )

    renderMembers('admin')

    fireEvent.click(await screen.findByRole('button', { name: 'Link kopieren' }))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Clipboard nicht verfuegbar.')
    })
  })

  it('Copy-Fehler ohne Error: faellt auf die generische Meldung zurueck', async () => {
    stubFetch(
      settingsHandlers({
        invitations: () => [invitation({ token: 'tok-liste' })],
      }),
    )
    vi.mocked(copyToClipboard).mockRejectedValueOnce('kaputt')

    renderMembers('admin')

    fireEvent.click(await screen.findByRole('button', { name: 'Link kopieren' }))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Ein Fehler ist aufgetreten.')
    })
  })

  it('widerruft eine Invitation via DELETE und laedt die Liste neu', async () => {
    let revoked = false
    const base = settingsHandlers({
      invitations: () => (revoked ? [] : [invitation()]),
    })
    stubFetch((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/invitations/i1`) {
        revoked = true
        return new Response(null, { status: 204 })
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    fireEvent.click(await screen.findByRole('button', { name: 'Widerrufen' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Einladung widerrufen.')
    })
    await waitFor(() => {
      expect(screen.getByText('Keine offenen Einladungen.')).toBeInTheDocument()
    })
  })

  it('meldet den Fehler per Toast, wenn das Widerrufen fehlschlaegt', async () => {
    const base = settingsHandlers({ invitations: () => [invitation()] })
    stubFetch((path, method, init) => {
      if (method === 'DELETE' && path === `${WS_PREFIX}/invitations/i1`) {
        return errorResponse(500, 'Widerruf kaputt')
      }
      return base(path, method, init)
    })

    renderMembers('admin')

    fireEvent.click(await screen.findByRole('button', { name: 'Widerrufen' }))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalledWith('Widerruf kaputt')
    })
    expect(notify.success).not.toHaveBeenCalled()
  })
})
