import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { notify } from '@/lib/feedback'

const { updateUser } = vi.hoisted(() => ({ updateUser: vi.fn() }))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { updateUser } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

import { SetPasswordPage } from './SetPasswordPage'

function AcceptMarker() {
  const params = useParams<{ token: string }>()
  return <div>ACCEPT token={params.token}</div>
}

function DashboardMarker() {
  return <div>DASHBOARD</div>
}

function renderPage(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/onboarding/set-password" element={<SetPasswordPage />} />
        <Route path="/invitations/:token/accept" element={<AcceptMarker />} />
        <Route path="/" element={<DashboardMarker />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  updateUser.mockReset()
  vi.mocked(notify.success).mockClear()
})

describe('SetPasswordPage', () => {
  it('setzt das Passwort und navigiert auf `next` zurueck', async () => {
    updateUser.mockResolvedValue({ data: {}, error: null })

    renderPage('/onboarding/set-password?next=/invitations/tok-7/accept?via=magic')

    fireEvent.change(screen.getByLabelText('Neues Passwort'), {
      target: { value: 'streng-geheim-123' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'streng-geheim-123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort setzen' }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ password: 'streng-geheim-123' })
    })
    await waitFor(() => {
      expect(screen.getByText('ACCEPT token=tok-7')).toBeInTheDocument()
    })
    expect(notify.success).toHaveBeenCalledWith('Passwort gesetzt.')
  })

  it('zeigt den GoTrue-Fehler bei updateUser-Error', async () => {
    updateUser.mockResolvedValue({ data: {}, error: { message: 'Password too weak' } })

    renderPage('/onboarding/set-password')

    fireEvent.change(screen.getByLabelText('Neues Passwort'), {
      target: { value: 'streng-geheim-123' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'streng-geheim-123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort setzen' }))

    await waitFor(() => {
      expect(screen.getByText('Password too weak')).toBeInTheDocument()
    })
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('blockt Submit, wenn Passwoerter nicht uebereinstimmen', async () => {
    renderPage('/onboarding/set-password')

    fireEvent.change(screen.getByLabelText('Neues Passwort'), {
      target: { value: 'streng-geheim-123' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'tippfehler' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort setzen' }))

    await waitFor(() => {
      expect(screen.getByText('Passwoerter stimmen nicht ueberein.')).toBeInTheDocument()
    })
    expect(updateUser).not.toHaveBeenCalled()
  })
})
