import type { CSSProperties } from 'react'

import type { CaseStatus } from '@/api/types'

// Punkt-Token je Fall-Status (D-Delta §0, E-Delta §6.1). `in_progress` teilt
// sich `review` mit `triaged` und unterscheidet sich durch die Ringform.
const STATUS_TOKEN: Record<CaseStatus, string> = {
  open: 'draft',
  reopened: 'draft',
  triaged: 'review',
  in_progress: 'review',
  addressed: 'active',
  verified: 'active',
  dismissed: 'inactive',
}

// Punktform je Status (E-Delta §6.1, §8): hohl bei „Geändert“, Ring bei „In
// Arbeit“, sonst gefuellt. Die Form unterscheidet ohne Farbe; die Bedeutung
// traegt das Wort daneben, der Punkt ist `aria-hidden`.
type DotShape = 'filled' | 'hollow' | 'ring'
const STATUS_SHAPE: Partial<Record<CaseStatus, DotShape>> = {
  addressed: 'hollow',
  in_progress: 'ring',
}

const SHAPE_CLASS: Record<DotShape, string> = {
  filled: 'inline-block size-2 shrink-0 rounded-full',
  hollow: 'inline-block size-2 shrink-0 rounded-full border-2',
  ring: 'inline-block size-2 shrink-0 rounded-full ring-2 ring-offset-1 ring-offset-background',
}

/**
 * Status-Punkt einer Rueckmeldung, an allen Orten in derselben Form: Liste,
 * Detail und Review-Ergebnis (E5c).
 */
export function CaseStatusDot({ status }: { status: CaseStatus }) {
  const token = STATUS_TOKEN[status]
  const shape = STATUS_SHAPE[status] ?? 'filled'
  const color = `var(--status-${token})`
  const style: CSSProperties & Record<'--tw-ring-color', string> =
    shape === 'hollow'
      ? { borderColor: color, '--tw-ring-color': color }
      : { backgroundColor: color, '--tw-ring-color': color }
  return (
    <span
      className={SHAPE_CLASS[shape]}
      style={style}
      data-shape={shape}
      data-testid="case-status-dot"
      aria-hidden="true"
    />
  )
}
