import { useState } from 'react'

import type { TokenCreated, TokenInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface UseTokenMutationsResult {
  createError: string | null
  /** Klartext-Reveal aus Create ODER Rotate — genau einmal anzeigbar. */
  revealed: TokenCreated | null
  dismissRevealed: () => void
  createToken: (input: TokenInput) => Promise<TokenCreated | null>
  renameToken: (id: string, name: string) => Promise<boolean>
  rotateToken: (id: string) => Promise<TokenCreated | null>
  revokeToken: (id: string) => Promise<void>
}

/**
 * Token-Mutationen (Create/Rename/Rotate/Revoke) inkl. dem einmaligen
 * Klartext-Reveal. Create und Rotate liefern beide ein frisches Secret →
 * gemeinsamer `revealed`-Slot. Mutationsfehler beim Rename/Rotate/Revoke gehen
 * ueber Toast; der Listen-`reload` ist die visuelle Erfolgsbestaetigung.
 */
export function useTokenMutations(reload: () => void): UseTokenMutationsResult {
  const api = useApi()
  const [createError, setCreateError] = useState<string | null>(null)
  const [revealed, setRevealed] = useState<TokenCreated | null>(null)

  async function createToken(input: TokenInput): Promise<TokenCreated | null> {
    setCreateError(null)
    try {
      const result = await api.createToken(input)
      setRevealed(result)
      reload()
      notify.success(i18n.t('tokens:create.created', { name: input.name }))
      return result
    } catch (cause) {
      setCreateError(describeError(cause))
      return null
    }
  }

  async function renameToken(id: string, name: string): Promise<boolean> {
    try {
      await api.renameToken(id, { name })
      reload()
      return true
    } catch (cause) {
      notify.error(describeError(cause))
      return false
    }
  }

  async function rotateToken(id: string): Promise<TokenCreated | null> {
    try {
      const result = await api.rotateToken(id)
      setRevealed(result)
      reload()
      notify.success(i18n.t('tokens:rotate.rotated'))
      return result
    } catch (cause) {
      notify.error(describeError(cause))
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

  function dismissRevealed(): void {
    setRevealed(null)
  }

  return {
    createError,
    revealed,
    dismissRevealed,
    createToken,
    renameToken,
    rotateToken,
    revokeToken,
  }
}
