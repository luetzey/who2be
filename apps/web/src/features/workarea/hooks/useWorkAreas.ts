import { useCallback } from 'react'

import type { WorkArea } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

export interface UseWorkAreasResult {
  areas: WorkArea[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Sichtbare Arbeitsbereiche des Workspace (ADR-0047).
 *
 * Der Scope kommt serverseitig: Menschen ab Rolle `editor` sehen alles — auch
 * die privaten Bereiche fremder Agenten —, Viewer nur `scope='shared'`.
 * „Privat" ist eine Grenze zwischen Agenten, keine gegenueber dem Betreiber.
 */
export function useWorkAreas(): UseWorkAreasResult {
  const api = useApi()
  const loader = useCallback(() => api.listWorkAreas(), [api])
  const { data, loading, error, reload } = useListData<WorkArea>(loader)
  return { areas: data, loading, error, reload }
}
