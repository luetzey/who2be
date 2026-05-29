import { useCallback, useEffect, useState } from 'react'

import type { ResourceLink, ResourceLinkItemInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UsePlaybookResourceLinksResult {
  links: ResourceLink[]
  loading: boolean
  error: string | null
  saving: boolean
  save: (items: ResourceLinkItemInput[]) => Promise<void>
}

/**
 * Laedt und setzt die Resource-Block-Refs eines Playbooks. `save` ersetzt den
 * gesamten Stand (PUT-Semantik des Backends) und laedt danach neu.
 */
export function usePlaybookResourceLinks(
  playbookId: string | undefined,
): UsePlaybookResourceLinksResult {
  const api = useApi()
  const [links, setLinks] = useState<ResourceLink[]>([])
  const [loading, setLoading] = useState(playbookId !== undefined)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    if (playbookId === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    api
      .listPlaybookResourceLinks(playbookId)
      .then(setLinks)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, playbookId])

  useEffect(load, [load])

  const save = useCallback(
    async (items: ResourceLinkItemInput[]) => {
      if (playbookId === undefined) {
        return
      }
      setSaving(true)
      try {
        const updated = await api.setPlaybookResourceLinks(playbookId, items)
        setLinks(updated)
        notify.success('Block-Verknuepfungen gespeichert.')
      } catch (cause: unknown) {
        notify.error(describeError(cause))
      } finally {
        setSaving(false)
      }
    },
    [api, playbookId],
  )

  return { links, loading, error, saving, save }
}
