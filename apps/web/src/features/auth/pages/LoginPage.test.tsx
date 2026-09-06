import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
  signInWithPassword,
  getSession,
  onAuthStateChange,
  getAuthenticatorAssuranceLevel,
  listFactors,
  challenge,
  verify,
  resend,
} = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  // Rueckgaben weit typisieren (Union statt inferiertem Literal), damit
  // einzelne Tests Erfolgs- UND Fehlzweige per mockResolvedValue setzen koennen.
  getSession: vi.fn(
    async (): Promise<{
      data: { session: { access_token: string; user: { id: string; email: string } } | null }
      error: { message: string } | null
    }> => ({ data: { session: null }, error: null }),
  ),
  onAuthStateChange: vi.fn(() => ({
    data: { subscription: { unsubscribe: vi.fn() } },
  })),
  // Default: kein Step-up faellig.
  getAuthenticatorAssuranceLevel: vi.fn(async () => ({
    data: { currentLevel: 'aal1', nextLevel: 'aal1' },
    error: null,
  })),
  listFactors: vi.fn(async () => ({ data: { all: [], totp: [{ id: 'f1' }] }, error: null })),
  challenge: vi.fn(
    async (): Promise<{ data: { id: string } | null; error: { message: string } | null }> => ({
      data: { id: 'ch1' },
      error: null,
    }),
  ),
  verify: vi.fn(
    async (): Promise<{ data: object | null; error: { message: string } | null }> => ({
      data: {},
      error: null,
    }),
  ),
  resend: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword,
      signOut: vi.fn(),
      getSession,
      onAuthStateChange,
      resend,
      mfa: { getAuthenticatorAssuranceLevel, listFactors, challenge, verify },
    },
  },
}))

const { notifySuccess, notifyError } = vi.hoisted(() => ({
  notifySuccess: vi.fn(),
  notifyError: vi.fn(),
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: notifySuccess, error: notifyError, info: vi.fn() },
}))

// `SessionProvider.apply()` loest bei einer bestehenden Session ein `fetchMe`
// aus — gemockt, damit der Bereits-eingeloggt-Test keinen echten Fetch macht.
const { fetchMe } = vi.hoisted(() => ({
  fetchMe: vi.fn(async () => ({
    user_id: 'u1',
    default_workspace_id: null,
    organizations: [],
    has_password: true,
  })),
}))

vi.mock('@/api/client', () => ({ fetchMe }))

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
import { sanitizeNext } from '@/features/auth/lib/sanitize-next'
import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  afterEach(() => {
    mockConfig.signupDisabled = false
    mockConfig.launchMode = 'open'
    mockConfig.launchContact = ''
    window.localStorage.clear()
  })

  it('versteckt den Registrieren-Link bei deaktiviertem Signup (Altschalter, kein Launch-Modus)', () => {
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

  it('zeigt den Registrieren-Link im "coming_soon"-Launch-Modus, auch wenn signupDisabled gesetzt ist', () => {
    mockConfig.signupDisabled = true
    mockConfig.launchMode = 'coming_soon'
    render(
      <BrowserRouter>
        <SessionProvider>
          <LoginPage />
        </SessionProvider>
      </BrowserRouter>,
    )

    expect(document.querySelector('a[href*="/signup"]')).not.toBeNull()
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

  // Issue #430: Checkbox-Default ist AUS, Beschriftung interpoliert die
  // konfigurierte Stundenzahl statt sie hart zu kodieren.
  it('zeigt die Remember-Checkbox unangehakt mit der konfigurierten Stundenzahl', () => {
    render(
      <BrowserRouter>
        <SessionProvider>
          <LoginPage />
        </SessionProvider>
      </BrowserRouter>,
    )

    const checkbox = screen.getByLabelText('Angemeldet bleiben (12 h)')
    expect(checkbox).not.toBeChecked()
  })

  it('setzt Remember-Flag + Login-Zeitstempel, wenn die Checkbox beim Login aktiviert ist (AC 1)', async () => {
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
    fireEvent.click(screen.getByLabelText('Angemeldet bleiben (12 h)'))
    fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))

    // Marker + Login-Zeitstempel stecken in EINEM Wert (ein `setItem`) —
    // ein Marker ohne gueltigen Zeitstempel waere eine Session ohne
    // Obergrenze und gilt deshalb als abgelaufen.
    await waitFor(() => {
      expect(window.localStorage.getItem('who2be.auth.remember')).not.toBeNull()
    })
    const marker = JSON.parse(window.localStorage.getItem('who2be.auth.remember') as string)
    expect(typeof marker.signedInAt).toBe('number')
  })

  it('laesst ohne Haken das heutige Tab-Verhalten unveraendert — kein Remember-Flag (AC 2)', async () => {
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
      expect(signInWithPassword).toHaveBeenCalled()
    })
    expect(window.localStorage.getItem('who2be.auth.remember')).toBeNull()
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

// ---------------------------------------------------------------------------
// Branch-Abdeckung (WP-1/TST-1): Fehlerpfade des Passwort-Logins, alle Zweige
// des MFA-Step-ups sowie das `next`-Param-Handling. MemoryRouter mit echten
// Ziel-Routen, damit Navigationen beobachtbar sind.
// ---------------------------------------------------------------------------

// Setzt alle Auth-Mocks auf den "normalen" Zustand zurueck (kein Step-up,
// keine Session) — die Bestandstests oben lassen z. T. abweichende
// mockResolvedValue-Defaults zurueck.
function primeAuthMocks() {
  signInWithPassword.mockReset()
  signInWithPassword.mockResolvedValue({ data: { session: null }, error: null })
  getSession.mockReset()
  getSession.mockResolvedValue({ data: { session: null }, error: null })
  onAuthStateChange.mockReset()
  onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } })
  getAuthenticatorAssuranceLevel.mockReset()
  getAuthenticatorAssuranceLevel.mockResolvedValue({
    data: { currentLevel: 'aal1', nextLevel: 'aal1' },
    error: null,
  })
  listFactors.mockReset()
  listFactors.mockResolvedValue({ data: { all: [], totp: [{ id: 'f1' }] }, error: null })
  challenge.mockReset()
  challenge.mockResolvedValue({ data: { id: 'ch1' }, error: null })
  verify.mockReset()
  verify.mockResolvedValue({ data: {}, error: null })
  resend.mockReset()
  fetchMe.mockReset()
  fetchMe.mockResolvedValue({
    user_id: 'u1',
    default_workspace_id: null,
    organizations: [],
    has_password: true,
  })
  notifySuccess.mockReset()
  notifyError.mockReset()
}

function renderLoginAt(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <SessionProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>HOME</div>} />
          <Route path="/dashboard" element={<div>DASHBOARD</div>} />
        </Routes>
      </SessionProvider>
    </MemoryRouter>,
  )
}

function fillAndSubmitLogin(email = 'agent@who2be.dev', password = 'streng-geheim') {
  fireEvent.change(screen.getByLabelText('E-Mail'), { target: { value: email } })
  fireEvent.change(screen.getByLabelText('Passwort'), { target: { value: password } })
  fireEvent.click(screen.getByRole('button', { name: 'Anmelden' }))
}

describe('LoginPage — Passwort-Login-Fehlerpfade', () => {
  beforeEach(() => {
    primeAuthMocks()
  })

  it('zeigt die GoTrue-Fehlermeldung bei falschen Zugangsdaten', async () => {
    signInWithPassword.mockResolvedValue({
      data: { session: null },
      error: { message: 'Invalid login credentials' },
    })
    renderLoginAt('/login')

    fillAndSubmitLogin()

    expect(await screen.findByText('Invalid login credentials')).toBeInTheDocument()
    // Bleibt auf der Login-Maske; kein Resend-CTA (nicht der Unconfirmed-Fall).
    expect(screen.getByRole('button', { name: 'Anmelden' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Bestaetigungs-Mail erneut senden' }),
    ).not.toBeInTheDocument()
  })

  it('zeigt bei unbestaetigter E-Mail den Resend-CTA und versendet die Mail erneut', async () => {
    signInWithPassword.mockResolvedValue({
      data: { session: null },
      error: { message: 'Email not confirmed' },
    })
    resend.mockResolvedValue({ error: null })
    renderLoginAt('/login')

    fillAndSubmitLogin()

    expect(
      await screen.findByText('Deine E-Mail-Adresse ist noch nicht bestaetigt.'),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Bestaetigungs-Mail erneut senden' }))

    await waitFor(() => {
      expect(resend).toHaveBeenCalledWith({
        type: 'signup',
        email: 'agent@who2be.dev',
        options: { emailRedirectTo: expect.stringContaining('/auth/callback') },
      })
    })
    expect(notifySuccess).toHaveBeenCalledWith('Bestaetigungs-Mail erneut gesendet.')
  })

  it('meldet einen Fehler beim erneuten Versand der Bestaetigungs-Mail', async () => {
    signInWithPassword.mockResolvedValue({
      data: { session: null },
      error: { message: 'Email not confirmed' },
    })
    resend.mockResolvedValue({ error: { message: 'over_email_send_rate_limit' } })
    renderLoginAt('/login')

    fillAndSubmitLogin()

    fireEvent.click(
      await screen.findByRole('button', { name: 'Bestaetigungs-Mail erneut senden' }),
    )

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('over_email_send_rate_limit')
    })
    expect(notifySuccess).not.toHaveBeenCalled()
  })

  it('validiert E-Mail und Passwort clientseitig, ohne GoTrue aufzurufen', async () => {
    renderLoginAt('/login')

    const emailInput = screen.getByLabelText('E-Mail')
    fireEvent.change(emailInput, { target: { value: 'nicht-gueltig' } })
    // Direktes submit-Event statt Button-Klick: jsdom blockiert den Klick
    // sonst per nativer Constraint-Validation (type="email"), bevor die
    // zod-Zweige von react-hook-form ueberhaupt laufen.
    const formEl = emailInput.closest('form')
    if (formEl === null) {
      throw new Error('Login-Formular nicht gefunden')
    }
    fireEvent.submit(formEl)

    expect(await screen.findByText('Bitte gueltige E-Mail eingeben.')).toBeInTheDocument()
    expect(screen.getByText('Passwort erforderlich.')).toBeInTheDocument()
    expect(signInWithPassword).not.toHaveBeenCalled()
  })
})

describe('LoginPage — MFA-Step-up-Zweige', () => {
  beforeEach(() => {
    primeAuthMocks()
    // Step-up faellig: Passwort korrekt, Session haengt auf aal1.
    getAuthenticatorAssuranceLevel.mockResolvedValue({
      data: { currentLevel: 'aal1', nextLevel: 'aal2' },
      error: null,
    })
  })

  async function reachMfaStep() {
    renderLoginAt('/login')
    fillAndSubmitLogin('admin@who2be.dev')
    return await screen.findByLabelText('Code')
  }

  it('zeigt bei falschem Code die lokalisierte Fehlermeldung und leert das Feld', async () => {
    verify.mockResolvedValue({ data: null, error: { message: 'invalid TOTP code' } })
    const codeField = await reachMfaStep()

    fireEvent.change(codeField, { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestaetigen' }))

    expect(
      await screen.findByText('Code konnte nicht verifiziert werden. Bitte erneut versuchen.'),
    ).toBeInTheDocument()
    // Die rohe GoTrue-Message wird bewusst nicht durchgereicht.
    expect(screen.queryByText('invalid TOTP code')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Code')).toHaveValue('')
  })

  it('validiert das 6-stellige Code-Format, ohne eine Challenge zu starten', async () => {
    const codeField = await reachMfaStep()

    fireEvent.change(codeField, { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestaetigen' }))

    expect(await screen.findByText('Bitte einen 6-stelligen Code eingeben.')).toBeInTheDocument()
    expect(challenge).not.toHaveBeenCalled()
  })

  it('faellt auf die Fehlermeldung zurueck, wenn kein verifizierter Faktor existiert', async () => {
    listFactors.mockResolvedValue({ data: { all: [], totp: [] }, error: null })
    const codeField = await reachMfaStep()

    fireEvent.change(codeField, { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestaetigen' }))

    expect(
      await screen.findByText('Code konnte nicht verifiziert werden. Bitte erneut versuchen.'),
    ).toBeInTheDocument()
    expect(challenge).not.toHaveBeenCalled()
  })

  it('faellt auf die Fehlermeldung zurueck, wenn die Challenge nicht startet', async () => {
    challenge.mockResolvedValue({ data: null, error: { message: 'challenge down' } })
    const codeField = await reachMfaStep()

    fireEvent.change(codeField, { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestaetigen' }))

    expect(
      await screen.findByText('Code konnte nicht verifiziert werden. Bitte erneut versuchen.'),
    ).toBeInTheDocument()
    expect(verify).not.toHaveBeenCalled()
  })
})

describe('LoginPage — next-Param-Handling', () => {
  beforeEach(() => {
    primeAuthMocks()
  })

  it('navigiert nach erfolgreichem Login zum sanitisierten next-Ziel', async () => {
    renderLoginAt('/login?next=%2Fdashboard')

    fillAndSubmitLogin()

    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument()
  })

  it('verwirft ein externes next und navigiert auf die Startseite', async () => {
    renderLoginAt(`/login?next=${encodeURIComponent('https://evil.com')}`)

    fillAndSubmitLogin()

    expect(await screen.findByText('HOME')).toBeInTheDocument()
  })

  it('haengt ein gesetztes next an Passwort-vergessen- und Registrieren-Link an', () => {
    renderLoginAt('/login?next=%2Fdashboard')

    expect(screen.getByRole('link', { name: 'Passwort vergessen?' })).toHaveAttribute(
      'href',
      '/reset-password?next=%2Fdashboard',
    )
    expect(screen.getByRole('link', { name: 'Registrieren' })).toHaveAttribute(
      'href',
      '/signup?next=%2Fdashboard',
    )
  })

  it('nutzt ohne next die Basis-Links', () => {
    renderLoginAt('/login')

    expect(screen.getByRole('link', { name: 'Passwort vergessen?' })).toHaveAttribute(
      'href',
      '/reset-password',
    )
    expect(screen.getByRole('link', { name: 'Registrieren' })).toHaveAttribute('href', '/signup')
  })

  it('leitet eine bereits bestehende Session sofort zum next-Ziel um', async () => {
    getSession.mockResolvedValue({
      data: {
        session: { access_token: 'tok', user: { id: 'u1', email: 'agent@who2be.dev' } },
      },
      error: null,
    })
    renderLoginAt('/login?next=%2Fdashboard')

    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument()
    expect(signInWithPassword).not.toHaveBeenCalled()
  })
})
