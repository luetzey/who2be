import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'

const {
  signInWithPassword,
  getSession,
  onAuthStateChange,
  getAuthenticatorAssuranceLevel,
  listFactors,
  challenge,
  verify,
} = vi.hoisted(() => ({
  signInWithPassword: vi.fn(async () => ({ data: { session: null }, error: null })),
  getSession: vi.fn(async () => ({ data: { session: null }, error: null })),
  onAuthStateChange: vi.fn(() => ({
    data: { subscription: { unsubscribe: vi.fn() } },
  })),
  // Default: kein Step-up faellig.
  getAuthenticatorAssuranceLevel: vi.fn(async () => ({
    data: { currentLevel: 'aal1', nextLevel: 'aal1' },
    error: null,
  })),
  listFactors: vi.fn(async () => ({ data: { all: [], totp: [{ id: 'f1' }] }, error: null })),
  challenge: vi.fn(async () => ({ data: { id: 'ch1' }, error: null })),
  verify: vi.fn(async () => ({ data: {}, error: null })),
}))

vi.mock('@/lib/supabase', () => ({
  // Muss jeden Export von `lib/supabase` fuehren, den der Produktivcode
  // aufruft: Vitests Mock-Proxy wirft schon beim LESEN einer hier
  // fehlenden Property, optional chaining faengt das nicht ab.
  syncStorageBackendForThisTab: vi.fn(),
  supabase: {
    auth: {
      signInWithPassword,
      signOut: vi.fn(),
      getSession,
      onAuthStateChange,
      resend: vi.fn(),
      mfa: { getAuthenticatorAssuranceLevel, listFactors, challenge, verify },
    },
  },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

import { SessionProvider } from '@/auth/SessionProvider'

import { LoginPage } from './LoginPage'

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <SessionProvider>
        <LoginPage />
      </SessionProvider>
    </MemoryRouter>,
  )
}

describe('LoginPage (a11y)', () => {
  it('hat keine axe-Violations im Passwort-Formular', async () => {
    const { container } = renderLogin()
    expect(await screen.findByRole('button', { name: 'Anmelden' })).toBeInTheDocument()

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('hat keine axe-Violations im MFA-Step-up-Schritt', async () => {
    // Step-up faellig: nach dem Passwort-Login erscheint das TOTP-Feld.
    getAuthenticatorAssuranceLevel.mockResolvedValue({
      data: { currentLevel: 'aal1', nextLevel: 'aal2' },
      error: null,
    })
    const { container } = renderLogin()

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'admin@who2be.dev' },
    })
    fireEvent.change(screen.getByLabelText('Passwort'), {
      target: { value: 'streng-geheim' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))

    expect(await screen.findByLabelText('Code')).toBeInTheDocument()

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
