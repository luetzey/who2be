import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'

import { fetchMe } from '@/api/client'
import type { Me } from '@/api/types'

import { config } from '../config'
import {
  clearRememberMarker,
  markRememberedLogin,
  purgeStoredSessionFrom,
  readRememberMarker,
  rememberedSessionExpired,
  restoreRememberMarker,
} from '../lib/remember-session'
import { supabase } from '../lib/supabase'
import { SessionContext, type SessionValue } from './session-context'

// "Angemeldet bleiben" (Issue #430, ADR-0052). Der gesamte Marker-Zustand
// liegt in `lib/remember-session.ts` — eine Quelle fuer den Storage-Adapter
// (`lib/supabase.ts`), die Ablaufpruefung hier und den Logout in der
// Account-Seite. Das Modul importiert nichts aus `lib/supabase.ts`, deshalb
// bleiben die vielen `vi.mock('@/lib/supabase', …)`-Stubs der Bestandstests
// davon unberuehrt.
const SESSION_MAX_AGE_MS = config.sessionMaxAgeHours * 60 * 60 * 1000

function sessionOverMaxAge(): boolean {
  return rememberedSessionExpired(SESSION_MAX_AGE_MS)
}

// Atomare me+session-Reihenfolge — Hintergrund:
// vertauschte Reihenfolge produziert einen Zwischen-Commit mit
// session=set+me=null, LoginPage redirected dann sofort zu `/`,
// DefaultWorkspaceRedirect wirft mangels `default_workspace_id` zurueck auf
// `/login`, und Chrome bricht die Schleife mit „Throttling navigation to
// prevent the browser from hanging" ab (weisser Screen). Beide setState-Calls
// liegen im selben Microtask nach dem await, React 18 batcht das zu einem
// einzigen Commit.
async function resolveMe(accessToken: string | undefined): Promise<Me | null> {
  if (accessToken === undefined || accessToken === '') {
    return null
  }
  try {
    return await fetchMe(accessToken)
  } catch {
    return null
  }
}

// Admin-MFA (WP-F/S1): Steht ein verifizierter zweiter Faktor bereit, liefert
// ein reiner Passwort-Login nur eine `aal1`-Session — GoTrue meldet dann
// `nextLevel: 'aal2'`, waehrend `currentLevel` noch `aal1` ist. Eine solche
// Session darf nicht in die App gelassen werden (sonst 403 `mfa_required` bei
// jeder Admin-Aktion, ohne Weg zurueck auf aal2). Fehlerhafte Abfrage faellt
// bewusst fail-open auf `false` zurueck, damit ein getAAL-Ausfall den Login
// nicht komplett blockiert — das Backend-Gate bleibt die harte Grenze.
async function mfaStepUpPending(): Promise<boolean> {
  try {
    const { data } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel()
    return data?.nextLevel === 'aal2' && data.currentLevel !== 'aal2'
  } catch {
    return false
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [me, setMe] = useState<Me | null>(null)
  // `false` bis der Mount-Bootstrap (getSession + apply) einmal durch ist.
  // Vorher ist `session === null` mehrdeutig ("laedt noch" vs. "ausgeloggt")
  // — RequireAuth wartet auf dieses Flag, statt sofort zu redirecten.
  const [sessionLoaded, setSessionLoaded] = useState(false)
  // Dedupe-Marker: speichert das zuletzt verarbeitete Access-Token (oder
  // `null` fuer "keine Session"). `onAuthStateChange` feuert direkt nach
  // `getSession()` mit `INITIAL_SESSION` und liefert das identische Token —
  // ohne diesen Vergleich wuerde `fetchMe` doppelt laufen.
  const lastTokenRef = useRef<string | null | undefined>(undefined)

  // Beim Mount: GoTrue parsed den URL-Hash (Magic-Link-Token) intern, wenn
  // wir `getSession()` aufrufen — unser React-State muss danach synchron
  // nachziehen, sonst sieht die App weiter `session === null` und der
  // Invitation-Flow schickt den frisch-eingeloggten User aufs Login zurueck.
  // `onAuthStateChange` haelt uns danach permanent synchron (refresh,
  // signOut, signIn aus einem anderen Tab/Reload).
  useEffect(() => {
    let cancelled = false
    // Generationszaehler gegen ein Ueberholmanoever: `bootstrap()` und der
    // `onAuthStateChange`-Handler laufen nebenlaeufig auf derselben `apply()`.
    // auth-js stellt einem frisch registrierten Subscriber sofort ein
    // `INITIAL_SESSION` zu (`GoTrueClient.js`), sodass zwei `apply()`-Laeufe
    // fuer dieselbe Session starten koennen — einer davon mit einem
    // Netzwerk-`fetchMe` dazwischen. Ohne Zaehler konnte der langsamere Lauf
    // nach einem bereits erfolgten Ablauf-Logout `setSession(X)` schreiben und
    // den Logout damit stillschweigend zuruecknehmen (Security-Review
    // MEDIUM-3). Jetzt gewinnt immer der zuletzt gestartete Lauf.
    let generation = 0

    async function apply(nextSession: Session | null) {
      // Dedupe VOR dem Generationszaehler — die Reihenfolge ist der ganze
      // Punkt. auth-js stellt einem frisch registrierten Subscriber sofort ein
      // `INITIAL_SESSION` mit derselben Session zu, die `bootstrap()` gerade
      // verarbeitet. Zaehlt dieser Zweitlauf mit, erklaert er den noch
      // laufenden Erstlauf fuer ueberholt und kehrt selbst hier oben um —
      // niemand committet, jede eingeloggte Session landet auf `/login`.
      // Ein Lauf, der nichts tut, darf keinen Lauf entwerten, der etwas tut.
      const nextToken = nextSession?.access_token ?? null
      if (lastTokenRef.current === nextToken) {
        return
      }
      lastTokenRef.current = nextToken
      const current = ++generation
      const stale = () => cancelled || current !== generation
      // Ablaufpruefung vor JEDEM Commit, nicht nur beim Boot: eine ueber der
      // Obergrenze liegende "angemeldet bleiben"-Session wird nie committed,
      // egal ob sie aus `getSession()`, einem `TOKEN_REFRESHED` oder einem
      // anderen Tab kommt. Erzwingt einen vollen Logout inkl. GoTrue-seitigem
      // `signOut` — kein 2FA-Bypass beim naechsten Login. Der Dedupe oben
      // sorgt dafuer, dass das pro Session genau einmal passiert: ein zweiter
      // `signOut` fuer denselben Token laeuft in einen 403 (Refresh-Token
      // bereits widerrufen).
      if (nextSession !== null && sessionOverMaxAge()) {
        await supabase.auth.signOut()
        clearRememberMarker()
        purgeStoredSessionFrom('local')
        if (stale()) return
        lastTokenRef.current = null
        setMe(null)
        setSession(null)
        return
      }
      // Aal1-Session mit faelligem zweiten Faktor zurueckhalten — egal ob der
      // Event aus signIn, einem Reload oder einem Refresh stammt. Erst der
      // Challenge-Schritt der LoginPage hebt sie auf aal2 und committet dann.
      if (nextSession !== null && (await mfaStepUpPending())) {
        if (stale()) return
        setMe(null)
        setSession(null)
        return
      }
      const resolved = await resolveMe(nextSession?.access_token)
      if (stale()) return
      setMe(resolved)
      setSession(nextSession)
    }

    async function bootstrap() {
      const { data } = await supabase.auth.getSession()
      if (cancelled) return
      await apply(data.session)
      if (cancelled) return
      setSessionLoaded(true)
    }
    void bootstrap()

    const { data } = supabase.auth.onAuthStateChange((event, nextSession) => {
      // Ein Logout — egal aus welcher Quelle, auch „Ueberall abmelden" auf der
      // Account-Seite oder der Broadcast aus einem anderen Tab — beendet auch
      // den "angemeldet bleiben"-Modus. Ohne das erbte der naechste Login ohne
      // Checkbox (OAuth, Magic-Link, Invitation) den stehengebliebenen Marker
      // und landete ungefragt auf der Platte (Security-Review MEDIUM-6).
      if (event === 'SIGNED_OUT') {
        clearRememberMarker()
      }
      void apply(nextSession)
    })

    return () => {
      cancelled = true
      data.subscription.unsubscribe()
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string, remember: boolean) => {
    // Marker VOR `signInWithPassword` setzen/loeschen: der delegierende
    // Storage-Adapter (`lib/supabase.ts`) liest ihn live und muss die gleich
    // folgende Session direkt ins richtige Backend schreiben — kein
    // nachtraeglicher Storage-Wechsel.
    const previousMarker = readRememberMarker()
    if (remember) {
      markRememberedLogin()
    } else {
      clearRememberMarker()
    }
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      // Fehlversuch aendert den Modus nicht: den vorherigen Marker exakt
      // wiederherstellen, statt pauschal zu loeschen. Ein Tippfehler im
      // Passwort duerfte sonst eine laufende "angemeldet bleiben"-Session in
      // einem anderen Tab ins falsche Backend umlenken.
      restoreRememberMarker(previousMarker)
      throw new Error(error.message)
    }
    // Der Moduswechsel laesst den Session-Blob des vorherigen Modus im nun
    // unzustaendigen Backend liegen. Blieb er dort, war er eine Datenleiche
    // ausserhalb jeder Ablaufpruefung — der Marker, an dem die Kappung haengt,
    // wurde ja gerade umgestellt (Security-Review HIGH-1).
    purgeStoredSessionFrom(remember ? 'session' : 'local')
    // Steht eine Step-up-Challenge aus, die aal1-Session NICHT committen — die
    // LoginPage fordert dann den TOTP-Code an. `apply()` (via onAuthStateChange)
    // haelt dieselbe Session ohnehin zurueck; hier signalisieren wir es nur an
    // den Aufrufer.
    if (await mfaStepUpPending()) {
      return { mfaRequired: true }
    }
    const resolved = await resolveMe(data.session?.access_token)
    lastTokenRef.current = data.session?.access_token ?? null
    setMe(resolved)
    setSession(data.session)
    return { mfaRequired: false }
  }, [])

  const signOut = useCallback(async () => {
    // Reihenfolge wichtig: `signOut()` entfernt den Session-Key ueber den
    // delegierenden Adapter, der dafuer noch den AKTUELLEN Marker braucht
    // (sonst sucht er im falschen Backend und der Token bleibt als Datenleiche
    // liegen). Den Marker selbst raeumt der `SIGNED_OUT`-Handler oben ab.
    await supabase.auth.signOut()
    clearRememberMarker()
    purgeStoredSessionFrom('local')
    lastTokenRef.current = null
    setSession(null)
    setMe(null)
  }, [])

  // Expliziter Re-Fetch ohne Token-Wechsel — z. B. nach Lazy-Seed eines
  // Personal-Workspace. Nur sinnvoll, wenn eine aktive Session vorliegt.
  const refreshMe = useCallback(async () => {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (!token) return
    const resolved = await resolveMe(token)
    setMe(resolved)
  }, [])

  const value = useMemo<SessionValue>(
    () => ({ session, sessionLoaded, me, signIn, signOut, refreshMe }),
    [session, sessionLoaded, me, signIn, signOut, refreshMe],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
