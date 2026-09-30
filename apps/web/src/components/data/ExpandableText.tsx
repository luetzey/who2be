import { useCallback, useId, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// Langer Text, gekuerzt auf N Zeilen, mit „Mehr anzeigen" im Seitenfluss
// (Mobil-Spec M2/M8, Weiche W3 = a: harte Kuerzung mit „…", Textknopf
// darunter, kein Verlauf).
//
// - Gekuerzt wird mit der Tailwind-Utility `line-clamp-(--clamp)`. Sie setzt
//   das praefixierte Muster `display:-webkit-box; -webkit-box-orient:vertical;
//   -webkit-line-clamp:N; overflow:hidden` — unpraefixiertes `line-clamp`
//   allein traegt noch nicht (R-F5).
// - Der Knopf erscheint NUR, wenn tatsaechlich gekuerzt wird
//   (`scrollHeight > clientHeight + 1`). Ein ResizeObserver misst neu bei
//   Drehung, Textzoom und 1.4.12-Abstaenden.
// - Aufgeklappt waechst die Seite; es gibt keinen inneren Scrollbereich.
// - Der gekuerzte Text bleibt vollstaendig im DOM, der Screenreader liest
//   alles; der Knopf traegt `aria-expanded` + `aria-controls`.

type ExpandableTextElement = 'p' | 'div' | 'pre'

interface ExpandableTextProps {
  text: string
  /** Zeilen im gekuerzten Zustand unter `md` (Standard 3). */
  lines?: number
  /** Zeilen ab `md`; ohne Angabe gilt `lines`. */
  mdLines?: number
  as?: ExpandableTextElement
  /** Klassen fuer das Textelement (Schrift, Farbe, Umbruch). */
  className?: string
  /** Klassen fuer den umschliessenden Block (Abstand nach aussen). */
  wrapperClassName?: string
  'data-testid'?: string
}

export function ExpandableText({
  text,
  lines = 3,
  mdLines,
  as: Element = 'p',
  className,
  wrapperClassName,
  'data-testid': testId,
}: ExpandableTextProps) {
  const { t } = useTranslation('common')
  const textId = useId()
  const textRef = useRef<HTMLElement | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [clamped, setClamped] = useState(false)

  const measure = useCallback(() => {
    const el = textRef.current
    // Aufgeklappt ist nichts gekuerzt — der Knopf bleibt als „Weniger" stehen.
    if (el === null || expanded) return
    setClamped(el.scrollHeight > el.clientHeight + 1)
  }, [expanded])

  useLayoutEffect(() => {
    measure()
    const el = textRef.current
    if (el === null || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => measure())
    observer.observe(el)
    return () => observer.disconnect()
  }, [measure, text, lines, mdLines])

  if (text === '') return null

  const toggle = () => {
    const willExpand = !expanded
    setExpanded(willExpand)
    if (!willExpand) {
      // Zuklappen: den Textanfang nur zurueckholen, wenn er oberhalb des
      // Viewports liegt — sonst springt die Seite unnoetig.
      const el = textRef.current
      if (el !== null && el.getBoundingClientRect().top < 0) {
        el.scrollIntoView({ block: 'start' })
      }
    }
  }

  const style = {
    '--clamp': lines,
    '--clamp-md': mdLines ?? lines,
  } as CSSProperties

  return (
    <div className={wrapperClassName} data-testid={testId}>
      <Element
        id={textId}
        ref={(node: HTMLElement | null) => {
          textRef.current = node
        }}
        style={style}
        data-expanded={expanded ? 'true' : 'false'}
        className={cn(
          'wrap-anywhere',
          !expanded && 'line-clamp-(--clamp) md:line-clamp-(--clamp-md)',
          className,
        )}
      >
        {text}
      </Element>
      {clamped || expanded ? (
        <Button
          type="button"
          variant="link"
          // 44 px Trefferflaeche unter `md` (R-P9), ab `md` 32 px (DL §11).
          className="h-auto min-h-11 px-0 py-0 md:min-h-8"
          aria-expanded={expanded}
          aria-controls={textId}
          onClick={toggle}
        >
          {expanded ? t('actions.showLess') : t('actions.showMore')}
        </Button>
      ) : null}
    </div>
  )
}
