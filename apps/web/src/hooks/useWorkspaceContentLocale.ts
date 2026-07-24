import { useEffect, useState } from 'react'

import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'
import { useWorkspaceId } from '@/auth/useWorkspaceId'

// Fallback, falls (noch) kein Workspace-Content-Locale ermittelbar ist —
// deckt sich mit dem Backend-Default (`Workspace.content_locale` DEFAULT
// 'de'), ist aber bewusst als eigenes Literal gefuehrt statt aus dem
// UI-String-i18n (`@/i18n`) importiert: Content-Sprache und UI-Sprache sind
// unabhaengige Konzepte, die heute zufaellig dasselbe Set (de/en) teilen.
const FALLBACK_CONTENT_LOCALE = 'de'

/**
 * Inhalts-Sprache des aktuellen Workspace (`Workspace.content_locale`,
 * ADR-0045) — Default fuer neu angelegte Elemente (Persona/Playbook/
 * Resource/Tool/System-Prompt). Der `/v1/me`-Snapshot (Membership-Liste)
 * fuehrt das Feld nicht; Quelle ist deshalb ein Best-effort-Nachladen ueber
 * `GET .../organizations/{orgId}/workspaces` (Track-C-Endpoint), sobald sich
 * die Organisation des aktiven Workspace aus `me` auflösen laesst.
 *
 * Bleibt beim Fallback, solange der Fetch laeuft, kein Treffer gefunden wird
 * oder er fehlschlaegt — Create-Flows funktionieren trotzdem sofort
 * (Sprache bleibt manuell waehlbar).
 */
export function useWorkspaceContentLocale(): string {
  const api = useApi()
  const { me } = useSession()
  const workspaceId = useWorkspaceId()
  const [contentLocale, setContentLocale] = useState<string>(FALLBACK_CONTENT_LOCALE)

  useEffect(() => {
    if (me === null || workspaceId === '') {
      return
    }
    let orgId: string | null = null
    for (const org of me.organizations) {
      if (org.workspaces.some((ws) => ws.id === workspaceId)) {
        orgId = org.id
        break
      }
    }
    if (orgId === null) {
      return
    }
    let cancelled = false
    api
      .listOrgWorkspaces(orgId)
      .then((list) => {
        if (cancelled) return
        const current = list.find((ws) => ws.id === workspaceId)
        if (current?.content_locale) {
          setContentLocale(current.content_locale)
        }
      })
      .catch(() => {
        // Fallback bleibt bestehen — kein Retry, kein Error-UI (reine
        // Vorbelegung eines Felds, das der User ohnehin aendern kann).
      })
    return () => {
      cancelled = true
    }
  }, [api, me, workspaceId])

  return contentLocale
}
