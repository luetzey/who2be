import { createContext, useContext } from 'react'

import { useWorkspacePath } from '@/auth/useWorkspacePath'

/**
 * Oeffentliche Hilfe ohne Sitzung (Owner W-B, UX-Audit K5): `true` blendet
 * alles aus, was ein Konto braucht (Tutorials, Fortschritt, „Was ist neu“,
 * Admin-Seiten), und interne Links bleiben `/help/…` statt `/w/<id>/help/…`.
 * Ohne Provider gilt der Workspace-Modus.
 */
export const PublicHelpContext = createContext(false)

/** `true` in der oeffentlichen Hilfe (`/help/*` ohne Sitzung). */
export function usePublicHelp(): boolean {
  return useContext(PublicHelpContext)
}

/** Ziel eines Hilfe-internen Pfads (`/help/<slug>`) im aktuellen Modus. */
export function useHelpPath(): (relative: string) => string {
  const wsPath = useWorkspacePath()
  const isPublic = usePublicHelp()
  return isPublic ? (relative) => (relative.startsWith('/') ? relative : `/${relative}`) : wsPath
}
