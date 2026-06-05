import { useTranslation } from 'react-i18next'

import type { VersionDiff, VersionDiffOp } from '@/api/types'
import { Badge } from '@/components/ui/badge'

import type { StatusBadgeVariant } from './versionStatus'

interface VersionDiffViewProps {
  diff: VersionDiff
}

const OP_KEY: Record<VersionDiffOp, string> = {
  added: 'diff.added',
  removed: 'diff.removed',
  changed: 'diff.changed',
}

const OP_VARIANT: Record<VersionDiffOp, StatusBadgeVariant> = {
  added: 'default',
  removed: 'destructive',
  changed: 'secondary',
}

// Rendert einen unbekannten JSON-Wert kompakt als Text. Strings unverändert,
// alles andere als (gekürztes) JSON — die Diff-Ansicht ist read-only.
function formatValue(value: unknown, emptyLabel: string): string {
  if (value === null || value === undefined) {
    return '—'
  }
  if (typeof value === 'string') {
    return value === '' ? emptyLabel : value
  }
  const serialized = JSON.stringify(value)
  return serialized.length > 200 ? `${serialized.slice(0, 200)}…` : serialized
}

/**
 * Read-only Darstellung eines serverseitig berechneten Versions-Diffs
 * (Track A). Listet je Änderung Pfad, Operation und Vorher/Nachher.
 */
export function VersionDiffView({ diff }: VersionDiffViewProps) {
  const { t } = useTranslation('version')
  const emptyLabel = t('diff.empty')
  const againstLabel =
    diff.against_version !== null ? `v${diff.against_version}` : t('diff.noBaseline')

  if (diff.identical) {
    return (
      <p className="text-sm text-muted-foreground">
        {t('diff.identical', { version: diff.version, against: againstLabel })}
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        {t('diff.comparing', { version: diff.version, against: againstLabel })}
      </p>
      <ul className="flex flex-col gap-2" aria-label={t('diff.changesLabel')}>
        {diff.changes.map((change) => (
          <li
            key={`${change.op}-${change.path}`}
            className="rounded-md border border-border bg-muted/30 p-2"
          >
            <div className="flex items-center gap-2">
              <Badge variant={OP_VARIANT[change.op]}>{t(OP_KEY[change.op])}</Badge>
              <code className="text-xs break-all text-foreground">{change.path}</code>
            </div>
            {change.op !== 'added' ? (
              <p className="mt-1 text-xs text-muted-foreground">
                <span className="font-medium">{t('diff.before')}</span>{' '}
                {formatValue(change.before, emptyLabel)}
              </p>
            ) : null}
            {change.op !== 'removed' ? (
              <p className="mt-1 text-xs text-muted-foreground">
                <span className="font-medium">{t('diff.after')}</span>{' '}
                {formatValue(change.after, emptyLabel)}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
