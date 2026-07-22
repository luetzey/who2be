import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'

import { fetchMe } from '@/api/client'
import type { Me } from '@/api/types'

import { supabase } from '../lib/supabase'
import { SessionContext, type SessionValue } from './session-context'

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
      await apply(data.session)
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

  const signIn = useCallback(async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
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
    await supabase.auth.signOut()
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
