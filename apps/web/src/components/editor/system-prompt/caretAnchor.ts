// caretMeasurable — Anker fuer das schwebende Picker-Panel beim Slash-Einfuegen.
// Liefert ein `Measurable` an der aktuellen Text-Cursor-Position (wie BlockNotes
// Slash-Menue); faellt auf den uebergebenen Container zurueck, wenn keine
// brauchbare Selektion existiert.
import { type Measurable } from '@/components/ui/popover'

export function caretMeasurable(fallback: HTMLElement | null): Measurable | null {
  const selection = typeof window !== 'undefined' ? window.getSelection() : null
  if (selection !== null && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0)
    // jsdom implementiert `Range.getBoundingClientRect` nicht — defensiv pruefen.
    if (typeof range.getBoundingClientRect === 'function') {
      const rect = range.getBoundingClientRect()
      // Eine kollabierte Selektion liefert oft Breite 0, aber valide Position.
      const hasPosition =
        rect.top !== 0 || rect.left !== 0 || rect.width !== 0 || rect.height !== 0
      if (hasPosition) {
        return { getBoundingClientRect: () => rect }
      }
    }
  }
  return fallback
}
