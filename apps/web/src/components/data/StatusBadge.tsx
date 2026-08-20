import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { cn } from '@/lib/utils'

// Kompaktes Status-Label fuer Listen-Zeilen. Farbe kommt aus den
// `--status-*`-Tokens (globals.css), ist aber nie das alleinige Signal:
// Punkt + Text-Label zusammen (Design-Language §11, A11y-Minimum).
//
// Lebt unter `components/data/`, weil es ueber alle vier Listen-Features
// geteilt wird und semantisch Datendarstellung ist.

interface StatusBadgeProps {
  status: VersionStatus | undefined
  // Aktive Version mit offenem Draft/Review dahinter — extra Marker, weil der
  // reine `active`-Status den Handlungsbedarf sonst verstecken wuerde.
  pendingDraft?: boolean
  className?: string
  /** Optionaler `data-testid`-Anker fuer E2E-Selektoren (ADR-0041 Phase 4). */
  testId?: string
}

export function StatusBadge({ status, pendingDraft, className, testId }: StatusBadgeProps) {
  const { t } = useTranslation(['common', 'data'])
  if (status === undefined) return null

  return (
    <span className={cn('inline-flex items-center gap-1.5', className)} data-testid={testId}>
      <span
        className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-xs font-medium text-muted-foreground"
        data-status={status}
      >
        <span
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: `var(--status-${status})` }}
          aria-hidden="true"
        />
        {t(`common:status.${status}`)}
      </span>
      {pendingDraft ? (
        <span
          className="rounded-full border border-[var(--status-draft)]/50 px-2 py-0.5 text-xs font-medium text-muted-foreground"
          data-testid="status-badge-pending-draft"
        >
          {t('data:filter.pendingDraft')}
        </span>
      ) : null}
    </span>
  )
}
