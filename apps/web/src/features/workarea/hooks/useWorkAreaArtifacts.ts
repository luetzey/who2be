import { useCallback } from 'react'

import type { WaArtifact } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

export interface UseWorkAreaArtifactsResult {
  artifacts: WaArtifact[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Metadaten-Liste eines Arbeitsbereichs.
 *
 * Bewusst nur Metadaten: der Inhalt eines Elements kommt einzeln ueber
 * `useArtifact` (Markdown mit Ankern). Genau deshalb ist die Artifact-Route
 * bereichs-geschachtelt — die Detail-Seite braucht diese Liste fuer Typ,
 * Sensibilitaet und Zeitpunkt, die der Inhalts-Endpunkt nicht mitliefert.
 */
export function useWorkAreaArtifacts(areaId: string): UseWorkAreaArtifactsResult {
  const api = useApi()
  const loader = useCallback(() => api.listWaArtifacts(areaId), [api, areaId])
  const { data, loading, error, reload } = useListData<WaArtifact>(loader)
  return { artifacts: data, loading, error, reload }
}
