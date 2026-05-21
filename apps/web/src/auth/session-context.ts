import type { Session } from '@supabase/supabase-js'
import { createContext, useContext } from 'react'

export interface SessionValue {
  session: Session | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

export const SessionContext = createContext<SessionValue | null>(null)

export function useSession(): SessionValue {
  const value = useContext(SessionContext)
  if (value === null) {
    throw new Error('useSession muss innerhalb von SessionProvider verwendet werden.')
  }
  return value
}
