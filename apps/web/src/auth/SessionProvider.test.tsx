import type { AuthChangeEvent, Session, Subscription } from '@supabase/supabase-js'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
  getSession,
  signInWithPassword,
  signOut,
  onAuthStateChange,
  unsubscribe,
  fetchMe,
  getAuthenticatorAssuranceLevel,
  syncStorageBackendForThisTab,
} = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(),
  unsubscribe: vi.fn(),
  fetchMe: vi.fn(async () => ({
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [],
    has_password: true,
  })),
  // Default: kein Step-up faellig (currentLevel == nextLevel).
  getAuthenticatorAssuranceLevel: vi.fn(async () => ({
    data: { currentLevel: 'aal1', nextLevel: 'aal1' },
    error: null,
  })),
  // Issue #471: `SessionProvider::signIn` ruft das nach jedem Marker-Schreiben
  // auf. Hier nur als Spy relevant (die eigentliche Frozen-Backend-Logik ist
  // Gegenstand von `lib/supabase.test.ts`, nicht dieser Datei).
  syncStorageBackendForThisTab: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession,
      signInWithPassword,
      signOut,
      onAuthStateChange,
      mfa: { getAuthenticatorAssuranceLevel },
    },
  },
  syncStorageBackendForThisTab,
}))

vi.mock('@/api/client', () => ({
  fetchMe,
}))

import { SessionProvider } from './SessionProvider'
import { useSession } from './session-context'

function Probe() {
  const { session, me, sessionLoaded } = useSession()
  return (
    <div>
      <span data-testid="session">{session?.access_token ?? '<none>'}</span>
      <span data-testid="me">{me?.user_id ?? '<none>'}</span>
      <span data-testid="loaded">{sessionLoaded ? 'yes' : 'no'}</span>
    </div>
  )
}

let listener:
  | ((event: AuthChangeEvent, session: Session | null) => void)
  | null = null

beforeEach(() => {
  listener = null
  getSession.mockResolvedValue({ data: { session: null }, error: null })
  onAuthStateChange.mockImplementation(
    (cb: (event: AuthChangeEvent, session: Session | null) => void) => {
      listener = cb
      return {
        data: { subscription: { unsubscribe } as unknown as Subscription },
      }
    },
  )
})

afterEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
})

describe('SessionProvider', () => {
  it('registriert onAuthStateChange beim Mount', async () => {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(getSession).toHaveBeenCalled()
    })
    expect(onAuthStateChange).toHaveBeenCalledTimes(1)
  })

  it('uebernimmt Hash-Session aus dem Bootstrap und fetcht me genau einmal', async () => {
    // Magic-Link-Hash: GoTrue parsed den Token und liefert die Session
    // schon beim ersten `getSession()`. `onAuthStateChange` feuert direkt
    // danach mit `INITIAL_SESSION` und identischem Token — der zweite
    // `fetchMe`-Call wuerde Daten doppelt holen und (bei race) den ersten
    // ueberholen.
    const magicSession = { access_token: 'magic-jwt' } as unknown as Session
    getSession.mockResolvedValueOnce({ data: { session: magicSession }, error: null })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('magic-jwt')
      expect(screen.getByTestId('me').textContent).toBe('u1')
    })

    // Listener feuert mit identischem Token — dedupe verhindert Doppel-Fetch.
    await act(async () => {
      listener?.('INITIAL_SESSION', magicSession)
      await Promise.resolve()
    })

    expect(fetchMe).toHaveBeenCalledTimes(1)
  })

  it('synct Session+Me, sobald onAuthStateChange feuert (Magic-Link-Hash)', async () => {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(listener).not.toBeNull()
    })

    const magicSession = { access_token: 'magic-jwt' } as unknown as Session
    await act(async () => {
      listener?.('SIGNED_IN', magicSession)
      // Microtask abwarten, damit das asynchrone fetchMe-Resolved-State setzt.
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('magic-jwt')
      expect(screen.getByTestId('me').textContent).toBe('u1')
    })
  })

  it('haelt eine aal1-Session mit faelligem zweiten Faktor zurueck (kein Commit)', async () => {
    // Passwort ok, aber TOTP-Faktor verlangt Step-up: nextLevel > currentLevel.
    // Die Session darf NICHT committed werden, sonst landet der User mit aal1
    // in der App und jede Admin-Aktion 403t (mfa_required).
    getAuthenticatorAssuranceLevel.mockResolvedValueOnce({
      data: { currentLevel: 'aal1', nextLevel: 'aal2' },
      error: null,
    })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )
    await waitFor(() => {
      expect(listener).not.toBeNull()
    })

    const aal1Session = { access_token: 'aal1-jwt' } as unknown as Session
    await act(async () => {
      listener?.('SIGNED_IN', aal1Session)
      await Promise.resolve()
    })

    // Weder Session noch me committed; fetchMe erst gar nicht aufgerufen.
    expect(screen.getByTestId('session').textContent).toBe('<none>')
    expect(screen.getByTestId('me').textContent).toBe('<none>')
    expect(fetchMe).not.toHaveBeenCalled()
  })

  it('setzt sessionLoaded erst nach abgeschlossenem Bootstrap', async () => {
    // Solange getSession() pending ist, muss sessionLoaded false bleiben —
    // RequireAuth zeigt dann eine Ladeanzeige statt nach /login zu redirecten
    // (sonst gehen Deep-Links beim Reload verloren).
    let resolveGetSession!: (value: { data: { session: Session | null }; error: null }) => void
    getSession.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveGetSession = resolve
        }),
    )

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    expect(screen.getByTestId('loaded').textContent).toBe('no')

    await act(async () => {
      resolveGetSession({ data: { session: null }, error: null })
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(screen.getByTestId('loaded').textContent).toBe('yes')
    })
    // Kein Session-Commit — der User ist tatsaechlich ausgeloggt.
    expect(screen.getByTestId('session').textContent).toBe('<none>')
  })

  it('unsubscribed das onAuthStateChange-Listener beim Unmount', async () => {
    const { unmount } = render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )
    await waitFor(() => {
      expect(onAuthStateChange).toHaveBeenCalled()
    })

    unmount()

    // StrictMode kann den Effect doppelt mounten/unmounten — wichtig ist nur,
    // dass beim finalen Unmount unsubscribed wird (kein Listener-Leak).
    expect(unsubscribe).toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// "Angemeldet bleiben" (Issue #430, ADR-0052). Kein `@/config`-Mock in dieser
// Datei -- es greift die echte `resolveConfig()` (Default `sessionMaxAgeHours
// = 12`, kein `window.__WHO2BE_CONFIG__` in jsdom gesetzt). `lib/remember-
// session.ts` ist ebenfalls NICHT gemockt: das Modul fasst nur `window`-
// Storage an, die echte Implementierung ist hier der Pruefgegenstand.
// ---------------------------------------------------------------------------
const REMEMBER_KEY = 'who2be.auth.remember'
const SESSION_KEY = 'who2be.auth.session'
const HOUR_MS = 60 * 60 * 1000

function markerAgedHours(hours: number): string {
  return JSON.stringify({ signedInAt: Date.now() - hours * HOUR_MS })
}

describe('SessionProvider -- Ablaufpruefung "angemeldet bleiben" (Issue #430 AC 1)', () => {
  it('erzwingt beim Boot einen vollen Logout, wenn die Obergrenze ueberschritten ist', async () => {
    window.localStorage.setItem(REMEMBER_KEY, markerAgedHours(13))
    window.localStorage.setItem(SESSION_KEY, 'stale-blob')

    const staleSession = { access_token: 'stale-jwt' } as unknown as Session
    getSession.mockResolvedValueOnce({ data: { session: staleSession }, error: null })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loaded').textContent).toBe('yes')
    })
    // Kein Commit der (technisch noch gueltigen) Session -- voller Logout,
    // beide Flags geloescht, kein 2FA-Bypass beim naechsten Login.
    expect(screen.getByTestId('session').textContent).toBe('<none>')
    expect(screen.getByTestId('me').textContent).toBe('<none>')
    expect(signOut).toHaveBeenCalledTimes(1)
    expect(window.localStorage.getItem(REMEMBER_KEY)).toBeNull()
    // Der Session-Blob darf nicht liegenbleiben: ohne Marker faellt er aus
    // der Ablaufpruefung heraus und waere damit unbefristet gueltig.
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(fetchMe).not.toHaveBeenCalled()
  })

  it('committet eine "angemeldet bleiben"-Session innerhalb der Obergrenze ohne erneuten Login', async () => {
    const marker = markerAgedHours(1)
    window.localStorage.setItem(REMEMBER_KEY, marker)

    const freshSession = { access_token: 'remembered-jwt' } as unknown as Session
    getSession.mockResolvedValueOnce({ data: { session: freshSession }, error: null })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('remembered-jwt')
      expect(screen.getByTestId('me').textContent).toBe('u1')
    })
    expect(signOut).not.toHaveBeenCalled()
    // Marker bleibt stehen -- der neue Tab/Neustart ist gerade der Zweck.
    expect(window.localStorage.getItem(REMEMBER_KEY)).toBe(marker)
  })

  it('prueft eine Session ohne Marker (heutiges Tab-Verhalten) nie auf Ablauf', async () => {
    // Kein Marker gesetzt -- kann bei einer normalen Tab-Lifetime-Session
    // auch gar nicht der Fall sein (AC 2 bleibt unberuehrt).
    const tabSession = { access_token: 'tab-jwt' } as unknown as Session
    getSession.mockResolvedValueOnce({ data: { session: tabSession }, error: null })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('tab-jwt')
    })
    expect(signOut).not.toHaveBeenCalled()
  })

  it('signIn(remember=true) setzt den Marker VOR signInWithPassword', async () => {
    signInWithPassword.mockResolvedValue({
      data: { session: { access_token: 'new-jwt' } },
      error: null,
    })

    function SignInProbe() {
      const { signIn } = useSession()
      return (
        <button type="button" onClick={() => void signIn('agent@who2be.dev', 'pw', true)}>
          signin
        </button>
      )
    }

    render(
      <SessionProvider>
        <SignInProbe />
      </SessionProvider>,
    )
    await waitFor(() => expect(getSession).toHaveBeenCalled())

    const before = Date.now()
    fireEvent.click(screen.getByRole('button', { name: 'signin' }))

    await waitFor(() => {
      expect(window.localStorage.getItem(REMEMBER_KEY)).not.toBeNull()
    })
    const marker = JSON.parse(window.localStorage.getItem(REMEMBER_KEY) as string)
    expect(marker.signedInAt).toBeGreaterThanOrEqual(before)
  })

  it('signIn(remember=false) laesst kein Remember-Flag stehen (AC 2)', async () => {
    signInWithPassword.mockResolvedValue({
      data: { session: { access_token: 'new-jwt' } },
      error: null,
    })

    function SignInProbe() {
      const { signIn } = useSession()
      return (
        <button type="button" onClick={() => void signIn('agent@who2be.dev', 'pw', false)}>
          signin
        </button>
      )
    }

    render(
      <SessionProvider>
        <SignInProbe />
      </SessionProvider>,
    )
    await waitFor(() => expect(getSession).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'signin' }))

    await waitFor(() => {
      expect(signInWithPassword).toHaveBeenCalled()
    })
    expect(window.localStorage.getItem(REMEMBER_KEY)).toBeNull()
  })

  // Issue #471: der delegierende Storage-Adapter liest den Marker nicht mehr
  // live, sondern haelt seinen Modus im eingefrorenen Modul-Zustand von
  // `lib/supabase.ts`. Ohne diesen Aufruf waere ein Moduswechsel IN DIESEM
  // TAB wirkungslos (AC 3) -- die eigentliche Backend-Wahl testet
  // `lib/supabase.test.ts`, hier geht es nur um die Verdrahtung.
  it('signIn synchronisiert den eingefrorenen Storage-Modus nach jedem Marker-Schreiben (Issue #471, AC 3)', async () => {
    signInWithPassword.mockResolvedValue({
      data: { session: { access_token: 'new-jwt' } },
      error: null,
    })

    function SignInProbe() {
      const { signIn } = useSession()
      return (
        <button type="button" onClick={() => void signIn('agent@who2be.dev', 'pw', true)}>
          signin
        </button>
      )
    }

    render(
      <SessionProvider>
        <SignInProbe />
      </SessionProvider>,
    )
    await waitFor(() => expect(getSession).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'signin' }))

    await waitFor(() => {
      expect(signInWithPassword).toHaveBeenCalled()
    })
    expect(syncStorageBackendForThisTab).toHaveBeenCalled()
    // Reihenfolge: der Marker steht bereits im localStorage, BEVOR die
    // Synchronisierung laeuft -- sonst friert sie den falschen Modus ein.
    const markerAtSyncTime = window.localStorage.getItem(REMEMBER_KEY)
    expect(markerAtSyncTime).not.toBeNull()
  })

  it('signIn synchronisiert den eingefrorenen Storage-Modus auch nach einem fehlgeschlagenen Login (Marker-Restore)', async () => {
    signInWithPassword.mockResolvedValue({
      data: { session: null },
      error: { message: 'Invalid login credentials' },
    })

    function SignInProbe() {
      const { signIn } = useSession()
      return (
        <button
          type="button"
          onClick={() => {
            void signIn('agent@who2be.dev', 'pw', true).catch(() => {})
          }}
        >
          signin
        </button>
      )
    }

    render(
      <SessionProvider>
        <SignInProbe />
      </SessionProvider>,
    )
    await waitFor(() => expect(getSession).toHaveBeenCalled())
    syncStorageBackendForThisTab.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'signin' }))

    await waitFor(() => {
      expect(signInWithPassword).toHaveBeenCalled()
    })
    // Zweimal: einmal vor `signInWithPassword` (Marker gesetzt), einmal nach
    // dem Fehlschlag (Marker zurueckgestellt) -- der eingefrorene Wert muss
    // in beiden Faellen mit dem Marker-Stand uebereinstimmen.
    expect(syncStorageBackendForThisTab).toHaveBeenCalledTimes(2)
  })

  it('signOut loescht den Marker NACH dem GoTrue-Signout (kein verwaister Token)', async () => {
    window.localStorage.setItem(REMEMBER_KEY, markerAgedHours(0))

    function SignOutProbe() {
      const { signOut: doSignOut } = useSession()
      return (
        <button type="button" onClick={() => void doSignOut()}>
          signout
        </button>
      )
    }

    render(
      <SessionProvider>
        <SignOutProbe />
      </SessionProvider>,
    )
    await waitFor(() => expect(getSession).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'signout' }))

    await waitFor(() => {
      expect(signOut).toHaveBeenCalledTimes(1)
    })
    expect(window.localStorage.getItem(REMEMBER_KEY)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Regressionen aus dem Security-Review zu Issue #430. Jeder Test haelt genau
// einen Befund fest, der die absolute Obergrenze umgehbar machte.
// ---------------------------------------------------------------------------
describe('SessionProvider -- Security-Review-Regressionen (Issue #430)', () => {
  function SignInProbe({ remember }: { remember: boolean }) {
    const { signIn } = useSession()
    return (
      <button
        type="button"
        onClick={() => {
          void signIn('agent@who2be.dev', 'pw', remember).catch(() => {})
        }}
      >
        signin
      </button>
    )
  }

  async function renderAndClickSignIn(remember: boolean) {
    render(
      <SessionProvider>
        <SignInProbe remember={remember} />
      </SessionProvider>,
    )
    await waitFor(() => expect(getSession).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'signin' }))
    await waitFor(() => expect(signInWithPassword).toHaveBeenCalled())
  }

  // HIGH-1: Der Wechsel "mit Haken" -> "ohne Haken" liess den alten
  // Refresh-Token im localStorage liegen. Weil der Marker beim Wechsel
  // verschwindet, fiel dieser Token zugleich aus der Ablaufpruefung heraus --
  // eine Datenleiche, die nie abgelaufen waere.
  it('signIn(remember=false) raeumt eine liegengebliebene localStorage-Session ab', async () => {
    window.localStorage.setItem(REMEMBER_KEY, markerAgedHours(1))
    window.localStorage.setItem(SESSION_KEY, 'alte-remembered-session')
    signInWithPassword.mockResolvedValue({
      data: { session: { access_token: 'neu' } },
      error: null,
    })

    await renderAndClickSignIn(false)

    await waitFor(() => {
      expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
    })
    expect(window.localStorage.getItem(REMEMBER_KEY)).toBeNull()
  })

  it('signIn(remember=true) raeumt die vorherige Tab-Session im sessionStorage ab', async () => {
    window.sessionStorage.setItem(SESSION_KEY, 'alte-tab-session')
    signInWithPassword.mockResolvedValue({
      data: { session: { access_token: 'neu' } },
      error: null,
    })

    await renderAndClickSignIn(true)

    await waitFor(() => {
      expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
    })
  })

  // Ein Tippfehler im Passwort darf den Modus nicht umstellen: sonst laufen
  // parallel offene "angemeldet bleiben"-Tabs ins falsche Storage-Backend.
  it('stellt bei fehlgeschlagenem Login den vorherigen Marker wieder her', async () => {
    const before = markerAgedHours(2)
    window.localStorage.setItem(REMEMBER_KEY, before)
    signInWithPassword.mockResolvedValue({
      data: { session: null },
      error: { message: 'Invalid login credentials' },
    })

    await renderAndClickSignIn(false)

    await waitFor(() => {
      expect(window.localStorage.getItem(REMEMBER_KEY)).toBe(before)
    })
  })

  // MEDIUM-5: fehlender/kaputter Zeitstempel hiess frueher "keine
  // Obergrenze". Ein einziges setItem aus den DevTools genuegte, um die
  // Kappung dauerhaft abzuschalten.
  it('behandelt einen Marker ohne gueltigen Zeitstempel als abgelaufen (fail-closed)', async () => {
    window.localStorage.setItem(REMEMBER_KEY, '{"signedInAt":"nie"}')
    const staleSession = { access_token: 'manipuliert' } as unknown as Session
    getSession.mockResolvedValueOnce({ data: { session: staleSession }, error: null })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loaded').textContent).toBe('yes')
    })
    expect(screen.getByTestId('session').textContent).toBe('<none>')
    expect(signOut).toHaveBeenCalledTimes(1)
    expect(window.localStorage.getItem(REMEMBER_KEY)).toBeNull()
  })

  // MEDIUM-6: "Ueberall abmelden" und die Account-Loeschung rufen
  // `supabase.auth.signOut` direkt auf, nicht ueber `signOut()` hier. Ohne
  // zentralen Handler blieb der Marker stehen und der naechste Login ohne
  // Checkbox (OAuth/Magic-Link) landete ungefragt auf der Platte.
  it('loescht den Marker bei JEDEM SIGNED_OUT, auch aus fremder Quelle', async () => {
    window.localStorage.setItem(REMEMBER_KEY, markerAgedHours(1))

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )
    await waitFor(() => expect(listener).not.toBeNull())

    await act(async () => {
      listener?.('SIGNED_OUT', null)
    })

    expect(window.localStorage.getItem(REMEMBER_KEY)).toBeNull()
  })

  // MEDIUM-3: `bootstrap()` und der Listener laufen auf derselben `apply()`.
  // Ein langsamer Lauf (fetchMe haengt) durfte einen spaeter gestarteten
  // Ablauf-Logout nicht ueberholen und die Session zurueckschreiben.
  it('laesst einen ueberholten apply()-Lauf die Session nicht nachtraeglich committen', async () => {
    const live = { access_token: 'live-jwt' } as unknown as Session
    let releaseFetchMe: (() => void) | null = null
    fetchMe.mockImplementationOnce(async () => {
      await new Promise<void>((resolve) => {
        releaseFetchMe = resolve
      })
      return { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [], has_password: true }
    })
    getSession.mockResolvedValueOnce({ data: { session: live }, error: null })

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )
    await waitFor(() => expect(releaseFetchMe).not.toBeNull())

    // Waehrend der erste Lauf im fetchMe haengt, kommt ein Logout herein.
    await act(async () => {
      listener?.('SIGNED_OUT', null)
    })
    // Jetzt kehrt der alte Lauf zurueck -- er darf nichts mehr schreiben.
    await act(async () => {
      releaseFetchMe?.()
      await Promise.resolve()
    })

    expect(screen.getByTestId('session').textContent).toBe('<none>')
    expect(screen.getByTestId('me').textContent).toBe('<none>')
  })
})

// ---------------------------------------------------------------------------
// Regression aus dem CI-Lauf zu PR #468: `@supabase/auth-js` stellt einem
// frisch registrierten Subscriber sofort ein `INITIAL_SESSION` mit DERSELBEN
// Session zu (`GoTrueClient.js`). Der Bestands-Mock oben tut das nicht — die
// Luecke hat einen Generationszaehler durchgelassen, der jede eingeloggte
// Session verworfen hat (drei bestehende E2E-Journeys rot). Dieser Mock bildet
// das Verhalten von auth-js nach.
// ---------------------------------------------------------------------------
describe('SessionProvider -- doppeltes INITIAL_SESSION (auth-js-Verhalten)', () => {
  it('committet die Session, obwohl derselbe Zustand zweimal ankommt', async () => {
    const live = { access_token: 'live-jwt' } as unknown as Session
    getSession.mockResolvedValue({ data: { session: live }, error: null })
    // auth-js ruft den Callback beim Registrieren sofort mit der geladenen
    // Session auf — waehrend `bootstrap()` noch im `await` haengt.
    onAuthStateChange.mockImplementation(
      (cb: (event: AuthChangeEvent, session: Session | null) => void) => {
        listener = cb
        cb('INITIAL_SESSION', live)
        return { data: { subscription: { unsubscribe } as unknown as Subscription } }
      },
    )

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loaded').textContent).toBe('yes')
    })
    expect(screen.getByTestId('session').textContent).toBe('live-jwt')
    expect(screen.getByTestId('me').textContent).toBe('u1')
  })

  it('meldet bei abgelaufener Session genau EINMAL ab, nicht pro Event', async () => {
    // Zwei signOut-Aufrufe fuer dieselbe Session: der zweite lief im CI in
    // einen 403, weil der Refresh-Token schon widerrufen war.
    window.localStorage.setItem(REMEMBER_KEY, markerAgedHours(13))
    const stale = { access_token: 'stale-jwt' } as unknown as Session
    getSession.mockResolvedValue({ data: { session: stale }, error: null })
    onAuthStateChange.mockImplementation(
      (cb: (event: AuthChangeEvent, session: Session | null) => void) => {
        listener = cb
        cb('INITIAL_SESSION', stale)
        return { data: { subscription: { unsubscribe } as unknown as Subscription } }
      },
    )

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loaded').textContent).toBe('yes')
    })
    expect(screen.getByTestId('session').textContent).toBe('<none>')
    expect(signOut).toHaveBeenCalledTimes(1)
  })
})
