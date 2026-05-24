import { type ReactNode, useCallback, useMemo, useState } from 'react'

import { AuthTokenContext, type AuthTokenValue } from './auth-token-context'

export function AuthTokenProvider({ children }: { children: ReactNode }) {
  const [overrideToken, setOverrideTokenState] = useState<string | null>(null)

  const setOverrideToken = useCallback((token: string | null) => {
    setOverrideTokenState(token === '' ? null : token)
  }, [])

  const value = useMemo<AuthTokenValue>(
    () => ({ overrideToken, setOverrideToken }),
    [overrideToken, setOverrideToken],
  )

  return <AuthTokenContext.Provider value={value}>{children}</AuthTokenContext.Provider>
}
