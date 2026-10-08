// Geteilte Filter-Logik fuer die Listen-Seiten (Personas, Playbooks,
// Resources, System-Prompts). Rein funktional, kein React — lebt in `@/lib`,
// weil die vier Feature-Listen dieselbe Status-/Quick-Filter-Semantik teilen
// und ein Cross-Feature-Import verboten waere.

import type { VersionStatus } from '@/api/types'

// Reihenfolge = Lifecycle (Draft → Review → Active → Inactive), damit die
// Quick-Filter-Chips und die Dashboard-Donut-Legende identisch sortiert sind.
export const LIST_STATUSES: readonly VersionStatus[] = [
  'draft',
  'review',
  'active',
  'inactive',
] as const

// `attention` ist ein abgeleiteter Sammel-Filter (Nutzer-Entscheidung 1c):
// alles, was Handlungsbedarf signalisiert. `all` = kein Status-Filter.
export type StatusFilterValue = VersionStatus | 'attention' | 'all'

export const STATUS_FILTER_VALUES: readonly StatusFilterValue[] = [
  'all',
  'attention',
  ...LIST_STATUSES,
] as const

export function isStatusFilterValue(value: string): value is StatusFilterValue {
  return (STATUS_FILTER_VALUES as readonly string[]).includes(value)
}

// --- Generische Filterleiste (Filter-Standard F0, E1/E3) ---------------------
// Listen ausserhalb des Versionsstatus (Faelle, Gedaechtnis) liefern ihre
// Status-Chips und Facetten fertig uebersetzt; die Leiste rendert nur.

/** Ein Status-Chip (Einfachauswahl). `count: null` = keine Zahl anzeigen. */
export interface StatusChipOption {
  value: string
  label: string
  count: number | null
  /** Status-Token fuer den Punkt: `active` → `var(--status-active)`. */
  token?: string
  /** Sammel-Chip mit Hinweis-Icon und Brand-Variante (z. B. „Braucht Aufmerksamkeit“). */
  accent?: boolean
  /** Bleibt auch bei 0 stehen (Standardwert der Liste). */
  keepWhenZero?: boolean
}

/** Ein Wert einer Facette. `count` nur bei echten Zahlen fuer genau diese Auswahl. */
export interface FacetOption {
  value: string
  label: string
  count?: number
  /** Hinweis unter dem Select, solange dieser Wert gewaehlt ist. */
  hint?: string
}

/** Eine generische Facette (natives Select, Einfachauswahl, '' = „Alle …“). */
export interface FacetSpec {
  key: string
  label: string
  allLabel: string
  options: FacetOption[]
  value: string
  onChange: (value: string) => void
}

/**
 * Chip-Regel: ein Chip mit 0 entfaellt, ausser er ist gewaehlt oder als
 * Standardwert markiert. Unbekannte Zahl (`null`) blendet nie aus.
 */
export function visibleStatusChips(
  options: readonly StatusChipOption[],
  selected: string,
): StatusChipOption[] {
  return options.filter(
    (option) => option.count !== 0 || option.value === selected || option.keepWhenZero === true,
  )
}

// Minimal-Sicht auf ein Listen-Item, die fuer den Status-Filter reicht.
export interface StatusLike {
  status: VersionStatus | undefined
  hasPendingDraft: boolean | undefined
}

// „Braucht Aufmerksamkeit": ein Entwurf, eine Review-Version oder eine aktive
// Version mit offenem Draft/Review dahinter (`has_pending_draft`). Bewusst
// NICHT `inactive` — inaktive Bestaende sind absichtlich stillgelegt.
export function needsAttention(item: StatusLike): boolean {
  return item.status === 'draft' || item.status === 'review' || item.hasPendingDraft === true
}

export function matchesStatusFilter(item: StatusLike, value: StatusFilterValue): boolean {
  if (value === 'all') return true
  if (value === 'attention') return needsAttention(item)
  return item.status === value
}

// Zaehler pro Quick-Filter — inklusive `all` und `attention`. Wird ueber die
// bereits nach Text/Tag/Typ eingegrenzte Basismenge gerechnet (faceted counts),
// damit die Chip-Zahlen zeigen, was ein Klick tatsaechlich ergaebe.
export type StatusCounts = Record<StatusFilterValue, number>

export function countByStatus(items: readonly StatusLike[]): StatusCounts {
  const counts: StatusCounts = {
    all: items.length,
    attention: 0,
    draft: 0,
    review: 0,
    active: 0,
    inactive: 0,
  }
  for (const item of items) {
    if (needsAttention(item)) counts.attention += 1
    if (item.status !== undefined) counts[item.status] += 1
  }
  return counts
}
