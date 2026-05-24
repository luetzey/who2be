import { createContext, useContext } from 'react'

// In-Memory-Override fuer einen `w2b_`-API-Token. Wird in W1 nur deklariert
// und vom AuthTokenProvider gehalten — die UI dahinter (Settings-Seite,
// Token-Login) kommt erst mit W2. Keine Persistenz: react-conventions
// verbieten Auth-Tokens im localStorage, und `persistSession: false` in
// `lib/supabase.ts` haelt dieselbe Linie fuer Supabase-Sessions.
export interface AuthTokenValue {
  overrideToken: string | null
  setOverrideToken: (token: string | null) => void
}

export const AuthTokenContext = createContext<AuthTokenValue | null>(null)

export function useAuthTokenContext(): AuthTokenValue {
  const value = useContext(AuthTokenContext)
  if (value === null) {
    throw new Error('useAuthTokenContext muss innerhalb von AuthTokenProvider verwendet werden.')
  }
  return value
}
