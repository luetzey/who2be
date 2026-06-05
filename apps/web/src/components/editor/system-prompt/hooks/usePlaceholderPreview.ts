// usePlaceholderPreview — kapselt das Laden der Pill-Vorschau und den nativen
// `placeholder-click`-Listener am `bn-container`. Haelt `useApi()` aus der
// Praesentations-Komponente (PlaceholderPreviewPopover) heraus.
import { useCallback, useEffect, useState } from 'react'

import type { PlaceholderPreview } from '@/api/types'
import { useApi } from '@/api/useApi'
import { type AnchorRef } from '@/components/ui/popover'

import { PLACEHOLDER_CLICK_EVENT, type PlaceholderClickDetail } from '../PlaceholderBlock'

export type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; preview: PlaceholderPreview }

export interface UsePlaceholderPreview {
  active: PlaceholderClickDetail | null
  setActive: (detail: PlaceholderClickDetail | null) => void
  state: LoadState
}

export function usePlaceholderPreview(
  containerRef: React.RefObject<HTMLElement | null>,
  anchorRef: AnchorRef,
  personaId: string | undefined,
): UsePlaceholderPreview {
  const api = useApi()
  const [active, setActive] = useState<PlaceholderClickDetail | null>(null)
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  const load = useCallback(
    (detail: PlaceholderClickDetail) => {
      setState({ status: 'loading' })
      api
        .previewPlaceholder({
          kind: detail.kind,
          target_id: detail.target_id,
          persona_id: personaId,
        })
        .then((preview) => setState({ status: 'ready', preview }))
        .catch(() =>
          setState({ status: 'error', message: 'Vorschau konnte nicht geladen werden.' }),
        )
    },
    [api, personaId],
  )

  useEffect(() => {
    const container = containerRef.current
    if (container === null) return
    const handler = (event: Event) => {
      // Die geklickte Pill ist der Anker fuer das schwebende Panel.
      if (event.target instanceof HTMLElement) {
        anchorRef.current = event.target
      }
      const detail = (event as CustomEvent<PlaceholderClickDetail>).detail
      setActive(detail)
      load(detail)
    }
    container.addEventListener(PLACEHOLDER_CLICK_EVENT, handler)
    return () => container.removeEventListener(PLACEHOLDER_CLICK_EVENT, handler)
  }, [containerRef, anchorRef, load])

  return { active, setActive, state }
}
