import { useCallback, useEffect, useMemo, useState } from 'react'

import type { Playbook } from '../api/types'
import { useApi } from '../api/useApi'
import { notify } from '../lib/feedback'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

interface PersonaPlaybooksState {
  playbooks: Playbook[]
  // Serverseitig gespeicherte Verknuepfungen als vollstaendige Playbooks —
  // Basis fuer den Anzeige-Modus (WP-E). Bleibt bei lokalen Toggles stabil,
  // bis `save` erfolgreich war.
  linked: Playbook[]
  linkedIds: string[]
  loading: boolean
  saving: boolean
  error: string | null
  toggle: (id: string) => void
  // Liefert `true` bei Erfolg, damit Konsumenten den Bearbeiten-Modus
  // verlassen koennen; Fehler landen in `error` (kein Throw).
  save: () => Promise<boolean>
  // Verwirft lokale (ungespeicherte) Auswahl-Aenderungen ohne Refetch.
  cancel: () => void
  reset: () => void
}

export function usePersonaPlaybooks(personaId: string | undefined): PersonaPlaybooksState {
  const api = useApi()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [linkedIds, setLinkedIds] = useState<string[]>([])
  const [savedIds, setSavedIds] = useState<string[]>([])
  const [loading, setLoading] = useState(personaId !== undefined)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (personaId === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([api.listPlaybooks(), api.listPersonaPlaybooks(personaId)])
      .then(([all, linked]) => {
        setPlaybooks(all)
        const ids = linked.map((playbook) => playbook.id)
        setLinkedIds(ids)
        setSavedIds(ids)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, personaId])

  useEffect(load, [load])

  const toggle = useCallback((id: string) => {
    setLinkedIds((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id],
    )
  }, [])

  const save = useCallback(async (): Promise<boolean> => {
    if (personaId === undefined) {
      return false
    }
    setSaving(true)
    setError(null)
    try {
      await api.setPersonaPlaybooks(personaId, linkedIds)
      setSavedIds(linkedIds)
      notify.success(i18n.t('common:toast.linksSaved'))
      return true
    } catch (cause) {
      setError(describeError(cause))
      return false
    } finally {
      setSaving(false)
    }
  }, [api, personaId, linkedIds])

  const cancel = useCallback(() => {
    setLinkedIds(savedIds)
  }, [savedIds])

  const reset = useCallback(() => {
    load()
  }, [load])

  // Anzeige-Liste aus der Workspace-Liste ableiten (nicht aus der Link-
  // Response), damit Listen-Anreicherungen wie `compose_children`/
  // `is_composite` auch hier ankommen.
  const linked = useMemo(
    () => playbooks.filter((playbook) => savedIds.includes(playbook.id)),
    [playbooks, savedIds],
  )

  return { playbooks, linked, linkedIds, loading, saving, error, toggle, save, cancel, reset }
}
