import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { resetPasswordForEmail } = vi.hoisted(() => ({ resetPasswordForEmail: vi.fn() }))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { resetPasswordForEmail } },
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
    // Default: KEIN Captcha — die Bestandstests bilden damit den Zustand vor
    // Issue #539 ab; der Captcha-Block setzt den Key pro Fall.
    turnstileSiteKey: '',
  },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

import { ResetPasswordPage } from './ResetPasswordPage'

afterEach(() => {
  resetPasswordForEmail.mockReset()
  mockConfig.turnstileSiteKey = ''
  delete (window as { turnstile?: unknown }).turnstile
  document.getElementById('cf-turnstile-script')?.remove()
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

  // --- Captcha (Issue #539, Folgebefund t_c007ed1d) -------------------------
  //
  // GoTrue haengt `/recover` an dieselbe Captcha-Middleware wie `/signup`
  // (api.go:179). Der Pfad wird von der App angeboten (Login → „Passwort
  // vergessen?"), also braucht er ein Token.

  function stubTurnstile() {
    let solve: ((token: string) => void) | null = null
    const render = vi.fn((_el: HTMLElement, options: Record<string, unknown>) => {
      solve = options.callback as (token: string) => void
      return 'widget-1'
    })
    ;(window as { turnstile?: unknown }).turnstile = {
      render,
      reset: vi.fn(),
      remove: vi.fn(),
    }
    return { render, solve: (token: string) => solve?.(token) }
  }

  function renderResetPage() {
    return render(
      <MemoryRouter initialEntries={['/reset-password']}>
        <ResetPasswordPage />
      </MemoryRouter>,
    )
  }

  // Responsive-Audit (#569): Hit-Targets unterhalb `md` >= 40px (§11).
  // Gemessen lieferte `size="sm"` hier 36px. `h-10 md:h-9` hebt den
  // Phone-Fall auf 40px und behaelt die Verdichtung ab `md`.
  it('haelt den Zurueck-Link unterhalb md auf 40px Hit-Target (#569)', () => {
    renderResetPage()

    const back = screen.getByRole('link', { name: 'Zurueck zur Anmeldung' })
    expect(back.className).toContain('h-10')
    expect(back.className).toContain('md:h-9')
  })

  // Lange GoTrue-Bezeichner im ErrorAlert duerfen die Karte nicht aufblaehen.
  it('laesst lange Bezeichner in der ganzen Karte umbrechen (#569)', () => {
    renderResetPage()

    expect(document.querySelector('main')?.className).toContain('break-words')
  })

  it('schickt ohne Site-Key kein captchaToken (Verhalten wie vor #539)', async () => {
    resetPasswordForEmail.mockResolvedValue({ data: {}, error: null })
    renderResetPage()

    fireEvent.change(screen.getByLabelText('E-Mail'), { target: { value: 'agent@who2be.dev' } })
    fireEvent.click(screen.getByRole('button', { name: 'Reset-Link senden' }))

    await waitFor(() => {
      expect(resetPasswordForEmail).toHaveBeenCalledTimes(1)
    })
    expect(screen.queryByTestId('turnstile-widget')).not.toBeInTheDocument()
    expect(resetPasswordForEmail.mock.calls[0][1]).not.toHaveProperty('captchaToken')
  })

  it('sperrt den Submit bei gesetztem Site-Key und schickt danach das Token mit', async () => {
    mockConfig.turnstileSiteKey = '0x4AAAAAAA-test'
    const turnstile = stubTurnstile()
    resetPasswordForEmail.mockResolvedValue({ data: {}, error: null })
    renderResetPage()

    await waitFor(() => {
      expect(turnstile.render).toHaveBeenCalledTimes(1)
    })
    expect(turnstile.render.mock.calls[0][1]).toMatchObject({ action: 'recover' })
    expect(screen.getByRole('button', { name: 'Reset-Link senden' })).toBeDisabled()

    fireEvent.change(screen.getByLabelText('E-Mail'), { target: { value: 'agent@who2be.dev' } })
    act(() => turnstile.solve('token-recover'))
    fireEvent.click(screen.getByRole('button', { name: 'Reset-Link senden' }))

    await waitFor(() => {
      expect(resetPasswordForEmail).toHaveBeenCalledTimes(1)
    })
    expect(resetPasswordForEmail.mock.calls[0][1]).toMatchObject({
      captchaToken: 'token-recover',
    })
  })

  it('zeigt bei captcha_failed die verstaendliche Meldung und stellt neu', async () => {
    mockConfig.turnstileSiteKey = '0x4AAAAAAA-test'
    const turnstile = stubTurnstile()
    resetPasswordForEmail.mockResolvedValue({
      data: null,
      error: Object.assign(
        new Error('captcha protection: request disallowed (invalid-input-response)'),
        { code: 'captcha_failed' },
      ),
    })
    renderResetPage()

    await waitFor(() => {
      expect(turnstile.render).toHaveBeenCalled()
    })
    fireEvent.change(screen.getByLabelText('E-Mail'), { target: { value: 'agent@who2be.dev' } })
    act(() => turnstile.solve('token-tot'))
    fireEvent.click(screen.getByRole('button', { name: 'Reset-Link senden' }))

    expect(
      await screen.findByText('Die Bot-Pruefung ist fehlgeschlagen. Bitte versuche es noch einmal.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/request disallowed/i)).not.toBeInTheDocument()
    await waitFor(() => {
      expect(turnstile.render).toHaveBeenCalledTimes(2)
    })
  })
})
