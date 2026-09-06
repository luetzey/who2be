import { createContext, useContext } from 'react'

// In-Memory-Override fuer einen `w2b_`-API-Token. Wird in W1 nur deklariert
// und vom AuthTokenProvider gehalten — die UI dahinter (Settings-Seite,
// Token-Login) kommt erst mit W2. Keine Persistenz: react-conventions
// verbieten Auth-Tokens im localStorage. Supabase-Sessions liegen aus
// demselben Grund per Default im `sessionStorage` (Tab-Lifetime statt Disk);
// seit ADR-0052 gibt es dazu die opt-in-Ausnahme "Angemeldet bleiben" mit
// absoluter Obergrenze — siehe `lib/supabase.ts` + `lib/remember-session.ts`.
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
