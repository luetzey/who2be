import { type ReactNode, useCallback, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'

import { supabase } from '../lib/supabase'
import { SessionContext, type SessionValue } from './session-context'

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)

  const signIn = useCallback(async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      throw new Error(error.message)
    }
    setSession(data.session)
  }, [])

  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
    setSession(null)
  }, [])

  const value = useMemo<SessionValue>(
    () => ({ session, signIn, signOut }),
    [session, signIn, signOut],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
