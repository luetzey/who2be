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

const { mockConfig } = vi.hoisted(() => ({
  mockConfig: {
    apiBaseUrl: 'http://localhost:8000',
    mcpUrl: 'http://localhost:8000/mcp',
    supabaseUrl: 'http://localhost:54321',
    supabaseAnonKey: 'anon',
    signupDisabled: false,
  },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

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

function acceptConsent() {
  // Checkbox ist via <Label htmlFor> assoziiert → ueber den Label-Text greifbar.
  fireEvent.click(screen.getByLabelText(/Ich akzeptiere die/))
}

function fillForm({ consent = true }: { consent?: boolean } = {}) {
  fireEvent.change(screen.getByLabelText('E-Mail'), { target: { value: 'neu@who2be.dev' } })
  fireEvent.change(screen.getByLabelText('Passwort'), { target: { value: 'streng-geheim-1' } })
  fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
    target: { value: 'streng-geheim-1' },
  })
  if (consent) {
    acceptConsent()
  }
}

afterEach(() => {
  signUp.mockReset()
  signInWithOAuth.mockReset()
  mockConfig.signupDisabled = false
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

  it('leitet bei deaktiviertem Signup auf /login um (kein Formular)', () => {
    mockConfig.signupDisabled = true

    render(
      <MemoryRouter initialEntries={['/signup']}>
        <Routes>
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/login" element={<div>LOGIN</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('LOGIN')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Konto erstellen' })).not.toBeInTheDocument()
  })

  it('blockt Signup ohne Consent (Submit + OAuth deaktiviert)', () => {
    renderPage()
    fillForm({ consent: false })

    const submit = screen.getByRole('button', { name: 'Konto erstellen' })
    const google = screen.getByRole('button', { name: 'Mit Google anmelden' })
    expect(submit).toBeDisabled()
    expect(google).toBeDisabled()

    fireEvent.click(submit)
    expect(signUp).not.toHaveBeenCalled()
  })

  it('startet den OAuth-Flow ueber den Google-Button (nach Consent)', async () => {
    signInWithOAuth.mockResolvedValue({ data: {}, error: null })

    renderPage()
    acceptConsent()
    fireEvent.click(screen.getByRole('button', { name: 'Mit Google anmelden' }))

    await waitFor(() => {
      expect(signInWithOAuth).toHaveBeenCalledWith(
        expect.objectContaining({ provider: 'google' }),
      )
    })
  })
})
