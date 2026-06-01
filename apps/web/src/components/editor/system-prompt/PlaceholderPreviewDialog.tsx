// PlaceholderPreviewDialog — Read-only-Overlay fuer den aufgeloesten Output
// einer Editor-Pill. Haengt einen nativen Listener fuer das bubbelnde
// `placeholder-click`-CustomEvent an den uebergebenen `bn-container`-Knoten;
// beim Klick wird der Preview-Endpoint befragt und das Ergebnis im Dialog
// gezeigt. Bewusst kein Editieren — nur Vorschau (Scope „Nur Vorschau").
import { useCallback, useEffect, useState } from 'react'

import { useApi } from '@/api/useApi'
import type { PlaceholderPreview } from '@/api/types'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

import {
  PLACEHOLDER_CLICK_EVENT,
  type PlaceholderClickDetail,
  type PlaceholderKind,
} from './PlaceholderBlock'

interface PlaceholderPreviewDialogProps {
  /** Ref auf den `bn-container`, an dem das `placeholder-click`-Event bubbelt. */
  containerRef: React.RefObject<HTMLElement | null>
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; preview: PlaceholderPreview }

// `persona-field`-Pills brauchen einen Persona-Kontext, den die Template-Editoren
// nicht haben — der Resolver liefert dann einen Miss. Statt einer leeren Vorschau
// erklaeren wir, dass die Aufloesung erst zur Agenten-Laufzeit passiert.
const PERSONA_FIELD_HINT =
  'Dieses Persona-Feld wird erst im Agenten-Kontext mit der zugewiesenen ' +
  'Persona aufgeloest. In der Vorlage gibt es noch keinen Persona-Bezug.'

function missHint(kind: PlaceholderKind): string {
  if (kind === 'persona-field') return PERSONA_FIELD_HINT
  return 'Der Platzhalter konnte nicht aufgeloest werden — Ziel nicht gefunden ' +
    'oder (noch) nicht aktiv.'
}

export function PlaceholderPreviewDialog({ containerRef }: PlaceholderPreviewDialogProps) {
  const api = useApi()
  const [active, setActive] = useState<PlaceholderClickDetail | null>(null)
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  const load = useCallback(
    (detail: PlaceholderClickDetail) => {
      setState({ status: 'loading' })
      api
        .previewPlaceholder({ kind: detail.kind, target_id: detail.target_id })
        .then((preview) => setState({ status: 'ready', preview }))
        .catch(() =>
          setState({ status: 'error', message: 'Vorschau konnte nicht geladen werden.' }),
        )
    },
    [api],
  )

  useEffect(() => {
    const container = containerRef.current
    if (container === null) return
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<PlaceholderClickDetail>).detail
      setActive(detail)
      load(detail)
    }
    container.addEventListener(PLACEHOLDER_CLICK_EVENT, handler)
    return () => container.removeEventListener(PLACEHOLDER_CLICK_EVENT, handler)
  }, [containerRef, load])

  const open = active !== null
  const title = active?.label !== undefined && active.label !== '' ? active.label : 'Vorschau'

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) setActive(null) }}>
      <DialogContent data-testid="placeholder-preview-dialog">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            So wird dieser Platzhalter im fertigen Prompt aufgeloest.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-96 overflow-y-auto rounded-md border bg-muted/40 p-3">
          {state.status === 'loading' && (
            <p className="text-sm text-muted-foreground">Lade Vorschau…</p>
          )}
          {state.status === 'error' && (
            <p className="text-sm text-destructive" data-testid="placeholder-preview-error">
              {state.message}
            </p>
          )}
          {state.status === 'ready' &&
            (state.preview.unresolved ? (
              <p
                className="text-sm text-muted-foreground"
                data-testid="placeholder-preview-miss"
              >
                {active !== null ? missHint(active.kind) : ''}
              </p>
            ) : (
              <pre
                className="font-mono text-xs whitespace-pre-wrap"
                data-testid="placeholder-preview-text"
              >
                {state.preview.text}
              </pre>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
