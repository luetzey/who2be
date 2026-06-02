import type { LucideIcon } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface KpiCardProps {
  label: string
  value: number
  icon: LucideIcon
  description?: string
}

// KPI-Karte mit Mini-Visual: das `icon` in einem getoenten Quadrat gibt der
// nackten Zahl einen visuellen Anker (Track G). Icons folgen der
// Design-Sprache (`text-muted-foreground`, nie `text-brand`).
export function KpiCard({ label, value, icon: Icon, description }: KpiCardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <span
          className="flex size-8 items-center justify-center rounded-md bg-muted text-muted-foreground"
          aria-hidden="true"
        >
          <Icon className="size-4" />
        </span>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tracking-tight">{value}</div>
        {description ? <p className="mt-1 text-xs text-muted-foreground">{description}</p> : null}
      </CardContent>
    </Card>
  )
}
