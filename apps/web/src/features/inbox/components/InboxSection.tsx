import { ArrowRight } from 'lucide-react'
import { type ComponentType, type ReactNode, type SVGProps, useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { CountPill } from '@/components/data/CountPill'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/** Hoechstens so viele Zeilen je Art (Spec §2.4); der Rest steht in der Fachliste. */
export const INBOX_ROWS_PER_KIND = 5

export interface InboxRow {
  id: string
  title: string
  /** Agent · Baustein · Alter · ggf. „wieder offen“ — fertig uebersetzt. */
  meta?: ReactNode
  /** Pill neben dem Titel, z. B. „seit 1 Tag fällig“. */
  badge?: ReactNode
  /** Genau eine Aktion: Link auf die Stelle, an der man erledigt (N7 a). */
  actionLabel: string
  /** Zugaenglicher Name der Aktion, wenn das Wort allein nicht reicht. */
  actionAriaLabel?: string
  href: string
}

interface InboxSectionProps {
  kind: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  title: string
  count: number
  hint?: string
  rows: InboxRow[] | null
  loading: boolean
  failed: boolean
  onRetry: () => void
  /** „Alle n ansehen“ — nur, wenn die Art mehr hat, als hier steht. */
  showAll?: { label: string; href: string } | null
  /** Die eine terminierte Art (Nachkontrolle) bekommt die Hauptaktion. */
  primary?: boolean
  /** Ersatz fuer Zeilen, wenn es (noch) keine Einzelansicht gibt. */
  note?: ReactNode
}

/**
 * Ein Abschnitt der Seite „Zu erledigen“ (Spec §2.4, §8): `section` mit `h2`,
 * die Zahl steht im zugaenglichen Namen der Ueberschrift („Gedächtnis zur
 * Freigabe, 2“), die sichtbare Zahl-Pill ist `aria-hidden`. Laden und Fehler
 * gelten nur fuer diesen Abschnitt — scheitert eine Liste, bleiben die
 * anderen stehen.
 */
export function InboxSection({
  kind,
  icon: Icon,
  title,
  count,
  hint,
  rows,
  loading,
  failed,
  onRetry,
  showAll,
  primary = false,
  note,
}: InboxSectionProps) {
  const { t } = useTranslation('inbox')
  const headingId = useId()
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-3"
      data-testid={`inbox-section-${kind}`}
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2
          id={headingId}
          className="flex items-center gap-2 text-base font-semibold"
          aria-label={t('section.heading', { title, count })}
        >
          <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span>{title}</span>
          <span aria-hidden="true">
            <CountPill count={count} />
          </span>
        </h2>
        {hint ? <p className="hidden text-sm text-muted-foreground md:block">{hint}</p> : null}
      </div>

      {note ? (
        <Card className="px-4 py-3 text-sm text-muted-foreground">{note}</Card>
      ) : loading && rows === null ? (
        <LoadingState rows={Math.min(count, 3)} />
      ) : failed ? (
        <Card
          role="alert"
          className="flex flex-col items-start gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          data-testid={`inbox-section-${kind}-error`}
        >
          <p className="text-sm text-destructive">{t('sectionError')}</p>
          <Button type="button" variant="outline" size="sm" className="min-h-11 md:min-h-0" onClick={onRetry}>
            {t('retry')}
          </Button>
        </Card>
      ) : rows !== null && rows.length > 0 ? (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-border/60">
            {rows.map((row) => (
              <li
                key={row.id}
                className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <p className="line-clamp-2 min-w-0 text-sm font-medium wrap-anywhere md:line-clamp-1">
                      {row.title}
                    </p>
                    {row.badge}
                  </div>
                  {row.meta ? (
                    <p className="text-xs wrap-anywhere text-muted-foreground">{row.meta}</p>
                  ) : null}
                </div>
                <Button
                  asChild
                  variant={primary ? 'default' : 'outline'}
                  size="sm"
                  className="min-h-11 w-full shrink-0 sm:w-auto md:min-h-0"
                >
                  <Link to={row.href} aria-label={row.actionAriaLabel}>
                    {row.actionLabel}
                  </Link>
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {showAll ? (
        <Link
          to={showAll.href}
          className={cn(
            'inline-flex min-h-11 items-center gap-1 self-start rounded-sm text-sm font-medium underline-offset-4 hover:underline md:min-h-0',
            'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
          )}
        >
          {showAll.label}
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      ) : null}
    </section>
  )
}

export interface InboxLookRow {
  id: string
  title: string
  description?: string
  href: string
}

/**
 * „Zum Anschauen“ (Spec §2.4): Muster und — fuer editor — Versionen zur
 * Freigabe. Zaehlt nicht in die Glocke, deshalb `ghost`-Zeilen ohne Gewicht.
 */
export function InboxLookSection({ rows }: { rows: InboxLookRow[] }) {
  const { t } = useTranslation('inbox')
  const headingId = useId()
  if (rows.length === 0) return null
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3" data-testid="inbox-section-look">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 id={headingId} className="text-base font-semibold">
          {t('section.toLook')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('section.toLookHint')}</p>
      </div>
      <Card className="overflow-hidden">
        <ul className="divide-y divide-border/60">
          {rows.map((row) => (
            <li
              key={row.id}
              className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex min-w-0 flex-col gap-1">
                <p className="text-sm font-medium wrap-anywhere">{row.title}</p>
                {row.description ? (
                  <p className="text-xs wrap-anywhere text-muted-foreground">{row.description}</p>
                ) : null}
              </div>
              <Button asChild variant="ghost" size="sm" className="min-h-11 self-start sm:self-auto md:min-h-0">
                <Link to={row.href} aria-label={t('look.openAria', { title: row.title })}>
                  {t('look.open')}
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  )
}
