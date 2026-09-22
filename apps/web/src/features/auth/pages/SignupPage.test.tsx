import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { signUp, signInWithOAuth } = vi.hoisted(() => ({
  signUp: vi.fn(),
  signInWithOAuth: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { signUp, signInWithOAuth } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/session-context', () => ({
  useSession: () => ({ session: null, me: null }),
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
    // Default in den Tests: KEIN Captcha (Leerstring), damit die
    // Bestandstests exakt den Zustand vor #539 abbilden. Die Captcha-Tests
    // setzen den Key pro Fall und `afterEach` raeumt ihn wieder ab.
    turnstileSiteKey: '',
  },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

import { SignupPage } from './SignupPage'

function renderPage(entry = '/signup') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/" element={<div>DASHBOARD</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

function acceptConsent() {
  // Checkbox ist via <Label htmlFor> assoziiert → ueber den Label-Text greifbar.
  fireEvent.click(screen.getByLabelText(/Ich akzeptiere die/))
}

function fillForm({ consent = true }: { consent?: boolean } = {}) {
  fireEvent.change(screen.getByLabelText('E-Mail'), { target: { value: 'neu@who2be.dev' } })
  fireEvent.change(screen.getByLabelText('Passwort'), { target: { value: 'streng-geheim-1' } })
  fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
    target: { value: 'streng-geheim-1' },
  })
  if (consent) {
    acceptConsent()
  }
}

afterEach(() => {
  signUp.mockReset()
  signInWithOAuth.mockReset()
  mockConfig.signupDisabled = false
  mockConfig.launchMode = 'open'
  mockConfig.launchContact = ''
  mockConfig.turnstileSiteKey = ''
  delete (window as { turnstile?: unknown }).turnstile
  document.getElementById('cf-turnstile-script')?.remove()
})

describe('SignupPage', () => {
  it('navigiert nach Autoconfirm-Signup direkt weiter (Session vorhanden)', async () => {
    signUp.mockResolvedValue({ data: { session: { access_token: 't' } }, error: null })

    renderPage()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))

    await waitFor(() => {
      expect(screen.getByText('DASHBOARD')).toBeInTheDocument()
    })
    expect(signUp).toHaveBeenCalledTimes(1)
  })

  it('zeigt den Confirm-Mail-Hinweis, wenn keine Session zurueckkommt', async () => {
    signUp.mockResolvedValue({ data: { session: null }, error: null })

    renderPage()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))

    await waitFor(() => {
      expect(screen.getByText(/Bestaetigungs-Link/i)).toBeInTheDocument()
    })
  })

  it('leitet bei deaktiviertem Signup auf /login um (kein Formular)', () => {
    mockConfig.signupDisabled = true

    render(
      <MemoryRouter initialEntries={['/signup']}>
        <Routes>
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/login" element={<div>LOGIN</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('LOGIN')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Konto erstellen' })).not.toBeInTheDocument()
  })

  it('zeigt im "coming_soon"-Launch-Modus die Hinweisseite statt des Formulars', () => {
    mockConfig.launchMode = 'coming_soon'

    renderPage()

    expect(
      screen.getByRole('heading', { name: 'Wir arbeiten noch an Who2Be — bald verfügbar.' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Konto erstellen' })).not.toBeInTheDocument()
  })

  it('zeigt die Hinweisseite auch, wenn der Altschalter zusaetzlich gesetzt ist', () => {
    mockConfig.launchMode = 'coming_soon'
    mockConfig.signupDisabled = true

    renderPage()

    expect(
      screen.getByRole('heading', { name: 'Wir arbeiten noch an Who2Be — bald verfügbar.' }),
    ).toBeInTheDocument()
  })

  it('blockt Signup ohne Consent (Submit + OAuth deaktiviert)', () => {
    renderPage()
    fillForm({ consent: false })

    const submit = screen.getByRole('button', { name: 'Konto erstellen' })
    const google = screen.getByRole('button', { name: 'Mit Google anmelden' })
    expect(submit).toBeDisabled()
    expect(google).toBeDisabled()

    fireEvent.click(submit)
    expect(signUp).not.toHaveBeenCalled()
  })

  it('startet den OAuth-Flow ueber den Google-Button (nach Consent)', async () => {
    signInWithOAuth.mockResolvedValue({ data: {}, error: null })

    renderPage()
    acceptConsent()
    fireEvent.click(screen.getByRole('button', { name: 'Mit Google anmelden' }))

    await waitFor(() => {
      expect(signInWithOAuth).toHaveBeenCalledWith(
        expect.objectContaining({ provider: 'google' }),
      )
    })
  })

  // --- Captcha / Cloudflare Turnstile (Issue #539) -------------------------
  //
  // Das echte Widget laedt ein Script von Cloudflare. In den Tests wird
  // `window.turnstile` gestubbt, BEVOR gerendert wird — dann nimmt
  // `loadTurnstileScript` den Kurzschluss und es geht kein Request raus.
  // `solve` erlaubt es, den Callback des Widgets von aussen auszuloesen.
  function stubTurnstile() {
    let solve: ((token: string) => void) | null = null
    let expire: (() => void) | null = null
    const render = vi.fn((_el: HTMLElement, options: Record<string, unknown>) => {
      solve = options.callback as (token: string) => void
      expire = options['expired-callback'] as () => void
      return 'widget-1'
    })
    const api = { render, reset: vi.fn(), remove: vi.fn() }
    ;(window as { turnstile?: unknown }).turnstile = api
    return {
      api,
      solve: (token: string) => solve?.(token),
      expire: () => expire?.(),
    }
  }

  it('rendert ohne Site-Key kein Widget und schickt keinen captchaToken (Verhalten wie vor #539)', async () => {
    signUp.mockResolvedValue({ data: { session: { access_token: 't' } }, error: null })

    renderPage()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))

    await waitFor(() => {
      expect(signUp).toHaveBeenCalledTimes(1)
    })
    expect(screen.queryByTestId('turnstile-widget')).not.toBeInTheDocument()
    expect(signUp.mock.calls[0][0].options).not.toHaveProperty('captchaToken')
  })

  it('sperrt den Submit bei gesetztem Site-Key, bis das Captcha geloest ist', async () => {
    mockConfig.turnstileSiteKey = '0x4AAAAAAA-test'
    const turnstile = stubTurnstile()

    renderPage()
    fillForm()

    await waitFor(() => {
      expect(turnstile.api.render).toHaveBeenCalledTimes(1)
    })
    expect(screen.getByRole('button', { name: 'Konto erstellen' })).toBeDisabled()
    expect(screen.getByText(/kein Bot bist/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))
    expect(signUp).not.toHaveBeenCalled()
  })

  it('schickt das Token nach geloestem Captcha am signUp mit', async () => {
    mockConfig.turnstileSiteKey = '0x4AAAAAAA-test'
    const turnstile = stubTurnstile()
    signUp.mockResolvedValue({ data: { session: { access_token: 't' } }, error: null })

    renderPage()
    fillForm()
    await waitFor(() => {
      expect(turnstile.api.render).toHaveBeenCalled()
    })

    act(() => turnstile.solve('token-abc'))
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))
    await waitFor(() => {
      expect(signUp).toHaveBeenCalledTimes(1)
    })
    expect(signUp.mock.calls[0][0].options).toMatchObject({
      captchaToken: 'token-abc',
    })
  })

  it('sperrt den Submit wieder, wenn das Token ablaeuft', async () => {
    mockConfig.turnstileSiteKey = '0x4AAAAAAA-test'
    const turnstile = stubTurnstile()

    renderPage()
    fillForm()
    await waitFor(() => {
      expect(turnstile.api.render).toHaveBeenCalled()
    })

    act(() => turnstile.solve('token-abc'))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Konto erstellen' })).toBeEnabled()
    })

    act(() => turnstile.expire())
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Konto erstellen' })).toBeDisabled()
    })
  })

  it('zeigt bei captcha_failed eine verstaendliche Meldung statt des GoTrue-Texts', async () => {
    mockConfig.turnstileSiteKey = '0x4AAAAAAA-test'
    const turnstile = stubTurnstile()
    // Wortlaut + Code aus GoTrue v2.158.1 (middleware.go:184, errorcodes.go:44).
    signUp.mockResolvedValue({
      data: { session: null },
      error: Object.assign(
        new Error('captcha protection: request disallowed (invalid-input-response)'),
        { code: 'captcha_failed' },
      ),
    })

    renderPage()
    fillForm()
    await waitFor(() => {
      expect(turnstile.api.render).toHaveBeenCalled()
    })

    act(() => turnstile.solve('token-abc'))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Konto erstellen' })).toBeEnabled()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))

    await waitFor(() => {
      expect(screen.getByText('Die Bot-Pruefung ist fehlgeschlagen. Bitte versuche es noch einmal.')).toBeInTheDocument()
    })
    expect(screen.queryByText(/request disallowed/i)).not.toBeInTheDocument()
    // Verbrauchtes Token verworfen → Submit wieder gesperrt, Widget neu
    // gerendert (zweiter render-Aufruf durch den key-Wechsel).
    expect(screen.getByRole('button', { name: 'Konto erstellen' })).toBeDisabled()
    await waitFor(() => {
      expect(turnstile.api.render).toHaveBeenCalledTimes(2)
    })
  })

  it('laesst andere GoTrue-Fehler im Wortlaut stehen', async () => {
    signUp.mockResolvedValue({
      data: { session: null },
      error: new Error('User already registered'),
    })

    renderPage()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Konto erstellen' }))

    await waitFor(() => {
      expect(screen.getByText('User already registered')).toBeInTheDocument()
    })
  })
})
