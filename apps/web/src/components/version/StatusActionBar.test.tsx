import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Me, VersionStatus, WorkspaceRole } from '@/api/types'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import { StatusActionBar, type StatusActionKey } from './StatusActionBar'

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

function renderBar(
  status: VersionStatus,
  onTransition = vi.fn().mockResolvedValue(undefined),
  onTransitioned = vi.fn(),
  role: WorkspaceRole = 'admin',
  labels?: Partial<Record<StatusActionKey, string>>,
) {
  return render(
    <SessionContext.Provider
      value={{
        session: null,
        me: buildMe(role),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <MemoryRouter>
        <StatusActionBar
          status={status}
          onTransition={onTransition}
          onTransitioned={onTransitioned}
          labels={labels}
        />
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.mocked(notify.success).mockClear()
  vi.mocked(notify.error).mockClear()
})

describe('StatusActionBar', () => {
  it('zeigt im Draft nur den Submit-Button', () => {
    renderBar('draft')
    expect(
      screen.getByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aktivieren' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Ablehnen' })).toBeNull()
  })

  it('zeigt im Review Aktivieren und Ablehnen', () => {
    renderBar('review')
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ablehnen' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeNull()
  })

  it('aktiviert ist für Admins klickbar, für Editoren gesperrt', () => {
    const { unmount } = renderBar('review', vi.fn().mockResolvedValue(undefined), vi.fn(), 'admin')
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    unmount()

    renderBar('review', vi.fn().mockResolvedValue(undefined), vi.fn(), 'editor')
    const promote = screen.getByRole('button', { name: 'Aktivieren' })
    expect(promote).toBeDisabled()
    expect(promote).toHaveAttribute('title', 'Nur Admins können aktivieren')
  })

  it('rendert nichts im Status active', () => {
    const { container } = renderBar('active')
    expect(container).toBeEmptyDOMElement()
  })

  it('zeigt im Status inactive den Reactivate-Button', () => {
    renderBar('inactive')
    expect(
      screen.getByRole('button', { name: 'Reaktivieren als Draft' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aktivieren' })).toBeNull()
    expect(
      screen.queryByRole('button', { name: 'Zur Review einreichen' }),
    ).toBeNull()
  })

  it('reaktiviert die Version per inactive→draft-Transition', async () => {
    const onTransition = vi.fn().mockResolvedValue(undefined)
    const onTransitioned = vi.fn()

    renderBar('inactive', onTransition, onTransitioned)
    fireEvent.click(screen.getByRole('button', { name: 'Reaktivieren als Draft' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Reaktiviert als Entwurf.')
    })
    expect(onTransitioned).toHaveBeenCalledTimes(1)
    expect(onTransition).toHaveBeenCalledWith('draft')
  })

  it('ruft den onTransition-Callback und onTransitioned bei Aktivieren auf', async () => {
    const onTransition = vi.fn().mockResolvedValue(undefined)
    const onTransitioned = vi.fn()

    renderBar('review', onTransition, onTransitioned)
    fireEvent.click(screen.getByRole('button', { name: 'Aktivieren' }))

    await waitFor(() => {
      expect(notify.success).toHaveBeenCalledWith('Version aktiviert.')
    })
    expect(onTransitioned).toHaveBeenCalledTimes(1)
    expect(onTransition).toHaveBeenCalledWith('active')
  })

  it('zeigt Inline-Fehler mit Feldnamen bei 409 Promote-Validation-Fail', async () => {
    const onTransition = vi.fn().mockRejectedValue(
      new ApiError(409, 'Promote nicht moeglich: Pflichtfelder fehlen', {
        type: 'https://who2be.dev/errors/promote-validation-failed',
        title: 'Promote nicht moeglich: Pflichtfelder fehlen',
        status: 409,
        detail: 'Pflichtfelder muessen vor Promote ausgefuellt sein.',
        missing: ['description', 'body'],
      }),
    )

    renderBar('review', onTransition)
    fireEvent.click(screen.getByRole('button', { name: 'Aktivieren' }))

    // Button bleibt klickbar (Welle 4: kein disabled-State).
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeEnabled()
    })
    // Feldnamen sichtbar im Inline-Fehler.
    expect(await screen.findByText(/Beschreibung/)).toBeInTheDocument()
    expect(await screen.findByText(/Inhalt/)).toBeInTheDocument()
    // Kein globaler notify.error bei Promote-Validation-Fail.
    expect(notify.error).not.toHaveBeenCalled()
  })

  // Issue #391: optionaler Label-Override + Testid-Schema fuer die zentrale
  // Bar, damit Personas/Playbooks ihre historisch gewachsenen Button-Texte
  // behalten koennen, waehrend e2e/journeys.spec.ts stabil auf
  // `branch-action-<suffix>` selektiert.
  describe('Testids (branch-action-<suffix>, Schema aus BranchStatus.tsx)', () => {
    it('traegt branch-action-submit im Draft', () => {
      renderBar('draft')
      expect(screen.getByTestId('branch-action-submit')).toBe(
        screen.getByRole('button', { name: 'Zur Review einreichen' }),
      )
    })

    it('traegt branch-action-publish (nicht branch-action-promote) und branch-action-reject im Review', () => {
      renderBar('review')
      expect(screen.getByTestId('branch-action-publish')).toBe(
        screen.getByRole('button', { name: 'Aktivieren' }),
      )
      expect(screen.getByTestId('branch-action-reject')).toBe(
        screen.getByRole('button', { name: 'Ablehnen' }),
      )
      expect(screen.queryByTestId('branch-action-promote')).toBeNull()
    })

    it('traegt branch-action-reactivate im Status inactive', () => {
      renderBar('inactive')
      expect(screen.getByTestId('branch-action-reactivate')).toBe(
        screen.getByRole('button', { name: 'Reaktivieren als Draft' }),
      )
    })
  })

  describe('labels-Override', () => {
    it('ueberschreibt den Submit-Text, ohne Testid/Verhalten zu aendern', async () => {
      const onTransition = vi.fn().mockResolvedValue(undefined)
      const onTransitioned = vi.fn()
      renderBar('draft', onTransition, onTransitioned, 'admin', {
        submit: 'Draft abschliessen',
      })

      expect(screen.queryByRole('button', { name: 'Zur Review einreichen' })).toBeNull()
      const button = screen.getByRole('button', { name: 'Draft abschliessen' })
      expect(button).toBe(screen.getByTestId('branch-action-submit'))

      fireEvent.click(button)
      await waitFor(() => {
        expect(onTransitioned).toHaveBeenCalledTimes(1)
      })
      expect(onTransition).toHaveBeenCalledWith('review')
      // Toast bleibt der geteilte common:statusBar-Text — nur das Button-
      // Label wird ueberschrieben.
      expect(notify.success).toHaveBeenCalledWith('Zur Review eingereicht.')
    })

    it('ueberschreibt Promote/Reject im Review, Admin-Gate bleibt unveraendert', () => {
      renderBar('review', vi.fn().mockResolvedValue(undefined), vi.fn(), 'editor', {
        promote: 'Veroeffentlichen',
        reject: 'Zurueck zu Draft',
      })

      const publish = screen.getByRole('button', { name: 'Veroeffentlichen' })
      expect(publish).toBe(screen.getByTestId('branch-action-publish'))
      expect(publish).toBeDisabled()
      expect(publish).toHaveAttribute('title', 'Nur Admins können aktivieren')

      expect(
        screen.getByRole('button', { name: 'Zurueck zu Draft' }),
      ).toBe(screen.getByTestId('branch-action-reject'))
      expect(screen.queryByRole('button', { name: 'Ablehnen' })).toBeNull()
    })

    it('fehlende Label-Keys fallen auf die Default-Texte zurueck', () => {
      renderBar('review', vi.fn().mockResolvedValue(undefined), vi.fn(), 'admin', {
        reject: 'Zurueck zu Draft',
      })

      // Nur `reject` ist ueberschrieben — `promote` bleibt beim geteilten
      // Default-Text.
      expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Zurueck zu Draft' })).toBeInTheDocument()
    })
  })
})
