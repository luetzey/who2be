import { ArrowRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { ProvenanceEntry } from '@/api/types'
import { Badge } from '@/components/ui/badge'

import { statusBadgeVariant, statusLabel } from './versionStatus'

interface ProvenanceListProps {
  entries: ProvenanceEntry[]
}

/**
 * Read-only Status-Historie einer Version ("warum aktiv", Track A). Rendert die
 * `status_history`-Kette chronologisch: Übergang, Zeitpunkt und optionale Notiz.
 */
export function ProvenanceList({ entries }: ProvenanceListProps) {
  const { t } = useTranslation('version')
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">{t('provenance.emptyForVersion')}</p>
    )
  }

  return (
    <ol className="flex flex-col gap-2" aria-label={t('provenance.listLabel')}>
      {entries.map((entry) => (
        <li key={entry.id} className="rounded-md border border-border bg-muted/30 p-2">
          <div className="flex flex-wrap items-center gap-2">
            {entry.from_status !== null ? (
              <>
                <Badge variant={statusBadgeVariant(entry.from_status)}>
                  {statusLabel(entry.from_status)}
                </Badge>
                <ArrowRight className="h-3 w-3 text-muted-foreground" aria-hidden />
              </>
            ) : null}
            <Badge variant={statusBadgeVariant(entry.to_status)}>
              {statusLabel(entry.to_status)}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {new Date(entry.changed_at).toLocaleString()}
            </span>
          </div>
          {entry.note !== null && entry.note !== '' ? (
            <p className="mt-1 text-xs text-muted-foreground">{entry.note}</p>
          ) : null}
        </li>
      ))}
    </ol>
  )
}
