import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const sessionMock = vi.hoisted(() => ({ current: { session: null as unknown } }))

vi.mock('@/auth/session-context', () => ({
  useSession: () => sessionMock.current,
}))

import { AuthCallbackPage } from './AuthCallbackPage'

function renderPage(entry = '/auth/callback') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route path="/" element={<div>DASHBOARD</div>} />
        <Route path="/w/abc/dashboard" element={<div>WS-DASHBOARD</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  sessionMock.current = { session: null }
  window.location.hash = ''
})

describe('AuthCallbackPage', () => {
  it('leitet bei vorhandener Session auf den gehaerteten next weiter', async () => {
    sessionMock.current = { session: { access_token: 't' } }
    renderPage('/auth/callback?next=/w/abc/dashboard')

    await waitFor(() => {
      expect(screen.getByText('WS-DASHBOARD')).toBeInTheDocument()
    })
  })

  it('zeigt den Fehler aus dem URL-Hash', async () => {
    window.location.hash = '#error=access_denied&error_description=User+denied+access'
    sessionMock.current = { session: null }

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('User denied access')).toBeInTheDocument()
    })
  })

  it('zeigt waehrend der Aufloesung einen Lade-Zustand', () => {
    sessionMock.current = { session: null }
    renderPage()
    expect(screen.getByText(/Anmeldung wird abgeschlossen/i)).toBeInTheDocument()
  })
})
