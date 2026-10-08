import { type ReactNode, type RefObject, useId } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

interface ListFilterSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Facetten-Selects (volle Breite). */
  facets: ReactNode
  /** Anzeige-Selects (Sortierung, Gruppieren), abgesetzt unter den Facetten. */
  display: ReactNode
  onReset: () => void
  /** Trefferzahl fuer den Fuss; `null` = „Fertig“. */
  resultCount: number | null
  /** Der „Filter“-Knopf: bekommt beim Schliessen den Fokus zurueck. */
  returnFocusRef: RefObject<HTMLButtonElement | null>
}

/**
 * Filter-Sheet unter `md` (Filter-Standard §2.2, E6): von unten, Hoehe nach
 * Inhalt bis 85svh, der Inhalt scrollt, der Fuss steht fest. Jeder Wert wirkt
 * sofort — beide Fuss-Knoepfe schliessen nur (Zuruecksetzen setzt vorher
 * zurueck). Radix liefert Fokusfalle, Escape und `aria-modal`.
 */
export function ListFilterSheet({
  open,
  onOpenChange,
  facets,
  display,
  onReset,
  resultCount,
  returnFocusRef,
}: ListFilterSheetProps) {
  const { t, i18n } = useTranslation('data')
  const descriptionId = useId()
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        aria-describedby={descriptionId}
        className="max-h-[85svh] gap-0 p-0"
        data-testid="list-filter-sheet"
        onCloseAutoFocus={(event) => {
          // Ohne `SheetTrigger` kennt Radix keinen Ausloeser — Fokus gezielt
          // zurueck auf „Filter“ (§5).
          event.preventDefault()
          returnFocusRef.current?.focus()
        }}
      >
        <SheetHeader className="border-b p-4 pr-12 text-left">
          <SheetTitle>{t('filter.sheetTitle')}</SheetTitle>
          <SheetDescription id={descriptionId}>{t('filter.sheetDescription')}</SheetDescription>
        </SheetHeader>
        <div
          className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain p-4"
          data-testid="list-filter-sheet-panel"
        >
          {facets}
          {display ? <div className="flex flex-col gap-4 border-t pt-4">{display}</div> : null}
        </div>
        <div className="flex gap-2 border-t p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <Button
            type="button"
            variant="outline"
            className="min-h-11 flex-1"
            onClick={() => {
              onReset()
              onOpenChange(false)
            }}
          >
            {t('filter.reset')}
          </Button>
          <Button type="button" className="min-h-11 flex-1" onClick={() => onOpenChange(false)}>
            {resultCount !== null
              ? t('filter.showResults', {
                  count: resultCount,
                  formatted: new Intl.NumberFormat(i18n.language).format(resultCount),
                })
              : t('filter.done')}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
