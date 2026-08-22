import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '@/api/client'
import type { Playbook, PlaybookRef } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface UsePlaybookComposesResult {
  /** Geordnete Liste der Sub-Playbooks (Kinder). */
  children: Playbook[]
  /** Backlinks — welche Composites enthalten dieses Playbook? */
  parents: PlaybookRef[]
  loading: boolean
  error: string | null
  saving: boolean
  /** Ersetzt die Kinder-Liste (Set-Replace, PUT-Semantik). */
  save: (childIds: string[]) => Promise<void>
}

/**
 * Laedt und setzt die Composite-Relation eines Playbooks.
 * `save` ersetzt die gesamte Kinder-Liste (PUT-Semantik).
 *
 * Faellt auf 404 zurueck, wenn Backend den Endpoint noch nicht kennt
 * (leere Listen statt Fehlerbanner).
 */
export function usePlaybookComposes(
  playbookId: string | undefined,
): UsePlaybookComposesResult {
  const api = useApi()
  const [children, setChildren] = useState<Playbook[]>([])
  const [parents, setParents] = useState<PlaybookRef[]>([])
  const [loading, setLoading] = useState(playbookId !== undefined)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    if (playbookId === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([
      api.listPlaybookComposes(playbookId).catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 404) return []
        throw cause
      }),
      api.listPlaybookComposedBy(playbookId).catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 404) return []
        throw cause
      }),
    ])
      .then(([c, p]) => {
        setChildren(c)
        setParents(p)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, playbookId])

  useEffect(load, [load])

  const save = useCallback(
    async (childIds: string[]) => {
      if (playbookId === undefined) {
        return
      }
      setSaving(true)
      try {
        const updated = await api.setPlaybookComposes(playbookId, childIds)
        setChildren(updated)
        notify.success(i18n.t('common:toast.compositionSaved'))
      } catch (cause: unknown) {
        if (cause instanceof ApiError && cause.status === 409) {
          notify.error(i18n.t('common:errors.cycleRejected'))
        } else {
          notify.error(describeError(cause))
        }
      } finally {
        setSaving(false)
      }
    },
    [api, playbookId],
  )

  return { children, parents, loading, error, saving, save }
}
