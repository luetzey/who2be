import {
  forwardRef,
  useCallback,
  useEffect,
  useRef,
  useState,
  type HTMLAttributes,
  type TableHTMLAttributes,
  type TdHTMLAttributes,
  type ThHTMLAttributes,
} from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

interface TableProps extends TableHTMLAttributes<HTMLTableElement> {
  /**
   * `id` der sichtbaren Ueberschrift, die die Tabelle benennt (etwa ein
   * `CardTitle`). Benennt den Scroll-Bereich UND die Tabelle; ohne sie faellt
   * der Bereich auf `aria-label` zurueck. Kann die Tabelle ueberlaufen, ist
   * einer von beiden Pflicht (ACT-Regel 0ssw9k: der Scroller ist dann ein
   * Tab-Stopp, und ein fokussierbarer Bereich braucht einen Namen).
   */
  labelledBy?: string
}

interface ScrollState {
  overflowing: boolean
  scrolled: boolean
  atEnd: boolean
}

const IDLE: ScrollState = { overflowing: false, scrolled: false, atEnd: true }

// Subpixel-Rundung (DPR 2/3) erzeugt Differenzen unter 1 px — kein Ueberlauf.
const TOLERANCE_PX = 1

function readScrollState(element: HTMLElement): ScrollState {
  const max = element.scrollWidth - element.clientWidth
  return {
    overflowing: max > TOLERANCE_PX,
    scrolled: element.scrollLeft > TOLERANCE_PX,
    atEnd: element.scrollLeft >= max - TOLERANCE_PX,
  }
}

/**
 * Tabellen-Muster fuer Datentabellen (Mobil-Spec M11).
 *
 * Eine breite Tabelle scrollt in ihrem eigenen Bereich, genau auf der
 * x-Achse; die Seite selbst nie (WCAG 1.4.10 nimmt Tabellen aus). Solange sie
 * ueberlaeuft, gilt:
 *
 * - Der Bereich ist per Tab erreichbar (`tabindex=0`) und benannt
 *   (`role=region` + `aria-labelledby`/`aria-label`). Safari macht
 *   Scroll-Container nicht von selbst fokussierbar; ohne Fokus kommt die
 *   Tastatur nicht an die verdeckten Spalten (ACT 0ssw9k). Mit dem Fokus
 *   darauf scrollen die Pfeiltasten.
 * - Die erste Spalte (der Datensatz-Bezeichner) bleibt links fixiert; sobald
 *   gescrollt ist, trennt ein Schatten sie vom durchlaufenden Inhalt.
 * - Rechts zeigt ein Verlauf, dass weitere Spalten folgen, bis das Ende
 *   erreicht ist; unter `md` steht darunter zusaetzlich ein Texthinweis.
 * - `overscroll-behavior-x: contain`: am Rand laeuft der Wisch nicht in die
 *   Seite oder die Zurueck-Geste des Browsers weiter.
 *
 * Ohne Ueberlauf bleibt es eine gewoehnliche Tabelle: kein zusaetzlicher
 * Tab-Stopp, kein Hinweis, keine fixierte Spalte.
 *
 * Eine fixierte Kopfzeile gibt es bewusst nicht: `position: sticky; top`
 * bezieht sich im x-Scroller auf den Scroller selbst, nicht auf das
 * Seitenfenster, und die Tabellen hier wachsen im Seitenfluss.
 */
export const Table = forwardRef<HTMLTableElement, TableProps>(function Table(
  { className, labelledBy, ...props },
  ref,
) {
  const { t } = useTranslation('common')
  const scrollerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<ScrollState>(IDLE)

  const update = useCallback(() => {
    const element = scrollerRef.current
    if (element === null) return
    const next = readScrollState(element)
    setState((previous) =>
      previous.overflowing === next.overflowing &&
      previous.scrolled === next.scrolled &&
      previous.atEnd === next.atEnd
        ? previous
        : next,
    )
  }, [])

  useEffect(() => {
    const element = scrollerRef.current
    if (element === null) return
    update()
    // Beobachtet werden Bereich UND Tabelle: der Bereich aendert sich mit dem
    // Viewport, die Tabelle mit ihren Daten (etwa wenn die Vorschau laedt).
    const observer = new ResizeObserver(update)
    observer.observe(element)
    const table = element.firstElementChild
    if (table !== null) observer.observe(table)
    return () => observer.disconnect()
  }, [update])

  const label = labelledBy === undefined ? props['aria-label'] : undefined
  const named = labelledBy !== undefined || label !== undefined
  const { overflowing, scrolled, atEnd } = state

  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <div
          ref={scrollerRef}
          onScroll={update}
          data-testid="table-scroller"
          data-overflow={overflowing ? 'true' : undefined}
          data-scrolled={scrolled ? 'true' : undefined}
          tabIndex={overflowing ? 0 : undefined}
          role={overflowing && named ? 'region' : undefined}
          aria-labelledby={overflowing ? labelledBy : undefined}
          aria-label={overflowing ? label : undefined}
          className={cn(
            'w-full overflow-x-auto overscroll-x-contain rounded-sm',
            'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none',
            // Erste Spalte fixieren — nur bei Ueberlauf; ohne ihn gaebe die
            // deckende Zelle dem Zeilen-Hover eine sichtbare Luecke.
            'data-[overflow=true]:[&_tr>*:first-child]:sticky data-[overflow=true]:[&_tr>*:first-child]:left-0 data-[overflow=true]:[&_tr>*:first-child]:z-10 data-[overflow=true]:[&_tr>*:first-child]:bg-card',
            // Kante der fixierten Spalte als Verlauf per Pseudo-Element:
            // `box-shadow` zeichnet Chromium an Zellen einer
            // `border-collapse`-Tabelle nicht (gemessen: berechnet, aber
            // unsichtbar). Die sticky Zelle ist Bezugsrahmen des `::after`.
            'data-[scrolled=true]:[&_tr>*:first-child]:after:pointer-events-none data-[scrolled=true]:[&_tr>*:first-child]:after:absolute data-[scrolled=true]:[&_tr>*:first-child]:after:inset-y-0 data-[scrolled=true]:[&_tr>*:first-child]:after:left-full data-[scrolled=true]:[&_tr>*:first-child]:after:w-2 data-[scrolled=true]:[&_tr>*:first-child]:after:bg-linear-to-r data-[scrolled=true]:[&_tr>*:first-child]:after:from-foreground/15 data-[scrolled=true]:[&_tr>*:first-child]:after:to-transparent',
          )}
        >
          <table
            ref={ref}
            aria-labelledby={labelledBy}
            className={cn('w-full caption-bottom text-sm', className)}
            {...props}
          />
        </div>
        {overflowing && !atEnd ? (
          <div
            aria-hidden="true"
            data-testid="table-scroll-shadow"
            className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-linear-to-l from-card to-transparent"
          />
        ) : null}
      </div>
      {overflowing ? (
        <p data-testid="table-scroll-hint" className="text-xs text-muted-foreground md:hidden">
          {t('table.scrollHint')}
        </p>
      ) : null}
    </div>
  )
})

export const TableHeader = forwardRef<HTMLTableSectionElement, HTMLAttributes<HTMLTableSectionElement>>(
  function TableHeader({ className, ...props }, ref) {
    return <thead ref={ref} className={cn('[&_tr]:border-b', className)} {...props} />
  },
)

export const TableBody = forwardRef<HTMLTableSectionElement, HTMLAttributes<HTMLTableSectionElement>>(
  function TableBody({ className, ...props }, ref) {
    return (
      <tbody ref={ref} className={cn('[&_tr:last-child]:border-0', className)} {...props} />
    )
  },
)

export const TableRow = forwardRef<HTMLTableRowElement, HTMLAttributes<HTMLTableRowElement>>(
  function TableRow({ className, ...props }, ref) {
    return (
      <tr
        ref={ref}
        className={cn(
          'border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted',
          className,
        )}
        {...props}
      />
    )
  },
)

export const TableHead = forwardRef<HTMLTableCellElement, ThHTMLAttributes<HTMLTableCellElement>>(
  function TableHead({ className, ...props }, ref) {
    return (
      <th
        ref={ref}
        className={cn(
          'h-12 px-4 text-left align-middle font-medium text-muted-foreground',
          className,
        )}
        {...props}
      />
    )
  },
)

export const TableCell = forwardRef<HTMLTableCellElement, TdHTMLAttributes<HTMLTableCellElement>>(
  function TableCell({ className, ...props }, ref) {
    return <td ref={ref} className={cn('p-4 align-middle', className)} {...props} />
  },
)
