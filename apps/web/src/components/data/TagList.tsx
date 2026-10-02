import { useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// Tag-Reihe, die unterhalb `md` nach `max` Tags auf einen Knopf „+n“
// einklappt (Audit A13, Weiche W3=a: Knopf im Seitenfluss, kein Popover).
// Ab `md` stehen immer alle Tags da, der Knopf entfaellt.
//
// - Die eingeklappten Tags sind `hidden md:inline-flex`: unter `md` nicht im
//   Tab-Fokus und nicht im A11y-Tree, ab `md` wie bisher sichtbar. Kein
//   JS-Breakpoint — dasselbe Mobile-first-Muster wie DetailHeader „Mehr“.
// - `display: contents` haelt die Tags als direkte Kinder der umgebenden
//   Badge-Zeile (Flex-Wrap des Aufrufers), damit sich am Umbruch ab `md`
//   nichts aendert.
// - Der Knopf liegt mit `relative z-10` ueber dem Stretched-Link einer
//   EntityCard; ein Klick klappt die Tags auf, statt die Karte zu oeffnen.
// - Wie bei ExpandableText bleibt der Knopf nach dem Aufklappen stehen
//   („Weniger“), damit der Fokus nicht ins Leere faellt.

interface TagListProps {
  tags: readonly string[]
  /** Rendert ein einzelnes Tag (Badge / MetaPill der jeweiligen Seite). */
  renderTag: (tag: string) => ReactNode
  /** Sichtbare Tags unterhalb `md` (Standard 3). */
  max?: number
  /** Accessible Name der Gruppe (z. B. „Tags“). */
  label?: string
}

export function TagList({ tags, renderTag, max = 3, label }: TagListProps) {
  const { t } = useTranslation('common')
  const [expanded, setExpanded] = useState(false)
  const restId = useId()
  if (tags.length === 0) return null

  const head = tags.slice(0, max)
  const rest = tags.slice(max)

  return (
    <span className="contents" role={label ? 'group' : undefined} aria-label={label} data-testid="tag-list">
      {head.map((tag) => (
        <span key={tag} className="contents" data-tag="">
          {renderTag(tag)}
        </span>
      ))}
      {rest.length > 0 ? (
        <>
          <span
            id={restId}
            className={cn(expanded ? 'contents' : 'hidden', 'md:contents')}
            data-testid="tag-list-rest"
          >
            {rest.map((tag) => (
              <span key={tag} className="contents" data-tag="">
                {renderTag(tag)}
              </span>
            ))}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            // Trefferflaeche 44 px Hoehe unter `md` (R-P9, Mobil-Spec; DL §11
            // Floor 32 px erfuellt). Sichtbar ist nur die innere Kapsel im
            // Badge-Stil, damit „+n“ nicht als Kreis aus der Tag-Reihe faellt.
            // `-my-2.5` laesst die Trefferflaeche in den Zeilenabstand ragen,
            // statt die Tag-Zeile auf 44 px zu strecken.
            className="group relative z-10 -my-2.5 h-11 px-0 hover:bg-transparent md:hidden"
            aria-expanded={expanded}
            aria-controls={restId}
            // Sichtbar nur „+n“ (Zahl, kein Fliesstext); der Accessible Name
            // nennt die Aktion, die Gruppe „Tags“ den Kontext.
            aria-label={expanded ? undefined : t('actions.showMoreCount', { count: rest.length })}
            data-testid="tag-list-more"
            onClick={() => setExpanded((open) => !open)}
          >
            <span className="rounded-full border px-2.5 py-0.5 text-xs font-semibold tabular-nums group-hover:bg-accent">
              {expanded ? t('actions.showLess') : `+${rest.length}`}
            </span>
          </Button>
        </>
      ) : null}
    </span>
  )
}
