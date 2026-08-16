import { useCallback, useEffect, useState } from 'react'

import type { ArtifactMarkdown } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('workarea:artifact.loadError')
}

export interface UseArtifactResult {
  artifact: ArtifactMarkdown | null
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Inhalt eines Artifacts: Markdown mit `[#block_id]`-Anker-Annotationen.
 *
 * Ohne `anchor` das ganze Dokument; die Lese-Ansicht laedt bewusst immer alles
 * und springt clientseitig zum Anker — ein Server-Roundtrip pro Block waere
 * fuer einen Menschen, der scrollt, die falsche Granularitaet (fuer Agenten
 * ist sie richtig, die lesen gezielt einen Block).
 */
export function useArtifact(artifactId: string): UseArtifactResult {
  const api = useApi()
  const [artifact, setArtifact] = useState<ArtifactMarkdown | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .readWaArtifact(artifactId)
      .then(setArtifact)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, artifactId])

  useEffect(load, [load])

  return { artifact, loading, error, reload: load }
}
