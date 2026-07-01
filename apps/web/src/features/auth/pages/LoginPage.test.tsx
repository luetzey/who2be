import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const {
  signInWithPassword,
  getSession,
  onAuthStateChange,
  getAuthenticatorAssuranceLevel,
  listFactors,
  challenge,
  verify,
} = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
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
  supabase: {
    auth: {
      signInWithPassword,
      signOut: vi.fn(),
      getSession,
      onAuthStateChange,
      mfa: { getAuthenticatorAssuranceLevel, listFactors, challenge, verify },
    },
  },
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

import { SessionProvider } from '@/auth/SessionProvider'
import { sanitizeNext } from '@/features/auth/lib/sanitize-next'
import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  afterEach(() => {
    mockConfig.signupDisabled = false
  })

  it('versteckt den Registrieren-Link bei deaktiviertem Signup', () => {
    mockConfig.signupDisabled = true
    render(
      <BrowserRouter>
        <SessionProvider>
          <LoginPage />
        </SessionProvider>
      </BrowserRouter>,
    )

    expect(document.querySelector('a[href*="/signup"]')).toBeNull()
  })

  it('ruft signInWithPassword mit den eingegebenen Daten', async () => {
    signInWithPassword.mockResolvedValue({ data: { session: null }, error: null })
    render(
      <BrowserRouter>
        <SessionProvider>
          <LoginPage />
        </SessionProvider>
      </BrowserRouter>,
    )

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    fireEvent.change(screen.getByLabelText('Passwort'), {
      target: { value: 'streng-geheim' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))

    await waitFor(() => {
      expect(signInWithPassword).toHaveBeenCalledWith({
        email: 'agent@who2be.dev',
        password: 'streng-geheim',
      })
    })
  })

  it('fordert bei faelligem zweiten Faktor den TOTP-Code an und verifiziert ihn', async () => {
    signInWithPassword.mockResolvedValue({ data: { session: null }, error: null })
    // Step-up faellig: Passwort ok, aber Session ist erst aal1.
    getAuthenticatorAssuranceLevel.mockResolvedValue({
      data: { currentLevel: 'aal1', nextLevel: 'aal2' },
      error: null,
    })

    render(
      <BrowserRouter>
        <SessionProvider>
          <LoginPage />
        </SessionProvider>
      </BrowserRouter>,
    )

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'admin@who2be.dev' },
    })
    fireEvent.change(screen.getByLabelText('Passwort'), {
      target: { value: 'streng-geheim' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))

    // Zweite Stufe: Code-Feld erscheint.
    const codeField = await screen.findByLabelText('Code')
    fireEvent.change(codeField, { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestaetigen' }))

    await waitFor(() => {
      expect(challenge).toHaveBeenCalledWith({ factorId: 'f1' })
      expect(verify).toHaveBeenCalledWith({ factorId: 'f1', challengeId: 'ch1', code: '123456' })
    })
  })
})

describe('sanitizeNext', () => {
  // Open-Redirect-Schutz: nur In-App-Pfade duerfen den Login-Redirect lenken.
  it('akzeptiert In-App-Pfade', () => {
    expect(sanitizeNext('/dashboard')).toBe('/dashboard')
    expect(sanitizeNext('/invitations/abc/accept?via=magic')).toBe(
      '/invitations/abc/accept?via=magic',
    )
  })

  it('ignoriert Protocol-Relative-URLs wie //evil.com', () => {
    expect(sanitizeNext('//evil.com')).toBe('/')
    expect(sanitizeNext('//evil.com/path')).toBe('/')
  })

  it('ignoriert Backslash-Tricks wie /\\evil.com', () => {
    // Browser normalisieren `\` teils zu `/` → protocol-relative Umgehung.
    expect(sanitizeNext('/\\evil.com')).toBe('/')
    expect(sanitizeNext('/\\/evil.com')).toBe('/')
    expect(sanitizeNext('/path\\with\\backslash')).toBe('/')
  })

  it('ignoriert vollqualifizierte URLs', () => {
    expect(sanitizeNext('https://evil.com')).toBe('/')
    expect(sanitizeNext('http://evil.com/path')).toBe('/')
    // Selbst ein Pfad, der ein `://` enthaelt, wird verworfen.
    expect(sanitizeNext('/redirect?to=https://evil.com')).toBe('/')
  })

  it('ignoriert relative Pfade und leere Werte', () => {
    expect(sanitizeNext('dashboard')).toBe('/')
    expect(sanitizeNext('')).toBe('/')
    expect(sanitizeNext(null)).toBe('/')
  })
})
