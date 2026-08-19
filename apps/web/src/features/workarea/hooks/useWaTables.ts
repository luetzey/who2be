import { useCallback } from 'react'

import type { WaTable } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

export interface UseWaTablesResult {
  tables: WaTable[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Tabellen-Katalog eines Arbeitsbereichs (ADR-0049).
 *
 * Bewusst nur der Katalog: `row_count` ist auf diesem Pfad immer `null`, weil
 * die Zeilenzahl in der SQLite-Datei der Area liegt und nur der describe-Pfad
 * sie zaehlt. Sie hier nachzuladen hiesse ein describe pro Zeile — ein N+1 fuer
 * eine Zahl, die in der Liste niemand braucht.
 *
 * Der Katalog ist ausserdem die einzige Quelle des Tabellen-NAMENS: describe
 * liefert Schema, Zeilenzahl und Konventionen, aber keinen Namen. Deshalb ist
 * die Tabellen-Route bereichs-geschachtelt (Muster `useWorkAreaArtifacts`).
 */
export function useWaTables(areaId: string): UseWaTablesResult {
  const api = useApi()
  const loader = useCallback(() => api.listWaTables(areaId), [api, areaId])
  const { data, loading, error, reload } = useListData<WaTable>(loader)
  return { tables: data, loading, error, reload }
}
