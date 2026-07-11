import type { LucideIcon } from 'lucide-react'

import { EntityIcon, type EntityTone } from '@/components/data'
import { Card, CardContent } from '@/components/ui/card'

interface KpiCardProps {
  label: string
  value: number
  icon: LucideIcon
  // Kategorie-Tinte der Icon-Kachel (EntityIcon): persona/playbook/resource
  // geben der nackten Zahl einen visuellen Anker (Warm-Citrus-Redesign).
  tone: EntityTone
  description?: string
}

// KPI-Karte: getoente EntityIcon-Kachel links, Label + tabellarische Zahl
// rechts. Icons folgen der Design-Sprache (EntityIcon traegt die Pill-Tinte,
// nie `text-brand`).
export function KpiCard({ label, value, icon, tone, description }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <EntityIcon icon={icon} tone={tone} size="sm" />
        <div className="min-w-0">
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
          {description ? (
            <p className="mt-1 text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
