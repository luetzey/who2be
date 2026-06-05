import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { updateUser, signOut, exportMyData, deleteAccount } = vi.hoisted(() => ({
  updateUser: vi.fn(),
  signOut: vi.fn(),
  exportMyData: vi.fn(),
  deleteAccount: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { updateUser, signOut } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// Track O: Export-/Konto-Löschen-Sektionen nutzen useApi — hier gestubbt, damit
// der Test ohne AuthTokenProvider auskommt.
vi.mock('@/api/useApi', () => ({
  useApi: () => ({ exportMyData, deleteAccount }),
}))

// ThemeToggle braucht den ThemeProvider-Context; fuer den AccountPage-Test
// irrelevant — durch einen Platzhalter ersetzt.
vi.mock('@/components/ui/theme-toggle', () => ({
  ThemeToggle: () => <div>theme</div>,
}))

// MfaSection spricht die GoTrue-`/factors`-API (supabase.auth.mfa) beim Mount
// an — hier irrelevant und durch einen Platzhalter ersetzt. Eigene Tests in
// MfaSection.test.tsx / MfaSection.a11y.test.tsx.
vi.mock('../components/MfaSection', () => ({
  MfaSection: () => <div>mfa</div>,
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
  exportMyData.mockReset()
  deleteAccount.mockReset()
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

  it('exportiert die Daten ueber die API', async () => {
    exportMyData.mockResolvedValue({ user_id: 'user-1', organizations: [] })
    // jsdom kennt createObjectURL nicht — stubben.
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Daten exportieren' }))

    await waitFor(() => {
      expect(exportMyData).toHaveBeenCalledTimes(1)
    })
  })

  it('loescht das Konto erst nach E-Mail-Bestaetigung und meldet ab', async () => {
    deleteAccount.mockResolvedValue({ purge_after: '2026-07-03T00:00:00Z' })
    signOut.mockResolvedValue({ error: null })
    renderPage()

    // Dialog oeffnen.
    fireEvent.click(screen.getByRole('button', { name: 'Konto löschen' }))

    // Ohne passende E-Mail bleibt der Bestaetigen-Button deaktiviert.
    const confirmButton = screen.getByRole('button', { name: 'Konto endgültig löschen' })
    expect(confirmButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    expect(confirmButton).toBeEnabled()
    fireEvent.click(confirmButton)

    await waitFor(() => {
      expect(deleteAccount).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(signOut).toHaveBeenCalledWith({ scope: 'global' })
    })
  })
})
