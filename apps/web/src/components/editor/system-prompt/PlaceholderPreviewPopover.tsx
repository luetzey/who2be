// PlaceholderPreviewPopover — nicht-blockierende, an der Pill verankerte
// Sprechblase mit dem aufgeloesten Output einer Editor-Pill (Layer 2,
// design-language §6). Haengt einen nativen Listener fuer das bubbelnde
// `placeholder-click`-CustomEvent an den `bn-container`; beim Klick wird der
// Anker (die Pill) gesetzt, der Preview-Endpoint befragt und das Ergebnis im
// Popover gezeigt. Kein Backdrop, kein Focus-Trap — Editor bleibt bedienbar.
import { useCallback, useEffect, useState } from 'react'

import { useApi } from '@/api/useApi'
import type { PlaceholderPreview } from '@/api/types'
import { ErrorAlert, LoadingState } from '@/components/data'
import { Button } from '@/components/ui/button'
import {
  type AnchorRef,
  type Measurable,
  Popover,
  PopoverAnchor,
  PopoverContent,
} from '@/components/ui/popover'

import {
  PLACEHOLDER_CLICK_EVENT,
  type PlaceholderClickDetail,
  type PlaceholderKind,
} from './PlaceholderBlock'

interface PlaceholderPreviewPopoverProps {
  /** Ref auf den `bn-container`, an dem das `placeholder-click`-Event bubbelt. */
  containerRef: React.RefObject<HTMLElement | null>
  /**
   * Gemeinsamer Anker (mit den Pickern geteilt). Wird beim Klick auf die
   * geklickte Pill gesetzt, damit Vorschau und ein anschliessendes Bearbeiten
   * an derselben Stelle erscheinen.
   */
  anchorRef: AnchorRef
  /** Im editierbaren Editor: zeigt einen „Bearbeiten"-Button im Popover. */
  editable?: boolean
  /** Klick auf „Bearbeiten" — der Wrapper oeffnet den vorbefuellten Picker. */
  onEdit?: (detail: PlaceholderClickDetail) => void
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

// `tools-overview` ist parameterlos — nichts zu bearbeiten.
function isEditableKind(kind: PlaceholderKind): boolean {
  return kind !== 'tools-overview'
}

export function PlaceholderPreviewPopover({
  containerRef,
  anchorRef,
  editable = false,
  onEdit,
}: PlaceholderPreviewPopoverProps) {
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

  const open = active !== null

  return (
    <Popover open={open} onOpenChange={(isOpen) => { if (!isOpen) setActive(null) }}>
      {/* Radix' virtualRef erwartet current non-null (React-Typen); null ist
          zur Laufzeit zulaessig (Radix faellt dann auf keinen Anker zurueck). */}
      <PopoverAnchor virtualRef={anchorRef as React.RefObject<Measurable>} />
      <PopoverContent
        align="start"
        className="w-96 max-w-[min(24rem,90vw)]"
        aria-label="Platzhalter-Vorschau"
        data-testid="placeholder-preview-popover"
      >
        <div className="flex flex-col gap-3">
          <div className="text-sm font-semibold tracking-tight">
            {active?.label !== undefined && active.label !== '' ? active.label : 'Vorschau'}
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {state.status === 'loading' && <LoadingState rows={2} />}
            {state.status === 'error' && (
              <ErrorAlert message={state.message} title="Vorschau fehlgeschlagen" />
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
          {editable && active !== null && isEditableKind(active.kind) && (
            <div className="flex justify-end">
              <Button
                variant="outline"
                size="sm"
                data-testid="placeholder-preview-edit"
                onClick={() => {
                  const detail = active
                  setActive(null)
                  onEdit?.(detail)
                }}
              >
                Bearbeiten
              </Button>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
