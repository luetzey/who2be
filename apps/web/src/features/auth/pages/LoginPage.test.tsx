import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

const { signInWithPassword, getSession, onAuthStateChange } = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  getSession: vi.fn(async () => ({ data: { session: null }, error: null })),
  onAuthStateChange: vi.fn(() => ({
    data: { subscription: { unsubscribe: vi.fn() } },
  })),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: { signInWithPassword, signOut: vi.fn(), getSession, onAuthStateChange },
  },
}))

import { SessionProvider } from '@/auth/SessionProvider'
import { sanitizeNext } from '@/features/auth/lib/sanitize-next'
import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
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
