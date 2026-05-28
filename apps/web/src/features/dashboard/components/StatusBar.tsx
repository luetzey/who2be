import type { CSSProperties } from 'react'

import type { StatusDistribution, VersionStatus } from '@/api/types'

import { statusLabel } from '../lib/statusLabel'

interface StatusBarProps {
  label: string
  distribution: StatusDistribution
}

// Reihenfolge im Stacked-Bar bewusst (Lifecycle): Draft → Review → Active
// → Inactive. Tokens leben in `src/styles/globals.css` (--status-*).
const SEGMENTS: readonly VersionStatus[] = ['draft', 'review', 'active', 'inactive']

function fillFor(status: VersionStatus): CSSProperties {
  return { backgroundColor: `var(--status-${status})` }
}

export function StatusBar({ label, distribution }: StatusBarProps) {
  const total = SEGMENTS.reduce((sum, status) => sum + (distribution[status] ?? 0), 0)

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{total} gesamt</span>
      </div>
      {total === 0 ? (
        <div
          className="h-2 w-full rounded-full bg-muted"
          aria-label={`${label}: keine Versionen`}
        />
      ) : (
        <div
          className="grid h-2 w-full overflow-hidden rounded-full bg-muted"
          style={{
            gridTemplateColumns: SEGMENTS.map(
              (status) => `${distribution[status] ?? 0}fr`,
            ).join(' '),
          }}
          role="img"
          aria-label={`${label}: ${SEGMENTS.map(
            (status) => `${statusLabel(status)} ${distribution[status] ?? 0}`,
          ).join(', ')}`}
        >
          {SEGMENTS.map((status) => (
            <span
              key={status}
              style={fillFor(status)}
              data-status={status}
              aria-hidden="true"
            />
          ))}
        </div>
      )}
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {SEGMENTS.map((status) => (
          <li key={status} className="flex items-center gap-1.5">
            <span
              className="inline-block size-2 rounded-full"
              style={fillFor(status)}
              aria-hidden="true"
            />
            {statusLabel(status)}: {distribution[status] ?? 0}
          </li>
        ))}
      </ul>
    </div>
  )
}
