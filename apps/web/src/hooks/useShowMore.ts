import { useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'

/** Schrittweite der Auswahllisten auf dem Handy (Mobil-Spec M9: „8 Treffer“). */
export const SHOW_MORE_STEP = 8

interface ShowMoreState {
  key: string
  count: number
  announced: boolean
}

export interface ShowMoreOptions {
  /** Kuerzen aktiv (unter `md`); sonst liefert der Hook alle Eintraege. */
  enabled: boolean
  /**
   * Die Liste, deren n-tes Kind nach „weitere anzeigen“ den Fokus bekommt.
   * Der Aufrufer haelt den Ref selbst, damit das Rueckgabeobjekt nur
   * Render-Werte traegt.
   */
  listRef: RefObject<HTMLElement>
  /**
   * Wechselt der Schluessel (etwa der Suchbegriff), beginnt die Liste wieder
   * bei der ersten Schrittweite — eine neue Suche ist eine neue Liste.
   */
  resetKey?: string
  step?: number
}

export interface ShowMoreResult<T> {
  visible: T[]
  /** Wie viele der naechste Klick nachlaedt; 0 = keinen Knopf rendern. */
  nextCount: number
  /** Beschriftung des Knopfs, `common:actions.showMoreCount`. */
  buttonLabel: string
  /**
   * Text fuer die `aria-live`-Region (`common:list.shownOfTotal`). Leer, bis
   * „weitere anzeigen“ benutzt wurde: beim ersten Render soll nichts
   * angesagt werden, und die Region muss vorher leer im DOM stehen, damit
   * Screenreader die Aenderung ueberhaupt melden.
   */
  liveMessage: string
  showMore: () => void
}

const FOCUSABLE = 'button:not([disabled]), a[href], input, select, [tabindex]'

/**
 * Auswahlliste im Seitenfluss statt Scroll-in-Scroll (Mobil-Spec M9).
 *
 * Unter `md` zeigt die Liste die ersten {@link SHOW_MORE_STEP} Treffer; jeder
 * Klick auf „{{count}} weitere anzeigen“ haengt die naechsten an. Danach
 * springt der Fokus auf das erste fokussierbare Element des ersten neuen
 * Eintrags — der Knopf selbst verschwindet mit dem letzten Schritt, und ein
 * Fokus auf `body` wuerfe Tastatur- und Screenreader-Nutzer an den
 * Seitenanfang. Die Live-Region nennt den neuen Stand („16 von 40 angezeigt“).
 *
 * Bewusst NICHT im Hook: die Breakpoint-Erkennung (der Aufrufer reicht
 * `enabled`, etwa `useIsMobile()`) und das Markup, weil die beiden Listen
 * unterschiedliche Rahmen haben.
 */
export function useShowMore<T>(items: T[], options: ShowMoreOptions): ShowMoreResult<T> {
  const { enabled, listRef, resetKey = '', step = SHOW_MORE_STEP } = options
  const { t } = useTranslation('common')
  // Fokusziel des naechsten Commits: im Klick-Handler gesetzt, im
  // Layout-Effekt verbraucht. Kein Render-Wert, deshalb Ref statt State.
  const pendingFocus = useRef<number | null>(null)
  const [state, setState] = useState<ShowMoreState>({
    key: resetKey,
    count: step,
    announced: false,
  })

  // Abgeleiteter Zustand (React-Muster „Zustand bei Prop-Wechsel anpassen“):
  // ein neuer Suchbegriff setzt die Liste im selben Render zurueck, ohne einen
  // Zwischenframe mit der alten Laenge.
  let current = state
  if (state.key !== resetKey) {
    current = { key: resetKey, count: step, announced: false }
    setState(current)
  }

  const total = items.length
  const visible = enabled ? items.slice(0, current.count) : items
  const nextCount = enabled ? Math.min(step, total - visible.length) : 0

  const showMore = () => {
    pendingFocus.current = current.count
    setState({ ...current, count: current.count + step, announced: true })
  }

  useLayoutEffect(() => {
    const index = pendingFocus.current
    if (index === null) return
    pendingFocus.current = null
    const item = listRef.current?.children.item(index)
    if (item instanceof HTMLElement) {
      ;(item.querySelector<HTMLElement>(FOCUSABLE) ?? item).focus()
    }
  }, [current.count, listRef])

  return {
    visible,
    nextCount,
    buttonLabel: t('actions.showMoreCount', { count: nextCount }),
    liveMessage:
      enabled && current.announced
        ? t('list.shownOfTotal', { shown: visible.length, total })
        : '',
    showMore,
  }
}
