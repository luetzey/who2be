import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Cloud-Auth (Owner-Entscheidung 2026-09-24): In der Cloud-Edition meldet man
 * sich ausschliesslich ueber externe Provider an — das Passwortformular ist
 * weder sichtbar noch per Direktlink erreichbar. Im Self-Hosting bleibt alles
 * unveraendert.
 *
 * **Beide Richtungen werden geprueft**, und zwar in derselben Datei: ein Test,
 * der nur die Cloud abdeckt, wuerde nicht auffallen, wenn das Gate versehentlich
 * immer `false` liefert und damit auch das Self-Hosting kastriert.
 *
 * Warum ueber `../lib/password-auth` gemockt wird und nicht ueber
 * `__CLOUD_BUILD__`: die Konstante ist ein Vite-`define`-Literal (ADR-0029,
 * `vite.config.ts`) und existiert zur Testlaufzeit nur als fest ersetzter Wert
 * — sie laesst sich nicht stubben. Das Gate-Modul ist die eine Stelle, an der
 * sie gelesen wird, und damit der Angriffspunkt fuer beide Richtungen.
 */

const { isPasswordAuthEnabled } = vi.hoisted(() => ({
  isPasswordAuthEnabled: vi.fn(() => true),
}))

vi.mock('../lib/password-auth', () => ({ isPasswordAuthEnabled }))

const { signInWithPassword, signUp, getSession, onAuthStateChange, signInWithOAuth } = vi.hoisted(
  () => ({
    signInWithPassword: vi.fn(),
    signUp: vi.fn(),
    signInWithOAuth: vi.fn(async () => ({ error: null })),
    getSession: vi.fn(async () => ({ data: { session: null }, error: null })),
    onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
  }),
)

vi.mock('@/lib/supabase', () => ({
  syncStorageBackendForThisTab: vi.fn(),
  supabase: {
    auth: {
      signInWithPassword,
      signUp,
      signInWithOAuth,
      signOut: vi.fn(),
      getSession,
      onAuthStateChange,
      resend: vi.fn(),
      resetPasswordForEmail: vi.fn(),
      mfa: {
        getAuthenticatorAssuranceLevel: vi.fn(async () => ({
          data: { currentLevel: 'aal1', nextLevel: 'aal1' },
          error: null,
        })),
        listFactors: vi.fn(),
        challenge: vi.fn(),
        verify: vi.fn(),
      },
    },
  },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/client', () => ({
  fetchMe: vi.fn(async () => ({
    user_id: 'u1',
    default_workspace_id: null,
    organizations: [],
    has_password: true,
  })),
}))

const { mockConfig } = vi.hoisted(() => ({
  mockConfig: {
    apiBaseUrl: 'http://localhost:8000',
    mcpUrl: 'http://localhost:8000/mcp',
    supabaseUrl: 'http://localhost:54321',
    supabaseAnonKey: 'anon',
    signupDisabled: false,
    launchMode: 'open' as 'open' | 'coming_soon',
    launchContact: '',
    sessionMaxAgeHours: 12,
  },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

import { SessionProvider } from '@/auth/SessionProvider'

import { LoginPage } from './LoginPage'
import { ResetPasswordPage } from './ResetPasswordPage'
import { SignupPage } from './SignupPage'

/** Rendert eine Auth-Seite unter ihrer echten Route, inkl. /login als Ziel. */
function renderAt(path: string) {
  return render(
    <SessionProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  )
}

/** Passwortfelder im gerenderten Baum — der eigentliche Prueffall. */
function passwordInputs(): Element[] {
  return Array.from(document.querySelectorAll('input[type="password"]'))
}

beforeEach(() => {
  isPasswordAuthEnabled.mockReturnValue(true)
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('Cloud-Edition: nur externe Provider', () => {
  beforeEach(() => {
    isPasswordAuthEnabled.mockReturnValue(false)
  })

  it('Login zeigt kein Passwortfeld, aber die Provider-Schaltflaechen', () => {
    renderAt('/login')

    expect(passwordInputs()).toHaveLength(0)
    expect(screen.queryByLabelText('E-Mail')).toBeNull()
    expect(screen.getByRole('button', { name: /Google/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /GitHub/ })).toBeInTheDocument()
  })

  it('Login zeigt weder "Passwort vergessen" noch "Angemeldet bleiben"', () => {
    renderAt('/login')

    expect(document.querySelector('a[href*="/reset-password"]')).toBeNull()
    expect(screen.queryByText(/Angemeldet bleiben/)).toBeNull()
  })

  it('Registrierung zeigt kein Passwortfeld, aber die Einwilligung bleibt Pflicht', () => {
    renderAt('/signup')

    expect(passwordInputs()).toHaveLength(0)
    // Der Consent-Gate ist der Grund, warum /signup in der Cloud NICHT auf
    // /login umgeleitet wird — er muss erhalten bleiben.
    expect(screen.getByLabelText(/AGB/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Google/ })).toBeDisabled()
  })

  it('Passwort-Reset ist per Direktlink nicht erreichbar — Weiterleitung auf /login', () => {
    renderAt('/reset-password')

    // Die Login-Seite hat die Provider-Schaltflaechen, die Reset-Seite nicht:
    // beides zusammen belegt, dass wirklich umgeleitet wurde.
    expect(screen.getByRole('button', { name: /Google/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reset-Link senden' })).toBeNull()
  })
})

describe('Self-Hosting: Passwort-Login unveraendert', () => {
  beforeEach(() => {
    isPasswordAuthEnabled.mockReturnValue(true)
  })

  it('Login zeigt E-Mail, Passwort, "Angemeldet bleiben" und die Provider', () => {
    renderAt('/login')

    expect(passwordInputs()).toHaveLength(1)
    expect(screen.getByLabelText('E-Mail')).toBeInTheDocument()
    expect(screen.getByText(/Angemeldet bleiben/)).toBeInTheDocument()
    expect(document.querySelector('a[href*="/reset-password"]')).not.toBeNull()
    expect(screen.getByRole('button', { name: /Google/ })).toBeInTheDocument()
  })

  it('Registrierung zeigt Passwort und Wiederholung', () => {
    renderAt('/signup')

    expect(passwordInputs()).toHaveLength(2)
    expect(screen.getByLabelText('E-Mail')).toBeInTheDocument()
  })

  it('Passwort-Reset bleibt erreichbar', () => {
    renderAt('/reset-password')

    expect(screen.getByRole('button', { name: 'Reset-Link senden' })).toBeInTheDocument()
  })
})
