import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '@/api/client'
import type { ResourceRef, SubResource, SubResourceLinkInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseResourceSubResourcesResult {
  /** Geordnete Liste der direkten Sub-Resources (Kinder). */
  children: SubResource[]
  /** Backlinks — welche Resources fuehren diese Resource als Sub-Resource? */
  parents: ResourceRef[]
  loading: boolean
  error: string | null
  saving: boolean
  /** Ersetzt die Sub-Resource-Liste (Set-Replace, PUT-Semantik). */
  save: (links: SubResourceLinkInput[]) => Promise<void>
}

/**
 * Laedt und setzt die Sub-Resource-Relation einer Resource (Track E §3.3).
 * `save` ersetzt die gesamte Kinder-Liste (PUT-Semantik).
 *
 * Faellt auf 404 zurueck, wenn das Backend den Endpoint noch nicht kennt
 * (leere Listen statt Fehlerbanner).
 */
export function useResourceSubResources(
  resourceId: string | undefined,
): UseResourceSubResourcesResult {
  const api = useApi()
  const [children, setChildren] = useState<SubResource[]>([])
  const [parents, setParents] = useState<ResourceRef[]>([])
  const [loading, setLoading] = useState(resourceId !== undefined)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    if (resourceId === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([
      api.listResourceSubResources(resourceId).catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 404) return []
        throw cause
      }),
      api.listResourceUsedBy(resourceId).catch((cause: unknown) => {
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
  }, [api, resourceId])

  useEffect(load, [load])

  const save = useCallback(
    async (links: SubResourceLinkInput[]) => {
      if (resourceId === undefined) {
        return
      }
      setSaving(true)
      try {
        const updated = await api.setResourceSubResources(resourceId, links)
        setChildren(updated)
        notify.success('Sub-Resources gespeichert.')
      } catch (cause: unknown) {
        if (cause instanceof ApiError && cause.status === 409) {
          notify.error('Verknuepfung wurde abgelehnt: Zyklus wuerde entstehen.')
        } else {
          notify.error(describeError(cause))
        }
      } finally {
        setSaving(false)
      }
    },
    [api, resourceId],
  )

  return { children, parents, loading, error, saving, save }
}
