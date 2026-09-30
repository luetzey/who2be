import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, VersionStatus, WorkspaceRole } from '@/api/types'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { SystemPromptStatusActionBar } from './SystemPromptStatusActionBar'

// Befund 1 aus dem Review von #693: die MFA-Vorankuendigung und der nicht-
// destruktive „Zurueck zu Draft" dieser eigenen Leiste waren ungetestet
// (Mutation `promoteNeedsMfa = false` blieb gruen). Dazu der Link
// „Aenderungen ansehen" (Audit E1 = A).

const { transition } = vi.hoisted(() => ({ transition: vi.fn() }))

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ transitionSystemPromptTemplateVersion: transition }),
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

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

function buildSession(aal: string | null): Session {
  // Nur der Payload-Teil zaehlt fuer `sessionAal`; Header/Signatur sind Attrappen.
  const payload = btoa(JSON.stringify(aal === null ? { sub: 'u1' } : { sub: 'u1', aal }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
  return { access_token: `h.${payload}.s` } as unknown as Session
}

interface RenderOptions {
  role?: WorkspaceRole
  aal?: string | null
  diffVersion?: number
  onTransitioned?: () => void
}

function renderBar(status: VersionStatus, options: RenderOptions = {}) {
  const { role = 'admin', aal = null, diffVersion, onTransitioned = vi.fn() } = options
  return render(
    <SessionContext.Provider
      value={{
        session: buildSession(aal),
        me: buildMe(role),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <MemoryRouter initialEntries={['/w/ws-1/system-prompts/sp1']}>
        <SystemPromptStatusActionBar
          templateId="sp1"
          version={3}
          status={status}
          onTransitioned={onTransitioned}
          diffVersion={diffVersion}
        />
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  transition.mockReset()
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('SystemPromptStatusActionBar — MFA-Vorankuendigung (Audit A1)', () => {
  it('zeigt einem Admin bei aal1 den Hinweis und den Weg zur Einrichtung statt Aktivieren', () => {
    renderBar('review', { aal: 'aal1' })

    expect(screen.queryByRole('button', { name: 'Aktivieren' })).toBeNull()
    expect(screen.getByTestId('publish-mfa-notice')).toHaveTextContent(
      'Veröffentlichen erfordert Zwei-Faktor-Anmeldung.',
    )
    expect(screen.getByRole('link', { name: 'Zwei-Faktor einrichten' })).toBeInTheDocument()
    // Zurueck zu Draft braucht kein aal2 und bleibt nutzbar.
    expect(screen.getByRole('button', { name: 'Zurück zu Draft' })).toBeEnabled()
  })

  it('zeigt einem Admin bei aal2 den aktiven Aktivieren-Knopf und keinen Hinweis', () => {
    renderBar('review', { aal: 'aal2' })

    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    expect(screen.queryByTestId('publish-mfa-notice')).toBeNull()
  })

  it('laesst Editoren auch bei aal1 beim gesperrten Knopf mit Admin-Tooltip', () => {
    renderBar('review', { role: 'editor', aal: 'aal1' })

    const activate = screen.getByRole('button', { name: 'Aktivieren' })
    expect(activate).toBeDisabled()
    expect(activate).toHaveAttribute('title', 'Nur Admins können aktivieren')
    expect(screen.queryByTestId('publish-mfa-notice')).toBeNull()
  })
})

describe('SystemPromptStatusActionBar — Review-Leiste', () => {
  // Audit A2: umkehrbar, also keine rote Aktion (design-language §9.1).
  it('rendert „Zurück zu Draft" als outline, nicht destruktiv', () => {
    renderBar('review', { aal: 'aal2' })

    const back = screen.getByRole('button', { name: 'Zurück zu Draft' })
    expect(back.className).toMatch(/\bborder-input\b/)
    expect(back.className).not.toMatch(/bg-destructive/)
  })

  it('fuehrt „Zurück zu Draft" als review→draft-Transition aus', async () => {
    transition.mockResolvedValue(undefined)
    const onTransitioned = vi.fn()
    renderBar('review', { aal: 'aal2', onTransitioned })

    fireEvent.click(screen.getByRole('button', { name: 'Zurück zu Draft' }))

    await waitFor(() => expect(onTransitioned).toHaveBeenCalledTimes(1))
    expect(transition).toHaveBeenCalledWith('sp1', 3, 'draft')
    expect(notify.success).toHaveBeenCalledWith('Zurück in den Entwurf.')
  })

  // Audit E1 = A: ein Klick aus der Leiste in den Diff der Review-Version.
  it('verlinkt im Review den Diff der uebergebenen Version auf demselben Pfad', () => {
    renderBar('review', { aal: 'aal2', diffVersion: 3 })

    expect(screen.getByRole('link', { name: 'Änderungen und Prüffälle ansehen' })).toHaveAttribute(
      'href',
      '/w/ws-1/system-prompts/sp1?tab=versions&diff=3',
    )
  })

  it('zeigt den Link auch neben dem MFA-Hinweis (Pruefen geht ohne aal2)', () => {
    renderBar('review', { aal: 'aal1', diffVersion: 3 })

    expect(screen.getByRole('link', { name: 'Änderungen und Prüffälle ansehen' })).toBeInTheDocument()
  })

  it('zeigt ohne diffVersion keinen Link', () => {
    renderBar('review', { aal: 'aal2' })

    expect(screen.queryByRole('link', { name: 'Änderungen und Prüffälle ansehen' })).toBeNull()
  })

  it('zeigt im Draft keinen Link, auch wenn eine Version uebergeben wird', () => {
    renderBar('draft', { diffVersion: 3 })

    expect(screen.getByRole('button', { name: 'Zur Review einreichen' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Änderungen und Prüffälle ansehen' })).toBeNull()
  })
})
