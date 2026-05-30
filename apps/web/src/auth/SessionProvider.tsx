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

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [me, setMe] = useState<Me | null>(null)
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
      const resolved = await resolveMe(nextSession?.access_token)
      if (cancelled) return
      setMe(resolved)
      setSession(nextSession)
    }

    async function bootstrap() {
      const { data } = await supabase.auth.getSession()
      if (cancelled) return
      await apply(data.session)
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
    const resolved = await resolveMe(data.session?.access_token)
    lastTokenRef.current = data.session?.access_token ?? null
    setMe(resolved)
    setSession(data.session)
  }, [])

  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
    lastTokenRef.current = null
    setSession(null)
    setMe(null)
  }, [])

  const value = useMemo<SessionValue>(
    () => ({ session, me, signIn, signOut }),
    [session, me, signIn, signOut],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
