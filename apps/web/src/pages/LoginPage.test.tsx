import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

const { signInWithPassword } = vi.hoisted(() => ({ signInWithPassword: vi.fn() }))

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: { signInWithPassword, signOut: vi.fn() },
  },
}))

import { SessionProvider } from '../auth/SessionProvider'
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
