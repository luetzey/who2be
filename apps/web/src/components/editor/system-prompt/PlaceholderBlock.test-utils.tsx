// PlaceholderBlock.test-utils.tsx — Testhelfer fuer PlaceholderBlock.
// Exportiert die Pill-Komponente als eigenstaendiges React-FC (ohne BlockNote-
// Kontext), damit Tests sie direkt rendern koennen.
// NICHT im Produktions-Bundle verwendet — nur von *.test.tsx importiert.

import { BookOpen, Calendar, FileText, User, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PlaceholderKind } from './PlaceholderBlock'

interface KindMeta {
  icon: React.FC<{ className?: string }>
  pillClass: string
  labelPrefix: string
}

// Kopie von KIND_META aus PlaceholderBlock — bewusste Duplizierung, damit
// der Test-Export ohne den BlockNote-Import-Overhead auskommt.
export const KIND_META_TEST_EXPORT: Record<PlaceholderKind, KindMeta> = {
  playbook: {
    icon: BookOpen,
    pillClass: 'bg-pill-playbook text-pill-playbook-fg border-pill-playbook-fg/25',
    labelPrefix: 'Playbook',
  },
  resource: {
    icon: FileText,
    pillClass: 'bg-pill-resource text-pill-resource-fg border-pill-resource-fg/25',
    labelPrefix: 'Resource',
  },
  'persona-field': {
    icon: User,
    pillClass: 'bg-pill-persona text-pill-persona-fg border-pill-persona-fg/25',
    labelPrefix: 'Persona',
  },
  date: {
    icon: Calendar,
    pillClass: 'bg-pill-date text-pill-date-fg border-pill-date-fg/25',
    labelPrefix: 'Datum',
  },
  'tools-overview': {
    icon: Wrench,
    pillClass: 'bg-pill-tools text-pill-tools-fg border-pill-tools-fg/25',
    labelPrefix: 'MCP-Tools',
  },
}

interface PlaceholderPillProps {
  kind: PlaceholderKind
  target_id: string
  label: string
}

/**
 * Standalone-Pill-Rendering ohne BlockNote-Kontext — nur fuer Tests.
 */
export function PlaceholderPill({ kind, label }: PlaceholderPillProps) {
  const meta = KIND_META_TEST_EXPORT[kind]
  const Icon = meta.icon
  return (
    <span
      data-testid={`placeholder-pill-${kind}`}
      className={cn(
        'inline-flex cursor-pointer items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs leading-none font-medium select-none',
        meta.pillClass,
      )}
    >
      <Icon className="h-3 w-3 shrink-0" />
      {label !== '' ? label : meta.labelPrefix}
    </span>
  )
}
