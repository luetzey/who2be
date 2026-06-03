import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { signUp, signInWithOAuth } = vi.hoisted(() => ({
  signUp: vi.fn(),
  signInWithOAuth: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { signUp, signInWithOAuth } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/session-context', () => ({
  useSession: () => ({ session: null, me: null }),
}))

import { SignupPage } from './SignupPage'

function renderPage(entry = '/signup') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/" element={<div>DASHBOARD</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

function fillForm() {
  fireEvent.change(screen.getByLabelText('E-Mail'), { target: { value: 'neu@who2be.dev' } })
  fireEvent.change(screen.getByLabelText('Passwort'), { target: { value: 'streng-geheim-1' } })
  fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
    target: { value: 'streng-geheim-1' },
  })
}

afterEach(() => {
  signUp.mockReset()
  signInWithOAuth.mockReset()
})

describe('SignupPage', () => {
  it('navigiert nach Autoconfirm-Signup direkt weiter (Session vorhanden)', async () => {
    signUp.mockResolvedValue({ data: { session: { access_token: 't' } }, error: null })

    renderPage()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD')).toBeInTheDocument()
    })
    expect(signUp).toHaveBeenCalledTimes(1)
  })

  it('zeigt den Confirm-Mail-Hinweis, wenn keine Session zurueckkommt', async () => {
    signUp.mockResolvedValue({ data: { session: null }, error: null })

    renderPage()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))

    await waitFor(() => {
      expect(screen.getByText(/Bestaetigungs-Link/i)).toBeInTheDocument()
    })
  })

  it('startet den OAuth-Flow ueber den Google-Button', async () => {
    signInWithOAuth.mockResolvedValue({ data: {}, error: null })

    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Mit Google anmelden' }))

    await waitFor(() => {
      expect(signInWithOAuth).toHaveBeenCalledWith(
        expect.objectContaining({ provider: 'google' }),
      )
    })
  })
})
