import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '@/api/client'
import type { DashboardData } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspaceId } from '@/auth/useWorkspaceId'

interface UseDashboardResult {
  data: DashboardData | null
  loading: boolean
  error: string | null
  notFound: boolean
  // True, solange noch keine Workspace-ID resolved werden konnte (Route-Param
  // fehlt UND `me.default_workspace_id` ist leer). Dann wird bewusst KEIN
  // Request gefeuert — die Page zeigt einen Preparing-State statt eines
  // irrefuehrenden „nicht erreichbar"-/404-Fehlers.
  preparing: boolean
  page: number
  setPage: (page: number) => void
  reload: () => void
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

/**
 * Laedt das Dashboard-Aggregat fuer den aktuellen Workspace. Der
 * Activity-Feed ist seitenbasiert paginiert (Track G, 20/Seite); `page`
 * blaettert nur durch die Activity, KPIs und Status-Verteilung kommen pro
 * Antwort identisch mit. Beim Seitenwechsel bleibt die vorherige `data`
 * stehen, damit die Visuals nicht in den Lade-State zurueckfallen.
 *
 * Ein 404 (Backend noch nicht gemergt) wird explizit als `notFound`
 * ausgewiesen, damit die Page einen sauberen Empty-State statt eines roten
 * Error-Alerts zeigt.
 */
export function useDashboard(): UseDashboardResult {
  const api = useApi()
  const workspaceId = useWorkspaceId()
  const preparing = workspaceId === ''
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [page, setPage] = useState(1)

  const load = useCallback(() => {
    // Ohne aufgeloeste Workspace-ID liefe der Request gegen
    // `/v1/workspaces//dashboard` (Backend → 404, bzw. bei einem
    // Netzwerk-/CORS-Fehler der generische „nicht erreichbar"-Alert). Beides
    // ist hier kein echter Fehlerzustand, sondern „Workspace noch nicht
    // resolved" — also gar nicht erst feuern.
    if (workspaceId === '') {
      setLoading(false)
      setError(null)
      setNotFound(false)
      setData(null)
      return
    }
    setLoading(true)
    setError(null)
    setNotFound(false)
    api
      .getDashboard(page)
      .then((result) => setData(result))
      .catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 404) {
          setNotFound(true)
          setData(null)
          return
        }
        setError(describeError(cause))
      })
      .finally(() => setLoading(false))
  }, [api, page, workspaceId])

  useEffect(load, [load])

  return { data, loading, error, notFound, preparing, page, setPage, reload: load }
}
