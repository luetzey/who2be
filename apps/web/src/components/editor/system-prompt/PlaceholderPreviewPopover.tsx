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
import i18n from '@/i18n'
import { useTranslation } from 'react-i18next'

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
// `persona-ref` und `playbooks-catalog` brauchen denselben Kontext.
// Die Texte werden beim Aufruf aufgeloest, nicht beim Modul-Import — sonst
// friert die Sprache auf den Stand des ersten Chunk-Ladens ein.
function missHint(kind: PlaceholderKind): string {
  if (kind === 'persona-field') return i18n.t('editor:preview.personaFieldUnresolved')
  if (kind === 'persona-ref' || kind === 'playbooks-catalog') {
    return i18n.t('editor:preview.personaUnresolved')
  }
  return i18n.t('editor:preview.targetMissing')
}

// `tools-overview`, `memory` und `persona-ref` sind parameterlos — nichts zu
// bearbeiten.
function isEditableKind(kind: PlaceholderKind): boolean {
  return kind !== 'tools-overview' && kind !== 'persona-ref' && kind !== 'memory'
}

export function PlaceholderPreviewPopover({
  containerRef,
  anchorRef,
  editable = false,
  onEdit,
  personaId,
}: PlaceholderPreviewPopoverProps) {
  const { t } = useTranslation('editor')
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
        aria-label={t('preview.ariaLabel')}
        data-testid="placeholder-preview-popover"
      >
        <div className="flex flex-col gap-3">
          <div className="text-sm font-semibold tracking-tight">
            {active?.label !== undefined && active.label !== '' ? active.label : t('preview.fallbackTitle')}
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {state.status === 'loading' && <LoadingState rows={2} />}
            {state.status === 'error' && (
              <ErrorAlert message={state.message} title={t('preview.errorTitle')} />
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
                {t('common:actions.edit')}
              </Button>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
