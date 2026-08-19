import { Fragment } from 'react'
import { Link } from 'react-router-dom'

import type { StatusDistribution, VersionStatus } from '@/api/types'
import { statusLabel } from '@/components/version'

interface StatusBarProps {
  label: string
  distribution: StatusDistribution
  // Optional: macht die Zahlen-Ablesung klickbar → verlinkt auf die nach
  // diesem Status vorgefilterte Listen-Seite (`…?status=<status>`).
  hrefFor?: (status: VersionStatus) => string
}

// Lifecycle-Reihenfolge des Balkens: Draft → Review → Active → Inactive.
// Farben kommen aus den `--status-*`-Tokens (`src/styles/globals.css`), die
// laut Token-Kommentar nur inline via CSS-Var konsumiert werden (kein
// `bg-status-*`-Utility) — genau wie StatusBadge/-Donut es taten.
const SEGMENTS: readonly VersionStatus[] = ['draft', 'review', 'active', 'inactive']

// Segmentierter Statusbalken pro Entity-Typ (Warm-Citrus-Redesign, ersetzt den
// fruehreren StatusDonut). Der Balken selbst ist ein `role="img"` mit
// sprechendem Label; die Klick-Navigation liegt in der Zahlen-Ablesung rechts,
// damit im `img` keine interaktiven Kinder haengen (A11y).
export function StatusBar({ label, distribution, hrefFor }: StatusBarProps) {
  const total = SEGMENTS.reduce((sum, status) => sum + (distribution[status] ?? 0), 0)

  const ariaLabel = `${label}: ${SEGMENTS.map(
    (status) => `${statusLabel(status)} ${distribution[status] ?? 0}`,
  ).join(', ')}`

  return (
    <div className="flex items-center gap-4">
      <span className="w-24 flex-none text-sm font-medium">{label}</span>
      <div
        role="img"
        aria-label={ariaLabel}
        className="flex h-3 flex-1 overflow-hidden rounded-md bg-muted"
      >
        {total > 0
          ? SEGMENTS.map((status) => {
              const value = distribution[status] ?? 0
              if (value === 0) return null
              return (
                <span
                  key={status}
                  data-status={status}
                  // Prozent-Breite + Token-Farbe sind datengetrieben und werden
                  // – wie bei StatusBadge – inline ueber die CSS-Var gesetzt.
                  style={{
                    width: `${(value / total) * 100}%`,
                    backgroundColor: `var(--status-${status})`,
                  }}
                />
              )
            })
          : null}
      </div>
      <span className="flex-none text-right text-xs text-muted-foreground tabular-nums">
        {SEGMENTS.map((status, index) => {
          const value = distribution[status] ?? 0
          const isActive = status === 'active'
          const numberLabel = `${statusLabel(status)}: ${value}`
          const content = hrefFor ? (
            <Link
              to={hrefFor(status)}
              aria-label={numberLabel}
              className={
                isActive
                  ? 'rounded-sm font-semibold text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none'
                  : 'rounded-sm hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none'
              }
            >
              {value}
            </Link>
          ) : (
            <span className={isActive ? 'font-semibold text-foreground' : undefined}>{value}</span>
          )
          return (
            <Fragment key={status}>
              {index > 0 ? <span aria-hidden="true"> · </span> : null}
              {content}
            </Fragment>
          )
        })}
      </span>
    </div>
  )
}
