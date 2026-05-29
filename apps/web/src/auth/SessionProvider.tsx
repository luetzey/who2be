import { type ReactNode, useCallback, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'

import { fetchMe } from '@/api/client'
import type { Me } from '@/api/types'

import { supabase } from '../lib/supabase'
import { SessionContext, type SessionValue } from './session-context'

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [me, setMe] = useState<Me | null>(null)

  const signIn = useCallback(async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      throw new Error(error.message)
    }
    // Erst `me` holen, dann beides atomar setzen. Vertauschte Reihenfolge
    // produziert einen Zwischen-Commit mit session=set+me=null: LoginPage
    // redirected dann sofort zu `/`, DefaultWorkspaceRedirect wirft mangels
    // `default_workspace_id` zurueck auf `/login`, und Chrome bricht die
    // Schleife mit "Throttling navigation to prevent the browser from hanging"
    // ab — sichtbar als weisser Screen. Beide setState-Calls liegen jetzt im
    // selben Microtask nach dem await, React 18 batcht das zu einem Commit.
    let resolved: Me | null = null
    try {
      resolved = await fetchMe(data.session?.access_token ?? '')
    } catch {
      resolved = null
    }
    setMe(resolved)
    setSession(data.session)
  }, [])

  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
    setSession(null)
    setMe(null)
  }, [])

  const value = useMemo<SessionValue>(
    () => ({ session, me, signIn, signOut }),
    [session, me, signIn, signOut],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
