import { useState } from 'react'

import type { TokenCreated, TokenInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useAuthTokenContext } from '@/auth/auth-token-context'
import { notify } from '@/lib/feedback'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseTokenMutationsResult {
  createError: string | null
  created: TokenCreated | null
  dismissCreated: () => void
  createToken: (input: TokenInput) => Promise<TokenCreated | null>
  revokeToken: (id: string) => Promise<void>
  overrideToken: string | null
  setOverrideToken: (token: string | null) => void
}

/**
 * Kapselt Token-Create/Revoke + den Override-Token-Slot. Create-Success
 * triggert sowohl Toast als auch das inline Klartext-Reveal (`created`).
 * Revoke-Failures gehen ausschliesslich ueber Toast — der Listen-Reload
 * ist die visuelle Bestaetigung des Erfolgs.
 */
export function useTokenMutations(reload: () => void): UseTokenMutationsResult {
  const api = useApi()
  const { overrideToken, setOverrideToken } = useAuthTokenContext()
  const [createError, setCreateError] = useState<string | null>(null)
  const [created, setCreated] = useState<TokenCreated | null>(null)

  async function createToken(input: TokenInput): Promise<TokenCreated | null> {
    setCreateError(null)
    try {
      const result = await api.createToken(input)
      setCreated(result)
      reload()
      notify.success(`Token „${input.name}" angelegt. Klartext jetzt einmalig kopieren.`)
      return result
    } catch (cause) {
      setCreateError(describeError(cause))
      return null
    }
  }

  async function revokeToken(id: string): Promise<void> {
    try {
      await api.revokeToken(id)
      reload()
    } catch (cause) {
      notify.error(describeError(cause))
    }
  }

  function dismissCreated(): void {
    setCreated(null)
  }

  return {
    createError,
    created,
    dismissCreated,
    createToken,
    revokeToken,
    overrideToken,
    setOverrideToken,
  }
}
