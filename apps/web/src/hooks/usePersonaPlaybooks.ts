import { useCallback, useEffect, useState } from 'react'

import type { Playbook } from '../api/types'
import { useApi } from '../api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

interface PersonaPlaybooksState {
  playbooks: Playbook[]
  linkedIds: string[]
  loading: boolean
  saving: boolean
  error: string | null
  status: string | null
  toggle: (id: string) => void
  save: () => Promise<void>
  reset: () => void
}

export function usePersonaPlaybooks(personaId: string | undefined): PersonaPlaybooksState {
  const api = useApi()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [linkedIds, setLinkedIds] = useState<string[]>([])
  const [loading, setLoading] = useState(personaId !== undefined)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  const load = useCallback(() => {
    if (personaId === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([api.listPlaybooks(), api.listPersonaPlaybooks(personaId)])
      .then(([all, linked]) => {
        setPlaybooks(all)
        setLinkedIds(linked.map((playbook) => playbook.id))
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, personaId])

  useEffect(load, [load])

  const toggle = useCallback((id: string) => {
    setStatus(null)
    setLinkedIds((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id],
    )
  }, [])

  const save = useCallback(async () => {
    if (personaId === undefined) {
      return
    }
    setSaving(true)
    setStatus(null)
    setError(null)
    try {
      await api.setPersonaPlaybooks(personaId, linkedIds)
      setStatus('Verknüpfungen gespeichert.')
    } catch (cause) {
      setError(describeError(cause))
    } finally {
      setSaving(false)
    }
  }, [api, personaId, linkedIds])

  const reset = useCallback(() => {
    load()
  }, [load])

  return { playbooks, linkedIds, loading, saving, error, status, toggle, save, reset }
}
