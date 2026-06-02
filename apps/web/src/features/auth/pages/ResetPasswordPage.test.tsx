import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { resetPasswordForEmail } = vi.hoisted(() => ({ resetPasswordForEmail: vi.fn() }))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { resetPasswordForEmail } },
}))

import { ResetPasswordPage } from './ResetPasswordPage'

afterEach(() => {
  resetPasswordForEmail.mockReset()
})

describe('ResetPasswordPage', () => {
  it('schickt die Recovery-Mail mit haertendem redirectTo auf die Set-Password-Seite', async () => {
    resetPasswordForEmail.mockResolvedValue({ data: {}, error: null })

    render(
      <MemoryRouter initialEntries={['/reset-password']}>
        <ResetPasswordPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reset-Link senden' }))

    await waitFor(() => {
      expect(resetPasswordForEmail).toHaveBeenCalledTimes(1)
    })
    const [emailArg, options] = resetPasswordForEmail.mock.calls[0]
    expect(emailArg).toBe('agent@who2be.dev')
    expect(options.redirectTo).toContain('/onboarding/set-password')
    // Erfolgs-Zustand erscheint.
    expect(screen.getByText(/Mail mit Reset-Link unterwegs/i)).toBeInTheDocument()
  })

  it('bettet einen gehaerteten next-Pfad in die redirectTo-URL ein', async () => {
    resetPasswordForEmail.mockResolvedValue({ data: {}, error: null })

    render(
      <MemoryRouter initialEntries={['/reset-password?next=//evil.com']}>
        <ResetPasswordPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reset-Link senden' }))

    await waitFor(() => {
      expect(resetPasswordForEmail).toHaveBeenCalledTimes(1)
    })
    // Open-Redirect-Versuch wird verworfen: kein evil.com in der redirectTo.
    const options = resetPasswordForEmail.mock.calls[0][1]
    expect(options.redirectTo).not.toContain('evil.com')
  })

  it('zeigt den GoTrue-Fehler', async () => {
    resetPasswordForEmail.mockResolvedValue({ data: {}, error: { message: 'rate limit' } })

    render(
      <MemoryRouter initialEntries={['/reset-password']}>
        <ResetPasswordPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reset-Link senden' }))

    await waitFor(() => {
      expect(screen.getByText('rate limit')).toBeInTheDocument()
    })
  })
})
