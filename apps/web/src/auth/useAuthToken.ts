import { useAuthTokenContext } from './auth-token-context'
import { useSession } from './session-context'

// Liefert den Bearer-Token fuer API-Calls. Praezedenz: expliziter
// `w2b_`-Override (Settings/Headless) > Supabase-JWT der aktuellen Session.
// Leerer String, wenn beides fehlt — `api/client.ts` laesst den
// Authorization-Header dann weg, und die API antwortet sauber 401.
export function useAuthToken(): string {
  const { overrideToken } = useAuthTokenContext()
  const { session } = useSession()
  if (overrideToken !== null && overrideToken !== '') {
    return overrideToken
  }
  return session?.access_token ?? ''
}
