import { ArrowRight, Bell, CircleCheck } from 'lucide-react'
import { Fragment } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { InboxCounts } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

// Hoechstens so viele Arten stehen in der Zeile, der Rest als „+ n weitere“
// (Spec §2.5).
export const INBOX_SUMMARY_MAX_KINDS = 3

type SummaryKind = 'followUps' | 'memory' | 'versions' | 'cases'

/**
 * Arten, die in die Glocke zaehlen, in der Reihenfolge aus Spec §2.2. Muster
 * zaehlen nie; Versionen nur fuer admin (nur admin darf `review -> active`).
 */
function countingKinds(counts: InboxCounts, isAdmin: boolean): { kind: SummaryKind; count: number }[] {
  const versions =
    isAdmin && counts.versions_review !== null
      ? counts.versions_review + (counts.system_prompts_review ?? 0)
      : 0
  const all: { kind: SummaryKind; count: number }[] = [
    { kind: 'followUps', count: counts.follow_ups_due ?? 0 },
    { kind: 'memory', count: counts.memory_approval ?? 0 },
    { kind: 'versions', count: versions },
    { kind: 'cases', count: counts.cases_open ?? 0 },
  ]
  return all.filter((entry) => entry.count > 0)
}

const ROW = 'flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4'
const TILE =
  'inline-flex size-9 flex-none items-center justify-center rounded-lg bg-card shadow-card [&_svg]:size-5'

interface InboxSummaryProps {
  /** Aus `useInboxCounts` — `null` waehrend des Ladens oder nach einem Fehler. */
  counts: InboxCounts | null
  /** `true`, wenn der letzte Abruf scheiterte: dann entfaellt die Zeile. */
  failed: boolean
  isAdmin: boolean
  /** Ziel von „Alle ansehen“, bereits workspace-praefixiert. */
  href: string
}

/**
 * Eine Zeile „n Aufgaben warten auf dich“ (Navigation & Transparenz W1-c,
 * Spec §2.5): ersetzt das Band „Braucht jetzt deine Aufmerksamkeit“. Card-
 * Rand, keine Brand-Flaeche. Die Zahl kommt aus derselben Quelle wie Glocke
 * und Seite „Zu erledigen“ (`useInboxCounts`) — drei Orte, eine Zahl.
 *
 * Zustaende: Laden → Skeleton (nie eine behauptete „0“); Fehler → keine
 * Zeile (die Glocke zeigt dann ebenfalls keinen Zaehler); 0 → „Nichts zu
 * erledigen.“ ohne Knopf.
 */
export function InboxSummary({ counts, failed, isAdmin, href }: InboxSummaryProps) {
  const { t } = useTranslation('dashboard')

  if (counts === null) {
    if (failed) return null
    return (
      <div
        className={ROW}
        role="status"
        aria-label={t('inbox.loading')}
        data-testid="inbox-summary-loading"
      >
        <Skeleton className="size-9 flex-none rounded-lg" />
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <Skeleton className="h-4 w-48 max-w-full" />
          <Skeleton className="h-3 w-64 max-w-full" />
        </div>
      </div>
    )
  }

  if (counts.total === 0) {
    return (
      <section className={ROW} aria-label={t('inbox.ariaLabel')} data-testid="inbox-summary">
        <span className={TILE}>
          <CircleCheck aria-hidden="true" />
        </span>
        <p className="min-w-0 flex-1 text-sm font-semibold">{t('inbox.clear')}</p>
      </section>
    )
  }

  const kinds = countingKinds(counts, isAdmin)
  const shown = kinds.slice(0, INBOX_SUMMARY_MAX_KINDS)
  const rest = kinds.length - shown.length

  return (
    <section className={ROW} aria-label={t('inbox.ariaLabel')} data-testid="inbox-summary">
      <span className={TILE}>
        <Bell aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">{t('inbox.title', { count: counts.total })}</p>
        {shown.length > 0 ? (
          <p className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
            {shown.map((entry, index) => (
              <Fragment key={entry.kind}>
                {index > 0 ? <span aria-hidden="true">·</span> : null}
                <span>{t(`inbox.kind.${entry.kind}`, { count: entry.count })}</span>
              </Fragment>
            ))}
            {rest > 0 ? (
              <>
                <span aria-hidden="true">·</span>
                <span>{t('inbox.more', { count: rest })}</span>
              </>
            ) : null}
          </p>
        ) : null}
      </div>
      {/* Unter `md` volle Breite und 44 px Trefferflaeche (Spec §2.5). */}
      <Button asChild variant="outline" className="h-11 w-full md:h-9 md:w-auto">
        <Link to={href}>
          {t('inbox.action')}
          <ArrowRight />
        </Link>
      </Button>
    </section>
  )
}
