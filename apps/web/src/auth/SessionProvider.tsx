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
    setSession(data.session)
    // Identity + Memberships zusammen mit der Session laden — die UI redirected
    // nach `/w/{default_workspace_id}/...`, sobald `me` gesetzt ist.
    try {
      const resolved = await fetchMe(data.session?.access_token ?? '')
      setMe(resolved)
    } catch {
      setMe(null)
    }
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
