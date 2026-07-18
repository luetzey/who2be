// useToolSearch — kapselt das Laden + Filtern der External-Tools fuer den
// ToolPicker. Haelt `useApi()` aus der Praesentations-Komponente heraus
// (Frontend-Standard, analog usePlaybookSearch/useResourceSearch).
//
// Nur `current_status === 'active'` Tools sind waehlbar: eine `tool-ref`-Pill
// referenziert den Alias und loest beim Rendern ausschliesslich gegen die
// aktive Version auf (ToolRefResolver-Vertrag, Backend WP-2/3). Ein
// Draft/Review/Inactive-Tool waere zwar waehlbar, jede Vorschau/jedes
// Rendering zeigte aber bis zur Promotion einen Miss — dieses verwirrende
// Zwischenstadium blendet der Picker aus (Entscheidung WP-5, analog dem
// "nur aktive Bindung" Rendering-Vertrag im Blueprint).
import { useEffect, useState } from 'react'

import type { ExternalTool } from '@/api/types'
import { useApi } from '@/api/useApi'

export interface UseToolSearch {
  query: string
  setQuery: (query: string) => void
  selected: ExternalTool | null
  setSelected: (tool: ExternalTool | null) => void
  loading: boolean
  filtered: ExternalTool[]
}

export function useToolSearch(
  open: boolean,
  initialTargetId: string | undefined,
): UseToolSearch {
  const api = useApi()
  const [tools, setTools] = useState<ExternalTool[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<ExternalTool | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setQuery('')
    api
      .listExternalTools()
      .then((list) => {
        const active = list.filter((tool) => tool.current_status === 'active')
        setTools(active)
        setSelected(
          initialTargetId !== undefined
            ? (active.find((tool) => tool.alias === initialTargetId) ?? null)
            : null,
        )
      })
      .catch(() => {
        setTools([])
        setSelected(null)
      })
      .finally(() => setLoading(false))
  }, [open, api, initialTargetId])

  const filtered =
    query.trim() === ''
      ? tools
      : tools.filter((tool) => {
          const q = query.toLowerCase()
          return (
            tool.name.toLowerCase().includes(q) ||
            tool.alias.toLowerCase().includes(q) ||
            tool.content.display_name.toLowerCase().includes(q)
          )
        })

  return { query, setQuery, selected, setSelected, loading, filtered }
}
