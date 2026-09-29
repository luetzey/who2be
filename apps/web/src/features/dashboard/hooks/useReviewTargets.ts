import { useEffect, useState } from 'react'

import type { DashboardStatusDistribution, VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { versionDiffSearch } from '@/components/version/versionDeepLink'

// Audit A4: Der Review-Banner auf dem Dashboard fuehrt direkt zur Pruefung.
// Das Dashboard-Aggregat liefert nur Zaehler; welche Versionen konkret in
// Review liegen, steht erst in den Listen. Geladen werden deshalb nur die
// Listen der Typen, deren Zaehler `review > 0` ist — und nur, solange die
// Gesamtzahl klein genug fuer Direktlinks ist. Darueber (oder wenn die
// Listen nicht alle Treffer liefern) bleibt es beim Link auf die gefilterte
// Liste; die API bleibt unveraendert.

export const MAX_DIRECT_REVIEW_LINKS = 3

export type ReviewEntityType = 'persona' | 'playbook' | 'resource'

const ENTITY_TYPES: readonly ReviewEntityType[] = ['persona', 'playbook', 'resource']

const LIST_PATH: Record<ReviewEntityType, string> = {
  persona: '/personas',
  playbook: '/playbooks',
  resource: '/resources',
}

export interface ReviewTarget {
  type: ReviewEntityType
  id: string
  name: string
  version: number
  /** Workspace-relativer Pfad auf die Pruefansicht (`?tab=versions&diff=<n>`). */
  path: string
}

export interface ReviewListLink {
  type: ReviewEntityType
  count: number
  /** Workspace-relativer Pfad auf die nach `review` gefilterte Liste. */
  path: string
}

export interface ReviewTargets {
  /** Direktlinks — gesetzt, wenn jede offene Version eindeutig gefunden wurde. */
  targets: ReviewTarget[] | null
  /** Fallback je Typ mit offenen Reviews: die gefilterte Liste. */
  lists: ReviewListLink[]
}

interface ListItem {
  id: string
  name: string
  current_version: number
  current_status?: VersionStatus
}

/** Reine Ableitung der Listen-Links aus der Status-Verteilung. */
export function reviewListLinks(distribution: DashboardStatusDistribution | undefined): ReviewListLink[] {
  if (distribution === undefined) return []
  return ENTITY_TYPES.flatMap((type) => {
    const count = distribution[type]?.review ?? 0
    return count > 0 ? [{ type, count, path: `${LIST_PATH[type]}?status=review` }] : []
  })
}

export function useReviewTargets(
  pendingReviews: number,
  distribution: DashboardStatusDistribution | undefined,
): ReviewTargets {
  const api = useApi()
  const lists = reviewListLinks(distribution)
  const wanted = pendingReviews > 0 && pendingReviews <= MAX_DIRECT_REVIEW_LINKS
  // Stabiler Schluessel statt Objekt-Identitaet: das Dashboard laedt beim
  // Blaettern der Activity neu, die Zaehler bleiben aber meist gleich.
  const key = wanted ? lists.map((l) => `${l.type}:${l.count}`).join(',') : ''
  const [state, setState] = useState<{ key: string; targets: ReviewTarget[] | null }>({
    key: '',
    targets: null,
  })

  useEffect(() => {
    if (key === '') return
    let cancelled = false
    const types = key.split(',').map((entry) => entry.split(':')[0] as ReviewEntityType)
    const loaders: Record<ReviewEntityType, () => Promise<ListItem[]>> = {
      persona: () => api.listPersonas(),
      playbook: () => api.listPlaybooks(),
      resource: () => api.listResources(),
    }
    Promise.all(
      types.map((type) =>
        loaders[type]().then((items) =>
          items
            .filter((item) => item.current_status === 'review')
            .map<ReviewTarget>((item) => ({
              type,
              id: item.id,
              name: item.name,
              version: item.current_version,
              path: `${LIST_PATH[type]}/${item.id}${versionDiffSearch(item.current_version)}`,
            })),
        ),
      ),
    )
      .then((perType) => {
        if (cancelled) return
        const found = perType.flat()
        // Nur wenn die Listen genau die gezaehlten Versionen liefern, sind die
        // Direktlinks vollstaendig; sonst (Paging, Rennen mit einem Status-
        // wechsel) waere die Auswahl stillschweigend unvollstaendig.
        setState({ key, targets: found.length === pendingReviews ? found : null })
      })
      .catch(() => {
        if (!cancelled) setState({ key, targets: null })
      })
    return () => {
      cancelled = true
    }
  }, [api, key, pendingReviews])

  return { targets: key !== '' && state.key === key ? state.targets : null, lists }
}
