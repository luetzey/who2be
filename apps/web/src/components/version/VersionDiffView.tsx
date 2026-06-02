import type { VersionDiff, VersionDiffOp } from '@/api/types'
import { Badge } from '@/components/ui/badge'

import type { StatusBadgeVariant } from './versionStatus'

interface VersionDiffViewProps {
  diff: VersionDiff
}

const OP_LABEL: Record<VersionDiffOp, string> = {
  added: 'Hinzugefügt',
  removed: 'Entfernt',
  changed: 'Geändert',
}

const OP_VARIANT: Record<VersionDiffOp, StatusBadgeVariant> = {
  added: 'default',
  removed: 'destructive',
  changed: 'secondary',
}

// Rendert einen unbekannten JSON-Wert kompakt als Text. Strings unverändert,
// alles andere als (gekürztes) JSON — die Diff-Ansicht ist read-only.
function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—'
  }
  if (typeof value === 'string') {
    return value === '' ? '(leer)' : value
  }
  const serialized = JSON.stringify(value)
  return serialized.length > 200 ? `${serialized.slice(0, 200)}…` : serialized
}

/**
 * Read-only Darstellung eines serverseitig berechneten Versions-Diffs
 * (Track A). Listet je Änderung Pfad, Operation und Vorher/Nachher.
 */
export function VersionDiffView({ diff }: VersionDiffViewProps) {
  const againstLabel =
    diff.against_version !== null ? `v${diff.against_version}` : 'kein Vergleichsstand'

  if (diff.identical) {
    return (
      <p className="text-sm text-muted-foreground">
        Keine Unterschiede zwischen v{diff.version} und {againstLabel}.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        Vergleich v{diff.version} gegen {againstLabel}
      </p>
      <ul className="flex flex-col gap-2" aria-label="Änderungen">
        {diff.changes.map((change) => (
          <li
            key={`${change.op}-${change.path}`}
            className="rounded-md border border-border bg-muted/30 p-2"
          >
            <div className="flex items-center gap-2">
              <Badge variant={OP_VARIANT[change.op]}>{OP_LABEL[change.op]}</Badge>
              <code className="text-xs break-all text-foreground">{change.path}</code>
            </div>
            {change.op !== 'added' ? (
              <p className="mt-1 text-xs text-muted-foreground">
                <span className="font-medium">Vorher:</span> {formatValue(change.before)}
              </p>
            ) : null}
            {change.op !== 'removed' ? (
              <p className="mt-1 text-xs text-muted-foreground">
                <span className="font-medium">Nachher:</span> {formatValue(change.after)}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
