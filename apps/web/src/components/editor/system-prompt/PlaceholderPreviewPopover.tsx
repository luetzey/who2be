// PlaceholderPreviewPopover — nicht-blockierende, an der Pill verankerte
// Sprechblase mit dem aufgeloesten Output einer Editor-Pill (Layer 2,
// design-language §6). Haengt einen nativen Listener fuer das bubbelnde
// `placeholder-click`-CustomEvent an den `bn-container`; beim Klick wird der
// Anker (die Pill) gesetzt, der Preview-Endpoint befragt und das Ergebnis im
// Popover gezeigt. Kein Backdrop, kein Focus-Trap — Editor bleibt bedienbar.
import { ErrorAlert, LoadingState } from '@/components/data'
import { Button } from '@/components/ui/button'
import {
  type AnchorRef,
  type Measurable,
  Popover,
  PopoverAnchor,
  PopoverContent,
} from '@/components/ui/popover'

import { usePlaceholderPreview } from './hooks/usePlaceholderPreview'
import { type PlaceholderClickDetail, type PlaceholderKind } from './PlaceholderBlock'

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
  /**
   * Optionaler Persona-Kontext fuer die Vorschau. Im Persona-Editor wird die
   * ID der bearbeiteten Persona durchgereicht, damit Katalog-Pills
   * (`playbooks-catalog`) und `persona-field`-Pills auch in der Editor-Vorschau
   * aufloesen statt einen Miss zu zeigen. Fehlt der Kontext (z. B. neue, noch
   * nicht gespeicherte Persona), bleibt das Miss-Verhalten unveraendert.
   */
  personaId?: string
}

// `persona-field`-Pills brauchen einen Persona-Kontext, den die Template-Editoren
// nicht haben — der Resolver liefert dann einen Miss. Statt einer leeren Vorschau
// erklaeren wir, dass die Aufloesung erst zur Agenten-Laufzeit passiert.
const PERSONA_FIELD_HINT =
  'Dieses Persona-Feld wird erst im Agenten-Kontext mit der zugewiesenen ' +
  'Persona aufgeloest. In der Vorlage gibt es noch keinen Persona-Bezug.'

// `persona-ref` und `playbooks-catalog` brauchen — wie `persona-field` — den
// Agenten-Kontext (zugewiesene Persona), den die Template-Editoren nicht haben.
const PERSONA_CONTEXT_HINT =
  'Dies wird erst im Agenten-Kontext mit der zugewiesenen Persona aufgeloest. ' +
  'In der Vorlage gibt es noch keinen Persona-Bezug.'

function missHint(kind: PlaceholderKind): string {
  if (kind === 'persona-field') return PERSONA_FIELD_HINT
  if (kind === 'persona-ref' || kind === 'playbooks-catalog') return PERSONA_CONTEXT_HINT
  return 'Der Platzhalter konnte nicht aufgeloest werden — Ziel nicht gefunden ' +
    'oder (noch) nicht aktiv.'
}

// `tools-overview` und `persona-ref` sind parameterlos — nichts zu bearbeiten.
function isEditableKind(kind: PlaceholderKind): boolean {
  return kind !== 'tools-overview' && kind !== 'persona-ref'
}

export function PlaceholderPreviewPopover({
  containerRef,
  anchorRef,
  editable = false,
  onEdit,
  personaId,
}: PlaceholderPreviewPopoverProps) {
  const { active, setActive, state } = usePlaceholderPreview(containerRef, anchorRef, personaId)

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
