// usePlaybookSearch — kapselt das Laden + Filtern der Playbook-Liste fuer den
// PlaybookPicker. Haelt `useApi()` aus der Praesentations-Komponente heraus
// (Frontend-Standard: Datenholen gehoert nicht in tief verschachtelte UI).
import { useEffect, useState } from 'react'

import type { Playbook } from '@/api/types'
import { useApi } from '@/api/useApi'

export interface UsePlaybookSearch {
  query: string
  setQuery: (query: string) => void
  selected: Playbook | null
  setSelected: (playbook: Playbook | null) => void
  loading: boolean
  filtered: Playbook[]
}

export function usePlaybookSearch(
  open: boolean,
  initialTargetId: string | undefined,
): UsePlaybookSearch {
  const api = useApi()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Playbook | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setQuery('')
    api
      .listPlaybooks()
      .then((list) => {
        setPlaybooks(list)
        setSelected(
          initialTargetId !== undefined
            ? (list.find((p) => p.id === initialTargetId) ?? null)
            : null,
        )
      })
      .catch(() => {
        setPlaybooks([])
        setSelected(null)
      })
      .finally(() => setLoading(false))
  }, [open, api, initialTargetId])

  const filtered =
    query.trim() === ''
      ? playbooks
      : playbooks.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))

  return { query, setQuery, selected, setSelected, loading, filtered }
}
