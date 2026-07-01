import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'

import type { StatusDistribution, VersionStatus } from '@/api/types'

import { statusLabel } from '../lib/statusLabel'

interface StatusDonutProps {
  label: string
  distribution: StatusDistribution
  // Optional: macht die Legenden-Eintraege klickbar → verlinkt auf die
  // nach diesem Status vorgefilterte Listen-Seite (`…?status=<status>`).
  hrefFor?: (status: VersionStatus) => string
}

// Lifecycle-Reihenfolge des Rings: Draft → Review → Active → Inactive.
// Farben kommen aus den `--status-*`-Tokens (`src/styles/globals.css`).
const SEGMENTS: readonly VersionStatus[] = ['draft', 'review', 'active', 'inactive']

// viewBox-Geometrie: r so gewaehlt, dass der Umfang exakt 100 ist
// (2·π·r = 100 ⇒ r = 50/π). Dadurch sind `stroke-dasharray`-Laengen
// direkt Prozente.
const CIRCUMFERENCE = 100
const RADIUS = 50 / Math.PI

function strokeFor(status: VersionStatus): CSSProperties {
  return { stroke: `var(--status-${status})` }
}

export function StatusDonut({ label, distribution, hrefFor }: StatusDonutProps) {
  const total = SEGMENTS.reduce((sum, status) => sum + (distribution[status] ?? 0), 0)

  const ariaLabel = `${label}: ${SEGMENTS.map(
    (status) => `${statusLabel(status)} ${distribution[status] ?? 0}`,
  ).join(', ')}`

  // Offset-Akkumulation: jedes Segment startet dort, wo das vorige endet.
  // Start bei 12 Uhr (Default-Stroke beginnt bei 3 Uhr → +25 zurueck).
  let accumulated = 0

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative size-32">
        <svg viewBox="0 0 36 36" className="size-full -rotate-90" role="img" aria-label={ariaLabel}>
          <circle
            cx="18"
            cy="18"
            r={RADIUS}
            fill="none"
            className="stroke-muted"
            strokeWidth="4"
          />
          {total > 0
            ? SEGMENTS.map((status) => {
                const value = distribution[status] ?? 0
                if (value === 0) return null
                const dash = (value / total) * CIRCUMFERENCE
                const offset = CIRCUMFERENCE * 0.25 - accumulated
                accumulated += dash
                return (
                  <circle
                    key={status}
                    cx="18"
                    cy="18"
                    r={RADIUS}
                    fill="none"
                    style={strokeFor(status)}
                    strokeWidth="4"
                    strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
                    strokeDashoffset={offset}
                    data-status={status}
                  />
                )
              })
            : null}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tracking-tight">{total}</span>
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
      </div>
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {SEGMENTS.map((status) => {
          const dot = (
            <span
              className="inline-block size-2 rounded-full"
              style={{ backgroundColor: `var(--status-${status})` }}
              aria-hidden="true"
            />
          )
          const text = `${statusLabel(status)}: ${distribution[status] ?? 0}`
          return (
            <li key={status} className="flex items-center gap-2">
              {hrefFor ? (
                <Link
                  to={hrefFor(status)}
                  className="flex items-center gap-2 rounded-sm hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
                >
                  {dot}
                  {text}
                </Link>
              ) : (
                <>
                  {dot}
                  {text}
                </>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
