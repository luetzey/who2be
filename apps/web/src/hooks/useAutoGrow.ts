import { useLayoutEffect, type RefObject } from 'react'

// Fallback fuer mitwachsende Textfelder (Mobil-Spec M5).
//
// Der Normalfall braucht kein JavaScript: `Textarea` setzt
// `field-sizing: content`, der Browser passt die Hoehe selbst an. Safari
// < 26.2 und Firefox < 152 kennen die Eigenschaft nicht; nur dort misst
// dieser Hook `scrollHeight` und setzt die Hoehe von Hand. Die Obergrenze
// (`max-h-[60svh]`) und die Mindesthoehe (`rows`) stehen weiter im CSS und
// gelten in beiden Pfaden gleich.

/** Kann der Browser Textfelder selbst an den Inhalt anpassen? */
export function supportsFieldSizing(): boolean {
  return (
    typeof CSS !== 'undefined' &&
    typeof CSS.supports === 'function' &&
    CSS.supports('field-sizing', 'content')
  )
}

/**
 * Stellt die Scrollposition der Seite und aller gescrollten Vorfahren wieder
 * her. Das kurze `height: auto` beim Messen kann das Dokument verkuerzen; der
 * Browser zieht die Scrollposition dann nach oben, und die Seite springt.
 */
function snapshotScroll(el: HTMLElement): () => void {
  const saved: Array<[HTMLElement, number]> = []
  for (let node = el.parentElement; node !== null; node = node.parentElement) {
    if (node.scrollTop > 0) saved.push([node, node.scrollTop])
  }
  const x = window.scrollX
  const y = window.scrollY
  return () => {
    for (const [node, top] of saved) {
      if (node.scrollTop !== top) node.scrollTop = top
    }
    if (window.scrollY !== y) window.scrollTo(x, y)
  }
}

/** Setzt die Hoehe des Feldes auf seinen Inhalt (samt Rahmen). */
export function fitToContent(el: HTMLTextAreaElement): void {
  const restore = snapshotScroll(el)
  el.style.height = 'auto'
  const style = window.getComputedStyle(el)
  const border =
    (Number.parseFloat(style.borderTopWidth) || 0) +
    (Number.parseFloat(style.borderBottomWidth) || 0)
  // `scrollHeight` enthaelt das Padding, aber nicht den Rahmen; mit
  // `box-sizing: border-box` (Tailwind-Preflight) gehoert er zur Hoehe.
  el.style.height = `${el.scrollHeight + border}px`
  restore()
}

/**
 * Laesst ein Textfeld ohne `field-sizing`-Unterstuetzung mit dem Inhalt
 * wachsen. Ist die Eigenschaft vorhanden oder `enabled` falsch, tut der Hook
 * nichts.
 *
 * `value` gehoert in die Abhaengigkeiten, weil ein kontrolliertes Feld (z. B.
 * nach `form.reset`) seinen Inhalt ohne `input`-Ereignis aendern kann.
 */
export function useAutoGrow(
  ref: RefObject<HTMLTextAreaElement | null>,
  enabled: boolean,
  value?: unknown,
): void {
  useLayoutEffect(() => {
    const el = ref.current
    if (el === null || !enabled || supportsFieldSizing()) return
    fitToContent(el)

    const onInput = () => fitToContent(el)
    el.addEventListener('input', onInput)

    // Aendert sich die Breite (Drehung, Seitenleiste, Textzoom), brechen die
    // Zeilen anders um — dann neu messen. Hoehenaenderungen loest der Hook
    // selbst aus; auf sie zu reagieren, waere eine Schleife.
    let lastWidth = el.clientWidth
    const observer =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => {
            if (el.clientWidth === lastWidth) return
            lastWidth = el.clientWidth
            fitToContent(el)
          })
    observer?.observe(el)

    return () => {
      el.removeEventListener('input', onInput)
      observer?.disconnect()
      el.style.height = ''
    }
  }, [ref, enabled, value])
}
