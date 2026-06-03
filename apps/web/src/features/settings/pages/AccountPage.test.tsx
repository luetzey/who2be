import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { updateUser, signOut } = vi.hoisted(() => ({
  updateUser: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { updateUser, signOut } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// ThemeToggle braucht den ThemeProvider-Context; fuer den AccountPage-Test
// irrelevant — durch einen Platzhalter ersetzt.
vi.mock('@/components/ui/theme-toggle', () => ({
  ThemeToggle: () => <div>theme</div>,
}))

vi.mock('@/auth/session-context', () => ({
  useSession: () => ({
    session: {
      access_token: 't',
      user: { id: 'user-1', email: 'agent@who2be.dev', user_metadata: { display_name: 'Agent' } },
    },
    me: { user_id: 'user-1', has_password: true },
  }),
}))

import { AccountPage } from './AccountPage'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/w/abc/settings/account']}>
      <Routes>
        <Route path="/w/abc/settings/account" element={<AccountPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  updateUser.mockReset()
  signOut.mockReset()
})

describe('AccountPage', () => {
  it('aendert das Passwort ueber updateUser', async () => {
    updateUser.mockResolvedValue({ data: {}, error: null })
    renderPage()

    fireEvent.change(screen.getByLabelText('Neues Passwort'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort aendern' }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ password: 'neues-passwort-1' })
    })
  })

  it('aendert die E-Mail und loest eine Re-Confirm-Mail aus', async () => {
    updateUser.mockResolvedValue({ data: {}, error: null })
    renderPage()

    fireEvent.change(screen.getByLabelText('E-Mail aendern'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'E-Mail aendern' }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ email: 'neu@who2be.dev' })
    })
  })

  it('meldet ueberall ab und navigiert zum Login', async () => {
    signOut.mockResolvedValue({ error: null })
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Überall abmelden' }))

    await waitFor(() => {
      expect(signOut).toHaveBeenCalledWith({ scope: 'global' })
    })
    await waitFor(() => {
      expect(screen.getByText('LOGIN')).toBeInTheDocument()
    })
  })
})
