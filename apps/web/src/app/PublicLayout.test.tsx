import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext, type SessionValue } from '@/auth/session-context'
import { LoginPage, OAuthConsentPage } from '@/features/auth'
import i18n from '@/i18n'

import { PublicLayout } from './PublicLayout'

// `useLocale.setLocale` schreibt die Praeferenz best-effort nach Supabase
// (`user_metadata.preferred_locale`) — ohne Mock wuerde der echte Client
// (ohne Session) zwar nur lokal abbrechen, aber wir wollen hier keine
// Abhaengigkeit vom echten `@supabase/supabase-js`-Verhalten testen.
const { updateUser } = vi.hoisted(() => ({
  updateUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
}))
vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { updateUser } },
}))

vi.mock('@/config', () => ({
  config: {
    apiBaseUrl: 'http://localhost:8000',
    mcpUrl: 'http://localhost:8000/mcp',
    supabaseUrl: 'http://localhost:54321',
    supabaseAnonKey: 'anon',
    signupDisabled: false,
  },
}))

// Beide Pages lesen `useSession()`/`useAuthToken()` aus Context — ohne
// Session (wie ein ausgeloggter Besucher) redirectet `OAuthConsentPage` auf
// `/login`, was hier bewusst in Kauf genommen wird: die PublicLayout-Insel
// bleibt in beiden Faellen im DOM, weil sie ausserhalb des Outlets sitzt.
const loggedOutSession: SessionValue = {
  session: null,
  sessionLoaded: true,
  me: null,
  signIn: vi.fn(async () => ({ mfaRequired: false })),
  signOut: vi.fn(async () => {}),
  refreshMe: vi.fn(async () => {}),
}

function renderPublicRoute(path: string) {
  return render(
    <SessionContext.Provider value={loggedOutSession}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<PublicLayout />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/oauth/consent" element={<OAuthConsentPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

// Der Trigger-Button traegt kein stabiles `data-testid`, aber ein Name-Match
// funktioniert unabhaengig vom aktuell aktiven `aria-label` (das sich nach
// einem Sprachwechsel selbst aendert).
function getSwitcherTrigger() {
  return screen.getByRole('button', { name: /sprache|language/i })
}

// Radix DropdownMenu nutzt PointerCapture-/scrollIntoView-APIs, die jsdom
// nicht implementiert, und oeffnet ueblicherweise auf pointerdown+up.
// Stub-Polyfill + `keyDown(Enter)` statt `click`, analog
// `WorkspaceSwitcher.test.tsx`.
function openMenu() {
  fireEvent.keyDown(getSwitcherTrigger(), { key: 'Enter' })
}

describe('PublicLayout', () => {
  beforeAll(() => {
    Object.defineProperty(window.HTMLElement.prototype, 'hasPointerCapture', {
      value: () => false,
      configurable: true,
    })
    Object.defineProperty(window.HTMLElement.prototype, 'releasePointerCapture', {
      value: () => undefined,
      configurable: true,
    })
    Object.defineProperty(window.HTMLElement.prototype, 'setPointerCapture', {
      value: () => undefined,
      configurable: true,
    })
    Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
      value: () => undefined,
      configurable: true,
    })
  })

  afterEach(async () => {
    // Zurueck auf Deutsch — nachfolgende Tests (in dieser wie in anderen
    // Dateien) assertieren deutsche Default-Strings (siehe analoge
    // Konvention in `AccountPage.test.tsx`).
    await i18n.changeLanguage('de')
  })

  it('zeigt den Sprachumschalter auf /login', () => {
    renderPublicRoute('/login')
    expect(getSwitcherTrigger()).toBeInTheDocument()
  })

  it('zeigt den Sprachumschalter auf /oauth/consent', () => {
    renderPublicRoute('/oauth/consent')
    expect(getSwitcherTrigger()).toBeInTheDocument()
  })

  it('wechselt die Sprache und schlaegt auf gerenderte Strings der Seite durch', async () => {
    renderPublicRoute('/login')

    // Default-Locale `de` (siehe `src/i18n/index.ts`).
    expect(screen.getByText('Anmeldung')).toBeInTheDocument()

    openMenu()
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'English' }))

    // `login.description` ist in beiden Locales eindeutig (anders als
    // `login.title`/`login.submit`, die auf Englisch beide „Sign in" lauten).
    await waitFor(() => {
      expect(screen.getByText('Sign in to your Who2Be account.')).toBeInTheDocument()
    })
    expect(screen.queryByText('Melde dich mit deinem Who2Be-Konto an.')).not.toBeInTheDocument()
  })
})
