import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'

import { fetchMe } from '@/api/client'
import type { Me } from '@/api/types'

import { config } from '../config'
import { supabase } from '../lib/supabase'
import { SessionContext, type SessionValue } from './session-context'

// "Angemeldet bleiben" (Issue #430, ADR-0052). Zwei localStorage-Keys, gesetzt
// vom Login (`signIn`, s.u.) und gelesen von der Ablaufpruefung beim Boot
// sowie vom delegierenden Storage-Adapter (`lib/supabase.ts`). Bewusst als
// lokale String-Literale statt Import aus `lib/supabase.ts`: viele bestehende
// Tests mocken `@/lib/supabase` minimal (nur `{ supabase: {...} }|`); ein
// echter Cross-Import wuerde deren Mocks brechen, sobald SessionProvider eine
// dort nicht gestubte Funktion aufruft. Beide Dateien muessen bei einer
// Aenderung der Key-Namen synchron gehalten werden.
const REMEMBER_ME_KEY = 'who2be.auth.remember'
const SIGNED_IN_AT_KEY = 'who2be.auth.signed_in_at'
const SESSION_MAX_AGE_MS = config.sessionMaxAgeHours * 60 * 60 * 1000

/** Setzt Remember-Flag + Login-Zeitstempel VOR `signInWithPassword` — der
 * Storage-Adapter liest das Flag live und muss die gleich folgende Session
 * direkt ins richtige Backend (`localStorage`) schreiben. */
function markRememberedLogin(): void {
  try {
    window.localStorage.setItem(REMEMBER_ME_KEY, 'true')
    window.localStorage.setItem(SIGNED_IN_AT_KEY, String(Date.now()))
  } catch {
    // Privacy-Mode/Quota — der Login funktioniert weiter, nur ohne Persistenz
    // ueber den Tab hinaus (faellt effektiv auf Tab-Lifetime zurueck).
  }
}

/** Loescht beide Keys — Logout (jeder Tab) und erzwungener Ablauf-Logout. */
function clearRememberedSession(): void {
  try {
    window.localStorage.removeItem(REMEMBER_ME_KEY)
    window.localStorage.removeItem(SIGNED_IN_AT_KEY)
  } catch {
    // s.o. — nichts zu tun, es war ohnehin nichts persistiert.
  }
}

function readSignedInAt(): number | null {
  try {
    const raw = window.localStorage.getItem(SIGNED_IN_AT_KEY)
    if (raw === null) return null
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
  } catch {
    return null
  }
}

// `signed_in_at` existiert NUR, wenn beim Login der Haken gesetzt war
// (`markRememberedLogin`) — eine normale Tab-Lifetime-Session hat keinen
// Zeitstempel und wird hier deshalb nie als abgelaufen erkannt (sie endet
// ohnehin mit dem Tab, AC 2 bleibt unberuehrt).
function rememberedSessionExpired(): boolean {
  const signedInAt = readSignedInAt()
  if (signedInAt === null) return false
  return Date.now() - signedInAt > SESSION_MAX_AGE_MS
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

    async function apply(nextSession: Session | null) {
      const nextToken = nextSession?.access_token ?? null
      if (lastTokenRef.current === nextToken) {
        return
      }
      lastTokenRef.current = nextToken
      // Aal1-Session mit faelligem zweiten Faktor zurueckhalten — egal ob der
      // Event aus signIn, einem Reload oder einem Refresh stammt. Erst der
      // Challenge-Schritt der LoginPage hebt sie auf aal2 und committet dann.
      if (nextSession !== null && (await mfaStepUpPending())) {
        if (cancelled) return
        setMe(null)
        setSession(null)
        return
      }
      const resolved = await resolveMe(nextSession?.access_token)
      if (cancelled) return
      setMe(resolved)
      setSession(nextSession)
    }

    async function bootstrap() {
      const { data } = await supabase.auth.getSession()
      if (cancelled) return
      // Ablaufpruefung VOR dem Commit (Issue #430, ADR-0052): ueberschreitet
      // eine "angemeldet bleiben"-Session die absolute Obergrenze, erzwingt
      // das einen vollen Logout inkl. GoTrue-seitigem `signOut` — kein
      // Committen der (technisch noch gueltigen) Session, kein 2FA-Bypass
      // beim naechsten Login. Betrifft nur neue Tabs/Browser-Neustart: ein
      // bereits offener, laufender Tab wird hier nicht neu geprueft.
      if (data.session !== null && rememberedSessionExpired()) {
        await supabase.auth.signOut()
        clearRememberedSession()
        if (cancelled) return
        await apply(null)
      } else {
        await apply(data.session)
      }
      if (cancelled) return
      setSessionLoaded(true)
    }
    void bootstrap()

    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      void apply(nextSession)
    })

    return () => {
      cancelled = true
      data.subscription.unsubscribe()
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string, remember: boolean) => {
    // VOR signInWithPassword setzen/loeschen: der delegierende Storage-
    // Adapter (`lib/supabase.ts`) liest das Flag live und muss die gleich
    // folgende Session direkt ins richtige Backend schreiben — kein
    // nachtraeglicher Storage-Wechsel.
    if (remember) {
      markRememberedLogin()
    } else {
      clearRememberedSession()
    }
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      // Fehlgeschlagener Login: kein Datenrest eines evtl. gesetzten
      // Remember-Flags ohne zugehoerige Session.
      clearRememberedSession()
      throw new Error(error.message)
    }
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
    // delegierenden Adapter, der dafuer noch das AKTUELLE Remember-Flag
    // braucht (sonst sucht er im falschen Backend und der Token bleibt als
    // Datenleiche liegen). Das Flag selbst erst danach loeschen.
    await supabase.auth.signOut()
    clearRememberedSession()
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
